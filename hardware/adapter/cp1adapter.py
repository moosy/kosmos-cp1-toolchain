#!/usr/bin/env python3
"""CP1-EA-Adapter: 8049 im ZIF-Sockel, Flachband zum CP1-Sockel, AT28C64B + 74HCT573 als externer Programmspeicher.
Erzeugt cp1-adapter.kicad_pcb (Platzierung, Netze, Leiterbahnen per eigenem Gitter-Router, GND-Flächen).
Aufruf: python3 cp1adapter.py (mit KiCads Python)"""
import heapq, itertools, math, sys
import pcbnew

LIB = '/usr/share/kicad/footprints/'
MM = pcbnew.FromMM
OX, OY, W, H = 100.0, 100.0, 92.0, 76.0       # Platine
G = 1.27                                        # Routing-Gitter
CLR, TW, PW, VIA, VDRILL = 0.2, 0.25, 0.4, 0.8, 0.4

# DIP-40-Pin des 8049 -> Signal
SIG = {1: 'T0', 2: 'XTAL1', 3: 'XTAL2', 4: '/RESET', 5: '/SS', 6: '/INT', 7: 'EA', 8: '/RD', 9: '/PSEN', 10: '/WR',
       11: 'ALE', 20: 'GND', 25: 'PROG', 26: 'VDD', 39: 'T1', 40: 'VCC'}
SIG.update({12 + i: f'DB{i}' for i in range(8)})
SIG.update({21 + i: f'P2{i}' for i in range(4)})
SIG.update({27 + i: f'P1{i}' for i in range(8)})
SIG.update({35 + i: f'P2{4 + i}' for i in range(4)})


def j1_pin(dip):
    """Pin am 2x20-Wannenstecker für DIP-Pin am Pfostenstecker: Ader 1 -> Pin 1, Ader 2 -> Pin 40, Ader 3 -> Pin 2 …"""
    return 2 * dip - 1 if dip <= 20 else 2 * (41 - dip)


NETZ = {}            # (ref, pad) -> net


def verbinde(net, *pads):
    for p in pads:
        NETZ[p] = net


for d, s in SIG.items():
    if d in (2, 3, 7):                          # Quarz lokal, EA über Jumper – diese Adern bleiben offen
        verbinde(s, ('U1', d))
    else:
        verbinde(s, ('U1', d), ('J1', j1_pin(d)))
# 74HCT573: D0-7 = 2-9, Q0-7 = 19-12, /OE 1, LE 11
for i in range(8):
    verbinde(f'DB{i}', ('U2', 2 + i))
    verbinde(f'LA{i}', ('U2', 19 - i), ('U3', 10 - i))      # AT28C64B A0-A7 = Pin 10..3
for i, p in enumerate((11, 12, 13, 15, 16, 17, 18, 19)):
    verbinde(f'DB{i}', ('U3', p))
verbinde('ALE', ('U2', 11))
verbinde('GND', ('U2', 1), ('U2', 10), ('U3', 14), ('JP1', 1), ('JP2', 1), ('JP3', 1),
         ('C1', 2), ('C2', 2), ('C3', 2), ('C4', 2), ('C5', 2), ('C6', 2))
verbinde('VCC', ('U2', 20), ('U3', 28), ('U3', 27), ('JP1', 3), ('JP2', 3), ('JP3', 3),
         ('C3', 1), ('C4', 1), ('C5', 1), ('C6', 1))
verbinde('/PSEN', ('U3', 20), ('U3', 22))
verbinde('P20', ('U3', 25)); verbinde('P21', ('U3', 24)); verbinde('P22', ('U3', 21))
verbinde('A11', ('U3', 23), ('JP2', 2)); verbinde('A12', ('U3', 2), ('JP3', 2))
verbinde('EA', ('JP1', 2))
verbinde('XTAL1', ('Y1', 1), ('C1', 1)); verbinde('XTAL2', ('Y1', 2), ('C2', 1))
POWER = {'GND', 'VCC'}

# ref, lib, footprint, x, y (Pin 1), Drehung, Wert
TEILE = [
    ('J1', 'Connector_IDC', 'IDC-Header_2x20_P2.54mm_Vertical', 107.62, 115.24, 0, 'zum CP1 (Flachband)'),
    ('U1', 'Package_DIP', 'DIP-40_W15.24mm_Socket', 127.94, 115.24, 0, '8049 (ZIF-40)'),
    ('U2', 'Package_DIP', 'DIP-20_W7.62mm_Socket', 153.34, 115.24, 0, '74HCT573'),
    ('U3', 'Package_DIP', 'DIP-28_W15.24mm_Socket', 171.12, 115.24, 0, 'AT28C64B'),
    ('Y1', 'Crystal', 'Crystal_HC49-4H_Vertical', 119.38, 118.0, -90, '6 MHz'),
    ('C1', 'Capacitor_THT', 'C_Disc_D3.0mm_W1.6mm_P2.50mm', 116.84, 110.16, 0, '22p'),
    ('C2', 'Capacitor_THT', 'C_Disc_D3.0mm_W1.6mm_P2.50mm', 116.84, 130.48, 0, '22p'),
    ('C3', 'Capacitor_THT', 'C_Disc_D3.0mm_W1.6mm_P2.50mm', 148.26, 115.24, -90, '100n'),
    ('C4', 'Capacitor_THT', 'C_Disc_D3.0mm_W1.6mm_P2.50mm', 156.97, 109.22, 0, '100n'),
    ('C5', 'Capacitor_THT', 'C_Disc_D3.0mm_W1.6mm_P2.50mm', 181.28, 109.22, 0, '100n'),
    ('C6', 'Capacitor_THT', 'CP_Radial_D5.0mm_P2.00mm', 111.76, 106.35, 0, '10µ'),
    ('JP1', 'Connector_PinHeader_2.54mm', 'PinHeader_1x03_P2.54mm_Vertical', 130.48, 170.18, 90, 'EA'),
    ('JP2', 'Connector_PinHeader_2.54mm', 'PinHeader_1x03_P2.54mm_Vertical', 181.28, 156.21, 90, 'A11'),
    ('JP3', 'Connector_PinHeader_2.54mm', 'PinHeader_1x03_P2.54mm_Vertical', 168.58, 156.21, 90, 'A12'),
]
LOECHER = [(104.0, 104.0), (188.0, 104.0), (104.0, 173.0), (188.0, 173.0)]
TEXTE = [
    (160.0, 166.5, 'CP1 EA-Adapter v1', 1.5),
    (160.0, 169.5, '8049 -> 74HCT573 + AT28C64B', 1.0),
    (160.0, 171.5, 'J1: rote Ader = Pin 1', 1.0),
    (133.02, 167.0, 'ROM . . EEPROM', 1.0), (133.02, 173.0, 'EA', 1.0),
    (171.12, 159.3, 'A12', 1.0), (183.82, 159.3, 'A11', 1.0),
    (171.12, 153.2, '0 . . 1', 1.0), (183.82, 153.2, '0 . . 1', 1.0),
]


def baue():
    b = pcbnew.BOARD()
    ds = b.GetDesignSettings()
    nc = ds.m_NetSettings.GetDefaultNetclass()
    nc.SetClearance(MM(CLR)); nc.SetTrackWidth(MM(TW)); nc.SetViaDiameter(MM(VIA)); nc.SetViaDrill(MM(VDRILL))
    netze = {}
    for n in sorted(set(NETZ.values())):
        ni = pcbnew.NETINFO_ITEM(b, n)
        b.Add(ni)
        netze[n] = ni
    for ref, lib, fp, x, y, rot, wert in TEILE:
        f = pcbnew.FootprintLoad(LIB + lib + '.pretty', fp)
        f.SetReference(ref); f.SetValue(wert)
        f.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
        f.SetOrientationDegrees(rot)
        b.Add(f)
        for p in f.Pads():
            k = (ref, int(p.GetNumber())) if p.GetNumber().isdigit() else None
            if k in NETZ:
                p.SetNet(netze[NETZ[k]])
    for i, (x, y) in enumerate(LOECHER):
        f = pcbnew.FootprintLoad(LIB + 'MountingHole.pretty', 'MountingHole_3.2mm_M3')
        f.SetReference(f'H{i + 1}'); f.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
        f.Reference().SetVisible(False)
        b.Add(f)
    r = pcbnew.PCB_SHAPE(b)
    r.SetShape(pcbnew.SHAPE_T_RECT); r.SetLayer(pcbnew.Edge_Cuts); r.SetWidth(MM(0.1))
    r.SetStart(pcbnew.VECTOR2I(MM(OX), MM(OY))); r.SetEnd(pcbnew.VECTOR2I(MM(OX + W), MM(OY + H)))
    b.Add(r)
    for x, y, t, s in TEXTE:
        tx = pcbnew.PCB_TEXT(b)
        tx.SetText(t); tx.SetLayer(pcbnew.F_SilkS); tx.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
        tx.SetTextSize(pcbnew.VECTOR2I(MM(s), MM(s))); tx.SetTextThickness(MM(s * 0.15))
        b.Add(tx)
    return b, netze


# ---------- Router ----------
class Router:
    def __init__(self, b):
        self.nx, self.ny = int(W / G), int(H / G)
        self.pads = []                                # (net, x0, y0, x1, y1)
        self.padzelle = {}                            # (ref, nr) -> zelle
        self.netzpads = {}
        for f in b.GetFootprints():
            for p in f.Pads():
                bb = p.GetBoundingBox()
                r = tuple(pcbnew.ToMM(v) for v in (bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom()))
                net = p.GetNetname() or None
                self.pads.append((net,) + r)
                if net:
                    x, y = pcbnew.ToMM(p.GetPosition().x), pcbnew.ToMM(p.GetPosition().y)
                    z = (round((x - OX) / G), round((y - OY) / G))
                    zx, zy = OX + z[0] * G, OY + z[1] * G
                    if math.hypot(zx - x, zy - y) > (r[2] - r[0]) / 2 - 0.15:
                        sys.exit(f'Pad {f.GetReference()}-{p.GetNumber()} liegt nicht auf dem Gitter')
                    self.netzpads.setdefault(net, []).append(z)
        self.occ = [dict(), dict()]                   # Lage -> zelle -> net
        for net, zs in self.netzpads.items():
            for z in zs:
                self.occ[0][z] = self.occ[1][z] = net
        self.cache = {}

    def frei(self, net, x, y, rad):
        """Punkt (mm) mit Radius rad hält zu fremden Pads, Löchern und Rand Abstand"""
        k = (net, x, y, rad)
        if k in self.cache:
            return self.cache[k]
        ok = OX + 0.5 + rad <= x <= OX + W - 0.5 - rad and OY + 0.5 + rad <= y <= OY + H - 0.5 - rad
        for pn, x0, y0, x1, y1 in self.pads if ok else ():
            if pn == net:
                continue
            dx, dy = max(x0 - x, 0, x - x1), max(y0 - y, 0, y - y1)
            if math.hypot(dx, dy) < rad + CLR + (0.3 if pn is None else 0.02):
                ok = False
                break
        self.cache[k] = ok
        return ok

    def route(self, net, start, ziel, breite):
        """A* von der Zellmenge start (Lage, zelle) zu einer der Zellen ziel; liefert Pfad [(lage, zelle)]"""
        hw = breite / 2
        zs = set(ziel)
        h = lambda z: min(abs(z[0] - a[0]) + abs(z[1] - a[1]) for a in zs)
        offen, cnt, kosten, vor = [], itertools.count(), {}, {}
        for s in start:
            kosten[s] = 0
            heapq.heappush(offen, (h(s[1]), next(cnt), s))
        while offen:
            _, _, s = heapq.heappop(offen)
            l, (x, y) = s
            if (x, y) in zs:
                pfad = [s]
                while pfad[-1] in vor:
                    pfad.append(vor[pfad[-1]])
                return pfad[::-1]
            c0 = kosten[s]
            nach = []
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (x + dx, y + dy)
                if not (0 <= n[0] <= self.nx and 0 <= n[1] <= self.ny):
                    continue
                o = self.occ[l].get(n)
                if o not in (None, net):
                    continue
                mx, my = OX + (x + dx / 2) * G, OY + (y + dy / 2) * G
                if not (self.frei(net, OX + n[0] * G, OY + n[1] * G, hw) and self.frei(net, mx, my, hw)):
                    continue
                quer = (l == 0 and dx == 0) or (l == 1 and dy == 0)
                nach.append(((l, n), 3 if quer else 1))
            ol = 1 - l
            if self.occ[ol].get((x, y)) in (None, net) and self.occ[l].get((x, y)) in (None, net) \
                    and self.frei(net, OX + x * G, OY + y * G, VIA / 2):
                nach.append(((ol, (x, y)), 12))
            for n, k in nach:
                if c0 + k < kosten.get(n, 1e9):
                    kosten[n] = c0 + k
                    vor[n] = s
                    heapq.heappush(offen, (c0 + k + h(n[1]), next(cnt), n))
        return None

    def netz(self, net):
        zs = self.netzpads[net]
        breite = PW if net in POWER else TW
        baum = [(l, zs[0]) for l in (0, 1)]
        rest = zs[1:]
        pfade = []
        while rest:
            # nächstgelegenes Pad zuerst
            rest.sort(key=lambda z: min(abs(z[0] - b[1][0]) + abs(z[1] - b[1][1]) for b in baum))
            ziel = rest.pop(0)
            p = self.route(net, baum, [ziel], breite)
            if p is None:
                return None
            pfade.append(p)
            for s in p:
                if s not in baum:
                    baum.append(s)
            baum += [(l, ziel) for l in (0, 1)]
        return pfade

    def belege(self, net, pfade, wert):
        for p in pfade:
            for i, (l, z) in enumerate(p):
                if wert is None:
                    if z not in self.netzpads[net]:
                        self.occ[l].pop(z, None)
                else:
                    self.occ[l][z] = wert
                if i and p[i - 1][0] != l:          # Via belegt beide Lagen
                    for ll in (0, 1):
                        if wert is None:
                            if z not in self.netzpads[net]:
                                self.occ[ll].pop(z, None)
                        else:
                            self.occ[ll][z] = wert


def alles_routen(r):
    netze = sorted(r.netzpads, key=lambda n: (n in POWER, len(r.netzpads[n]) > 2,
                   max(z[0] for z in r.netzpads[n]) - min(z[0] for z in r.netzpads[n]) +
                   max(z[1] for z in r.netzpads[n]) - min(z[1] for z in r.netzpads[n])))
    netze = [n for n in netze if len(r.netzpads[n]) > 1]
    for runde in range(60):
        erg, fehl = {}, None
        for n in netze:
            p = r.netz(n)
            if p is None:
                fehl = n
                break
            erg[n] = p
            r.belege(n, p, n)
        if fehl is None:
            print(f'alle {len(netze)} Netze geroutet in Runde {runde + 1}')
            return erg
        print(f'Runde {runde + 1}: {fehl} scheitert nach {len(erg)} Netzen')
        for n, p in erg.items():
            r.belege(n, p, None)
        netze.remove(fehl)
        netze.insert(0, fehl)
    sys.exit('Routing gescheitert')


def schreibe(b, netze, erg):
    lagen = (pcbnew.F_Cu, pcbnew.B_Cu)
    vias = set()
    for net, pfade in erg.items():
        breite = MM(PW if net in POWER else TW)
        for p in pfade:
            # gerade Stücke je Lage zusammenfassen
            i = 0
            while i < len(p) - 1:
                l = p[i][0]
                if p[i + 1][0] != l:
                    vias.add((net, p[i][1]))
                    i += 1
                    continue
                j = i + 1
                d = (p[j][1][0] - p[i][1][0], p[j][1][1] - p[i][1][1])
                while j + 1 < len(p) and p[j + 1][0] == l and \
                        (p[j + 1][1][0] - p[j][1][0], p[j + 1][1][1] - p[j][1][1]) == d:
                    j += 1
                t = pcbnew.PCB_TRACK(b)
                t.SetStart(pcbnew.VECTOR2I(MM(OX + p[i][1][0] * G), MM(OY + p[i][1][1] * G)))
                t.SetEnd(pcbnew.VECTOR2I(MM(OX + p[j][1][0] * G), MM(OY + p[j][1][1] * G)))
                t.SetWidth(breite); t.SetLayer(lagen[l]); t.SetNet(netze[net])
                b.Add(t)
                i = j
    for net, z in vias:
        v = pcbnew.PCB_VIA(b)
        v.SetPosition(pcbnew.VECTOR2I(MM(OX + z[0] * G), MM(OY + z[1] * G)))
        v.SetWidth(MM(VIA)); v.SetDrill(MM(VDRILL)); v.SetNet(netze[net])
        b.Add(v)
    print(f'{len(vias)} Vias')
    # GND-Flächen auf beiden Lagen
    for lage in lagen:
        zn = pcbnew.ZONE(b)
        zn.SetLayer(lage); zn.SetNet(netze['GND'])
        zn.SetLocalClearance(MM(0.3)); zn.SetMinThickness(MM(0.25))
        zn.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        o = zn.Outline(); o.NewOutline()
        for x, y in ((OX, OY), (OX + W, OY), (OX + W, OY + H), (OX, OY + H)):
            o.Append(MM(x), MM(y))
        b.Add(zn)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())


if __name__ == '__main__':
    b, netze = baue()
    r = Router(b)
    erg = alles_routen(r)
    schreibe(b, netze, erg)
    b.Save('cp1-adapter.kicad_pcb')
    print('gespeichert')
