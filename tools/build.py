#!/usr/bin/env python3
"""Escape the README: a click-to-play first-person maze that runs inside GitHub.

GitHub markdown can't run code, so the game is pre-computed: a tiny raycaster
renders the view from every (cell, facing) state, and each state gets its own
markdown page whose buttons link to the neighbouring states. Clicking around
those links *is* the game.

All art (textures, posters, sprites, font) is generated procedurally here.

    pip install pillow numpy
    python tools/build.py
"""
import math
import os
import shutil

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OWNER = "tanzuo017"
REPO = "escape-the-readme"
PROFILE = f"https://github.com/{OWNER}"

# ---------------------------------------------------------------- the level --
# '#' brick  '=' tech panel  'A' 'B' 'C' 'D' 'G' posters/signs  'X' exit door
# '.' floor  'S' start  'L' lamp post  'P' potted plant (both block movement)
LEVEL = [
    "#################",
    "######==C==######",
    "#####=P...P=#####",
    "##A##=..S..=##B##",
    "##.##=.....=##.##",
    "##.###==.==###.##",
    "##.###.....###.##",
    "##.###.L.L.###.##",
    "##.............##",
    "##.###.L.L.###.##",
    "##.###.....###.##",
    "##.#####G#####.##",
    "##.=====D=====.##",
    "##.............##",
    "###=====X=====###",
    "#################",
]
MW, MH = len(LEVEL[0]), len(LEVEL)
assert all(len(r) == MW for r in LEVEL)
WALLS = "#=ABCDGX"
SPRITE_CELLS = "LP"


def cell(x, y):
    if 0 <= x < MW and 0 <= y < MH:
        return LEVEL[y][x]
    return "#"


def walkable(x, y):
    return cell(x, y) in ".S"


START = next((x, y) for y, r in enumerate(LEVEL) for x, c in enumerate(r) if c == "S")
SPRITES = [(x + 0.5, y + 0.5, c) for y, r in enumerate(LEVEL) for x, c in enumerate(r) if c in SPRITE_CELLS]

POSTERS = {
    "A": dict(name="NTEST", url=f"{PROFILE}/NTEST-clinical-digitization-tool",
              hint="📌 <b>NTEST</b>: a bilingual (English / বাংলা) clinical data-entry tool for diabetes outpatient records, built to benchmark against paper and Google Forms."),
    "B": dict(name="Find Every Child", url=f"{PROFILE}/find_a_child",
              hint="📌 <b>Find Every Child</b>: the campaign site for Project Q2's response to the 2026 measles outbreak in Bangladesh."),
    "C": dict(name=None, url=None, hint="👋 Welcome in. Find the exit, and my projects on the way."),
    "G": dict(name=None, url=None, hint="🚪 The exit is on the other side of this wall. Go around, through the west or east wing."),
    "D": dict(name=None, url=None, hint="👀 Psst… turn around."),
}

DIRS = "NESW"
DVEC = {"N": (0, -1), "E": (1, 0), "S": (0, 1), "W": (-1, 0)}
DANG = {"N": -math.pi / 2, "E": 0.0, "S": math.pi / 2, "W": math.pi}
DNAME = {"N": "NORTH", "E": "EAST", "S": "SOUTH", "W": "WEST"}


def turn(d, k):
    return DIRS[(DIRS.index(d) + k) % 4]


# ------------------------------------------------------------- render setup --
W, VIEW_H, HUD_H = 320, 180, 36           # logical pixel grid for the HUD and pixel art
H = VIEW_H + HUD_H
UPSCALE = 2
RW, RH = W * UPSCALE, VIEW_H * UPSCALE     # the 3D view renders at full output resolution
HORIZON = RH / 2
PLANE = 0.9
K = (RW / 2) / PLANE          # square texels: 1 world unit is as tall as it is wide
TEX = 128
BACK = 0.45                   # camera sits a little behind the cell centre
FOG = np.array([12, 10, 26], np.float32)
AMBIENT = np.array([0.10, 0.10, 0.16], np.float32)

LIGHTS = [  # x, y, colour, intensity, radius
    (8.5, 3.0, (0.80, 0.80, 1.00), 1.0, 3.6),    # lobby
    (2.5, 4.4, (1.00, 0.90, 0.80), 0.9, 2.4),    # NTEST poster
    (14.5, 4.4, (1.00, 0.90, 0.80), 0.9, 2.4),   # Find Every Child poster
    (8.5, 13.6, (0.45, 1.00, 0.60), 1.3, 3.2),   # exit
]
LIGHTS += [(x, y, (1.0, 0.80, 0.55), 1.4, 3.0) for x, y, c in SPRITES if c == "L"]
LIGHTS = [(x, y, np.array(c, np.float32), i, r) for x, y, c, i, r in LIGHTS]

# ------------------------------------------------------------------- font --
FONT = {
    "A": ".###.|#...#|#...#|#####|#...#|#...#|#...#", "B": "####.|#...#|#...#|####.|#...#|#...#|####.",
    "C": ".###.|#...#|#....|#....|#....|#...#|.###.", "D": "####.|#...#|#...#|#...#|#...#|#...#|####.",
    "E": "#####|#....|#....|####.|#....|#....|#####", "F": "#####|#....|#....|####.|#....|#....|#....",
    "G": ".###.|#...#|#....|#.###|#...#|#...#|.####", "H": "#...#|#...#|#...#|#####|#...#|#...#|#...#",
    "I": ".###.|..#..|..#..|..#..|..#..|..#..|.###.", "J": "..###|...#.|...#.|...#.|...#.|#..#.|.##..",
    "K": "#...#|#..#.|#.#..|##...|#.#..|#..#.|#...#", "L": "#....|#....|#....|#....|#....|#....|#####",
    "M": "#...#|##.##|#.#.#|#.#.#|#...#|#...#|#...#", "N": "#...#|#...#|##..#|#.#.#|#..##|#...#|#...#",
    "O": ".###.|#...#|#...#|#...#|#...#|#...#|.###.", "P": "####.|#...#|#...#|####.|#....|#....|#....",
    "Q": ".###.|#...#|#...#|#...#|#.#.#|#..#.|.##.#", "R": "####.|#...#|#...#|####.|#.#..|#..#.|#...#",
    "S": ".####|#....|#....|.###.|....#|....#|####.", "T": "#####|..#..|..#..|..#..|..#..|..#..|..#..",
    "U": "#...#|#...#|#...#|#...#|#...#|#...#|.###.", "V": "#...#|#...#|#...#|#...#|#...#|.#.#.|..#..",
    "W": "#...#|#...#|#...#|#.#.#|#.#.#|#.#.#|.#.#.", "X": "#...#|#...#|.#.#.|..#..|.#.#.|#...#|#...#",
    "Y": "#...#|#...#|.#.#.|..#..|..#..|..#..|..#..", "Z": "#####|....#|...#.|..#..|.#...|#....|#####",
    "0": ".###.|#...#|#..##|#.#.#|##..#|#...#|.###.", "1": "..#..|.##..|..#..|..#..|..#..|..#..|.###.",
    "2": ".###.|#...#|....#|...#.|..#..|.#...|#####", "3": "####.|....#|....#|.###.|....#|....#|####.",
    "4": "...#.|..##.|.#.#.|#..#.|#####|...#.|...#.", "5": "#####|#....|####.|....#|....#|#...#|.###.",
    "6": ".###.|#....|#....|####.|#...#|#...#|.###.", "7": "#####|....#|...#.|..#..|.#...|.#...|.#...",
    "8": ".###.|#...#|#...#|.###.|#...#|#...#|.###.", "9": ".###.|#...#|#...#|.####|....#|....#|.###.",
    " ": ".....|.....|.....|.....|.....|.....|.....", ".": ".....|.....|.....|.....|.....|.##..|.##..",
    ",": ".....|.....|.....|.....|.##..|..#..|.#...", "!": "..#..|..#..|..#..|..#..|..#..|.....|..#..",
    "?": ".###.|#...#|....#|...#.|..#..|.....|..#..", "-": ".....|.....|.....|.###.|.....|.....|.....",
    ":": ".....|.##..|.##..|.....|.##..|.##..|.....", "'": "..#..|..#..|.#...|.....|.....|.....|.....",
    "/": "....#|....#|...#.|..#..|.#...|#....|#....", "@": ".###.|#...#|#.###|#.#.#|#.###|#....|.###.",
    ">": ".#...|..#..|...#.|....#|...#.|..#..|.#...", "<": "...#.|..#..|.#...|#....|.#...|..#..|...#.",
    "+": ".....|..#..|..#..|#####|..#..|..#..|.....", "&": ".##..|#..#.|#.#..|.#...|#.#.#|#..#.|.##.#",
    "(": "...#.|..#..|.#...|.#...|.#...|..#..|...#.", ")": ".#...|..#..|...#.|...#.|...#.|..#..|.#...",
    "_": ".....|.....|.....|.....|.....|.....|#####", "*": ".....|.....|.....|.##..|.##..|.....|.....",
    "=": ".....|.....|#####|.....|#####|.....|.....",
}
GLYPH = {k: np.array([[ch == "#" for ch in row] for row in v.split("|")]) for k, v in FONT.items()}
ARROW_UP = np.array([[ch == "#" for ch in r] for r in
                     ["....#....", "...###...", "..#####..", ".#######.", "...###...", "...###...", "...###...", "...###..."]])
IDENTICON = ["XX.XX", "XXXXX", ".X.X.", ".X.X.", "X.X.X"]
INDIGO = (91, 95, 214)


def text_w(s, scale=1):
    return (len(s) * 6 - 1) * scale


def fill(img, x0, y0, x1, y1, color):
    h, w = img.shape[:2]
    x0, x1 = max(0, int(x0)), min(w, int(x1))
    y0, y1 = max(0, int(y0)), min(h, int(y1))
    if x0 < x1 and y0 < y1:
        img[y0:y1, x0:x1] = color


def stamp(img, mask, x, y, color, scale=1, emis=None, ev=1.0):
    m = np.kron(mask, np.ones((scale, scale), bool)) if scale > 1 else mask
    h, w = img.shape[:2]
    mh, mw = m.shape
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(w, x + mw), min(h, y + mh)
    if x0 >= x1 or y0 >= y1:
        return
    sub = m[y0 - y:y1 - y, x0 - x:x1 - x]
    img[y0:y1, x0:x1][sub] = color
    if emis is not None:
        emis[y0:y1, x0:x1][sub] = ev


def text(img, x, y, s, color, scale=1, emis=None, ev=1.0, shadow=None):
    for i, ch in enumerate(s.upper()):
        g = GLYPH.get(ch, GLYPH["?"])
        if shadow is not None:
            o = max(1, scale // 2)
            stamp(img, g, x + i * 6 * scale + o, y + o, shadow, scale)
        stamp(img, g, x + i * 6 * scale, y, color, scale, emis, ev)


def ctext(img, cx, y, s, color, scale=1, **kw):
    text(img, int(round(cx - text_w(s, scale) / 2)), y, s, color, scale, **kw)


def line(img, pts, color, th=2, emis=None, ev=1.0):
    for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
        n = int(max(abs(xb - xa), abs(yb - ya)) * 2) + 1
        for t in np.linspace(0, 1, n):
            x = int(round(xa + (xb - xa) * t))
            y = int(round(ya + (yb - ya) * t))
            fill(img, x, y, x + th, y + th, color)
            if emis is not None:
                fill(emis, x, y, x + th, y + th, ev)


def grid(n):
    yy, xx = np.mgrid[0:n, 0:n]
    return xx + 0.5, yy + 0.5


# --------------------------------------------------------------- textures --
def tex_brick(seed=1, tint=(76, 74, 116)):
    rng = np.random.default_rng(seed)
    img = np.empty((TEX, TEX, 3), np.float32)
    img[:] = (30, 28, 46)
    for row in range(8):
        y0 = row * 16
        off = 16 if row % 2 else 0
        for col in range(5):
            xs = np.arange(col * 32 - off + 1, col * 32 - off + 31) % TEX
            c = np.array(tint, np.float32) + rng.normal(0, 7) + rng.normal(0, 3, 3)
            img[y0 + 1:y0 + 15, xs] = c
            img[y0 + 1, xs] += 14
            img[y0 + 14, xs] -= 16
    img += rng.normal(0, 4, (TEX, TEX, 1))
    specks = rng.random((TEX, TEX)) < 0.012
    img[specks] *= 0.6
    return np.clip(img, 0, 255), np.zeros((TEX, TEX), np.float32)


def tex_panel(seed=2):
    rng = np.random.default_rng(seed)
    img = np.empty((TEX, TEX, 3), np.float32)
    em = np.zeros((TEX, TEX), np.float32)
    img[:] = (30, 32, 48)
    for y0, y1 in ((0, 48), (80, 128)):
        img[y0:y1] = (48, 52, 72)
        img[y0 + 1, 1:-1] += 18
        img[y1 - 1] -= 18
        img[y0:y1, 1] += 10
        img[y0:y1, TEX - 2] -= 14
        for rx in (7, 118):
            for ry in (y0 + 6, y1 - 9):
                fill(img, rx, ry, rx + 3, ry + 3, (112, 116, 142))
                fill(img, rx + 1, ry + 3, rx + 4, ry + 4, (24, 24, 36))
    img[:, 0] = (18, 18, 28)
    img[:, TEX - 1] = (18, 18, 28)
    fill(img, 8, 61, 120, 67, (90, 95, 210))
    fill(em, 8, 61, 120, 67, 1.0)
    fill(img, 8, 63, 120, 65, (190, 195, 255))
    for lx in (18, 106):
        fill(img, lx, 52, lx + 4, 56, (255, 170, 80))
        fill(em, lx, 52, lx + 4, 56, 1.0)
    img += rng.normal(0, 2.5, (TEX, TEX, 1))
    return np.clip(img, 0, 255), em


def tex_floor(seed=3):
    rng = np.random.default_rng(seed)
    img = np.empty((TEX, TEX, 3), np.float32)
    for ty in range(2):
        for tx in range(2):
            c = (44, 42, 62) if (tx + ty) % 2 == 0 else (37, 35, 54)
            img[ty * 64:(ty + 1) * 64, tx * 64:(tx + 1) * 64] = c
    for g in (0, 1, 63, 64, 127):
        img[g, :] = (22, 20, 34)
        img[:, g] = (22, 20, 34)
    img += rng.normal(0, 3, (TEX, TEX, 1))
    return np.clip(img, 0, 255), np.zeros((TEX, TEX), np.float32)


def tex_ceiling(seed=4):
    rng = np.random.default_rng(seed)
    img = np.empty((TEX, TEX, 3), np.float32)
    img[:] = (30, 28, 44)
    for g in (0, 63, 64, 127):
        img[g, :] = (19, 18, 30)
        img[:, g] = (19, 18, 30)
    img += rng.normal(0, 2, (TEX, TEX, 1))
    return np.clip(img, 0, 255), np.zeros((TEX, TEX), np.float32)


def poster(base, frame, bg, box=(12, 8, 116, 118), glow=0.35):
    img, em = base[0].copy(), base[1].copy()
    x0, y0, x1, y1 = box
    img[y0 + 3:y1 + 3, x0 + 3:x1 + 3] *= 0.5
    fill(img, x0, y0, x1, y1, frame)
    fill(img, x0, y0, x1, y0 + 1, tuple(min(255, c + 50) for c in frame))
    fill(img, x0 + 3, y0 + 3, x1 - 3, y1 - 3, bg)
    fill(em, x0 + 3, y0 + 3, x1 - 3, y1 - 3, glow)
    return img, em


def tex_welcome(brick):
    img, em = poster(brick, INDIGO, (22, 20, 46))
    ctext(img, 64, 15, "WELCOME TO", (190, 192, 255), emis=em, ev=0.7)
    ctext(img, 64, 28, "ESCAPE", (255, 255, 255), 2, emis=em, ev=0.8)
    ctext(img, 64, 46, "THE", (255, 255, 255), 2, emis=em, ev=0.8)
    ctext(img, 64, 64, "README", (150, 155, 255), 2, emis=em, ev=0.9)
    fill(img, 30, 85, 98, 86, (91, 95, 214))
    ctext(img, 64, 91, "FIND THE EXIT", (255, 214, 120), emis=em, ev=0.8)
    ctext(img, 64, 103, "SEE MY WORK", (200, 200, 225), emis=em, ev=0.6)
    return img, em


def tex_ntest(brick):
    img, em = poster(brick, (40, 190, 170), (12, 32, 36))
    ctext(img, 64, 14, "NTEST", (255, 255, 255), 3, emis=em, ev=0.8)
    pts = [(18, 50), (40, 50), (45, 46), (50, 50), (56, 50), (60, 36), (65, 62), (70, 50),
           (78, 50), (83, 45), (88, 50), (110, 50)]
    line(img, pts, (90, 255, 200), 2, em, 1.0)
    ctext(img, 64, 67, "CLINICAL DATA", (235, 245, 245), emis=em, ev=0.6)
    ctext(img, 64, 78, "DIGITIZATION", (235, 245, 245), emis=em, ev=0.6)
    ctext(img, 64, 93, "ENGLISH+BANGLA", (120, 235, 210), emis=em, ev=0.7)
    ctext(img, 64, 104, "REACT+TAILWIND", (150, 175, 175), emis=em, ev=0.5)
    return img, em


def tex_findchild(brick):
    img, em = poster(brick, (240, 120, 60), (46, 20, 18))
    xx, yy = grid(TEX)
    disc = (xx - 64) ** 2 + (yy - 23) ** 2 <= 11.5 ** 2
    img[disc] = (245, 240, 235)
    em[disc] = 0.7
    fill(img, 61, 14, 67, 32, (225, 55, 45))
    fill(img, 55, 20, 73, 26, (225, 55, 45))
    ctext(img, 64, 38, "FIND", (255, 255, 255), 2, emis=em, ev=0.8)
    ctext(img, 64, 55, "EVERY", (255, 255, 255), 2, emis=em, ev=0.8)
    ctext(img, 64, 72, "CHILD", (255, 160, 90), 2, emis=em, ev=0.9)
    ctext(img, 64, 93, "MEASLES 2026", (255, 205, 175), emis=em, ev=0.6)
    ctext(img, 64, 104, "PROJECT Q2", (190, 160, 150), emis=em, ev=0.5)
    return img, em


def tex_behind(brick):
    img, em = poster(brick, (230, 200, 90), (34, 28, 16))
    ctext(img, 64, 16, "PSST...", (210, 200, 160), emis=em, ev=0.6)
    ctext(img, 64, 31, "EXIT IS", (255, 255, 255), 2, emis=em, ev=0.8)
    ctext(img, 64, 49, "BEHIND", (255, 255, 255), 2, emis=em, ev=0.8)
    ctext(img, 64, 67, "YOU!", (255, 220, 100), 2, emis=em, ev=0.9)
    ctext(img, 64, 93, "TURN AROUND", (225, 205, 150), emis=em, ev=0.6)
    return img, em


def tex_exit_sign(brick):
    img, em = brick[0].copy(), brick[1].copy()
    img[33:103, 17:117] *= 0.5
    fill(img, 14, 30, 114, 100, (64, 72, 84))
    fill(img, 16, 32, 112, 98, (14, 22, 18))
    ctext(img, 64, 40, "EXIT", (90, 255, 130), 3, emis=em, ev=1.0)
    ctext(img, 64, 72, "< GO AROUND >", (205, 225, 212), emis=em, ev=0.7)
    return img, em


def tex_door(panel):
    img, em = panel[0].copy(), panel[1].copy()
    fill(img, 28, 26, 100, 128, (72, 76, 94))
    fill(img, 32, 30, 96, 128, (38, 66, 54))
    fill(img, 32, 30, 96, 31, (70, 110, 90))
    xx, yy = grid(TEX)
    win = (xx >= 42) & (xx < 86) & (yy >= 40) & (yy < 72)
    t = np.clip((yy - 40) / 32, 0, 1)
    img[win] = np.stack([200 + 40 * t, 255 - 10 * t, 215 + 20 * t], -1)[win]
    em[win] = 1.0
    fill(img, 63, 40, 65, 72, (60, 100, 80))
    fill(img, 42, 55, 86, 57, (60, 100, 80))
    fill(img, 38, 84, 90, 86, (28, 50, 40))
    fill(img, 38, 104, 90, 106, (28, 50, 40))
    fill(img, 84, 90, 90, 96, (190, 192, 200))
    em[26:128, 28:100] = np.maximum(em[26:128, 28:100], 0.18)
    fill(img, 36, 4, 92, 23, (40, 90, 50))
    fill(img, 38, 6, 90, 21, (10, 30, 16))
    ctext(img, 64, 7, "EXIT", (90, 255, 130), 2, emis=em, ev=1.0)
    em[4:23, 36:92] = np.maximum(em[4:23, 36:92], 0.6)
    return img, em


def spr_lamp():
    rgb = np.zeros((TEX, TEX, 3), np.float32)
    a = np.zeros((TEX, TEX), bool)
    em = np.zeros((TEX, TEX), np.float32)
    xx, yy = grid(TEX)
    base = ((xx - 64) / 18) ** 2 + ((yy - 122) / 5) ** 2 <= 1
    rgb[base], a[base] = (44, 44, 60), True
    fill(rgb, 61, 34, 67, 122, (72, 74, 94))
    fill(rgb, 62, 34, 63, 122, (120, 122, 146))
    a[34:122, 61:67] = True
    fill(rgb, 57, 32, 71, 36, (56, 58, 76))
    a[32:36, 57:71] = True
    d = np.hypot(xx - 64, yy - 21)
    orb = d <= 12
    t = np.clip(d / 12, 0, 1)
    rgb[orb] = np.stack([255 + 0 * t, 240 - 50 * t, 200 - 90 * t], -1)[orb]
    a[orb], em[orb] = True, 1.0
    fill(rgb, 55, 6, 73, 10, (52, 54, 70))
    a[6:10, 55:73] = True
    return rgb, a, em


def spr_plant(seed=5):
    rng = np.random.default_rng(seed)
    rgb = np.zeros((TEX, TEX, 3), np.float32)
    a = np.zeros((TEX, TEX), bool)
    xx, yy = grid(TEX)
    for ang in (-78, -58, -40, -22, -6, 8, 24, 42, 60, 80, -30, 32):
        r = math.radians(ang + rng.normal(0, 4))
        dx, dy = math.sin(r), -math.cos(r)
        length = rng.uniform(52, 78)
        px, py = xx - 64, yy - 98
        t = px * dx + py * dy
        perp = np.abs(px * -dy + py * dx)
        width = 5.5 * (1 - t / length) + 0.8
        leaf = (t >= 0) & (t <= length) & (perp <= width)
        g = rng.uniform(0.8, 1.15)
        col = np.stack([np.full_like(t, 52 * g), 140 * g + 0.4 * t, 82 * g + 0.2 * t], -1)
        col[perp < 0.9] += 35
        rgb[leaf] = col[leaf]
        a[leaf] = True
    pot = (yy >= 96) & (yy < 127) & (np.abs(xx - 64) <= 22 - (yy - 96) * 6 / 31)
    rgb[pot] = (168, 92, 62)
    rgb[pot & (xx > 70)] = (140, 74, 50)
    a[pot] = True
    fill(rgb, 40, 93, 88, 100, (192, 110, 74))
    a[93:100, 40:88] = True
    fill(rgb, 44, 93, 84, 95, (60, 40, 30))
    return rgb, a, np.zeros((TEX, TEX), np.float32)


BRICK = tex_brick()
PANEL = tex_panel()
WALL_TEX = {
    "#": BRICK, "=": PANEL,
    "A": tex_ntest(BRICK), "B": tex_findchild(BRICK), "C": tex_welcome(tex_brick(7, (70, 70, 120))),
    "D": tex_behind(BRICK), "G": tex_exit_sign(BRICK), "X": tex_door(PANEL),
}
TEX_ORDER = list(WALL_TEX) + ["floor", "ceiling"]
TEX_ID = {k: i for i, k in enumerate(TEX_ORDER)}
_all = list(WALL_TEX.values()) + [tex_floor(), tex_ceiling()]
ATLAS = np.stack([t[0] for t in _all]).astype(np.float32)
EMIS = np.stack([t[1] for t in _all]).astype(np.float32)
FLOOR_ID, CEIL_ID = TEX_ID["floor"], TEX_ID["ceiling"]
SPR = {"L": spr_lamp(), "P": spr_plant()}


# --------------------------------------------------------------- renderer --
def lighting(wx, wy, dist):
    L = np.empty(np.shape(wx) + (3,), np.float32)
    L[:] = AMBIENT
    L += (0.95 * np.exp(-np.asarray(dist) * 0.42))[..., None] * np.array([1.0, 0.96, 0.92], np.float32)
    for lx, ly, col, inten, rad in LIGHTS:
        f = np.clip(1 - np.hypot(wx - lx, wy - ly) / rad, 0, 1) ** 2 * inten
        L += f[..., None] * col
    return L


def cast(px, py, rdx, rdy):
    mx, my = int(px), int(py)
    ddx = abs(1 / rdx) if rdx else 1e30
    ddy = abs(1 / rdy) if rdy else 1e30
    if rdx < 0:
        sx, sdx = -1, (px - mx) * ddx
    else:
        sx, sdx = 1, (mx + 1 - px) * ddx
    if rdy < 0:
        sy, sdy = -1, (py - my) * ddy
    else:
        sy, sdy = 1, (my + 1 - py) * ddy
    for _ in range(64):
        if sdx < sdy:
            sdx += ddx
            mx += sx
            side = 0
        else:
            sdy += ddy
            my += sy
            side = 1
        c = cell(mx, my)
        if c in WALLS:
            break
    perp = (sdx - ddx) if side == 0 else (sdy - ddy)
    perp = max(perp, 1e-3)
    wallx = (py + perp * rdy) if side == 0 else (px + perp * rdx)
    wallx -= math.floor(wallx)
    tx = int(wallx * TEX)
    # keep textures (and poster text) reading left-to-right from every side
    if (side == 0 and rdx < 0) or (side == 1 and rdy > 0):
        tx = TEX - 1 - tx
    return perp, side, TEX_ID[c], min(max(tx, 0), TEX - 1)


def render_view(px, py, ang):
    dx, dy = math.cos(ang), math.sin(ang)
    plx, ply = -dy * PLANE, dx * PLANE
    camx = (np.arange(RW) + 0.5) / RW * 2 - 1
    rdx = dx + plx * camx
    rdy = dy + ply * camx
    perp = np.empty(RW, np.float32)
    side = np.empty(RW, np.int32)
    tid = np.empty(RW, np.int32)
    tcol = np.empty(RW, np.int32)
    for x in range(RW):
        perp[x], side[x], tid[x], tcol[x] = cast(px, py, rdx[x], rdy[x])

    ys = (np.arange(RH) + 0.5)[:, None]
    lh = K / perp
    top = HORIZON - lh / 2
    wall = (ys >= top) & (ys < HORIZON + lh / 2)
    ty = np.clip(((ys - top) / lh * TEX).astype(np.int32), 0, TEX - 1)

    rowd = (K / 2) / np.abs(ys - HORIZON)
    fx = px + rowd * rdx[None, :]
    fy = py + rowd * rdy[None, :]
    is_floor = np.broadcast_to(ys > HORIZON, wall.shape)
    fu = ((fx % 1.0) * TEX).astype(np.int32) % TEX
    fv = ((fy % 1.0) * TEX).astype(np.int32) % TEX

    t_id = np.where(wall, tid[None, :], np.where(is_floor, FLOOR_ID, CEIL_ID))
    u = np.where(wall, tcol[None, :], fu)
    v = np.where(wall, ty, fv)
    col = ATLAS[t_id, v, u]
    emi = EMIS[t_id, v, u]

    hx, hy = px + perp * rdx, py + perp * rdy
    wx = np.where(wall, hx[None, :], fx)
    wy = np.where(wall, hy[None, :], fy)
    dist = np.where(wall, perp[None, :], rowd)
    shade = np.where(wall, np.where(side[None, :] == 1, 0.78, 1.0), np.where(is_floor, 1.0, 0.72))
    light = lighting(wx, wy, dist) * shade[..., None]
    light = np.maximum(light, emi[..., None] * 1.15)
    out = col * light
    fog = np.exp(-dist * 0.10)[..., None]
    out = out * fog + FOG * (1 - fog)

    glows = []
    inv = 1.0 / (plx * dy - dx * ply)
    items = []
    for sx, sy, kind in SPRITES:
        ox, oy = sx - px, sy - py
        tx = inv * (dy * ox - dx * oy)
        tz = inv * (-ply * ox + plx * oy)
        if tz > 0.25:
            items.append((tz, tx, sx, sy, kind))
    for tz, tx, sx, sy, kind in sorted(items, reverse=True):
        scx = (RW / 2) * (1 + tx / tz)
        h = K / tz
        w = (RW / 2) / (PLANE * tz)
        bottom = HORIZON + K / (2 * tz)
        top_s = bottom - h
        x0, x1 = max(0, int(math.floor(scx - w / 2))), min(RW, int(math.ceil(scx + w / 2)))
        y0, y1 = max(0, int(math.floor(top_s))), min(RH, int(math.ceil(bottom)))
        if x0 >= x1 or y0 >= y1:
            continue
        uu = np.clip(((np.arange(x0, x1) + 0.5 - (scx - w / 2)) / w * TEX).astype(int), 0, TEX - 1)
        vv = np.clip(((np.arange(y0, y1) + 0.5 - top_s) / h * TEX).astype(int), 0, TEX - 1)
        rgb, alpha, em = SPR[kind]
        srgb = rgb[vv[:, None], uu[None, :]]
        mask = alpha[vv[:, None], uu[None, :]] & (tz < perp[x0:x1])[None, :]
        lit = srgb * lighting(np.array(sx), np.array(sy), np.array(tz))
        lit = np.maximum(lit, srgb * em[vv[:, None], uu[None, :]][..., None] * 1.1)
        f = math.exp(-tz * 0.10)
        lit = lit * f + FOG * (1 - f)
        region = out[y0:y1, x0:x1]
        region[mask] = lit[mask]
        if kind == "L":
            cx = int(scx)
            if 0 <= cx < RW and tz < perp[cx]:
                glows.append((scx, top_s + 21 / 128 * h, 0.30 * h, math.exp(-tz * 0.18)))
    if glows:
        gx, gy = np.meshgrid(np.arange(RW) + 0.5, np.arange(RH) + 0.5)
        for cx, cy, r, s in glows:
            g = np.exp(-((gx - cx) ** 2 + (gy - cy) ** 2) / (r * r)) * s * 110
            out += g[..., None] * np.array([1.0, 0.8, 0.55], np.float32)
    return np.clip(out, 0, 255)


def zone(x, y):
    if 6 <= x <= 10 and y <= 5:
        return "THE LOBBY"
    if 6 <= x <= 10 and 6 <= y <= 10:
        return "LAMP PLAZA"
    if y >= 12:
        return "SOUTH HALL"
    return "WEST WING" if x < 8 else "EAST WING"


def draw_hud(cx, cy, facing):
    hud = np.empty((HUD_H, W, 3), np.float32)
    hud[:] = (16, 15, 30)
    hud[0] = INDIGO
    hud[1] = (40, 40, 80)
    fill(hud, 4, 4, 33, 33, (236, 236, 244))
    for r, row in enumerate(IDENTICON):
        for c, ch in enumerate(row):
            if ch == "X":
                fill(hud, 6 + c * 5, 6 + r * 5, 11 + c * 5, 11 + r * 5, INDIGO)
    text(hud, 40, 5, OWNER.upper(), (255, 255, 255))
    text(hud, 40, 15, zone(cx, cy), (255, 214, 120))
    text(hud, 40, 25, "FACING " + DNAME[facing], (160, 160, 190))
    fill(hud, 196, 4, 197, 33, (50, 50, 90))
    text(hud, 204, 5, "COMPASS", (120, 120, 170))
    ctext(hud, 225, 14, facing, (255, 214, 120), 2)
    fill(hud, 254, 4, 255, 33, (50, 50, 90))
    # minimap of the playable area
    xs = [x for y in range(MH) for x in range(MW) if LEVEL[y][x] not in "#"]
    ys = [y for y in range(MH) for x in range(MW) if LEVEL[y][x] not in "#"]
    bx0, by0 = min(xs) - 1, min(ys) - 1
    bx1, by1 = max(xs) + 1, max(ys) + 1
    ox = W - 3 - (bx1 - bx0 + 1) * 2
    oy = 3 + max(0, (30 - (by1 - by0 + 1) * 2) // 2)
    colours = {".": (26, 24, 44), "S": (26, 24, 44), "L": (255, 200, 120), "P": (70, 150, 90),
               "A": (40, 200, 175), "B": (240, 120, 60), "C": INDIGO, "X": (90, 255, 130),
               "G": (60, 140, 80), "D": (230, 200, 90), "=": (64, 66, 100), "#": (54, 52, 84)}
    for y in range(by0, by1 + 1):
        for x in range(bx0, bx1 + 1):
            c = cell(x, y)
            fill(hud, ox + (x - bx0) * 2, oy + (y - by0) * 2, ox + (x - bx0) * 2 + 2, oy + (y - by0) * 2 + 2,
                 colours.get(c, (54, 52, 84)))
    fx_, fy_ = cx + DVEC[facing][0], cy + DVEC[facing][1]
    fill(hud, ox + (fx_ - bx0) * 2, oy + (fy_ - by0) * 2, ox + (fx_ - bx0) * 2 + 2, oy + (fy_ - by0) * 2 + 2, (150, 120, 40))
    fill(hud, ox + (cx - bx0) * 2, oy + (cy - by0) * 2, ox + (cx - bx0) * 2 + 2, oy + (cy - by0) * 2 + 2, (255, 230, 90))
    return hud


def finish(view, hud):
    view = view.copy()
    view[1::2] *= 0.9   # faint CRT scanlines
    hud = np.repeat(np.repeat(hud, UPSCALE, 0), UPSCALE, 1)
    return Image.fromarray(np.clip(np.concatenate([view, hud], 0), 0, 255).astype(np.uint8))


def camera(cx, cy, ang):
    return cx + 0.5 - math.cos(ang) * BACK, cy + 0.5 - math.sin(ang) * BACK


def frame(x, y, d):
    return finish(render_view(*camera(x, y, DANG[d]), DANG[d]), draw_hud(x, y, d))


# --------------------------------------------------------------------- ui --
def keycap(label, glyph, face=(66, 64, 116), ink=(255, 255, 255), w=40, h=30):
    img = np.zeros((h, w, 4), np.float32)
    rgb = img[..., :3]
    fill(rgb, 1, 0, w - 1, h, (14, 12, 28))
    fill(rgb, 0, 1, w, h - 1, (14, 12, 28))
    fill(rgb, 2, h - 6, w - 2, h - 1, tuple(c * 0.55 for c in face))
    fill(rgb, 1, 1, w - 1, h - 6, face)
    fill(rgb, 2, 1, w - 2, 2, tuple(min(255, c + 45) for c in face))
    img[..., 3] = 0
    img[0:h, 1:w - 1, 3] = 255
    img[1:h - 1, 0:w, 3] = 255
    if glyph is not None:
        gh, gw = glyph.shape
        stamp(rgb, glyph, (w - gw) // 2, 4, ink)
    ctext(rgb, w / 2, h - 15 if glyph is not None else (h - 13) // 2, label, ink)
    big = np.repeat(np.repeat(img, UPSCALE, 0), UPSCALE, 1)
    return Image.fromarray(big.astype(np.uint8))


ARROW_RUN = np.array([[ch == "#" for ch in r] for r in
                      ["....#....", "...###...", "..##.##..", ".##...##.", "....#....", "...###...", "..##.##..", ".##...##."]])
OFF = dict(face=(44, 44, 54), ink=(110, 110, 125))


def build_ui(out):
    up = ARROW_UP
    caps = {
        "left": keycap("LEFT", np.rot90(up, 1)),
        "right": keycap("RIGHT", np.rot90(up, -1)),
        "up": keycap("WALK", up),
        "back": keycap("TURN", up[::-1]),
        "up_off": keycap("WALL", up, **OFF),
        "run": keycap("RUN", ARROW_RUN, face=(122, 84, 168)),
        "run_off": keycap("RUN", ARROW_RUN, **OFF),
        "open": keycap("OPEN", up, face=(26, 120, 108)),
        "exit": keycap("EXIT", up, face=(34, 130, 64)),
        "start": keycap("START", None, face=INDIGO, w=64, h=22),
    }
    for name, im in caps.items():
        im.save(os.path.join(out, f"{name}.png"), optimize=True)


# ------------------------------------------------------------------ pages --
def key(x, y, d):
    return f"{x}-{y}-{d}"


def ahead(x, y, d):
    """First wall straight ahead and how many steps away it is."""
    vx, vy = DVEC[d]
    n = 0
    while True:
        x, y, n = x + vx, y + vy, n + 1
        c = cell(x, y)
        if c in WALLS:
            return c, n


def forward(x, y, d):
    nx, ny = x + DVEC[d][0], y + DVEC[d][1]
    c = cell(nx, ny)
    if walkable(nx, ny):
        return f"{key(nx, ny, d)}.md", "up", "Walk forward"
    if c == "X":
        return "win.md", "exit", "Escape!"
    if c in POSTERS and POSTERS[c]["url"]:
        return POSTERS[c]["url"], "open", f"Open {POSTERS[c]['name']}"
    return None, "up_off", "Blocked"


def run_target(x, y, d):
    """Keep walking until there's something to stop for: a side opening, a poster or a wall ahead."""
    vx, vy = DVEC[d]
    sx, sy = DVEC[turn(d, 1)]
    n = 0
    while walkable(x + vx, y + vy):
        x, y, n = x + vx, y + vy, n + 1
        if any(walkable(x + k * sx, y + k * sy) or cell(x + k * sx, y + k * sy) in "ABCDGX" for k in (-1, 1)):
            break
    return x, y, n


# Images link straight to raw.githubusercontent.com. GitHub's own relative image links
# go through an uncacheable redirect, which would defeat the preloading below.
# For a local preview, build with ASSET_BASE=../
ASSET_BASE = os.environ.get("ASSET_BASE", f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/")


def img(path, width, alt):
    return f'<img src="{ASSET_BASE}{path}" width="{width}" alt="{alt}">'


def button(href, cap, width, alt):
    b = img(f"ui/{cap}.png", width, alt)
    return f'<a href="{href}">{b}</a>' if href else b


def preload(keys):
    """Tiny copies of the views one click away, so the next frame is already cached."""
    return "".join(f'<img src="{ASSET_BASE}frames/{k}.webp" width="1" height="1" alt="">' for k in dict.fromkeys(keys))


FOOTER = ('<sub><b>WALK</b> (or click the view) steps forward · <b>RUN</b> dashes to the next junction · '
          f'<a href="start.md">restart</a> · <a href="../README.md">how this works</a> · '
          f'<a href="{PROFILE}">back to my profile</a></sub>')


def page(x, y, d):
    fwd, cap, fwd_alt = forward(x, y, d)
    rx, ry, rn = run_target(x, y, d)
    run = f"{key(rx, ry, d)}.md" if rn >= 2 else None
    wall, dist = ahead(x, y, d)
    hint = ""
    if wall == "X":
        hint = "🚪 <b>The exit!</b> Press <b>EXIT</b> to escape." if dist == 1 else "🚪 That green glow up ahead is the way out."
    elif wall in POSTERS and dist <= 6:
        p = POSTERS[wall]
        hint = p["hint"]
        if p["url"]:
            hint += f' <a href="{p["url"]}">Open the repo ↗</a>'
    view = img(f"frames/{key(x, y, d)}.webp", 640, f"First-person view in {zone(x, y).title()}, facing {DNAME[d].lower()}")
    view = f'<a href="{fwd}">{view}</a>' if fwd else view
    nxt = [key(x, y, turn(d, k)) for k in (-1, 1, 2)]
    if walkable(x + DVEC[d][0], y + DVEC[d][1]):
        nxt.insert(0, key(x + DVEC[d][0], y + DVEC[d][1], d))
    if run:
        nxt.insert(1, key(rx, ry, d))
    if fwd == "win.md":
        nxt.insert(0, "win")
    return "\n".join([
        "<!-- Escape the README · generated by tools/build.py -->",
        '<div align="center">',
        "",
        button(f"{key(x, y, turn(d, -1))}.md", "left", 76, "Turn left"),
        button(fwd, cap, 76, fwd_alt),
        button(run, "run" if run else "run_off", 76, "Run to the next junction" if run else "Nowhere to run"),
        button(f"{key(x, y, turn(d, 1))}.md", "right", 76, "Turn right"),
        button(f"{key(x, y, turn(d, 2))}.md", "back", 76, "Turn around"),
        "",
        view,
        "",
        hint,
        "",
        FOOTER,
        "",
        preload(nxt),
        "",
        "</div>",
        "",
    ])


def title_frames():
    sx, sy = START
    base = render_view(*camera(3, 13, DANG["E"]), DANG["E"]) * 0.45 + FOG * 0.35
    frames = []
    for blink in (True, False):
        v = base.copy()
        u = UPSCALE
        ctext(v, RW / 2, 26 * u, "ESCAPE THE", (200, 202, 255), 3 * u, shadow=(0, 0, 0))
        ctext(v, RW / 2, 52 * u, "README", (255, 255, 255), 5 * u, shadow=(40, 30, 120))
        ctext(v, RW / 2, 100 * u, "A TINY FIRST-PERSON GAME", (180, 180, 210), u, shadow=(0, 0, 0))
        ctext(v, RW / 2, 110 * u, "THAT RUNS INSIDE GITHUB", (180, 180, 210), u, shadow=(0, 0, 0))
        if blink:
            ctext(v, RW / 2, 136 * u, "CLICK TO START", (255, 214, 120), 2 * u, shadow=(0, 0, 0))
        frames.append(finish(v, draw_hud(sx, sy, "N")))
    return frames


def win_image():
    img = np.empty((H, W, 3), np.float32)
    t = np.linspace(0, 1, H)[:, None]
    img[:] = (np.array([22, 16, 60]) * (1 - t) + np.array([250, 150, 110]) * t)[:, None, :]
    rng = np.random.default_rng(9)
    for _ in range(70):
        x, y = rng.integers(0, W), rng.integers(0, 90)
        img[y, x] = (255, 255, 255) if rng.random() < 0.5 else (200, 200, 255)
    xx, yy = np.meshgrid(np.arange(W) + 0.5, np.arange(H) + 0.5)
    sun = np.hypot(xx - 250, yy - 168) < 26
    img[sun] = (255, 220, 150)
    for i in range(3):
        img[(yy > 150 + i * 6) & (yy < 152 + i * 6) & sun] = (250, 150, 110)
    hills = yy > 176 + 8 * np.sin(xx / 23) + 5 * np.sin(xx / 9)
    img[hills] = (34, 22, 54)
    fill(img, 145, 112, 175, 142, (236, 236, 244))
    for r, row in enumerate(IDENTICON):
        for c, ch in enumerate(row):
            if ch == "X":
                fill(img, 148 + c * 5, 115 + r * 5, 153 + c * 5, 120 + r * 5, INDIGO)
    ctext(img, W / 2, 24, "YOU ESCAPED!", (255, 255, 255), 4, shadow=(40, 30, 120))
    ctext(img, W / 2, 64, "THE README IS BEHIND YOU", (255, 225, 180), shadow=(30, 20, 60))
    ctext(img, W / 2, 82, "THANKS FOR PLAYING", (220, 215, 255), 2, shadow=(30, 20, 60))
    ctext(img, W / 2, 148, "- TANZUO017 -", (255, 255, 255), shadow=(30, 20, 60))
    big = np.repeat(np.repeat(img, UPSCALE, 0), UPSCALE, 1)
    return Image.fromarray(np.clip(big, 0, 255).astype(np.uint8))


def map_image():
    s = 14
    img = np.zeros((MH * s, MW * s, 3), np.float32)
    colours = {".": (36, 34, 56), "S": (36, 34, 56), "L": (36, 34, 56), "P": (36, 34, 56),
               "A": (40, 200, 175), "B": (240, 120, 60), "C": INDIGO, "X": (90, 255, 130),
               "G": (60, 160, 90), "D": (230, 200, 90), "=": (70, 72, 108), "#": (18, 16, 30)}
    for y in range(MH):
        for x in range(MW):
            c = cell(x, y)
            fill(img, x * s, y * s, x * s + s, y * s + s, colours[c])
            if c in "=#" and any(walkable(x + a, y + b) or cell(x + a, y + b) in "LP"
                                 for a, b in DVEC.values()):
                fill(img, x * s, y * s, x * s + s, y * s + s, (70, 72, 108))
            if c == "L":
                fill(img, x * s + 4, y * s + 4, x * s + s - 4, y * s + s - 4, (255, 200, 120))
            if c == "P":
                fill(img, x * s + 4, y * s + 4, x * s + s - 4, y * s + s - 4, (70, 160, 90))
            if c == "S":
                ctext(img, x * s + s / 2, y * s + 4, "S", (255, 230, 90))
    big = np.repeat(np.repeat(img, 2, 0), 2, 1)
    return Image.fromarray(big.astype(np.uint8))


def preview_anim(path):
    """A smooth walk from the lobby to the NTEST poster, for the profile README."""
    sx, sy = START
    keys = [((sx, sy), -90, 10)]
    route = [("turn", 90, 14), ("walk", (sx, sy + 5), 25), ("turn", 180, 6),
             ("walk", (2, sy + 5), 30), ("turn", 270, 6), ("walk", (2, 5), 15), ("hold", None, 16)]
    pos, ang = (sx, sy), -90.0
    shots = [(pos, ang)] * 10
    for kind, target, n in route:
        if kind == "turn":
            shots += [(pos, ang + (target - ang) * (i + 1) / n) for i in range(n)]
            ang = float(target)
        elif kind == "walk":
            shots += [((pos[0] + (target[0] - pos[0]) * (i + 1) / n, pos[1] + (target[1] - pos[1]) * (i + 1) / n), ang)
                      for i in range(n)]
            pos = target
        else:
            shots += [(pos, ang)] * n
    frames = []
    for (fx, fy), a in shots:
        r = math.radians(a)
        facing = DIRS[int(round(((a + 90) % 360) / 90)) % 4]
        view = render_view(*camera(fx, fy, r), r)
        frames.append(finish(view, draw_hud(int(round(fx)), int(round(fy)), facing)))
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=70, loop=0, quality=72, method=4)


def main():
    for d in ("play", "frames", "ui", "static"):
        p = os.path.join(ROOT, d)
        if os.path.isdir(p):
            shutil.rmtree(p)
        os.makedirs(p)
    build_ui(os.path.join(ROOT, "ui"))

    states = [(x, y, d) for y in range(MH) for x in range(MW) if walkable(x, y) for d in DIRS]
    for i, (x, y, d) in enumerate(states):
        frame(x, y, d).save(os.path.join(ROOT, "frames", f"{key(x, y, d)}.webp"), quality=82, method=6)
        with open(os.path.join(ROOT, "play", f"{key(x, y, d)}.md"), "w") as f:
            f.write(page(x, y, d))
        if i % 40 == 0:
            print(f"  rendered {i}/{len(states)}")

    sx, sy = START
    first = f"{key(sx, sy, 'N')}.md"
    t = title_frames()
    t[0].save(os.path.join(ROOT, "frames", "title.gif"), save_all=True, append_images=t[1:], duration=650, loop=0)
    with open(os.path.join(ROOT, "play", "start.md"), "w") as f:
        f.write("\n".join([
            "<!-- Escape the README · generated by tools/build.py -->",
            '<div align="center">', "",
            button(first, "start", 128, "Start"), "",
            f'<a href="{first}">{img("frames/title.gif", 640, "Escape the README: click to start")}</a>', "",
            "<b>How to play:</b> <b>WALK</b> steps forward, <b>RUN</b> dashes to the next junction, "
            "<b>LEFT</b>/<b>RIGHT</b> turn 90°, <b>TURN</b> spins you around.<br>",
            "Find the exit. My projects are hanging on the walls along the way.", "",
            f'<sub><a href="../README.md">how this works</a> · <a href="{PROFILE}">back to my profile</a></sub>', "",
            preload([key(sx, sy, "N"), key(sx, sy, "S")]) + "".join(
                f'<img src="{ASSET_BASE}ui/{u}.png" width="1" height="1" alt="">'
                for u in ("left", "up", "run", "run_off", "right", "back")), "",
            "</div>", ""]))

    win_image().save(os.path.join(ROOT, "frames", "win.webp"), quality=90, method=6)
    with open(os.path.join(ROOT, "play", "win.md"), "w") as f:
        f.write("\n".join([
            "<!-- Escape the README · generated by tools/build.py -->",
            '<div align="center">', "",
            img("frames/win.webp", 640, "You escaped the README!"), "",
            "### You made it out 🎉", "",
            "Thanks for playing! While you're here:", "",
            f'<a href="{POSTERS["A"]["url"]}"><b>NTEST</b></a>: bilingual clinical data-entry tool<br>',
            f'<a href="{POSTERS["B"]["url"]}"><b>Find Every Child</b></a>: measles outbreak response campaign site', "",
            f'<a href="{PROFILE}"><img src="https://img.shields.io/badge/follow-{OWNER}-5b5fd6?style=for-the-badge&logo=github" alt="Follow {OWNER}"></a>', "",
            f'<sub><a href="start.md">play again</a> · <a href="../README.md">how this works</a> · '
            f'<a href="https://github.com/{OWNER}/{REPO}">⭐ star the game</a></sub>', "",
            "</div>", ""]))

    map_image().save(os.path.join(ROOT, "static", "map.png"), optimize=True)
    print("  rendering preview animation…")
    preview_anim(os.path.join(ROOT, "static", "preview.webp"))
    print(f"done: {len(states)} states")


if __name__ == "__main__":
    main()
