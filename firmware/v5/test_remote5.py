"""5.00: kosmos_remote.py gegen den Simulator. NIE-Rahmen und Antworten laufen wirklich über die simulierte
Leitung (wie kosmos_rc), FNI über das Pi-Modell pi_fni (wie kosmos_rc „F …“)."""
import sys, os
_hier = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.join(_hier, '..', '..'), os.path.join(_hier, '..', 'fernsteuerung'), os.path.join(_hier, '..', '..', 'remote'), _hier):
    sys.path.insert(0, _p)                     # Repo-Wurzel bzw. ältere Ablagen
from sim48 import CP1, SPIFlash, text
from pi_fni import FNIPi
import kosmos_remote as kr
ROM = open(os.path.join(_hier, 'cp1v5-eeprom.bin'), 'rb').read()
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
        pi = FNIPi({'E': 'ein', 'A': 'aus', 'K': 'komplett', 'N': 'namen'}[richtung], tuple(kopf), daten)
        m.geraet = pi
        t0 = m.us
        m.bis(m.us + 300_000, halt=lambda mm: mm.takt() == 0)
        if m.takt() != 0:
            m.geraet = None; return ['FEHLER', 'nicht_angenommen']
        m.bis(m.us + 8_000_000, halt=lambda mm: pi.fertig)
        m.geraet = None
        if pi.fehler: return ['FEHLER', pi.fehler.replace(' ', '_')]
        if richtung == 'N': return ['OK', b''.join(bytes([b, 0]) + n for b, n in pi.namen).hex()]
        return ['OK'] + ([bytes(pi.empfangen).hex()] if richtung != 'E' else [])

kr.time.sleep = lambda s: m.bis(m.us + s * 1e6)
L = Sim(); f = 0
def pruef(n, ok, i=''):
    global f; print(('  ok   ' if ok else '  FEHL ') + n + ('' if ok else f'  [{i}]')); f += not ok

print('NIE')
pruef('Anzeige über Statusabfrage (mit Trennpunkt)', L.anzeige()['text'] == 'P  .000', str(L.anzeige()))
L.tasten(['1', '2', '3', 'pc']); m.bis(m.us + 200_000)
pruef('Tasten: PC = 123', m.ram[0x38] == 123, str(m.ram[0x38]))
L.schreib(0x2C, 77); pruef('03 RAM schreiben', m.ram[0x2C] == 77)

print('Programm-RAM per FNI')
prog = {n: (n % 7, (n * 11) & 0xFF) for n in range(5, 45)}
r = L.laden(prog)
pruef('laden 5..44', all(tuple(m.intern.ram[2 * n:2 * n + 2]) == v for n, v in prog.items()) and r['von'] == 5, str(r))
z = L.speichern(0, 60)
pruef('speichern 0..60 = RAM', z == {n: tuple(m.intern.ram[2 * n:2 * n + 2]) for n in range(61)}, str(list(z.items())[:6]))
z = L.speichern()
pruef('speichern ohne Bereich: 0..MEM_SIZE (255)', len(z) == 256, str(len(z)))

print('Zellen per NIE (auch bei laufendem Programm)')
m.intern.ram[0:6] = bytes([5, 50, 2, 0, 9, 0])          # LDA 50, ANZ, SPU 0
m.intern.ram[100:102] = bytes([0, 5]); m.ram[0x38] = 0
m.drueck('run', m.us + 10_000, 120); m.bis(m.us + 300_000)
z = L.zellen_lesen(48, 4)
pruef('Zellen 48..51 lesen', z == {n: tuple(m.intern.ram[2 * n:2 * n + 2]) for n in range(48, 52)}, str(z))
L.zelle_schreiben(50, 0, 222); m.bis(m.us + 100_000)
pruef('Zelle 50 = 222 -> Programm zeigt 222', m.ram[0x37] == 222, str(m.ram[0x37]))
try:
    L.laden({0: (1, 0)}); pruef('FNI bei laufendem Programm abgelehnt', False)
except kr.FlashFehler as e:
    pruef('FNI bei laufendem Programm abgelehnt', 'keinen Auftrag' in str(e), str(e))
m.drueck('stp', m.us + 10_000, 120); m.bis(m.us + 300_000)

print('Flash: Bank direkt sichern/einspielen, Aufträge über 04')
L.bank_einspielen(9, prog, 'Muster', start=5)
v = L.flash_verzeichnis()
pruef('Verzeichnis: Bank 9 „Muster“, Start 5', {'bank': 9, 'name': 'Muster', 'start': 5} in v['baenke'], str(v))
z, name = L.bank_sichern(9)
pruef('Bank 9 komplett zurückgelesen, Name „Muster“', all(z[n] == v_ for n, v_ in prog.items()) and z[0] == (0, 0) and name == 'Muster', f'{name} {[z[n] for n in (0, 5, 44)]}')
pruef('RAM dabei unberührt (Zelle 50 = 222)', tuple(m.intern.ram[100:102]) == (0, 222))
L.bank_einspielen(11, prog, 'Benannt', start=5, namen={5: 'anfang', 44: 'ende', 200: 'puffer'})
k = L.bank_komplett(11)
pruef('5.03: Bank mit Namen ($29) und zurück ($25)', k['namen'] == {5: 'anfang', 44: 'ende', 200: 'puffer'} and k['name'] == 'Benannt' and all(k['zellen'][n] == v_ for n, v_ in prog.items()), str(k['namen']))
pruef('Bank ohne Namen liefert keine', L.bank_komplett(9)['namen'] == {})
L.flash_speichern(12, 'Rakete', 0)
L.flash_autoboot(12)
pruef('Autoboot 12', L.flash_verzeichnis()['autoboot'] == 12)
L.flash_laden(9)
pruef('Bank 9 laden: PC = 5', m.ram[0x38] == 5 and tuple(m.intern.ram[10:12]) == prog[5], f'{m.ram[0x38]}')
try: L.flash_laden(99); pruef('leere Bank -> Fehler', False)
except kr.FlashFehler as e: pruef('leere Bank -> F-011', 'F-011' in str(e), str(e))
print('Reset (5.02)')
L.flash_autoboot(0)
m.intern.ram[0:6] = bytes([5, 50, 2, 0, 9, 0]); m.drueck('run', m.us + 10_000, 120); m.bis(m.us + 300_000)
t = L.reset(); m.bis(m.us + 1_500_000)
pruef('reset(): Version erkannt, danach alles leer, P 000', '5' in t and not any(m.intern.ram[:256]) and L.anzeige()['text'] == 'P  .000', f'{t!r} {L.anzeige()}')
print('ALLES OK' if not f else f'{f} FEHLER'); sys.exit(1 if f else 0)
