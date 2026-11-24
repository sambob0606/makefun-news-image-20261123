#!/usr/bin/env python3
"""News in one image: Monday 23 November 2026.

A pure-stdlib Python program. It draws a newspaper front page that sums
up the day's world news -- one hero story, five more stories in a grid,
and a ticker of the rest -- and writes it as a deterministic 1024x1024
PNG to the output directory. No network, no files read, no randomness:
two runs produce byte-identical output.
"""

import os
import struct
import sys
import zlib

WIDTH = 1024
HEIGHT = 1024

# ---------------------------------------------------------------------------
# 5x7 bitmap font. Each glyph is seven rows; each row is a 5-bit mask whose
# most significant bit is the leftmost pixel. Only capitals are drawn: every
# string is upper-cased before rendering.
# ---------------------------------------------------------------------------

def _g(*rows):
    return tuple(int(r, 2) for r in rows)


GLYPHS = {
    "A": _g("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": _g("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": _g("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "D": _g("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": _g("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": _g("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": _g("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    "H": _g("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": _g("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "J": _g("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    "K": _g("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": _g("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": _g("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": _g("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": _g("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": _g("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": _g("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": _g("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": _g("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": _g("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": _g("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": _g("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": _g("10001", "10001", "10001", "10101", "10101", "10101", "01010"),
    "X": _g("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": _g("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": _g("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "0": _g("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": _g("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": _g("01110", "10001", "00001", "00110", "01000", "10000", "11111"),
    "3": _g("11111", "00010", "00100", "00010", "00001", "10001", "01110"),
    "4": _g("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": _g("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    "6": _g("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
    "7": _g("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": _g("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": _g("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
    " ": _g("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    ".": _g("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    ",": _g("00000", "00000", "00000", "00000", "01100", "00100", "01000"),
    ":": _g("00000", "01100", "01100", "00000", "01100", "01100", "00000"),
    ";": _g("00000", "01100", "01100", "00000", "01100", "00100", "01000"),
    "!": _g("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    "?": _g("01110", "10001", "00001", "00110", "00100", "00000", "00100"),
    "'": _g("00100", "00100", "01000", "00000", "00000", "00000", "00000"),
    "-": _g("00000", "00000", "00000", "01110", "00000", "00000", "00000"),
    "+": _g("00000", "00100", "00100", "11111", "00100", "00100", "00000"),
    "%": _g("11001", "11010", "00010", "00100", "01000", "01011", "10011"),
    "(": _g("00010", "00100", "01000", "01000", "01000", "00100", "00010"),
    ")": _g("01000", "00100", "00010", "00010", "00010", "00100", "01000"),
    "/": _g("00001", "00010", "00010", "00100", "01000", "01000", "10000"),
    "&": _g("01100", "10010", "10100", "01000", "10101", "10010", "01101"),
    "$": _g("00100", "01111", "10100", "01110", "00101", "11110", "00100"),
    "=": _g("00000", "00000", "11111", "00000", "11111", "00000", "00000"),
    '"': _g("01010", "01010", "00000", "00000", "00000", "00000", "00000"),
    "*": _g("00000", "10101", "01110", "11111", "01110", "10101", "00000"),
    "[": _g("01110", "01000", "01000", "01000", "01000", "01000", "01110"),
    "]": _g("01110", "00010", "00010", "00010", "00010", "00010", "01110"),
    "|": _g("00100", "00100", "00100", "00100", "00100", "00100", "00100"),
}

CHAR_W = 6   # 5 glyph columns + 1 spacing column
CHAR_H = 7


def text_width(text, scale):
    return len(text) * CHAR_W * scale - scale


def wrap_text(text, scale, max_width):
    """Greedy word wrap; returns a list of lines that fit max_width."""
    words = text.upper().split()
    lines = []
    current = ""
    for word in words:
        trial = word if not current else current + " " + word
        if text_width(trial, scale) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


# ---------------------------------------------------------------------------
# PNG writer: 8-bit RGB, no interlace, filter 0 on every scanline.
# ---------------------------------------------------------------------------

def _chunk(kind, payload):
    out = struct.pack(">I", len(payload)) + kind + payload
    return out + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)


def encode_png(pixels, width, height):
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = bytearray()
    stride = width * 3
    for y in range(height):
        raw.append(0)
        raw += pixels[y * stride:(y + 1) * stride]
    blob = b"\x89PNG\r\n\x1a\n"
    blob += _chunk(b"IHDR", ihdr)
    blob += _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    blob += _chunk(b"IEND", b"")
    return blob


# ---------------------------------------------------------------------------
# Sheet: an RGB canvas with filled shapes, outlines, lines and text.
# ---------------------------------------------------------------------------

class Sheet:
    def __init__(self, width, height, background):
        self.width = width
        self.height = height
        self.buf = bytearray(background * (width * height))

    def put(self, x, y, color):
        if 0 <= x < self.width and 0 <= y < self.height:
            i = (y * self.width + x) * 3
            self.buf[i:i + 3] = color

    def fill(self, x0, y0, x1, y1, color):
        x0 = max(0, x0)
        y0 = max(0, y0)
        x1 = min(self.width, x1)
        y1 = min(self.height, y1)
        for y in range(y0, y1):
            base = (y * self.width + x0) * 3
            self.buf[base:base + (x1 - x0) * 3] = color * (x1 - x0)

    def hline(self, x0, x1, y, color, thick=1):
        for t in range(thick):
            for x in range(x0, x1):
                self.put(x, y + t, color)

    def vline(self, x, y0, y1, color, thick=1):
        for t in range(thick):
            for y in range(y0, y1):
                self.put(x + t, y, color)

    def line(self, x0, y0, x1, y1, color, thick=1):
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        x, y = x0, y0
        while True:
            for a in range(thick):
                for b in range(thick):
                    self.put(x + a, y + b, color)
            if x == x1 and y == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x += sx
            if e2 <= dx:
                err += dx
                y += sy

    def frame(self, x0, y0, x1, y1, color, thick=2):
        self.hline(x0, x1, y0, color, thick)
        self.hline(x0, x1, y1 - thick, color, thick)
        self.vline(x0, y0, y1, color, thick)
        self.vline(x1 - thick, y0, y1, color, thick)

    def disc(self, cx, cy, r, color):
        for y in range(cy - r, cy + r + 1):
            for x in range(cx - r, cx + r + 1):
                if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                    self.put(x, y, color)

    def ring(self, cx, cy, r, color, thick=3):
        for y in range(cy - r - thick, cy + r + thick + 1):
            for x in range(cx - r - thick, cx + r + thick + 1):
                d2 = (x - cx) ** 2 + (y - cy) ** 2
                if (r - thick) ** 2 <= d2 <= (r + thick) ** 2:
                    self.put(x, y, color)

    def poly(self, points, color):
        """Scanline fill of a simple polygon (even-odd rule)."""
        if len(points) < 3:
            return
        top = min(p[1] for p in points)
        bottom = max(p[1] for p in points)
        n = len(points)
        for y in range(top, bottom + 1):
            hits = []
            for i in range(n):
                x0, y0 = points[i]
                x1, y1 = points[(i + 1) % n]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    t = (y - y0) / (y1 - y0)
                    hits.append(x0 + t * (x1 - x0))
            hits.sort()
            for k in range(0, len(hits) - 1, 2):
                for x in range(int(hits[k]), int(hits[k + 1]) + 1):
                    self.put(x, y, color)

    def glyph(self, x, y, char, scale, color):
        rows = GLYPHS.get(char, GLYPHS["?"])
        for r in range(CHAR_H):
            bits = rows[r]
            for c in range(5):
                if bits & (1 << (4 - c)):
                    self.fill(x + c * scale, y + r * scale,
                              x + (c + 1) * scale, y + (r + 1) * scale,
                              color)

    def text(self, x, y, string, scale, color):
        for i, ch in enumerate(string.upper()):
            self.glyph(x + i * CHAR_W * scale, y, ch, scale, color)

    def centred(self, cx, y, string, scale, color):
        self.text(cx - text_width(string, scale) // 2, y, string, scale, color)

    def paragraph(self, x, y, string, scale, color, max_width, leading=None):
        if leading is None:
            leading = CHAR_H * scale + 4 * scale // 2
        for line in wrap_text(string, scale, max_width):
            self.text(x, y, line, scale, color)
            y += leading
        return y

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------

PAPER = bytes((247, 243, 234))
INK = bytes((22, 33, 61))
NAVY = bytes((22, 33, 61))
GOLD = bytes((212, 160, 60))
WHITE = bytes((255, 255, 255))
GREEN = bytes((22, 120, 70))
GREEN_SOFT = bytes((220, 240, 228))
BLUE = bytes((38, 90, 160))
BLUE_SOFT = bytes((222, 234, 248))
RED = bytes((178, 44, 36))
RED_SOFT = bytes((248, 226, 222))
GREY = bytes((90, 96, 110))
LIGHT_GREY = bytes((228, 226, 218))
TEAL = bytes((16, 110, 110))
TEAL_SOFT = bytes((216, 238, 238))
ORANGE = bytes((196, 106, 28))
ORANGE_SOFT = bytes((250, 232, 214))


# ---------------------------------------------------------------------------
# Icons: small geometric drawings, one per story.
# ---------------------------------------------------------------------------

def icon_chip(s, cx, cy, size):
    """A processor chip: square body, gold pins, green core."""
    half = size // 2
    s.fill(cx - half, cy - half, cx + half, cy + half, NAVY)
    s.fill(cx - half + 12, cy - half + 12, cx + half - 12, cy + half - 12,
           GREEN)
    s.frame(cx - half + 24, cy - half + 24, cx + half - 24, cy + half - 24,
            GOLD, 4)
    for k in range(-1, 2):
        off = k * size // 4
        s.fill(cx + off - 4, cy - half - 12, cx + off + 4, cy - half, GOLD)
        s.fill(cx + off - 4, cy + half, cx + off + 4, cy + half + 12, GOLD)
        s.fill(cx - half - 12, cy + off - 4, cx - half, cy + off + 4, GOLD)
        s.fill(cx + half, cy + off - 4, cx + half + 12, cy + off + 4, GOLD)
    s.text(cx - text_width("AI", 4) // 2, cy - 14, "AI", 4, WHITE)


def icon_globe_slash(s, cx, cy, size):
    """Earth with a red slash across it: the climate deal that failed."""
    r = size // 2
    s.disc(cx, cy, r, BLUE)
    s.ring(cx, cy, r - 6, BLUE_SOFT, 4)
    s.line(cx - r + 14, cy - 6, cx + r - 20, cy - 2, BLUE_SOFT, 5)
    s.line(cx - r + 18, cy + 14, cx + r - 14, cy + 18, BLUE_SOFT, 5)
    s.line(cx - r - 6, cy + r + 4, cx + r + 6, cy - r - 4, RED, 12)


def icon_ship(s, cx, cy, size):
    """A warship on waves: hull, mast, radar, sea lines."""
    half = size // 2
    s.poly([(cx - half, cy + 6), (cx + half - 8, cy + 6),
            (cx + half - 26, cy + 26), (cx - half + 14, cy + 26)], NAVY)
    s.vline(cx - 6, cy - half + 6, cy + 6, NAVY, 5)
    s.hline(cx - 26, cx + 14, cy - half + 14, NAVY, 5)
    s.disc(cx - 6, cy - half + 2, 8, RED)
    for k, yy in enumerate((cy + 38, cy + 48, cy + 58)):
        s.hline(cx - half + 6 + k * 8, cx + half - 6 - k * 4, yy, BLUE, 4)


def icon_radar_plane(s, cx, cy, size):
    """An AWACS early-warning jet: fuselage, swept wings, radar dome."""
    half = size // 2
    s.poly([(cx - half + 6, cy + 2), (cx + half - 4, cy - 6),
            (cx + half + 6, cy + 2), (cx + half - 4, cy + 10),
            (cx - half + 6, cy + 10)], NAVY)
    s.poly([(cx - 12, cy + 8), (cx + 26, cy + 34), (cx + 8, cy + 34),
            (cx - 26, cy + 10)], NAVY)
    s.poly([(cx - 4, cy - 4), (cx + 20, cy - 30), (cx + 34, cy - 28),
            (cx + 12, cy - 2)], NAVY)
    s.disc(cx + 2, cy - 22, 13, RED)
    s.line(cx + 2, cy - 9, cx + 2, cy - 2, NAVY, 4)


def icon_barrel(s, cx, cy, size):
    """An oil barrel stamped with a dollar sign: sanctions on oil money."""
    half = size // 2
    w = size - 28
    s.fill(cx - w // 2, cy - half + 6, cx + w // 2, cy + half - 6, INK)
    s.hline(cx - w // 2, cx + w // 2, cy - half + 22, GOLD, 6)
    s.hline(cx - w // 2, cx + w // 2, cy + half - 28, GOLD, 6)
    s.text(cx - text_width("$", 5) // 2, cy - 18, "$", 5, GOLD)


def icon_capitol(s, cx, cy, size):
    """A capitol dome on columns: the House majority."""
    half = size // 2
    s.poly([(cx - half + 8, cy - 6), (cx, cy - half + 2),
            (cx + half - 8, cy - 6)], NAVY)
    s.fill(cx - half + 8, cy - 6, cx + half - 8, cy + 2, NAVY)
    for k in range(-2, 3):
        s.vline(cx + k * 22, cy + 6, cy + half - 12, NAVY, 6)
    s.hline(cx - half, cx + half, cy + half - 12, NAVY, 6)
    s.fill(cx - half - 4, cy + half - 6, cx + half + 4, cy + half + 2, RED)


# ---------------------------------------------------------------------------
# Story panels
# ---------------------------------------------------------------------------

def kicker_bar(s, x, y, w, color):
    s.fill(x, y, x + w, y + 6, color)


def story_panel(s, x, y, w, h, accent, soft, kicker, headline,
                 body, icon=None, head_scale=3, body_scale=2):
    s.fill(x, y, x + w, y + h, WHITE)
    s.frame(x, y, x + w, y + h, INK, 2)
    kicker_bar(s, x + 2, y + 2, w - 4, accent)
    pad = 18
    ty = y + 20
    s.text(x + pad, ty, kicker, 2, accent)
    ty += 26
    if icon is not None:
        icon(s, x + w - 62, ty + 34, 84)
        head_w = w - pad * 2 - 110
    else:
        head_w = w - pad * 2
    for line in wrap_text(headline, head_scale, head_w):
        s.text(x + pad, ty, line, head_scale, INK)
        ty += CHAR_H * head_scale + 5
    ty += 6
    # Body text keeps clear of the icon column when one is drawn.
    s.paragraph(x + pad, ty, body, body_scale, GREY, head_w,
                leading=CHAR_H * body_scale + 6)


# ---------------------------------------------------------------------------
# The day's news, as reported on Monday 23 November 2026.
# ---------------------------------------------------------------------------

HERO = {
    "kicker": "BUSINESS - MARKETS",
    "headline": "HUANG IS BACK",
    "sub": "NVIDIA BOARD REINSTATES JENSEN HUANG AS CEO",
    "body": ("Shares jump about 30 percent as the board reverses course. "
             "Trump says he assured the board Huang poses no national "
             "security threat, ending a boardroom standoff that had "
             "rattled the chip giant."),
}

STORIES = [
    {
        "accent": RED, "soft": RED_SOFT,
        "kicker": "CLIMATE - ANTALYA",
        "headline": "COP31 FALLOUT: BLAME GAME BEGINS",
        "body": ("A day after UN climate talks collapse with no deal, "
                 "the blame game begins. Australia is under fire and "
                 "Pacific island nations voice despair."),
        "icon": icon_globe_slash,
    },
    {
        "accent": NAVY, "soft": BLUE_SOFT,
        "kicker": "WAR AT SEA",
        "headline": "UKRAINE SINKS RUSSIAN WARSHIP",
        "body": ("Kyiv says its sea drones sank the Russian corvette "
                 "Merkury in a Libyan port. The war at sea spreads "
                 "beyond Europe."),
        "icon": icon_ship,
    },
    {
        "accent": TEAL, "soft": TEAL_SOFT,
        "kicker": "NATO - EASTERN FLANK",
        "headline": "AWACS TO POLAND",
        "body": ("Early-warning jets deploy after three Russian missiles "
                 "land in Poland."),
    },
    {
        "accent": ORANGE, "soft": ORANGE_SOFT,
        "kicker": "IRAN - SANCTIONS",
        "headline": "IRAN DEFIES US BLOCKADE",
        "body": ("Tehran vows to defy the US naval blockade as "
                 "Washington sanctions dozens over shadow banking."),
        "icon": icon_barrel,
    },
    {
        "accent": GREEN, "soft": GREEN_SOFT,
        "kicker": "US MIDTERMS",
        "headline": "DEMOCRATS TAKE THE HOUSE",
        "body": ("Democrats win at least 258 seats in preliminary 2026 "
                 "calls, a historic House majority."),
        "icon": icon_capitol,
    },
]

TICKER = ("FBI PROBES HACK OF ITS CRIME DATABASE  |  MEXICO CAPTURES "
          "'EL CHAPO ISIDRO'  |  UK TO HOST 2035 WOMEN'S WORLD CUP  |  "
          "SKUBAL AGREES $450M METS DEAL, A RECORD FOR A PITCHER")


def compose():
    s = Sheet(WIDTH, HEIGHT, PAPER)

    # Masthead.
    s.fill(0, 0, WIDTH, 108, NAVY)
    s.centred(WIDTH // 2, 16, "THE WORLD IN ONE DAY", 5, WHITE)
    s.hline(212, WIDTH - 212, 72, GOLD, 3)
    s.centred(WIDTH // 2, 82, "MONDAY 23 NOVEMBER 2026", 3, GOLD)

    # Hero story: Nvidia.
    hx, hy, hw, hh = 24, 120, 976, 284
    s.fill(hx, hy, hx + hw, hy + hh, WHITE)
    s.frame(hx, hy, hx + hw, hy + hh, INK, 2)
    s.fill(hx + 2, hy + 2, hx + 14, hy + hh - 2, GREEN)
    tx = hx + 36
    ty = hy + 22
    s.text(tx, ty, HERO["kicker"], 2, GREEN)
    ty += 30
    s.text(tx, ty, HERO["headline"], 6, INK)
    ty += CHAR_H * 6 + 12
    for line in wrap_text(HERO["sub"], 3, 560):
        s.text(tx, ty, line, 3, NAVY)
        ty += CHAR_H * 3 + 5
    ty += 8
    s.paragraph(tx, ty, HERO["body"], 2, GREY, 560,
                leading=CHAR_H * 2 + 7)
    # Chip artwork on the right of the hero.
    s.fill(hx + 640, hy + 24, hx + hw - 24, hy + hh - 24, GREEN_SOFT)
    s.frame(hx + 640, hy + 24, hx + hw - 24, hy + hh - 24, GREEN, 2)
    icon_chip(s, hx + 800, hy + hh // 2 - 14, 140)
    s.centred(hx + 800, hy + hh - 58, "SHARES +30%", 3, GREEN)

    # Second row: two wide panels.
    row2_y, row2_h = 416, 232
    story_panel(s, 24, row2_y, 476, row2_h,
                STORIES[0]["accent"], STORIES[0]["soft"],
                STORIES[0]["kicker"], STORIES[0]["headline"],
                STORIES[0]["body"], icon=STORIES[0]["icon"])
    story_panel(s, 524, row2_y, 476, row2_h,
                STORIES[1]["accent"], STORIES[1]["soft"],
                STORIES[1]["kicker"], STORIES[1]["headline"],
                STORIES[1]["body"], icon=STORIES[1]["icon"])

    # Third row: three panels.
    row3_y, row3_h = 660, 232
    xs = (24, 348, 688)
    ws = (312, 328, 312)
    for i, x, w in zip(range(2, 5), xs, ws):
        st = STORIES[i]
        # Row 3 is narrow: no icon, so headlines and bodies get full width.
        story_panel(s, x, row3_y, w, row3_h,
                    st["accent"], st["soft"], st["kicker"],
                    st["headline"], st["body"],
                    head_scale=3, body_scale=2)

    # Footer ticker.
    fy = 904
    s.fill(0, fy, WIDTH, HEIGHT, NAVY)
    s.text(24, fy + 16, "ALSO ON MONDAY", 2, GOLD)
    s.paragraph(24, fy + 44, TICKER, 2, WHITE, WIDTH - 48,
                leading=CHAR_H * 2 + 8)
    return s


def main(argv):
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    sheet = compose()
    data = encode_png(sheet.buf, WIDTH, HEIGHT)
    path = os.path.join(out_dir, "entry.png")
    with open(path, "wb") as fh:
        fh.write(data)
    print(f"wrote {path} ({len(data)} bytes, {WIDTH}x{HEIGHT})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
