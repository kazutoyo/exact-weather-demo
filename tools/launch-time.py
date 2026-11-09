#!/usr/bin/env python3
"""Cold-launch timing on an iOS Simulator, the same way for any app: record the screen at
60 fps, launch the app from the home screen, then find in the video
  start   the first frame that differs from the home screen (the launch animation begins)
  ui      the first frame whose tab bar icons and labels match the settled screen's (UI drawn)
  ready   the first frame that matches the settled screen (data loaded and shown)
Usage: python3 tools/launch-time.py <udid> <bundle id> [runs] [out dir]"""
import os, signal, subprocess, sys, time, statistics, glob, shutil
from PIL import Image, ImageChops, ImageStat, ImageFilter

udid, bundle = sys.argv[1], sys.argv[2]
runs = int(sys.argv[3]) if len(sys.argv) > 3 else 5
out = sys.argv[4] if len(sys.argv) > 4 else ".exact/launch"
os.makedirs(out, exist_ok=True)
FPS = 60

def sh(*a): return subprocess.run(a, capture_output=True, text=True)

def diff(a, b, box=None):
    if box: a, b = a.crop(box), b.crop(box)
    return sum(ImageStat.Stat(ImageChops.difference(a, b)).mean) / 3

def measure(i):
    sh("xcrun", "simctl", "terminate", udid, bundle)
    sh("xcrun", "simctl", "launch", udid, "com.apple.springboard")  # the home screen
    time.sleep(2)
    video = f"{out}/{bundle}-{i}.mp4"
    rec = subprocess.Popen(["xcrun", "simctl", "io", udid, "recordVideo", "--codec", "h264", "--force", video],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)
    sh("xcrun", "simctl", "launch", udid, bundle)
    time.sleep(7)
    rec.send_signal(signal.SIGINT); rec.wait()
    frames = f"{out}/f"
    shutil.rmtree(frames, ignore_errors=True); os.makedirs(frames)
    # Small frames are enough to compare screens; fps=60 keeps each frame at 1/60 s.
    sh("ffmpeg", "-v", "error", "-i", video, "-vf", f"fps={FPS},scale=201:-2", f"{frames}/%05d.png")
    files = sorted(glob.glob(f"{frames}/*.png"))
    ims = [Image.open(f).convert("RGB") for f in files]
    home, final = ims[0], ims[-1]
    w, h = final.size
    tabbar = (0, int(h * 0.88), w, h)
    start = next(k for k, im in enumerate(ims) if diff(im, home) > 2)
    # The tab bar's icons and labels, by their edges: the sky behind them changes colour when data arrives.
    edges = lambda im: im.crop(tabbar).convert("L").filter(ImageFilter.FIND_EDGES)
    final_edges = edges(final)
    edge_diff = lambda im: ImageStat.Stat(ImageChops.difference(edges(im), final_edges)).mean[0]
    ui = next(k for k in range(start, len(ims)) if edge_diff(ims[k]) < 12)
    ready = next(k for k in range(start, len(ims)) if all(diff(ims[j], final) < 1.5 for j in range(k, min(k + 10, len(ims)))))
    if os.environ.get("KEEP"):
        print("diff to final:", [round(diff(im, final), 1) for im in ims[start:start + 300:15]])
        print("tabbar edge diff:", [round(edge_diff(im), 1) for im in ims[start:start + 300:15]])
        print("start", start, "ui", ui, "ready", ready, "frames", len(ims))
        return (ui - start) * 1000 / FPS, (ready - start) * 1000 / FPS
    shutil.rmtree(frames)
    os.remove(video)
    return (ui - start) * 1000 / FPS, (ready - start) * 1000 / FPS

results = [measure(i) for i in range(runs)]
for ui, ready in results:
    print(f"ui {ui:6.0f} ms   ready {ready:6.0f} ms")
print(f"median: ui {statistics.median(r[0] for r in results):.0f} ms, ready {statistics.median(r[1] for r in results):.0f} ms")
