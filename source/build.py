"""Build the Contour theme for T3 Code: contour.json + SVG layers (+ the landing page from index.tpl.html)."""
import json, math, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")

PAPER = "#f3edda"
INK = "#2b2519"
SIENNA = "#b87345"      # minor contour
SIENNA_D = "#8f4a28"    # index contour
HYDRO = "#2f7396"       # water
SAGE = "#6b8a4a"        # vegetation
ORANGE = "#c0401a"      # survey orange
MONO = "ui-monospace,Menlo,monospace"
SERIF = "'Iowan Old Style',Palatino,Georgia,serif"

W, Hh = 1600, 1000
CELL = 47
DH = 0.08            # contour interval in field units (50 m)
K = 3                  # elevation frames
STEPS = [0, 1, 2, 1]   # ping-pong; each frame is held, with a short dip between
CYCLE = 15             # seconds; the hero film is 30s = 2 cycles
SKIP = (0.31, 0.69)    # centre columns stay empty: the reading column's scrim covers them


def elev(h):
    return int(round(h * 625 + 600))


# ---------------------------------------------------------------- terrain
PEAKS = [
    (190, 430, 1.00, 170, 230), (150, 150, .55, 110, 100), (100, 800, .50, 150, 140), (270, 650, .35, 110, 100),
    (1420, 330, .95, 180, 170), (1500, 800, .65, 190, 170), (1390, 90, .45, 110, 80), (1330, 650, .35, 110, 100),
]


def H(x, y):
    h = 0.0
    for cx, cy, a, sx, sy in PEAKS:
        h += a * math.exp(-(((x - cx) / sx) ** 2 + ((y - cy) / sy) ** 2))
    h += 0.05 * math.sin(x / 83 + y / 121) + 0.04 * math.sin(x / 47 - y / 71 + 1) + 0.03 * math.sin(y / 37 + x / 190)
    return h + 0.02


def contours(level, xmin=0, xmax=None):
    """Marching squares on a coarse grid -> list of polylines (lists of (x,y)); closed ones repeat the first point."""
    nx, ny = int(W / CELL) + 1, int(Hh / CELL) + 1
    v = [[H(i * CELL, j * CELL) - level for i in range(nx + 1)] for j in range(ny + 1)]
    segs = {}

    def pt(edge):
        kind, i, j = edge
        if kind == "h":  # between (i,j) and (i+1,j)
            a, b = v[j][i], v[j][i + 1]
            t = a / (a - b)
            return ((i + t) * CELL, j * CELL)
        a, b = v[j][i], v[j + 1][i]
        t = a / (a - b)
        return (i * CELL, (j + t) * CELL)

    adj = {}
    for j in range(ny):
        for i in range(nx):
            cx = (i + .5) / nx
            if SKIP[0] < cx < SKIP[1] or (xmax is not None and (i * CELL > xmax or (i + 1) * CELL < xmin)):
                continue
            c = [v[j][i] > 0, v[j][i + 1] > 0, v[j + 1][i + 1] > 0, v[j + 1][i] > 0]
            idx = c[0] * 8 + c[1] * 4 + c[2] * 2 + c[3]
            if idx in (0, 15):
                continue
            top, right, bot, left = ("h", i, j), ("v", i + 1, j), ("h", i, j + 1), ("v", i, j)
            table = {1: [(left, bot)], 2: [(bot, right)], 3: [(left, right)], 4: [(top, right)], 6: [(top, bot)], 7: [(left, top)],
                     8: [(left, top)], 9: [(top, bot)], 11: [(top, right)], 12: [(left, right)], 13: [(bot, right)], 14: [(left, bot)]}
            if idx == 5:
                pairs = [(left, top), (bot, right)]
            elif idx == 10:
                pairs = [(left, bot), (top, right)]
            else:
                pairs = table[idx]
            for a, b in pairs:
                adj.setdefault(a, []).append(b)
                adj.setdefault(b, []).append(a)
    seen = set()
    lines = []

    def walk(start, prev=None):
        path = [start]
        seen.add(start)
        cur = start
        while True:
            nxt = None
            for n in adj.get(cur, []):
                if n != prev and (n not in seen or (n == start and len(path) > 2)):
                    nxt = n
                    break
            if nxt is None:
                break
            if nxt == start:
                path.append(start)
                break
            seen.add(nxt)
            path.append(nxt)
            prev, cur = cur, nxt
        return path

    ends = [e for e, ns in adj.items() if len(ns) == 1]
    for e in ends:
        if e not in seen:
            lines.append(walk(e))
    for e in adj:
        if e not in seen:
            lines.append(walk(e))
    return [[pt(e) for e in l] for l in lines if len(l) > 3]


def num(n):
    return str(n)


def smooth_path(pts):
    """Closed/open polyline -> relative quadratic path through edge midpoints, integer coords."""
    closed = pts[0] == pts[-1]
    if closed:
        pts = pts[:-1]
        mids = [((pts[i][0] + pts[(i + 1) % len(pts)][0]) / 2, (pts[i][1] + pts[(i + 1) % len(pts)][1]) / 2) for i in range(len(pts))]
        start = (round(mids[-1][0]), round(mids[-1][1]))
        out = [f"M{start[0]} {start[1]}"]
        cur = start
        nums = []
        for i, p in enumerate(pts):
            c = (round(p[0]), round(p[1]))
            e = (round(mids[i][0]), round(mids[i][1]))
            nums += [c[0] - cur[0], c[1] - cur[1], e[0] - cur[0], e[1] - cur[1]]
            cur = e
        return out[0] + "q" + join(nums) + "z"
    start = (round(pts[0][0]), round(pts[0][1]))
    cur = start
    nums = []
    for i in range(1, len(pts) - 1):
        c = (round(pts[i][0]), round(pts[i][1]))
        e = (round((pts[i][0] + pts[i + 1][0]) / 2), round((pts[i][1] + pts[i + 1][1]) / 2))
        nums += [c[0] - cur[0], c[1] - cur[1], e[0] - cur[0], e[1] - cur[1]]
        cur = e
    last = (round(pts[-1][0]), round(pts[-1][1]))
    nums += [last[0] - cur[0], last[1] - cur[1], last[0] - cur[0], last[1] - cur[1]]
    return f"M{start[0]} {start[1]}q" + join(nums)


def join(nums):
    s = ""
    for n in nums:
        t = str(n)
        s += t if (not s or t.startswith("-")) else " " + t
    return s


def polylen(p):
    return sum(math.dist(p[i], p[i + 1]) for i in range(len(p) - 1))


L_FADE = (250, 440)               # left half: opaque until 330, gone at 496 (the empty centre columns)
R_FADE = (1160, 1350)
HALF = 560                       # each gutter image covers 560 of the 1600 units, full height
SIDES = {"l": (0, HALF), "r": (W - HALF, W)}


def frame(k, x0, x1, labels=True):
    """Contour lines (and index labels) of terrain frame k, restricted to x0..x1."""
    shift = k / K * DH
    minor, index, labs = [], [], []
    i = 0
    h = 0.02
    while h + shift < 1.12:
        lvl = h + shift
        ls = contours(lvl, x0, x1)
        isidx = (i % 5 == 0)
        for l in ls:
            if polylen(l) < 90:
                continue
            (index if isidx else minor).append(smooth_path(l))
            if labels and isidx and polylen(l) > 420:
                tgt, acc = polylen(l) * .4, 0
                for a in range(len(l) - 1):
                    d = math.dist(l[a], l[a + 1])
                    if acc + d >= tgt:
                        t = (tgt - acc) / d
                        x = l[a][0] + (l[a + 1][0] - l[a][0]) * t
                        y = l[a][1] + (l[a + 1][1] - l[a][1]) * t
                        ang = math.degrees(math.atan2(l[a + 1][1] - l[a][1], l[a + 1][0] - l[a][0]))
                        if ang > 90: ang -= 180
                        if ang <= -90: ang += 180
                        if (60 < x < 205 if x0 == 0 else 1395 < x < 1540) or x0 == 0 and x1 == W:
                            labs.append(f"<text transform='translate({round(x)} {round(y)}) rotate({round(ang)})' dy='5'>{elev(lvl)}</text>")
                        break
                    acc += d
        h += DH
        i += 1
    return minor, index, labs


def descend(x, y, steps=70, step=9):
    pts = [(x, y)]
    for _ in range(steps):
        e = 4
        gx = (H(x + e, y) - H(x - e, y)) / (2 * e)
        gy = (H(x, y + e) - H(x, y - e)) / (2 * e)
        n = math.hypot(gx, gy) or 1
        x, y = x - gx / n * step, y - gy / n * step
        pts.append((x, y))
        if not (0 < x < W and 0 < y < Hh):
            break
        if SKIP[0] < x / W < SKIP[1]:
            break
    return pts[::4]


def stream(x, y):
    p = descend(x, y)
    return smooth_path(p) if len(p) > 3 else ""


def statics(side, text=True, marks=True):
    """Streams, lake, trig marks, spot heights, benchmark and water names for one gutter."""
    x0, x1 = SIDES[side]
    out = []
    for sx, sy in ((205, 300), (1470, 190), (1480, 560)):
        if x0 <= sx <= x1:
            d = stream(sx, sy)
            if d:
                out.append(f"<path class='w' d='{d}'/>")
    if side == "r":
        out.append("<path class='lk' d='M1440 905c18-10 52-8 66 4s2 30-28 34-52-14-38-38z'/>")

    def tri(x, y, label, dx=14, dy=4):
        s = f"<g transform='translate({x} {y})'><path class='mk' d='M-8 6 0-9 8 6z'/><circle class='dt' r='1.6'/></g>"
        return s + (f"<text class='lb' x='{x + dx}' y='{y + dy}'>{label}</text>" if text else "")
    for x, y in ((1420, 330), (150, 150)):
        if marks and x0 <= x <= x1:
            out.append(tri(x, y, f"{elev(H(x, y))}"))
    for x, y in ((100, 800), (1500, 800), (1520, 580)):
        if marks and x0 <= x <= x1:
            out.append(f"<path class='mk' d='M{x - 4} {y - 4}l8 8m0-8l-8 8'/>" + (f"<text class='lb' x='{x + 9}' y='{y + 5}'>{elev(H(x, y))}</text>" if text else ""))
    if side == "r" and marks:
        out.append("<g transform='translate(1372 480)'><rect class='mk' x='-4' y='-4' width='8' height='8' fill='none'/>" + ("<text class='lb' x='11' y='4'>BM 1204</text>" if text else "") + "</g>")
        if text:
            out.append("<text class='hy' x='1450' y='215' transform='rotate(-24 1450 215)'>Linden Beck</text>")
    elif text:
        out.append("<text class='hy' x='215' y='262' transform='rotate(34 215 262)'>Salt Run</text>")
    return "".join(out)


def art_css(q=1.0):
  return (
    "path,circle,rect{fill:none}"
    f".m{{stroke:{SIENNA};stroke-width:1.05;stroke-opacity:{.62 * q:.2f};stroke-linejoin:round;vector-effect:non-scaling-stroke}}"
    f".x{{stroke:{SIENNA_D};stroke-width:1.8;stroke-opacity:{.78 * q:.2f};stroke-linejoin:round;vector-effect:non-scaling-stroke}}"
    f"text{{fill:{SIENNA_D};font:600 22px {MONO};text-anchor:middle;stroke:{PAPER};stroke-width:4;paint-order:stroke;stroke-linejoin:round}}"
    f".w{{stroke:{HYDRO};stroke-width:1.7;stroke-opacity:.8;stroke-linecap:round;vector-effect:non-scaling-stroke}}"
    f".lk{{fill:{HYDRO};fill-opacity:.22;stroke:{HYDRO};stroke-width:1.2;stroke-opacity:.8;vector-effect:non-scaling-stroke}}"
    f".mk{{stroke:{INK};stroke-width:1.4;stroke-opacity:.8;vector-effect:non-scaling-stroke}}.dt{{fill:{INK};fill-opacity:.8}}"
    f"text.lb{{fill:{INK};fill-opacity:.82;font:600 21px {MONO};text-anchor:start;stroke-width:3.5}}"
    f"text.hy{{fill:{HYDRO};font:italic 600 22px {SERIF};letter-spacing:.14em;stroke:{PAPER};stroke-width:3}}"
  )


ART_CSS = art_css()


def wrap(side, body, fade=False, q=1.0):
    x0, x1 = SIDES[side]
    if fade:
        # contours dissolve toward the reading column: an SVG mask (rasterised once), so ultrawide gutters never end in a hard cut
        ga, gb = (L_FADE[1], L_FADE[0]) if side == "l" else (R_FADE[0], R_FADE[1])
        body = (f"<defs><linearGradient id='g' gradientUnits='userSpaceOnUse' x1='{ga}' x2='{gb}' y1='0' y2='0'><stop offset='0' stop-color='#000'/><stop offset='1' stop-color='#fff'/></linearGradient>"
                f"<mask id='f' maskUnits='userSpaceOnUse' x='{x0}' y='0' width='{HALF}' height='{Hh}'><rect x='{x0}' y='0' width='{HALF}' height='{Hh}' style='fill:url(%23g)'/></mask>"
                f"<linearGradient id='v' gradientUnits='userSpaceOnUse' x1='0' x2='0' y1='820' y2='990'><stop offset='0' stop-color='#fff'/><stop offset='1' stop-color='#000'/></linearGradient>"
                f"<mask id='vm' maskUnits='userSpaceOnUse' x='{x0}' y='0' width='{HALF}' height='{Hh}'><rect x='{x0}' y='0' width='{HALF}' height='{Hh}' style='fill:url(%23v)'/></mask></defs>"
                f"<g mask='url(%23f)'><g mask='url(%23vm)'>{body}</g></g>")
    return (f"<svg xmlns='http://www.w3.org/2000/svg' width='{HALF}' height='{Hh}' viewBox='{x0} 0 {HALF} {Hh}'>"
            f"<style>{art_css(q)}</style>{body}</svg>")


def half_frame(side, k):
    """Contours + index labels only (the layer that changes while a turn runs)."""
    x0, x1 = SIDES[side]
    minor, index, labs = frame(k, x0, x1)
    return wrap(side, f"<path class='m' d='{''.join(minor)}'/><path class='x' d='{''.join(index)}'/>{''.join(labs)}", fade=True)


def half_static(side):
    return wrap(side, statics(side))


def half_plain(side):
    """Label-free still for narrow windows: lines and streams only, softer, fading toward the column."""
    x0, x1 = SIDES[side]
    minor, index, _ = frame(0, x0, x1, labels=False)
    return wrap(side, f"<path class='m' d='{''.join(minor)}'/><path class='x' d='{''.join(index)}'/>{statics(side, False, False)}", fade=True, q=.6)


def site_svg():
    """Whole sheet for the landing page hero (static, fixed aspect)."""
    global SKIP
    keep, SKIP = SKIP, (2, 3)
    minor, index, labs = frame(0, 0, W)
    SKIP = keep
    return (f"<svg xmlns='http://www.w3.org/2000/svg' width='{W}' height='{Hh}' viewBox='0 0 {W} {Hh}'><style>{ART_CSS}</style>"
            f"{statics('l', False, False)}{statics('r')}<path class='m' d='{''.join(minor)}'/><path class='x' d='{''.join(index)}'/>{''.join(l for l in labs if float(l.split('translate(')[1].split(' ')[0]) > 800)}</svg>")


# ---------------------------------------------------------------- small art
def grain_svg():
    return ("<svg xmlns='http://www.w3.org/2000/svg' width='240' height='240'>"
            "<filter id='n' x='0' y='0' width='100%' height='100%'><feTurbulence type='fractalNoise' baseFrequency='.75' numOctaves='2' stitchTiles='stitch'/>"
            "<feColorMatrix values='0 0 0 0 .42  0 0 0 0 .32  0 0 0 0 .18  1.1 0 0 0 -.42'/></filter>"
            "<rect width='240' height='240' filter='url(#n)'/></svg>")


def plus_svg():
    return ("<svg xmlns='http://www.w3.org/2000/svg' width='96' height='96'>"
            f"<path d='M48 41v14M41 48h14' stroke='{SIENNA_D}' stroke-opacity='.32' stroke-width='1' fill='none'/></svg>")


def ridge_svg():
    """Elevation profile for the header foot: a ridge line with hachure under it. Periodic so it tiles."""
    w, hh = 1500, 20
    pts = []
    for x in range(0, w + 1, 15):
        y = 8 + 3.4 * math.sin(2 * math.pi * x / w * 3 + .6) + 2.2 * math.sin(2 * math.pi * x / w * 7 + 2) + 1.4 * math.sin(2 * math.pi * x / w * 13)
        pts.append((x, y))
    d = "M" + "L".join(f"{x} {y:.1f}" for x, y in pts)
    hat = "".join(f"M{x} {y + 2.5:.1f}V{hh}" for x, y in pts[::1] if x % 15 == 0 and (x // 15) % 2 == 0)
    return (f"<svg xmlns='http://www.w3.org/2000/svg' width='{w}' height='{hh}' viewBox='0 0 {w} {hh}'>"
            f"<path d='{hat}' fill='none' stroke='{SIENNA}' stroke-width='1' stroke-opacity='.28'/>"
            f"<path d='{d}' fill='none' stroke='{SIENNA}' stroke-width='1.2' stroke-opacity='.8' stroke-linejoin='round'/></svg>")


def stake_svg():
    return (f"<svg xmlns='http://www.w3.org/2000/svg' width='9' height='9' viewBox='0 0 9 9'><path d='M0.5 8.5 4.5 0.5 8.5 8.5z' fill='{ORANGE}'/></svg>")


PIN_W, PIN_H, PIN_TIP = 44, 64, 58


def pin_svg():
    return (f"<svg xmlns='http://www.w3.org/2000/svg' width='{PIN_W}' height='{PIN_H}' viewBox='0 0 44 64'>"
            "<ellipse cx='22' cy='58' rx='9' ry='3' fill='#2b2519' fill-opacity='.22'/>"
            f"<path d='M22 58C22 58 7 38 7 23a15 15 0 1 1 30 0C37 38 22 58 22 58z' fill='{ORANGE}' stroke='#7c2208' stroke-width='1.4'/>"
            "<circle cx='22' cy='23' r='6' fill='#fff6e6'/><path d='M14 14a11 11 0 0 1 8-3' stroke='#fff' stroke-opacity='.55' stroke-width='2' fill='none' stroke-linecap='round'/></svg>")


def reticle_svg():
    return (f"<svg xmlns='http://www.w3.org/2000/svg' width='56' height='56' viewBox='0 0 56 56' fill='none' stroke='{ORANGE}' stroke-width='1.6'>"
            "<circle cx='28' cy='28' r='17'/><path d='M28 0v22M28 34v22M0 28h22M34 28h22'/><circle cx='28' cy='28' r='1.6' fill='" + ORANGE + "' stroke='none'/></svg>")


def legend_svg():
    """Sidebar-foot strip for wide windows: scale line and north arrow, 44px tall so it never sits behind thread rows."""
    css = (f"text{{font:600 10px {MONO};letter-spacing:.08em;fill:{INK};fill-opacity:.8}}path,circle{{fill:none}}")
    body = (
        f"<path d='M12 25h120M12 21v8M52 22v6M92 22v6M132 21v8' stroke='{INK}' stroke-opacity='.3'/>"
        f"<rect x='12' y='23' width='40' height='3' fill='{INK}' fill-opacity='.3'/><rect x='92' y='23' width='40' height='3' fill='{INK}' fill-opacity='.3'/>"
        f"<path d='M200 12l-6 22 6-6 6 6z' fill='{ORANGE}' fill-opacity='.38' stroke='none'/>"
    )
    return f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 220 40'>" + f"<style>{css}</style>{body}</svg>"


MINI_VB = (60, 368, 260, 54)          # sidebar-foot mini map: a 232 x 48 px strip around the summit


def mini_svg(which):
    """Sidebar-foot mini map for narrow windows. 'base' = paper + contours + neatline; 'pin' / 'ret' = the mark alone (same viewBox)."""
    css = (f".m{{fill:none;stroke:{SIENNA};stroke-width:1.2;stroke-opacity:.7;stroke-linejoin:round;vector-effect:non-scaling-stroke}}"
           f".x{{fill:none;stroke:{SIENNA_D};stroke-width:1.8;stroke-opacity:.8;stroke-linejoin:round;vector-effect:non-scaling-stroke}}")
    x, y, w, h = MINI_VB
    head = f"<svg xmlns='http://www.w3.org/2000/svg' width='{w * 2}' height='{h * 2}' viewBox='{x} {y} {w} {h}'>"
    if which == "ret":
        mark = (f"<g transform='translate(190 397) scale(.62)' fill='none' stroke='{ORANGE}' stroke-width='2' opacity='.4'><circle r='17'/><path d='M0-28v22M0 6v22M-28 0h22M6 0h22'/>"
                f"<circle r='2' fill='{ORANGE}' stroke='none'/></g>")
    else:
        mark = (f"<g transform='translate(190 416) scale(.78)' opacity='.4'><ellipse cx='0' cy='1' rx='8' ry='2.6' fill='#2b2519' fill-opacity='.25'/>"
                f"<path d='M0 0C0 0-14-19-14-33a14 14 0 1 1 28 0C14-19 0 0 0 0z' fill='{ORANGE}' stroke='#7c2208' stroke-width='1.4'/><circle cy='-33' r='5.5' fill='#fff6e6'/></g>")
    if which != "base":
        return head + mark + "</svg>"
    minor, index, _ = frame(0, x, x + w, labels=False)
    fade = (f"<defs><linearGradient id='t' gradientUnits='userSpaceOnUse' x1='0' x2='0' y1='{y}' y2='{y + h}'><stop offset='0' stop-color='#000'/><stop offset='.5' stop-color='#000'/><stop offset='1' stop-color='#fff'/></linearGradient>"
            f"<mask id='mm' maskUnits='userSpaceOnUse' x='{x}' y='{y}' width='{w}' height='{h}'><rect x='{x}' y='{y}' width='{w}' height='{h}' fill='url(%23t)'/></mask></defs>")
    return (head + f"<style>{css}</style>{fade}<g mask='url(%23mm)' opacity='.8'><path class='m' d='{''.join(minor)}'/><path class='x' d='{''.join(index)}'/></g></svg>")


def data_uri(svg):
    svg = svg.replace("%23", "\0")
    out = svg.replace("%", "%25").replace("#", "%23").replace('"', "'").replace("<", "%3C").replace("\0", "%23")
    return "url(\"data:image/svg+xml," + out + "\")"
# ---------------------------------------------------------------- theme colours
colors = {
    "canvas": PAPER, "chrome": "#ece4cd", "toolbar": "#ece4cd", "toolbarForeground": INK,
    "toolbarBorder": "#cdbf9a", "toolbarControl": "#e2d8bb", "toolbarControlForeground": INK,
    "toolbarControlHover": "#d8cca9", "surface": "#f8f4e6", "surfaceRaised": "#fbf8ee",
    "surfaceOverlay": "#fffdf6", "text": INK, "textMuted": "#61563f", "border": "#cdbf9a",
    "input": "#b3a37a", "focus": ORANGE, "accent": ORANGE, "accentForeground": "#fff8ee",
    "secondary": "#dcd2b2", "secondaryForeground": INK, "muted": "#e4dbbf",
    "mutedForeground": "#5f553f", "placeholder": "#766a51", "secondaryLabel": "#5f553f",
    "iconMuted": "#6b5f46", "error": "#b3261e", "errorForeground": "#8f1d17", "errorSurface": "#f6ddd2",
    "warning": "#a86a08", "warningForeground": "#744802", "warningSurface": "#f5e6bd",
    "update": HYDRO, "updateForeground": "#1d516b", "updateSurface": "#d8e7e3",
    "accentSurface": "#f1d9c6", "accentSurfaceForeground": "#8a2c0f", "messageSurface": "#e6dcbd",
    "messageForeground": INK, "messageAction": ORANGE, "messageActionForeground": "#fff8ee",
    "messageActionHover": "#a93513", "codeBackground": "#ebe3c9", "codeForeground": "#3b3020",
    "searchMatchBackground": "#f3d98a", "searchMatchForeground": INK,
    "searchMatchActiveBackground": ORANGE, "searchMatchActiveForeground": "#fff8ee",
    "sidebar": "#e7dec2", "sidebarForeground": INK, "sidebarMutedForeground": "#62573f",
    "sidebarControlSurface": "#efe7cf", "sidebarRowHover": "#ded4b5", "sidebarRowActive": "#d7ccaa",
    "sidebarRowSelected": "#d2c69f", "sidebarBorder": "#bfb08a", "terminalBackground": "#efe8d1",
    "terminalForeground": INK, "terminalCursor": ORANGE, "terminalSelection": "#e2c99a",
    "terminalScrollbar": "#cdbf9a", "terminalScrollbarHover": "#b3a37a",
}

# ---------------------------------------------------------------- CSS
CW = "var(--chat-content-max-width,46rem)"
GUTW = f"min(calc((100% - {CW})/2 - 20px),56vh)"
CONV = '[data-workspace-area="conversation"]'
BUSY = ('body:has([data-timeline-row-kind="working"])',
        'body:has([data-thread-item] [aria-busy="true"][aria-current]:not([aria-current="false"]))')


def busy(sel):
    return ",".join(f"{b} {sel}" for b in BUSY)


def idle(sel):
    """Matches only while no turn is running (its transitions/animation play when a turn ends)."""
    return f"body:not(:has([data-timeline-row-kind=\"working\"])):not(:has([data-thread-item] [aria-busy=\"true\"][aria-current]:not([aria-current=\"false\"]))) {sel}"


WASH = ("radial-gradient(ellipse 15% 26% at 12% 43%,rgba(212,168,108,.20),transparent),"
        "radial-gradient(ellipse 15% 24% at 89% 33%,rgba(212,168,108,.17),transparent),"
        "radial-gradient(ellipse 16% 22% at 92% 86%,rgba(120,150,84,.16),transparent),"
        "radial-gradient(ellipse 14% 20% at 8% 88%,rgba(120,150,84,.13),transparent)")

GRAIN, PLUS, RIDGE, STAKE, PIN, RETICLE = (data_uri(s) for s in (grain_svg(), plus_svg(), ridge_svg(), stake_svg(), pin_svg(), reticle_svg()))
LEGEND = data_uri(legend_svg())
MINI_B, MINI_P, MINI_R = (data_uri(mini_svg(w)) for w in ('base', 'pin', 'ret'))
FL = [data_uri(half_frame("l", k)) for k in range(K)]
FR = [data_uri(half_frame("r", k)) for k in range(K)]
SL, SR = data_uri(half_static("l")), data_uri(half_static("r"))
NL, NR = data_uri(half_plain("l")), data_uri(half_plain("r"))

ROOT_VARS = "".join(f"--ct-l{k}:{FL[k]};--ct-r{k}:{FR[k]};" for k in range(K)) + f"--ct-sl:{SL};--ct-sr:{SR};--ct-nl:{NL};--ct-nr:{NR};--ct-mb:{MINI_B};--ct-mp:{MINI_P};--ct-mr:{MINI_R};--ct-lg:{LEGEND};--ct-pin:{PIN};--ct-ret:{RETICLE};"

# Gutter geometry. Each terrain half is a 560 x 1000 unit image on a gutter-sized pseudo-element (aspect-ratio 560/1000,
# full pane height), so the summit, pin and labels keep their proportions whatever the pane's size, terminal drawer or panels.
SUMMIT = (190, 430)
GW, GH = HALF, Hh


def pct(v, total):
    return f"{v / total * 100:.3f}%"


RIP_BOX = 280
RIP_SIZE = f"{pct(RIP_BOX, GW)} {pct(RIP_BOX, GH)}"
RIP_POS = f"{(SUMMIT[0] - RIP_BOX / 2) / (GW - RIP_BOX) * 100:.3f}% {(SUMMIT[1] - RIP_BOX / 2) / (GH - RIP_BOX) * 100:.3f}%"
PW = 52
PH = round(PW * PIN_H / PIN_W)
PIN_SIZE = f"{pct(PW, GW)} {pct(PH, GH)}"
tip_top = SUMMIT[1] - PH * PIN_TIP / PIN_H
PIN_X = (SUMMIT[0] - PW / 2) / (GW - PW) * 100
PIN_REST = f"{PIN_X:.3f}% {tip_top / (GH - PH) * 100:.3f}%"
PIN_LIFT = f"{PIN_X:.3f}% {(tip_top - 60) / (GH - PH) * 100:.3f}%"
RET = 56
RET_SIZE = f"{pct(RET, GW)} {pct(RET, GH)}"
RET_POS = f"{(SUMMIT[0] - RET / 2) / (GW - RET) * 100:.3f}% {(SUMMIT[1] - RET / 2) / (GH - RET) * 100:.3f}%"
RIPPLE = ("radial-gradient(circle at 50% 50%,transparent calc(var(--ct-rr) - 1.5px),rgba(192,64,26,var(--ct-ra)) calc(var(--ct-rr) - .5px),"
          "rgba(192,64,26,var(--ct-ra)) calc(var(--ct-rr) + .5px),transparent calc(var(--ct-rr) + 1.5px))")
BOUNCE = "linear(0,.35 14%,1 38%,.82 50%,1 62%,.94 74%,1 86%,1)"
DIM = .6


def shift_keyframes(name, side):
    """Ping-pong through the frames. Each frame is held ~75% of its slot; the layer dips to .6, switches while dimmed, and returns."""
    n = len(STEPS)
    dips = [100 * (i + .5) / n for i in range(n)]
    half = 100 * .14 / n * 3 / 3   # dip half-width in percent of the cycle

    def L(f):
        if side == "l":
            return f"var(--ct-l{f}),{RIPPLE},var(--ct-ret),var(--ct-pin)"
        return f"var(--ct-r{f})"
    out = []
    cur = STEPS[0]
    out.append(f"0%{{background-image:{L(cur)};opacity:1}}")
    for i, c in enumerate(dips):
        nxt = STEPS[(i + 1) % n]
        out.append(f"{c - half:g}%{{background-image:{L(cur)};opacity:1}}")
        out.append(f"{c - .01:g}%{{background-image:{L(cur)};opacity:{DIM}}}")
        out.append(f"{c:g}%{{background-image:{L(nxt)};opacity:{DIM}}}")
        out.append(f"{c + half:g}%{{background-image:{L(nxt)};opacity:1}}")
        cur = nxt
    out.append(f"100%{{background-image:{L(cur)};opacity:1}}")
    return "@keyframes " + name + "{" + "".join(out) + "}"


def resurvey_keyframes(name, side):
    """Long turns: a calm 60s loop. Slow breath, then one re-survey (dim, step to frame 1, return) and a step back, so minute ten still says working."""
    def L(f):
        return f"var(--ct-l{f}),{RIPPLE},var(--ct-ret),var(--ct-pin)" if side == "l" else f"var(--ct-r{f})"
    o = []
    o.append(f"0%{{background-image:{L(0)};opacity:1}}")
    o.append(f"20%{{background-image:{L(0)};opacity:.86}}")
    o.append(f"40%{{background-image:{L(0)};opacity:1}}")
    o.append(f"58%{{background-image:{L(0)};opacity:1}}")
    o.append(f"59.9%{{background-image:{L(0)};opacity:{DIM}}}")
    o.append(f"60%{{background-image:{L(1)};opacity:{DIM}}}")
    o.append(f"62%{{background-image:{L(1)};opacity:1}}")
    o.append(f"88%{{background-image:{L(1)};opacity:1}}")
    o.append(f"89.9%{{background-image:{L(1)};opacity:{DIM}}}")
    o.append(f"90%{{background-image:{L(0)};opacity:{DIM}}}")
    o.append(f"92%{{background-image:{L(0)};opacity:1}}")
    o.append(f"100%{{background-image:{L(0)};opacity:1}}")
    return "@keyframes " + name + "{" + "".join(o) + "}"


# the conversation background keeps the static features (streams, lake, trig marks, names) so only the contour lines breathe
SIZES = f"{GUTW} auto,{GUTW} auto,96px 96px," + ",".join("100% 100%" for _ in range(4)) + ",240px 240px"
REPEATS = "no-repeat,no-repeat,repeat," + ",".join("no-repeat" for _ in range(4)) + ",repeat"
POS = "0 0,100% 0," + ",".join("0 0" for _ in range(6))
BASE_LAYERS = f"{PLUS},{WASH},{GRAIN}"
SB = "231,222,194"
SB_TAIL = f"{PLUS} 0 0/96px 96px,{GRAIN} 0 0/240px 240px,#e7dec2"


def sidebar_mini(pin, ret):
    return (f"var(--ct-mr) center bottom 58px/{ret} no-repeat,var(--ct-mp) center bottom 58px/{pin} no-repeat,var(--ct-mb) center bottom 58px/232px 48px no-repeat,{SB_TAIL}")


GUT = f"content:\"\";position:absolute;top:0;height:auto;width:{GUTW};aspect-ratio:560/1000;z-index:-1;pointer-events:none;background-repeat:no-repeat;"
IDLE_L = (f"background-size:100% 100%,{RIP_SIZE},0 0,{PIN_SIZE};background-position:0 0,{RIP_POS},{RET_POS},{PIN_REST}")
BUSY_L = (f"background-size:100% 100%,{RIP_SIZE},{RET_SIZE},0 0;background-position:0 0,{RIP_POS},{RET_POS},{PIN_LIFT}")

css = (
    "@property --ct-rr{syntax:'<length>';inherits:false;initial-value:2px}"
    "@property --ct-ra{syntax:'<number>';inherits:false;initial-value:0}"
    f":root{{{ROOT_VARS}}}"
    f"body{{font-family:'Avenir Next','SF Pro Text',system-ui,sans-serif!important}}"
    # ---- the sheet: paper, graticule, washes, grain and the static map features sit on the conversation background
    f"{CONV}{{position:relative;isolation:isolate;"
    f"background-color:{PAPER}!important;background-image:var(--ct-sl),var(--ct-sr),{BASE_LAYERS}!important;"
    f"background-size:{SIZES}!important;background-repeat:{REPEATS}!important;background-position:{POS}!important}}"
    # reading-column scrim: paper opaque enough that contours never touch the text
    f"{CONV} .messages-timeline-scroll{{background:"
    f"linear-gradient(90deg,transparent calc(50% - {CW}/2 - 96px),rgba(243,237,218,.94) calc(50% - {CW}/2 - 14px),rgba(243,237,218,.94) calc(50% + {CW}/2 + 14px),transparent calc(50% + {CW}/2 + 96px))!important}}"
    # contours: two gutter-sized layers (left ::before, right ::after). While a turn runs they step through three elevations on a
    # 15s cycle: each frame is held ~3s, the layer dips to 60% and switches while dimmed (labels never cross-fade).
    # The left layer also carries the survey pin / reticle / ripple at the summit; those are transitions between the idle and busy
    # values, so the drop only plays when a turn actually ends (never on load or thread switch).
    f"{CONV}::before{{{GUT}left:0;background-image:var(--ct-l0),{RIPPLE},var(--ct-ret),var(--ct-pin);"
    f"{IDLE_L};--ct-rr:2px;--ct-ra:0}}"
    f"{CONV}::after{{{GUT}right:0;background-image:var(--ct-r0);background-size:100% 100%;background-position:0 0}}"
    + idle(f"{CONV}::before") +
    f"{{--ct-rr:110px;--ct-ra:0;{IDLE_L};"
    f"transition:background-size .28s ease-in .12s,background-position 1s {BOUNCE} .1s,--ct-rr 1.5s cubic-bezier(.2,.6,.3,1) .55s,--ct-ra 1.5s ease-out .55s;animation:ct-reveal .6s ease-out}}"
    + idle(f"{CONV}::after") + "{animation:ct-reveal .6s ease-out}"
    + busy(f"{CONV}::before") +
    f"{{opacity:.6;--ct-rr:2px;--ct-ra:.7;{BUSY_L};"
    f"transition:background-size .35s ease-in,background-position .4s ease-in,--ct-rr 0s,--ct-ra 0s;animation:ct-shift {CYCLE}s linear 2 forwards,ct-resurvey 60s linear {CYCLE*2}s infinite}}"
    + busy(f"{CONV}::after") + f"{{opacity:.6;animation:ct-shift-r {CYCLE}s linear 2 forwards,ct-resurvey-r 60s linear {CYCLE*2}s infinite}}"
    + resurvey_keyframes("ct-resurvey", "l") + resurvey_keyframes("ct-resurvey-r", "r") + "@keyframes ct-reveal{from{opacity:.6}to{opacity:1}}" + shift_keyframes("ct-shift", "l") + shift_keyframes("ct-shift-r", "r") +
    # ---- header: an elevation profile with hachure along its foot; a survey stake walks it during a turn
    f"[data-chat-header]{{font-family:{SERIF};letter-spacing:.01em;background-color:rgba(236,228,205,.96)!important;background-image:{STAKE},{RIDGE}!important;"
    "background-repeat:no-repeat,repeat-x!important;background-size:0 0,1500px 20px!important;background-position:12px 100%,0 100%;"
    f"border-bottom:1px solid #cdbf9a!important;transition:background-size .4s}}"
    + busy("[data-chat-header]") + f"{{background-size:9px 9px,1500px 20px!important;animation:ct-walk {CYCLE}s ease-in-out infinite}}"
    "@keyframes ct-walk{0%,100%{background-position:12px 100%,0 100%}50%{background-position:calc(100% - 12px) 100%,0 100%}}"
    # ---- working row: hachure ticks march (the survey's depression-contour mark); work rows are set in mono
    "[data-timeline-row-kind=\"working\"]{"
    f"background-image:linear-gradient({ORANGE},{ORANGE}),repeating-linear-gradient(90deg,{ORANGE} 0 1.5px,transparent 1.5px 7px)!important;"
    "background-size:100% 1px,100% 5px!important;background-repeat:no-repeat,repeat-x!important;background-position:0 100%,0 100%;"
    "animation:ct-hach 1.25s linear infinite}"
    "@keyframes ct-hach{to{background-position:0 100%,7px 100%}}"
    f"[data-timeline-row-kind=\"work\"],[data-timeline-row-kind=\"working\"]{{font-family:{MONO}!important;font-size:12px!important;letter-spacing:-.01em;font-variant-numeric:tabular-nums}}"
    # ---- thread rows: hover = contour rings from the right edge; busy = a survey line sweeps the foot of the row
    "[data-thread-item]{font-variant-numeric:tabular-nums}"
    "[data-thread-item]>*{border-radius:3px!important;"
    f"background-image:linear-gradient(90deg,transparent,{ORANGE} 40%,{ORANGE} 60%,transparent),repeating-radial-gradient(circle at 100% 50%,transparent 0 7px,rgba(184,115,69,.22) 7px 8px);"
    "background-repeat:no-repeat;background-position:-100% 100%,100% 0;background-size:0 2px,0 100%;transition:background-size .45s cubic-bezier(.2,.7,.2,1)}"
    "[data-thread-item]:hover>*{background-size:0 2px,56px 100%}"
    "[data-thread-item] [aria-busy=\"true\"]{"
    f"background-image:linear-gradient(90deg,transparent,{ORANGE} 40%,{ORANGE} 60%,transparent),repeating-radial-gradient(circle at 100% 50%,transparent 0 7px,rgba(184,115,69,.22) 7px 8px)!important;"
    "background-size:44% 2px,0 100%!important;background-repeat:no-repeat!important;animation:ct-sweep 2.5s linear infinite}"
    "[data-thread-item]:hover [aria-busy=\"true\"]{background-size:44% 2px,56px 100%!important}"
    "@keyframes ct-sweep{from{background-position:-100% 100%,100% 0}to{background-position:200% 100%,100% 0}}"
    f"[data-thread-item] [aria-current]:not([aria-current=\"false\"]){{box-shadow:inset 3px 0 {ORANGE}}}"
    # project monogram: a benchmark square with a neatline
    f"[data-slot=\"project-monogram\"]{{border-radius:1px!important;outline:1px solid rgba(143,100,60,.55);outline-offset:1.5px;font-family:{MONO}}}"
    # ---- sidebar: map margin. Wide: a legend card. Narrow: a mini map (below).
    f"[data-slot=\"sidebar-inner\"]{{background:var(--ct-lg) center bottom 58px/224px 44px no-repeat,{SB_TAIL}!important}}"
    # ---- message bubble: a legend label, hydro-blue left stripe
    "[data-user-message-bubble]{background:#e6dcbd!important;border:1px solid rgba(143,100,60,.4)!important;border-left:3px solid #2f7396!important;border-radius:2px!important}"
    # ---- composer: double neatline; the outer line turns survey orange on focus (the app's own ring is removed)
    "[data-slot=\"composer-host\"]{background:rgba(251,248,238,.97)!important;border:1px solid rgba(143,100,60,.55)!important;border-radius:2px!important;"
    "box-shadow:0 0 0 3px rgba(243,237,218,.96),0 0 0 4px rgba(143,100,60,.32);transition:border-color .2s,box-shadow .3s}"
    f"[data-slot=\"composer-host\"]:focus-within{{border-color:{ORANGE}!important;box-shadow:0 0 0 3px rgba(243,237,218,.96),0 0 0 4px {ORANGE}}}"
    "[data-slot=\"composer-host\"] :focus-visible,.composer-tiptap:focus-visible{outline:none!important}"
    # ---- markdown
    f".chat-markdown-codeblock{{background:#ebe3c9!important;border:1px solid rgba(143,100,60,.3)!important;border-left:3px solid {SAGE}!important;border-radius:2px!important}}"
    ".chat-markdown :not(pre)>code{color:#7a3417;background:rgba(184,115,69,.14);padding:.05em .32em;border-radius:2px}"
    f".chat-markdown :is(h1,h2,h3){{font-family:{SERIF};letter-spacing:.015em}}.chat-markdown :is(h1,h2){{border-bottom:1px dotted rgba(143,100,60,.55);padding-bottom:.2em}}"
    f".chat-markdown h3{{font-family:{MONO};font-size:.82em;letter-spacing:.16em;text-transform:uppercase;color:#8f4a28}}.chat-markdown h3 code{{text-transform:none}}"
    ".chat-markdown a{color:#1d5f82!important;text-decoration-style:dotted;text-underline-offset:3px}"
    "::selection{background:rgba(192,64,26,.24)}"
    ".chat-markdown blockquote{border-left:3px double #2f7396;background:rgba(47,115,150,.07);margin-left:0;padding:.35em 1em;border-radius:0 2px 2px 0}"
    f".chat-markdown table{{border-collapse:collapse;border:1px solid rgba(143,100,60,.55);background:rgba(251,248,238,.6)}}"
    f".chat-markdown th{{background:#e6dcbd;font-family:{MONO};font-size:.76em;letter-spacing:.1em;text-transform:uppercase;color:#8f4a28}}"
    ".chat-markdown :is(th,td){border:1px dotted rgba(143,100,60,.5);padding:.35em .7em}"
    ".chat-markdown hr{border:0;border-top:2px dotted rgba(143,100,60,.55);margin:1.4em 0}"
    ".chat-markdown ul>li::marker{content:\"\\25B3  \";color:#8f4a28;font-size:.78em}.chat-markdown ol>li::marker{color:#8f4a28;font-family:" + MONO + ";font-size:.9em}"
    # ---- popups: the neatline double border, in the map's language
    "[data-slot=\"dialog-popup\"],[data-slot=\"popover-popup\"],[data-slot=\"menu-popup\"]{border-radius:3px!important;border:1px solid rgba(143,100,60,.55)!important;"
    "box-shadow:0 10px 30px rgba(60,40,15,.22),inset 0 0 0 3px #fffdf6,inset 0 0 0 4px rgba(143,100,60,.28)!important}"
    f"[data-slot=\"tooltip-popup\"]{{background:{INK}!important;color:{PAPER}!important;border-radius:2px!important;font-family:{MONO}!important;font-size:11px!important;letter-spacing:.08em;text-transform:uppercase}}"
    # ---- controls
    "[data-slot=\"button\"],[data-slot=\"input\"],[data-slot=\"select-trigger\"]{border-radius:3px!important;transition:background-color .15s,border-color .15s,box-shadow .15s}"
    "[data-slot=\"input\"],[data-slot=\"select-trigger\"]{border:1px solid rgba(143,100,60,.5)!important}"
    f"[data-slot=\"input\"]:hover,[data-slot=\"select-trigger\"]:hover{{border-color:{SIENNA_D}!important}}"
    f"[data-slot=\"button\"]:hover{{box-shadow:inset 0 0 0 1px rgba(143,100,60,.55)}}"
    f"[data-slot=\"button\"]:active{{transform:translateY(1px)}}"
    f"[data-slot=\"sidebar\"] [data-slot=\"button\"]{{font-family:{MONO};font-size:12px;letter-spacing:.04em}}"
    f":focus-visible{{outline:2px solid {ORANGE};outline-offset:2px}}"
    f"[data-slot=\"switch\"]{{border-radius:3px!important;border:1px solid rgba(143,100,60,.6)!important}}"
    f"[data-slot=\"switch\"][aria-checked=\"true\"]{{background:{ORANGE}!important;border-color:#7c2208!important}}"
    "svg.lucide{stroke-width:1.6;stroke-linecap:square;stroke-linejoin:miter}"
    # ---- scrollbars
    "::-webkit-scrollbar{width:10px;height:10px}::-webkit-scrollbar-track{background:rgba(143,100,60,.08);border-left:1px dotted rgba(143,100,60,.35)}"
    "::-webkit-scrollbar-thumb,[data-slot=\"scroll-area-thumb\"]{background:rgba(143,100,60,.34)!important;border-radius:2px!important}"
    "::-webkit-scrollbar-thumb:hover,[data-slot=\"scroll-area-thumb\"]:hover{background:rgba(192,64,26,.6)!important}"
    "[data-slot=\"scroll-area-scrollbar\"]{background:rgba(143,100,60,.06)}"
    # ---- panels
    "[data-thread-details-card]{border:1px solid rgba(143,100,60,.55)!important;border-radius:2px!important;box-shadow:inset 0 0 0 3px #f8f4e6,inset 0 0 0 4px rgba(143,100,60,.28)!important}"
    f"[data-thread-terminal-drawer]{{border-top:2px dotted rgba(143,100,60,.6)!important;background-image:{PLUS}!important;background-size:96px 96px!important}}"
    f"[data-settings-page-scroll]{{background-image:{PLUS},{GRAIN}!important;background-size:96px 96px,240px 240px!important}}"
    # ---- narrow windows: gutters are thin, so the terrain becomes a soft, label-free still and the mini map carries the pin
    "@media (max-width:1459px){"
    f"{CONV}{{background-image:var(--ct-nl),var(--ct-nr),{BASE_LAYERS}!important}}"
    f"{CONV}::before,{CONV}::after{{display:none!important}}"
    f"{CONV} .messages-timeline-scroll{{background:linear-gradient(90deg,transparent calc(50% - {CW}/2 - 44px),rgba(243,237,218,.94) calc(50% - {CW}/2 - 8px),rgba(243,237,218,.94) calc(50% + {CW}/2 + 8px),transparent calc(50% + {CW}/2 + 44px))!important}}"
    f"[data-slot=\"sidebar-inner\"]{{background:{sidebar_mini('232px 48px', '0 0')}!important;transition:background-size .5s cubic-bezier(.2,.7,.2,1)}}"
    + busy("[data-slot=\"sidebar-inner\"]") + f"{{background:{sidebar_mini('0 0', '232px 48px')}!important}}"
    "}"
    # ---- reduced motion: freeze to the idle sheet, pin planted
    "@media (prefers-reduced-motion:reduce){"
    "*,*::before,*::after{animation:none!important;transition:none!important}"
    + busy(f"{CONV}::before") + f"{{--ct-ra:0;opacity:1;{BUSY_L}}}"
    + busy(f"{CONV}::after") + "{opacity:1}"
    + "[data-thread-item] [aria-busy=\"true\"]{background-position:0 100%,100% 0!important}"
    + busy("[data-chat-header]") + "{background-size:0 0,1500px 20px!important}"
    "}"
    "@media (prefers-reduced-motion:reduce) and (max-width:1459px){"
    + busy("[data-slot=\"sidebar-inner\"]") + f"{{background:{sidebar_mini('0 0', '232px 48px')}!important}}"
    "}"
)

theme = {"version": 1, "id": "contour", "name": "Contour", "appearance": "light", "accent": ORANGE, "canvas": PAPER,
         "colors": colors, "css": css}

if __name__ == "__main__":
    with open(os.path.join(ROOT, "contour.json"), "w") as fh:
        json.dump(theme, fh, ensure_ascii=False)
    print("css chars:", len(css))
    os.makedirs(os.path.join(ROOT, "assets", "svg"), exist_ok=True)
    for n, s in (("terrain", site_svg()), ("legend", legend_svg()), ("pin", pin_svg())):
        with open(os.path.join(ROOT, "assets", "svg", f"{n}.svg"), "w") as fh:
            fh.write(s.replace("%23", "#"))
    for n in ("terrain-live",):
        p = os.path.join(ROOT, "assets", "svg", f"{n}.svg")
        if os.path.exists(p):
            os.remove(p)


# ---------------------------------------------------------------- landing page
SITE = "https://joshsaintjacque.github.io/t3code-theme-contour/"
PAL = [("canvas", "Canvas", "Field-sheet paper"), ("sidebar", "Sidebar", "Map margin"), ("messageSurface", "Message", "Legend label box"),
       ("codeBackground", "Code", "Code block ground"), ("text", "Text", "Survey ink"), ("textMuted", "Muted", "Secondary text"),
       ("accent", "Accent", "Survey orange: focus, send, work"), ("update", "Update", "Hydro blue"), ("border", "Border", "Neatline"),
       ("error", "Error", ""), ("warning", "Warning", ""), ("sidebarRowSelected", "Selected row", "Current thread")]


def site():
    rows = []
    for key, name, note in PAL:
        hx = colors[key].upper()
        sub = f"<small>{note}</small>" if note else ""
        rows.append(f"        <button class=\"sw\" type=\"button\" data-hex=\"{hx}\"><i style=\"background:{hx}\"></i><span><b>{name}</b>{sub}</span><code>{hx}</code></button>")
    t = open(os.path.join(HERE, "index.tpl.html")).read()
    t = t.replace("__PALETTE__", "\n".join(rows)).replace("__SITE__", SITE)
    open(os.path.join(ROOT, "index.html"), "w").write(t)


if __name__ == "__main__":
    site()
