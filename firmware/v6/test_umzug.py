"""5.00: kosmos_remote.py gegen den Simulator. NIE-Rahmen und Antworten laufen wirklich über die simulierte
Leitung (wie kosmos_rc), FNI über das Pi-Modell pi_fni (wie kosmos_rc „F …“)."""
import sys, os
_hier = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.join(_hier, '..', '..'), os.path.join(_hier, '..', 'fernsteuerung'), os.path.join(_hier, '..', '..', 'remote'), _hier):
    sys.path.insert(0, _p)                     # Repo-Wurzel bzw. ältere Ablagen
from sim48 import CP1, SPIFlash, text
from pi_fni import FNIPi
import kosmos_remote as kr
ROM = open(os.path.join(_hier, next((a for a in sys.argv[1:] if a.endswith('.bin')), 'cp1v6-eeprom.bin')), 'rb').read()
fl = SPIFlash()
m = CP1(ROM, flash=fl)
m.bis(m.us + 100_000)

class PiLeitung:
    def __init__(self): self.lows = []
    def __call__(self, t):
        for a, b in self.lows[-60:]:
            if a <= t < b: return 0
        return 1
m.pi = PiLeitung()

class Sim(kr.Leitung):
    def __init__(self): self.lock = kr.threading.RLock()

    def _rc(self, auftrag, bits):
        t = m.us + 2_000
        if auftrag == '-':
            m.pi.lows.append((t, t + 3500)); ende = t + 3500
        else:
            b = bytes.fromhex(auftrag)
            m.pi.lows.append((t, t + 8500)); t += 8500 + 300
            for byte in b:
                for i in range(8):
                    d = 50 if byte >> i & 1 else 150
                    m.pi.lows.append((t, t + d)); t += d + 50
            ende = t
        if bits == 0:
            m.bis(ende + 200); return []
        m.bis(ende + 6_000 + 3_000 * (bits // 8))
        log = [(tt, l) for tt, l in m.p1_log if tt >= ende]
        return [round(t2 - t1) for (t1, l1), (t2, l2) in zip(log, log[1:]) if l1 == 0 and l2 == 1][:bits]

    def _fni_zeile(self, zeile):
        teile = zeile.split()
        richtung, anf, anz, kopf = teile[1], int(teile[2]), int(teile[3]), bytes.fromhex(teile[4])
        daten = bytes.fromhex(teile[5]) if len(teile) > 5 else b''
        pi = FNIPi({'E': 'ein', 'A': 'aus', 'K': 'komplett', 'N': 'namen', 'V': 'verz'}[richtung], tuple(kopf), daten)
        m.geraet = pi
        t0 = m.us
        m.bis(m.us + 300_000, halt=lambda mm: mm.takt() == 0)
        if m.takt() != 0:
            m.geraet = None; return ['FEHLER', 'nicht_angenommen']
        m.bis(m.us + 30_000_000, halt=lambda mm: pi.fertig)
        m.geraet = None
        if pi.fehler: return ['FEHLER', pi.fehler.replace(' ', '_')]
        if richtung == 'N': return ['OK', b''.join(bytes([b, 0]) + n for b, n in pi.namen).hex()]
        if richtung == 'V': return ['OK', b''.join(bytes([n]) + e for n, e in pi.verz).hex()]
        return ['OK'] + ([bytes(pi.empfangen).hex()] if richtung != 'E' else [])

kr.time.sleep = lambda s: m.bis(m.us + s * 1e6)
L = Sim(); f = 0
def pruef(n, ok, i=''):
    global f; print(('  ok   ' if ok else '  FEHL ') + n + ('' if ok else f'  [{i}]')); f += not ok
import glob, verz6
"""6.00 Umzug: alle gesicherten Projekte (.cp1 aus 5.07) in einen leeren Flash einspielen, wie es der Pi tut.
Aufruf: python3 test_umzug.py [ROM] ordner/  (ohne Ordner: übersprungen – die Projektdateien liegen nicht im Repo)"""
ordner = next((a for a in sys.argv[1:] if os.path.isdir(a)), None)
if not ordner:
    print('kein Projektordner angegeben – übersprungen'); sys.exit(0)
dateien = sorted(glob.glob(os.path.join(ordner, '*.cp1')))
nummern = {}
for d in dateien:
    p = kr.projekt_lesen(d)
    t0 = m.us
    nr = L.projekt_einspielen(p)
    nummern[p['name']] = nr
    print(f'   {os.path.basename(d)} -> Projekt {nr:02d} ({len(p["baenke"])} Bänke, {(m.us - t0) / 1e6:.0f} s Simulationszeit)')
v = L.verzeichnis()
pruef(f'{len(dateien)} Projekte im Verzeichnis, Namen stimmen', sorted(e['name'] for e in v['projekte']) == sorted(nummern), str(v['projekte']))
pruef('keine Bank doppelt vergeben', len({e['bank'] + k for e in v['projekte'] for k in range(e['res'])}) == sum(e['res'] for e in v['projekte']))
pruef('Autoboot = Minenflug', v['autoboot'] == nummern.get('Minenflug'), v['autoboot'])
for d in dateien:
    p = kr.projekt_lesen(d)
    q = L.projekt_sichern(nummern[p['name']])
    gleich = all(q['baenke'][k]['zellen'] == p['baenke'][k]['zellen'] and q['baenke'][k]['labels'] == p['baenke'][k]['labels']
                 and q['baenke'][k]['bilder'] == p['baenke'][k]['bilder'] for k in range(len(p['baenke'])))
    pruef(f'{p["name"]}: zurückgelesen = Datei (Zellen, Labels, Bilder, Start)', gleich and len(q['baenke']) == len(p['baenke']) and q['start'] == p['start'])
print('Einschalten: Autoboot Minenflug')
m2 = CP1(ROM, True, vorlauf=False, flash=fl); m2.bis(1_900_000)
pruef('„bot nn“ beim Einschalten', text(m2.anzeige()) == f"bot {nummern['Minenflug']:02d}", text(m2.anzeige()))
m2.bis(m2.us + 4_000_000)
pruef('Minenflug läuft (Projekt geladen, S_PBANK/S_PRES gesetzt)', m2.ram[0x5f] == next(e['bank'] for e in v['projekte'] if e['name'] == 'Minenflug') and m2.ram[0x5e] == 4, f'{text(m2.anzeige())} {m2.ram[0x5f]} {m2.ram[0x5e]}')
print('ALLES OK' if not f else f'{f} FEHLER'); sys.exit(1 if f else 0)
