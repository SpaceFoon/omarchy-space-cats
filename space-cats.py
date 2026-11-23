#!/usr/bin/python3
"""space-cats: a very animated, almost-ASCII terminal screensaver for Omarchy.

Run it directly in any truecolor terminal to preview; any key quits.
Stdlib only. Colours follow the current Omarchy theme when one is set.
"""
import math
import os
import random
import re
import select
import signal
import sys
import time

TAU = math.tau
FPS = 30
U = random.uniform
WHITE = (235, 240, 255)


# ───────────────────────────── colour helpers ─────────────────────────────

def load_palette():
    fallback = [(122, 162, 247), (187, 154, 247), (125, 207, 255), (158, 206, 106),
                (224, 175, 104), (247, 118, 142), (255, 158, 100)]
    try:
        with open(os.path.expanduser("~/.local/state/omarchy/current/theme/colors.toml")) as f:
            txt = f.read()
    except OSError:
        return fallback
    cols = []
    for hexv in re.findall(r'^\s*\w+\s*=\s*"#([0-9a-fA-F]{6})"', txt, re.M):
        c = tuple(int(hexv[i:i + 2], 16) for i in (0, 2, 4))
        if max(c) > 140 and max(c) - min(c) > 40 and c not in cols:  # bright + saturated only
            cols.append(c)
    return cols if len(cols) >= 3 else fallback


def dim(c, f):
    f = 0.0 if f < 0 else 1.0 if f > 1 else f
    return (int(c[0] * f) & ~7, int(c[1] * f) & ~7, int(c[2] * f) & ~7)


def mix(a, b, t):
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t), int(a[2] + (b[2] - a[2]) * t))


def ramp(cols, f):
    f = min(max(f, 0.0), 0.9999) * (len(cols) - 1)
    i = int(f)
    return mix(cols[i], cols[i + 1], f - i)


_sgr = {}


def sgr(c):
    s = _sgr.get(c)
    if s is None:
        if len(_sgr) > 8000:
            _sgr.clear()
        # 3 values = foreground on the default background; 6 = foreground + background
        s = _sgr[c] = ("\x1b[49;38;2;%d;%d;%dm" if len(c) == 3 else "\x1b[38;2;%d;%d;%d;48;2;%d;%d;%dm") % c
    return s


# ───────────────────────────────── screen ─────────────────────────────────

class Screen:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.clear()

    def clear(self):
        w = self.w
        self.ch = [[" "] * w for _ in range(self.h)]
        self.co = [[WHITE] * w for _ in range(self.h)]

    def put(self, x, y, ch, col):
        x = int(x)
        y = int(y)
        if 0 <= x < self.w and 0 <= y < self.h:
            self.ch[y][x] = ch
            self.co[y][x] = col

    def text(self, x, y, s, col):
        x = int(x)
        for i, c in enumerate(s):
            if c != " ":
                self.put(x + i, y, c, col)

    def sprite(self, lines, x, y, col, over=None, t=0.0):
        """Space is transparent, ¬ is an opaque blank. over maps char -> colour or fn(i, j, t)."""
        x = int(round(x))
        y = int(round(y))
        for j, line in enumerate(lines):
            for i, c in enumerate(line):
                if c == " ":
                    continue
                k = col
                if c == "■":
                    k = SHADE
                elif over and c in over:
                    k = over[c]
                    if callable(k):
                        k = k(i, j, t)
                self.put(x + i, y + j, " " if c == "¬" else c, k)

    def render(self, x0=0, w=None, y0=0, h=None):
        """Render the (x0, y0, w, h) window of the canvas; defaults to all of it."""
        w = self.w - x0 if w is None else w
        h = self.h - y0 if h is None else h
        out = []
        for y in range(y0, y0 + h):
            if y >= self.h:
                out.append("")
                continue
            row, cr = self.ch[y], self.co[y]
            parts = []
            last = None
            for x in range(x0, min(x0 + w, self.w)):
                c = row[x]
                if c != " ":
                    k = cr[x]
                    if k != last:
                        parts.append(sgr(k))
                        last = k
                elif last is not None and len(last) == 6:  # don't let a background bleed into empty space
                    parts.append("\x1b[49m")
                    last = None
                parts.append(c)
            if last is not None and len(last) == 6:
                parts.append("\x1b[49m")
            out.append("".join(parts))
        return "\x1b[?2026h\x1b[H" + "\r\n".join(out) + "\x1b[?2026l"


SHADE = (86, 92, 120)  # sunglasses lens colour
COOL = ["shades on.", "too bright!", "deal with it", "my retinas", "*puts on shades*", "who turned that on"]


def shades(w, lines):
    """While a pulsar is out, every cat wears sunglasses: swap whatever face it has for lenses."""
    if not w.shades:
        return lines
    out = []
    for ln in lines:
        for face in ("o.o", "O.O", "-.-", "^.^", "@.@", ">.<"):
            ln = ln.replace(face, "■-■")
        for face in ("^w^", "^o^", ">w<"):
            ln = ln.replace(face, "■w■")
        out.append(ln)
    return out


def art(s):
    return s.strip("\n").split("\n")


# ───────────────────────────────── the art ─────────────────────────────────

ASTRO = art(r"""
   .-'''''-.
  /¬¬/\_/\¬¬\
 |¬¬(¬o.o¬)¬¬|
  \¬¬>¬^¬<¬¬¬/
   '-.___.-'
   /|[=#=]|\
  (_|¬¬:¬¬|_)~~
    |__|__|
    (_/ \_)
""")

ROCKET = art(r"""
   ▄▄
   ███▄
   ▀████▄        /\_/\
 ▄▄▄▄██████▄▄▄▄▄( ^w^ )▄▄▄
▐███▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓██████▒▒█▄
▐██████████████████████████████
 ▀▀████████████████████████▀▀▀
     ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀
""")

UFO = art(r"""
        ▄▄▄▄▄▄▄▄▄
      ▄▀¬¬/\_/\¬¬▀▄
     █¬¬¬(¬o.o¬)¬¬¬█
 ▄▄▄▄█▄▄▄▄▄▄▄▄▄▄▄▄▄█▄▄▄▄
▀██▄●▄▄●▄▄●▄▄●▄▄●▄▄●▄██▀
   ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀
""")

RUNNER_TOP = art(r"""
            .-'''''-.
           /¬¬/\_/\¬¬\
  ~.      |¬¬(¬o.o¬)¬¬|
    \======\¬¬>¬^¬<¬¬¬/
     ||  || '-.___.-'
""")
RUNNER_LEGS = [["    _/|  _/|", "   [▄▄] [▄▄]"], ["     |\\_  |\\_", "     [▄▄] [▄▄]"]]  # two strides, with jet boots

CONSTELLATION = art(r"""
   *           *
  · ·         · ·
 ·   * · · · *   ·
 ·               ·
*    ✦       ✦    *
 ·       v       ·
  ·    ' - '    ·
   * · · · · · *
""")

# A 3x5 pixel font for the tow banners (M, N and W are wider). Each pixel becomes two columns by
# one row of cloth, so letters come out roughly square.
FONT = {
    "A": ("###", "#.#", "###", "#.#", "#.#"), "B": ("##.", "#.#", "##.", "#.#", "##."),
    "C": ("###", "#..", "#..", "#..", "###"), "D": ("##.", "#.#", "#.#", "#.#", "##."),
    "E": ("###", "#..", "###", "#..", "###"), "F": ("###", "#..", "##.", "#..", "#.."),
    "G": ("###", "#..", "#.#", "#.#", "###"), "H": ("#.#", "#.#", "###", "#.#", "#.#"),
    "I": ("###", ".#.", ".#.", ".#.", "###"), "J": ("..#", "..#", "..#", "#.#", "###"),
    "K": ("#.#", "#.#", "##.", "#.#", "#.#"), "L": ("#..", "#..", "#..", "#..", "###"),
    "M": ("#...#", "##.##", "#.#.#", "#...#", "#...#"), "N": ("#..#", "##.#", "#.##", "#..#", "#..#"),
    "O": ("###", "#.#", "#.#", "#.#", "###"), "P": ("###", "#.#", "###", "#..", "#.."),
    "Q": ("###", "#.#", "#.#", "###", "..#"), "R": ("###", "#.#", "##.", "#.#", "#.#"),
    "S": ("###", "#..", "###", "..#", "###"), "T": ("###", ".#.", ".#.", ".#.", ".#."),
    "U": ("#.#", "#.#", "#.#", "#.#", "###"), "V": ("#.#", "#.#", "#.#", "#.#", ".#."),
    "W": ("#...#", "#...#", "#.#.#", "#.#.#", ".#.#."), "X": ("#.#", "#.#", ".#.", "#.#", "#.#"),
    "Y": ("#.#", "#.#", ".#.", ".#.", ".#."), "Z": ("###", "..#", ".#.", "#..", "###"),
    "0": ("###", "#.#", "#.#", "#.#", "###"), "1": (".#.", "##.", ".#.", ".#.", "###"),
    "2": ("###", "..#", "###", "#..", "###"), "3": ("###", "..#", "###", "..#", "###"),
    "4": ("#.#", "#.#", "###", "..#", "..#"), "5": ("###", "#..", "###", "..#", "###"),
    "6": ("###", "#..", "###", "#.#", "###"), "7": ("###", "..#", "..#", "..#", "..#"),
    "8": ("###", "#.#", "###", "#.#", "###"), "9": ("###", "#.#", "###", "..#", "###"),
    "'": ("#", "#", ".", ".", "."), "!": ("#", "#", "#", ".", "#"), ".": (".", ".", ".", ".", "#"),
    "?": ("###", "..#", ".##", "...", ".#."), "-": ("...", "...", "###", "...", "..."),
    " ": ("..", "..", "..", "..", ".."),
}
WORDS = ["SPACE CATS", "MEOW", "PURR", "ASTRO CATS", "MEOW MEOW", "FEED ME", "EAT AT JOE'S", "404 MOUSE NOT FOUND",
         "NO DOGS", "SEND TUNA", "CATS RULE", "I FITS I SITS", "WET FOOD NOW", "HAIL CATNIP", "OPEN THE DOOR",
         "LAND? NEVER", "PET ME", "9 LIVES LEFT", "NAP ZONE"]
MEOWS = ["meow", "mrrp?", "purrrr", "ground control to major tom-cat", "*zero-g zoomies*", "no gravity, no rules",
         "is that a laser?", "feed me, houston", "one small step for cat", "prrrt", "i knocked the moon off the table",
         "mew.", "*slow blink*"]


def banner_cells(word):
    """Return ([(x, y)] of filled banner cells, total width) for a word."""
    rows = [""] * 5
    for chx in word:
        g = FONT.get(chx, FONT["?"])
        for r in range(5):
            rows[r] += g[r] + "."
    cells = [(i * 2 + dx, r) for r, ln in enumerate(rows) for i, c in enumerate(ln) if c == "#" for dx in (0, 1)]
    return cells, len(rows[0]) * 2


# ──────────────────────────────── entities ────────────────────────────────

class Ent:
    z = 5
    dead = False

    def update(self, w, dt):
        pass

    def draw(self, w, s):
        pass


class Particle(Ent):
    z = 6

    def __init__(self, x, y, vx, vy, life, chars, cols):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.life, self.age, self.chars, self.cols = life, 0.0, chars, cols

    def update(self, w, dt):
        self.age += dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.dead = self.age >= self.life

    def draw(self, w, s):
        f = self.age / self.life
        s.put(self.x, self.y, self.chars[min(int(f * len(self.chars)), len(self.chars) - 1)], ramp(self.cols, f))


def lit(c, col, f):
    """Colour c with light col added at strength f. Works on fg (3) and fg+bg (6) colours."""
    r, g, b = col[0] * f, col[1] * f, col[2] * f
    if len(c) == 3:
        return (min(255, int(c[0] + r)) & ~7, min(255, int(c[1] + g)) & ~7, min(255, int(c[2] + b)) & ~7)
    return (min(255, int(c[0] + r)) & ~7, min(255, int(c[1] + g)) & ~7, min(255, int(c[2] + b)) & ~7,
            min(255, int(c[3] + r)) & ~7, min(255, int(c[4] + g)) & ~7, min(255, int(c[5] + b)) & ~7)


class Flash(Ent):
    """A burst of light that fades out (impacts, a black hole collapsing)."""

    def __init__(self, x, y, r, col, life, power=1.0):
        self.x, self.y, self.r, self.col, self.life, self.power, self.age = x, y, r, col, life, power, 0.0

    def update(self, w, dt):
        self.age += dt
        self.dead = self.age >= self.life

    def draw(self, w, s):
        w.lights.append((self.x, self.y, self.r, self.col, self.power * (1 - self.age / self.life)))


class Bubble(Ent):
    z = 9

    def __init__(self, owner, msg, col, dx=13, dy=-1):
        self.o, self.msg, self.col, self.age, self.dx, self.dy = owner, msg, col, 0.0, dx, dy

    def update(self, w, dt):
        self.age += dt
        self.dead = self.age > 4 or self.o.dead

    def draw(self, w, s):
        shown = self.msg[:int(self.age * 30)]
        x = min(max(1, self.o.x + self.dx), max(1, s.w - len(self.msg) - 5))
        y = self.o.y + self.dy
        s.text(x, y, "( " + shown + " )", dim(self.col, min(1, (4 - self.age) * 2)))
        s.put(x - 1, y + 1, "'", self.col)


class Comet(Ent):
    """A shooting star. Black holes bend its path and can swallow it; cats can bat it away."""
    z = 3

    def __init__(self, w, x=None, y=-1.0, vx=None, vy=None, col=None):
        self.x = U(w.W * 0.2, w.W * 1.3) if x is None else x
        self.y = y
        self.vx = -U(40, 75) if vx is None else vx
        self.vy = U(12, 26) if vy is None else vy
        self.col = col or random.choice(w.pal)
        self.hist = []
        self.batted = False  # each one gets a single chance of being swatted

    def update(self, w, dt):
        self.hist.append((self.x, self.y))
        del self.hist[:-16]
        for h in w.holes:
            dx, dy = h.x - self.x, (h.y - self.y) * 2
            d = math.hypot(dx, dy) or 1.0
            g = h.strength()
            if g > 0 and d < h.reach:
                pull = g * (1 - d / h.reach) * 220
                self.vx += dx / d * pull * dt
                self.vy += dy / d * pull * dt * 0.5
                if d < h.R0 * 1.3 and g > 0.5:
                    h.swallow(w, self)
                    return
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.dead = self.x < -30 or self.x > w.W + 30 or self.y > w.H + 8 or self.y < -12

    def draw(self, w, s):
        n = len(self.hist)
        for i, (x, y) in enumerate(self.hist):
            f = (i + 1) / n
            s.put(x, y, ".·:*"[int(f * 3.99)], dim(self.col, f * f))
        s.put(self.x, self.y, "✦", WHITE)
        w.lights.append((self.x, self.y, 5, mix(self.col, WHITE, 0.4), 0.55))


class Planet(Ent):
    """A shaded, slowly turning planet drifting past. With moon=True it is a small moon that a nearby
    cat will wander over to and push off its path, the way cats do with a glass on a table."""
    z = 2
    RAMP = " .:-=+*#%@"

    def __init__(self, w, moon=False):
        self.moon = moon
        if moon:
            self.r = 3 if w.H >= 28 else 2
            self.y = U(self.r + 9, max(self.r + 10, w.H - self.r - 3))
            self.rings = False
            self.speed = U(4, 6)
        else:
            self.r = random.randint(5, max(5, min(10, w.H // 5)))
            self.y = U(self.r + 2, max(self.r + 3, w.H - self.r - 3))
            self.rings = random.random() < 0.65
            self.speed = U(3, 5)
        self.x = w.W + self.r * 4 + 4.0
        self.y0 = self.y
        self.c1, self.c2, self.rc = random.sample(w.pal, 3)
        self.rot = U(0, TAU)
        self.vy, self.taps, self.fallen, self.pusher = 0.0, 0, False, None

    def center(self):
        return self.x, self.y

    def nudge(self, w):
        """One tap from a paw: it shifts a little... until it goes."""
        self.taps += 1
        self.y += 1.0
        for _ in range(6):
            w.add(Particle(self.x + U(-3, 3), self.y - self.r, U(-4, 4), -U(1, 4), U(0.4, 0.9), "*·.", [WHITE, self.c1, (0, 0, 0)]))
        if self.taps >= 4:
            self.fallen, self.vy = True, 3.0

    def update(self, w, dt):
        self.x -= self.speed * dt * (1 + w.warp * 6)
        self.rot += dt * 0.5
        if self.fallen:
            self.vy += 16 * dt
        self.y += self.vy * dt
        if self.moon and self.pusher is None and not self.fallen and 24 < self.x < w.W - 12:
            near = [c for c in w.cats if c.state == "float" and c.buddy is None and abs(c.x + 7 - self.x) < 55]
            if near:
                self.pusher = min(near, key=lambda c: abs(c.x + 7 - self.x))
                self.pusher.start_push(w, self)
        self.dead = self.x < -self.r * 5 or self.y > w.H + self.r + 3

    def ring(self, s, front):
        r, cx, cy = self.r, self.x, self.y
        for rr, chx in ((1.45, "="), (1.65, "-"), (1.85, "=")):
            n = int(rr * r * 14)
            for i in range(n):
                a = TAU * i / n
                sa, ca = math.sin(a), math.cos(a)
                if (sa > 0) != front:
                    continue
                dx = ca * rr * r * 2
                dy = sa * rr * r * 0.24 + ca * rr * r * 0.13
                if not front and (dx / (2 * r)) ** 2 + (dy / r) ** 2 < 1:
                    continue
                s.put(round(cx + dx), round(cy + dy), chx, dim(self.rc, 0.95 if front else 0.45))

    def draw(self, w, s):
        r, cx, cy = self.r, int(self.x), int(self.y)
        if self.rings:
            self.ring(s, False)
        for dy in range(-r, r + 1):
            ny = dy / r
            for dx in range(-2 * r, 2 * r + 1):
                nx = dx / (2.0 * r)
                d2 = nx * nx + ny * ny
                if d2 > 1:
                    continue
                nz = math.sqrt(1 - d2)
                light = max(0.0, -0.58 * nx - 0.47 * ny + 0.67 * nz)
                lon = math.atan2(nx, nz) + self.rot
                band = math.sin(ny * 7 + 0.9 * math.sin(lon * 2)) * 0.5 + 0.5
                val = light * (0.7 + 0.3 * math.sin(lon * 5 + ny * 4) * band + 0.0) + 0.02
                chx = self.RAMP[min(9, int(val * 10))]
                s.put(cx + dx, cy + dy, chx, dim(mix(self.c1, self.c2, band), 0.3 + 0.7 * light))
        if self.rings:
            self.ring(s, True)


class Ring(Ent):
    """A shockwave from a pulsar pulse: an expanding ring that brightens whatever it sweeps over."""
    z = 20  # drawn last, so it can light up things already on screen

    def __init__(self, x, y, col, speed, life):
        self.x, self.y, self.col, self.speed, self.life, self.age = x, y, col, speed, life, 0.0

    def update(self, w, dt):
        self.age += dt
        self.dead = self.age >= self.life

    def draw(self, w, s):
        fade = (1 - self.age / self.life) ** 1.5
        ch, co, W, H = s.ch, s.co, s.w, s.h
        for k, r in enumerate((self.age * self.speed, self.age * self.speed - 2.5)):
            if r < 2:
                continue
            n = int(TAU * r * 0.8)
            f = fade * (1.0 if k == 0 else 0.5)
            for i in range(n):
                a = TAU * i / n
                x, y = int(self.x + math.cos(a) * r), int(self.y + math.sin(a) * r * 0.5)
                if 0 <= x < W and 0 <= y < H:
                    if ch[y][x] == " ":
                        ch[y][x], co[y][x] = ("∙" if k == 0 else "·"), dim(self.col, f * 0.8)
                    else:
                        co[y][x] = lit(co[y][x], self.col, f * 0.9)


class Pulsar(Ent):
    """A spinning neutron star: wide beam cones sweeping the sky, a spiked core, and a shockwave ring on every pulse."""
    z = 1
    COL = (150, 190, 255)
    RATE = 1.3  # pulses per second

    def __init__(self, w):
        self.x = U(w.W * 0.2, w.W * 0.8)
        self.y = U(w.H * 0.25, w.H * 0.75)
        self.age, self.life = 0.0, U(20, 26)
        self.spin = random.choice((-1, 1)) * U(0.9, 1.3)
        self.reach = max(40, min(120, int(w.W * 0.45)))
        self.beat = -1

    def strength(self):
        return max(0.0, min(1.0, self.age / 2, (self.life - self.age) / 2))

    def pulse(self):
        return max(0.0, math.sin(self.age * TAU * self.RATE)) ** 6

    def update(self, w, dt):
        self.age += dt
        self.x -= 1.5 * dt
        beat = int(self.age * self.RATE - 0.25)  # one shockwave per pulse peak
        if beat != self.beat and self.strength() > 0.3:
            self.beat = beat
            w.add(Ring(self.x, self.y, self.COL, U(46, 58), 1.7))
        self.dead = self.age >= self.life

    def draw(self, w, s):
        g, pulse = self.strength(), self.pulse()
        cx, cy, n = self.x, self.y, self.reach
        glow = 0.6 + 0.4 * pulse
        # Beam cones: walk out along each beam, filling a wedge that widens with distance.
        for k in (0, 1):
            a = self.age * self.spin + k * math.pi
            ca, sa = math.cos(a), math.sin(a)
            for r in range(4, n, 1):
                half = r * 0.13 + 0.6
                fall = (1 - r / n) ** 1.3 * g * glow
                if fall < 0.05:
                    break
                px, py = cx + ca * r, cy + sa * r * 0.5
                m = int(half) + 1
                for j in range(-m, m + 1):
                    f = fall * (1 - abs(j) / (half + 1)) ** 1.5
                    if f > 0.06:  # step sideways across the beam (perpendicular to its axis)
                        s.put(px - sa * j, py + ca * j * 0.5, ".:-=+*#@"[min(7, int(f * 9))],
                              dim(mix(self.COL, WHITE, f), 0.25 + 0.75 * f))
        # Core: a corona plus four spikes that stretch with each pulse.
        rad = (2.2 + 1.6 * pulse) * g
        for dy in range(-4, 5):
            for dx in range(-9, 10):
                d = math.hypot(dx / 2, dy)
                if d < rad + 0.4:
                    s.put(cx + dx, cy + dy, "@@#*+=:."[min(7, int(d / (rad + 0.4) * 8))], dim(mix(WHITE, self.COL, d / (rad + 0.4)), g * glow))
        for i in range(1, int((6 + 16 * pulse) * g)):
            f = (1 - i / (6 + 16 * pulse)) * g
            for sx in (-1, 1):
                s.put(cx + sx * (i + 2), cy, "=" if f > 0.5 else "-", dim(WHITE, f))
                if i % 2 == 0 and i < 14:
                    s.put(cx, cy + sx * (1 + i // 2), "|", dim(WHITE, f))
        w.lights.append((cx, cy, 40, self.COL, g * (0.12 + 1.0 * pulse)))


class Constellation(Ent):
    z = 1

    def __init__(self, w):
        self.x = U(w.W * 0.3, max(w.W * 0.3 + 1, w.W - 22))
        self.y = U(2, max(3, w.H - 13))
        self.age = 0.0
        self.col = random.choice(w.pal)
        self.cells = [(i, j, c) for j, line in enumerate(CONSTELLATION) for i, c in enumerate(line) if c != " "]
        self.cells.sort(key=lambda p: math.atan2(p[1] - 3.5, (p[0] - 9) * 0.5))

    def update(self, w, dt):
        self.age += dt
        self.x -= 1.5 * dt
        self.dead = self.age > 18

    def draw(self, w, s):
        fade = min(1.0, (18 - self.age) / 3)
        shown = int(len(self.cells) * min(1.0, self.age / 4))
        for k, (i, j, c) in enumerate(self.cells[:shown]):
            if c in "*✦":
                b = 0.7 + 0.3 * math.sin(w.t * 5 + k)
                s.put(self.x + i, self.y + j, c, dim(WHITE, b * fade))
            else:
                s.put(self.x + i, self.y + j, c, dim(self.col, 0.6 * fade))
        if self.age > 4:
            label = "· felis major ·"
            s.text(self.x + 2, self.y + 9, label[:int((self.age - 4) * 12)], dim(self.col, 0.8 * fade))


def line(s, x0, y0, x1, y1, col):
    """Plot a rope between two points with slope-appropriate ASCII."""
    dx, dy = x1 - x0, y1 - y0
    n = int(max(abs(dx), abs(dy))) or 1
    ch = "-" if abs(dy) * 2 < abs(dx) else ("\\" if (dx > 0) == (dy > 0) else "/")
    for k in range(n + 1):
        s.put(round(x0 + dx * k / n), round(y0 + dy * k / n), ch, col)


class TowUfo(Ent):
    """A saucer towing a big block-letter title as a waving cloth banner. Tow ships never beam anything up."""
    z = 7
    PAD = 2
    SHIP_W = LEN = len(UFO[3])
    MID = 3

    def __init__(self, w, word=None):
        fits = [x for x in WORDS if banner_cells(x)[1] < w.W * 0.75] or ["MEOW"]
        self.word = word or random.choice(fits)
        self.cells, width = banner_cells(self.word)
        self.bw = width - 2 + self.PAD * 2  # banner_cells leaves a trailing gap
        self.bh = 7
        self.tug = 0.0  # rows the free end is being dragged toward a black hole
        self.ink = [set() for _ in range(self.bw)]  # per banner column: half-rows covered by lettering
        for cx, cy in self.cells:
            self.ink[cx + self.PAD].update(((cy + 1) * 2, (cy + 1) * 2 + 1))
        self.dir = random.choice((-1, 1))
        self.speed = U(15, 20)
        self.gap = 9
        self.y0 = near_a_cat(w, 0.5, U(1, max(2, w.H * 0.45 - 4)), 8)
        self.y = self.y0
        self.x = -self.SHIP_W - 1.0 if self.dir > 0 else float(w.W)
        self.seen = []
        self.col = random.choice(w.pal)
        self.cloth = random.choice(w.pal)
        self.age = 0.0

    def wave(self, c, t):
        """(vertical offset in rows, brightness) of banner column c.

        Pinned at the tow point and swinging wider toward the free end, like a real flag: one big
        travelling wave plus a faster small ripple. Offsets are fractional rows; draw() renders them
        at half-row resolution.
        """
        d = abs((self.bw - 1 if self.dir > 0 else 0) - c)
        amp = min(3.4, d * 0.075)  # in half-rows
        ph = d * 0.15 - t * 4.2
        off = amp * math.sin(ph) + amp * 0.35 * math.sin(d * 0.37 - t * 7.1)
        return off / 2 + self.tug * (d / self.bw) ** 2, 0.72 + 0.28 * math.cos(ph)

    def banner_left(self):
        if self.dir > 0:
            return self.x - self.gap - self.bw
        return self.x + self.SHIP_W + self.gap

    def update(self, w, dt):
        self.age += dt
        self.x += self.dir * self.speed * dt
        self.y = self.y0 + math.sin(self.age * 1.4) * 0.8
        bl = self.banner_left()
        self.tug = 0.0
        tail = bl if self.dir > 0 else bl + self.bw  # the free end
        for h in w.holes:
            dy = h.y - (self.y + 4)
            dist = math.hypot(h.x - tail, dy * 2)
            if dist < h.reach:
                self.tug += h.strength() * (1 - dist / h.reach) * max(-6.0, min(6.0, dy))
        self.dead = bl > w.W + 2 if self.dir > 0 else bl + self.bw < -2

    def draw(self, w, s):
        t, pal, n = w.t, w.pal, len(w.pal)
        bl, by = self.banner_left(), self.y + 0.5
        front = self.bw - 1 if self.dir > 0 else 0  # banner column nearest the ship

        # tow lines from the saucer's rear rim to the banner's front corners
        ax = self.x - 0.5 if self.dir > 0 else self.x + self.SHIP_W - 0.5
        ay = self.y + 4
        fx = bl + front
        rope = dim(WHITE, 0.55)
        line(s, ax, ay, fx + self.dir, by, rope)
        line(s, ax, ay, fx + self.dir, by + self.bh - 1, rope)

        # Cloth and lettering, drawn in half-rows: each terminal cell holds two stacked "pixels",
        # shown with half-block characters (foreground = top pixel, background = bottom pixel).
        base, height = round(by * 2), self.bh * 2
        for c in range(self.bw):
            off, shade = self.wave(c, t)
            h0 = base + round(off * 2)
            f = c * 0.035 - t * 0.6
            i = int(math.floor(f))
            cols = (None, dim(self.cloth, 0.40 * shade), dim(mix(pal[i % n], pal[(i + 1) % n], f - i), shade))
            ink = self.ink[c]
            for cell in range(h0 // 2, (h0 + height - 1) // 2 + 1):
                p = cell * 2 - h0
                a = 0 if p < 0 or p >= height else 2 if p in ink else 1
                p += 1
                b = 0 if p < 0 or p >= height else 2 if p in ink else 1
                if a == b:
                    if a:
                        s.put(bl + c, cell, "█", cols[a])
                elif not b:
                    s.put(bl + c, cell, "▀", cols[a])
                elif not a:
                    s.put(bl + c, cell, "▄", cols[b])
                else:
                    s.put(bl + c, cell, "▀", cols[a] + cols[b])

        lines = list(UFO)
        if (self.age % 3.3) < 0.2:
            lines[2] = lines[2].replace("o.o", "-.-")
        over = {"/": WHITE, "\\": WHITE, "_": WHITE, "(": WHITE, ")": WHITE, ".": WHITE, "-": WHITE,
                "o": self.cloth, "●": lambda i, j, tt: pal[(self.dir * -i // 3 + int(tt * 8)) % n]}
        s.sprite(shades(w, lines), self.x, self.y, self.col, over, t)


SMALL_CAT = art(r"""
 /\_/\
(¬o.o¬)
 >¬^¬<
""")
FLIP = str.maketrans("()<>[]^'._", ")(><][v.'‾")
OUCH = ["MROW!", "hey!!", "rude.", "*bonk*", "watch it!", "my helmet!"]
WHEE = ["wheeee", "cowabunga", "surf's up", "free ride!", "faster!!"]
VOID = ["i saw things", "...what.", "spaghettified!", "0/10 would not again", "it was dark in there"]
BAP = ["*bap*", "*swat*", "mine.", "got it!", "*boop*"]
BUMP = ["oof", "excuse you", "watch the tail", "hi.", "personal space!"]
FRIEND = ["friend.", "*holds paw*", "we float together", "ok you can stay"]
SLEEPY = ["zzz", "*curls up*", "nap time", "five minutes..."]
YAWN = ["*yawn*", "mrrrh?", "what did i miss", "*stretch*"]
YARN = ["YARN!!", "must. have.", "is that... yarn", "*pupils dilate*"]
MOUSE = ["MOUSE!", "get it get it", "*chatters*", "dinner!!"]
BOXY = ["box!!", "if i fits...", "must sit", "is that a BOX"]
INBOX = ["i fits. i sits.", "mine now", "perfect.", "do not disturb"]
UNBOX = ["ok, bored now", "*hops out*", "keep the box", "needs more box"]
BEAMED = ["put me down!", "not the probe", "hey! HEY", "i was busy!", "unhand me"]
DROPPED = ["never speak of this", "...rude.", "where am i", "0 stars"]
PUSHED = ["oops.", "it was like that", "gravity did it", "...what?", "i regret nothing"]
CUKE = ["!!!!", "CUCUMBER!", "NOPE", "AAAAAA", "SNAKE!!"]


def flipped(lines):
    """The sprite rotated 180 degrees, for tumbling."""
    wd = max(len(ln) for ln in lines)
    return [ln.ljust(wd)[::-1].translate(FLIP) for ln in reversed(lines)]


def head_rows(eyes, look):
    """Ears, face and mouth rows of the astronaut sprite, with the head turned inside the helmet (look = -1, 0, 1)."""
    pl, pr = "¬" * (2 + look), "¬" * (2 - look)
    return ["  /" + pl + "/\\_/\\" + pr + "\\",
            " |" + pl + "(¬" + eyes + "¬)" + pr + "|",
            "  \\" + pl + ">¬^¬<" + pr + "¬/"]


class AstroCat(Ent):
    """A floating astronaut cat with simple physics and a lot of opinions.

    States:
      float   drifting freely; stays wherever it ends up
      nap     asleep after being left alone for a while
      tumble  knocked flying, bouncing off the edges
      surf    riding a shuttle's exhaust on a board      ride    sitting on a towed banner
      sucked  spiralling into a black hole               gone    inside one until it spits the cat out
      beamed  held in a saucer's tractor beam            boxed   sitting in a cardboard box (the box draws it)
      chase   after the space mouse                      push    nudging a moon off its path
    While floating it can also hold paws with a buddy, stare at or go after a target (yarn, a box),
    and swat at things that pass.
    """
    z = 8  # in front of banners and saucers

    def __init__(self, w, k):
        self.p1, self.p2 = U(0, TAU), U(0, TAU)
        self.f1, self.f2 = U(0.09, 0.14), U(0.13, 0.2)
        self.col = mix(WHITE, w.pal[k % len(w.pal)], 0.35)
        self.tail = w.pal[(k + 2) % len(w.pal)]
        self.eye = w.pal[(k + 3) % len(w.pal)]
        self.talk = U(4, 9)
        self.vx = self.vy = 0.0
        self.state, self.timer = "float", 0.0
        self.ship = self.hole = self.ufo = self.box = None
        self.target, self.want = None, False  # something it is watching / actively going after
        self.buddy, self.lead, self.buddy_t = None, False, 0.0
        self.ang = self.rad = 0.0
        self.calm, self.nap_at = 0.0, U(10, 20)  # seconds left alone / when that becomes a nap
        self.bump_cd = self.swat = self.wide = self.poke = 0.0
        self.look = 0
        self.x, self.y = U(2, max(3, w.W - 16)), U(1, max(2, w.H - 10))

    def center(self):
        return self.x + 7, self.y + 4.5

    def free(self):
        return self.state in ("float", "nap")

    def say(self, w, msgs):
        self.talk = U(9, 18)
        w.add(Bubble(self, random.choice(msgs), self.tail))

    def disturb(self):
        """Something happened: no nap coming, let go of a friend, forget what it was looking at."""
        self.calm = 0.0
        self.target, self.want = None, False
        b, self.buddy = self.buddy, None
        if b is not None and b.buddy is self:
            b.buddy = None

    def knock(self, w, vx, vy, secs, msgs):
        """Send the cat tumbling."""
        self.disturb()
        self.state, self.timer, self.vx, self.vy = "tumble", secs, vx, vy
        self.ship = self.hole = self.ufo = None
        self.say(w, msgs)
        w.add(Flash(self.x + 7, self.y + 4, 9, WHITE, 0.45, 0.8))
        for _ in range(14):
            w.add(Particle(self.x + 7, self.y + 4, U(-18, 18), U(-8, 8), U(0.4, 1.0), "✦*+·.", [WHITE, self.tail, (0, 0, 0)]))

    def spit(self, w, x, y):
        """Thrown back out of a collapsing black hole."""
        a = U(0, TAU)
        self.x, self.y = x - 7, y - 4.5
        self.knock(w, math.cos(a) * U(25, 40), math.sin(a) * U(8, 14), 5.0, VOID)

    def release(self, vx):
        self.state, self.ship, self.vx, self.vy = "float", None, vx, 0.0

    def notice(self, w, thing, want, msgs):
        """Start watching something; with want, go after it."""
        if self.state == "float" and self.target is None and self.buddy is None:
            self.target, self.want, self.wide, self.calm = thing, want, 1.5, 0.0
            if want:
                self.say(w, msgs)

    def start_chase(self, w, prey):
        self.disturb()
        self.state, self.target = "chase", prey
        self.say(w, MOUSE)

    def start_push(self, w, moon):
        self.disturb()
        self.state, self.target, self.timer = "push", moon, 1.0

    def meet_ships(self, w):
        """React once to each ship as its nose passes: get hit, hitch a ride, or be left alone."""
        cx, cy = self.x + 7, self.y + 4.5
        for ship in w.ships:
            if self in ship.seen:
                continue
            lead = ship.x + ship.LEN if ship.dir > 0 else ship.x
            if (lead - cx) * ship.dir < 0:
                continue  # not here yet
            ship.seen.append(self)
            if abs(lead - cx) > 8:
                continue  # it spawned already past us
            dy = cy - (ship.y + ship.MID)
            if abs(dy) <= 5:
                self.knock(w, ship.dir * ship.speed * 0.9, (1 if dy >= 0 else -1) * U(8, 14), U(3.5, 5.5), OUCH)
            elif self.state == "float" and abs(dy) <= 15 and random.random() < 0.65:
                self.disturb()
                self.state, self.ship = ("surf" if isinstance(ship, RocketCat) else "ride"), ship
                self.say(w, WHEE)
            return

    def drift(self, w, dt, asleep):
        """Floating (or napping): wander, watch things, keep a buddy close, feel black holes, doze off."""
        t = w.t
        cx, cy = self.x + 7, self.y + 4.5
        ax = ay = 0.0
        self.look = 0
        if not asleep:
            # A lazy, ever-changing push. There is no "home" spot: wherever the cat ends up, it stays.
            ax = 2.2 * math.sin(self.f1 * 2.6 * t + self.p1) + 1.4 * math.sin(self.f2 * 1.1 * t + self.p2)
            ay = 0.9 * math.sin(self.f2 * 2.2 * t + self.p2) + 0.6 * math.sin(self.f1 * 1.3 * t + self.p1)
            tgt, b = self.target, self.buddy
            if tgt is not None:
                if tgt.dead or getattr(tgt, "away", False):
                    self.target, self.want = None, False
                else:
                    tx, ty = tgt.center()
                    dx, dy = tx - cx, (ty - cy) * 2
                    d = math.hypot(dx, dy) or 1.0
                    self.look = 1 if dx > 4 else -1 if dx < -4 else 0
                    if self.want:
                        ax += dx / d * 10
                        ay += dy / d * 5
            elif b is None:  # cats are a little sociable: lean toward the nearest other cat
                best, bd = None, 90.0
                for o in w.cats:
                    if o is not self and o.free():
                        dd = math.hypot(o.x - self.x, (o.y - self.y) * 2)
                        if 18 < dd < bd:
                            best, bd = o, dd
                if best is not None:
                    ax += (best.x - self.x) / bd * 0.8
                    ay += (best.y - self.y) * 2 / bd * 0.4
            if b is not None:
                self.buddy_t -= dt
                if b.state != "float" or b.buddy is not self or self.buddy_t <= 0:
                    self.buddy = None
                    if b.buddy is self:
                        b.buddy = None
                elif not self.lead:  # the follower keeps station beside the leader, paw in paw
                    ax += (b.x + 15 - self.x) * 4 - (self.vx - b.vx) * 3
                    ay += (b.y - self.y) * 4 - (self.vy - b.vy) * 3
                    if random.random() < dt * 1.2:
                        w.add(Particle(self.x - 1, self.y + 5, U(-1, 1), -U(2, 3), 1.4, "♥♥♥·", [(255, 120, 160), (255, 120, 160), (60, 20, 40)]))
        if self.x < 4:
            ax += (4 - self.x) * 1.5
        elif self.x > w.W - 18:
            ax -= (self.x - (w.W - 18)) * 1.5
        if self.y < 1:
            ay += (1 - self.y) * 1.5
        elif self.y > w.H - 10:
            ay -= (self.y - (w.H - 10)) * 1.5
        for h in w.holes:
            dx, dy = h.x - cx, (h.y - cy) * 2
            d = math.hypot(dx, dy) or 1.0
            inf = h.strength() * max(0.0, 1 - d / h.reach)
            if inf <= 0:
                continue
            ax += dx / d * (20 + 60 * inf)
            ay += dy / d * (20 + 60 * inf) * 0.5
            if d < h.grab and h.strength() > 0.6:
                self.disturb()
                self.state, self.hole = "sucked", h
                self.ang, self.rad = math.atan2(-dy, -dx), d
                h.caught.append(self)
                self.say(w, ["uh oh", "nope nope nope", "not again", "tell my human i—"])
                return
        drag = 1.6 if asleep else 0.4
        self.vx += (ax - self.vx * drag) * dt
        self.vy += (ay - self.vy * drag) * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        if asleep:
            self.timer -= dt
            if random.random() < dt * 1.4:
                w.add(Particle(self.x + 13, self.y + 1, U(1, 3), -U(2, 3.5), 1.8, "zzZZ·", [self.tail, self.tail, (40, 40, 60)]))
            if self.timer <= 0:
                self.state, self.calm, self.nap_at = "float", 0.0, U(14, 28)
                self.say(w, YAWN)
        else:
            self.calm += dt
            if self.calm > self.nap_at and self.target is None and self.buddy is None:
                self.state, self.timer = "nap", U(18, 30)
                self.say(w, SLEEPY)

    def update(self, w, dt):
        st = self.state
        if st == "gone":
            return
        if st == "boxed":
            if self.box is None or self.box.dead:
                self.state, self.box = "float", None
            return
        self.bump_cd -= dt
        self.swat -= dt
        self.wide -= dt
        self.poke -= dt
        if st in ("float", "nap"):
            self.drift(w, dt, st == "nap")
            if self.state in ("float", "nap"):
                self.meet_ships(w)
        elif st == "tumble":
            self.timer -= dt
            self.x += self.vx * dt
            self.y += self.vy * dt
            drag = 1 - 0.35 * dt
            self.vx *= drag
            self.vy *= drag
            if self.x < 0 or self.x > w.W - 14:
                self.vx = abs(self.vx) if self.x < 0 else -abs(self.vx)
                self.x = min(max(self.x, 0), w.W - 14)
            if self.y < 0 or self.y > w.H - 9:
                self.vy = abs(self.vy) if self.y < 0 else -abs(self.vy)
                self.y = min(max(self.y, 0), w.H - 9)
            if self.timer <= 0:
                self.state = "float"
        elif st in ("surf", "ride"):
            ship = self.ship
            if st == "surf":
                tx, ty = ship.x - 19, ship.y - 4 + math.sin(w.t * 3) * 1.2
                done = ship.dead or ship.x > w.W - 3 or ship.mode != "fly"
                if random.random() < dt * 25:  # spray off the board
                    w.add(Particle(self.x, self.y + 9, -U(6, 20), U(-2, 2), U(0.3, 0.8), "*·.", [WHITE, self.tail, (0, 0, 0)]))
            else:
                c = ship.bw / 2
                tx = ship.banner_left() + c - 7
                ty = ship.y + 0.5 + ship.wave(c, w.t)[0] - 9
                done = ship.dead or tx < 3 or tx > w.W - 17
            f = min(1.0, dt * 4)
            self.x += (tx - self.x) * f
            self.y += (ty - self.y) * f
            if done:
                self.release(ship.dir * ship.speed * 0.4)
        elif st == "sucked":
            h = self.hole
            self.ang += dt * (2.5 + 30 / (self.rad + 3))
            self.rad -= dt * (3 + 40 / (self.rad + 4))
            self.x = h.x + math.cos(self.ang) * self.rad - 7
            self.y = h.y + math.sin(self.ang) * self.rad * 0.5 - 4.5
            if self.rad <= 0.8:
                self.state = "gone"
            return
        elif st == "beamed":  # the saucer moves us; just notice if it lets go without saying
            u = self.ufo
            if u is None or u.dead or u.cargo is not self:
                self.state, self.ufo = "float", None
        elif st == "chase":
            m = self.target
            if m is None or m.dead:
                self.state, self.target = "float", None
            else:
                tx, ty = m.center()
                dx, dy = tx - (self.x + 7), (ty - (self.y + 4.5)) * 2
                d = math.hypot(dx, dy) or 1.0
                f = min(1.0, dt * 3)
                self.vx += (dx / d * 26 - self.vx) * f  # just slower than the mouse, so it never quite gets there
                self.vy += (dy / d * 13 - self.vy) * f
                self.x = min(max(self.x + self.vx * dt, -2), w.W - 12)
                self.y = min(max(self.y + self.vy * dt, 0), max(0, w.H - 9))
                self.look = 1 if dx > 0 else -1
        elif st == "push":
            m = self.target
            if m is None or m.dead or m.fallen:
                self.state, self.target, self.calm = "float", None, 0.0
                self.say(w, PUSHED)
            else:  # sit at the moon's upper right with a paw on it, and tap. and tap.
                tx, ty = m.x + 1.4 * m.r - 2, m.y0 - 0.7 * m.r - 6
                f = min(1.0, dt * 2.2)
                self.x += (tx - self.x) * f
                self.y += (ty - self.y) * f
                self.vx = self.vy = 0.0
                self.look = -1
                if abs(tx - self.x) < 4 and abs(ty - self.y) < 1.2:
                    self.timer -= dt
                    if self.timer <= 0:
                        self.timer, self.poke = 1.1, 0.3
                        m.nudge(w)
        self.talk -= dt
        if self.talk < 0 and self.state == "float" and self.target is None:
            self.say(w, MEOWS)
        if random.random() < dt * 4:
            w.add(Particle(self.x + U(0, 14), self.y + U(0, 9), U(-2, 2), U(-2, 2), U(0.5, 1.2), "✦+·.", [WHITE, self.tail, (0, 0, 0)]))

    def draw(self, w, s):
        st = self.state
        if st in ("gone", "boxed"):
            return
        t = w.t + self.p1
        over = {"o": self.eye, "O": self.eye, "@": self.eye, "~": self.tail, "^": self.tail, "v": self.tail,
                "=": dim(self.tail, 0.8), "#": (255, 60, 60) if int(t * 2) % 2 else (90, 20, 20),
                ".": self.col, "'": dim(self.col, 0.8)}
        if st == "sucked" and self.rad <= self.hole.grab * 0.6:  # shrinking as it falls in
            cx, cy = self.x + 7, self.y + 4.5
            if self.rad > self.hole.grab * 0.3:
                s.sprite(shades(w, SMALL_CAT), cx - 3, cy - 1, self.col, over)
            else:
                s.text(cx - 2, cy, "=^.^=", self.col)
            return
        if st in ("tumble", "sucked"):
            eyes = "@.@"
        elif st in ("surf", "ride") or self.buddy is not None:
            eyes = "^.^"
        elif st == "nap":
            eyes = "-.-"
        elif st in ("beamed", "chase") or self.wide > 0 or (self.want and self.target is not None):
            eyes = "O.O"
        elif (t % 4.3) < 0.18:
            eyes = "-.-"
        else:
            eyes = "o.o"
        lines = list(ASTRO)
        lines[1:4] = head_rows(eyes, self.look if st in ("float", "chase", "push") else 0)
        if self.swat > 0:
            lines[5] = "   \\|[=#=]|/"  # both paws up: bap
        if st != "nap":
            lines[6] = lines[6].replace("~~", ("~~", "~^", "^~", "-~")[int(t * 5) % 4])
        lines = shades(w, lines)
        if st == "tumble" and int(self.timer * 2.5) % 2:
            lines = flipped(lines)
        s.sprite(lines, self.x, self.y, self.col, over)
        if st == "surf":
            s.text(self.x + 1, self.y + 9, "\\__________/", self.tail)
        elif st == "push" and self.poke > 0:
            s.text(self.x, self.y + 6, "<=", self.tail)


HOLE_COLS = [(255, 250, 220), (255, 200, 90), (255, 120, 40), (200, 50, 60), (90, 30, 110)]


class BlackHole(Ent):
    """Opens near a cat and drags things in: cats, the runner's ball, shooting stars. It bends a passing
    shuttle's path and tugs on banners. When it collapses, everything it swallowed comes flying back out."""
    z = 4

    def __init__(self, w):
        cats = [e for e in w.ents if isinstance(e, AstroCat) and e.state == "float"]
        if cats:
            cat = random.choice(cats)
            a, dist = U(0, TAU), U(30, 44)
            self.x = cat.x + 7 + math.cos(a) * dist
            self.y = cat.y + 4 + math.sin(a) * dist * 0.5
        else:
            self.x, self.y = U(0, w.W), U(0, w.H)
        self.R0 = min(7.5, max(3.0, w.H / 4.8))  # ring radius in rows (twice that in columns)
        self.reach, self.grab = self.R0 * 13, self.R0 * 2.7  # how far it pulls / where a cat is caught
        mx, my = self.R0 * 2 + 4, self.R0 + 2
        self.x = min(max(self.x, mx), max(mx, w.W - mx))
        self.y = min(max(self.y, my), max(my, w.H - my))
        self.age, self.life = 0.0, U(13, 17)
        self.caught = []  # anything with a spit(w, x, y) method that fell in
        self.meals = []   # colours of the shooting stars it ate

    def strength(self):
        return max(0.0, min(1.0, self.age / 2.5, (self.life - self.age) / 1.2))

    def swallow(self, w, comet):
        comet.dead = True
        if len(self.meals) < 14:
            self.meals.append(comet.col)
        w.add(Flash(self.x, self.y, self.R0 * 2, comet.col, 0.3, 0.7))

    def update(self, w, dt):
        self.age += dt
        g = self.strength()
        if random.random() < dt * 55 * g:  # dust spiralling in
            a, r = U(0, TAU), self.R0 * U(2.6, 5.5)
            sp = r / 0.9
            w.add(Particle(self.x + math.cos(a) * r, self.y + math.sin(a) * r * 0.5,
                           (-math.cos(a) * 0.8 - math.sin(a) * 0.6) * sp, (-math.sin(a) * 0.8 + math.cos(a) * 0.6) * sp * 0.5,
                           0.9, ".·:*", [HOLE_COLS[4], HOLE_COLS[2], HOLE_COLS[0]]))
        if self.age >= self.life:
            self.dead = True
            w.add(Flash(self.x, self.y, self.R0 * 5, HOLE_COLS[0], 0.9, 1.6))
            for _ in range(40):
                a, sp = U(0, TAU), U(8, 40)
                w.add(Particle(self.x, self.y, math.cos(a) * sp, math.sin(a) * sp * 0.5, U(0.4, 1.3), "█▓▒░*·.", HOLE_COLS))
            for thing in self.caught:
                thing.spit(w, self.x, self.y)
            for col in self.meals:
                a, sp = U(0, TAU), U(45, 80)
                w.add(Comet(w, self.x, self.y, math.cos(a) * sp, math.sin(a) * sp * 0.5, col))

    def draw(self, w, s):
        t, x, y = w.t, int(self.x), int(self.y)
        R = self.R0 * self.strength()
        if R < 0.7:
            s.put(x, y, "*", HOLE_COLS[1])
            return
        for dy in range(-int(R * 1.35) - 1, int(R * 1.35) + 2):
            for dx in range(-int(2.7 * R) - 2, int(2.7 * R) + 3):
                d = math.hypot(dx / 2, dy) / R
                if d < 0.55:
                    s.put(x + dx, y + dy, " ", WHITE)  # the hole itself: blots out everything behind it
                elif d >= 1.0:
                    if d < 1.35 and (dx * 7 + dy * 13 + int(t * 6)) % 3 == 0:  # faint outer glow
                        s.put(x + dx, y + dy, ".", dim(HOLE_COLS[3], 1.2 - (d - 1.0) * 2.4))
                else:
                    f = (d - 0.55) / 0.45
                    sw = math.sin(math.atan2(dy, dx / 2) * 3 + d * 6 - t * 7)
                    s.put(x + dx, y + dy, "@%#*+=:."[min(7, int(f * 6 + (1 - sw)))], dim(ramp(HOLE_COLS, f), 0.6 + 0.4 * sw))
        w.lights.append((self.x, self.y, R * 3.2, HOLE_COLS[2], 0.55 * self.strength() * (0.85 + 0.15 * math.sin(t * 9))))
        span = int(3.7 * R)
        for dx in range(-span, span + 1):  # accretion disk seen edge-on, crossing in front
            f = abs(dx) / (span + 1)
            s.put(x + dx, y, "=" if f < 0.6 else "-", dim(ramp(HOLE_COLS, f), 0.7 + 0.3 * math.sin(abs(dx) * 0.8 - t * 9)))


FLAME = [(255, 255, 230), (255, 220, 90), (255, 140, 40), (220, 50, 30), (60, 10, 10)]
SMOKE = [(170, 170, 175), (90, 90, 96), (0, 0, 0)]


def near_a_cat(w, chance, fallback, spread):
    """A flight height that passes close to a floating cat (so ships actually meet them), else the fallback."""
    cats = [e for e in w.ents if isinstance(e, AstroCat) and e.state == "float"]
    if not cats or random.random() > chance:
        return fallback
    return min(max(random.choice(cats).y + U(-spread, spread), 1), max(2, w.H - 10))


# The cat out the back of a stalled shuttle, in its helmet, paws braced against the engines
# (the "==" on the arm row), legs pumping between two frames.
PUSHER_TOP = art(r"""
 .-'''''-.
/¬¬/\_/\¬¬\
|¬¬(>.<)¬¬|
\¬¬¬>^<¬¬¬/
 '-.___.-'
  /|[=#]|==
""")
PUSHER = [PUSHER_TOP + [" /_/   \\_\\"], PUSHER_TOP + ["  \\_\\ /_/"]]
PUSH_ARMS = 5  # sprite row the arms are on


class RocketCat(Ent):
    """A toy-sized Space Shuttle with a cat in it. Now and then the engine dies mid-flight and the cat
    has to get out and push until it restarts. Black holes bend its path."""
    z = 8
    LEN, MID = 31, 4.5  # sprite length and vertical centre, for cats reacting to it

    def __init__(self, w):
        self.x = -32.0
        self.by = near_a_cat(w, 0.7, U(4, max(5, w.H - 10)), 9)
        self.dir, self.seen = 1, []
        self.y = self.by
        self.col = random.choice(w.pal)
        self.cruise = U(32, 46)
        self.speed = self.cruise
        self.ph = U(0, TAU)
        self.vby, self.wob = 0.0, 2.0
        self.mode, self.timer = "fly", 0.0  # fly, sputter (engine dying), push (cat out the back, shoving)
        self.fail_x = U(w.W * 0.25, w.W * 0.6) if random.random() < 0.3 else None
        self.engine = True

    def say(self, w, msgs):
        w.add(Bubble(self, random.choice(msgs), WHITE, 24, 0))

    def update(self, w, dt):
        m = self.mode
        if m == "fly":
            self.speed += (self.cruise - self.speed) * min(1.0, dt * 1.5)
            if self.fail_x is not None and self.x > self.fail_x:
                self.fail_x = None
                self.mode, self.timer = "sputter", 1.8
                self.say(w, ["*sputter*", "uh oh", "*cough* *clunk*"])
        elif m == "sputter":
            self.speed -= self.speed * 2.2 * dt
            self.timer -= dt
            if self.timer <= 0:
                self.mode, self.timer = "push", U(5, 7)
                self.say(w, ["...seriously?", "fine. i'll push", "hnnngh"])
        else:
            self.speed = 4.5 + 2.5 * max(0.0, math.sin(w.t * 5))  # heave... heave...
            self.timer -= dt
            if self.timer <= 0:
                self.mode = "fly"
                self.say(w, ["VROOM", "we're back!", "*engine purrs*"])
                w.add(Flash(self.x - 4, self.y + 4.5, 12, (255, 180, 80), 0.5, 1.2))
        for h in w.holes:  # a black hole drags the flight path toward itself
            dx, dy = h.x - (self.x + 15), h.y - (self.y + 4.5)
            d = math.hypot(dx, dy * 2)
            if d < h.reach:
                self.vby += (1 if dy > 0 else -1) * h.strength() * (1 - d / h.reach) * 22 * dt
        self.vby -= self.vby * 1.2 * dt
        self.by = min(max(self.by + self.vby * dt, 1), max(1, w.H - 9))
        self.x += self.speed * dt
        self.wob += ((2.0 if m == "fly" else 0.3) - self.wob) * min(1.0, dt * 3)
        self.y = self.by + math.sin(w.t * 2.2 + self.ph) * self.wob
        self.engine = m == "fly" or (m == "sputter" and int(w.t * 9) % 3 == 0)
        if self.engine:
            for _ in range(4):
                w.add(Particle(self.x - 1, self.y + 4.5 + U(-1.2, 1.2), -U(8, 30), U(-3, 3), U(0.3, 1.0), "█▓▓▒▒░*·.", FLAME))
        elif random.random() < dt * 12:
            w.add(Particle(self.x - 1, self.y + 4.5 + U(-1, 1), -U(2, 9), -U(1, 4), U(0.8, 1.6), "▒░░··", SMOKE))
        if m == "push" and random.random() < dt * 5:  # sweat
            w.add(Particle(self.x - 9, self.y - 1, -U(2, 6), -U(2, 5), 0.6, "'·", [(150, 210, 255), (0, 0, 0)]))
        self.dead = self.x > w.W + 30

    def draw(self, w, s):
        # Side view of the orbiter: white hull and swept tail fin, dark belly, delta wing and nose tip,
        # cockpit windows, engine bells at the back.
        lines = list(ROCKET)
        if self.mode == "push":  # nobody in the cockpit
            lines[2] = lines[2].replace("/\\_/\\", "     ")
            lines[3] = lines[3].replace("( ^w^ )", "▄▄▄▄▄▄▄")
        elif self.mode == "sputter":
            lines[3] = lines[3].replace("^w^", "O.O")
        else:
            lines[3] = lines[3].replace("^w^", ("^w^", "^o^", ">w<", "^w^")[int(w.t * 3) % 4])
        hull, tile, pod, accent = (208, 212, 224), (84, 84, 98), (150, 154, 170), self.col

        def body(i, j, t):
            if j >= 6 or (j >= 4 and i >= 29):  # heat-shield tiles: belly, wing, nose tip
                return tile
            if j <= 2:  # tail fin: coloured tip and rudder edge
                return accent if j == 0 or i == 3 else hull
            if i <= 4 and j <= 4:  # engine pods at the back
                return pod
            if j == 5:  # livery stripe along the lower fuselage
                return accent if 3 <= i <= 26 else pod if i < 3 else hull
            return hull

        if self.engine:
            glow = (255, 170, 70) if int(w.t * 12) % 2 else (255, 120, 50)
        else:
            glow = (70, 60, 60)
        over = {"/": WHITE, "\\": WHITE, "_": WHITE, "(": WHITE, ")": WHITE, "^": WHITE, "w": WHITE, "o": WHITE,
                "O": WHITE, ".": WHITE, ">": WHITE, "<": WHITE, "█": body, "▄": body, "▀": body,
                "▓": (140, 150, 178), "▐": glow, "▒": (90, 200, 255)}  # ▓ = payload-bay doors
        s.sprite(shades(w, lines), self.x, self.y, hull, over, w.t)
        if self.mode == "push":
            # Arms end right at the engine bells, level with them (ship row 4).
            px, py = self.x - len(PUSHER_TOP[PUSH_ARMS]), self.y + 4 - PUSH_ARMS
            red = (255, 60, 60) if int(w.t * 2) % 2 else (90, 20, 20)
            s.sprite(shades(w, PUSHER[int(w.t * 6) % 2]), px, py, mix(WHITE, self.col, 0.25),
                     {"=": self.col, "#": red, ">": WHITE, "<": WHITE, ".": WHITE, "^": self.col})
        if self.engine:
            # Engine plume: shines backwards only. The hull blocks it, so just the engine end catches the glow.
            w.lights.append((self.x - 6, self.y + 4.5, 13, (255, 150, 60), 0.75 + 0.25 * math.sin(w.t * 31), self.x + 2))


class UfoCat(Ent):
    """A beam saucer. Its job decides what the beam is for:

      fish  beams up a fish, as saucers do
      cat   hunts down a floating cat, beams it up, carries it across the sky and drops it somewhere else
      ball  lies in wait for the runner and steals its ball, then either drops it back or flies off with it

    Beam saucers never tow banners.
    """
    z = 7

    def __init__(self, w, job="fish", target=None):
        self.job, self.target = job, target
        self.col = random.choice(w.pal)
        self.beam = (120, 255, 150)
        self.age = self.pt = 0.0  # pt = time in the current phase
        self.phase = "enter"      # enter, hover, beam, carry (cat), gloat (ball), leave
        self.cargo = None
        self.glow, self.len = 0.0, 2  # beam strength 0..1 and its length in rows
        self.sway = 7.0 if job == "fish" else 1.5
        self.x0 = U(8, max(9, w.W - 34))
        self.hy = U(2, max(3, w.H * 0.3))
        self.keep = random.random() < 0.5  # ball job: fly off with it instead of dropping it back
        if job == "cat":
            self.aim(w, 1.0)
        elif job == "ball":  # be where the ball will be when the beam comes on
            b = target.ball
            self.x0 = b.x + target.speed * 2.4 - 12
            self.hy = min(max(b.y - 12, 1), max(1, w.H - 14))
        self.dest = self.x0
        self.x, self.y = self.x0, -8.0

    def aim(self, w, f):
        """Line the beam up over the target cat."""
        c = self.target
        self.x0 += (c.x + 7 - 12 - self.x0) * f
        self.hy += (min(max(c.y - 9, 1), max(1, w.H - 14)) - self.hy) * f

    def go(self, phase):
        self.phase, self.pt = phase, 0.0

    def in_beam(self, px, py):
        k = py - (self.y + 6)
        return self.glow > 0.6 and 0 <= k <= self.len and abs(px - (self.x + 12)) <= 3 + k * 0.7

    def update(self, w, dt):
        self.age += dt
        self.pt += dt
        ph, job, tg = self.phase, self.job, self.target
        beam = False
        if ph == "enter":
            dur = 1.0 if job == "ball" else 2.0
            if job == "cat" and tg.free():
                self.aim(w, min(1.0, dt * 2.5))
            if self.pt >= dur:
                self.go("hover")
        elif ph == "hover":
            if job == "cat" and tg.free():
                self.aim(w, min(1.0, dt * 2.5))
            if self.pt >= (0.3 if job == "ball" else 1.6):
                self.go("beam")
        elif ph == "beam":
            beam = True
            if job == "fish":
                if self.pt > 8:
                    self.go("leave")
            elif job == "cat":
                c = tg
                if self.cargo is None:
                    if not c.free() or self.pt > 7:
                        self.go("leave")  # somebody else got to it first, or it won't hold still
                    else:
                        self.aim(w, min(1.0, dt * 2.5))
                        if self.in_beam(*c.center()):
                            c.disturb()
                            c.state, c.ufo, c.vx, c.vy = "beamed", self, 0.0, 0.0
                            self.cargo = c
                            c.say(w, BEAMED)
                else:  # reel it in
                    c.x += (self.x + 5 - c.x) * min(1.0, dt * 5)
                    c.y -= min(max(c.y - (self.y + 6), 0.0), 6 * dt)
                    if c.y - (self.y + 6) < 0.3:
                        self.go("carry")
                        far = (U(8, max(9, w.W * 0.35)), U(w.W * 0.6, max(w.W * 0.6 + 1, w.W - 34)))
                        self.dest = far[1] if self.x0 < w.W / 2 else far[0]
            else:
                b = tg.ball
                if self.cargo is None:
                    if b.mode in ("lead", "loose") and self.in_beam(b.x, b.y):
                        b.mode, b.holder = "held", self
                        self.cargo = b
                        tg.react(w, "stolen", self)
                    elif self.pt > 9 or tg.dead or b.dead:
                        self.go("leave")
                else:
                    b.x += (self.x + 12 - b.x) * min(1.0, dt * 6)
                    b.y -= min(max(b.y - (self.y + 5.5), 0.0), 9 * dt)
                    if b.y - (self.y + 5.5) < 0.3:
                        self.go("gloat")
        elif ph == "carry":
            beam = True
            c = self.cargo
            step, d = 26 * dt, self.dest - self.x0
            if c.state != "beamed" or c.ufo is not self:
                self.cargo = None
                self.go("leave")
            elif abs(d) > step:
                self.x0 += step if d > 0 else -step
            else:  # arrived: let go
                self.x0 = self.dest
                c.state, c.ufo, c.vx, c.vy, c.calm = "float", None, 0.0, 5.0, 0.0
                c.say(w, DROPPED)
                self.cargo = None
                self.go("leave")
        elif ph == "gloat":
            beam = True
            if self.pt > 1.8:
                if self.keep:
                    tg.react(w, "chase", self)
                else:
                    b = self.cargo
                    b.mode, b.holder, b.timer, b.vx, b.vy = "loose", None, 1.0, 0.0, 6.0
                    self.cargo = None
                    tg.react(w, "returned", self)
                self.go("leave")
        ph = self.phase
        if ph == "leave":
            self.y -= self.pt * 60 * dt
            self.x0 += self.pt * 50 * dt
            self.dead = self.pt > 2.5
        elif ph == "enter":
            dur = 1.0 if job == "ball" else 2.0
            self.y = -8 + (self.hy + 8) * (1 - (1 - min(1.0, self.pt / dur)) ** 3)
        else:
            self.y = self.hy + math.sin(self.age * 2) * 0.7
        self.x = self.x0 + math.sin(self.age * 0.7) * self.sway
        c = self.cargo
        if c is not None:  # whatever we are holding comes with us
            if job == "cat":
                if ph == "carry":
                    c.x, c.y = self.x + 5, self.y + 6 + 0.4 * math.sin(self.age * 5)
            elif ph in ("gloat", "leave"):
                c.x, c.y = self.x + 12, self.y + 5.5
        self.glow += ((1.0 if beam else 0.0) - self.glow) * min(1.0, dt * 4)
        self.len = max(2, min(11 if ph == "carry" else 14, w.H - int(self.y) - 7))

    def draw(self, w, s):
        a, x, y = self.age, int(round(self.x)), int(round(self.y))
        g = self.glow
        if g > 0.05:
            length = self.len * g
            w.lights.append((x + 12, y + 6 + length / 2, 5 + length * 0.55, self.beam,
                             0.6 * g * (0.85 + 0.15 * math.sin(a * 23))))  # tractor beam glow
            for k in range(int(length)):
                hw = 3 + k * 0.7
                for dx in range(int(-hw), int(hw) + 1):
                    if random.random() < 0.6:
                        edge = 1 - abs(dx) / (hw + 1)
                        s.put(x + 12 + dx, y + 6 + k, random.choice("░░:.|"), dim(self.beam, 0.25 + 0.6 * edge))
            f = (self.pt - 1) / 6
            if self.job == "fish" and self.phase == "beam" and 0 < f < 1:
                fy = y + 6 + (self.len - 1) * (1 - f)
                s.text(x + 11 + math.sin(a * 6) * 1.5, fy, "><>" if int(a * 4) % 2 else "><»", (255, 170, 80))
        lines = list(UFO)
        if self.phase == "gloat" or (self.phase == "leave" and self.cargo is not None):
            lines[2] = lines[2].replace("o.o", "^.^")  # smug
        elif (a % 3.1) < 0.2:
            lines[2] = lines[2].replace("o.o", "-.-")
        elif g > 0.5:
            lines[2] = lines[2].replace("o.o", "O.O")
        pal = w.pal
        over = {"/": WHITE, "\\": WHITE, "_": WHITE, "(": WHITE, ")": WHITE, ".": WHITE, "o": self.beam, "O": self.beam,
                "^": self.beam, "-": WHITE, "●": lambda i, j, t: pal[(i // 3 + int(t * 8)) % len(pal)]}
        s.sprite(shades(w, lines), x, y, self.col, over, w.t)


class Ball(Ent):
    """The runner's glowing ball. It leads the runner, but it can be batted by a cat, stolen by a
    saucer's beam, or swallowed by a black hole and spat back out."""
    z = 7
    RED = (255, 70, 60)

    def __init__(self, runner, w):
        self.r = runner
        self.mode = "lead"  # lead, loose (knocked free), held (by a saucer), sucked, gone (in a black hole)
        self.holder = self.hole = None
        self.vx = self.vy = self.timer = self.cd = self.ang = self.rad = 0.0
        self.x, self.y = self.spot(w)

    def spot(self, w):
        return self.r.x + 37 + math.sin(w.t * 5) * 5, self.r.y + 3 + math.sin(w.t * 7.3) * 2

    def center(self):
        return self.x, self.y

    def bat(self, w, vx, vy):
        self.mode, self.timer, self.cd = "loose", 1.3, 3.0
        self.vx += vx
        self.vy += vy

    def spit(self, w, x, y):
        a = U(0, TAU)
        self.x, self.y, self.vx, self.vy = x, y, math.cos(a) * 30, math.sin(a) * 10
        self.mode, self.timer, self.hole = "loose", 2.0, None
        self.r.react(w, "returned")

    def update(self, w, dt):
        self.cd -= dt
        m = self.mode
        if self.r.dead:
            self.dead = True
        elif m in ("lead", "loose"):
            if m == "loose":
                self.timer -= dt
                ax, ay = -self.vx * 0.8, -self.vy * 0.8
                if self.timer <= 0:
                    self.mode = "lead"
            else:  # a stiff leash to a spot dancing just ahead of the runner
                tx, ty = self.spot(w)
                ax, ay = (tx - self.x) * 30 - self.vx * 11, (ty - self.y) * 30 - self.vy * 11
            for h in w.holes:
                dx, dy = h.x - self.x, (h.y - self.y) * 2
                d = math.hypot(dx, dy) or 1.0
                g = h.strength()
                inf = g * max(0.0, 1 - d / h.reach)
                if inf <= 0:
                    continue
                ax += dx / d * (30 + 200 * inf)
                ay += dy / d * (30 + 200 * inf) * 0.5
                if inf > 0.4 and self.mode == "lead":  # too close: the leash snaps
                    self.mode, self.timer = "loose", 3.0
                if d < h.grab * 0.7 and g > 0.6:
                    self.mode, self.hole = "sucked", h
                    self.ang, self.rad = math.atan2(-dy, -dx), d
                    h.caught.append(self)
                    self.r.react(w, "lost", h)
                    return
            self.vx += ax * dt
            self.vy += ay * dt
            self.x += self.vx * dt
            self.y += self.vy * dt
            if self.y < 0 or self.y > w.H - 1:
                self.vy = abs(self.vy) if self.y < 0 else -abs(self.vy)
                self.y = min(max(self.y, 0), w.H - 1)
        elif m == "held":
            if self.holder is None or self.holder.dead:
                self.dead = True  # gone with the saucer
        elif m == "sucked":
            h = self.hole
            self.ang += dt * (2.5 + 30 / (self.rad + 3))
            self.rad -= dt * (3 + 40 / (self.rad + 4))
            self.x = h.x + math.cos(self.ang) * self.rad
            self.y = h.y + math.sin(self.ang) * self.rad * 0.5
            if self.rad <= 0.8:
                self.mode = "gone"
        if self.mode != "gone" and not self.dead:
            for _ in range(2):  # sparks
                w.add(Particle(self.x + U(-1, 1), self.y + U(-0.5, 0.5), U(-14, 3), U(-5, 5), U(0.3, 0.9), "✦*+·.",
                               [WHITE, (255, 90, 70), (120, 0, 0), (0, 0, 0)]))

    def draw(self, w, s):
        if self.mode == "gone":
            return
        pulse = 0.75 + 0.25 * math.sin(w.t * 14)
        s.put(self.x - 1, self.y, "(", dim(self.RED, pulse * 0.7))
        s.put(self.x + 1, self.y, ")", dim(self.RED, pulse * 0.7))
        s.put(self.x, self.y, "●", dim(self.RED, pulse + 0.2))
        w.lights.append((self.x, self.y, 6, (255, 50, 40), 0.7 * pulse))


class Runner(Ent):
    """A helmeted cat on jet boots sprinting after its ball.

    Moods: run; stare (a saucer took the ball: skid to a stop and glare at it); chase (the saucer is
    leaving with it); dive (a black hole swallowed the ball: go in after it); sucked and gone (inside
    the hole, until it spits cat and ball back out).
    """
    z = 7

    def __init__(self, w):
        self.x = -28.0
        self.y = U(w.H * 0.45, max(w.H * 0.45 + 1, w.H - 9))
        self.col = mix(WHITE, random.choice(w.pal), 0.5)
        self.eye = random.choice(w.pal)
        self.boot = random.choice(w.pal)
        self.speed = 30.0
        self.mood, self.wait, self.thief = "run", 0.0, None
        self.ang = self.rad = 0.0
        self.ball = Ball(self, w)
        w.add(self.ball)

    def say(self, w, msgs):
        w.add(Bubble(self, random.choice(msgs), self.eye, 24, 0))

    def react(self, w, what, src=None):
        if what == "stolen":
            self.mood, self.wait, self.thief = "stare", 0.0, src
            self.say(w, ["HEY!", "my ball!!", "give it back", "...seriously?"])
        elif what == "lost":  # into a black hole: go and get it
            if self.mood == "run":
                self.mood, self.thief = "dive", src
                self.say(w, ["MY BALL!", "i'm going in", "not my ball!!", "hold on, ball!"])
        elif what == "chase":
            self.mood = "chase"
            self.say(w, ["COME BACK!!", "THIEF!", "that's MINE"])
        elif self.mood in ("stare", "dive"):
            self.mood = "run"
            self.say(w, ["ball!!", "yay!", "mine again"])

    def spit(self, w, x, y):
        """Thrown back out of a collapsing black hole."""
        self.x, self.y = x - 12, min(max(y - 3, 0), max(0, w.H - 8))
        self.mood, self.speed = "run", 0.0
        self.say(w, ["worth it.", "got it!", "never again", "what a ride"])
        w.sparks(x, y, self.boot, 14)

    def stride(self, w):
        return int(w.t * 9) % 2 if self.speed > 4 else 0

    def update(self, w, dt):
        b, m = self.ball, self.mood
        if m in ("sucked", "gone"):
            self.speed = 0.0
            if m == "sucked":
                h = self.thief
                self.ang += dt * (2.5 + 30 / (self.rad + 3))
                self.rad -= dt * (3 + 40 / (self.rad + 4))
                self.x = h.x + math.cos(self.ang) * self.rad - 12
                self.y = h.y + math.sin(self.ang) * self.rad * 0.5 - 3
                if self.rad <= 0.8:
                    self.mood = "gone"
            return
        if m == "dive":
            h = self.thief
            dx, dy = h.x - (self.x + 12), h.y - (self.y + 3)
            d = math.hypot(dx, dy * 2) or 1.0
            if h.dead:
                self.mood = "run"
            elif d < h.grab:
                self.mood, self.ang, self.rad = "sucked", math.atan2(-dy * 2, -dx), d
                h.caught.append(self)
                return
            else:  # jets on full, straight at it
                self.speed += (46 - self.speed) * min(1.0, dt * 3)
                self.x += dx / d * self.speed * dt
                self.y += dy * 2 / d * self.speed * 0.5 * dt
        else:
            if m == "stare":
                want = 0.0
                self.wait += dt
                if self.wait > 26 or b.dead:  # it isn't coming back
                    self.mood = "run"
                    self.say(w, ["...fine.", "i didn't want it anyway"])
            elif m == "chase":
                want = 60.0
            else:
                gap = b.x - self.x
                want = 30.0 if b.mode == "lead" or b.dead else 44.0 if gap > 45 else 12.0 if gap < 25 else 30.0
            self.speed += (want - self.speed) * min(1.0, dt * (6 if want < self.speed else 2.5))
            self.x += self.speed * dt
            if want == 0 and self.speed > 4:  # skidding
                w.add(Particle(self.x + 12, self.y + 7, U(4, 14), -U(0, 3), 0.5, "*·.", [WHITE, self.boot, (0, 0, 0)]))
        if self.speed > 4:
            bx = self.x + (3 if self.stride(w) == 0 else 5)
            for foot in (2, 7):  # jet boots: flame out the back of each boot
                for _ in range(2):
                    w.add(Particle(bx + foot, self.y + 6.6, -U(8, 24), U(2, 9), U(0.25, 0.7), "▓▒▒░*·.", FLAME))
        self.dead = self.x > w.W + 45

    def draw(self, w, s):
        m = self.mood
        if m == "gone":
            return
        if m == "sucked" and self.rad <= self.thief.grab * 0.6:  # shrinking as it falls in
            cx, cy = self.x + 12, self.y + 3
            if self.rad > self.thief.grab * 0.3:
                s.sprite(shades(w, SMALL_CAT), cx - 3, cy - 1, self.col, {"o": self.eye})
            else:
                s.text(cx - 2, cy, "=^.^=", self.col)
            return
        k = self.stride(w)
        lines = list(RUNNER_TOP) + RUNNER_LEGS[k]
        if k:
            lines[2] = lines[2].replace("~.", ".~")
        if m == "stare":
            lines[2] = lines[2].replace("o.o", "O.O")
            s.put(self.x + 16, self.y - 1, "!" if self.wait < 1.2 else "?", (255, 90, 80))
        elif m in ("chase", "dive"):
            lines[2] = lines[2].replace("o.o", ">.<")
        elif m == "sucked":
            lines[2] = lines[2].replace("o.o", "@.@")
        over = {"o": self.eye, "O": self.eye, "@": self.eye, "~": self.eye, "^": self.eye,
                "[": self.boot, "]": self.boot, "▄": self.boot}
        s.sprite(shades(w, lines), self.x, self.y, self.col, over)
        if self.speed > 4:
            w.lights.append((self.x + 7, self.y + 7.5, 6, (255, 150, 60), 0.5 + 0.2 * math.sin(w.t * 37)))  # boot jets


class Yarn(Ent):
    """A giant ball of yarn rolling through, unravelling as it goes. Cats can't not look, and the
    keen ones go after it and bat it around."""
    z = 5

    def __init__(self, w):
        self.r = 4 if w.H >= 30 else 3
        self.dir = random.choice((-1, 1))
        self.speed = U(10, 14)
        self.x = -2.0 * self.r - 3 if self.dir > 0 else w.W + 2.0 * self.r + 3
        lo, hi = self.r + 1, max(self.r + 1, w.H - self.r - 2)
        self.y = min(max(near_a_cat(w, 0.7, U(lo, hi), 6) + 4, lo), hi)
        self.vy = self.rot = 0.0
        self.col = random.choice(w.pal)
        self.thread = []  # [x, y, born]: the loose end it leaves behind
        self.seen = []
        self.away = False

    def center(self):
        return self.x, self.y

    def update(self, w, dt):
        r = self.r
        self.x += self.dir * self.speed * dt
        self.y += self.vy * dt
        self.vy -= self.vy * 1.5 * dt
        lo, hi = r + 1, max(r + 1, w.H - r - 2)
        if self.y < lo or self.y > hi:
            self.vy = abs(self.vy) if self.y < lo else -abs(self.vy)
            self.y = min(max(self.y, lo), hi)
        self.rot += self.dir * self.speed * dt / (2.0 * r)  # rolling without slipping
        tx = self.x - self.dir * (2 * r - 1)
        if 0 <= tx < w.W and (not self.thread or abs(self.thread[-1][0] - tx) >= 1):
            self.thread.append([tx, self.y + r - 0.3 + math.sin(tx * 0.35) * 0.7, w.t])
        while self.thread and w.t - self.thread[0][2] > 14:
            self.thread.pop(0)
        for p in self.thread:
            p[1] += 0.12 * dt  # the thread slowly sags
        self.away = self.x > w.W + 2 * r + 3 if self.dir > 0 else self.x < -2 * r - 3
        if not self.away:
            for c in w.cats:
                if c.state != "float":
                    continue
                if c not in self.seen and abs(c.x + 7 - self.x) < 110:
                    self.seen.append(c)
                    c.notice(w, self, abs(c.x + 7 - self.x) < 80 and random.random() < 0.75, YARN)
                if c.target is self and c.want and c.bump_cd <= 0:
                    cx, cy = c.center()
                    dx, dy = self.x - cx, (self.y - cy) * 2
                    d = math.hypot(dx, dy) or 1.0
                    if d < 2 * r + 7:  # bap
                        c.swat, c.bump_cd = 0.4, 1.5
                        self.vy += (1 if dy >= 0 else -1) * U(3, 6)
                        c.vx -= dx / d * 8
                        c.vy -= dy / d * 4
                        for _ in range(8):
                            w.add(Particle(self.x - dx * 0.5, self.y - dy * 0.25, U(-10, 10), U(-5, 5), U(0.3, 0.8), "~*·.", [WHITE, self.col, (0, 0, 0)]))
                        if random.random() < 0.4:
                            c.say(w, BAP)
        self.dead = self.away and not self.thread

    def draw(self, w, s):
        t, r = w.t, self.r
        for i, (tx, ty, born) in enumerate(self.thread):
            f = 1 - (t - born) / 14
            s.put(tx, ty, "~" if i % 3 else "-", dim(self.col, 0.15 + 0.6 * f))
        if self.away:
            return
        cx, cy = int(round(self.x)), int(round(self.y))
        # Two sets of strands wound at different angles; both turn with the ball as it rolls.
        strands = []
        for ang in (self.rot, self.rot + 1.25):
            a = ang % math.pi
            ch = "-" if a < 0.39 or a > 2.75 else "\\" if a < 1.18 else "|" if a < 1.96 else "/"
            strands.append((math.sin(ang), math.cos(ang), ch))
        for dy in range(-r, r + 1):
            ny = dy / r
            for dx in range(-2 * r, 2 * r + 1):
                nx = dx / (2.0 * r)
                d2 = nx * nx + ny * ny
                if d2 > 1:
                    continue
                light = 0.45 + 0.55 * max(0.0, -0.5 * nx - 0.5 * ny + 0.7 * math.sqrt(1 - d2))
                ch, shade = ":", 0.55
                for k, (sa, ca, sch) in enumerate(strands):
                    if math.sin((-nx * sa + ny * ca) * 11 + k * 2) > 0.1:
                        ch, shade = sch, 1.0 - 0.2 * k
                        break
                s.put(cx + dx, cy + dy, ch, dim(self.col, light * shade))


MOUSE_SHIP = art(r"""
   ()_()
  (¬·.·¬)
▄▄█▄▄▄▄▄█▄▄
 ▀▀●▀●▀●▀▀
""")


class MouseShip(Ent):
    """A space mouse in a tiny saucer, zig-zagging across with a cat or two in hot pursuit."""
    z = 7

    def __init__(self, w):
        self.dir = random.choice((-1, 1))
        self.speed = 30.0
        self.x = -12.0 if self.dir > 0 else w.W + 1.0
        self.y0 = min(max(near_a_cat(w, 0.7, U(4, w.H - 8), 5) + 2, 4), max(4, w.H - 8))
        self.y = self.y0
        self.age = self.boost = 0.0
        self.squeak = U(0.5, 2)
        self.col = random.choice(w.pal)
        cats = sorted((c for c in w.cats if c.state == "float"), key=lambda c: abs(c.x + 7 - self.x))
        for c in cats[:2]:
            c.start_chase(w, self)

    def center(self):
        return self.x + 5, self.y + 2

    def say(self, w, msgs):
        w.add(Bubble(self, random.choice(msgs), self.col, 11, -1))

    def update(self, w, dt):
        self.age += dt
        self.boost -= dt
        self.squeak -= dt
        self.x += self.dir * self.speed * (2.0 if self.boost > 0 else 1.0) * dt
        self.y = self.y0 + math.sin(self.age * 3.1) * 3
        if self.squeak <= 0:
            self.squeak = U(2.5, 5)
            self.say(w, ["squeak!", "eep!", "cheese?", "nope nope nope", "not today"])
        mx, my = self.center()
        for c in w.cats:
            if c.state == "chase" and c.target is self and self.boost <= 0:
                cx, cy = c.center()
                if math.hypot(cx - mx, (cy - my) * 2) < 11:  # too close: floor it
                    self.boost, self.squeak = 0.7, 3.0
                    self.say(w, ["EEK!", "TOO CLOSE", "AAA"])
        if random.random() < dt * 20:
            w.add(Particle(self.x + (0 if self.dir > 0 else 10), self.y + 3, -self.dir * U(4, 14), U(-1, 2), 0.5, "*·.", [WHITE, self.col, (0, 0, 0)]))
        self.dead = self.x > w.W + 2 if self.dir > 0 else self.x < -13

    def draw(self, w, s):
        pal = w.pal
        fur = (200, 200, 210)
        over = {"(": fur, ")": fur, "_": fur, ".": (255, 150, 170), "·": WHITE,
                "●": lambda i, j, t: pal[(i + int(t * 10)) % len(pal)]}
        s.sprite(MOUSE_SHIP, self.x, self.y, self.col, over, w.t)
        s.put(self.x + (-1 if self.dir > 0 else 11), self.y + 1, "~", fur)  # tail streaming behind


class Box(Ent):
    """A cardboard box drifting through. Any cat that reaches it climbs in and sits there for a while."""
    z = 6
    CARD = (196, 150, 96)
    LABELS = ["FRAGILE", "THIS UP", "CAT BOX", "DO NOT ", " TUNA  ", "IF FITS", "  ???  "]

    def __init__(self, w):
        self.dir = random.choice((-1, 1))
        self.speed = U(6, 9)
        self.x = -12.0 if self.dir > 0 else w.W + 1.0
        self.y = min(max(near_a_cat(w, 0.8, U(3, w.H - 8), 4) + 3, 2), max(2, w.H - 6))
        self.label = random.choice(self.LABELS)
        self.cat, self.used, self.timer, self.age = None, False, 0.0, 0.0
        self.seen = []
        self.away = False  # True once it is taken or finished with, so other cats lose interest

    def center(self):
        return self.x + 5, self.y + 2.5

    def update(self, w, dt):
        self.age += dt
        c = self.cat
        if c is None:
            self.x += self.dir * self.speed * dt
            if not self.used:
                bx, by = self.center()
                for o in w.cats:
                    if o.state != "float":
                        continue
                    cx, cy = o.center()
                    dx, dy = bx - cx, by - cy
                    if o not in self.seen and abs(dx) < 50 and abs(dy) < 16:
                        self.seen.append(o)
                        o.notice(w, self, True, BOXY)
                    if abs(dx) < 8 and abs(dy) < 4:  # close enough: in it goes
                        o.disturb()
                        o.state, o.box, o.vx, o.vy = "boxed", self, 0.0, 0.0
                        o.x, o.y = self.x - 1, self.y - 4
                        o.say(w, INBOX)
                        self.cat, self.timer, self.away = o, U(13, 20), True
                        break
            self.dead = self.x > w.W + 2 or self.x < -13
        else:  # occupied: mill about slowly, staying on screen
            self.timer -= dt
            self.x += self.dir * 2.0 * dt
            if self.x < 3:
                self.dir = 1
            elif self.x > w.W - 14:
                self.dir = -1
            c.x, c.y = self.x - 1, self.y - 4
            if self.timer <= 0:  # bored now
                c.state, c.box, c.calm = "float", None, 0.0
                c.x, c.y, c.vx, c.vy = self.x - 2, max(0.0, self.y - 6), -self.dir * 3.0, -5.0
                c.say(w, UNBOX)
                self.cat, self.used, self.speed = None, True, 10.0

    def draw(self, w, s):
        c, card = self.cat, self.CARD
        if c is None:
            lines = [" _________ ", "|\\_______/|"]
            over = None
        else:
            eyes = "-.-" if (w.t % 3.7) < 0.2 else "o.o"
            lines = shades(w, ["   /\\_/\\   ", "|‾(¬" + eyes + "¬)‾|"])
            over = {"/": c.col, "\\": c.col, "_": c.col, "(": c.col, ")": c.col, ".": c.col, "-": c.col, "o": c.eye}
        s.sprite(lines + ["|¬¬¬¬¬¬¬¬¬|", "|¬¬¬¬¬¬¬¬¬|", "'---------'"], self.x, self.y, card, over)
        s.text(self.x + 2, self.y + 3, self.label, dim(card, 0.6))
        if c is not None:
            s.put(self.x + 11, self.y + 3, "~^"[int(w.t * 4) % 2], c.tail)  # tail hanging out the side


class Satellite(Ent):
    """A slow satellite with a cat sitting on it, pushing the loose parts off the edge one at a time."""
    z = 6
    DECK = 26  # deck length; it starts 11 columns in, after the left solar panel and its strut
    PANEL = ["┌─┬─┬─┬─┐", "│▒│▒│▒│▒│", "├─┼─┼─┼─┤", "│▒│▒│▒│▒│", "└─┴─┴─┴─┘"]
    GOLD = (214, 170, 84)

    def __init__(self, w):
        self.dir = random.choice((-1, 1))
        self.speed = U(5, 7)
        self.x = -50.0 if self.dir > 0 else w.W + 1.0
        if random.random() < 0.5:
            self.y = U(2, max(3, w.H * 0.25))
        else:
            self.y = U(w.H * 0.6, max(w.H * 0.6 + 1, w.H - 8))
        self.items = [[8 + 4 * i, ch] for i, ch in enumerate("▪o+▫x")]  # [offset along the deck, glyph]
        self.timer, self.paw, self.gaze, self.age = U(2, 3), 0.0, 0.0, 0.0
        self.eye = random.choice(w.pal)
        self.done = False

    def update(self, w, dt):
        self.age += dt
        self.paw -= dt
        self.gaze -= dt
        self.x += self.dir * self.speed * dt
        self.timer -= dt
        if self.timer <= 0 and self.items and 0 < self.x + 24 < w.W:
            self.timer, self.paw = U(2.6, 4.2), 0.35
            keep = []
            for it in self.items:  # one shove moves the whole row along; whatever passes the edge is gone
                it[0] += 3
                if it[0] >= self.DECK:
                    self.gaze = 1.6
                    w.add(Particle(self.x + 11 + self.DECK, self.y + 1, self.dir * self.speed + U(1, 4), U(2, 4), 3.0,
                                   it[1] * 5 + "·.", [WHITE, (150, 150, 165), (0, 0, 0)]))
                else:
                    keep.append(it)
            self.items = keep
            if not keep and not self.done:
                self.done = True
                w.add(Bubble(self, random.choice(["...what.", "they were loose", "all done.", "it's cleaner now"]), self.eye, 20, -1))
        self.dead = self.x > w.W + 2 if self.dir > 0 else self.x < -50

    def draw(self, w, s):
        x, y, t = self.x, self.y, w.t
        gold, frame = self.GOLD, (120, 140, 190)
        for px in (0, 39):  # two solar panels: a grid of cells that shimmer
            for j, row in enumerate(self.PANEL):
                for i, ch in enumerate(row):
                    if ch == "▒":
                        s.put(x + px + i, y + 1 + j, "▒", dim((70, 130, 230), 0.55 + 0.45 * math.sin(i * 0.9 + j * 1.7 + px + t * 2.5)))
                    else:
                        s.put(x + px + i, y + 1 + j, ch, frame)
        s.text(x + 9, y + 3, "══", frame)
        s.text(x + 37, y + 3, "══", frame)
        s.text(x + 11, y + 2, "▄" * self.DECK, gold)  # the body, wrapped in gold foil
        for i in range(self.DECK):
            s.put(x + 11 + i, y + 3, "█" if i % 6 else "▓", dim(gold, 0.85))
        s.text(x + 11, y + 4, "▀" * self.DECK, dim(gold, 0.65))
        s.put(x + 11 + self.DECK - 3, y + 3, "●", (255, 60, 60) if int(t * 2) % 2 else (90, 20, 20))
        s.text(x + 20, y + 5, "\\__/", WHITE)  # dish underneath
        s.put(x + 21.5, y + 6, "'", WHITE)
        s.text(x + 33, y + 0, "|", frame)  # antenna
        s.put(x + 33, y - 1, "*" if int(t * 3) % 2 else "·", (255, 90, 80))
        s.put(x + 33, y + 1, "|", frame)
        for off, ch in self.items:
            s.put(x + 11 + off, y + 1, ch, WHITE)
        if self.done:
            eyes = "^.^"
        elif self.gaze > 0:
            eyes = "o.o"
        else:
            eyes = "-.-" if (t % 4.1) < 0.2 else "o.o"
        face = "(¬¬" + eyes + ")" if self.gaze > 0 else "(¬" + eyes + "¬)"  # watches each one go
        lines = shades(w, ["  /\\_/\\", " " + face + ("=-" if self.paw > 0 else "")])
        s.sprite(lines, x + 11, y, WHITE, {"o": self.eye, "^": self.eye, "=": self.eye, "-": WHITE})


class Cucumber(Ent):
    """Appears silently behind a cat. The cat notices. The cat leaves, quickly."""
    z = 6
    GREEN = (110, 190, 90)

    def __init__(self, w, cat):
        self.cat = cat
        self.side = -1 if cat.x > 18 else 1  # behind it if there is room, otherwise in front
        self.x, self.y = cat.x + (-13 if self.side < 0 else 16), cat.y + 6
        self.age, self.fired = 0.0, None

    def update(self, w, dt):
        self.age += dt
        c = self.cat
        if self.fired is None:
            if not c.free():
                self.fired = self.age  # something else got to the cat first; just fade away
            else:
                self.x, self.y = c.x + (-13 if self.side < 0 else 16), c.y + 6
                if self.age > 2.0:
                    c.wide = 0.5
                if self.age > 2.4:
                    self.fired = self.age
                    c.knock(w, -self.side * U(75, 95), -U(10, 18), 4.5, CUKE)
        self.dead = self.fired is not None and self.age - self.fired > 3.5

    def draw(self, w, s):
        f = min(1.0, self.age / 1.2) if self.fired is None else max(0.0, 1 - (self.age - self.fired - 2) / 1.5)
        s.text(self.x, self.y, "(▓▒▓▓▒▓▓▒▓)", dim(self.GREEN, f))


# ───────────────────────────────── world ─────────────────────────────────

class World:
    def __init__(self, W, H):
        self.pal = load_palette()
        self.t = 0.0
        self.warp = 0.0
        self.warp_until = -1.0
        self.ents = []
        self.ships, self.holes, self.cats = [], [], []
        self.shades = False  # True while a pulsar is out: cats wear sunglasses
        self.next = {"hole": 18.0, "pulsar": 34.0, "banner": 0.8, "comet": 1.5, "planet": 0.0, "rocket": 6.0, "const": 10.0, "ufo": 14.0,
                     "runner": 22.0, "warp": 12.0,
                     "shower": 26.0, "shower_comet": 0.0,
                     "box": 30.0, "moon": 42.0, "cuke": 52.0, "mouse": 62.0, "yarn": 74.0, "sat": 86.0}
        for name in os.environ.get("SPACECATS_SOON", "").split(","):  # preview aid: bring named events forward
            if name in self.next:
                self.next[name] = 2.0
        self.lights = []
        self.neb_off = 0.0
        self.shower_until = -1.0
        self.resize(W, H)

    def add(self, e):
        self.ents.append(e)

    def resize(self, W, H):
        self.W, self.H = W, H
        self.scr = Screen(W, H)
        rnd = random.Random(7)
        self.stars = []
        for _ in range(W * H // 28):
            layer = rnd.choices((0, 1, 2), (6, 3, 1))[0]
            tint = mix(WHITE, rnd.choice(self.pal), rnd.random() * 0.6)
            chx = (".", rnd.choice(".·"), rnd.choice("*+✦·"))[layer]
            self.stars.append([rnd.uniform(0, W), rnd.randrange(H), layer, chx, tint, rnd.uniform(0, TAU), rnd.uniform(1, 5)])
        # nebula: a horizontally tiling dust texture that scrolls slowly
        tw = self.tw = max(2, W * 2)
        a, b = rnd.sample(self.pal, 2)
        self.neb = []
        for y in range(H):
            row = []
            for x in range(tw):
                u = TAU * x / tw
                v = (math.sin(u * 2 + y * 0.21) + math.sin(u * 3 - y * 0.13 + 1.7)
                     + math.sin(u * 5 + y * 0.09 + 4.0) * 0.6 + math.sin(y * 0.3 + u) * 0.5)
                cell = None
                if v > 1.1:
                    i = (v - 1.1) / 2.0
                    if rnd.random() < 0.35 + i:
                        chx = "." if i < 0.3 else ":" if i < 0.6 else "░"
                        cell = (chx, dim(mix(a, b, 0.5 + 0.5 * math.sin(u + y * 0.1)), 0.16 + 0.22 * i))
                row.append(cell)
            self.neb.append(row)
        self.ents = [e for e in self.ents if not isinstance(e, AstroCat)]
        for k in range(max(2 if W * H > 6000 else 1, W // 80)):
            self.add(AstroCat(self, k * 3))

    def direct(self):
        t, nx = self.t, self.next

        def due(name, lo, hi):
            if t >= nx[name]:
                nx[name] = t + U(lo, hi)
                return True
            return False

        if due("comet", 0.3, 1.8):
            self.add(Comet(self))
        if due("shower", 40, 70):
            self.shower_until = t + 3.5
        if t < self.shower_until and due("shower_comet", 0.06, 0.22):  # meteor shower
            self.add(Comet(self))
        if due("banner", 28, 45):
            self.add(TowUfo(self, "SPACE CATS" if t < 2 else None))
        if due("planet", 4, 10) and self.H >= 20:
            if any(isinstance(e, Planet) and not e.moon for e in self.ents):
                nx["planet"] = t + 3
            else:
                p = Planet(self)
                if t < 1:
                    p.x = self.W * 0.72
                self.add(p)
        if due("rocket", 14, 26):
            self.add(RocketCat(self))
        if due("const", 30, 50):
            self.add(Constellation(self))
        if due("ufo", 30, 48):
            floating = [c for c in self.cats if c.state == "float"]
            if floating and random.random() < 0.5:  # abduct a cat instead of a fish
                self.add(UfoCat(self, "cat", random.choice(floating)))
            else:
                self.add(UfoCat(self))
        if due("runner", 24, 40):
            runner = Runner(self)
            self.add(runner)
            if random.random() < 0.5:  # a saucer lies in wait for the ball
                thief = UfoCat(self, "ball", runner)
                if 4 < thief.x0 < self.W - 28:
                    self.add(thief)
        if due("box", 70, 110) and not self.has(Box):
            self.add(Box(self))
        if due("moon", 80, 120) and self.H >= 24 and not any(isinstance(e, Planet) and e.moon for e in self.ents):
            self.add(Planet(self, moon=True))
        if due("cuke", 70, 120):
            free = [c for c in self.cats if c.free()]
            if free:
                self.add(Cucumber(self, random.choice(free)))
        if due("mouse", 80, 130) and not self.has(MouseShip):
            self.add(MouseShip(self))
        if due("yarn", 90, 140) and not self.has(Yarn):
            self.add(Yarn(self))
        if due("sat", 110, 170) and not self.has(Satellite):
            self.add(Satellite(self))
        if due("pulsar", 60, 95) and not any(isinstance(e, Pulsar) for e in self.ents):
            self.add(Pulsar(self))
        if due("hole", 40, 65) and not self.holes:
            self.add(BlackHole(self))
        if due("warp", 20, 34):
            self.warp_until = t + 5.0

    def step(self, dt):
        self.update(dt)
        self.draw()

    def update(self, dt):
        """Advance the simulation. Uses the global RNG, so every instance sharing a seed stays in lockstep."""
        self.t += dt
        self.cats = [e for e in self.ents if isinstance(e, AstroCat)]
        self.ships = [e for e in self.ents if isinstance(e, (RocketCat, TowUfo))]
        self.holes = [e for e in self.ents if isinstance(e, BlackHole)]
        self.direct()
        target = 1.0 if self.t < self.warp_until else 0.0
        self.warp += (target - self.warp) * min(1.0, dt * 2.5)
        boost = 1 + self.warp * 18
        self.neb_off += dt * 1.2 * (1 + self.warp * 30)
        if self.warp > 0.25:  # speed lines whipping past
            for _ in range(max(1, self.W // 45)):
                if random.random() < self.warp:
                    w_col = random.choice(self.pal)
                    self.add(Particle(U(self.W * 0.3, self.W * 1.3), U(0, self.H), -U(140, 260), 0, U(0.25, 0.6),
                                      "━━──--", [WHITE, mix(w_col, (150, 200, 255), 0.5), (0, 0, 0)]))
        for st in self.stars:
            st[0] = (st[0] - (2, 5, 11)[st[2]] * boost * dt) % self.W
        out = any(isinstance(e, Pulsar) and e.strength() > 0.15 for e in self.ents)
        if out and not self.shades:  # pulsar just came out: shades on, with commentary
            for e in self.ents:
                if isinstance(e, AstroCat) and e.state == "float":
                    e.say(self, COOL)
        self.shades = out
        for e in list(self.ents):
            e.update(self, dt)
        self.cat_bumps()
        self.cat_bats()
        self.ents = [e for e in self.ents if not e.dead]

    def has(self, kind):
        return any(isinstance(e, kind) for e in self.ents)

    def sparks(self, x, y, col, n=8):
        for _ in range(n):
            self.add(Particle(x, y, U(-12, 12), U(-6, 6), U(0.3, 0.8), "✦*+·.", [WHITE, col, (0, 0, 0)]))

    def cat_bumps(self):
        """Floating cats that drift into each other bounce apart, or now and then hold paws for a while."""
        cats = [c for c in self.cats if c.free()]
        for i, a in enumerate(cats):
            for b in cats[i + 1:]:
                if a.buddy is b or a.bump_cd > 0 or b.bump_cd > 0:
                    continue
                dx, dy = b.x - a.x, (b.y - a.y) * 2
                d = math.hypot(dx, dy)
                if d >= 13:
                    continue
                nx, ny = (dx / d, dy / d) if d > 0.01 else (1.0, 0.0)
                a.bump_cd = b.bump_cd = 3.0
                idle = all(c.state == "float" and c.buddy is None and c.target is None for c in (a, b))
                if idle and random.random() < 0.35:
                    lead, tail = (a, b) if a.x <= b.x else (b, a)
                    lead.disturb()
                    tail.disturb()
                    lead.buddy, tail.buddy = tail, lead
                    lead.lead, tail.lead = True, False
                    lead.buddy_t = tail.buddy_t = U(12, 20)
                    tail.say(self, FRIEND)
                else:
                    a.vx -= nx * 7
                    a.vy -= ny * 3.5
                    b.vx += nx * 7
                    b.vy += ny * 3.5
                    for c in (a, b):
                        if c.state == "nap":
                            c.state, c.nap_at = "float", U(14, 28)
                        c.calm = 0.0
                    random.choice((a, b)).say(self, BUMP)
                    self.sparks((a.x + b.x) / 2 + 7, (a.y + b.y) / 2 + 4.5, a.tail)

    def cat_bats(self):
        """A floating cat swats at a shooting star or the runner's ball that comes within reach."""
        cats = [c for c in self.cats if c.state == "float" and c.swat <= 0]
        if not cats:
            return
        for e in self.ents:
            star = isinstance(e, Comet)
            if e.dead or not (star and not e.batted or isinstance(e, Ball) and e.mode == "lead" and e.cd <= 0):
                continue
            for c in cats:
                cx, cy = c.center()
                if abs(e.x - cx) < 9 and abs(e.y - cy) < 5:
                    if star:
                        e.batted = True
                        if random.random() > 0.35:
                            break  # missed it
                        e.vx, e.vy = abs(e.vx) * U(0.5, 1.1), -abs(e.vy) * U(0.6, 1.3)
                        col = e.col
                    else:
                        e.bat(self, random.choice((-1, 1)) * U(10, 25), random.choice((-1, 1)) * U(8, 14))
                        col = e.RED
                    c.swat, c.calm = 0.4, 0.0
                    self.add(Flash(e.x, e.y, 6, col, 0.3, 0.9))
                    self.sparks(e.x, e.y, col)
                    if random.random() < 0.5:
                        c.say(self, BAP)
                    break

    def draw(self):
        rng_state = random.getstate()  # draw-time noise must not disturb the shared simulation
        s, W, H, t, warp = self.scr, self.W, self.H, self.t, self.warp
        s.clear()
        self.lights = []
        off = int(self.neb_off)
        tw = self.tw
        for y in range(H):
            nrow, crow, korow = self.neb[y], s.ch[y], s.co[y]
            for x in range(W):
                c = nrow[(x + off) % tw]
                if c:
                    crow[x], korow[x] = c
        for st in self.stars:
            layer = st[2]
            b =(0.4, 0.65, 1.0)[layer] * (0.6 + 0.4 * math.sin(t * st[6] + st[5]))
            n = 1 + int(warp * (layer + 1) * 6)
            if n == 1:
                s.put(st[0], st[1], st[3], dim(st[4], b))
            else:
                for k in range(n):
                    s.put(st[0] + k, st[1], "─", dim(mix(st[4], (150, 200, 255), warp * 0.6), (b + 0.35) * (1 - k / n)))
        for e in sorted(self.ents, key=lambda e: e.z):
            e.draw(self, s)
        self.light_pass()
        random.setstate(rng_state)

    def light_pass(self):
        """Tint everything already drawn by the nearby lights (soft falloff; rows count double)."""
        s = self.scr
        ch, co, W, H = s.ch, s.co, self.W, self.H
        for lx, ly, r, col, power, *edge in self.lights:  # optional edge: nothing right of that column is lit
            if r < 1 or power <= 0.02:
                continue
            x_hi = min(W - 1, int(lx + 2 * r), int(edge[0])) if edge else min(W - 1, int(lx + 2 * r))
            r2 = r * r
            for y in range(max(0, int(ly - r)), min(H - 1, int(ly + r)) + 1):
                dy2 = (y - ly) ** 2
                row, crow = ch[y], co[y]
                for x in range(max(0, int(lx - 2 * r)), x_hi + 1):
                    if row[x] == " ":
                        continue
                    d2 = ((x - lx) * 0.5) ** 2 + dy2
                    if d2 < r2:
                        f = 1 - d2 / r2
                        crow[x] = lit(crow[x], col, f * f * power)


# ────────────────────────────────── main ──────────────────────────────────

def term_size():
    try:
        c, r = os.get_terminal_size(sys.stdout.fileno())
        return max(c, 20), max(r, 8)
    except OSError:
        return 80, 24


def hypr_monitors():
    """{name: (x, y, logical_w, logical_h)} from Hyprland, or {} if unavailable."""
    import json
    import subprocess
    try:
        mons = json.loads(subprocess.run(["hyprctl", "monitors", "-j"], capture_output=True, text=True, timeout=2).stdout)
        geo = {}
        for m in mons:
            mw, mh, sc = m["width"], m["height"], m.get("scale") or 1
            if m.get("transform", 0) % 2:
                mw, mh = mh, mw
            geo[m["name"]] = (m["x"], m["y"], mw / sc, mh / sc)
        return geo
    except Exception:
        return {}


RUN_DIR = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "space-cats")


def write_atomic(path, text, exclusive=False):
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w") as f:
        f.write(text)
    try:
        if exclusive:
            os.link(tmp, path)  # fails if another window got there first
        else:
            os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def shared_run(mon, size, geo):
    """Join this launch's shared run. Returns (start_time, seed, canvas_w, canvas_h, x0, y0).

    The first window publishes the clock and seed; every window publishes its real terminal size,
    then waits until all monitors have reported. Everyone ends up with the identical canvas, laid out
    from the real column/row counts, so the slices meet edge to edge and show one scene.
    """
    os.makedirs(RUN_DIR, exist_ok=True)
    epoch_file = os.path.join(RUN_DIR, "epoch")
    ep = seed = None
    for _ in range(20):
        try:
            with open(epoch_file) as f:
                ep, seed = f.read().split()
            ep, seed = float(ep), int(seed)
            if time.time() - ep < 20:  # older = leftover from a crashed run
                break
            for n in os.listdir(RUN_DIR):
                os.unlink(os.path.join(RUN_DIR, n))
        except (OSError, ValueError):
            pass
        try:
            write_atomic(epoch_file, "%r %d" % (time.time(), random.randrange(1 << 30)), exclusive=True)
        except OSError:
            time.sleep(0.05)
        ep = None
    if ep is None:
        ep, seed = time.time(), 1
    write_atomic(os.path.join(RUN_DIR, "mon-" + mon), "%d %d" % size)

    sizes = {}
    deadline = ep + 8  # the launcher opens windows one by one; don't wait forever on one that never comes
    while True:
        for name in geo:
            try:
                with open(os.path.join(RUN_DIR, "mon-" + name)) as f:
                    c, r = f.read().split()
                sizes[name] = (int(c), int(r))
            except (OSError, ValueError):
                pass
        if len(sizes) == len(geo) or time.time() > deadline:
            break
        time.sleep(0.05)
    lw, lh = geo[mon][2:]
    for name, g in geo.items():  # estimate any monitor that never reported, from this window's cell size
        sizes.setdefault(name, (round(g[2] * size[0] / lw), round(g[3] * size[1] / lh)))

    def origin(name):
        x, y = geo[name][:2]
        x0 = sum(sizes[k][0] for k, g in geo.items() if g[0] + g[2] <= x)  # monitors fully to the left
        y0 = sum(sizes[k][1] for k, g in geo.items() if g[1] + g[3] <= y)  # monitors fully above
        return x0, y0

    cw = max(origin(k)[0] + sizes[k][0] for k in geo)
    ch = max(origin(k)[1] + sizes[k][1] for k in geo)
    return (ep, seed, cw, ch) + origin(mon)


def main():
    test = os.environ.get("SPACECATS_TEST")  # "WxH:frames" -> print one plain frame and exit
    if test:
        size, frames = test.split(":")
        W, H = map(int, size.split("x"))
        w = World(W, H)
        for _ in range(int(frames)):
            w.step(1 / FPS)
        w.scr.render()
        print("\n".join("".join(r) for r in w.scr.ch))
        return

    stop = []
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT):
        signal.signal(sig, lambda *_: stop.append(1))

    mon = sys.argv[1] if len(sys.argv) > 1 else None  # monitor name, passed in by the launcher
    old = None
    keys = sys.stdin.isatty()
    if keys:
        import termios
        import tty
        old = termios.tcgetattr(sys.stdin)
        tty.setcbreak(sys.stdin)
    out = sys.stdout
    out.write("\x1b[?1049h\x1b[?25l\x1b[?7l\x1b]11;rgb:00/00/00\x07\x1b[2J")
    try:
        # Terminals start at 80x24 and only resize once the compositor sizes the window.
        deadline = time.time() + 2
        while term_size() == (80, 24) and time.time() < deadline:
            time.sleep(0.02)

        cols, rows = term_size()
        geo = hypr_monitors() if mon else {}
        if mon in geo and len(geo) > 1:
            epoch, seed, vw, vh, x0, y0 = shared_run(mon, (cols, rows), geo)
        else:
            epoch, seed, vw, vh, x0, y0 = time.time(), random.randrange(1 << 30), cols, rows, 0, 0
        random.seed(seed)
        w = World(vw, vh)
        steps = 0
        while not stop:
            if term_size() != (cols, rows):  # keep the shared world; just show more or less of our slice
                cols, rows = term_size()
                out.write("\x1b[2J")
            due = int((time.time() - epoch) * FPS)
            if due > steps:  # catch up on fixed-size steps so every window computes the identical world
                for _ in range(min(due - steps, 120)):
                    w.update(1 / FPS)
                    steps += 1
                if due - steps > 1:
                    continue  # still far behind (late start): keep simulating, draw once caught up
            w.draw()
            out.write(w.scr.render(x0, cols, y0, rows))
            out.flush()
            wait = max(0.0, epoch + (steps + 1) / FPS - time.time())  # tick on the shared clock
            if keys:
                if select.select([sys.stdin], [], [], wait)[0]:
                    break
            else:
                time.sleep(wait)
    except (BrokenPipeError, OSError):
        pass
    finally:
        try:
            out.write("\x1b[0m\x1b[?7h\x1b[?25h\x1b[?1049l\x1b]111\x07")
            out.flush()
        except (BrokenPipeError, OSError):
            pass
        if old:
            import termios
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old)


if __name__ == "__main__":
    main()
