#!/usr/bin/env python3
"""Draw one SVG diagram per camera term into assets/camera/ and write camera_angles.json.

camera_angles.json maps each camera term to its image link. Replace any link with your own
image (a relative path or a full URL) and check_camera.py will use it.
"""

import json
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "assets" / "camera"

SKY, GROUND, HILL = "#dbe7f3", "#cdb894", "#a9c18f"
SKIN, HAIR, SHIRT, PANTS = "#f0c9a4", "#5a3b26", "#4f7cac", "#3b4a5a"
CAM, ARROW, LINE = "#d9534f", "#2a7ae2", "#7a8796"


def svg(body, view="0 0 320 180", defs=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view}" width="320" height="180">'
            f'<defs>{defs}<marker id="ah" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" '
            f'markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{ARROW}"/>'
            f'</marker><filter id="blur"><feGaussianBlur stdDeviation="2.2"/></filter></defs>'
            f'{body}</svg>')


def person(cx=160, top=40, h=100, shirt=SHIRT):
    """A front-facing figure; top = top of head, h = full height."""
    s = h / 100
    def X(v): return cx + v * s
    def Y(v): return top + v * s
    return (
        f'<g>'
        f'<rect x="{X(-8)}" y="{Y(55)}" width="{7*s}" height="{45*s}" fill="{PANTS}"/>'
        f'<rect x="{X(1)}" y="{Y(55)}" width="{7*s}" height="{45*s}" fill="{PANTS}"/>'
        f'<rect x="{X(-15)}" y="{Y(21)}" width="{5*s}" height="{31*s}" rx="{2*s}" fill="{shirt}"/>'
        f'<rect x="{X(10)}" y="{Y(21)}" width="{5*s}" height="{31*s}" rx="{2*s}" fill="{shirt}"/>'
        f'<rect x="{X(-10)}" y="{Y(20)}" width="{20*s}" height="{36*s}" rx="{3*s}" fill="{shirt}"/>'
        f'<rect x="{X(-1.5)}" y="{Y(17)}" width="{3*s}" height="{4*s}" fill="{SKIN}"/>'
        f'<circle cx="{X(0)}" cy="{Y(9)}" r="{9*s}" fill="{SKIN}"/>'
        f'<path d="M{X(-9)},{Y(8)} A{9*s},{9*s} 0 0 1 {X(9)},{Y(8)} Q{X(0)},{Y(3)} {X(-9)},{Y(8)} z" fill="{HAIR}"/>'
        f'<line x1="{X(-5)}" y1="{Y(5.6)}" x2="{X(-2.2)}" y2="{Y(5.2)}" stroke="{HAIR}" stroke-width="{0.6*s}"/>'
        f'<line x1="{X(2.2)}" y1="{Y(5.2)}" x2="{X(5)}" y2="{Y(5.6)}" stroke="{HAIR}" stroke-width="{0.6*s}"/>'
        f'<circle cx="{X(-3.5)}" cy="{Y(8)}" r="{1.4*s}" fill="#fff"/><circle cx="{X(-3.4)}" cy="{Y(8.1)}" r="{0.75*s}" fill="#222"/>'
        f'<circle cx="{X(3.5)}" cy="{Y(8)}" r="{1.4*s}" fill="#fff"/><circle cx="{X(3.6)}" cy="{Y(8.1)}" r="{0.75*s}" fill="#222"/>'
        f'<path d="M{X(0)},{Y(9)} L{X(-0.8)},{Y(11.2)} L{X(0.6)},{Y(11.2)}" fill="none" stroke="#c9967a" stroke-width="{0.5*s}"/>'
        f'<path d="M{X(-2.6)},{Y(13.4)} Q{X(0)},{Y(15.4)} {X(2.6)},{Y(13.4)}" fill="none" stroke="#a5523f" stroke-width="{0.7*s}"/>'
        f'</g>')


def world(extra=""):
    return (f'<rect x="-2000" y="-2000" width="4320" height="2140" fill="{SKY}"/>'
            f'<rect x="-2000" y="140" width="4320" height="2000" fill="{GROUND}"/>'
            f'<rect x="-30" y="70" width="60" height="70" fill="#b98a5c"/><path d="M-38,72 L0,40 L38,72 z" fill="#8c5a3c"/>'
            f'<rect x="290" y="95" width="10" height="45" fill="#7a5233"/><circle cx="295" cy="85" r="26" fill="#6f9a5a"/>'
            f'{extra}{person()}')


def crop(x, y, w, h, extra=""):
    """Frame a 16:9 crop of the world, as a shot size does."""
    return svg(world(extra), view=f"{x} {y} {w} {h}")


def camera(x, y, rot=0, scale=1):
    return (f'<g transform="translate({x},{y}) rotate({rot}) scale({scale})">'
            f'<rect x="-14" y="-9" width="22" height="18" rx="3" fill="{CAM}"/>'
            f'<path d="M8,-6 L20,-11 L20,11 L8,6 z" fill="{CAM}"/>'
            f'<circle cx="-6" cy="-12" r="4" fill="{CAM}"/><circle cx="3" cy="-12" r="4" fill="{CAM}"/></g>')


def top_person(x, y, r=13):
    """A person seen from above: shoulders and head."""
    return (f'<ellipse cx="{x}" cy="{y}" rx="{r*1.4}" ry="{r*0.7}" fill="{SHIRT}"/>'
            f'<circle cx="{x}" cy="{y}" r="{r*0.6}" fill="{HAIR}"/>')


def arrow(d, dash=False, width=3):
    extra = ' stroke-dasharray="6 5"' if dash else ""
    return (f'<path d="{d}" fill="none" stroke="{ARROW}" stroke-width="{width}"{extra} '
            f'marker-end="url(#ah)"/>')


def sight(x1, y1, x2, y2):
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{LINE}" stroke-width="1.5" stroke-dasharray="4 4"/>'


def floor_plan(body):
    return svg(f'<rect width="320" height="180" fill="#eef2f6"/>'
               f'<path d="M0,0 H320 M0,180" stroke="#dde3ea"/>{body}')


def side_view(body):
    return svg(f'<rect width="320" height="180" fill="{SKY}"/><rect y="160" width="320" height="20" fill="{GROUND}"/>{body}')


def ots(mirror=False):
    flip = ' transform="translate(320,0) scale(-1,1)"' if mirror else ""
    inner = (f'<svg x="0" y="0" width="320" height="180" viewBox="112 34 110 62">{world()}</svg>'
             f'<g filter="url(#blur)"><ellipse cx="40" cy="190" rx="95" ry="70" fill="{PANTS}"/>'
             f'<circle cx="62" cy="88" r="46" fill="{HAIR}"/></g>')
    return f'<g{flip}>{inner}</g>'


def images():
    img = {}
    # Shot sizes: the same world, cropped tighter each time.
    img["Establishing shot"] = svg(
        f'<rect width="320" height="180" fill="{SKY}"/><circle cx="270" cy="34" r="16" fill="#f6d36b"/>'
        f'<path d="M0,120 Q80,70 160,110 T320,100 V180 H0 z" fill="{HILL}"/>'
        f'<rect y="138" width="320" height="42" fill="{GROUND}"/>'
        + "".join(f'<rect x="{x}" y="{118-h}" width="22" height="{h}" fill="#b98a5c"/>'
                  f'<path d="M{x-4},{120-h} L{x+11},{106-h} L{x+26},{120-h} z" fill="#8c5a3c"/>'
                  for x, h in [(40, 14), (78, 18), (120, 12), (200, 16), (236, 20)])
        + person(cx=160, top=128, h=14))
    img["Wide shot"] = crop(-120, -100, 560, 315)
    img["Long shot"] = crop(40, 22, 240, 135)
    img["Medium long shot"] = crop(80, 30, 160, 90)
    img["Medium shot"] = crop(104, 34, 112, 63)
    img["Medium close-up"] = crop(126, 36, 67.5, 38)
    img["Close-up"] = crop(138.7, 37.5, 42.7, 24)
    img["Big close-up"] = crop(147.6, 42, 24.9, 14)
    img["Extreme close-up"] = crop(154.7, 45, 10.7, 6)

    # Framing.
    two = person(120) + person(200, shirt="#8a6bb0")
    img["Two-shot"] = svg(f'<rect x="-500" y="-500" width="1400" height="640" fill="{SKY}"/>'
                          f'<rect x="-500" y="140" width="1400" height="400" fill="{GROUND}"/>{two}',
                          view="80 30 160 90")
    three = person(105) + person(160, shirt="#8a6bb0") + person(215, shirt="#5e9e74")
    img["Three-shot"] = svg(f'<rect x="-500" y="-500" width="1400" height="640" fill="{SKY}"/>'
                            f'<rect x="-500" y="140" width="1400" height="400" fill="{GROUND}"/>{three}',
                            view="70 28 180 101")
    img["Over-the-shoulder shot"] = svg(ots())
    img["Shot/reverse shot"] = svg(
        f'<rect width="320" height="180" fill="#eef2f6"/>'
        f'<svg x="8" y="45" width="140" height="79" viewBox="0 0 320 180">{ots()}</svg>'
        f'<svg x="172" y="45" width="140" height="79" viewBox="0 0 320 180">{ots(mirror=True)}</svg>'
        + arrow("M140,140 Q160,160 180,140", width=2.5)
        + arrow("M180,36 Q160,16 140,36", width=2.5))
    img["Point-of-view shot"] = svg(
        f'<radialGradient id="vig"><stop offset="60%" stop-color="#000" stop-opacity="0"/>'
        f'<stop offset="100%" stop-color="#000" stop-opacity="0.55"/></radialGradient>'
        f'<svg width="320" height="180" viewBox="80 30 160 90">{world()}</svg>'
        f'<ellipse cx="60" cy="185" rx="38" ry="26" fill="{SKIN}"/><ellipse cx="260" cy="185" rx="38" ry="26" fill="{SKIN}"/>'
        f'<rect width="320" height="180" fill="url(#vig)"/>')
    img["Insert shot"] = svg(
        f'<rect width="320" height="180" fill="#e9dcc6"/>'
        f'<ellipse cx="160" cy="98" rx="70" ry="44" fill="#e8e1d2" stroke="#b9a98c" stroke-width="3"/>'
        + "".join(f'<circle cx="{x}" cy="{y}" r="15" fill="#c98d4a"/><circle cx="{x}" cy="{y}" r="5" fill="#a46a2f"/>'
                  for x, y in [(132, 96), (164, 84), (190, 104)])
        + f'<ellipse cx="78" cy="132" rx="40" ry="24" fill="{SKIN}"/><ellipse cx="242" cy="132" rx="40" ry="24" fill="{SKIN}"/>')

    # Angles (side view: camera position relative to the subject).
    subject = person(cx=215, top=62, h=98)
    img["Eye-level shot"] = side_view(subject + sight(80, 71, 205, 71) + camera(64, 71))
    img["High-angle shot"] = side_view(subject + sight(84, 34, 207, 68) + camera(70, 30, rot=16))
    img["Low-angle shot"] = side_view(subject + sight(86, 150, 207, 74) + camera(70, 150, rot=-32))
    img["Overhead shot"] = side_view(person(cx=200, top=86, h=74) + sight(200, 38, 200, 84) + camera(200, 22, rot=90))
    img["Aerial shot"] = svg(
        f'<rect width="320" height="180" fill="{SKY}"/><path d="M0,140 Q100,110 200,135 T320,128 V180 H0 z" fill="{HILL}"/>'
        f'<rect y="152" width="320" height="28" fill="{GROUND}"/>' + person(cx=210, top=134, h=18)
        + f'<path d="M78,52 L170,150 L250,150 z" fill="{ARROW}" fill-opacity="0.12"/>'
        + f'<line x1="50" y1="34" x2="106" y2="34" stroke="{PANTS}" stroke-width="3"/>'
        + f'<ellipse cx="50" cy="31" rx="13" ry="3" fill="{LINE}"/><ellipse cx="106" cy="31" rx="13" ry="3" fill="{LINE}"/>'
        + camera(78, 44, rot=50, scale=0.8))

    # Movements (floor plan unless the move is vertical).
    cam, subj = camera(80, 90), top_person(240, 90)
    img["Static shot"] = floor_plan(subj + "".join(
        f'<line x1="80" y1="90" x2="{x}" y2="{y}" stroke="{PANTS}" stroke-width="3"/>'
        for x, y in [(56, 66), (56, 114), (108, 90)]) + cam)
    img["Pan"] = floor_plan(subj + sight(100, 90, 226, 90) + cam
                            + arrow("M80,52 A38,38 0 0 1 117,82") + arrow("M80,128 A38,38 0 0 0 117,98"))
    img["Tilt"] = side_view(person(cx=230, top=62, h=98) + camera(80, 100)
                            + arrow("M104,60 A44,44 0 0 1 124,96") + arrow("M104,140 A44,44 0 0 0 124,104"))
    img["Tracking shot"] = floor_plan(top_person(170, 60) + camera(170, 135, rot=-90)
                                      + arrow("M70,60 H140") + arrow("M70,135 H140"))
    img["Push-in"] = floor_plan(subj + cam + arrow("M110,90 H205"))
    img["Pull-back"] = floor_plan(top_person(160, 90) + camera(110, 90) + arrow("M86,90 H20"))
    img["Crane shot"] = side_view(
        person(cx=240, top=62, h=98) + f'<rect x="40" y="140" width="40" height="20" fill="{PANTS}"/>'
        f'<line x1="60" y1="140" x2="140" y2="50" stroke="{PANTS}" stroke-width="5"/>'
        + camera(150, 46, rot=20) + arrow("M178,30 V100") + arrow("M178,100 V30"))
    img["Arc shot"] = floor_plan(top_person(170, 90)
                                 + '<circle cx="170" cy="90" r="62" fill="none" stroke="#9fb3c8" stroke-dasharray="5 5"/>'
                                 + camera(108, 90) + arrow("M112,56 A62,62 0 0 1 200,36"))
    img["Zoom"] = svg(f'<rect width="320" height="180" fill="#eef2f6"/>'
                      f'<svg x="60" y="34" width="200" height="112" viewBox="99.5 32 121 68">{world()}</svg>'
                      f'<rect x="20" y="12" width="280" height="156" fill="none" stroke="{LINE}" stroke-width="3" stroke-dasharray="8 6"/>'
                      f'<rect x="60" y="34" width="200" height="112" fill="none" stroke="{ARROW}" stroke-width="3"/>'
                      + arrow("M28,20 L56,38") + arrow("M292,20 L264,38") + arrow("M28,160 L56,142") + arrow("M292,160 L264,142"))
    img["Dolly zoom"] = floor_plan(top_person(240, 90) + camera(150, 90) + arrow("M126,90 H40")
                                   + f'<path d="M170,90 L300,40 M170,90 L300,140" stroke="{LINE}" stroke-width="2"/>'
                                   + f'<path d="M170,90 L300,62 M170,90 L300,118" stroke="{ARROW}" stroke-width="2"/>')

    # Focus.
    bg = person(cx=240, top=58, h=60, shirt="#8a6bb0") + '<circle cx="60" cy="70" r="30" fill="#6f9a5a"/>'
    fg = person(cx=120, top=40, h=140)
    base = f'<rect width="320" height="180" fill="{SKY}"/><rect y="118" width="320" height="62" fill="{GROUND}"/>'
    img["Shallow focus"] = svg(base + f'<g filter="url(#blur)">{bg}</g>' + fg)
    img["Deep focus"] = svg(base + bg + fg)
    img["Rack focus"] = svg(base + bg + f'<g filter="url(#blur)">{fg}</g>' + arrow("M150,52 Q200,20 236,54"))
    return img


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    mapping = {}
    for term, content in images().items():
        name = term.lower().replace("/", "-").replace(" ", "-") + ".svg"
        (OUT / name).write_text(content)
        mapping[term] = f"assets/camera/{name}"
    (ROOT / "camera_angles.json").write_text(json.dumps(mapping, indent=2) + "\n")
    print(f"Wrote {len(mapping)} images to {OUT.relative_to(ROOT)}/ and camera_angles.json")


if __name__ == "__main__":
    main()
