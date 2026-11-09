#!/usr/bin/env python3
"""Films the same flow on web, iOS and macOS with Exact's agent (one virtual clock, so the
three stay in step), then lays them side by side as one MP4.
Usage: python3 tools/film.py [web ios macos]   (run from the app's directory)"""
import os, subprocess, sys, shutil

HOSTS = sys.argv[1:] or ["web", "ios", "macos"]
OUT = ".exact/film"
FLAGS = {
    "web": ["--size", "402x874"],
    "ios": ["--scale", "2"],
    "macos": ["--size", "1000x700"],
}
STEP = 33  # ms between frames (~30 fps)

def ops(host):
    win = "" if host == "web" else " window"
    n = 0
    def film(ms):
        # one capture holds at most 64M pixels: chunks of 1.3 s (40 frames at 804x1748)
        nonlocal n
        shots = []
        while ms > 0:
            n += 1
            part = min(ms, 1300)
            shots.append(f"screenshot {OUT}/{host}/{n:02d}.apng over {part} every {STEP}{win}")
            ms -= part
        return shots
    flow = [
        "clock +1", "type @4 35.6895,139.6917", "clock data", "clock data", film(2500),
        "tap tab-search", film(700),
        "type search-input Osaka", film(500), "clock data", film(1500),
        "tap result-1853909", "clock data", film(2200),
        "tap star-search", "clock data", film(1000),
        "tap tab-favorites", "clock data", film(1600),
        "tap fav-1853909", "clock data", film(2000),
        "back", film(800),
        "tap tab-weather", film(1600),
    ]
    return [op for x in flow for op in (x if isinstance(x, list) else [x])]

env = dict(os.environ, EXACT_FEEDBACK="0")
for host in HOSTS:
    shutil.rmtree(f"{OUT}/{host}", ignore_errors=True)
    os.makedirs(f"{OUT}/{host}")
    cmd = ["bun", "exact.mjs", "agent", host, "--storage", f"film-{os.getpid()}",
           "--permission", "geolocation=granted", *FLAGS[host], *ops(host)]
    r = subprocess.run(cmd, env=env, capture_output=True, text=True)
    print(host, "exit", r.returncode, (r.stdout + r.stderr).strip().splitlines()[-1][:200])
    if r.returncode:
        sys.exit(r.stdout + r.stderr)
    # One ffmpeg concat list of every frame, in order.
    frames = []
    for seg in sorted(d for d in os.listdir(f"{OUT}/{host}") if d.endswith(".frames")):
        frames += [f"{seg}/{f}" for f in sorted(os.listdir(f"{OUT}/{host}/{seg}"))]
    with open(f"{OUT}/{host}/list.txt", "w") as f:
        for fr in frames:
            f.write(f"file '{fr}'\nduration {STEP / 1000}\n")
        f.write(f"file '{frames[-1]}'\n")
    print(host, len(frames), "frames")
