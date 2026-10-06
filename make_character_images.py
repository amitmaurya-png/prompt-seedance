#!/usr/bin/env python3
"""Draw reference images for the named characters and write characters.json.

For each character this writes, into assets/characters/:
  <name>_full.svg / .png   full body, front view, plain background
  <name>_head.svg / .png   head-only close-up (Jesus: back of head and shoulders only)
PNG files are what Seedance accepts; they are rendered with macOS Quick Look (qlmanage).

The drawings are proposed designs built from the few details the screenplay gives
(see "from_script" in characters.json). Replace any image link in characters.json with
final artwork, for example made with the "image_prompt" in Seedream.
"""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "assets" / "characters"
SIZE = 1024  # PNG pixels

STYLE = ("warm, painterly 2D storybook animation style, soft textured brushwork, gentle natural light, "
         "ancient Galilee setting, simple handwoven clothing")

LINE = "#4a3426"


def page(body, view="0 0 512 512"):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view}" width="512" height="512">'
            '<defs><radialGradient id="bg" cx="50%" cy="40%" r="75%"><stop offset="0" stop-color="#fbf5ea"/>'
            '<stop offset="1" stop-color="#ecdcc2"/></radialGradient></defs>'
            '<rect x="-2000" y="-2000" width="5000" height="5000" fill="url(#bg)"/>'
            f'{body}</svg>')


# ---------- face and hair parts ----------

def eyes(cx, cy, r, iris="#5a3a22", worried=False, wide=False, brow="#3a2a1f", brow_w=None):
    dx, ey = r * 0.38, cy + r * 0.05
    er = r * (0.17 if wide else 0.15)
    bw = brow_w or r * 0.07
    tilt = -r * 0.06 if worried else r * 0.02
    out = []
    for s in (-1, 1):
        x = cx + s * dx
        out.append(f'<ellipse cx="{x}" cy="{ey}" rx="{er}" ry="{er*1.1}" fill="#fff"/>'
                   f'<circle cx="{x}" cy="{ey+er*0.1}" r="{er*0.72}" fill="{iris}"/>'
                   f'<circle cx="{x}" cy="{ey+er*0.12}" r="{er*0.38}" fill="#1c1410"/>'
                   f'<circle cx="{x-er*0.28}" cy="{ey-er*0.25}" r="{er*0.22}" fill="#fff"/>')
        inner_y = ey - er * 1.9 + (tilt if s == 1 else tilt) * (-1 if worried else 1)
        bx1, bx2 = x - s * er * 1.3, x + s * er * 1.3
        y1 = ey - er * 1.7 - (r * 0.08 if worried else 0)
        y2 = ey - er * 1.9 + (r * 0.05 if worried else 0)
        out.append(f'<path d="M{min(bx1,bx2)},{y1 if s==-1 else y2} Q{x},{ey-er*2.3} {max(bx1,bx2)},{y2 if s==-1 else y1}" '
                   f'stroke="{brow}" stroke-width="{bw}" fill="none" stroke-linecap="round"/>')
    return "".join(out)


def face(cx, cy, r, skin, iris="#5a3a22", smile=0.6, worried=False, wide=False, brow="#3a2a1f",
         blush=True, dust=False, wrinkles=False, brow_w=None):
    out = [f'<circle cx="{cx-r*0.98}" cy="{cy+r*0.08}" r="{r*0.17}" fill="{skin}" stroke="{LINE}" stroke-opacity="0.25"/>',
           f'<circle cx="{cx+r*0.98}" cy="{cy+r*0.08}" r="{r*0.17}" fill="{skin}" stroke="{LINE}" stroke-opacity="0.25"/>',
           f'<ellipse cx="{cx}" cy="{cy}" rx="{r}" ry="{r*1.05}" fill="{skin}"/>']
    if blush:
        out.append(f'<ellipse cx="{cx-r*0.55}" cy="{cy+r*0.38}" rx="{r*0.16}" ry="{r*0.1}" fill="#e98b7a" opacity="0.35"/>'
                   f'<ellipse cx="{cx+r*0.55}" cy="{cy+r*0.38}" rx="{r*0.16}" ry="{r*0.1}" fill="#e98b7a" opacity="0.35"/>')
    if dust:
        for x, y, rr in [(-0.6, 0.45, 0.07), (-0.48, 0.55, 0.05), (0.58, 0.5, 0.06), (0.47, 0.36, 0.04)]:
            out.append(f'<circle cx="{cx+x*r}" cy="{cy+y*r}" r="{rr*r}" fill="#9b7a55" opacity="0.45"/>')
    if wrinkles:
        out.append(f'<path d="M{cx-r*0.62},{cy+r*0.02} q{-r*0.1},{r*0.08} {-r*0.16},{r*0.02} M{cx+r*0.62},{cy+r*0.02} '
                   f'q{r*0.1},{r*0.08} {r*0.16},{r*0.02} M{cx-r*0.3},{cy-r*0.55} h{r*0.6}" stroke="{LINE}" '
                   f'stroke-opacity="0.35" stroke-width="{r*0.03}" fill="none" stroke-linecap="round"/>')
    out.append(eyes(cx, cy, r, iris, worried, wide, brow, brow_w))
    out.append(f'<path d="M{cx},{cy+r*0.12} q{-r*0.08},{r*0.18} {r*0.04},{r*0.22}" stroke="#b5755a" '
               f'stroke-width="{r*0.04}" fill="none" stroke-linecap="round"/>')
    if smile >= 0:
        out.append(f'<path d="M{cx-r*0.22},{cy+r*0.5} Q{cx},{cy+r*(0.5+0.18*smile)} {cx+r*0.22},{cy+r*0.5}" '
                   f'stroke="#9c4a3a" stroke-width="{r*0.05}" fill="none" stroke-linecap="round"/>')
    else:
        out.append(f'<path d="M{cx-r*0.16},{cy+r*0.56} Q{cx},{cy+r*0.48} {cx+r*0.16},{cy+r*0.56}" '
                   f'stroke="#9c4a3a" stroke-width="{r*0.05}" fill="none" stroke-linecap="round"/>')
    return "".join(out)


def short_hair(cx, cy, r, color):
    return (f'<path d="M{cx-r*1.02},{cy+r*0.05} C{cx-r*1.1},{cy-r*1.2} {cx+r*1.1},{cy-r*1.2} {cx+r*1.02},{cy+r*0.05} '
            f'C{cx+r*0.8},{cy-r*0.55} {cx+r*0.2},{cy-r*0.62} {cx-r*0.2},{cy-r*0.48} C{cx-r*0.5},{cy-r*0.65} '
            f'{cx-r*0.85},{cy-r*0.45} {cx-r*1.02},{cy+r*0.05} z" fill="{color}"/>')


def curly_hair_back(cx, cy, r, color):
    curls = [(-1.0, -0.2, .38), (1.0, -0.2, .38), (-0.95, 0.35, .33), (0.95, 0.35, .33), (-0.8, 0.8, .3),
             (0.8, 0.8, .3), (-1.3, 0.9, .32), (-1.45, 1.3, .3), (-1.3, 1.65, .26)]
    return "".join(f'<circle cx="{cx+x*r}" cy="{cy+y*r}" r="{s*r}" fill="{color}"/>' for x, y, s in curls)


def curly_hair_top(cx, cy, r, color, tie="#c9772f"):
    curls = [(-0.75, -0.65, .32), (-0.35, -0.9, .34), (0.1, -0.98, .34), (0.52, -0.85, .32), (0.85, -0.55, .3),
             (-0.95, -0.25, .27), (0.98, -0.2, .25), (-0.1, -0.7, .28), (0.35, -0.62, .24), (-0.5, -0.55, .24)]
    out = "".join(f'<circle cx="{cx+x*r}" cy="{cy+y*r}" r="{s*r}" fill="{color}"/>' for x, y, s in curls)
    return out + f'<ellipse cx="{cx-r*1.1}" cy="{cy+r*0.62}" rx="{r*0.14}" ry="{r*0.09}" fill="{tie}"/>'


def beard(cx, cy, r, color, full=False):
    depth = 1.15 if full else 0.35
    return (f'<path d="M{cx-r*0.95},{cy+r*0.05} C{cx-r*0.95},{cy+r*(0.9+depth*0.4)} {cx-r*0.4},{cy+r*(1.0+depth)} '
            f'{cx},{cy+r*(1.05+depth)} C{cx+r*0.4},{cy+r*(1.0+depth)} {cx+r*0.95},{cy+r*(0.9+depth*0.4)} '
            f'{cx+r*0.95},{cy+r*0.05} C{cx+r*0.8},{cy+r*0.5} {cx+r*0.45},{cy+r*0.35} {cx+r*0.3},{cy+r*0.42} '
            f'Q{cx},{cy+r*0.3} {cx-r*0.3},{cy+r*0.42} C{cx-r*0.45},{cy+r*0.35} {cx-r*0.8},{cy+r*0.5} '
            f'{cx-r*0.95},{cy+r*0.05} z" fill="{color}"/>'
            f'<path d="M{cx-r*0.2},{cy+r*0.62} Q{cx},{cy+r*0.72} {cx+r*0.2},{cy+r*0.62}" stroke="#9c4a3a" '
            f'stroke-width="{r*0.05}" fill="none" stroke-linecap="round"/>')


# ---------- bodies ----------

def body(cx, shoulder_y, hem_y, feet_y, width, tunic, skin, sash=None, mantle=None, long=False,
         arms=None, legs=True):
    w = width
    out = [f'<ellipse cx="{cx}" cy="{feet_y+6}" rx="{w*0.75}" ry="10" fill="#000" opacity="0.08"/>']
    if legs:
        for s in (-1, 1):
            out.append(f'<rect x="{cx+s*w*0.2-w*0.09}" y="{hem_y-10}" width="{w*0.18}" height="{feet_y-hem_y+8}" '
                       f'rx="{w*0.07}" fill="{skin}"/>'
                       f'<ellipse cx="{cx+s*w*0.2+s*w*0.04}" cy="{feet_y}" rx="{w*0.15}" ry="{w*0.06}" fill="#8a5a36"/>'
                       f'<path d="M{cx+s*w*0.2-w*0.09},{feet_y-w*0.12} l{w*0.18},{w*0.06}" stroke="#8a5a36" '
                       f'stroke-width="{w*0.035}"/>')
    flare = w * (0.62 if long else 0.56)
    out.append(f'<path d="M{cx-w*0.42},{shoulder_y+w*0.05} Q{cx},{shoulder_y-w*0.08} {cx+w*0.42},{shoulder_y+w*0.05} '
               f'L{cx+flare},{hem_y} Q{cx},{hem_y+w*0.06} {cx-flare},{hem_y} z" fill="{tunic}"/>'
               f'<path d="M{cx-w*0.12},{shoulder_y-w*0.02} Q{cx},{shoulder_y+w*0.14} {cx+w*0.12},{shoulder_y-w*0.02}" '
               f'stroke="{LINE}" stroke-opacity="0.35" stroke-width="2.5" fill="none"/>')
    if mantle:
        out.append(f'<path d="M{cx-w*0.44},{shoulder_y+w*0.04} L{cx-w*0.66},{hem_y-w*0.05} L{cx-w*0.3},{hem_y-w*0.12} '
                   f'L{cx-w*0.12},{shoulder_y+w*0.1} z" fill="{mantle}"/>'
                   f'<path d="M{cx+w*0.44},{shoulder_y+w*0.04} L{cx+w*0.62},{hem_y-w*0.4} L{cx+w*0.2},{shoulder_y+w*0.6} '
                   f'L{cx+w*0.12},{shoulder_y+w*0.1} z" fill="{mantle}"/>')
    if sash:
        sy = shoulder_y + (hem_y - shoulder_y) * 0.42
        out.append(f'<path d="M{cx-w*0.5},{sy} Q{cx},{sy+w*0.08} {cx+w*0.5},{sy} l0,{w*0.1} Q{cx},{sy+w*0.18} '
                   f'{cx-w*0.5},{sy+w*0.1} z" fill="{sash}"/>'
                   f'<path d="M{cx+w*0.18},{sy+w*0.12} l{w*0.04},{w*0.32} l{w*0.07},-{w*0.02} l-{w*0.02},-{w*0.3}" fill="{sash}"/>')
    for a in arms or []:
        out.append(a)
    return "".join(out)


def arm(x1, y1, x2, y2, sleeve, skin, w=26, bend=None):
    path = f"M{x1},{y1} Q{bend[0]},{bend[1]} {x2},{y2}" if bend else f"M{x1},{y1} L{x2},{y2}"
    return (f'<path d="{path}" stroke="{sleeve}" stroke-width="{w}" fill="none" stroke-linecap="round"/>'
            f'<circle cx="{x2}" cy="{y2}" r="{w*0.48}" fill="{skin}"/>')


def patch(x, y, s=1):
    return (f'<rect x="{x}" y="{y}" width="{18*s}" height="{14*s}" rx="2" fill="#9a8a6a" transform="rotate(-12 {x} {y})"/>'
            f'<rect x="{x}" y="{y}" width="{18*s}" height="{14*s}" rx="2" fill="none" stroke="#5e5040" '
            f'stroke-dasharray="3 2" stroke-width="1.4" transform="rotate(-12 {x} {y})"/>')


# ---------- props ----------

def bundle(x, y, s=1, color="#e8dcc4"):
    return (f'<ellipse cx="{x}" cy="{y}" rx="{30*s}" ry="{22*s}" fill="{color}" stroke="#b9a98c" stroke-width="2"/>'
            f'<path d="M{x-6*s},{y-20*s} q{6*s},-{10*s} {12*s},0" stroke="#b9a98c" stroke-width="{4*s}" fill="none"/>'
            f'<path d="M{x-22*s},{y+4*s} q{22*s},{10*s} {44*s},0" stroke="#b9a98c" stroke-width="1.5" fill="none"/>')


def linen_basket(x, y):
    return (f'<path d="M{x-48},{y-10} L{x+48},{y-10} L{x+38},{y+34} L{x-38},{y+34} z" fill="#c69a5b"/>'
            + "".join(f'<path d="M{x-46+i*12},{y-8} l-4,40" stroke="#a87c42" stroke-width="2"/>' for i in range(9))
            + f'<rect x="{x-40}" y="{y-26}" width="80" height="12" rx="5" fill="#f3ede0"/>'
              f'<rect x="{x-36}" y="{y-36}" width="72" height="12" rx="5" fill="#e3ecf2"/>')


def sandal(x, y):
    return (f'<ellipse cx="{x}" cy="{y}" rx="13" ry="28" fill="#8a5a36" transform="rotate(25 {x} {y})"/>'
            f'<path d="M{x-10},{y-6} q10,-12 20,0" stroke="#5a3b26" stroke-width="4" fill="none"/>')


def cart_wheel(x, y):
    return (f'<circle cx="{x}" cy="{y}" r="22" fill="none" stroke="#8a5a36" stroke-width="7"/>'
            + "".join(f'<line x1="{x}" y1="{y}" x2="{x+20*c}" y2="{y+20*s}" stroke="#8a5a36" stroke-width="4"/>'
                      for c, s in [(1, 0), (-1, 0), (0, 1), (0, -1)])
            + f'<circle cx="{x}" cy="{y}" r="5" fill="#5a3b26"/>')


def staff(x, top, bottom):
    return f'<line x1="{x}" y1="{top}" x2="{x}" y2="{bottom}" stroke="#7a5233" stroke-width="9" stroke-linecap="round"/>'


# ---------- characters ----------

def miri():
    skin, hair, tunic = "#c98e62", "#2e1d14", "#e2c79a"
    cx, hy, r = 256, 175, 62
    arms = [arm(205, 262, 236, 318, tunic, skin, bend=(196, 302)), arm(307, 262, 278, 318, tunic, skin, bend=(316, 302))]
    return (curly_hair_back(cx, hy, r, hair)
            + body(cx, 250, 410, 478, 150, tunic, skin, sash="#c9772f", arms=arms)
            + bundle(256, 312, 1.0) + f'<circle cx="236" cy="320" r="12" fill="{skin}"/><circle cx="278" cy="320" r="12" fill="{skin}"/>'
            + f'<rect x="248" y="226" width="16" height="24" fill="{skin}"/>'
            + face(cx, hy, r, skin, iris="#5a3a22", smile=0.8) + curly_hair_top(cx, hy, r, hair)), (cx, hy, r)


def nim():
    fur, cream, dark = "#d97a2b", "#f7e6cb", "#3a2418"
    cx, hy = 256, 230
    tail = (f'<path d="M300,430 C410,440 440,330 380,300 C360,360 330,400 290,400 z" fill="{fur}"/>'
            f'<path d="M380,300 C400,315 412,340 404,362 C392,346 380,330 366,322 z" fill="{cream}"/>')
    bodyp = (f'<ellipse cx="256" cy="485" rx="95" ry="10" fill="#000" opacity="0.08"/>'
             f'<path d="M200,470 C180,380 200,300 256,290 C312,300 332,380 312,470 z" fill="{fur}"/>'
             f'<path d="M228,470 C220,400 232,330 256,318 C280,330 292,400 284,470 z" fill="{cream}"/>'
             f'<ellipse cx="226" cy="472" rx="22" ry="11" fill="{dark}"/><ellipse cx="286" cy="472" rx="22" ry="11" fill="{dark}"/>')
    ears = "".join(f'<path d="M{cx+s*28},{hy-48} L{cx+s*92},{hy-160} L{cx+s*96},{hy-30} z" fill="{fur}"/>'
                   f'<path d="M{cx+s*40},{hy-52} L{cx+s*86},{hy-136} L{cx+s*86},{hy-44} z" fill="#f2c7b0"/>' for s in (-1, 1))
    head = (f'<path d="M{cx-92},{hy-10} C{cx-90},{hy-80} {cx+90},{hy-80} {cx+92},{hy-10} C{cx+80},{hy+50} {cx+30},{hy+78} '
            f'{cx},{hy+82} C{cx-30},{hy+78} {cx-80},{hy+50} {cx-92},{hy-10} z" fill="{fur}"/>'
            f'<path d="M{cx-70},{hy+12} C{cx-40},{hy+20} {cx-20},{hy+30} {cx},{hy+82} C{cx+20},{hy+30} {cx+40},{hy+20} '
            f'{cx+70},{hy+12} C{cx+50},{hy+60} {cx+20},{hy+80} {cx},{hy+82} C{cx-20},{hy+80} {cx-50},{hy+60} {cx-70},{hy+12} z" fill="{cream}"/>')
    eye = "".join(f'<ellipse cx="{cx+s*36}" cy="{hy-6}" rx="15" ry="18" fill="{dark}"/>'
                  f'<circle cx="{cx+s*36-5}" cy="{hy-13}" r="5" fill="#fff"/>' for s in (-1, 1))
    nose = (f'<ellipse cx="{cx}" cy="{hy+60}" rx="11" ry="8" fill="{dark}"/>'
            f'<path d="M{cx-12},{hy+72} Q{cx},{hy+80} {cx+12},{hy+72}" stroke="{dark}" stroke-width="3" fill="none"/>')
    whiskers = "".join(f'<path d="M{cx+s*24},{hy+58+d} q{s*30},{d*0.4} {s*58},{d}" stroke="{dark}" stroke-opacity="0.5" '
                       f'stroke-width="1.6" fill="none"/>' for s in (-1, 1) for d in (-6, 4))
    return tail + bodyp + ears + head + eye + nose + whiskers, (cx, hy - 45, 118)


def ima():
    skin, tunic, mantle = "#bf835a", "#b5553c", "#56708c"
    cx, hy, r = 256, 120, 44
    arms = [arm(214, 188, 196, 300, mantle, skin, w=24), arm(298, 188, 330, 280, tunic, skin, w=24, bend=(330, 230))]
    cover = (f'<path d="M{cx-r*1.25},{hy+r*0.4} C{cx-r*1.4},{hy-r*1.5} {cx+r*1.4},{hy-r*1.5} {cx+r*1.25},{hy+r*0.4} '
             f'L{cx+r*1.6},{hy+r*2.6} L{cx-r*1.6},{hy+r*2.6} z" fill="{mantle}"/>')
    fringe = (f'<path d="M{cx-r*0.95},{hy-r*0.1} C{cx-r*0.8},{hy-r*0.95} {cx+r*0.8},{hy-r*0.95} {cx+r*0.95},{hy-r*0.1} '
              f'C{cx+r*0.5},{hy-r*0.55} {cx-r*0.5},{hy-r*0.55} {cx-r*0.95},{hy-r*0.1} z" fill="#2b1c14"/>')
    return (body(cx, 175, 455, 482, 120, tunic, skin, sash="#e0b45a", long=True, arms=arms)
            + linen_basket(345, 268) + cover + f'<rect x="248" y="155" width="16" height="22" fill="{skin}"/>'
            + face(cx, hy, r, skin, smile=0.5, blush=False) + fringe), (cx, hy, r)


def tav():
    skin, hair, tunic = "#c48a5f", "#3b2618", "#7e8f4e"
    cx, hy, r = 256, 210, 58
    arms = [arm(210, 292, 230, 352, tunic, skin, w=24, bend=(198, 338)), arm(302, 292, 282, 352, tunic, skin, w=24, bend=(314, 338))]
    return (body(cx, 280, 420, 478, 132, tunic, skin, sash="#6b4a2e", arms=arms) + cart_wheel(256, 352)
            + f'<circle cx="232" cy="354" r="11" fill="{skin}"/><circle cx="280" cy="354" r="11" fill="{skin}"/>'
            + f'<rect x="248" y="258" width="16" height="24" fill="{skin}"/>'
            + face(cx, hy, r, skin, smile=0.7, wide=True, dust=True) + short_hair(cx, hy, r, hair)), (cx, hy, r)


def saba():
    skin, robe, mantle, white = "#b47a52", "#8a6a4a", "#5d4a3a", "#f1ece3"
    cx, hy, r = 256, 120, 44
    arms = [arm(212, 190, 200, 300, robe, skin, w=26), arm(300, 190, 322, 268, robe, skin, w=26, bend=(330, 225))]
    hair = (f'<ellipse cx="{cx-r*0.95}" cy="{hy-r*0.05}" rx="{r*0.26}" ry="{r*0.4}" fill="{white}"/>'
            f'<ellipse cx="{cx+r*0.95}" cy="{hy-r*0.05}" rx="{r*0.26}" ry="{r*0.4}" fill="{white}"/>')
    return (body(cx, 178, 455, 482, 124, robe, skin, sash="#c9a66b", mantle=mantle, long=True, arms=arms)
            + patch(318, 215) + sandal(330, 270) + f'<rect x="248" y="158" width="16" height="22" fill="{skin}"/>'
            + face(cx, hy, r, skin, smile=0.9, brow="#f1ece3", wrinkles=True, blush=False, brow_w=r * 0.12)
            + hair + beard(cx, hy, r, white, full=True)), (cx, hy, r)


def yonah():
    skin, hair, tunic = "#c08559", "#24170f", "#a9b8c2"
    cx, hy, r = 256, 175, 60
    arms = [arm(206, 262, 214, 380, tunic, skin, w=25), arm(306, 262, 310, 330, tunic, skin, w=25, bend=(336, 300))]
    return (body(cx, 250, 410, 478, 146, tunic, skin, sash="#6c7f8f", arms=arms) + bundle(320, 318, 0.85, "#efe3c8")
            + f'<rect x="248" y="228" width="16" height="24" fill="{skin}"/>'
            + face(cx, hy, r, skin, smile=0.45, wide=True, worried=True) + short_hair(cx, hy, r, hair)), (cx, hy, r)


def andrew():
    skin, hair, tunic, mantle = "#b97e55", "#2c1d14", "#d8c7a3", "#7c5b3a"
    cx, hy, r = 256, 120, 44
    arms = [arm(212, 190, 168, 268, tunic, skin, w=24, bend=(180, 220)), arm(300, 190, 344, 268, tunic, skin, w=24, bend=(332, 220))]
    return (body(cx, 178, 455, 482, 124, tunic, skin, sash="#7c5b3a", mantle=mantle, long=True, arms=arms)
            + f'<rect x="248" y="158" width="16" height="22" fill="{skin}"/>'
            + face(cx, hy, r, skin, smile=0.7, blush=False) + short_hair(cx, hy, r, hair) + beard(cx, hy, r, hair)), (cx, hy, r)


def philip():
    skin, hair, tunic, mantle = "#c2875c", "#3a2a20", "#e6d9bd", "#8a3b34"
    cx, hy, r = 256, 120, 44
    arms = [arm(212, 190, 196, 250, tunic, skin, w=24, bend=(184, 230)), arm(300, 190, 316, 250, tunic, skin, w=24, bend=(328, 230))]
    grey = (f'<ellipse cx="{cx-r*0.9}" cy="{hy-r*0.15}" rx="{r*0.16}" ry="{r*0.28}" fill="#9a948c"/>'
            f'<ellipse cx="{cx+r*0.9}" cy="{hy-r*0.15}" rx="{r*0.16}" ry="{r*0.28}" fill="#9a948c"/>')
    return (body(cx, 178, 455, 482, 116, tunic, skin, sash="#8a3b34", mantle=mantle, long=True, arms=arms)
            + f'<rect x="248" y="158" width="16" height="22" fill="{skin}"/>'
            + face(cx, hy, r, skin, smile=-1, worried=True, blush=False) + short_hair(cx, hy, r, hair)
            + grey + beard(cx, hy, r, hair)), (cx, hy, r)


def jesus():
    """From behind: hair, robe, mantle, open hands, staff. The face is never shown."""
    skin, hair, robe, mantle = "#b97e55", "#3b2618", "#eee6d6", "#6f87a0"
    cx, hy, r = 256, 120, 44
    head = (f'<ellipse cx="{cx}" cy="{hy}" rx="{r}" ry="{r*1.08}" fill="{hair}"/>'
            f'<path d="M{cx-r*0.95},{hy} C{cx-r*1.1},{hy+r*1.6} {cx+r*1.1},{hy+r*1.6} {cx+r*0.95},{hy} z" fill="{hair}"/>')
    arms = [arm(212, 192, 150, 262, robe, skin, w=26, bend=(170, 210)), arm(300, 192, 362, 262, robe, skin, w=26, bend=(342, 210))]
    drape = (f'<path d="M{cx-58},{185} C{cx-30},{260} {cx+40},{300} {cx+66},{420} L{cx+20},{440} C{cx},{340} {cx-40},{270} '
             f'{cx-70},{200} z" fill="{mantle}"/>')
    return (staff(372, 150, 482) + body(cx, 180, 455, 482, 126, robe, skin, long=True, arms=arms) + drape + head), (cx, hy + 20, 70)


CHARACTERS = {
    "Miri": dict(draw=miri, role="Lead; a young village girl who has three honey cakes",
                 from_script="Young girl; carries a small cloth bundle of three honey-date cakes; later the linen basket.",
                 design="About 8 years old, warm brown skin, dark curly hair tied back loosely with an ochre tie, "
                        "brown eyes, sand-coloured tunic with an ochre sash, holding a small cloth bundle."),
    "Nim": dict(draw=nim, role="Miri's small fox companion",
                from_script="A small fox (never a dog); oversized ears, twitching nose, tail, whiskers.",
                design="Small orange fox with oversized ears, cream chest and muzzle, big dark eyes, "
                       "bushy tail with a cream tip, sitting upright."),
    "Ima": dict(draw=ima, role="Miri's mother",
                from_script="Comes from the doorway with a basket of folded linen; warm but firm.",
                design="Woman in her thirties, warm brown skin, dark hair under a muted blue head covering, "
                       "terracotta dress with a golden sash, holding a basket of folded linen on her hip."),
    "Tav": dict(draw=tav, role="Village boy with a broken toy cart",
                from_script="A small boy with dust on his cheeks; his toy cart has one wooden wheel off.",
                design="About 6 years old, warm brown skin, short dark hair, dust on his cheeks, "
                       "olive-green tunic, holding a small wooden cart wheel."),
    "Saba": dict(draw=saba, role="Saba Elior, the elderly storyteller",
                 from_script="Old; sleeves patched ('more patch than sleeve'); repairs a sandal; eyes twinkle; sits under a fig tree.",
                 design="Elderly man, white beard, white hair at the sides, bushy white brows, kind smile, "
                        "brown robe with a darker mantle and a visibly patched sleeve, holding a sandal."),
    "Yonah": dict(draw=yonah, role="The boy with five barley loaves and two fish",
                  from_script="A boy about Miri's age; careful, bright-eyed, slightly nervous; small bundle tucked under his arm.",
                  design="About 8 years old, warm brown skin, short dark hair, bright slightly nervous eyes, "
                         "pale blue-grey tunic, small cloth lunch bundle tucked under one arm."),
    "Andrew": dict(draw=andrew, role="Disciple",
                   from_script="A disciple; gentle and steady with the children.",
                   design="Man in his thirties, short dark hair and beard, kind expression, "
                          "undyed tunic with a brown mantle, hands open."),
    "Philip": dict(draw=philip, role="Disciple",
                   from_script="A disciple; worried and practical about feeding the crowd.",
                   design="Lean man in his late thirties, short dark hair greying at the temples, short beard, "
                          "worried brows, cream tunic with a deep red mantle."),
    "Jesus": dict(draw=jesus, role="Shown only as hands, robe, and silhouette",
                  from_script="Seen from behind and to the side: robe moving in the wind, hands open, hand on a staff. "
                              "His face is never shown.",
                  design="Seen from behind only: shoulder-length dark hair, off-white robe, blue-grey mantle over one "
                         "shoulder, open hands, wooden staff. No face visible."),
}


def image_prompt(name, info):
    view = ("full body seen from behind, face not visible" if name == "Jesus"
            else "full body, front view, neutral standing pose")
    return (f"Character reference of {name}: {info['design']} {view}, plain warm parchment background, "
            f"{STYLE}, no text, no logo, no watermark.")


def render_png(svg_paths):
    """Render SVGs to square PNGs with macOS Quick Look; returns {svg: png} for those that worked."""
    if not shutil.which("qlmanage"):
        print("qlmanage not found: PNG files were not created (SVG files are still written).")
        return {}
    done = {}
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["qlmanage", "-t", "-s", str(SIZE), "-o", tmp, *map(str, svg_paths)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for svg in svg_paths:
            out = Path(tmp) / (svg.name + ".png")
            if out.exists():
                png = svg.with_suffix(".png")
                shutil.move(str(out), png)
                done[svg] = png
    return done


def write_gallery(data):
    """characters.html: every character's images, script details, design, and image prompt."""
    import html as h
    cards = "".join(
        f'<article><div class="imgs"><img src="{h.escape(d["full"])}" alt="{h.escape(n)} full body">'
        f'<img src="{h.escape(d["head"])}" alt="{h.escape(n)} close-up"></div><h2>{h.escape(n)}</h2>'
        f'<p class="role">{h.escape(d["role"])}</p><p><b>From the script:</b> {h.escape(d["from_script"])}</p>'
        f'<p><b>Design:</b> {h.escape(d["design"])}</p><details><summary>Image prompt</summary>'
        f'<p class="prompt">{h.escape(d["image_prompt"])}</p></details></article>' for n, d in data.items())
    (ROOT / "characters.html").write_text(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Character References</title><style>
:root{{--bg:#f6f1e8;--card:#fff;--text:#2b2118;--muted:#6b5d50;--line:#e6dccd}}
@media (prefers-color-scheme:dark){{:root{{--bg:#16130f;--card:#211c17;--text:#efe7dc;--muted:#b3a593;--line:#3a3128}}}}
body{{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif}}
main{{max-width:1200px;margin:0 auto;padding:24px 16px}}h1{{margin:0}}.muted{{color:var(--muted)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px;margin-top:20px}}
article{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px}}
.imgs{{display:grid;grid-template-columns:1fr 1fr;gap:8px}}img{{width:100%;border-radius:10px;display:block}}
h2{{margin:12px 0 0}}.role{{color:var(--muted);margin:2px 0 10px}}p{{margin:6px 0}}
.prompt{{font-size:13px;background:var(--bg);padding:8px;border-radius:8px}}summary{{cursor:pointer;color:var(--muted)}}
</style></head><body><main><h1>Character references</h1>
<p class="muted">Little Witnesses: "The Smallest Lunch". Proposed designs: full body and head close-up for each
character, as Seedance reference images. Replace with final artwork in characters.json.</p>
<div class="grid">{cards}</div></main></body></html>""")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    svgs, data = [], {}
    for name, info in CHARACTERS.items():
        art, (hx, hy, hr) = info["draw"]()
        key = name.lower()
        full, head = OUT / f"{key}_full.svg", OUT / f"{key}_head.svg"
        full.write_text(page(art))
        pad = hr * 1.9
        head.write_text(page(art, view=f"{hx-pad} {hy-pad*0.95} {pad*2} {pad*2}"))
        svgs += [full, head]
        data[name] = {"role": info["role"], "from_script": info["from_script"], "design": info["design"],
                      "image_prompt": image_prompt(name, info),
                      "full": f"assets/characters/{key}_full.png", "head": f"assets/characters/{key}_head.png"}
    pngs = render_png(svgs)
    for name in data:
        for kind in ("full", "head"):
            svg = OUT / Path(data[name][kind]).with_suffix(".svg").name
            if svg not in pngs:
                data[name][kind] = f"assets/characters/{svg.name}"
    (ROOT / "characters.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    write_gallery(data)
    print(f"Wrote {len(svgs)} SVGs and {len(pngs)} PNGs to {OUT.relative_to(ROOT)}/ and characters.json")


if __name__ == "__main__":
    main()
