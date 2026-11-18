"""6.22: Bank leeren ($30) – Pi und CP1 leeren die reservierten Bänke eines Projekts, damit keine alten
Inhalte (z. B. 5.x-Reste nach dem Umstieg) darin stehen bleiben. Leitung wie in test_projekt."""
import sys, os
_hier = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.join(_hier, '..', '..'), os.path.join(_hier, '..', 'fernsteuerung'), os.path.join(_hier, '..', '..', 'remote'), _hier, os.path.join(_hier, 'pi')):  # pi/: Pi-Software 6.x im Repo
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
def projekt(name, start, baenke, autoboot=False):
    out = []
    for prog, labels, bilder, anz in baenke:
        out.append({'zellen': [list(prog.get(n, (0, 0))) for n in range(256)], 'labels': {f'{a:03d}': n for a, n in labels.items()},
                    'bilder': [{'name': n, 'segmente': list(b)} for n, b in bilder], 'anzeige': list(anz) if anz else None})
    return {'format': kr.PROJEKT_FORMAT, 'version': kr.PROJEKT_VERSION, 'name': name, 'start': start, 'autoboot': autoboot,
            'baenke': out}

import verz6

def alt_sektor(text, gen):
    s = verz6.projektbank(bytes([7, 7, 7, 7]) * 40, name=text)
    s[0x210] = gen
    return bytes(s)
def altlast(bank, text):
    """wie im Gerät nach 5.x: beide Sektoren beschrieben und gültig (Generation 1 und 2)"""
    a = bank * 0x2000
    fl.m[a:a + 0x1000] = alt_sektor(text, 1)
    fl.m[a + 0x1000:a + 0x2000] = alt_sektor(text, 2)
def ganz_ff(bank):
    a = bank * 0x2000
    return fl.m[a:a + 0x2000] == bytes([0xFF]) * 0x2000

print('6.22: Ausgangslage wie im Gerät nach dem Umstieg (5.x-Reste, kein Verzeichnis)')
verz6.setzen(fl, 0, verz6.projektbank(b'\x01\x02', name='alt Bank 0'))
for b in list(range(4, 16)) + [40]: altlast(b, f'alt {b}')
pruef('Reste in Bank 4..15 gültig, kein Verzeichnis', all(verz6.gueltig(fl, b) is not None for b in range(4, 16)) and verz6.lesen(fl) is None)

print('$30 Bank leeren')
t0 = m.us
L.bank_leeren(13)
dauer = (m.us - t0) / 1e6
pruef('Bank 13: beide Sektoren FF, gilt als leer', ganz_ff(13) and verz6.gueltig(fl, 13) is None)
pruef('Nachbarn 12 und 14 unberührt', verz6.gueltig(fl, 12) is not None and verz6.gueltig(fl, 14) is not None and not ganz_ff(12) and not ganz_ff(14))
pruef(f'fertig: F_JOB = 0, Anzeige ohne Fehler ({dauer:.1f} s Simulationszeit)', L.ram(kr.F_JOB, 1)[0] == 0 and not text(m.anzeige()).startswith('F'), text(m.anzeige()))
L.bank_leeren(13)
pruef('leere Bank noch einmal leeren schadet nicht', ganz_ff(13))
L.verzeichnis(); a = text(m.anzeige())
L.bank_leeren(40)
pruef(f'nach einem Flash-Lesen („{a}“ bleibt stehen) kein falscher Fehler', ganz_ff(40) and a.startswith('F'), a)

print('Pi: Projekt einspielen leert die unbenutzten reservierten Bänke')
eins = projekt('Eins', 0, [({0: (1, 0), 1: (2, 3)}, {}, [], None)])
nr = L.projekt_einspielen(eins, 1)
v = verz6.lesen(fl)
pruef('Projekt 1 = Bank 4, 4 Bänke reserviert', nr == 1 and v['projekte'][1]['bank'] == 4 and v['projekte'][1]['res'] == 4, str(v))
pruef('Bank 4: das Projekt', verz6.gueltig(fl, 4)[0:4] == bytes([1, 0, 2, 3]))
pruef('Bänke 5..7: leer (vorher 5.x-Reste)', all(ganz_ff(b) for b in (5, 6, 7)))
pruef('Bank 8: Reste unberührt (gehört nicht zum Projekt)', verz6.gueltig(fl, 8) is not None)
p = L.projekt_sichern(1)
pruef('projekt-sichern: nur die eine echte Bank', len(p['baenke']) == 1, str(len(p['baenke'])))
zwei = projekt('Zwei', 0, [({0: (5, 5)}, {}, [], None), ({0: (6, 6)}, {}, [], None)])
L.projekt_einspielen(zwei, 1)
pruef('vorhandenes Projekt mit 2 Bänken neu: Bank 4, 5 belegt, 6 und 7 leer', verz6.gueltig(fl, 5)[0:2] == bytes([6, 6]) and ganz_ff(6) and ganz_ff(7))
L.projekt_einspielen(eins, 1)
pruef('wieder mit 1 Bank: Bank 5 jetzt leer', ganz_ff(5) and verz6.gueltig(fl, 4)[0:2] == bytes([1, 0]))

print('CP1: neues Projekt anlegen (CAS bzw. $80) leert alle reservierten Bänke')
L.laden({0: (9, 9), 1: (8, 8)}, 0, 1)
L.flash_speichern(2)
v = verz6.lesen(fl)
pruef('Projekt 2 = Bank 8, 4 Bänke', v['projekte'][2]['bank'] == 8 and v['projekte'][2]['res'] == 4, str(v['projekte']))
pruef('Bank 8: das RAM', verz6.gueltig(fl, 8)[0:4] == bytes([9, 9, 8, 8]))
pruef('Bänke 9..11: leer (vorher 5.x-Reste)', all(ganz_ff(b) for b in (9, 10, 11)), str([verz6.gueltig(fl, b) is not None for b in (9, 10, 11)]))
pruef('Bank 12: Reste unberührt', verz6.gueltig(fl, 12) is not None)
L.laden({0: (4, 4)}, 0, 0)
L.flash_speichern(2)
pruef('vorhandenes Projekt noch einmal speichern: nur Bank 8 neu, kein Leeren nötig', verz6.gueltig(fl, 8)[0:2] == bytes([4, 4]) and verz6.gueltig(fl, 12) is not None)
L.flash_laden(1)
z = L.speichern(0, 1)
pruef('Projekt 1 lädt weiterhin', z == {0: (1, 0), 1: (2, 3)}, str(z))

print('bank-leeren über die Befehlszeile')
kr.Leitung = Sim; kr.server_laeuft = lambda port=None: False
vorher = bytes(fl.m[0x2000:0x4000])
pruef('Bank 0..3 nur mit --auch-system', kr.main(['bank-leeren', '1']) == 2 and bytes(fl.m[0x2000:0x4000]) == vorher)
pruef('bank-leeren 14 15', kr.main(['bank-leeren', '14', '15']) == 0 and ganz_ff(14) and ganz_ff(15))
print('ALLES OK' if not f else f'{f} FEHLER'); sys.exit(1 if f else 0)
