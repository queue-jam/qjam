import uuid

from fastapi import FastAPI, HTTPException, status

from .types import Room, Song, User

app = FastAPI()

rooms: list[Room] = []


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "FastAPI is up and running!"}


@app.post("/new", status_code=status.HTTP_201_CREATED)
def create_room(host_id: str, host_name: str) -> Room:
    room: Room = Room(
        session_id=uuid.uuid4().hex,
        users=[User(id=host_id, name=host_name, host=True)],
        queue=[],
        queue_index=-1,
    )
    rooms.append(room)
    return room


@app.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_room(session_id: str) -> None:
    try:
        rooms.remove(Room.get_room_from_session_id(session_id, rooms))
    except ValueError:
        raise HTTPException(status_code=404, detail="Room to delete not found")
    except Exception:
        raise HTTPException(status_code=400, detail="Unknown server error")


@app.post("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def queue_song(session_id: str, song_url: Song, queuer_id: str) -> None:
    current_room: Room = Room.get_room_from_session_id(session_id, rooms)

    queuer: User = User.get_user_from_id(queuer_id, current_room.users)
    if not queuer.host:
        raise HTTPException(status_code=403, detail="Bad queue permissions")

    song: Song = Song(name=uuid.uuid4().hex, yt_url=song_url, added_by=queuer)
    current_room.queue.append(song)


@app.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def dequeue_song(session_id: str, song_url: Song, dequeuer_id: str) -> None:
    current_room: Room = Room.get_room_from_session_id(session_id, rooms)

    dequeuer: User = User.get_user_from_id(dequeuer_id, current_room.users)
    if not dequeuer.host:
        raise HTTPException(status_code=403, detail="Bad dequeue permissions")

    song: Song = Song.get_song_from_yt_url(song_url, current_room.queue)
    current_room.queue.remove(song)


# DO NOT MAKE THIS PUBLIC
@app.get("/list", status_code=status.HTTP_200_OK)
def list_rooms() -> list[Room]:
    return rooms


@app.get("/{session_id}/users", status_code=status.HTTP_200_OK)
def list_users(session_id: str) -> list[User]:
    current_room: Room = Room.get_room_from_session_id(session_id, rooms)
    return current_room.users


@app.get("/{session_id}/queue", status_code=status.HTTP_200_OK)
def list_queue(session_id: str) -> list[Song]:
    current_room: Room = Room.get_room_from_session_id(session_id, rooms)
    return current_room.queue
