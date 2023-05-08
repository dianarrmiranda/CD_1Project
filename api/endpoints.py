from fastapi import FastAPI, UploadFile, File
from typing import List
from pydub.utils import mediainfo_json
import shutil

from schemas import Music, Progress, Track

app = FastAPI()

idx = 0
defaultTracks = [
    Track(name = "drums", track_id = 1),
    Track(name = "bass", track_id = 2),
    Track(name = "vocals", track_id = 3),
    Track(name = "other", track_id = 4)
]

# Music


@app.get("/music")
async def listAll() -> List[Music]:
    pass


@app.get("/music/{music_id}")
async def getProgress() -> Progress:
    pass


@app.post("/music")
async def submit(mp3file: UploadFile = File(...)) -> Music:
    # adiciona nova música
    global idx
    idx += 1

    metadata = mediainfo_json(mp3file.file)
    title = metadata["format"]["tags"]["title"]

    with open("../tracks/" + str(idx) + "_" + title + ".mp3","wb") as buffer:
        shutil.copyfileobj(mp3file.file,buffer)
    mp3file.file.close()

    return Music(music_id=idx, name=title, band="", tracks=defaultTracks)
    


@app.post("/music/{music_id}")
async def process(music_id: int, tracks_ids: list):
    # procurar música com music_id usando os tracks da lista
    pass


# System


@app.get("/job")
async def listJobs() -> List[int]:
    # lista ids dos jobs
    pass


@app.get("/job/{job_id}")
async def getJob() -> List[int]:
    # lista ids dos jobs
    pass


@app.get("/reset")
async def reset():
    pass