from fastapi import FastAPI, UploadFile, File, Request
from typing import List
from pydub.utils import mediainfo_json
import shutil, os, signal, sys
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from schemas import Music, Progress, Track
from server import Server

server = Server()

app = FastAPI()

templates = Jinja2Templates(directory="../../templates")

app.mount("/static", StaticFiles(directory="static"), name="static")


def signal_handler(self, sig, frame):
    print('\nDone!')
    server.close()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
print('Press Ctrl+C to exit...')


idx = -1
defaultTracks = [
    Track(name = "drums", track_id = 1),
    Track(name = "bass", track_id = 2),
    Track(name = "vocals", track_id = 3),
    Track(name = "other", track_id = 4)
]

# Music


@app.get("/music")
async def listAll() -> List[Music]:
    return server.listAll()


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

    with open("static/music/{:0>3d}_{}.mp3".format(idx,title),"wb") as buffer:
        mp3file.file.seek(0)
        shutil.copyfileobj(mp3file.file,buffer)
    mp3file.file.close()

    music = Music(music_id=idx, name=title, band=band, tracks=defaultTracks)

    server.addMusic(music)

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

    dir = "static/music"
    for f in os.listdir(dir):
        os.remove(os.path.join(dir, f))

    dir = "static/tracks"
    for f in os.listdir(dir):
        os.remove(os.path.join(dir, f))


@app.get("/")
async def home(request: Request):
    music_list = await listAll()
    return templates.TemplateResponse("index.html", {"request": request, "music_list": music_list})
