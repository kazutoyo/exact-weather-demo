#!/usr/bin/env python3
"""Lays the three films from tools/film.py side by side on a 1920x1080 card, as an MP4 for X.
Usage: python3 tools/compose.py [out.mp4]   (run from the app's directory)"""
import subprocess, sys
from PIL import Image, ImageDraw, ImageFont

OUT = sys.argv[1] if len(sys.argv) > 1 else "docs/demo/weather-exact-3platforms.mp4"
FILM = ".exact/film"
W, H = 1920, 1080
PANE_H = 860            # phones' height
TOP = 150
FONT = "/System/Library/Fonts/SFNS.ttf"

def size(host):
    first = open(f"{FILM}/{host}/list.txt").readline().split("'")[1]
    return Image.open(f"{FILM}/{host}/{first}").size

# Panes: iOS | macOS | Web, phones scaled to PANE_H, the Mac window at its own size.
iw, ih = size("ios"); ww, wh = size("web"); mw, mh = size("macos")
phone_w = round(iw * PANE_H / ih) // 2 * 2
web_w = round(ww * PANE_H / wh) // 2 * 2
mac_w, mac_h = mw // 2 * 2, mh // 2 * 2
gap = (W - phone_w - web_w - mac_w) // 4
x_ios, x_mac = gap, gap * 2 + phone_w
x_web = x_mac + mac_w + gap
y_mac = TOP + (PANE_H - mac_h) // 2

bg = Image.new("RGB", (W, H))
d = ImageDraw.Draw(bg)
top, bot = (14, 22, 40), (34, 64, 110)
for y in range(H):
    t = y / H
    d.line([(0, y), (W, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
def text(s, size, x, y, fill, anchor="mm"):
    d.text((x, y), s, font=ImageFont.truetype(FONT, size), fill=fill, anchor=anchor)
text("One app, three platforms — built with Expo Exact", 50, W / 2, 60, (255, 255, 255))
text("One Contract view + one TypeScript data module · Open-Meteo", 26, W / 2, 112, (190, 205, 230))
label_y = TOP + PANE_H + 34
text("iOS · UIKit", 28, x_ios + phone_w / 2, label_y, (230, 238, 250))
text("macOS · AppKit", 28, x_mac + mac_w / 2, label_y, (230, 238, 250))
text("Web · DOM", 28, x_web + web_w / 2, label_y, (230, 238, 250))
bg.save(f"{FILM}/bg.png")

def mask(w, h, r, name):
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], radius=r, fill=255)
    m.save(f"{FILM}/{name}")
mask(phone_w, PANE_H, 44, "mask-ios.png")
mask(web_w, PANE_H, 44, "mask-web.png")
mask(mac_w, mac_h, 14, "mask-mac.png")

dur = min(sum(float(l.split()[1]) for l in open(f"{FILM}/{h}/list.txt") if l.startswith("duration"))
          for h in ("ios", "macos", "web"))
def pane(i, w, h, m):
    return (f"[{i}:v]fps=30,scale={w}:{h}:flags=lanczos,format=rgba[p{i}];"
            f"[{m}:v]format=gray,scale={w}:{h}[m{i}];[p{i}][m{i}]alphamerge[r{i}];")
filt = (pane(1, phone_w, PANE_H, 4) + pane(2, mac_w, mac_h, 5) + pane(3, web_w, PANE_H, 6) +
        f"[0:v][r1]overlay={x_ios}:{TOP}[a];[a][r2]overlay={x_mac}:{y_mac}[b];"
        f"[b][r3]overlay={x_web}:{TOP},format=yuv420p[v]")
cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y",
       "-loop", "1", "-t", f"{dur}", "-i", f"{FILM}/bg.png"]
for h in ("ios", "macos", "web"):
    cmd += ["-f", "concat", "-safe", "0", "-i", f"{FILM}/{h}/list.txt"]
for m in ("mask-ios.png", "mask-mac.png", "mask-web.png"):
    cmd += ["-loop", "1", "-t", f"{dur}", "-i", f"{FILM}/{m}"]
cmd += ["-filter_complex", filt, "-map", "[v]", "-t", f"{dur}", "-r", "30",
        "-c:v", "libx264", "-profile:v", "high", "-crf", "20", "-preset", "medium",
        "-movflags", "+faststart", OUT]
subprocess.run(cmd, check=True)
print(OUT, f"{dur:.1f}s", f"panes: ios {phone_w}x{PANE_H} mac {mac_w}x{mac_h} web {web_w}x{PANE_H}")
