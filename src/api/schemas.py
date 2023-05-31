from pydantic import BaseModel
from typing import List, Union


class Track(BaseModel):
    name: str
    track_id: int


class Music(BaseModel):
    music_id: int
    name: str
    band: str
    tracks: List[Track]


class Instrument(BaseModel):
    name: str
    track: str


class Progress(BaseModel):
    progress: int
    instruments: List[Instrument]
    final: str


class Job(BaseModel):
    job_id: int
    size: int
    time: int # timestamp em segundos
    music_id: int
    track_id: Union[str,List[str]] #Union[int,List[int]]
