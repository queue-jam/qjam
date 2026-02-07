import logging
import uuid
from typing import Any, List, Dict

import yt_dlp
from fastapi import FastAPI, Form, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

# Assuming your types are in a local module
try:
    from backend.types import Room, Song, User
except ImportError:
    from .types import Room, Song, User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

connections: Dict[str, List[WebSocket]] = {}
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

rooms: list[Room] = []

def get_audio_url(youtube_url: str):
    """
    Helper to extract direct audio URL from YouTube.
    """
    ydl_opts = {"format": "bestaudio/best", "quiet": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=False)
        return info["url"]


@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    """
    Serves the main page and assigns a session_id cookie if missing.
    """
    response = templates.TemplateResponse("index.html", {"request": request})
    if not request.cookies.get("user_id"):
        new_user_id = uuid.uuid4().hex
        response.set_cookie(
            key="user_id", 
            value=new_user_id, 
            httponly=True
        )
        logger.info(f"Generated new User ID: {new_user_id}")
    else:
        logger.info(f"User returned with User ID: {request.cookies.get('user_id')}")

    return response

# --- UPDATED: Uses templates/join.html ---
@app.get("/join", response_class=HTMLResponse)
def get_join_page(request: Request, code: str):
    """
    Serves the 'Enter Name' page when a user scans the QR code.
    Ensures they get a user_id cookie if they are new.
    """
    user_id = request.cookies.get("user_id")
    new_cookie = None
    if not user_id:
        user_id = uuid.uuid4().hex
        new_cookie = user_id
    
    response = templates.TemplateResponse("join.html", {"request": request, "code": code})
    
    if new_cookie:
        response.set_cookie(key="user_id", value=new_cookie, httponly=True)
        
    return response

@app.post("/play", response_class=HTMLResponse)
async def play_stream(request: Request):
    session_id = request.cookies.get("session_id")
    user_id = request.cookies.get("user_id")

    if not session_id or not user_id:
        return "<p style='color:red;'>Session or User missing.</p>"

    current_room = Room.get_room_from_session_id(session_id, rooms)
    
    requesting_user = next((u for u in current_room.users if u.id == user_id), None)
    
    if not requesting_user or not requesting_user.host:
        return "<p style='color:red; padding: 10px;'>Only the host can play songs.</p>"

    if not current_room.queue:
        return "<p style='padding: 20px; text-align: center; color: #aaa;'>Queue is empty.</p>"

    current_room.current_song = current_room.queue[0] 
    
    await dequeue_song(
        session_id=session_id, 
        song_id=current_room.current_song.name,
        dequeuer_id=user_id
    )

    try:
        direct_stream_url = get_audio_url(current_room.current_song.yt_url)
        return templates.TemplateResponse("partials/player.html", {
            "request": request,
            "stream_url": direct_stream_url,
            "title": current_room.current_song.title,
            "artist": current_room.current_song.artist,
            "album_art": current_room.current_song.album_art
        })
    except Exception as e:
        logger.error(f"Error fetching audio: {e}")
        return f"<p style='color:red;'>Error: {str(e)}</p>"

async def dequeue_song(session_id: str, song_id: str, dequeuer_id: str) -> None:
    current_room: Room = Room.get_room_from_session_id(session_id, rooms)
    dequeuer: User = User.get_user_from_id(dequeuer_id, current_room.users)

    song_to_remove = next((s for s in current_room.queue if s.name == song_id), None)
    
    if not song_to_remove:
        return

    if not dequeuer.host and song_to_remove.added_by.id != dequeuer.id:
        raise HTTPException(status_code=403, detail="You can only remove your own songs.")

    current_room.queue.remove(song_to_remove)
    await broadcast_queue(session_id)

@app.delete("/{session_id}/queue/{song_id}")
async def remove_song_endpoint(request: Request, session_id: str, song_id: str):
    user_id = request.cookies.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="No user ID")

    await dequeue_song(session_id=session_id, song_id=song_id, dequeuer_id=user_id)
    return HTMLResponse(content="", status_code=200)

@app.post("/{session_id}/queue", response_class=HTMLResponse)
async def add_to_queue(request: Request, session_id: str, url: str = Form(...)):
    """
    HTMX Endpoint: Adds song to queue. Returns a fresh input field to reset the form.
    """
    user_id = request.cookies.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="No user ID found in cookies")

    await queue_song(session_id=session_id, song_url=url, queuer_id=user_id)
    
    await broadcast_queue(session_id)

    return ""
 

@app.post("/room", response_class=HTMLResponse)
def jam_room(request: Request, username: str = Form(...)):
    user_id: str = request.cookies.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="No user ID found in cookies")

    new_room: Room = create_room(host_id=user_id, host_name=username)
    current_user: User = User.get_user_from_id(user_id, new_room.users)
    response: Any = templates.TemplateResponse("room.html", {
        "request": request, 
        "room": new_room,
        "user": current_user,
    })
    response.set_cookie(key="session_id", value=new_room.session_id, httponly=True)
    
    return response

@app.post("/join", response_class=HTMLResponse)
def join_room(request: Request, session_id: str = Form(...), username: str = Form(...)):
    user_id: str = request.cookies.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="No user ID found in cookies")
    
    current_room: Room = Room.get_room_from_session_id(session_id, rooms)
    current_user: User = User(id=user_id, name=username, host=False)
    current_room.users.append(current_user)
    response: Any = templates.TemplateResponse("room.html", {
        "request": request, 
        "room": current_room,
        "user": current_user,
    })
    response.set_cookie(key="session_id", value=current_room.session_id, httponly=True)
    
    return response

def create_room(host_id: str, host_name: str) -> Room:
    room: Room = Room(
        session_id=uuid.uuid4().hex,
        users=[User(id=host_id, name=host_name, host=True)],
        queue=[],
        current_song=None,
        queue_index=-1,
    )
    rooms.append(room)
    return room

def delete_room(session_id: str) -> None:
    try:
        rooms.remove(Room.get_room_from_session_id(session_id, rooms))
    except ValueError:
        raise HTTPException(status_code=404, detail="Room to delete not found")
    except Exception:
        raise HTTPException(status_code=400, detail="Unknown server error")

async def queue_song(session_id: str, song_url: str, queuer_id: str) -> None:

    current_room = Room.get_room_from_session_id(session_id, rooms)
    queuer = User.get_user_from_id(queuer_id, current_room.users)

    ydl_opts = {
        'quiet': True,      
        'skip_download': True,
        'noplaylist': True,  
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(song_url, download=False)
            
            title = info.get('title', 'Unknown Title')
            artist = info.get('artist') or info.get('uploader', 'Unknown Artist')
            thumbnail = info.get('thumbnail', None)
            album = info.get('album', None)

    except Exception as e:
        print(f"Error extracting info: {e}")
        raise HTTPException(status_code=400, detail="Could not fetch video metadata")

    song = Song(
        name=uuid.uuid4().hex,
        title=title,         
        artist=artist,      
        album_art=thumbnail,
        yt_url=song_url,
        added_by=queuer
    )
    
    current_room.queue.append(song)
    
def list_users(session_id: str) -> list[User]:
    current_room: Room = Room.get_room_from_session_id(session_id, rooms)
    return current_room.users

def list_queue(session_id: str) -> list[Song]:
    current_room: Room = Room.get_room_from_session_id(session_id, rooms)
    return current_room.queue

@app.get("/{session_id}/queue", response_class=HTMLResponse)
async def get_queue_partial(request: Request, session_id: str):

    queue = list_queue(session_id)
    return templates.TemplateResponse(
        "partials/queue_items.html",
        {"request": request, "queue": queue},
    )

def search_youtube(query: str):
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'noplaylist': True,
        'extract_flat': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(f"ytsearch5:{query}", download=False)
            return info.get('entries', [])
        except Exception:
            return []

@app.post("/search", response_class=HTMLResponse)
async def search_videos(request: Request, query: str = Form(...)):
    results = search_youtube(query)
    
    html_content = ""
    for video in results:
        title = video.get('title')
        url = video.get('url')
        if not url and video.get('id'):
            url = f"https://www.youtube.com/watch?v={video.get('id')}"
            
        html_content += f"""
        <li role="option" 
            onclick="document.getElementById('url-input').value = '{url}'; document.getElementById('search-results').innerHTML = '';">
            <strong>{title}</strong>
        </li>
        """
        
    if not html_content:
        html_content = "<li>No results found</li>"
        
    return html_content


@app.websocket("/ws/{session_id}")
async def queue_ws(websocket: WebSocket, session_id: str):
    await websocket.accept()

    try:
        room = Room.get_room_from_session_id(session_id, rooms)
    except Exception:
        await websocket.close()
        return

    connections.setdefault(session_id, []).append(websocket)

    await websocket.send_json([serialize_song(s) for s in room.queue])

    try:
        while True:
            data = await websocket.receive_json()

            if data["type"] == "reorder":
                new_order = data["order"] 
                
                id_map = {song.name: song for song in room.queue}

                room.queue = [
                    id_map[song_id]
                    for song_id in new_order
                    if song_id in id_map
                ]

                await broadcast_queue(session_id)

    except WebSocketDisconnect:
        if session_id in connections:
            connections[session_id].remove(websocket)


def serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "host": user.host
    }

def serialize_song(song: Song) -> dict:
    return {
        "id": song.name,
        "title": song.title,
        "artist": song.artist,
        "yt_url": song.yt_url,
        "added_by": song.added_by.name,
        "added_by_id": song.added_by.id,
        "album_art": song.album_art,
    }

async def broadcast_queue(session_id: str):
    """Helper to send the current queue AND now_playing to all connected clients."""
    room = Room.get_room_from_session_id(session_id, rooms)
    if not room: return

    queue_data = [serialize_song(s) for s in room.queue]
   
    users = [serialize_user(u) for u in room.users]
    if not users: return
    now_playing_song = None
    if room.current_song:
        now_playing_song = serialize_song(room.current_song)

    payload = {
        "queue": queue_data,
        "now_playing": now_playing_song,
        "users": users
    }

    active_connections = connections.get(session_id, [])

    for ws in active_connections:
        try:
            await ws.send_json(payload)
        except RuntimeError:
            # Connection might be closed already
            pass