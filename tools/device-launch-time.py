#!/usr/bin/env python3
"""Cold-launch timing on a USB-connected iPhone, measured the same way as tools/launch-time.py:
record the iPhone's screen from this Mac (tools/rec.swift, like QuickTime), kill the app so the
home screen shows, launch it with devicectl, then find in the video
  start   the first frame that differs from the home screen (the launch animation begins)
  ui      the first frame whose tab bar icons and labels match the settled screen's (UI drawn)
  ready   the first frame that matches the settled screen (data loaded and shown)
Usage: python3 tools/device-launch-time.py <device udid> <bundle id> [runs] [out dir]
Needs: swiftc tools/rec.swift -o <out dir>/rec   (built on first run)"""
import os, signal, subprocess, sys, time, statistics, glob, shutil, json
from PIL import Image, ImageChops, ImageStat, ImageFilter

dev, bundle = sys.argv[1], sys.argv[2]
runs = int(sys.argv[3]) if len(sys.argv) > 3 else 7
out = sys.argv[4] if len(sys.argv) > 4 else ".exact/device-launch"
os.makedirs(out, exist_ok=True)
FPS = 60
here = os.path.dirname(os.path.abspath(__file__))
rec = f"{out}/rec"
if not os.path.exists(rec):
    subprocess.run(["swiftc", "-O", f"{here}/rec.swift", "-o", rec], check=True)

def sh(*a): return subprocess.run(a, capture_output=True, text=True)

def devjson(*a):
    f = f"{out}/q.json"
    sh("xcrun", "devicectl", *a, "--device", dev, "--json-output", f)
    return json.load(open(f))["result"]

app_dir = next(a["url"] for a in devjson("device", "info", "apps", "--bundle-id", bundle)["apps"])
app_dir = app_dir.replace("file://", "").rstrip("/") + "/"

others = [b for b in os.environ.get("ALSO_KILL", "").split(",") if b]
app_dirs = [app_dir] + [next(a["url"] for a in devjson("device", "info", "apps", "--bundle-id", b)["apps"])
                        .replace("file://", "").rstrip("/") + "/" for b in others]

def kill():
    # Every app under test, so the home screen (not the last app measured) is what shows.
    for p in devjson("device", "info", "processes")["runningProcesses"]:
        exe = p.get("executable", "").replace("file://", "")
        if any(exe.startswith(d) for d in app_dirs) and ".appex/" not in exe:
            sh("xcrun", "devicectl", "device", "process", "signal", "--device", dev,
               "--pid", str(p["processIdentifier"]), "--signal", "SIGKILL")

def diff(a, b, box=None):
    if box: a, b = a.crop(box), b.crop(box)
    return sum(ImageStat.Stat(ImageChops.difference(a, b)).mean) / 3

def measure(i):
    kill()
    time.sleep(2.5)  # back on the home screen
    video = f"{out}/{bundle}-{i}.mov"
    r = subprocess.Popen([rec, "iPhone", "9", video], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3.5)  # the recorder warms up for 1.5 s
    sh("xcrun", "devicectl", "device", "process", "launch", "--device", dev, bundle)
    r.wait()
    frames = f"{out}/f"
    shutil.rmtree(frames, ignore_errors=True); os.makedirs(frames)
    sh("ffmpeg", "-v", "error", "-i", video, "-vf", f"fps={FPS},scale=195:-2", f"{frames}/%05d.png")
    ims = [Image.open(f).convert("RGB") for f in sorted(glob.glob(f"{frames}/*.png"))]
    home, final = ims[0], ims[-1]
    w, h = final.size
    tabbar = (0, int(h * 0.88), w, h)
    start = next(k for k, im in enumerate(ims) if diff(im, home) > 2)
    edges = lambda im: im.crop(tabbar).convert("L").filter(ImageFilter.FIND_EDGES)
    final_edges = edges(final)
    edge_diff = lambda im: ImageStat.Stat(ImageChops.difference(edges(im), final_edges)).mean[0]
    # UI drawn: the tab bar's outlines match the settled screen's, once the home screen has gone
    # (the zooming, blurred home screen can look alike) and past the white launch screen.
    center = (w // 4, h // 4, 3 * w // 4, 3 * h // 4)
    white = lambda im: ImageStat.Stat(im.crop(center).convert("L")).mean[0] > 230
    ui = next(k for k in range(start, len(ims))
              if diff(ims[k], home) > 80 and not white(ims[k]) and edge_diff(ims[k]) < 12)
    ready = next(k for k in range(start, len(ims)) if all(diff(ims[j], final) < 1.5 for j in range(k, min(k + 10, len(ims)))))
    if os.environ.get("KEEP"):
        print("start", start, "ui", ui, "ready", ready, "frames", len(ims))
    else:
        shutil.rmtree(frames); os.remove(video)
    return (ui - start) * 1000 / FPS, (ready - start) * 1000 / FPS

results = [measure(i) for i in range(runs)]
for ui, ready in results:
    print(f"ui {ui:6.0f} ms   ready {ready:6.0f} ms")
print(f"median: ui {statistics.median(r[0] for r in results):.0f} ms, ready {statistics.median(r[1] for r in results):.0f} ms")
