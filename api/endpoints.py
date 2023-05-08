from fastapi import FastAPI, UploadFile, File
from typing import List
from pydub.utils import mediainfo_json
import shutil, os

from schemas import Music, Progress, Track

app = FastAPI()

idx = -1
defaultTracks = [
    Track(name = "drums", track_id = 1),
    Track(name = "bass", track_id = 2),
    Track(name = "vocals", track_id = 3),
    Track(name = "other", track_id = 4)
]
musicData = []

# Music


@app.get("/music")
async def listAll() -> List[Music]:
    return musicData


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
    try:
        band = metadata["format"]["tags"]["band"]
    except:
        band = ""

    with open("../music/{:0>3d}_{}.mp3".format(idx,title),"wb") as buffer:
        shutil.copyfileobj(mp3file.file,buffer)
    mp3file.file.close()

    music = Music(music_id=idx, name=title, band=band, tracks=defaultTracks)

    musicData.append(music)

    return music
    


@app.post("/music/{music_id}")
async def process(music_id: int, tracks_ids: list):
    # procurar música com music_id e passar os tracks da lista
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

    dir = "../music"
    for f in os.listdir(dir):
        os.remove(os.path.join(dir, f))

    dir = "../tracks"
    for f in os.listdir(dir):
        os.remove(os.path.join(dir, f))