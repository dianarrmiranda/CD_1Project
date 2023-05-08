from fastapi import FastAPI
from typing import List

from schemas import Music, Progress

app = FastAPI()


# Music


@app.get("/music")
async def listAll() -> List[Music]:
    pass


@app.get("/music/{music_id}")
async def getProgress() -> Progress:
    pass


@app.post("/music")
async def submit(audio: bytes) -> Music:
    # adiciona nova música
    pass


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
async def listJobs() -> List[int]:
    # lista ids dos jobs
    pass


@app.get("/reset")
async def listJobs():
    pass