"""6.22: Projekt in den Editor holen – bei Overlay-Paketen der ganze Paket-Quelltext aus allen Teilen
(paket_aus_baenken), Teilnamen als Banknamen im Flash. Leitung wie in test_projekt."""
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
def projekt(name, start, baenke, autoboot=False):
    out = []
    for prog, labels, bilder, anz in baenke:
        out.append({'zellen': [list(prog.get(n, (0, 0))) for n in range(256)], 'labels': {f'{a:03d}': n for a, n in labels.items()},
                    'bilder': [{'name': n, 'segmente': list(b)} for n, b in bilder], 'anzeige': list(anz) if anz else None})
    return {'format': kr.PROJEKT_FORMAT, 'version': kr.PROJEKT_VERSION, 'name': name, 'start': start, 'autoboot': autoboot,
            'baenke': out}

import verz6

ex = os.path.join(_hier, '..', '..', 'examples')
q = open(os.path.join(ex, 'minenflug-bonus.koa'), encoding='utf-8').read()
bt = open(os.path.join(ex, 'minenflug-bonus.bilder')).read()
p = kr.paket_projekt(q, 'Wuerfelminen', 0, '', bt)
print('Paket einspielen (6 Bänke), in den Editor holen, wieder assemblieren')
L.projekt_einspielen(p, 7)
e = L.projekt_bank(7)
pruef('Teilnamen stehen als Banknamen im Flash', [L.bank_komplett(e['bank'] + k)['name'].strip() for k in range(6)] == ['Wuerfelminen', 'spiel', 'bonus', 'anim', 'wuerfel', 'ergebnis'])
r = L.projekt_editor(7)
pruef('Editor bekommt ein Paket mit allen 6 Teilen', r['paket'] and r['teile'] == 6 and kr.ist_paket(r['listing']), (r['paket'], r['teile']))
pruef('.bereich und Teile mit Namen', '.bereich 090-219' in r['listing'] and all(f'>>teil {k} {n}' in r['listing'] for k, n in enumerate(['spiel', 'bonus', 'anim', 'wuerfel', 'ergebnis'], 1)))
pruef('LADE statt PSK/PSK/JOV', r['listing'].count('LADE ') == 7 and 'JOV' not in r['listing'], r['listing'].count('LADE '))
p2 = kr.paket_projekt(r['listing'], 'Wuerfelminen', r['start'], r['namen'], r['bilder'])
pruef('wieder assembliert: alle Bänke Zelle für Zelle gleich', len(p2['baenke']) == 6 and all(a['zellen'] == b['zellen'] for a, b in zip(p['baenke'], p2['baenke'])))
pruef('Labels und Bilder gleich', all(a['labels'] == b['labels'] for a, b in zip(p['baenke'], p2['baenke'])) and p2['baenke'][0]['bilder'] == p['baenke'][0]['bilder'])

print('Sicherung (.cp1) behält die Teilnamen')
s = L.projekt_sichern(7)
pruef('projekt-sichern: Teilnamen je Bank', [b.get('name') for b in s['baenke']] == [None, 'spiel', 'bonus', 'anim', 'wuerfel', 'ergebnis'], [b.get('name') for b in s['baenke']])
L.projekt_einspielen(s, 8)
r8 = L.projekt_editor(8)
pruef('Sicherung eingespielt: wieder dieselben Teilnamen im Editor', all(f'>>teil {k} {n}' in r8['listing'] for k, n in enumerate(['spiel', 'bonus', 'anim', 'wuerfel', 'ergebnis'], 1)))

print('Projekt ohne Teile: wie bisher die erste Bank')
eins = {'format': kr.PROJEKT_FORMAT, 'version': kr.PROJEKT_VERSION, 'name': 'Eins', 'start': 0, 'autoboot': False,
        'baenke': [{'zellen': [[4, 7], [1, 0]] + [[0, 0]] * 254, 'labels': {'000': 'anfang'}, 'bilder': [], 'anzeige': None}]}
L.projekt_einspielen(eins, 9)
r9 = L.projekt_editor(9)
pruef('kein Paket: Listing der ersten Bank', not r9['paket'] and r9['teile'] == 1 and 'AKO 007' in r9['listing'] and '>>' not in r9['listing'], r9['listing'][:80])
print('ALLES OK' if not f else f'{f} FEHLER'); sys.exit(1 if f else 0)
