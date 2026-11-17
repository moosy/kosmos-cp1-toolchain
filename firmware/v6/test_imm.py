"""5.06: Befehle 40..46 = ADD/SUB/VGL/VGR/VKL/UND/ODR mit festem Wert (Argument statt Zelle)."""
import sys, random
sys.path.insert(0, '.')
from sim48 import CP1, text
ROM = open('cp1v6-eeprom.bin', 'rb').read()
HLT, AKO, ABS, SPB, OVF, LDA = 1, 4, 6, 11, 26, 5
ADDK, SUBK, VGLK, VGRK, VKLK, UNDK, ODRK = range(40, 47)
f = 0
def pruef(n, ok, i=''):
    global f; print(('  ok   ' if ok else '  FEHL ') + n + ('' if ok else f'  [{i}]')); f += not ok
def lauf(prog, ms=300, vorher=None):
    m = CP1(ROM)
    for n, (b, a) in enumerate(prog): m.intern.ram[2*n:2*n+2] = bytes([b, a])
    if vorher: vorher(m)
    t = m.us + 50_000
    m.drueck('run', t, 100)
    m.bis(t + ms * 1000)
    return m
def zelle(m, n): return m.intern.ram[2*n + 1]
def akku(m): return (m.ram[0x36], m.ram[0x37])

# Rechnen: Ergebnis landet über ABS in Zelle 60
for name, op, a, w, erw in [('ADD 100+27', ADDK, 100, 27, 127), ('ADD 0+0', ADDK, 0, 0, 0), ('ADD 200+55', ADDK, 200, 55, 255),
                            ('SUB 100-27', SUBK, 100, 27, 73), ('SUB 5-5', SUBK, 5, 5, 0), ('SUB 9-0', SUBK, 9, 0, 9),
                            ('UND 197&60', UNDK, 197, 60, 4), ('UND x&0', UNDK, 197, 0, 0), ('ODR 197|60', ODRK, 197, 60, 253),
                            ('ODR 0|128', ODRK, 0, 128, 128)]:
    m = lauf([(AKO, a), (op, w), (ABS, 60), (HLT, 0)])
    pruef(name, zelle(m, 60) == erw and m.ram[0x38] == 4, f'{zelle(m, 60)} PC {m.ram[0x38]} {text(m.anzeige())!r}')

# Überlauf: OVF an -> F 006, OVF aus -> modulo 256
m = lauf([(AKO, 250), (ADDK, 10), (ABS, 60), (HLT, 0)])
pruef('ADD 250+10 ohne OVF 000: F 006', 'F' in text(m.anzeige()) and text(m.anzeige()).endswith('006'), text(m.anzeige()))
m = lauf([(OVF, 0), (AKO, 250), (ADDK, 10), (ABS, 60), (HLT, 0)])
pruef('ADD 250+10 mit OVF 000: 4', zelle(m, 60) == 4, zelle(m, 60))
m = lauf([(AKO, 3), (SUBK, 5), (ABS, 60), (HLT, 0)])
pruef('SUB 3-5 ohne OVF 000: F 006', text(m.anzeige()).endswith('006'), text(m.anzeige()))
m = lauf([(OVF, 0), (AKO, 3), (SUBK, 5), (ABS, 60), (HLT, 0)])
pruef('SUB 3-5 mit OVF 000: 254', zelle(m, 60) == 254, zelle(m, 60))

# Vergleiche: SPB 5 springt zu ABS-Pfad "ja" (Zelle 60 = 1), sonst Zelle 60 = 2
def vergleich(op, a, w):
    prog = [(AKO, a), (op, w), (SPB, 7), (AKO, 2), (ABS, 60), (HLT, 0), (HLT, 0), (AKO, 1), (ABS, 60), (HLT, 0)]
    return zelle(lauf(prog), 60) == 1
for a in (0, 1, 5, 127, 128, 254, 255):
    for w in (0, 1, 5, 128, 255):
        if vergleich(VGLK, a, w) != (a == w): pruef(f'VGL {a} #{w}', False)
        if vergleich(VGRK, a, w) != (a > w): pruef(f'VGR {a} #{w}', False)
        if vergleich(VKLK, a, w) != (a < w): pruef(f'VKL {a} #{w}', False)
pruef('VGL/VGR/VKL mit festem Wert: 105 Fälle', True)
# Vergleichsergebnis wird gelöscht (erst wahr, dann falsch -> SPB springt nicht)
prog = [(AKO, 5), (VGLK, 5), (VGLK, 6), (SPB, 8), (AKO, 2), (ABS, 60), (HLT, 0), (HLT, 0), (AKO, 1), (ABS, 60), (HLT, 0)]
pruef('zweiter Vergleich löscht das Ergebnis', zelle(lauf(prog), 60) == 2)
# ADD mit festem Wert lässt das Vergleichsergebnis stehen (wie ADD mit Zelle)
prog = [(AKO, 5), (VGLK, 5), (ADDK, 1), (SPB, 8), (AKO, 2), (ABS, 60), (HLT, 0), (HLT, 0), (AKO, 1), (ABS, 60), (HLT, 0)]
pruef('ADD # lässt das Vergleichsergebnis stehen', zelle(lauf(prog), 60) == 1)

# Akku mit Befehl -> F 005; Befehl 47 -> F 002
m = lauf([(LDA, 10), (ADDK, 1), (HLT, 0)] + [(0, 0)] * 7 + [(9, 3)])
pruef('Befehl im Akku: F 005', text(m.anzeige()).endswith('005'), text(m.anzeige()))
m = lauf([(AKO, 1), (50, 1), (HLT, 0)])
pruef('Befehl 50: F 002 (48 = JOV, 49 = ZUF)', text(m.anzeige()).endswith('002'), text(m.anzeige()))

# Zufällige Gegenprobe gegen die Zellen-Variante
random.seed(5)
ops = [(ADDK, 7), (SUBK, 8), (UNDK, 15), (ODRK, 25)]
for _ in range(40):
    op, zop = random.choice(ops); a = random.randrange(256); w = random.randrange(256)
    m1 = lauf([(OVF, 0), (AKO, a), (op, w), (ABS, 60), (HLT, 0)])
    m2 = lauf([(OVF, 0), (AKO, a), (zop, 61), (ABS, 60), (HLT, 0)], vorher=lambda m: m.intern.ram.__setitem__(slice(122, 124), bytes([0, w])))
    if zelle(m1, 60) != zelle(m2, 60): pruef(f'Gegenprobe {op} {a} {w}', False, f'{zelle(m1, 60)} {zelle(m2, 60)}')
pruef('40 Zufallsfälle gleich wie mit Zelle', True)

# INP nimmt 46 an, 47 nicht
m = CP1(ROM); t = m.us + 50_000
for i, k in enumerate(['0', '0', '0', 'out', '4', '7', '0', '0', '1', 'inp']): m.drueck(k, t + i * 120_000, 60)
m.bis(t + 1_500_000)
pruef('INP 47.001 angenommen', m.intern.ram[0:2] == bytes([47, 1]), (m.intern.ram[0:2].hex(), text(m.anzeige())))
m = CP1(ROM); t = m.us + 50_000
for i, k in enumerate(['0', '0', '0', 'out', '4', '8', '0', '0', '1', 'inp']): m.drueck(k, t + i * 120_000, 60)
m.bis(t + 1_500_000)
pruef('INP 48.001: F 004', text(m.anzeige()).endswith('004'), text(m.anzeige()))
print('ALLES OK' if not f else f'{f} FEHLER')
