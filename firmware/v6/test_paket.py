"""5.00: kosmos_remote.py gegen den Simulator. NIE-Rahmen und Antworten laufen wirklich über die simulierte
Leitung (wie kosmos_rc), FNI über das Pi-Modell pi_fni (wie kosmos_rc „F …“)."""
import sys, os
_hier = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.join(_hier, '..', '..'), os.path.join(_hier, '..', 'fernsteuerung'), os.path.join(_hier, '..', '..', 'remote'), _hier):
    sys.path.insert(0, _p)                     # Repo-Wurzel bzw. ältere Ablagen
from sim48 import CP1, SPIFlash, text
from pi_fni import FNIPi
import kosmos_remote as kr
ROM = open(os.path.join(_hier, sys.argv[1] if len(sys.argv) > 1 else 'cp1v6-eeprom.bin'), 'rb').read()
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
import tempfile, verz6
"""6.10: Overlay-Pakete im Pi-Assembler (.bereich, >>kern, >>teil k name, LADE name) bis zum Lauf im CP1"""
Q = '''// Overlay-Probe: Kern zählt, Teile setzen Startwerte
.bereich 128-255
>>kern
>start:
LADE eins
>zurueck:
LDA wert
ADD #1
ABS wert
LADE zwei
>ende:
HLT
>wert:
# 0
>>teil 1 eins
>los:
AKO 10
ABS wert
SPU zurueck
>>teil 2 zwei
>los:
LDA wert
ADD #100
ABS wert
SPU ende
'''
print('Assembler')
r = kr.paket_assemblieren(Q)
pruef('Teile: eins 3 Zellen, zwei 4 Zellen; Bereich 128–255', r['teile'] == [{'k': 1, 'name': 'eins', 'laenge': 3}, {'k': 2, 'name': 'zwei', 'laenge': 4}] and r['bereich'] == (128, 255), str(r['teile']))
pruef('LADE eins -> PSK 1 / PSK 3 / JOV 128', [r['zellen'][n] for n in range(3)] == [(36, 1), (36, 3), (48, 128)], str([r['zellen'][n] for n in range(3)]))
pruef('LADE zwei -> PSK 2 / PSK 4 / JOV 128', [r['zellen'][n] for n in range(6, 9)] == [(36, 2), (36, 4), (48, 128)])
pruef('„los“ in jedem Teil erlaubt, Kern-Namen (wert, zurueck) im Teil aufgelöst', r['baenke'][1]['zellen'][129] == (6, 10) and r['baenke'][1]['zellen'][130] == (9, 3) and r['baenke'][2]['namen'][128] == 'los')
pruef('Quelltext: Marken mit Adressen, auch in den Teilen', '>los:                       128' in r['quelltext'] and '>wert:                      010' in r['quelltext'])
for q, w in [('.bereich 128-130\n>>teil 1 a\nAKO 1\nAKO 2\nAKO 3\nAKO 4\n', 'passt nicht'), ('.bereich 10-20\nAKO 1\n15 AKO 2\n', 'Kern belegt'),
             ('.bereich 128-200\n>x:\nHLT\n>>teil 1 a\n>x:\nHLT\n', 'auch im Kern'), ('.bereich 128-200\nLADE b\n>>teil 1 a\nHLT\n', 'unbekannt'),
             ('>>teil 1 a\nHLT\n', '.bereich'), ('.bereich 128-200\n>>teil 1 a\n130 HLT\n', 'beginnen')]:
    try: kr.paket_assemblieren(q); pruef(f'Fehler erkannt: {w}', False)
    except ValueError as e: pruef(f'Fehler erkannt: {w}', w in str(e), str(e))
r2 = kr.paket_assemblieren('.bereich 128-200\n>>kern\nLADE a\n>>teil 1 a\nAKO 1\nLADE b\n>>teil 2 b\nHLT\n')
pruef('LADE auch in einem Teil (Teil a lädt Teil b, Länge 1)', r2['baenke'][1]['zellen'][129:132] if False else
      [r2['baenke'][1]['zellen'][n] for n in (129, 130, 131)] == [(36, 2), (36, 1), (48, 128)], [r2['baenke'][1]['zellen'][n] for n in (129, 130, 131)])
print('Befehlszeile: paket -> .cp1, projekt-einspielen, laden, laufen')
kr.Leitung = Sim; kr.server_laeuft = lambda port=None: False
d = tempfile.mkdtemp(dir=os.environ.get('TMPDIR'))
open(os.path.join(d, 'probe.koa'), 'w').write(Q)
pruef('paket probe.koa probe.cp1', kr.main(['paket', os.path.join(d, 'probe.koa'), os.path.join(d, 'probe.cp1'), '--name', 'Overlay']) == 0)
p = kr.projekt_lesen(os.path.join(d, 'probe.cp1'))
pruef('Projektdatei: 3 Bänke, Name Overlay, Quelltext dabei', len(p['baenke']) == 3 and p['name'] == 'Overlay' and '>>teil 2' in p['quelltext'])
nr = L.projekt_einspielen(p, 7)
v = verz6.lesen(fl)
pruef('Projekt 7: Bank 4, 4 Bänke reserviert, Teile in Bank 5 und 6', v['projekte'][7]['bank'] == 4 and v['projekte'][7]['res'] == 4 and verz6.gueltig(fl, 5)[256:262] == bytes([4, 10, 6, 10, 9, 3]), str(v['projekte']))
L.flash_laden(7)
m.drueck('run', m.us + 10_000, 120); m.bis(m.us + 3_000_000)
w = (m.intern.ram[20], m.intern.ram[21])
pruef('läuft: Teil eins setzt 10, Kern +1, Teil zwei +100 -> wert = 111, HLT (PC danach 10)', w == (0, 111) and m.ram[0x38] == 10, f'{w} PC {m.ram[0x38]} {L.anzeige()}')
print('ALLES OK' if not f else f'{f} FEHLER'); sys.exit(1 if f else 0)
