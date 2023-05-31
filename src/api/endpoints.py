from fastapi import FastAPI, Form, UploadFile, File, Request
from typing import List
from pydub.utils import mediainfo_json
import shutil, os, signal, sys
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from schemas import Music, Progress, Track, Job
from server import Server
import uvicorn, threading


app = FastAPI()

templates = Jinja2Templates(directory="../../templates")

app.mount("/static", StaticFiles(directory="static"), name="static")


idx = -1
defaultTracks = [
    Track(name = "drums", track_id = 1),
    Track(name = "bass", track_id = 2),
    Track(name = "vocals", track_id = 3),
    Track(name = "other", track_id = 4)
]

tracksDict = { 
    1: "drums",
    2: "bass",
    3: "vocals",
    4: "other"
}

# Music
@app.get("/music")
async def listAll() -> List[Music]:
    return server.listAll()


@app.get("/music/{music_id}")
async def getProgress(music_id: int) -> Progress:
    progress = server.getInstrumentProgress(music_id)
    
    for instrument in progress[music_id]:
        if progress[instrument] == 1:   # 100%
            pass



@app.post("/music")
async def submit(request: Request, mp3file: UploadFile = File(...)) -> Music:
    # adiciona nova música
    global idx
    idx += 1

    metadata = mediainfo_json(mp3file.file)
    try:
        title = metadata["format"]["tags"]["title"]
    except:
        title = "Unknown"
    try:
        band = metadata["format"]["tags"]["artist"]
    except:
        band = ""

    with open("static/unprocessed/{:0>3d}_{}.mp3".format(idx,title),"wb") as buffer:
        mp3file.file.seek(0)
        shutil.copyfileobj(mp3file.file,buffer)
    mp3file.file.close()

    music = Music(music_id=idx, name=title, band=band, tracks=defaultTracks)

    server.addMusic(music)

    music_list = await listAll()
    return templates.TemplateResponse("index.html", {"request": request,"music_list": music_list})


@app.post("/music/{music_id}", response_class=HTMLResponse)
async def process(request: Request, music_id: int, tracks: str = Form(...)):
    print("music_id: ", music_id)
    tracks_ids = [track.strip() for track in tracks.split(",")]
    tracks_names = [tracksDict[int(id)] for id in tracks_ids]

    print("tracks_names: ", tracks_names)

    server.split_music(music_id, tracks_names)
    
    music_list = await listAll()
    return templates.TemplateResponse("index.html", {"request": request,"music_list": music_list})


@app.get("/job", response_class=HTMLResponse)
async def listJobs(request: Request) -> List[Job]:
    jobs = server.getJobList()
    music_list = await listAll()
    return templates.TemplateResponse("index.html", {"request": request,"music_list": music_list, "jobs": jobs})

@app.get("/job/{job_id}")
async def getJob() -> List[int]:
    # lista ids dos jobs
    pass


@app.get("/reset")
async def reset():

    dir = "static/unprocessed"
    for f in os.listdir(dir):
        os.remove(os.path.join(dir, f))



@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    music_list = await listAll()
    return templates.TemplateResponse("index.html", {"request": request, "music_list": music_list})


if __name__ == "__main__":
    server = Server()
    server.start()

    uvicorn.run(app, host="0.0.0.0", port=8000)

    server.stop()
    server.join()