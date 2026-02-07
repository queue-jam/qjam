import logging
import uuid
from typing import Any

import yt_dlp
from fastapi import FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from backend.types import Room, Song, User

from .types import Room, Song, User

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Point to the templates directory
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

# --- Frontend / View Routes ---

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

@app.post("/play", response_class=HTMLResponse)
def play_stream(request: Request, url: str = Form(...)):
    """
    HTMX Endpoint: Returns an audio player fragment.
    """
    try:
        direct_stream_url = get_audio_url(url)
        logger.info(f"Fetched audio URL: {direct_stream_url}")
        return templates.TemplateResponse(
            "partials/player.html", 
            {"request": request, "stream_url": direct_stream_url}
        )
    except Exception as e:
        logger.error(f"Error fetching audio: {e}")
        return f"<p style='color:red'>Error fetching audio: {str(e)}</p>"
    
@app.post("/{session_id}/queue", response_class=HTMLResponse)
async def add_to_queue(request: Request, session_id: str, url: str = Form(...)):
    """
    HTMX Endpoint: Adds song to queue. Returns a fresh input field to reset the form.
    """
    user_id = request.cookies.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="No user ID found in cookies")

    queue_song(session_id=session_id, song_url=url, queuer_id=user_id)
    
    return """
    <input type="text" name="url" placeholder="Song queued! Add another..." required>
    """
    
@app.get("/{session_id}/queue", response_class=HTMLResponse)
async def current_queue_partial(request: Request, session_id: str):
    queue: list[Song] = list_queue(session_id) 
    
    html_content = ""
    for song in queue:
        html_content += f"<li>{song}</li>"
        
    return html_content

@app.post("/room", response_class=HTMLResponse)
def jam_room(request: Request, username: str = Form(...)):
    user_id: str = request.cookies.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="No user ID found in cookies")

    new_room: Room = create_room(host_id=user_id, host_name=username)
    response: Any = templates.TemplateResponse("room.html", {
        "request": request, 
        "room": new_room,
        "user_name": username,
    })
    response.set_cookie(key="session_id", value=new_room.session_id, httponly=True)
    
    return response

@app.post("/join", response_class=HTMLResponse)
def join_room(request: Request, session_id: str = Form(...), username: str = Form(...)):
    response: Any = templates.TemplateResponse("room.html", {
        "request": request, 
        "room": Room.get_room_from_session_id(session_id, rooms),
        "user_name": username,
    })
    return response
    

# --- API Routes ---

# @app.post("/new", status_code=status.HTTP_201_CREATED)
def create_room(host_id: str, host_name: str) -> Room:
    room: Room = Room(
        session_id=uuid.uuid4().hex,
        users=[User(id=host_id, name=host_name, host=True)],
        queue=[],
        queue_index=-1,
    )
    rooms.append(room)
    return room

# @app.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_room(session_id: str) -> None:
    try:
        rooms.remove(Room.get_room_from_session_id(session_id, rooms))
    except ValueError:
        raise HTTPException(status_code=404, detail="Room to delete not found")
    except Exception:
        raise HTTPException(status_code=400, detail="Unknown server error")

# @app.post("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def queue_song(session_id: str, song_url: str, queuer_id: str) -> None:
    current_room: Room = Room.get_room_from_session_id(session_id, rooms)

    queuer: User = User.get_user_from_id(queuer_id, current_room.users)
    if not queuer.host:
        raise HTTPException(status_code=403, detail="Bad queue permissions")

    song: Song = Song(name=uuid.uuid4().hex, yt_url=song_url, added_by=queuer)
    current_room.queue.append(song)

# @app.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def dequeue_song(session_id: str, song_url: str, dequeuer_id: str) -> None:
    current_room: Room = Room.get_room_from_session_id(session_id, rooms)

    dequeuer: User = User.get_user_from_id(dequeuer_id, current_room.users)
    if not dequeuer.host:
        raise HTTPException(status_code=403, detail="Bad dequeue permissions")

    song: Song = Song.get_song_from_yt_url(song_url, current_room.queue)
    current_room.queue.remove(song)
    
def list_users(session_id: str) -> list[User]:
    current_room: Room = Room.get_room_from_session_id(session_id, rooms)
    return current_room.users

def list_queue(session_id: str) -> list[Song]:
    current_room: Room = Room.get_room_from_session_id(session_id, rooms)
    return current_room.queue
