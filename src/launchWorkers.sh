#!/bin/bash
NUM_WORKERS=7

gnome-terminal --tab --title="Worker 1" -- python3 worker.py

for ((i=2; i<=NUM_WORKERS; i++)); do
    gnome-terminal --tab --title="Worker $i" -- python3 worker.py
done

wait
