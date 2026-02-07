from typing import override

from pydantic import BaseModel


class User(BaseModel):
    id: str
    name: str
    host: bool

    @classmethod
    def get_user_from_id(cls, id: str, users: list["User"]) -> "User":
        for user in users:
            if user.id == id:
                return user
        raise ValueError(f"User ID '{id}' was not in known users")


class Song(BaseModel):
    name: str
    yt_url: str
    added_by: User

    @classmethod
    def get_song_from_yt_url(cls, yt_url: str, songs: list["Song"]) -> "Song":
        for song in songs:
            if song.yt_url == yt_url:
                return song
        raise ValueError(f"YT URL '{yt_url}' was not in queued songs")


class Room(BaseModel):
    session_id: str
    users: list[User]
    queue: list[Song]
    queue_index: int

    @classmethod
    def get_room_from_session_id(cls, session_id: str, rooms: list["Room"]) -> "Room":
        for room in rooms:
            if room.session_id == session_id:
                return room
        raise ValueError(f"Session ID '{session_id}' was not in known rooms")
