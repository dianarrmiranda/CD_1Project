from fastapi import FastAPI, Form, UploadFile, File, Request, HTTPException
from typing import List
from pydub.utils import mediainfo_json
import shutil, os, signal, sys
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from schemas import Music, Progress, Track, Job, Instrument
from server import Server
import uvicorn, threading



app = FastAPI()

templates = Jinja2Templates(directory="../../templates")

app.mount("/static", StaticFiles(directory="static"), name="static")


idx = -1
idx_lock = threading.Lock()

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

progressTotal = {}

# Music
@app.get("/music")
async def listAll() -> List[Music]:
    return server.listAll()


@app.get("/music/{music_id}", response_class=HTMLResponse)
async def getProgress(request: Request ,music_id: int) -> List[Progress]: 

    try:
        progress = server.getProgress(music_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Music not found")

    instruments = []
        
    for i in range(len(progress[1])):
        inst = Instrument(name=progress[1][i][0], track=progress[1][i][1])
        instruments.append(inst)

    progressTotal = Progress(progress=int(progress[0]), instruments=instruments, final=str(progress[2]))

    music_list = await listAll()
    return templates.TemplateResponse("index.html", {"request": request,"music_list": music_list, "progress": progressTotal, "music_id": music_id})


@app.post("/music")
async def submit(request: Request, mp3file: UploadFile = File(...)) -> Music:
    # adiciona nova música
    global idx
    global idx_lock

    with idx_lock:
        idx += 1
        current_idx = idx

    metadata = mediainfo_json(mp3file.file)
    try:
        title = metadata["format"]["tags"]["title"]
    except:
        title = "Unknown"
    try:
        band = metadata["format"]["tags"]["artist"]
    except:
        band = ""

    try:
        with open("static/unprocessed/{:0>3d}_{}.mp3".format(current_idx,title),"wb") as buffer:
            mp3file.file.seek(0)
            shutil.copyfileobj(mp3file.file,buffer)
        mp3file.file.close()
    except Exception:
        raise HTTPException(status_code=405, detail="Invalid input")

    music = Music(music_id=current_idx, name=title, band=band, tracks=defaultTracks)

    server.addMusic(music)

    music_list = await listAll()
    return templates.TemplateResponse("index.html", {"request": request,"music_list": music_list})


@app.post("/music/{music_id}", response_class=HTMLResponse)
async def process(request: Request, music_id: int, tracks: str = Form(...)):

    with idx_lock:
        if music_id > idx or music_id < 0:
            raise HTTPException(status_code=404, detail="Music not found")
        
    tracks_ids = [track.strip() for track in tracks.split(",")]

    for track in tracks_ids:
        if int(track) not in tracksDict.keys():
            raise HTTPException(status_code=404, detail="Track not found")
        
    tracks_names = [tracksDict[int(id)] for id in tracks_ids]

    server.split_music(music_id, tracks_names)
    
    music_list = await listAll()
    return templates.TemplateResponse("index.html", {"request": request,"music_list": music_list})


@app.get("/job", response_class=HTMLResponse)
async def listJobs(request: Request) -> List[Job]:

    try:
        jobs = server.getJobList()
    except:
        raise HTTPException(status_code=405, detail="Invalid input")

    jobs_list = []
    for job in jobs:
        jobs_list.append(Job(job_id=job, size=jobs[job][0], time=jobs[job][1], music_id=jobs[job][2], track_id=jobs[job][3]))

    music_list = await listAll()
    return templates.TemplateResponse("index.html", {"request": request, "music_list": music_list, "jobs": jobs_list})


@app.get("/job/{job_id}", response_class=HTMLResponse)
async def getJob(request: Request, job_id: int) -> Job:

    try:
        job = server.getJobList()[job_id]
    except:
        raise HTTPException(status_code=404, detail="Job not found")

    j = Job(job_id=job_id, size=job[0], time=job[1], music_id=job[2], track_id=job[3])

    music_list = await listAll()
    return templates.TemplateResponse("index.html", {"request": request, "music_list": music_list, "job": j})


@app.post("/reset", response_class=HTMLResponse)
async def reset(request: Request):
    server.reset()
    global idx
    idx = -1
    music_list = await listAll()
    
    return templates.TemplateResponse("index.html", {"request": request, "music_list": music_list})


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