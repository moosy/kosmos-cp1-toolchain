"""6.10: JOV z (48) – PSK k / PSK n / JOV z: n Zellen ab z aus Bank k des Projekts an dieselbe Stelle, dann weiter bei z.
Overlays: fester Kern unten, wechselnder Bereich oben. Fehler F-003 / F-009, Projektbank bleibt, JSR-Stapel bleibt."""
import sys
sys.path.insert(0, '.')
from sim48 import CP1, SPIFlash, text
import verz6
ROM = open('cp1v6-eeprom.bin', 'rb').read()
HLT, AKO, ABS, SPU, PSH, SEF, LDA, ADD, PSK, FRD, JSR, RET, JOV = 1, 4, 6, 9, 34, 47, 5, 7, 36, 37, 32, 33, 48
f = 0
def pruef(n, ok, i=''):
    global f; print(('  ok   ' if ok else '  FEHL ') + n + ('' if ok else f'  [{i}]')); f += not ok
def zellen(prog):
    b = bytearray(512)
    for n, (c, a) in prog.items(): b[2 * n:2 * n + 2] = bytes([c, a])
    return bytes(b)
def zelle(m, n):
    chip, a = (m.intern, 2 * n) if n < 128 else (m.cp3, 2 * (n - 128))
    return chip.ram[a], chip.ram[a + 1]

def maschine(kern, teile, res=4, laden=True):
    """Projekt 3 ab Bank 4: Bank 4 = kern, Bank 5.. = teile; geladen wie per CAL (Auftrag $04)"""
    fl = SPIFlash()
    pr = {3: {'bank': 4, 'res': res, 'zellen': zellen(kern), 'start': 0, 'meta': bytes([0x77, 0x79, 0x38, 0x38, 0x3f, 0x80]) * 0 + b''}}
    verz6.anlegen(fl, pr)
    s = verz6.projektbank(zellen(kern), 'Kern', 0, meta=bytes(0x200) + bytes([0x76, 0x79, 0x38, 0x38, 0x3f, 0x80]))  # Bild 0 = HELLO.
    verz6.setzen(fl, 4, s)
    for k, t in enumerate(teile):
        if t is not None: verz6.setzen(fl, 5 + k, verz6.projektbank(zellen(t)))
    m = CP1(ROM, True, flash=fl); m.bis(m.us + 1_500_000)
    if laden:
        m.ram[0x2c] = 3; m.ram[0x26] = 4; m.drueck('cal', m.us + 1000, 100); m.bis(m.us + 2_000_000)
    return m
def lauf(m, ms=1500):
    m.drueck('run', m.us + 1000, 100); m.bis(m.us + ms * 1000)
    return text(m.anzeige())

print('JOV lädt einen Teil und springt hinein')
kern = {0: (PSK, 1), 1: (PSK, 3), 2: (JOV, 100), 3: (HLT, 0)}
teil1 = {100: (AKO, 77), 101: (ABS, 50), 102: (HLT, 0), 103: (AKO, 99)}
m = maschine(kern, [teil1])
pruef('geladen: Projekt 3 (S_PBANK 4, S_PRES 4)', (m.ram[0x5f], m.ram[0x5e]) == (4, 4), (m.ram[0x5f], m.ram[0x5e]))
t0 = m.us; anz = lauf(m)
pruef('Teil läuft: Zelle 50 = 77, angehalten bei 102 (PC 103)', zelle(m, 50) == (0, 77) and m.ram[0x38] == 103, f'{anz!r} PC {m.ram[0x38]} {zelle(m, 50)}')
pruef('nur 3 Zellen geladen: Zelle 103 bleibt 00', zelle(m, 103) == (0, 0), zelle(m, 103))
pruef('Projektbank bleibt (SEF, PSK 0)', (m.ram[0x5f], m.ram[0x5e]) == (4, 4))

print('Kern und Teile wechseln sich ab (Overlay-Spiel)')
kern = {0: (PSK, 1), 1: (PSK, 4), 2: (JOV, 128), 10: (LDA, 60), 11: (ADD, 61), 12: (ABS, 60), 13: (PSK, 2), 14: (PSK, 4), 15: (JOV, 128),
        20: (LDA, 60), 21: (ADD, 61), 22: (ABS, 60), 23: (HLT, 0), 61: (0, 1)}
teil1 = {128: (AKO, 10), 129: (ABS, 60), 130: (SPU, 10), 131: (HLT, 0)}           # Teil 1: Startwert, zurück in den Kern
teil2 = {128: (AKO, 100), 129: (ADD, 60), 130: (ABS, 60), 131: (SPU, 20)}        # Teil 2 (anderer Inhalt an derselben Stelle)
m = maschine(kern, [teil1, teil2])
anz = lauf(m, 2500)
pruef('10 + 1 = 11, Teil 2: 100 + 11 = 111, + 1 = 112', zelle(m, 60) == (0, 112) and m.ram[0x38] == 24, f'{anz!r} PC {m.ram[0x38]} {zelle(m, 60)}')
pruef('Bereich 128.. enthält jetzt Teil 2', zelle(m, 128) == (AKO, 100), zelle(m, 128))

print('JOV aus einem Unterprogramm im Kern: JSR-Stapel bleibt stehen (Rücksprung in den Kern)')
kern = {0: (JSR, 10), 1: (HLT, 0), 10: (PSK, 1), 11: (PSK, 2), 12: (JOV, 128)}
teil1 = {128: (AKO, 5), 129: (RET, 0)}
m = maschine(kern, [teil1]); anz = lauf(m)
pruef('RET im Teil kehrt hinter das JSR im Kern zurück (PC 2), Akku 5', m.ram[0x38] == 2 and m.ram[0x37] == 5 and m.ram[0x45] == 0, f'{anz!r} PC {m.ram[0x38]} SP {m.ram[0x45]}')

print('Fehler')
def fehler(kern, teile=[{}], **kw):
    m = maschine(kern, teile, **kw); return lauf(m), m
anz, m = fehler({0: (PSK, 4), 1: (PSK, 1), 2: (JOV, 100), 3: (HLT, 0)})
pruef('k = 4 bei 4 reservierten Bänken -> F-003', anz == 'F  003', anz)
anz, m = fehler({0: (PSK, 2), 1: (PSK, 1), 2: (JOV, 100), 3: (HLT, 0)})
pruef('leere Bank (k = 2) -> F-003, kein Sprung in Nullen', anz == 'F  003' and m.ram[0x38] == 2, f'{anz!r} PC {m.ram[0x38]}')
anz, m = fehler({0: (PSK, 1), 1: (PSK, 60), 2: (JOV, 200), 3: (HLT, 0)})
pruef('z + n über 256 -> F-003', anz == 'F  003', anz)
anz, m = fehler({0: (PSK, 1), 1: (JOV, 100), 2: (HLT, 0)})
pruef('nur ein Wert auf dem Stapel -> F-009', anz == 'F  009', anz)
m = maschine({}, [{100: (HLT, 0)}], laden=False)
for n, (c, a) in {0: (PSK, 1), 1: (PSK, 1), 2: (JOV, 100), 3: (HLT, 0)}.items(): m.intern.ram[2 * n:2 * n + 2] = bytes([c, a])
anz = lauf(m)
pruef('getipptes Programm ohne Projekt -> F-003', anz == 'F  003', anz)

print('Tempo')
teil = {100 + i: (0, i) for i in range(60)}; teil[100] = (HLT, 0)
kern = {0: (PSK, 1), 1: (PSK, 60), 2: (JOV, 100)}
m = maschine(kern, [teil]); m.drueck('run', m.us + 1000, 100); t = m.us
while m.us < t + 3_000_000 and m.ram[0x38] != 101: m.bis(m.us + 500)
dauer = (m.us - t) / 1000
pruef(f'JOV mit 60 Zellen: {dauer:.0f} ms bis zum ersten Befehl im Teil', m.ram[0x38] == 101 and dauer < 400, dauer)
print('ALLES OK' if not f else f'{f} FEHLER'); sys.exit(1 if f else 0)
