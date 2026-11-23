#!/usr/bin/python3
"""Render a Space Cats GIF offscreen, for the README. Nothing is drawn on your screen.

Runs the simulation headlessly, paints each frame's characters onto an image with a monospace
font, and stitches the frames into a GIF with ffmpeg. Needs Pillow and ffmpeg (dev-only; the
screensaver itself needs neither).

    tools/render-gif.py                     # writes docs/space-cats.gif
    tools/render-gif.py --seed 3 --secs 24  # try another take
"""
import argparse
import importlib.util
import os
import random
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = "/usr/share/fonts/TTF/JetBrainsMonoNerdFont-Regular.ttf"  # Omarchy's default terminal font
FALLBACK = "/usr/share/fonts/Adwaita/AdwaitaMono-Regular.ttf"   # for glyphs it lacks, like ✦

# A calm highlight reel (seconds from start): a few set pieces with room to breathe. Everything
# else is pushed past the end. The screensaver itself is unaffected.
NEVER = 1e9
SCHEDULE = {"planet": 0.0, "banner": 0.5, "rocket": 4.0, "runner": 11.0, "hole": 15.0, "pulsar": 21.0,
            "warp": NEVER, "ufo": NEVER, "box": NEVER, "mouse": NEVER, "yarn": NEVER, "cuke": NEVER,
            "sat": NEVER, "moon": NEVER, "shower": NEVER, "const": NEVER}


def load_sim():
    spec = importlib.util.spec_from_file_location("space_cats", os.path.join(ROOT, "space-cats.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Painter:
    """Paints a character grid the way a truecolor terminal would."""

    def __init__(self, cols, rows, size):
        self.font = ImageFont.truetype(FONT, size)
        self.fallback = ImageFont.truetype(FALLBACK, size) if os.path.exists(FALLBACK) else None
        asc, desc = self.font.getmetrics()
        self.cw = round(self.font.getlength("M"))
        self.chh = asc + desc
        self.cols, self.rows = cols, rows
        self.glyphs = {}
        self.fonts = {}
        self.notdef = self.ink(self.font, "\U0010fffd")  # what a missing glyph looks like

    def ink(self, font, ch):
        img = Image.new("L", (self.cw * 2, self.chh))
        ImageDraw.Draw(img).text((0, 0), ch, font=font, fill=255)
        return img.tobytes()

    def font_for(self, ch):
        """Like a terminal: use the main font unless it lacks the glyph."""
        f = self.fonts.get(ch)
        if f is None:
            missing = self.fallback and self.ink(self.font, ch) == self.notdef
            f = self.fonts[ch] = self.fallback if missing else self.font
        return f

    def glyph(self, ch, col):
        """Pre-rendered glyph tile (RGBA) for a character in a colour."""
        key = (ch, col)
        g = self.glyphs.get(key)
        if g is None:
            if len(self.glyphs) > 20000:
                self.glyphs.clear()
            g = Image.new("RGBA", (self.cw, self.chh), (0, 0, 0, 0))
            ImageDraw.Draw(g).text((0, 0), ch, font=self.font_for(ch), fill=col + (255,))
            self.glyphs[key] = g
        return g

    def frame(self, ch, co):
        cw, chh = self.cw, self.chh
        img = Image.new("RGB", (self.cols * cw, self.rows * chh), (0, 0, 0))
        d = ImageDraw.Draw(img)
        half = chh // 2
        for y in range(self.rows):
            row, crow = ch[y], co[y]
            py = y * chh
            for x in range(self.cols):
                c = row[x]
                if c == " ":
                    continue
                k = crow[x]
                fg, bg = (k[:3], k[3:]) if len(k) == 6 else (k, None)
                px = x * cw
                if bg is not None:
                    d.rectangle((px, py, px + cw - 1, py + chh - 1), fill=bg)
                # Block elements are drawn as exact rectangles so they tile without gaps.
                if c == "█":
                    d.rectangle((px, py, px + cw - 1, py + chh - 1), fill=fg)
                elif c == "▀":
                    d.rectangle((px, py, px + cw - 1, py + half - 1), fill=fg)
                elif c == "▄":
                    d.rectangle((px, py + half, px + cw - 1, py + chh - 1), fill=fg)
                elif c == "▌":
                    d.rectangle((px, py, px + cw // 2 - 1, py + chh - 1), fill=fg)
                elif c == "▐":
                    d.rectangle((px + cw // 2, py, px + cw - 1, py + chh - 1), fill=fg)
                else:
                    img.paste(self.glyph(c, tuple(fg)), (px, py), self.glyph(c, tuple(fg)))
        return img


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cols", type=int, default=180)
    ap.add_argument("--rows", type=int, default=34)
    ap.add_argument("--font-size", type=int, default=12)
    ap.add_argument("--secs", type=float, default=26)
    ap.add_argument("--fps", type=int, default=12, help="GIF frame rate (the simulation always runs at 30)")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "space-cats.gif"))
    a = ap.parse_args()
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg is required")

    sim = load_sim()
    random.seed(a.seed)
    world = sim.World(a.cols, a.rows)
    for name, at in SCHEDULE.items():
        if name in world.next:
            world.next[name] = at
    painter = Painter(a.cols, a.rows, a.font_size)

    tmp = tempfile.mkdtemp(prefix="space-cats-gif-")
    try:
        n = 0
        steps = 0
        while n < int(a.secs * a.fps):  # one GIF frame per 1/fps seconds of simulated time
            while steps < round(n * sim.FPS / a.fps):
                world.update(1 / sim.FPS)
                steps += 1
            world.draw()
            painter.frame(world.scr.ch, world.scr.co).save(os.path.join(tmp, "f%05d.png" % n))
            n += 1
            if n % 50 == 0:
                print("  %d frames" % n, file=sys.stderr)
        os.makedirs(os.path.dirname(a.out), exist_ok=True)
        pal = os.path.join(tmp, "palette.png")
        src = ["-framerate", str(a.fps), "-i", os.path.join(tmp, "f%05d.png")]
        subprocess.run(["ffmpeg", "-v", "error", "-y", *src, "-vf", "palettegen=max_colors=256:stats_mode=diff", pal], check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", *src, "-i", pal, "-lavfi",
                        "paletteuse=dither=none:diff_mode=rectangle", "-loop", "0", a.out], check=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("%s: %d frames, %.1f MB" % (a.out, n, os.path.getsize(a.out) / 1e6))


if __name__ == "__main__":
    main()
