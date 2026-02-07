from typing import override

from pydantic import BaseModel


class Room(BaseModel):
    session_id: str
    queue: list[str]
    queue_index: int

    @classmethod
    def get_room_from_session_id(cls, session_id: str, rooms: list["Room"]) -> "Room":
        for room in rooms:
            if room.session_id == session_id:
                return room
        raise ValueError(f"Session ID '{session_id}' was not in known rooms")
