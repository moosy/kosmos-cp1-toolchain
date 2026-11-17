"""Cheat Sheet CP1 als 2 A4-Seiten: eigener kleiner Tabellensatz -> SVG -> rsvg-convert -> PDF.
Markup in Zellen: **fett**, `Anzeige` (LED-Kasten), ★ (neu, farbig), ~mono~."""
import re, subprocess, sys
from xml.sax.saxutils import escape
from PIL import ImageFont

N = '/usr/share/fonts/noto/'
GR = 8.35                                   # Grundschrift pt
LH = GR * 1.30                             # Zeilenhöhe
F = {'n': (N + 'NotoSans-Regular.ttf', 'Noto Sans', 'normal'),
     'b': (N + 'NotoSans-Bold.ttf', 'Noto Sans', 'bold'),
     'm': (N + 'NotoSansMono-Regular.ttf', 'Noto Sans Mono', 'normal'),
     'led': (N + 'NotoSansMono-Bold.ttf', 'Noto Sans Mono', 'bold'),
     'star': (N + 'NotoSansSymbols2-Regular.ttf', 'Noto Sans Symbols2', 'normal'),
     'sym': (N + 'NotoSansSymbols-Regular.ttf', 'Noto Sans Symbols', 'normal')}
_cache = {}
def breite(txt, st, gr=GR):
    k = (st, gr)
    if k not in _cache: _cache[k] = ImageFont.truetype(F[st][0], int(gr * 20))
    return _cache[k].getlength(txt) / 20

FARBE = dict(tinte='#1F3A4D', zeile='#EEF2F5', neu='#B5410E', ledbg='#FBE7E3', ledfg='#9E1C0C', grau='#5A6872', ink='#1B2228')
W, H = 595.28, 841.89
RAND = 31.0
BR = W - 2 * RAND


def runs(s):
    out = []
    for t in re.split(r'(\*\*.+?\*\*|`.+?`|★|~.+?~|[→↔])', s):
        if not t: continue
        if t.startswith('**'): out.append((t[2:-2], 'b'))
        elif t.startswith('`'): out.append((t[1:-1], 'led'))
        elif t == '★': out.append(('★', 'star'))
        elif t in '→↔': out.append((t, 'sym'))
        elif t.startswith('~'): out.append((t[1:-1], 'm'))
        else: out.append((t, 'n'))
    return out


def umbrechen(s, w):
    """-> Zeilen: Liste von [(text, stil)]; LED-Kästen und mono bleiben ganz; Text bricht an Leerzeichen."""
    zeilen, z, x = [], [], 0.0
    for teil in s.split('\n'):
        for text, st in runs(teil):
            woerter = [text] if st in ('led', 'star', 'sym') else re.findall(r'\S+\s*|\s+', text)
            for wo in woerter:
                extra = 4 if st == 'led' else 0
                b = breite(wo, st) + extra
                if x + b > w and z and wo.strip():
                    zeilen.append(z); z, x = [], 0.0
                    wo = wo.lstrip() if st in ('n', 'm') else wo
                    b = breite(wo, st) + extra
                z.append((wo, st)); x += b
        zeilen.append(z); z, x = [], 0.0
    return [l for l in zeilen if l] or [[]]


class Seite:
    def __init__(s):
        s.el = []; s.y = RAND

    def rect(s, x, y, w, h, f, r=0):
        s.el.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" rx="{r}" fill="{f}"/>')

    def text(s, x, y, t, st='n', gr=GR, farbe=None):
        datei, fam, gew = F[st]
        farbe = farbe or {'led': FARBE['ledfg'], 'star': FARBE['neu']}.get(st, FARBE['ink'])
        s.el.append(f'<text x="{x:.2f}" y="{y:.2f}" font-family="{fam}" font-weight="{gew}" font-size="{gr}" fill="{farbe}" xml:space="preserve">{escape(t)}</text>')

    def zeile(s, x, y, z, farbe=None):
        for t, st in z:
            if st == 'led':
                b = breite(t, 'led')
                s.rect(x, y - GR * 0.86, b + 4, GR * 1.18, FARBE['ledbg'], 1.5)
                s.text(x + 2, y, t, 'led'); x += b + 4
            else:
                s.text(x, y, t, st, farbe=farbe); x += breite(t, st)

    def titel(s, links, rechts):
        s.text(RAND, s.y + 15, links, 'b', 16, FARBE['tinte'])
        b = breite(rechts, 'n', 8)
        s.text(W - RAND - b, s.y + 15, rechts, 'n', 8, FARBE['grau'])
        s.y += 22

    def absatz(s, t, farbe=None, gr=None):
        for z in umbrechen(t, BR):
            s.zeile(RAND, s.y + GR, z, farbe); s.y += LH
        s.y += 2

    def balken(s, t):
        s.y += 5
        s.rect(RAND, s.y, BR, 15, FARBE['tinte'])
        x = RAND + 4
        for text, st in runs(t):
            st2 = 'star' if st == 'star' else 'b'
            s.text(x, s.y + 11, text, st2, 10, '#FFFFFF'); x += breite(text, st2, 10)
        s.y += 17

    def tabelle(s, spalten, reihen, kopf=None):
        """spalten: Breiten in mm (letzte = Rest)"""
        ws = [c * 2.8346 for c in spalten[:-1]]; ws.append(BR - sum(ws))
        for i, r in enumerate(reihen):
            zellen = [umbrechen(c, w - 6) for c, w in zip(r, ws)]
            h = max(len(z) for z in zellen) * LH + 4
            if i % 2: s.rect(RAND, s.y, BR, h, FARBE['zeile'])
            x = RAND
            for z, w in zip(zellen, ws):
                yy = s.y + 2 + GR
                for l in z:
                    s.zeile(x + 3, yy, l); yy += LH
                x += w
            s.y += h

    def segbild(s, x, y, gr=1.0):
        """große 7-Segment-Stelle mit Segmentnamen und Werten; liefert Höhe"""
        L, D = 46 * gr, 8 * gr                       # Segmentlänge, -dicke
        seg = {'a': (x + D, y, L, D, 'h'), 'g': (x + D, y + L + D, L, D, 'h'), 'd': (x + D, y + 2 * L + 2 * D, L, D, 'h'),
               'f': (x, y + D, D, L, 'v'), 'b': (x + L + D, y + D, D, L, 'v'),
               'e': (x, y + L + 2 * D, D, L, 'v'), 'c': (x + L + D, y + L + 2 * D, D, L, 'v')}
        wert = dict(a=1, b=2, c=4, d=8, e=16, f=32, g=64)
        for k, (sx, sy, w, h, o) in seg.items():
            s.rect(sx + 0.8, sy + 0.8, w - 1.6, h - 1.6, FARBE['ledfg'], 2)
            t = f'{k} = {wert[k]}'
            if o == 'h':
                tx, ty = sx + w / 2 - breite(t, 'b') / 2, sy - 2.5
            else:
                tx = sx - breite(t, 'b') - 4 if k in 'fe' else sx + w + 4
                ty = sy + h / 2 + 3
            s.text(tx, ty, t, 'b', GR, FARBE['ink'])
        px, py = x + L + 2 * D + 4, y + 2 * L + 2.6 * D
        s.el.append(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="{D * 0.6:.2f}" fill="{FARBE["ledfg"]}"/>')
        s.text(px + 8, py + 3, 'Punkt = 128', 'b', GR, FARBE['ink'])
        return 2 * L + 3 * D

    def svg(s):
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}pt" height="{H}pt" viewBox="0 0 {W} {H}">'
                f'<rect width="{W}" height="{H}" fill="#FFFFFF"/>' + ''.join(s.el) + '</svg>')


# Aufruf: python3 satz.py [inhalt.py [ausgabe.pdf]]  (6.x: python3 satz.py inhalt6.py cp1-schnelluebersicht-6.pdf)
INHALT = sys.argv[1] if len(sys.argv) > 1 else 'inhalt.py'
AUSGABE = sys.argv[2] if len(sys.argv) > 2 else 'cp1-schnelluebersicht.pdf'
exec(open(INHALT, encoding='utf-8').read())       # definiert SEITEN: Liste von Funktionen(seite)
dateien = []
for i, f in enumerate(SEITEN, 1):
    sv = Seite(); f(sv)
    print(f'Seite {i}: Höhe {sv.y:.0f} von {H - RAND:.0f} pt', 'ZU LANG' if sv.y > H - RAND + 2 else '')
    fn = f'seite{i}.svg'; open(fn, 'w').write(sv.svg()); dateien.append(fn)
subprocess.run(['rsvg-convert', '-f', 'pdf', '-o', AUSGABE] + dateien, check=True)
