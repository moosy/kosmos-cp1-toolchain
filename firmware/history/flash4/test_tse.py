"""4.02: TSE (nicht blockierend) und VZG mit Tastengedächtnis."""
import sys
sys.path.insert(0, '.')
from sim48 import CP1, text
ROM = open('cp1v4-eeprom.bin', 'rb').read()
TSE, ABS, VZG, HLT, SPU, AKO = 39, 6, 3, 1, 9, 4
f = 0
def pruef(n, ok, i=''):
    global f; print(('  ok   ' if ok else '  FEHL ') + n + ('' if ok else f'  [{i}]')); f += not ok
def maschine(prog):
    m = CP1(ROM)
    for n, (b, a) in enumerate(prog): m.intern.ram[2*n:2*n+2] = bytes([b, a])
    return m
def zelle(m, n): return m.intern.ram[2*n + 1]

m = maschine([(TSE, 0), (ABS, 30), (VZG, 250), (TSE, 0), (ABS, 31), (TSE, 0), (ABS, 32), (HLT, 0)])
t = m.us + 50_000
m.drueck('run', t, 100)
m.drueck('8', t + 200_000, 80)          # kurz, mitten im VZG 250
m.bis(t + 1_500_000)
pruef('ohne Taste: 255 (RUN zählt nicht)', zelle(m, 30) == 255, zelle(m, 30))
pruef('8 während VZG gedrückt: TSE = 8', zelle(m, 31) == 8, zelle(m, 31))
pruef('danach wieder 255', zelle(m, 32) == 255, zelle(m, 32))

# Taste zwischen zwei TSE ohne VZG dazwischen (enge Schleife): wird auch erkannt
m = maschine([(TSE, 0), (ABS, 30), (AKO, 255), (5 + 0, 0)] )
prog = [(TSE, 0), (10, 40), (11, 0), (ABS, 41), (HLT, 0)]   # TSE / VGL 40 (=255) / SPB 0 / ABS 41 / HLT
m = maschine(prog); m.intern.ram[80:82] = bytes([0, 255])
t = m.us + 50_000
m.drueck('run', t, 100); m.drueck('2', t + 300_000, 60)
m.bis(t + 1_000_000)
pruef('Warteschleife mit TSE erkennt 2', zelle(m, 41) == 2, f'{zelle(m, 41)} {text(m.anzeige())!r}')

# VZG-Dauer: 4 x VZG 250
m = maschine([(VZG, 250), (VZG, 250), (VZG, 250), (VZG, 250), (HLT, 0)])
t = m.us + 50_000; m.drueck('run', t, 100)
ende = None
while m.us < t + 2_000_000:
    m.bis(m.us + 2000)
    if ende is None and m.intern.ram[0] == VZG and text(m.anzeige()).startswith('P'): pass
m2 = maschine([(VZG, 250), (VZG, 250), (VZG, 250), (VZG, 250), (HLT, 0)])
t = m2.us + 50_000; m2.drueck('run', t, 100)
t_hlt = None
while m2.us < t + 2_000_000:
    m2.bis(m2.us + 1000)
    if t_hlt is None and m2.ram[0x38] == 5: t_hlt = m2.us
dauer = (t_hlt - t - 100_000) / 1000 if t_hlt else None
pruef('4 x VZG 250 ~ 1,15 s wie das Original (mit Interrupt)', dauer is not None and 1100 < dauer < 1200, dauer)
print('ALLES OK' if not f else f'{f} FEHLER')
