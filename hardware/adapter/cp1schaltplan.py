#!/usr/bin/env python3
"""Schaltplan des CP1-EA-Adapters als SVG mit echten Leitungen, direkt aus der Netzliste in cp1adapter.py.
Leitungen per Gitter-Router (rechtwinklig, Kreuzungen ohne Punkt, Abzweige mit Punkt); GND/VCC als Symbole.
Aufruf: python3 cp1schaltplan.py > schaltplan.svg"""
import heapq, itertools
from cp1adapter import NETZ, SIG, j1_pin

E = 10                       # px je Gitterschritt
U2N = {1: '/OE', 10: 'GND', 11: 'LE', 20: 'VCC'}
U2N.update({2 + i: f'D{i}' for i in range(8)}); U2N.update({19 - i: f'Q{i}' for i in range(8)})
U3N = {1: 'RDY', 2: 'A12', 14: 'GND', 20: '/CE', 21: 'A10', 22: '/OE', 23: 'A11', 24: 'A9', 25: 'A8', 26: 'NC',
       27: '/WE', 28: 'VCC'}
U3N.update({10 - i: f'A{i}' for i in range(8)})
U3N.update({p: f'I/O{i}' for i, p in enumerate((11, 12, 13, 15, 16, 17, 18, 19))})
POWER = {'GND', 'VCC'}

boxen = []                   # (x0, y0, x1, y1, ref, wert, farbe)
pins = {}                    # (ref, nr) -> (x, y, seite, name)
texte = []
gesperrt = set()


def box(x0, y0, x1, y1, ref, wert, farbe='#ffe'):
    boxen.append((x0, y0, x1, y1, ref, wert, farbe))
    for x in range(x0, x1 + 1):
        for y in range(y0 - 2, y1 + 1):
            gesperrt.add((x, y))


def pin(ref, nr, x, y, seite, name=''):
    """Pinende (x, y); Stummel 3 Schritte Richtung Box"""
    pins[(ref, nr)] = (x, y, seite, name)
    d = 1 if seite == 'l' else -1 if seite == 'r' else 0
    dv = 1 if seite == 'o' else -1 if seite == 'u' else 0
    for i in range(1, 3):
        gesperrt.add((x + d * i, y + dv * i))


def dip(x0, y0, breite, ref, wert, n, namen):
    h = n // 2
    box(x0, y0, x0 + breite, y0 + 2 * h + 2, ref, wert)
    for i in range(1, h + 1):
        pin(ref, i, x0 - 3, y0 + 2 * i, 'l', namen.get(i, ''))
        pin(ref, n + 1 - i, x0 + breite + 3, y0 + 2 * i, 'r', namen.get(n + 1 - i, ''))


# --- Platzierung ---
Y0 = 20
dip(46, Y0, 12, 'U1', '8049 (ZIF-40)', 40, SIG)
box(10, Y0, 17, Y0 + 42, 'J1', 'Kabel → CP1, DIP 1–20', '#eef')
box(88, Y0, 95, Y0 + 42, 'J1', 'Kabel → CP1, DIP 21–40', '#eef')
for k in range(1, 21):
    pin('J1', j1_pin(k), 20, Y0 + 2 * k, 'r', f'DIP{k}')
    pin('J1', j1_pin(41 - k), 85, Y0 + 2 * k, 'l', f'DIP{41 - k}')
# U2/U3 als logische Symbole: Datenbus von oben, Q0-7 -> A0-7 waagrecht
YU = 86
box(24, YU, 42, YU + 24, 'U2', '74HCT573')
for i in range(8):
    pin('U2', 2 + i, 26 + 2 * i, YU - 3, 'o', f'D{i}')
    pin('U2', 19 - i, 45, YU + 4 + 2 * i, 'r', f'Q{i}')
for nr, y in ((11, 6), (1, 10), (20, 14), (10, 18)):
    pin('U2', nr, 21, YU + y, 'l', U2N[nr])
box(54, YU, 74, YU + 26, 'U3', 'AT28C64B')
for i, nr in enumerate((11, 12, 13, 15, 16, 17, 18, 19)):
    pin('U3', nr, 56 + 2 * i, YU - 3, 'o', f'I/O{i}')
for i in range(8):
    pin('U3', 10 - i, 51, YU + 4 + 2 * i, 'l', f'A{i}')
pin('U3', 20, 51, YU + 22, 'l', '/CE'); pin('U3', 22, 51, YU + 24, 'l', '/OE')
for nr, y in ((25, 2), (24, 4), (21, 6), (23, 8), (2, 10), (27, 14), (1, 16), (26, 18), (28, 20), (14, 22)):
    pin('U3', nr, 77, YU + y, 'r', U3N[nr])
for ref, y in (('JP2', YU + 4), ('JP3', YU + 16)):
    box(90, y, 96, y + 8, ref, 'Bank ' + ('A11' if ref == 'JP2' else 'A12'), '#eef')
    for i, nm in enumerate(('0', ref == 'JP2' and 'A11' or 'A12', '1')):
        pin(ref, i + 1, 87, y + 2 + 2 * i, 'l', nm)
box(2, 4, 8, 12, 'JP1', 'EA', '#eef')
for i, nm in enumerate(('ROM', 'EA', 'EEPROM')):
    pin('JP1', i + 1, 11, 6 + 2 * i, 'r', nm)
# Quarz und Lastkondensatoren über U1
zweipol = {}                  # ref -> (x, y oben, y unten, typ, wert)


def zp(ref, x, y, typ, wert):
    zweipol[ref] = (x, y, y + 6, typ, wert)
    pins[(ref, 1)] = (x, y, 'o', ''); pins[(ref, 2)] = (x, y + 6, 'u', '')
    for yy in range(y + 1, y + 6):
        gesperrt.add((x, yy))
        gesperrt.add((x - 1, yy)); gesperrt.add((x + 1, yy))


zp('Y1', 32, 4, 'Q', '6 MHz')
zp('C1', 26, 4, 'C', '22p')
zp('C2', 38, 4, 'C', '22p')
for i, (ref, wert, typ) in enumerate((('C3', '100n (U1)', 'C'), ('C4', '100n (U2)', 'C'), ('C5', '100n (U3)', 'C'),
                                      ('C6', '10µ', 'CP'))):
    zp(ref, 106 + 10 * i, 24, typ, wert)
BREITE, HOEHE = 150, 124

# --- Netze ---
netze = {}
nc = []
for k, n in NETZ.items():
    if k in pins:
        netze.setdefault(n, []).append(k)
for k in pins:
    if k not in NETZ:
        nc.append(k)
power = [(k, n) for n, ks in netze.items() if n in POWER for k in ks]
AUSSEN = {'l': (-1, 0), 'r': (1, 0), 'o': (0, -1), 'u': (0, 1)}
for (ref, nr), n in power:          # Platz fürs Symbol nach außen freihalten
    x, y, s, _ = pins[(ref, nr)]
    dx, dy = AUSSEN[s]
    for i in (1, 2, 3):
        gesperrt.add((x + dx * i, y + dy * i))
for k in nc:
    gesperrt.add(pins[k][:2])

kanten = {}                         # frozenset(p, q) -> net
an = {}                             # punkt -> {net: set(richtungen)}
endpunkt = {}                       # pinpunkt -> net
for n, ks in netze.items():
    for k in ks:
        endpunkt[pins[k][:2]] = n
D = {'R': (1, 0), 'L': (-1, 0), 'D': (0, 1), 'U': (0, -1)}
GEGEN = {'R': 'L', 'L': 'R', 'U': 'D', 'D': 'U'}
ACHSE = {'R': 'h', 'L': 'h', 'U': 'v', 'D': 'v'}
AUSGANG = {'l': 'L', 'r': 'R', 'o': 'U', 'u': 'D'}       # Richtung vom Pinende weg


def fremd(p, net):
    return {m: r for m, r in an.get(p, {}).items() if m != net}


def kreuzbar(p, net, richtung):
    """net darf p in richtung gerade durchqueren"""
    f = fremd(p, net)
    if not f:
        return True
    if len(f) > 1 or p in endpunkt:
        return False
    (r,) = f.values()
    quer = {'h': {'U', 'D'}, 'v': {'L', 'R'}}[ACHSE[richtung]]
    return r == quer and not an.get(p, {}).get(net)


def route(net, baum, ziel):
    zx, zy = ziel
    h = lambda p: abs(p[0] - zx) + abs(p[1] - zy)
    offen, cnt, best, vor = [], itertools.count(), {}, {}
    for p in baum:
        if fremd(p, net):
            continue
        for r in D:
            if p in endpunkt and (net, p) and r != AUSGANG[pin_seite[p]]:
                continue
            s = (p, r, False)
            best[s] = 0
            heapq.heappush(offen, (h(p), next(cnt), s))
    while offen:
        _, _, s = heapq.heappop(offen)
        p, r, gezw = s
        c0 = best[s]
        richt = [r] if gezw else [x for x in D if x != GEGEN[r]]
        for nr in richt:
            if p not in baum or s in vor:
                pass
            q = (p[0] + D[nr][0], p[1] + D[nr][1])
            if not (0 <= q[0] <= BREITE and 0 <= q[1] <= HOEHE):
                continue
            if frozenset((p, q)) in kanten:
                continue
            if q == ziel:
                if nr != GEGEN[AUSGANG[pin_seite[q]]]:
                    continue
                pfad = [q, p]
                while s in vor:
                    s = vor[s]
                    pfad.append(s[0])
                return pfad[::-1]
            if q in gesperrt or q in endpunkt:
                continue
            f = fremd(q, net)
            if f and not kreuzbar(q, net, nr):
                continue
            k = c0 + 1 + (4 if nr != r and p not in baum else 0) + (6 if f else 0)
            ns = (q, nr, bool(f))
            if k < best.get(ns, 1e9):
                best[ns] = k
                vor[ns] = s
                heapq.heappush(offen, (k + h(q), next(cnt), ns))
    return None


pin_seite = {pins[k][:2]: pins[k][2] for k in pins}


def belege(net, pfad, wert=True):
    for a, b in zip(pfad, pfad[1:]):
        r = [x for x, d in D.items() if (a[0] + d[0], a[1] + d[1]) == b][0]
        if wert:
            kanten[frozenset((a, b))] = net
            an.setdefault(a, {}).setdefault(net, set()).add(r)
            an.setdefault(b, {}).setdefault(net, set()).add(GEGEN[r])
        else:
            kanten.pop(frozenset((a, b)), None)
            for p in (a, b):
                an.get(p, {}).pop(net, None)


def netz_routen(net):
    ps = [pins[k][:2] for k in netze[net]]
    baum = {ps[0]}
    rest = ps[1:]
    pfade = []
    while rest:
        rest.sort(key=lambda z: min(abs(z[0] - b[0]) + abs(z[1] - b[1]) for b in baum))
        z = rest.pop(0)
        p = route(net, baum, z)
        if p is None:
            for pf in pfade:
                belege(net, pf, False)
            return None
        belege(net, p)
        pfade.append(p)
        baum |= set(p)
    return pfade


def spanne(n):
    ps = [pins[k][:2] for k in netze[n]]
    return max(p[0] for p in ps) - min(p[0] for p in ps) + max(p[1] for p in ps) - min(p[1] for p in ps)


reihe = sorted((n for n in netze if n not in POWER and len(netze[n]) > 1), key=lambda n: (len(netze[n]) > 2, spanne(n)))
for runde in range(80):
    erg, fehl = {}, None
    for n in reihe:
        p = netz_routen(n)
        if p is None:
            fehl = n
            break
        erg[n] = p
    if fehl is None:
        break
    for n, pf in erg.items():
        for p in pf:
            belege(n, p, False)
    reihe.remove(fehl); reihe.insert(0, fehl)
else:
    raise SystemExit('Schaltplan-Routing gescheitert: ' + fehl)

# --- Zeichnen ---
o = []
P = lambda v: v * E
txt = lambda x, y, s, a='start', g=11, w='normal', c='#000': o.append(
    f'<text x="{x}" y="{y}" font-size="{g}" text-anchor="{a}" font-weight="{w}" fill="{c}">{s}</text>')
lin = lambda x1, y1, x2, y2, c='#000', sw=1.3: o.append(
    f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{c}" stroke-width="{sw}" stroke-linecap="round"/>')
for x0, y0, x1, y1, ref, wert, f in boxen:
    o.append(f'<rect x="{P(x0)}" y="{P(y0)}" width="{P(x1 - x0)}" height="{P(y1 - y0)}" fill="{f}" stroke="#000" stroke-width="1.6"/>')
    oben = any(r == ref and pp[2] == 'o' for (r, _), pp in pins.items())      # Pins oben -> Name in die Box
    ty = P(y0 + y1) / 2 + 6 if oben else P(y0) - 16
    txt(P(x0 + x1) / 2, ty, ref, 'middle', 15 if oben else 13, 'bold'); txt(P(x0 + x1) / 2, ty + (16 if oben else 12), wert, 'middle', 11 if oben else 10)
for (ref, nr), (x, y, s, name) in pins.items():
    if ref in zweipol:
        continue
    if s == 'o':
        lin(P(x), P(y), P(x), P(y + 3))
        o.append(f'<text x="{P(x) + 4}" y="{P(y + 3) + 6}" font-size="10" text-anchor="end" '
                 f'transform="rotate(-90 {P(x) + 4} {P(y + 3) + 6})">{name}</text>')
        txt(P(x) + 3, P(y + 1.5) + 3, str(nr), 'start', 8, c='#555')
        continue
    d = 1 if s == 'l' else -1
    lin(P(x), P(y), P(x + 3 * d), P(y))
    txt(P(x + 3 * d) + 3 * d, P(y) + 4, name, 'start' if d > 0 else 'end', 10)
    txt(P(x + 1.5 * d), P(y) - 3, str(nr), 'middle', 8, c='#555')
for ref, (x, y, y2, typ, wert) in zweipol.items():
    X = P(x)
    lin(X, P(y), X, P(y) + 22); lin(X, P(y2) - 22, X, P(y2))
    if typ == 'Q':
        o.append(f'<rect x="{X - 7}" y="{P(y) + 25}" width="14" height="10" fill="none" stroke="#000" stroke-width="1.5"/>')
        lin(X - 10, P(y) + 22, X + 10, P(y) + 22, sw=2); lin(X - 10, P(y2) - 22, X + 10, P(y2) - 22, sw=2)
    else:
        lin(X - 10, P(y) + 22, X + 10, P(y) + 22, sw=2.5)
        if typ == 'CP':
            o.append(f'<path d="M{X - 10},{P(y2) - 18} Q{X},{P(y2) - 27} {X + 10},{P(y2) - 18}" fill="none" stroke="#000" stroke-width="2.5"/>')
            txt(X - 14, P(y) + 20, '+', 'middle', 11)
        else:
            lin(X - 10, P(y2) - 22, X + 10, P(y2) - 22, sw=2.5)
    txt(X + 13, P(y) + 30, ref, 'start', 11, 'bold'); txt(X + 13, P(y) + 42, wert, 'start', 9)
# Leitungen
grad = {}
for e, n in kanten.items():
    a, b = tuple(e)
    lin(P(a[0]), P(a[1]), P(b[0]), P(b[1]), '#063', 1.4)
    for p in (a, b):
        grad[(p, n)] = grad.get((p, n), 0) + 1
for (p, n), g in grad.items():
    if g + (1 if endpunkt.get(p) == n else 0) >= 3:
        o.append(f'<circle cx="{P(p[0])}" cy="{P(p[1])}" r="3.2" fill="#063"/>')
# Netznamen an den Pinenden der CPU zur Orientierung
for (ref, nr), (x, y, s, name) in pins.items():
    if ref == 'U1' and NETZ.get((ref, nr)) not in POWER:
        pass
# Power-Symbole, vom Pin weg nach außen
for (ref, nr), n in power:
    x, y, s, _ = pins[(ref, nr)]
    dx, dy = AUSSEN[s]
    X, Y = P(x), P(y)
    c = '#06c' if n == 'GND' else '#b00'
    bar = lambda t, w, sw=2: lin(X + dx * t - dy * w, Y + dy * t - dx * w, X + dx * t + dy * w, Y + dy * t + dx * w, c, sw)
    lin(X, Y, X + dx * 12, Y + dy * 12, c)
    if n == 'GND':
        bar(12, 7); bar(16, 4.5); bar(20, 2)
    else:
        bar(12, 7)
        tx, ty = X + dx * 16, Y + dy * 16 + (4 if dy == 0 else (-2 if dy < 0 else 10))
        txt(tx, ty, 'VCC', 'start' if dx > 0 else 'end' if dx < 0 else 'middle', 9, 'bold', c)
for k in nc:
    x, y = pins[k][:2]
    X, Y = P(x), P(y)
    lin(X - 4, Y - 4, X + 4, Y + 4, '#888', 1.5); lin(X - 4, Y + 4, X + 4, Y - 4, '#888', 1.5)
txt(P(100), P(6), 'Kosmos CP1 – EA-Adapter v1 (2026-11-02)', 'start', 16, 'bold')
for i, h in enumerate(['Punkt = Verbindung, Kreuzung ohne Punkt = keine Verbindung, × = unbeschaltet.',
                       'J1 ist ein Wannenstecker 2×20, hier in der Reihenfolge des DIP-Pfostensteckers im CP1-Sockel',
                       'gezeichnet (kleine Zahl = Pin am Wannenstecker; Ader 1 → DIP 1, Ader 2 → DIP 40 …).',
                       'XTAL1/2 und EA gehen nicht zum CP1: Quarz auf dem Adapter, EA am Jumper JP1.',
                       'JP1 nur ausgeschaltet umstecken: 1-2 Masken-ROM, 2-3 EEPROM. JP2/JP3: 4 Bänke à 2 KB.',
                       'VDD (DIP 26) wird nur durchgereicht. C3–C6 sitzen an den jeweiligen ICs.']):
    txt(P(100), P(46) + i * 16, h, 'start', 11)
print(f'<svg xmlns="http://www.w3.org/2000/svg" width="{P(BREITE)}" height="{P(HOEHE) + 10}" '
      f'font-family="DejaVu Sans, sans-serif"><rect width="100%" height="100%" fill="#fff"/>' + ''.join(o) + '</svg>')
