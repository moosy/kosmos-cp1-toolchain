"""5.00: kosmos_remote.py gegen den Simulator. NIE-Rahmen und Antworten laufen wirklich über die simulierte
Leitung (wie kosmos_rc), FNI über das Pi-Modell pi_fni (wie kosmos_rc „F …“)."""
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
import tempfile, json
import verz6
def projekt(name, start, baenke, autoboot=False):
    out = []
    for prog, labels, bilder, anz in baenke:
        out.append({'zellen': [list(prog.get(n, (0, 0))) for n in range(256)], 'labels': {f'{a:03d}': n for a, n in labels.items()},
                    'bilder': [{'name': n, 'segmente': list(b)} for n, b in bilder], 'anzeige': list(anz) if anz else None})
    return {'format': kr.PROJEKT_FORMAT, 'version': kr.PROJEKT_VERSION, 'name': name, 'start': start, 'autoboot': autoboot,
            'baenke': out}

print('6.00: leerer Flash, Projekt einspielen legt das Verzeichnis an')
v0 = L.verzeichnis()
pruef('leerer Flash: kein Verzeichnis', v0 == {'vorhanden': False, 'autoboot': 0, 'projekte': []}, str(v0))
prog = {n: (n % 7, (n * 13) & 0xFF) for n in range(0, 60)}
bilder = [('titel', bytes([0x76, 0x79, 0x38, 0x38, 0x3f, 0])), ('boom', bytes([0x7c, 0x3f, 0x3f, 0x37]))]
anz = bytes([0x73, 0x50, 0x5c, 0x1e, 0, 0x06])
spiel = projekt('Spiel', 7, [(prog, {7: 'anfang', 44: 'ende'}, bilder, anz)], autoboot=True)
t0 = m.us
nr = L.projekt_einspielen(spiel, 11)
print(f'     (Verzeichnis anlegen + Projekt einspielen: {(m.us - t0) / 1e6:.0f} s Simulationszeit)')
v = verz6.lesen(fl)
pruef('Projekt 11 = Bank 4, 4 Bänke, Name und Kurzanzeige im Verzeichnis, Autoboot 11', nr == 11 and v['projekte'].get(11) == {'bank': 4, 'res': 4, 'name': 'Spiel', 'anzeige': list(anz)} and v['autoboot'] == 11, str(v))
zwei = projekt('Zweites', 1, [({0: (1, 0), 1: (2, 3)}, {}, [], None), ({0: (0, 42), 5: (0, 99)}, {}, [], None)])
t0 = m.us
nr2 = L.projekt_einspielen(zwei)
print(f'     (zweites Projekt mit zwei Bänken: {(m.us - t0) / 1e6:.0f} s Simulationszeit)')
v = L.verzeichnis()
pruef('zweites Projekt: erster freier Platz (1), Bänke 8.., über $2A gelesen', nr2 == 1 and [(e['nr'], e['bank'], e['res'], e['name']) for e in v['projekte']] == [(1, 8, 4, 'Zweites'), (11, 4, 4, 'Spiel')] and v['autoboot'] == 11, str(v))
pruef('zweite Bank des Projekts = Bank 9', verz6.gueltig(fl, 9)[0:2] == bytes([0, 42]))

print('Projektdatei (.cp1, Format 1)')
p = L.projekt_sichern(11, quelltext='HLT')
b = p['baenke'][0]
pruef('Kopf: Name, Start 7, Autoboot, Herkunft Projekt 11 / Bank 4', (p['name'], p['start'], p['autoboot'], p['herkunft']['projekt'], p['herkunft']['aus_baenken']) == ('Spiel', 7, True, 11, [4]), str({k: p[k] for k in ('name', 'start', 'autoboot', 'herkunft')}))
pruef('eine Bank (leere reservierte Bänke fehlen)', len(p['baenke']) == 1)
pruef('256 Zellen, Inhalt stimmt, Rest 00.000', len(b['zellen']) == 256 and all(tuple(b['zellen'][n]) == v_ for n, v_ in prog.items()) and all(c == [0, 0] for c in b['zellen'][60:]))
pruef('Labels', b['labels'] == {'007': 'anfang', '044': 'ende'}, str(b['labels']))
pruef('Bilder', [(x['name'], bytes(x['segmente'])) for x in b['bilder']] == bilder, str(b['bilder']))
pruef('Anzeige', bytes(b['anzeige']) == anz, str(b['anzeige']))
pruef('roh = 0x200..0x5FF (1024 Byte), Name vorn, Start in 0x213', len(bytes.fromhex(b['roh'])) == 0x400 and bytes.fromhex(b['roh'])[:5] == b'Spiel' and bytes.fromhex(b['roh'])[0x13] == 7)
pruef('Quelltext', p['quelltext'] == 'HLT')
t = kr.projekt_text(p)
pruef('Text: je Zeile 8 Zellen, liest sich zurück', json.loads(t) == p and '[0,0], [1,13], [2,26]' in t, t[:300])
pruef('prüfen: gelesen = gesichert', kr.projekt_pruefen(json.loads(t)) == p)
kaputt = json.loads(t); kaputt['baenke'][0]['labels']['007'] = 'anders'
try: kr.projekt_pruefen(kaputt); pruef('prüfen erkennt abweichende Labels', False)
except ValueError as e: pruef('prüfen erkennt abweichende Labels', 'Rohbereich' in str(e), str(e))
p2 = L.projekt_sichern(1)
pruef('Projekt mit zwei Bänken: beide gesichert, Start 1, kein Autoboot', len(p2['baenke']) == 2 and p2['baenke'][1]['zellen'][0] == [0, 42] and p2['baenke'][1]['zellen'][5] == [0, 99] and p2['start'] == 1 and not p2['autoboot'], str(len(p2['baenke'])))

print('Ändern und Löschen (ganzes Verzeichnis neu)')
p['name'] = 'Spiel neu'; p['autoboot'] = False
t0 = m.us
L.projekt_einspielen(p, 11)
print(f'     (Projekt mit neuem Namen: {(m.us - t0) / 1e6:.0f} s Simulationszeit)')
v = L.verzeichnis()
pruef('umbenannt, Platz und Bänke bleiben', [(e['nr'], e['bank'], e['name']) for e in v['projekte']] == [(1, 8, 'Zweites'), (11, 4, 'Spiel neu')], str(v['projekte']))
L.projekt_loeschen(1)
v = L.verzeichnis()
pruef('Projekt 1 gelöscht, 11 bleibt', [e['nr'] for e in v['projekte']] == [11], str(v['projekte']))
nr3 = L.projekt_einspielen(zwei, 5)
pruef('neues Projekt nimmt die frei gewordene Lücke (Bank 8)', [(e['nr'], e['bank']) for e in L.verzeichnis()['projekte']] == [(5, 8), (11, 4)])

print('alle-sichern über die Befehlszeile')
kr.Leitung = Sim; kr.server_laeuft = lambda port=None: False
d = tempfile.mkdtemp(dir=os.environ.get('TMPDIR'))
r = kr.main(['alle-sichern', d])
dat = sorted(os.listdir(d))
pruef('alle-sichern: eine Datei je Projekt', r == 0 and dat == ['05-Zweites.cp1', '11-Spiel_neu.cp1'], str(dat))
pruef('Datei lesbar und = projekt_sichern', kr.projekt_lesen(os.path.join(d, '11-Spiel_neu.cp1'))['baenke'] == L.projekt_sichern(11)['baenke'])
print('ALLES OK' if not f else f'{f} FEHLER'); sys.exit(1 if f else 0)
