import uuid

from fastapi import FastAPI, HTTPException, status
from room import Room

app = FastAPI()

rooms: list[Room] = []


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "FastAPI is up and running!"}


@app.get("/new", status_code=status.HTTP_201_CREATED)
def create_room() -> Room:
    room: Room = Room(session_id=uuid.uuid4().hex, queue=[], queue_index=-1)
    rooms.append(room)
    return room


# DO NOT MAKE THIS PUBLIC
@app.get("/list", status_code=status.HTTP_200_OK)
def list_rooms() -> list[Room]:
    return rooms


@app.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_room(session_id: str) -> None:
    try:
        rooms.remove(Room.get_room_from_session_id(session_id, rooms))
    except ValueError:
        raise HTTPException(status_code=404, detail="Item not found")
    except Exception:
        raise HTTPException(status_code=400, detail="Unknown server error")


@app.get("/test/{get_num}")
def read_item(item_id: int, q: str = None):
    return {"get_num": item_id, "q": q}
