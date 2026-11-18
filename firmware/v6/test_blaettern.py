"""5.05/6.00: CAL kurz = Projekte durchblättern (Pro nn blitzt auf, dann eigene Anzeige oder Name), CAL halten = laden,
Ziffer = normale Eingabe, STP = Abbruch. Dazu die Kopfanzeigen jetzt aus Hälfte A."""
import sys, os
sys.path.insert(0, '.')
for _p in (os.path.join('..', '..'), os.path.join('..', 'fernsteuerung'), os.path.join('..', '..', 'remote'), os.path.join('..', '..', 'tc')):
    sys.path.insert(0, _p)
from sim48 import CP1, SPIFlash, text
from pi_fni import FNIPi
from kosmos_remote import namen_bytes, anzeige_aus_text
ROM = open('cp1v6-eeprom.bin', 'rb').read()
F = []
def pruef(n, ok, i=''):
    print(('  ok   ' if ok else '  FEHL ') + n + (f'  [{i}]' if i else '')); ok or F.append(n)

def zelle(m, n):
    chip, a = (m.intern, 2 * n) if n < 128 else (m.cp3, 2 * (n - 128))
    return chip.ram[a], chip.ram[a + 1]

def fni(m, job, bank, daten, name=None, start=255):
    m.ram[0x2C] = bank; m.ram[0x3C] = 0; m.ram[0x3D] = 0; m.ram[0x3E] = start
    if name is not None: m.ram[0x60:0x70] = name.encode().ljust(16)[:16]
    m.ram[0x26] = job; m.ram[0x17] = 0x0D
    pi = FNIPi('ein', (job, bank, 0, 0), daten); m.geraet = pi
    m.bis(m.us + 15_000_000, halt=lambda mm: mm.ram[0x26] in (0, 0xEE) and pi.fertig and mm.tcnti)
    m.geraet = None; m.bis(m.us + 50_000)
    assert m.ram[0x26] == 0, hex(m.ram[0x26])

def tippe(m, tasten, abstand=200, dauer=120):
    t = m.us + 50_000
    for k in tasten:
        k, d = k if isinstance(k, tuple) else (k, dauer)
        m.drueck(k, t, d); t += d * 1000 + abstand * 1000
    m.bis(t)

def segs(m): return list(m.anzeige())

fl = SPIFlash()
m = CP1(ROM, True, flash=fl); m.bis(1_700_000)
prog = lambda w: b''.join(bytes([4, w, 1, 0]) if n == 0 else bytes(2) for n in range(255)) + bytes(2)   # AKO w, HLT
p2 = bytearray(512); p2[0:4] = bytes([4, 22, 1, 0])
p5 = bytearray(512); p5[0:4] = bytes([4, 55, 1, 0])
p9 = bytearray(512); p9[0:4] = bytes([4, 99, 1, 0])
import verz6                                                         # 6.00: Projekte 2, 5, 9 im Verzeichnis
verz6.anlegen(fl, {2: {'bank': 4, 'name': 'Rakete', 'zellen': bytes(p2), 'start': 0},
                   5: {'bank': 8, 'zellen': bytes(p5), 'start': 0},                       # ohne Name
                   9: {'bank': 12, 'name': 'Asteroiden', 'anzeige': list(anzeige_aus_text('AStEr.')), 'zellen': bytes(p9), 'start': 0}})
RAKETE = [0x50, 0x77, 0x75, 0x79, 0x78, 0x79]

print('CAL kurz: erstes Projekt')
tippe(m, ['cal']); m.bis(m.us + 150_000)
pruef('„Pro 02“ blitzt auf', text(m.anzeige()) == 'Pro 02', text(m.anzeige()))
m.bis(m.us + 500_000)
pruef('dann der Name als Anzeige „rAkEtE“', segs(m) == RAKETE, str([hex(x) for x in segs(m)]))
tippe(m, ['cal']); m.bis(m.us + 150_000)
pruef('CAL: „Pro 05“', text(m.anzeige()) == 'Pro 05', text(m.anzeige()))
m.bis(m.us + 500_000)
pruef('ohne Name bleibt „Pro 05“ stehen', text(m.anzeige()) == 'Pro 05', text(m.anzeige()))
tippe(m, ['cal']); m.bis(m.us + 700_000)
pruef('CAL: Projekt 9 mit Kurzanzeige „AStEr.“', segs(m) == list(anzeige_aus_text('AStEr.')), str([hex(x) for x in segs(m)]))
t0 = m.us
tippe(m, ['cal']); m.bis(m.us + 3_000_000, halt=lambda mm: text(mm.anzeige()) == 'Pro 02')
pruef('nach der letzten wieder von vorn: „Pro 02“ (Suche über alle Einträge)', text(m.anzeige()) == 'Pro 02', f'{text(m.anzeige())} nach {(m.us - t0) / 1000:.0f} ms')
m.bis(m.us + 500_000)
print('CAL halten: laden')
tippe(m, [('cal', 1300)]); m.bis(m.us + 1_500_000)
pruef('Projekt 2 geladen (Zelle 0 = AKO 22), Anzeige P 000', zelle(m, 0) == (4, 22) and text(m.anzeige()) == 'P  000', f'{zelle(m, 0)} {text(m.anzeige())}')
print('Ziffern beim Blättern: normale Eingabe')
tippe(m, ['cal']); m.bis(m.us + 700_000)
tippe(m, ['0', '5'])
pruef('„Pro 05“ in der Eingabe', text(m.anzeige()) == 'Pro 05', text(m.anzeige()))
tippe(m, ['cal']); m.bis(m.us + 1_500_000)
pruef('Projekt 5 geladen (AKO 55)', zelle(m, 0) == (4, 55), str(zelle(m, 0)))
print('STP bricht ab')
tippe(m, ['cal']); m.bis(m.us + 700_000)
tippe(m, ['stp']); m.bis(m.us + 300_000)
pruef('Anzeige leer, RAM unverändert', text(m.anzeige()).strip() == '' and zelle(m, 0) == (4, 55), text(m.anzeige()))
tippe(m, ['1', '2', '3', 'pc']); m.bis(m.us + 300_000)
pruef('danach normale Tasten (PC = 123)', m.ram[0x38] == 123, str(m.ram[0x38]))
print('schnell hintereinander CAL (während „Pro“ aufblitzt)')
tippe(m, ['cal', 'cal', 'cal'], abstand=150); m.bis(m.us + 150_000)
pruef('drei Mal weiter: Projekt 9', text(m.anzeige()) == 'Pro 09', text(m.anzeige()))
tippe(m, ['stp']); m.bis(m.us + 300_000)
print('Kopfanzeigen aus 1111')
tippe(m, [('run', 1300), '0', '9', 'run']); m.bis(m.us + 100_000)
pruef('RUN lang: „bot 09“ während der Arbeit', text(m.anzeige()) in ('bot 09', 'botrdY'), text(m.anzeige()))
m.bis(m.us + 3_000_000)
pruef('dann „bot rdY“', text(m.anzeige()) == 'botrdY', text(m.anzeige()))
m2 = CP1(ROM, True, vorlauf=False, flash=fl); m2.bis(1_700_000)
pruef('Einschalten mit Autoboot 9: „bot 09“', text(m2.anzeige()) == 'bot 09', text(m2.anzeige()))
m2.bis(m2.us + 3_000_000)
pruef('… lädt und startet Projekt 9 (Akku 99)', m2.ram[0x37] == 99, f'{m2.ram[0x37]} {text(m2.anzeige())}')
print('leerer Flash: F-011')
m3 = CP1(ROM, True, flash=SPIFlash()); m3.bis(1_700_000)
tippe(m3, ['cal']); m3.bis(m3.us + 3_000_000)
pruef('„F 011“', text(m3.anzeige()) == 'F  011', text(m3.anzeige()))
print('ALLES OK' if not F else f'{len(F)} FEHLER: {F}'); sys.exit(1 if F else 0)
