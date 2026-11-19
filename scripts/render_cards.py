#!/usr/bin/env python3
"""Render the profile README cards as animated SVGs (night-city noir theme, Montserrat display type).

Reads data/profile.json, pulls the last 12 months of GitHub contributions
(GraphQL API, needs GH_TOKEN), and writes cards/*.svg.

    python scripts/render_cards.py           # live data (GH_TOKEN required)
    python scripts/render_cards.py --demo    # made-up contribution data, for previews
"""
from __future__ import annotations

import base64
import datetime as dt
import html
import json
import math
import os
import random
import sys
import urllib.request
from pathlib import Path

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
CARDS = ROOT / "cards"
FONTS = ROOT / "fonts"

# ---- palette: sodium-lamp amber on wet asphalt -------------------------------
NIGHT = "#08090c"
PANEL = "#111216"
PANEL_HI = "#17181e"
EDGE = "#2a2b33"
BONE = "#ece6d8"
SMOKE = "#9c978c"
ASH = "#5d5a55"
AMBER = "#ff8a1f"
AMBER_HI = "#ffb35c"
AMBER_DEEP = "#b8500c"
LEVELS = ["#202128", "#3a2716", "#7a3f12", "#c95e10", "#ff9a3c"]
SHADOW = 6

FONT_FILES = {"N": "noir.woff", "NS": "noir-semi.woff", "M": "mono.woff", "MB": "mono-bold.woff", "S": "sans.woff"}
_metrics: dict = {}


def _font(key):
    if key not in _metrics:
        f = TTFont(FONTS / FONT_FILES[key])
        _metrics[key] = (f.getBestCmap(), f["hmtx"].metrics, f["head"].unitsPerEm)
    return _metrics[key]


def text_width(s, key, size, spacing=0.0):
    cmap, hmtx, upm = _font(key)
    w = sum(hmtx.get(cmap.get(ord(c), ".notdef"), (upm // 2, 0))[0] for c in s)
    return w * size / upm + spacing * max(len(s) - 1, 0)


def fit(s, key, max_w, max_size, spacing=0.0):
    size = max_size
    while size > 8 and text_width(s, key, size, spacing) > max_w:
        size -= 1
    return size


def wrap(s, key, size, max_w):
    lines, cur = [], ""
    for word in s.split():
        trial = f"{cur} {word}".strip()
        if text_width(trial, key, size) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def font_css(keys):
    return "".join(
        f"@font-face{{font-family:'{k}';src:url(data:font/woff;base64,"
        f"{base64.b64encode((FONTS / FONT_FILES[k]).read_bytes()).decode()}) format('woff');}}"
        for k in keys
    )


BASE_CSS = """
.n{font-family:'N','Montserrat','Arial Black',sans-serif;font-weight:700;}
.ns{font-family:'NS','Montserrat',sans-serif;font-weight:600;}
.m{font-family:'M',ui-monospace,Menlo,Consolas,monospace;}
.mb{font-family:'MB',ui-monospace,Menlo,Consolas,monospace;font-weight:700;}
.s{font-family:'S','Inter',-apple-system,'Segoe UI',Helvetica,Arial,sans-serif;}
.rise{animation:rise .8s cubic-bezier(.2,.8,.2,1) both;}
@keyframes rise{from{opacity:0;transform:translateY(12px);}to{opacity:1;transform:none;}}
.fade{animation:fade .6s ease-out both;}
@keyframes fade{from{opacity:0;}to{opacity:1;}}
.pulse{animation:pulse 2.4s ease-in-out infinite;}
@keyframes pulse{0%,100%{opacity:1;}50%{opacity:.2;}}
.blink{animation:blink 1.05s steps(1) infinite;}
@keyframes blink{50%{opacity:0;}}
.neon{animation:neon 2.2s linear both;}
@keyframes neon{0%{opacity:0;}8%{opacity:.9;}10%{opacity:.1;}14%{opacity:1;}16%{opacity:.3;}22%,100%{opacity:1;}}
@media (prefers-reduced-motion: reduce){*{animation:none!important;}}
"""

COMMON_DEFS = f"""
<filter id="grain" x="0" y="0" width="100%" height="100%">
<feTurbulence type="fractalNoise" baseFrequency=".85" numOctaves="2" stitchTiles="stitch" seed="4"/>
<feColorMatrix type="saturate" values="0"/>
<feComponentTransfer><feFuncA type="table" tableValues="0 .09"/></feComponentTransfer></filter>
<filter id="glow" x="-20%" y="-50%" width="140%" height="200%">
<feGaussianBlur stdDeviation="5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<radialGradient id="vig" cx="50%" cy="40%" r="75%">
<stop offset="55%" stop-color="#000" stop-opacity="0"/><stop offset="100%" stop-color="#000" stop-opacity=".55"/></radialGradient>
<linearGradient id="sheen" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="{PANEL_HI}"/><stop offset="1" stop-color="{PANEL}"/></linearGradient>
<pattern id="hazard" width="14" height="14" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
<rect width="14" height="14" fill="{NIGHT}"/><rect width="7" height="14" fill="{AMBER}"/></pattern>
<pattern id="stripes" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
<rect width="7" height="7" fill="#2a1a0e"/><line x1="0" y1="0" x2="0" y2="7" stroke="{AMBER}" stroke-width="2.4"/></pattern>
"""


def esc(s):
    return html.escape(str(s), quote=True)


def svg(w, h, body, fonts=("N", "M", "MB", "S"), css="", defs=""):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img">\n'
        f"<defs><style>{font_css(fonts)}{BASE_CSS}{css}</style>{COMMON_DEFS}{defs}</defs>\n{body}\n</svg>\n"
    )


def card(x, y, w, h, r=14, brackets=True, fill="url(#sheen)"):
    out = (
        f'<rect x="{x+SHADOW}" y="{y+SHADOW}" width="{w}" height="{h}" rx="{r}" fill="#000" opacity=".85"/>'
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}"/>'
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="url(#vig)"/>'
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" filter="url(#grain)"/>'
        f'<rect x="{x+.75}" y="{y+.75}" width="{w-1.5}" height="{h-1.5}" rx="{r}" fill="none" stroke="{EDGE}" stroke-width="1.5"/>'
    )
    if brackets:  # case-file corner marks
        L, o = 18, 10
        out += (
            f'<g stroke="{AMBER}" stroke-width="2" fill="none" stroke-linecap="square">'
            f'<path d="M{x+o} {y+o+L} V{y+o} H{x+o+L}"/>'
            f'<path d="M{x+w-o} {y+h-o-L} V{y+h-o} H{x+w-o-L}"/></g>'
        )
    return out


def arrow_badge(cx, cy, r=17):
    s = r * 0.6
    x, y = cx - s / 2, cy - s / 2
    return (
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{AMBER}" stroke-width="1.8"/>'
        f'<g stroke="{AMBER}" stroke-width="2" stroke-linecap="square" fill="none">'
        f'<path d="M{x:.1f} {y+s:.1f} L{x+s:.1f} {y:.1f}"/><path d="M{x+s*0.3:.1f} {y:.1f} H{x+s:.1f} V{y+s*0.7:.1f}"/></g>'
    )


def pill(x, y, label, size=12, filled=False, dot=True):
    tw = text_width(label, "MB", size, 0.14 * size)
    pad, dot_w = 13, (15 if dot else 0)
    w, h = pad * 2 + dot_w + tw, size + 15
    out = (
        f'<rect x="{x}" y="{y}" width="{w:.1f}" height="{h}" rx="3" fill="{AMBER if filled else "none"}" '
        f'stroke="{AMBER}" stroke-width="1.5"/>'
    )
    if dot:
        out += f'<circle cx="{x+pad+3.5}" cy="{y+h/2}" r="3.6" fill="{NIGHT if filled else AMBER}" class="pulse"/>'
    out += (
        f'<text x="{x+pad+dot_w:.1f}" y="{y+h/2+size*0.36:.1f}" class="mb" font-size="{size}" '
        f'letter-spacing="{0.14*size:.2f}" fill="{NIGHT if filled else AMBER}">{esc(label)}</text>'
    )
    return out, w


# ---- data ------------------------------------------------------------------
def gql(query, variables):
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GH_TOKEN is not set. Run with --demo for sample data.")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if payload.get("errors"):
        raise SystemExit(f"GitHub API error: {payload['errors']}")
    return payload["data"]


def fetch_days(login):
    q = """query($login:String!){user(login:$login){contributionsCollection{
      contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}"""
    weeks = gql(q, {"login": login})["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return [(dt.date.fromisoformat(d["date"]), d["contributionCount"]) for w in weeks for d in w["contributionDays"]]


def fetch_repo(full):
    owner, name = full.split("/", 1)
    q = """query($o:String!,$n:String!){repository(owner:$o,name:$n){stargazerCount isPrivate primaryLanguage{name}}}"""
    return gql(q, {"o": owner, "n": name})["repository"]


def demo_days():
    rnd = random.Random(7)
    today = dt.date.today()
    start = today - dt.timedelta(days=364)
    start -= dt.timedelta(days=(start.weekday() + 1) % 7)
    days, d = [], start
    while d <= today:
        heat = max(0.0, 1 - (today - d).days / 240)
        n = rnd.randint(1, int(3 + 22 * heat)) if rnd.random() < 0.08 + 0.75 * heat else 0
        days.append((d, n))
        d += dt.timedelta(days=1)
    return days


def stats(days):
    today = days[-1][0]
    counts = dict(days)
    longest = run = 0
    for _, c in days:
        run = run + 1 if c else 0
        longest = max(longest, run)
    cur, d = 0, today
    if not counts.get(d):
        d -= dt.timedelta(days=1)
    while counts.get(d):
        cur += 1
        d -= dt.timedelta(days=1)
    months, (y, m) = [], (today.year, today.month)
    for _ in range(12):
        months.append((y, m))
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    months.reverse()
    return dict(
        total=sum(counts.values()),
        active=sum(1 for c in counts.values() if c),
        longest=longest,
        current=cur,
        busiest=max(days, key=lambda x: x[1]),
        monthly=[(ym, sum(c for d, c in days if (d.year, d.month) == ym)) for ym in months],
    )


# ---- cards -----------------------------------------------------------------
W = 1100


def eeg_path(period, amp, mid, length, seed=3, step=3):
    """Periodic EEG-like trace (alpha + steady SSVEP + jitter), drawn over `length` px."""
    rnd = random.Random(seed)
    harm = [(rnd.uniform(0.15, 0.5) / (1 + h * 0.15), rnd.uniform(0, 6.28), h) for h in range(3, 40)]
    pts = []
    for i in range(int(length / step) + 1):
        x = i * step
        t = x / period * 2 * math.pi
        v = 0.55 * math.sin(t * 6) + 0.35 * math.sin(t * 14 + 1.1)
        v += sum(a * math.sin(t * h + ph) for a, ph, h in harm) * 0.35
        v += 1.8 * math.exp(-(((x % period) - period * 0.62) ** 2) / 60)
        pts.append(f"{x:.0f},{mid - v * amp:.1f}")
    return "M" + " L".join(pts)


def skyline(w, base, rnd):
    """Generic city silhouette with lit windows; returns (buildings, windows)."""
    blds, wins, x = [], [], -10
    while x < w + 10:
        bw = rnd.randint(34, 96)
        bh = rnd.choice([rnd.randint(40, 80), rnd.randint(70, 130), rnd.randint(110, 165)])
        top = base - bh
        blds.append(f'<rect x="{x}" y="{top}" width="{bw}" height="{bh+20}" fill="#050508"/>')
        if rnd.random() < 0.3:  # rooftop detail
            ax = x + rnd.randint(6, max(7, bw - 12))
            blds.append(f'<rect x="{ax}" y="{top-rnd.randint(8,22)}" width="3" height="24" fill="#050508"/>')
            if rnd.random() < 0.5:
                blds.append(f'<circle cx="{ax+1.5}" cy="{top-20}" r="2" fill="#ff3b1f" class="pulse" style="animation-duration:{rnd.uniform(1.4,2.6):.1f}s"/>')
        for wy in range(top + 10, base - 6, 11):
            for wx in range(x + 7, x + bw - 7, 9):
                r = rnd.random()
                if r < 0.13:
                    flick = f' class="flk" style="animation-duration:{rnd.uniform(3,9):.1f}s;animation-delay:-{rnd.uniform(0,9):.1f}s"' if rnd.random() < 0.25 else ""
                    col = AMBER_HI if rnd.random() < 0.8 else "#e8e2cf"
                    wins.append(f'<rect x="{wx}" y="{wy}" width="3.5" height="5" fill="{col}" opacity="{rnd.uniform(.45,.95):.2f}"{flick}/>')
        x += bw + rnd.randint(-4, 4)
    return "".join(blds), "".join(wins)


def render_hero(p):
    H = 650
    rnd = random.Random(11)
    x0, y0, cw, ch = 4, 4, W - 8 - SHADOW, H - 8 - SHADOW
    sky_base = y0 + ch  # skyline sits on the card's bottom edge
    body = [
        f'<rect x="{x0+SHADOW}" y="{y0+SHADOW}" width="{cw}" height="{ch}" rx="16" fill="#000" opacity=".85"/>',
        f'<g clip-path="url(#heroclip)">',
        f'<rect x="{x0}" y="{y0}" width="{cw}" height="{ch}" fill="url(#night)"/>',
    ]
    # night haze for the beams to light up
    for cx, cy, rx, ry, op in ((180, 40, 260, 60, .55), (520, 20, 300, 70, .5), (860, 50, 280, 60, .55), (1040, 15, 200, 50, .45)):
        body.append(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="#262630" opacity="{op}" filter="url(#haze)"/>')

    # searchlights: two beams swinging back and forth from behind the rooftops
    oy = sky_base - 95
    top = y0 - 120
    beams = ((560, 7.5, "alternate"), (940, 9.5, "alternate-reverse"))

    def beam_group(bx, dur, direction, inner):
        return (
            f'<g class="sweep" style="transform-origin:{bx}px {oy}px;animation-duration:{dur}s;'
            f'animation-direction:{direction}">{inner}</g>'
        )

    for bx, dur, direction in beams:
        body.append(f'<circle cx="{bx}" cy="{oy+6}" r="70" fill="url(#src)"/>')
        cone = (
            f'<polygon points="{bx-8},{oy} {bx+8},{oy} {bx+230},{top} {bx-230},{top}" fill="url(#beam)" opacity=".26" filter="url(#soft)"/>'
            f'<polygon points="{bx-3},{oy} {bx+3},{oy} {bx+80},{top} {bx-80},{top}" fill="url(#beam)" opacity=".32" filter="url(#softer)"/>'
            f'<ellipse cx="{bx}" cy="{y0+34}" rx="190" ry="46" fill="url(#hot)" opacity=".55"/>'
        )
        body.append(f'<g style="mix-blend-mode:screen">{beam_group(bx, dur, direction, cone)}</g>')

    # rain: once dim everywhere, once bright where the beams pass (masked by the same moving cones)
    drops = []
    for _ in range(90):
        rx, ry, ln = rnd.uniform(0, W + 60), rnd.uniform(0, H), rnd.uniform(12, 30)
        op, du, de = rnd.uniform(.06, .2), rnd.uniform(.7, 1.3), rnd.uniform(0, 1.3)
        drops.append((rx, ry, ln, op, du, de))

    def rain_layer(color, scale, width):
        return "".join(
            f'<line x1="{rx:.0f}" y1="{ry:.0f}" x2="{rx-ln*0.25:.0f}" y2="{ry+ln:.0f}" stroke="{color}" '
            f'stroke-width="{width}" opacity="{min(1, op*scale):.2f}" class="rain" '
            f'style="animation-duration:{du:.2f}s;animation-delay:-{de:.2f}s"/>'
            for rx, ry, ln, op, du, de in drops
        )

    body.append(rain_layer(BONE, 1, 1))
    mask_cones = "".join(
        beam_group(bx, dur, direction,
                   f'<polygon points="{bx-8},{oy} {bx+8},{oy} {bx+230},{top} {bx-230},{top}" fill="#fff" filter="url(#soft)"/>')
        for bx, dur, direction in beams
    )
    body.append(f'<g mask="url(#beammask)">{rain_layer("#fff6e0", 3.5, 1.2)}</g>')
    blds, wins = skyline(W, sky_base, rnd)
    # the "city pulse": EEG trace running along the rooftops
    period, pulse_y = 360, sky_base - 200
    body.append(
        f'<g class="scroll"><path d="{eeg_path(period, 9, pulse_y, W + period + 20)}" fill="none" stroke="{AMBER}" '
        f'stroke-width="2" stroke-linejoin="round" opacity=".85" filter="url(#glow)"/></g>'
    )
    body.append(blds + wins)
    body.append(f'<rect x="{x0}" y="{y0}" width="{cw}" height="{ch}" fill="url(#vig)"/>')
    body.append(f'<rect x="{x0}" y="{y0}" width="{cw}" height="{ch}" filter="url(#grain)"/>')
    body.append("</g>")
    body.append(f'<rect x="{x0+.75}" y="{y0+.75}" width="{cw-1.5}" height="{ch-1.5}" rx="16" fill="none" stroke="{EDGE}" stroke-width="1.5"/>')

    pl, _ = pill(44, 40, p["status"], size=12)
    body.append(f'<g class="fade">{pl}</g>')

    lines = p["name_lines"]
    size = 100
    while size > 20 and max(text_width(l, "N", size, size * 0.12) for l in lines) > 620:
        size -= 1
    sp = size * 0.12
    lh, base = size * 1.18, 96 + size * 0.75
    for i, line in enumerate(lines):
        yy = base + i * lh
        body.append(
            f'<g class="neon" style="animation-delay:{0.2 + i*0.25:.2f}s">'
            f'<text x="44" y="{yy:.1f}" class="n" font-size="{size}" letter-spacing="{sp:.1f}" fill="{AMBER}" opacity=".45" filter="url(#glow)">{esc(line)}</text>'
            f'<text x="44" y="{yy:.1f}" class="n" font-size="{size}" letter-spacing="{sp:.1f}" fill="{BONE}">{esc(line)}</text></g>'
        )
    ty = base + (len(lines) - 1) * lh + 58
    role = p["role"].lstrip("/ ").strip()
    body.append(
        f'<text x="46" y="{ty:.1f}" class="mb fade" font-size="15" letter-spacing="2.4" style="animation-delay:.7s">'
        f'<tspan fill="{AMBER}">//</tspan><tspan fill="{BONE}" dx="10">{esc(role)}</tspan></text>'
    )
    for i, s in enumerate(p["summary"]):
        body.append(
            f'<text x="46" y="{ty+32+i*26:.1f}" class="s fade" font-size="18" fill="{SMOKE}" '
            f'style="animation-delay:{.8+i*.08:.2f}s">{esc(s)}</text>'
        )

    # terminal
    tx, ty0, tw, th = 712, 40, 340, 300
    t = p["terminal"]
    term = [
        f'<rect x="{tx+5}" y="{ty0+5}" width="{tw}" height="{th}" rx="10" fill="#000" opacity=".9"/>',
        f'<rect x="{tx}" y="{ty0}" width="{tw}" height="{th}" rx="10" fill="#0a0b0e" fill-opacity=".92" stroke="{EDGE}" stroke-width="1.5"/>',
        f'<line x1="{tx}" y1="{ty0+36}" x2="{tx+tw}" y2="{ty0+36}" stroke="{EDGE}" stroke-width="1.5"/>',
    ]
    for i, col in enumerate((AMBER, ASH, ASH)):
        term.append(f'<circle cx="{tx+22+i*18}" cy="{ty0+18}" r="5" fill="{col}"/>')
    term.append(f'<text x="{tx+tw-18}" y="{ty0+23}" class="m" font-size="12" fill="{ASH}" text-anchor="end">{esc(t["path"])}</text>')
    ly, step = ty0 + 74, 0.55
    for i, (kind, txt) in enumerate(t["lines"]):
        delay = 0.9 + i * step
        if kind == "cmd":
            line = f'<tspan class="mb" fill="{AMBER}">$</tspan><tspan class="mb" fill="{BONE}" dx="9">{esc(txt)}</tspan>'
        else:
            line = f'<tspan class="m" fill="{SMOKE}">{esc(txt)}</tspan>'
        term.append(f'<text x="{tx+22}" y="{ly}" font-size="14.5" class="fade" style="animation-delay:{delay:.2f}s">{line}</text>')
        ly += 32
    cdelay = 0.9 + len(t["lines"]) * step
    term.append(
        f'<g class="fade" style="animation-delay:{cdelay:.2f}s"><text x="{tx+22}" y="{ly}" class="mb" font-size="14.5" fill="{AMBER}">$</text>'
        f'<rect x="{tx+40}" y="{ly-13}" width="9" height="16" fill="{AMBER}" class="blink"/></g>'
    )
    body.append("".join(term))

    # caption along the street
    cap = p.get("hero_caption", "CH·O1 · LIVE EEG")
    cw_ = text_width(cap, "M", 11.5, 1.6)
    body.append(f'<rect x="{x0+cw-34-cw_:.0f}" y="{sky_base-34}" width="{cw_+24:.0f}" height="26" rx="3" fill="#000" opacity=".75"/>')
    body.append(f'<text x="{x0+cw-22}" y="{sky_base-16}" class="m" font-size="11.5" letter-spacing="1.6" fill="{AMBER}" text-anchor="end" opacity=".8">{esc(cap)}</text>')

    defs = (
        f'<clipPath id="heroclip"><rect x="{x0}" y="{y0}" width="{cw}" height="{ch}" rx="16"/></clipPath>'
        f'<linearGradient id="night" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#07080b"/>'
        f'<stop offset=".7" stop-color="#121219"/><stop offset="1" stop-color="#1d1610"/></linearGradient>'
        f'<linearGradient id="beam" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#fff1d6" stop-opacity="1"/>'
        f'<stop offset=".55" stop-color="#f6e7c8" stop-opacity=".55"/><stop offset="1" stop-color="#f6e7c8" stop-opacity="0"/></linearGradient>'
        f'<radialGradient id="hot"><stop offset="0" stop-color="#fff3dc" stop-opacity=".9"/><stop offset="1" stop-color="#fff3dc" stop-opacity="0"/></radialGradient>'
        f'<radialGradient id="src"><stop offset="0" stop-color="#fff1d6" stop-opacity=".55"/><stop offset=".35" stop-color="{AMBER_HI}" stop-opacity=".18"/><stop offset="1" stop-color="{AMBER_HI}" stop-opacity="0"/></radialGradient>'
        f'<filter id="soft" x="-50%" y="-10%" width="200%" height="120%"><feGaussianBlur stdDeviation="14"/></filter>'
        f'<filter id="softer" x="-50%" y="-10%" width="200%" height="120%"><feGaussianBlur stdDeviation="6"/></filter>'
        f'<filter id="haze" x="-30%" y="-80%" width="160%" height="260%"><feGaussianBlur stdDeviation="22"/></filter>'
        f'<mask id="beammask" maskUnits="userSpaceOnUse" x="0" y="0" width="{W}" height="{H}"><rect width="{W}" height="{H}" fill="#000"/>{mask_cones}</mask>'
    )
    css = (
        ".sweep{animation:sweep ease-in-out infinite alternate;}"
        "@keyframes sweep{from{transform:rotate(-26deg);}to{transform:rotate(26deg);}}"
        ".rain{animation:rain linear infinite;}"
        "@keyframes rain{from{transform:translate(0,-60px);}to{transform:translate(-15px,60px);}}"
        f".scroll{{animation:scroll 7s linear infinite;}}@keyframes scroll{{from{{transform:translateX(0);}}to{{transform:translateX(-{period}px);}}}}"
        ".flk{animation:flk steps(1) infinite;}@keyframes flk{0%,100%{opacity:.9;}40%{opacity:.1;}46%{opacity:.9;}}"
    )
    return svg(W, H, "\n".join(body), css=css, defs=defs)


TW, TH = 360, 250


def render_tile(t):
    cw, ch = TW - 8 - SHADOW, TH - 8 - SHADOW
    body = [card(4, 4, cw, ch)]
    num, _, rest = t["kicker"].partition(" / ")
    body.append(
        f'<text x="32" y="48" class="mb" font-size="12.5" letter-spacing="2"><tspan fill="{AMBER}">FILE {esc(num)}</tspan>'
        f'<tspan fill="{ASH}" dx="9">/</tspan><tspan fill="{SMOKE}" dx="9">{esc(rest)}</tspan></text>'
    )
    body.append(arrow_badge(cw - 26, 40))
    size = fit(t["title"], "N", cw - 56, 38, 3)
    body.append(f'<text x="30" y="128" class="n rise" font-size="{size}" letter-spacing="3" fill="{BONE}" style="animation-delay:.1s">{esc(t["title"])}</text>')
    body.append(f'<rect x="32" y="146" width="56" height="3" fill="{AMBER}" class="bar"/>')
    s1 = fit(t["line1"], "MB", cw - 60, 14.5)
    body.append(f'<text x="32" y="182" class="mb fade" font-size="{s1}" fill="{BONE}" style="animation-delay:.25s">{esc(t["line1"])}</text>')
    s2 = fit(t["line2"], "S", cw - 60, 15)
    body.append(f'<text x="32" y="208" class="s fade" font-size="{s2}" fill="{SMOKE}" style="animation-delay:.35s">{esc(t["line2"])}</text>')
    css = ".bar{transform-box:fill-box;transform-origin:0 50%;animation:bar .8s .3s cubic-bezier(.2,.8,.2,1) both;}@keyframes bar{from{transform:scaleX(0);}to{transform:scaleX(1);}}"
    return svg(TW, TH, "\n".join(body), css=css)


def render_ticker(items):
    """Static banner: items spread evenly across the band, separators centred in the gaps."""
    H = 96
    cw, ch = W - 8 - SHADOW, H - 8 - SHADOW
    band = 9
    body = [
        f'<rect x="{4+SHADOW}" y="{4+SHADOW}" width="{cw}" height="{ch}" rx="6" fill="#000" opacity=".85"/>',
        f'<g clip-path="url(#tclip)">',
        f'<rect x="4" y="4" width="{cw}" height="{ch}" fill="{NIGHT}"/>',
        f'<rect x="4" y="4" width="{cw+40}" height="{band}" fill="url(#hazard)" class="tape"/>',
        f'<rect x="-36" y="{4+ch-band}" width="{cw+80}" height="{band}" fill="url(#hazard)" class="tape2"/>',
        f'<rect x="4" y="4" width="{cw}" height="{ch}" filter="url(#grain)"/></g>',
    ]
    labels = [i.upper() for i in items]
    pad = 44
    size = 26
    while size > 14:
        widths = [text_width(l, "NS", size, size * 0.22) for l in labels]
        if sum(widths) + 60 * (len(labels) - 1) <= cw - 2 * pad:
            break
        size -= 1
    gap = (cw - 2 * pad - sum(widths)) / max(len(labels) - 1, 1)
    x, yb = 4 + pad, 4 + ch / 2 + size * 0.35
    for i, (l, w) in enumerate(zip(labels, widths)):
        body.append(
            f'<text x="{x:.1f}" y="{yb:.1f}" class="ns fade" font-size="{size}" letter-spacing="{size*0.22:.1f}" fill="{AMBER}" '
            f'style="animation-delay:{.1+i*.12:.2f}s">{esc(l)}</text>'
        )
        if i < len(labels) - 1:
            cx = x + w + gap / 2
            body.append(f'<text x="{cx:.1f}" y="{yb:.1f}" class="ns" font-size="{size}" fill="{ASH}" text-anchor="middle">/</text>')
        x += w + gap
    body.append(f'<rect x="4.75" y="4.75" width="{cw-1.5}" height="{ch-1.5}" rx="6" fill="none" stroke="{EDGE}" stroke-width="1.5"/>')
    defs = f'<clipPath id="tclip"><rect x="4" y="4" width="{cw}" height="{ch}" rx="6"/></clipPath>'
    css = (".tape{animation:tape 3s linear infinite;}.tape2{animation:tape 3s linear infinite reverse;}"
           "@keyframes tape{from{transform:translateX(0);}to{transform:translateX(-19.8px);}}")
    return svg(W, H, "\n".join(body), fonts=("NS",), css=css, defs=defs)


def render_heatmap(days):
    H = 300
    cw, ch = W - 8 - SHADOW, H - 8 - SHADOW
    body = [card(4, 4, cw, ch, 16)]
    body.append(f'<text x="44" y="56" class="mb" font-size="13" letter-spacing="2.2" fill="{BONE}">ACTIVITY LOG <tspan fill="{AMBER}">·</tspan> LAST 12 MONTHS</text>')
    lab = "SYNCED NIGHTLY"
    lw = text_width(lab, "MB", 13, 2.2)
    body.append(f'<circle cx="{cw-30-lw-14}" cy="51.5" r="4.5" fill="{AMBER}" class="pulse"/>')
    body.append(f'<text x="{cw-30-lw}" y="56" class="mb" font-size="13" letter-spacing="2.2" fill="{AMBER}">{lab}</text>')

    nz = sorted(c for _, c in days if c)
    q = [nz[int(len(nz) * f)] for f in (0.25, 0.5, 0.8)] if nz else []

    def level(c):
        return 0 if not c else 1 + sum(c > t for t in q)

    weeks = []
    for d, c in days:
        if not weeks or d.weekday() == 6:
            weeks.append([])
        weeks[-1].append((d, c))
    gx, gy = 44, 104
    step = (cw - 44 - 30) / len(weeks)
    cell = step * 0.78
    cells, labels, last_month = [], [], None
    for wi, wk in enumerate(weeks):
        x = gx + wi * step
        m = wk[0][0].month
        if m != last_month and wk[0][0].day <= 7:
            labels.append(f'<text x="{x:.1f}" y="{gy-12}" class="m" font-size="12.5" fill="{ASH}">{wk[0][0].strftime("%b").upper()}</text>')
        last_month = m
        for d, c in wk:
            r = (d.weekday() + 1) % 7
            lv = level(c)
            glow = ' filter="url(#glow)"' if lv == 4 else ""
            cells.append(
                f'<rect x="{x:.1f}" y="{gy + r*step:.1f}" width="{cell:.1f}" height="{cell:.1f}" rx="2" '
                f'fill="{LEVELS[lv]}"{glow} class="fade" style="animation-delay:{0.2 + wi*0.02:.2f}s"/>'
            )
    d_last = days[-1][0]
    x = gx + (len(weeks) - 1) * step
    r = (d_last.weekday() + 1) % 7
    cells.append(f'<rect x="{x-2.5:.1f}" y="{gy + r*step - 2.5:.1f}" width="{cell+5:.1f}" height="{cell+5:.1f}" rx="4" fill="none" stroke="{BONE}" stroke-width="1.5" class="pulse"/>')
    body += labels + cells
    fy = gy + 7 * step + 34
    body.append(f'<text x="44" y="{fy:.1f}" class="m" font-size="12.5" fill="{ASH}">one square per night · tonight ringed</text>')
    lx = cw - 30
    more_w = text_width("MORE", "M", 12.5, 1)
    body.append(f'<text x="{lx-more_w:.1f}" y="{fy:.1f}" class="m" font-size="12.5" letter-spacing="1" fill="{ASH}">MORE</text>')
    sx = lx - more_w - 12 - 5 * 18
    for i, col in enumerate(LEVELS):
        body.append(f'<rect x="{sx+i*18:.1f}" y="{fy-11:.1f}" width="13" height="13" rx="2" fill="{col}"/>')
    less_w = text_width("LESS", "M", 12.5, 1)
    body.append(f'<text x="{sx-12-less_w:.1f}" y="{fy:.1f}" class="m" font-size="12.5" letter-spacing="1" fill="{ASH}">LESS</text>')
    return svg(W, H, "\n".join(body), fonts=("M", "MB"))


def render_activity(st):
    H = 430
    cw, ch = W - 8 - SHADOW, H - 8 - SHADOW
    body = [card(4, 4, cw, ch, 16)]
    body.append(f'<text x="44" y="60" class="mb" font-size="13" letter-spacing="2.2" fill="{ASH}">THE LAST 12 MONTHS ON GITHUB</text>')
    tot = f"{st['total']:,}"
    big = 52
    while big > 20 and text_width(tot, "N", big, 2) + 22 + text_width("CONTRIBUTIONS", "N", big, 2) > 700:
        big -= 1
    tw_ = text_width(tot, "N", big, 2)
    body.append(f'<text x="42" y="132" class="n rise" font-size="{big}" letter-spacing="2" fill="{BONE}">{tot}</text>')
    body.append(f'<text x="{42+tw_+22:.1f}" y="132" class="n rise" font-size="{big}" letter-spacing="2" fill="{ASH}" style="animation-delay:.1s">CONTRIBUTIONS</text>')

    monthly = st["monthly"]
    peak = max((c for _, c in monthly), default=0) or 1
    peak_i = max(range(len(monthly)), key=lambda i: monthly[i][1])
    bx, area, bottom, maxh = 44, 680, 352, 150
    slot = area / len(monthly)
    bw = slot * 0.62
    body.append(f'<line x1="{bx}" y1="{bottom+1}" x2="{bx+area}" y2="{bottom+1}" stroke="{EDGE}" stroke-width="2"/>')
    for i, ((y, m), c) in enumerate(monthly):
        x = bx + i * slot + (slot - bw) / 2
        h = max(5, maxh * c / peak) if c else 2
        last = i == len(monthly) - 1
        extra = ""
        if i == peak_i and c:
            fill, extra = AMBER, ' filter="url(#glow)"'
        elif last:
            fill = "url(#stripes)"
        elif c:
            fill = "#3b3c45"
        else:
            fill = "#22232a"
        delay = 0.3 + i * 0.06
        body.append(
            f'<rect x="{x:.1f}" y="{bottom-h:.1f}" width="{bw:.1f}" height="{h:.1f}" rx="2" fill="{fill}"{extra} '
            f'class="grow" style="animation-delay:{delay:.2f}s"/>'
        )
        if i == peak_i and c:
            body.append(f'<text x="{x+bw/2:.1f}" y="{bottom-h-12:.1f}" class="mb fade" font-size="13" fill="{AMBER}" text-anchor="middle" style="animation-delay:{delay+.4:.2f}s">{c:,}</text>')
        elif last and c:
            body.append(f'<text x="{x+bw/2:.1f}" y="{bottom-h-12:.1f}" class="m fade" font-size="11.5" fill="{ASH}" text-anchor="middle" style="animation-delay:{delay+.4:.2f}s">so far</text>')
        mn = dt.date(y, m, 1).strftime("%b").upper()
        body.append(f'<text x="{x+bw/2:.1f}" y="{bottom+28}" class="m" font-size="12.5" fill="{ASH}" text-anchor="middle">{mn}</text>')

    sx = 775
    bd, bc = st["busiest"]
    rows = [
        (f'{st["current"]}', f'/ {st["longest"]}', "night streak now, and the longest", AMBER),
        (f'{st["active"]}', "", "days with a contribution", BONE),
        (f"{bc:,}", "", f"on the busiest day, {bd.strftime('%b')} {bd.day}", BONE),
    ]
    y = 142
    for i, (big, tail, cap, col) in enumerate(rows):
        tail_svg = f'<tspan dx="10" fill="{ASH}">{esc(tail)}</tspan>' if tail else ""
        body.append(
            f'<g class="rise" style="animation-delay:{0.4 + i*0.12:.2f}s">'
            f'<text x="{sx}" y="{y}" class="n" font-size="44" letter-spacing="1" fill="{col}">{esc(big)}{tail_svg}</text>'
            f'<text x="{sx}" y="{y+28}" class="s" font-size="15" fill="{SMOKE}">{esc(cap)}</text></g>'
        )
        if i < len(rows) - 1:
            body.append(f'<line x1="{sx}" y1="{y+54}" x2="{cw-34}" y2="{y+54}" stroke="{EDGE}" stroke-width="1.5" stroke-dasharray="3 5"/>')
        y += 104
    css = (
        ".grow{transform-box:fill-box;transform-origin:50% 100%;animation:grow .9s cubic-bezier(.2,.8,.2,1) both;}"
        "@keyframes grow{from{transform:scaleY(0);}to{transform:scaleY(1);}}"
    )
    return svg(W, H, "\n".join(body), css=css)


def render_section(title, right):
    H = 118
    cw, ch = W - 8 - SHADOW, H - 8 - SHADOW
    body = [card(4, 4, cw, ch, 14, brackets=False)]
    body.append(f'<rect x="4" y="4" width="8" height="{ch}" fill="{AMBER}" clip-path="url(#sclip)"/>')
    body.append(f'<text x="40" y="{4+ch/2+11:.1f}" class="n rise" font-size="32" letter-spacing="5" fill="{BONE}">{esc(title)}</text>')
    rw = text_width(right, "MB", 13, 2.2)
    rx = cw - 30 - rw
    body.append(f'<circle cx="{rx-15}" cy="{4+ch/2}" r="4.5" fill="{AMBER}" class="pulse"/>')
    body.append(f'<text x="{rx:.1f}" y="{4+ch/2+4.5:.1f}" class="mb" font-size="13" letter-spacing="2.2" fill="{AMBER}">{esc(right)}</text>')
    defs = f'<clipPath id="sclip"><rect x="4" y="4" width="{cw}" height="{ch}" rx="14"/></clipPath>'
    return svg(W, H, "\n".join(body), fonts=("N", "MB"), defs=defs)


PW, PH = 360, 300


def render_project(pj, info=None):
    cw, ch = PW - 8 - SHADOW, PH - 8 - SHADOW
    body = [card(4, 4, cw, ch)]
    pl, w = pill(30, 28, pj["status"], size=11.5, filled=pj.get("highlight", False))
    body.append(pl)
    private = pj.get("private") or (info or {}).get("isPrivate")
    if private:
        lx = 30 + w + 12
        body.append(
            f'<g fill="{ASH}"><rect x="{lx}" y="39" width="11" height="9" rx="1.5"/>'
            f'<path d="M{lx+2.3} 40 v-3.6 a3.2 3.2 0 0 1 6.4 0 v3.6" fill="none" stroke="{ASH}" stroke-width="1.8"/></g>'
            f'<text x="{lx+18}" y="48" class="mb" font-size="11" letter-spacing="1.4" fill="{ASH}">PRIVATE</text>'
        )
    body.append(arrow_badge(cw - 26, 40, 16))
    ts = fit(pj["title"], "N", cw - 60, 24, 1.5)
    body.append(f'<text x="30" y="108" class="n rise" font-size="{ts}" letter-spacing="1.5" fill="{BONE}">{esc(pj["title"])}</text>')
    for i, line in enumerate(wrap(pj["desc"], "S", 15, cw - 58)[:4]):
        body.append(f'<text x="30" y="{144+i*23}" class="s fade" font-size="15" fill="{SMOKE}" style="animation-delay:{.15+i*.06:.2f}s">{esc(line)}</text>')
    fy = ch - 46
    body.append(f'<line x1="30" y1="{fy}" x2="{cw-28}" y2="{fy}" stroke="{EDGE}" stroke-width="1.5" stroke-dasharray="3 5"/>')
    lang = ((info or {}).get("primaryLanguage") or {}).get("name", "")
    foot = pj.get("foot") or lang
    body.append(f'<rect x="30" y="{fy+20}" width="9" height="9" fill="{AMBER}"/>')
    body.append(f'<text x="46" y="{fy+29}" class="m" font-size="13" fill="{SMOKE}">{esc(foot)}</text>')
    if info and not private:
        stars = f'★ {info.get("stargazerCount", 0)}'
        sw = text_width(stars, "MB", 13)
        body.append(f'<text x="{cw-28-sw:.1f}" y="{fy+29}" class="mb" font-size="13" fill="{AMBER}">{esc(stars)}</text>')
    return svg(PW, PH, "\n".join(body), fonts=("N", "MB", "M", "S"))


def main():
    demo = "--demo" in sys.argv
    p = json.loads((ROOT / "data" / "profile.json").read_text())
    CARDS.mkdir(exist_ok=True)
    days = demo_days() if demo else fetch_days(p["github_login"])
    st = stats(days)

    out = {
        "hero.svg": render_hero(p),
        "ticker.svg": render_ticker(p["ticker"]),
        "heatmap.svg": render_heatmap(days),
        "activity.svg": render_activity(st),
        "building.svg": render_section("WHAT I'M BUILDING", "RIGHT NOW"),
    }
    for t in p["tiles"]:
        out[f'{t["file"]}.svg'] = render_tile(t)
    for pj in p["projects"]:
        info = None
        if pj.get("repo") and not demo:
            try:
                info = fetch_repo(pj["repo"])
            except Exception as e:  # one bad repo shouldn't block the rest
                print(f"warning: {pj['repo']}: {e}", file=sys.stderr)
        out[f'{pj["file"]}.svg'] = render_project(pj, info)

    for name, content in out.items():
        (CARDS / name).write_text(content)
    print(f"wrote {len(out)} cards · {st['total']} contributions · streak {st['current']}/{st['longest']}")


if __name__ == "__main__":
    main()
