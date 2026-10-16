"""Pixel-art header: a road cyclist hops onto "Hi, I'm Théodore", rides the letters and the mountain.

Regenerate the README header GIFs (needs Pillow):
    pip install pillow
    python .github/header/cyclist.py              # writes assets/header-light.gif + header-dark.gif
    HEADER_FONT=/path/to/font.ttf python .github/header/cyclist.py   # use a different font
"""
import math, os, sys
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets")
SCALE = 3                       # screen pixels per art pixel
W, H = 300, 46                  # art pixels (-> 900 x 138)
ROAD = H - 2                    # y of the road surface
FRAMES = 190
TEXT = "Hi, I'm Théodore"
FONT = os.environ.get("HEADER_FONT", "/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf")  # macOS default
FONT_SIZE = 23

PAL = {
    "clear": (0, 0, 0), "tire": (110, 118, 129), "frame": (59, 130, 196),
    "jersey": (46, 160, 67), "skin": (240, 190, 150), "skin2": (205, 152, 115),
    "shorts": (22, 24, 28), "helmet": (246, 248, 250), "road": (139, 148, 158),
    "chrome": (175, 184, 193), "outline": (125, 133, 144), "text": (31, 35, 40),
    "rock": (110, 118, 129), "rock2": (87, 96, 106), "snow": (246, 248, 250),
    "sun": (247, 190, 60), "sun2": (240, 140, 50),
}
TEXT_COLOR = {"light": (31, 35, 40), "dark": (230, 237, 243)}
NAMES = list(PAL)
IDX = {n: i for i, n in enumerate(NAMES)}


# ---------- static scenery: lettering + mountain + sun ----------
def build_scenery():
    img = Image.new("P", (W, H), 0)
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, FONT_SIZE)
    l, t, r, b = d.textbbox((0, 0), TEXT, font=font)
    tw = r - l
    mtn_w, gap = 64, 8
    x_text = (W - (tw + gap + mtn_w)) // 2
    # crisp (non-antialiased) glyphs: render greyscale, then threshold
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).text((x_text - l, ROAD - b), TEXT, font=font, fill=255)
    img.paste(IDX["text"], mask=mask.point(lambda v: 255 if v > 110 else 0).convert("1"))
    # mountain with a snow cap
    mx0, peak = x_text + tw + gap, ROAD - 22
    mx1, cx = mx0 + mtn_w, mx0 + mtn_w // 2
    d.polygon([(mx0, ROAD), (cx, peak), (mx1, ROAD)], fill=IDX["rock"])
    d.polygon([(cx, peak), (mx1, ROAD), (cx + 4, ROAD)], fill=IDX["rock2"])
    d.polygon([(cx - 5, peak + 7), (cx, peak), (cx + 5, peak + 7), (cx + 2, peak + 5), (cx - 2, peak + 6)], fill=IDX["snow"])
    return img, (cx, peak)


def draw_sun(d, f, cx, cy):
    d.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=IDX["sun"])
    for k in range(8):                                   # slowly turning rays
        a = k * math.pi / 4 + f * 0.03
        d.line([(cx + 6 * math.cos(a), cy + 6 * math.sin(a)), (cx + 8 * math.cos(a), cy + 8 * math.sin(a))], fill=IDX["sun2"])


def skyline(scenery):
    """y of the surface a wheel rests on at each column (letters, mountain or road)."""
    px = scenery.load()
    solid = (IDX["text"], IDX["rock"], IDX["rock2"], IDX["snow"])
    return [next((y for y in range(H) if px[x, y] in solid), ROAD + 1) - 1 for x in range(W)]


def trajectory(sky, frames, travel, start=-20):
    """Rear-hub (x, y, tilt, grounded) per frame: ride on surfaces, hop up steps, fly off edges."""
    G, LOOK, WHEEL, SPAN, CLOSE = 0.28, 26, 5, 16, 11
    pad = 40
    xs = range(-pad, W + pad)
    sk = lambda x: sky[min(W - 1, max(0, x))]
    # highest point under the bike, then a morphological closing that fills the
    # dips between letters narrower than ~2*CLOSE px, so the bike glides across them
    contact = {x: min(sk(x + i) for i in range(-1, SPAN + 1)) - WHEEL for x in xs}
    lo = {x: min(contact[min(max(x + i, -pad), W + pad - 1)] for i in range(-CLOSE, CLOSE + 1)) for x in xs}
    surf_tab = {x: max(lo[min(max(x + i, -pad), W + pad - 1)] for i in range(-CLOSE, CLOSE + 1)) for x in xs}
    # soften the pixel staircase on slopes, then interpolate between columns
    clamp = lambda x: min(max(x, -pad), W + pad - 1)
    smooth = {x: sum(surf_tab[clamp(x + i)] for i in range(-3, 4)) / 7 for x in xs}

    def surf(x):
        x0 = math.floor(x)
        return smooth[clamp(x0)] + (smooth[clamp(x0 + 1)] - smooth[clamp(x0)]) * (x - x0)

    dx = travel / frames
    x, y, vy, grounded, raw = start, surf(start), 0.0, True, []
    for _ in range(frames):
        ground = surf(x)
        if grounded:
            ahead = [(i, y - surf(x + i)) for i in range(1, LOOK)]
            if max(r - i * 0.75 for i, r in ahead) > 1.5:           # wall ahead -> hop
                need = max(r for _, r in ahead) + 3
                vy, grounded = -math.sqrt(2 * G * need), False
            elif ground > y + 2.6:                                   # edge -> roll off
                vy, grounded = 0.6, False
            else:                                                    # ride: follow the surface
                y = ground
        if not grounded:
            vy += G
            y += vy
            if vy > 0 and y >= ground:
                y, vy, grounded = ground, 0.0, True
        raw.append([x, y, vy, grounded])
        x += dx

    # tilt from the path itself (where the wheels actually are), eased between frames
    out, tilt = [], 0.0
    for i, (x, y, vy, grounded) in enumerate(raw):
        if grounded:
            j = min(len(raw) - 1, i + max(1, round(SPAN / dx)))
            target = math.atan2(raw[j][1] - y, raw[j][0] - x) if raw[j][3] else 0.0
        else:
            target = math.atan2(vy, dx) * 0.45
        target = max(-0.45, min(0.45, target))
        tilt += (target - tilt) * 0.3
        out.append((x, y, tilt, grounded))
    return out


# ---------- rider ----------
def ik(hip, foot, l1=4.6, l2=4.6):
    dx, dy = foot[0] - hip[0], foot[1] - hip[1]
    dist = min(math.hypot(dx, dy), l1 + l2 - 0.01)
    a = math.atan2(dy, dx)
    b = math.acos((l1 * l1 + dist * dist - l2 * l2) / (2 * l1 * dist))
    return hip[0] + l1 * math.cos(a - b), hip[1] + l1 * math.sin(a - b)


def draw_rider(d, R, tilt, t):
    """Rear hub at R, bike tilted by `tilt` radians (negative = climbing)."""
    ca, sa = math.cos(tilt), math.sin(tilt)
    P = lambda x, y: (R[0] + x * ca - y * sa, R[1] + x * sa + y * ca)   # bike frame -> screen
    L = lambda a, b, c, w=1: d.line([a, b], fill=IDX[c], width=w)

    F, BB, S, Hh = P(15, 0), P(6, 0), P(5, -7), P(13, -7)
    for cx, cy in (R, F):
        d.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], outline=IDX["tire"])
        for k in range(2):
            a = t * 0.9 + k * math.pi / 2
            L((cx - 4 * math.cos(a), cy - 4 * math.sin(a)), (cx + 4 * math.cos(a), cy + 4 * math.sin(a)), "chrome")
    L(R, BB, "frame"); L(R, S, "frame"); L(BB, S, "frame")
    L(S, Hh, "frame"); L(BB, P(13, -6), "frame"); L(Hh, F, "frame")
    L(P(4, -8), P(7, -8), "shorts")                                       # saddle
    L(Hh, P(15, -7), "chrome"); L(P(15, -7), P(15, -5), "chrome")         # drop bar

    hip, shoulder = P(5.5, -9), P(11, -12)
    for phase, col in ((math.pi, "skin2"), (0.0, "skin")):
        a = t + phase
        foot = (BB[0] + 2.2 * math.cos(a), BB[1] + 2.2 * math.sin(a))
        knee = ik(hip, foot)
        L(hip, knee, "shorts", 2); L(knee, foot, col)
    L(hip, shoulder, "jersey", 3)
    L(P(11, -11), P(14, -8), "skin")                                      # arm
    hx, hy = P(13, -14)
    d.rectangle([hx, hy, hx + 1, hy + 1], fill=IDX["skin"])
    d.line([(hx - 1, hy - 1), (hx + 2, hy - 1)], fill=IDX["helmet"])
    d.point((hx - 2, hy), fill=IDX["helmet"])


def outline(img, names=("helmet", "shorts", "snow")):
    """Grey 1px outline around white/black parts so they read on light and dark backgrounds."""
    px, (w, h) = img.load(), img.size
    want = {IDX[n] for n in names}
    edge = [(x + dx, y + dy) for y in range(h) for x in range(w) if px[x, y] in want
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            if 0 <= x + dx < w and 0 <= y + dy < h and px[x + dx, y + dy] == 0]
    for x, y in edge:
        px[x, y] = IDX["outline"]


# ---------- render ----------
scenery, (peak_x, peak_y) = build_scenery()
sky = skyline(scenery)
sun = (min(W - 10, peak_x + 22), 9)
travel = W + 40
path = trajectory(sky, FRAMES, travel)

frames, phase = [], 0.0
for f, (xr, rear_y, tilt, grounded) in enumerate(path):
    phase += 0.55 if grounded else 0.0
    img = scenery.copy()
    d = ImageDraw.Draw(img)
    for x in range(-int(f * 2) % 8 - 8, W, 8):                         # road dashes
        d.line([(x, H - 1), (x + 3, H - 1)], fill=IDX["road"])
    draw_sun(d, f, *sun)
    for k in range(3):                                                 # speed lines
        y = rear_y - 7 + 3 * k
        d.line([(xr - 9 - 3 * k, y), (xr - 6 - 3 * k, y)], fill=IDX["road"])
    draw_rider(d, (xr, rear_y), tilt, phase)                         # pedals pause in the air
    outline(img)
    frames.append(img)

for theme, text_rgb in TEXT_COLOR.items():
    pal = dict(PAL, text=text_rgb)
    flat = [c for n in NAMES for c in pal[n]] + [0] * (768 - 3 * len(NAMES))
    out = []
    for fr in frames:
        fr = fr.copy(); fr.putpalette(flat)
        out.append(fr.resize((W * SCALE, H * SCALE), Image.NEAREST))
    path = f"{OUT_DIR}/header-{theme}.gif"
    out[0].save(path, save_all=True, append_images=out[1:], duration=40, loop=0,
                transparency=0, disposal=2, optimize=False)
    print(path, out[0].size, len(out), "frames")
