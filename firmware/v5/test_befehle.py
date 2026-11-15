"""Befehlserweiterungen NEG/UND/ODR im Simulator: CP1-Programme laufen lassen."""
import sys
sys.path.insert(0, '.')
from sim48 import CP1, text
ROM = open('cp1v5-eeprom.bin', 'rb').read()
ORIG = None
if '--original' in sys.argv:                       # Gegenprobe: gleiches mit dem Original-ROM
    sys.path.insert(0, '.'); import asm48
    ROM = bytes(asm48.assembliere('cp1.asm', 0, 0x800)[0])
fehler = 0
def pruef(name, ok, info=''):
    global fehler
    print(('  ok   ' if ok else '  FEHL ') + name + (f'  [{info}]' if info else ''))
    if not ok: fehler += 1

def lauf(prog, daten={}, cp3=True):
    """prog: Liste (befehl, argument) ab Zelle 0; daten: {zelle: wert}. -> (Akku, Anzeige)"""
    m = CP1(ROM, cp3); m.bis(300_000)
    for n, (b, a) in list(enumerate(prog)) + [(z, (0, w)) for z, w in daten.items()]:
        chip, adr = (m.intern, 2 * n) if n < 128 else (m.cp3, 2 * (n - 128))
        chip.ram[adr] = b; chip.ram[adr + 1] = a
    m.drueck('run', 400_000, 120)
    m.bis(1_500_000)
    return (m.ram[0x36], m.ram[0x37]), text(m.anzeige())

AKO, UND, NEG, ODR, HLT, LDA, ABS, VZG = 4, 15, 14, 25, 1, 5, 6, 3
print('UND bitweise')
for a, b in ((197, 60), (1, 1), (1, 0), (0, 1), (255, 170), (12, 10)):
    akku, _ = lauf([(AKO, a), (UND, 10), (HLT, 0)], {10: b})
    pruef(f'{a} UND {b} = {a & b}', akku == (0, a & b), str(akku))
print('ODR (25) bitweise')
for a, b in ((197, 60), (0, 0), (1, 0), (128, 1), (12, 10)):
    akku, _ = lauf([(AKO, a), (ODR, 10), (HLT, 0)], {10: b})
    pruef(f'{a} ODR {b} = {a | b}', akku == (0, a | b), str(akku))
print('NEG als XOR mit Maske')
for a, m, erw in ((0, 0, 1), (1, 0, 0), (0, 1, 1), (1, 1, 0), (197, 255, 58), (15, 15, 0), (170, 85, 255), (5, 0, 4)):
    akku, _ = lauf([(AKO, a), (NEG, m), (HLT, 0)])
    pruef(f'{a} NEG {m:03d} = {erw}', akku == (0, erw), str(akku))
print('Fehler wie im Original')
_, anz = lauf([(AKO, 1), (UND, 200), (HLT, 0)], cp3=False)
pruef('UND 200 ohne CP3 -> F-003', anz == 'F  003', anz)
_, anz = lauf([(AKO, 1), (UND, 10), (HLT, 0)], {})          # Zelle 10 = 00.000 ist Datum -> ok
_, anz2 = lauf([(AKO, 1), (UND, 2), (HLT, 0)])               # Zelle 2 = HLT (01.000): kein Datum
pruef('UND auf Befehlszelle -> F-005', anz2 == 'F  005', anz2)
_, anz = lauf([(LDA, 3), (NEG, 0), (HLT, 0), (7, 1)])        # Akku = Zelle 3 = 07.001 (kein Datum)
pruef('NEG mit Befehl im Akku -> F-005', anz == 'F  005', anz)
_, anz = lauf([(40, 0), (HLT, 0)])
pruef('Befehl 40 -> F-002', anz == 'F  002', anz)
_, anz = lauf([(0, 5), (HLT, 0)])
pruef('Befehl 00 (Datum ausführen) -> F-002', anz == 'F  002', anz)
_, anz = lauf([(99, 0), (HLT, 0)])
pruef('Befehl 99 -> F-002', anz == 'F  002', anz)
OVF, ADD, SUB, ANZ, SPU = 26, 7, 8, 2, 9
print('OVF (26): Überlauf ein/aus')
_, anz = lauf([(AKO, 200), (ADD, 10), (HLT, 0)], {10: 100})
pruef('Standard: 200 + 100 -> F-006', anz == 'F  006', anz)
akku, _ = lauf([(OVF, 0), (AKO, 200), (ADD, 10), (HLT, 0)], {10: 100})
pruef('OVF 000: 200 + 100 = 44', akku == (0, 44), str(akku))
akku, _ = lauf([(OVF, 0), (AKO, 255), (ADD, 10), (HLT, 0)], {10: 1})
pruef('OVF 000: 255 + 1 = 0', akku == (0, 0), str(akku))
akku, _ = lauf([(OVF, 0), (AKO, 5), (SUB, 10), (HLT, 0)], {10: 10})
pruef('OVF 000: 5 - 10 = 251', akku == (0, 251), str(akku))
akku, _ = lauf([(OVF, 0), (AKO, 0), (SUB, 10), (HLT, 0)], {10: 1})
pruef('OVF 000: 0 - 1 = 255', akku == (0, 255), str(akku))
_, anz = lauf([(AKO, 5), (SUB, 10), (HLT, 0)], {10: 10})
pruef('Standard: 5 - 10 -> F-006', anz == 'F  006', anz)
_, anz = lauf([(OVF, 0), (OVF, 1), (AKO, 200), (ADD, 10), (HLT, 0)], {10: 100})
pruef('OVF 000, dann OVF 001: wieder F-006', anz == 'F  006', anz)
akku, _ = lauf([(OVF, 0), (AKO, 100), (ADD, 10), (HLT, 0)], {10: 50})
pruef('OVF 000 ohne Überlauf: 100 + 50 = 150', akku == (0, 150), str(akku))
print('ANZ 001: mit Vorzeichen')
for v, m, erw in ((255, 1, 'A -001'), (128, 1, 'A -128'), (200, 1, 'A -056'), (127, 1, 'A00127'), (0, 1, 'A00000'), (255, 0, 'A00255'), (5, 2, 'A00005')):
    _, anz = lauf([(AKO, v), (ANZ, m), (SPU, 2)])   # auf der Stelle treten: Anzeige steht (bei SPU 1 erwischt man ANZ mitten im Schreiben)
    pruef(f'AKO {v:03d}, ANZ {m:03d} -> {erw}', anz == erw, anz)
print('Eintippen über INP')
def tippe(folge, cp3=True):
    m = CP1(ROM, cp3); m.bis(300_000); t = 400_000
    for k in folge:
        m.drueck(k, t, 100); t += 250_000
    m.bis(t + 200_000); return m
m = tippe(['0', '0', '0', 'inp', '2', '5', '0', '1', '0', 'inp', '2', '6', '0', '0', '0', 'inp', '1', '4', '2', '5', '5', 'inp'])
pruef('25.010, 26.000, 14.255 eingetippt', [tuple(m.intern.ram[2 * n:2 * n + 2]) for n in range(3)] == [(25, 10), (26, 0), (14, 255)],
      str([tuple(m.intern.ram[2 * n:2 * n + 2]) for n in range(3)]))
m = tippe(['0', '0', '0', 'inp', '4', '0', '0', '0', '0', 'inp'])
pruef('40.000 eintippen -> F-004', text(m.anzeige()) == 'F  004', text(m.anzeige()))
m = tippe(['0', '0', '0', 'inp', '2', '4', '0', '0', '1', 'inp'])
pruef('24.001 geht weiterhin', tuple(m.intern.ram[0:2]) == (24, 1))
SEG = 27
print('SEG (27): Zellen als Segmentmuster')
muster = {100: 57, 101: 109, 102: 121, 103: 0, 104: 80, 105: 94}          # C S E _ r d
_, anz = lauf([(SEG, 100), (SPU, 1)], muster)
pruef('SEG 100 -> "CSE rd"', anz == 'C5E rd', anz)
_, anz = lauf([(SEG, 100), (SEG, 255), (SPU, 2)], muster)
pruef('SEG 255 löscht', anz == '      ', anz)
akku, anz = lauf([(AKO, 7), (SEG, 100), (SPU, 2)], muster)
pruef('SEG lässt Akku in Ruhe', akku == (0, 7) and anz == 'C5E rd', f'{akku} {anz}')
_, anz = lauf([(SEG, 123), (HLT, 0)], cp3=False)
pruef('SEG 123 ohne CP3 -> F-003 (128 > 127)', anz == 'F  003', anz)
_, anz = lauf([(SEG, 122), (SPU, 1)], {n: 6 for n in range(122, 128)}, cp3=False)
pruef('SEG 122 ohne CP3 geht (bis 127)', anz == '111111', anz)
_, anz = lauf([(SEG, 251), (HLT, 0)])
pruef('SEG 251 -> F-003', anz == 'F  003', anz)
_, anz = lauf([(SEG, 250), (SPU, 1)], {n: 64 for n in range(250, 256)})
pruef('SEG 250 mit CP3 geht', anz == '------', anz)
_, anz = lauf([(SEG, 0), (HLT, 0)])
pruef('SEG 000 auf Programmzellen -> F-005', anz == 'F  005', anz)
m = CP1(ROM); m.bis(300_000)                                   # Programm ab Zelle 10, Anzeige in 000..005
for n, v in {0: 6, 1: 91, 2: 79, 3: 102, 4: 109, 5: 125}.items(): m.intern.ram[2 * n:2 * n + 2] = bytes([0, v])
m.intern.ram[20:24] = bytes([SEG, 0, SPU, 11])
for k, tt in (('0', 400_000), ('1', 600_000), ('0', 800_000), ('pc', 1_000_000), ('run', 1_300_000)): m.drueck(k, tt, 100)
m.bis(2_000_000)
pruef('SEG 000 mit Anzeige in 000..005 (Programm ab 010)', text(m.anzeige()) == '123456', text(m.anzeige()))
_, anz = lauf([(SEG, 100), (HLT, 0)], muster)
pruef('HLT zeigt wie im Original den PC', anz.startswith('P'), anz)
AS1, AS2, AS3 = 28, 29, 30
ZIFF = [63, 6, 91, 79, 102, 109, 125, 39, 127, 111]
print('AS1..AS3 (28..30): Ziffer des Akkus als Segmentmuster')
def zellen(m, von, bis):
    return [tuple(m.intern.ram[2 * n:2 * n + 2]) if n < 128 else tuple(m.cp3.ram[2 * (n - 128):2 * (n - 128) + 2]) for n in range(von, bis + 1)]
def lauf_m(prog, daten={}, cp3=True):
    m = CP1(ROM, cp3); m.bis(300_000)
    for n, (b, a) in list(enumerate(prog)) + [(z, (0, w)) for z, w in daten.items()]:
        chip, adr = (m.intern, 2 * n) if n < 128 else (m.cp3, 2 * (n - 128))
        chip.ram[adr] = b; chip.ram[adr + 1] = a
    m.drueck('run', 400_000, 120); m.bis(1_500_000); return m
for v in (234, 7, 90, 255, 0, 105):
    m = lauf_m([(AKO, v), (AS1, 101), (AS2, 102), (AS3, 103), (HLT, 0)], {101: 0, 102: 0, 103: 0})
    erw = [(0, ZIFF[v // 100]), (0, ZIFF[v // 10 % 10]), (0, ZIFF[v % 10])]
    pruef(f'{v:03d} -> AS1/AS2/AS3', zellen(m, 101, 103) == erw, str(zellen(m, 101, 103)))
m = lauf_m([(AKO, 234), (AS2, 200), (HLT, 0)])
pruef('AS2 nach Zelle 200 (CP3), Ziel vorher Befehl/leer egal', zellen(m, 200, 200) == [(0, 79)], str(zellen(m, 200, 200)))
m = lauf_m([(AKO, 234), (AS2, 4), (HLT, 0), (0, 0), (HLT, 0)])
pruef('Zielzelle mit Befehl wird überschrieben (wie ABS)', zellen(m, 4, 4) == [(0, 79)], str(zellen(m, 4, 4)))
m = lauf_m([(AKO, 197), (AS1, 100), (AS2, 101), (AS3, 102), (SEG, 97), (SPU, 5)], {97: 0, 98: 0, 99: 56})
pruef('Zusammen mit SEG: "  L197"', text(m.anzeige()) == '  L197', text(m.anzeige()))
_, anz = lauf([(AS1, 200), (HLT, 0)], cp3=False)
pruef('AS1 200 ohne CP3 -> F-003', anz == 'F  003', anz)
_, anz = lauf([(LDA, 3), (AS1, 100), (HLT, 0), (7, 1)])
pruef('Befehl im Akku -> F-005', anz == 'F  005', anz)
m = tippe(['0', '0', '0', 'inp', '3', '0', '1', '0', '0', 'inp'])
pruef('30.100 eintippen geht', tuple(m.intern.ram[0:2]) == (30, 100))
TST = 31
print('TST (31): Zifferntaste abwarten')
def lauf_tasten(prog, tasten, bis_us=3_000_000, daten={}):
    m = CP1(ROM); m.bis(300_000)
    for n, (b, a) in list(enumerate(prog)) + [(z, (0, w)) for z, w in daten.items()]:
        m.intern.ram[2 * n] = b; m.intern.ram[2 * n + 1] = a
    m.drueck('run', 400_000, 120)
    for k, tt in tasten: m.drueck(k, tt, 120)
    m.bis(bis_us); return m
for ziffer in '0379':
    m = lauf_tasten([(TST, 0), (ABS, 50), (HLT, 0)], [(ziffer, 1_000_000)])
    pruef(f'Taste {ziffer} -> Akku {ziffer}', zellen(m, 50, 50) == [(0, int(ziffer))] and (m.ram[0x36], m.ram[0x37]) == (0, int(ziffer)), str(zellen(m, 50, 50)))
m = lauf_tasten([(TST, 0), (ABS, 50), (HLT, 0)], [('clr', 900_000), ('acc', 1_200_000), ('out', 1_500_000), ('5', 1_800_000)])
pruef('CLR/ACC/OUT werden übergangen, dann 5', zellen(m, 50, 50) == [(0, 5)], str(zellen(m, 50, 50)))
m = lauf_tasten([(TST, 0), (ABS, 50), (HLT, 0)], [], bis_us=2_000_000, daten={50: 99})
pruef('ohne Taste wartet TST (Zelle 50 unverändert, PC = 0)', zellen(m, 50, 50) == [(0, 99)] and m.ram[0x38] == 0, f'{zellen(m, 50, 50)} PC={m.ram[0x38]}')
m = lauf_tasten([(TST, 0), (ABS, 50), (HLT, 0)], [('stp', 1_000_000)], bis_us=1_600_000, daten={50: 99})
pruef('STP hält an, PC bleibt auf TST', m.ram[0x38] == 0 and zellen(m, 50, 50) == [(0, 99)], f'PC={m.ram[0x38]} {text(m.anzeige())}')
m.drueck('run', 1_700_000, 120); m.drueck('8', 2_200_000, 120); m.bis(3_000_000)
pruef('RUN macht beim TST weiter, dann 8', zellen(m, 50, 50) == [(0, 8)], str(zellen(m, 50, 50)))
m = lauf_tasten([(TST, 0), (ABS, 50), (TST, 0), (ABS, 51), (TST, 0), (ABS, 52), (HLT, 0)], [('1', 900_000), ('2', 1_300_000), ('3', 1_700_000)])
pruef('drei TST hintereinander: 1, 2, 3', zellen(m, 50, 52) == [(0, 1), (0, 2), (0, 3)], str(zellen(m, 50, 52)))
m = lauf_tasten([(VZG, 250), (VZG, 250), (TST, 0), (ABS, 50), (HLT, 0)], [('4', 500_000), ('6', 1_500_000)])
pruef('Taste vor dem TST zählt nicht (4 verworfen, 6 genommen)', zellen(m, 50, 50) == [(0, 6)], str(zellen(m, 50, 50)))
JSR, RET = 32, 33
print('JSR/RET (32/33): Unterprogramme')
akku, anz = lauf([(AKO, 1), (JSR, 10), (JSR, 10), (HLT, 0)] + [(HLT, 0)] * 6 + [(ADD, 20), (RET, 0)], {20: 5})
pruef('zweimal JSR auf "ADD 5": 1 -> 11', akku == (0, 11), str(akku))
prog = [(AKO, 0), (JSR, 10), (HLT, 0)] + [(HLT, 0)] * 7 + \
       [(ADD, 50), (JSR, 20), (RET, 0)] + [(HLT, 0)] * 7 + \
       [(ADD, 50), (JSR, 30), (RET, 0)] + [(HLT, 0)] * 7 + \
       [(ADD, 50), (RET, 0)]
akku, anz = lauf(prog, {50: 1})
pruef('drei Ebenen verschachtelt: Akku 3, sauber zurück', akku == (0, 3) and anz.startswith('P'), f'{akku} {anz}')
m = lauf_m([(JSR, 0)])
pruef('Endlos-Rekursion -> F-008 nach 24 Ebenen', text(m.anzeige()) == 'F  008' and m.ram[0x45] == 24, f'{text(m.anzeige())} SP={m.ram[0x45]}')
_, anz = lauf([(RET, 0), (HLT, 0)])
pruef('RET ohne JSR -> F-009', anz == 'F  009', anz)
_, anz = lauf([(JSR, 200), (HLT, 0)], cp3=False)
pruef('JSR 200 ohne CP3 -> F-003', anz == 'F  003', anz)
m = lauf_m([(SPU, 255)] + [(HLT, 0)] * 9, {})
m2 = CP1(ROM); m2.bis(300_000)
m2.intern.ram[0:2] = bytes([SPU, 255]); m2.cp3.ram[254:256] = bytes([JSR, 5]); m2.intern.ram[10:12] = bytes([HLT, 0])
m2.drueck('run', 400_000, 120); m2.bis(1_200_000)
pruef('JSR in Zelle 255 -> F-003 (kein Rücksprung möglich)', text(m2.anzeige()) == 'F  003', text(m2.anzeige()))
m = lauf_tasten([(JSR, 10), (ABS, 50), (HLT, 0)] + [(HLT, 0)] * 7 + [(TST, 0), (RET, 0)],
                [('stp', 900_000), ('run', 1_300_000), ('6', 1_800_000)], bis_us=2_600_000)
pruef('STP im Unterprogramm, RUN macht weiter, RET kommt zurück', zellen(m, 50, 50) == [(0, 6)] and m.ram[0x45] == 0, f'{zellen(m, 50, 50)} SP={m.ram[0x45]}')
m = tippe(['0', '0', '0', 'inp', '3', '3', '0', '0', '0', 'inp'])
pruef('33.000 eintippen geht', tuple(m.intern.ram[0:2]) == (33, 0))
m = lauf_m([(JSR, 0)])
for k, tt in (('0', 1_600_000), ('0', 1_800_000), ('2', 2_000_000), ('pc', 2_200_000)): m.drueck(k, tt, 100)
m.bis(2_500_000)
pruef('nach F-008: "002 PC" leert den Stapel', m.ram[0x45] == 0 and m.ram[0x38] == 2, f'SP={m.ram[0x45]} PC={m.ram[0x38]}')
m = lauf_tasten([(JSR, 10), (HLT, 0)] + [(HLT, 0)] * 8 + [(TST, 0), (RET, 0)], [('stp', 900_000), ('run', 1_300_000)], bis_us=1_700_000)
pruef('RUN allein lässt den Stapel stehen', m.ram[0x45] == 1, f'SP={m.ram[0x45]}')
PSH, POP = 34, 35
print('PSH/POP (34/35): Akku auf den gemeinsamen Stapel')
akku, _ = lauf([(AKO, 7), (PSH, 0), (AKO, 9), (POP, 0), (HLT, 0)])
pruef('AKO 7, PSH, AKO 9, POP -> 7', akku == (0, 7), str(akku))
m = lauf_m([(AKO, 42), (PSH, 0), (JSR, 10), (POP, 0), (HLT, 0)] + [(HLT, 0)] * 5 + [(AKO, 1), (RET, 0)])
pruef('Akku über JSR gerettet: 42, Stapel leer', (m.ram[0x36], m.ram[0x37]) == (0, 42) and m.ram[0x45] == 0, f'{(m.ram[0x36], m.ram[0x37])} SP={m.ram[0x45]}')
m = lauf_m([(AKO, 1), (PSH, 0), (AKO, 2), (PSH, 0), (AKO, 3), (PSH, 0), (POP, 0), (ABS, 50), (POP, 0), (ABS, 51), (POP, 0), (ABS, 52), (HLT, 0)])
pruef('LIFO: 1, 2, 3 rein -> 3, 2, 1 raus', zellen(m, 50, 52) == [(0, 3), (0, 2), (0, 1)], str(zellen(m, 50, 52)))
m = lauf_m([(AKO, 0), (PSH, 0), (SPU, 1)])
pruef('endlos PSH -> F-008 nach 24', text(m.anzeige()) == 'F  008' and m.ram[0x45] == 24, f'{text(m.anzeige())} SP={m.ram[0x45]}')
m = lauf_m([(AKO, 0)] + [(PSH, 0)] * 23 + [(JSR, 30), (HLT, 0)] + [(HLT, 0)] * 4 + [(RET, 0)])
pruef('23 PSH + JSR = 24 Ebenen geht', m.ram[0x45] == 23 and text(m.anzeige()).startswith('P'), f'SP={m.ram[0x45]} {text(m.anzeige())}')
m = lauf_m([(AKO, 0)] + [(PSH, 0)] * 24 + [(JSR, 30)] + [(HLT, 0)] * 4 + [(RET, 0)])
pruef('24 PSH + JSR -> F-008', text(m.anzeige()) == 'F  008', text(m.anzeige()))
_, anz = lauf([(POP, 0), (HLT, 0)])
pruef('POP auf leerem Stapel -> F-009', anz == 'F  009', anz)
_, anz = lauf([(LDA, 3), (PSH, 0), (HLT, 0), (7, 1)])
pruef('PSH mit Befehl im Akku -> F-005', anz == 'F  005', anz)
m = tippe(['0', '0', '0', 'inp', '3', '5', '0', '0', '0', 'inp'])
pruef('35.000 eintippen geht', tuple(m.intern.ram[0:2]) == (35, 0))
print('4.03: Dezimalpunkte über PA7')
ANZ = 2
from sim48 import punkte
m = lauf_m([(AKO, 5), (HLT, 0)])
pruef('normal (P xxx): nur der Trennpunkt bei Ziffer 3', punkte(m) == [False, False, True, False, False, False], str(punkte(m)))
m = lauf_m([(SEG, 100), (SPU, 1)], {100: 6, 101: 6 + 128, 102: 6, 103: 6 + 128, 104: 6, 105: 6 + 128})
pruef('SEG: Punkt nur mit +128 (auch Ziffer 3 ohne Trennpunkt)', punkte(m) == [False, True, False, True, False, True] and text(m.sichtbar()) == '111111', f'{punkte(m)} {text(m.sichtbar())}')
m = lauf_m([(SEG, 100), (SPU, 1)], {n: 6 + 128 for n in range(100, 106)})
pruef('SEG: alle sechs Punkte', all(punkte(m)), str(punkte(m)))
m = lauf_m([(SEG, 255), (SPU, 1)])
pruef('SEG 255: dunkel, auch kein Trennpunkt', not any(punkte(m)) and not any(m.sichtbar()), str([hex(x) for x in m.sichtbar()]))
m = lauf_m([(AKO, 123), (ANZ, 0), (SPU, 1)])
pruef('ANZ: kein Trennpunkt', not any(punkte(m)), f'{punkte(m)} {text(m.sichtbar())}')
m = lauf_m([(AKO, 253), (ANZ, 1), (SPU, 1)])
pruef('ANZ 001 negativ: kein Trennpunkt', not any(punkte(m)), f'{punkte(m)} {text(m.sichtbar())}')
m = lauf_m([(AKO, 7), (SEG, 100), (HLT, 0)], {n: 0 for n in range(100, 106)})
pruef('HLT nach SEG: Trennpunkt wieder da', punkte(m) == [False, False, True, False, False, False], str(punkte(m)))
for name, prog, daten in (('ANZ-Schleife', [(AKO, 123), (ANZ, 0), (SPU, 1)], {}),
                          ('ANZ 001-Schleife negativ', [(AKO, 253), (ANZ, 1), (SPU, 1)], {}),
                          ('SEG-Schleife', [(SEG, 100), (SPU, 0)], {n: 6 for n in range(100, 106)}),
                          ('SEG 255-Schleife', [(SEG, 255), (SPU, 0)], {})):
    m = lauf_m(prog, daten); an = 0
    for k in range(400):                      # 0,4 s lang jede ms nachsehen
        m.bis(m.us + 1000); an += punkte(m)[2]
    pruef(f'{name}: Trennpunkt glimmt nie', an == 0, f'{an}/400')
print('ALLES OK' if not fehler else f'{fehler} FEHLER'); sys.exit(1 if fehler else 0)
