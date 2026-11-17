"""6.00: AT28C256 – A13 = P1.5, A14 = P1.1 (SCK, SPI Mode 3). Abbild-Aufbau, Code läuft nur in den Blöcken 1111, 1011, 1101, 1001,
aus Hälfte 2 nur der eine Befehl im SCK-Fenster von spi; Timer-Interrupts mitten im Fenster gehen gut."""
import sys
sys.path.insert(0, '.')
from sim48 import CP1, SPIFlash, text
ROM = open('cp1v6-eeprom.bin', 'rb').read()
SYM = {l.split()[1]: int(l.split()[0], 16) for l in open('cp1v6.sym')}
HLT, AKO, ABS, LDA, PSK, FRD, FWR, SEF = 1, 4, 6, 5, 36, 37, 38, 47
f = 0
def pruef(n, ok, i=''):
    global f; print(('  ok   ' if ok else '  FEHL ') + n + ('' if ok else f'  [{i}]')); f += not ok

H = [ROM[i * 0x1000:(i + 1) * 0x1000] for i in range(8)]
pruef('32 KB', len(ROM) == 0x8000)
pruef('untere 2 KB in allen acht Hälften gleich', all(h[:0x800] == H[7][:0x800] for h in H))
pruef('Hälfte 2 = Hälfte 6 (Spiegel für das SCK-Fenster)', H[2] == H[6])
TAB, TAB_B = SYM['TABELLE'] & 0xFFF, SYM['TABELLE_1011'] & 0xFFF      # Sprungtabelle: Offset im Block (ganz / Teil für 1011)
pruef('Sprungtabelle in allen Blöcken außer 1011/1010 ganz gleich', all(H[i][TAB:] == H[7][TAB:] for i in (0, 1, 3, 4, 5)) and TAB >= 0xE00, hex(TAB))
pruef('1011/1010 tragen den oberen Teil der Tabelle', H[6][TAB_B:] == H[7][TAB_B:] and TAB <= TAB_B, hex(TAB_B))
pruef('Reserveblöcke 1000, 1100, 1110 sonst leer', all(H[i][0x800:TAB] == bytes([0xFF]) * (TAB - 0x800) for i in (0, 1, 3)))
pruef('1101 (Befehle) und 1001 (Aufträge) enthalten Code', all(H[i][0x800:0x900] != bytes([0xFF]) * 0x100 for i in (4, 5)))
fa = sorted(k for k in SYM if k.startswith('fa_'))
pruef('Fernaufrufe 1001 -> 1011 liegen im Tabellenteil von 1011 (gleiche Bytes in beiden Blöcken)',
      fa and all(SYM[k] & 0xFFF >= TAB_B and H[4][SYM[k] & 0xFFF:(SYM[k] & 0xFFF) + 7] == H[6][SYM[k] & 0xFFF:(SYM[k] & 0xFFF) + 7] for k in fa), fa)
spk = SYM['sp_k'] & 0xFFF                      # 6.x: Symbol = EEPROM-Adresse (Block 1011 = 0x6800..)
fenster = {spk + 2, spk + 3}                   # ORL P1,#$02 – geholt, während SCK low ist
pruef('sp_k in Block 1011', SYM['sp_k'] & 0x7800 == 0x6800 and spk < TAB_B, hex(SYM['sp_k']))
pruef('im Fenster steht ORL P1,#$02', H[6][spk + 2:spk + 4] == bytes([0x89, 0x02]), H[6][spk:spk + 4].hex())

def bank(fl, b):
    s = bytearray([0xFF]) * 0x1000
    for n in range(256): s[2 * n:2 * n + 2] = bytes([n % 30, n])
    s[0x200:0x210] = b'A14-Test        '; s[0x210:0x213] = b'\0\0\0'
    fl.m[b * 0x2000:b * 0x2000 + 0x1000] = s

fl = SPIFlash(); bank(fl, 8)
m = CP1(ROM, True, flash=fl)
m.ram[0x5f], m.ram[0x5e] = 0, 255               # 6.00: „Projekt über alles“ (S_PBANK 0, S_PRES 255): PSK k = Bank k
prog = [(AKO, 4), (ABS, 60)] + [(PSK, 8), (PSK, 0), (PSK, 117), (FRD, 120)] + \
       [(LDA, 60), (41, 1), (ABS, 60), (42, 0), (11, 12), (9, 2), (PSK, 9), (PSK, 120), (PSK, 20), (FWR, 120), (HLT, 0)]
for n, (b, a) in enumerate(prog): m.intern.ram[2 * n:2 * n + 2] = bytes([b, a])
t = m.us + 50_000; m.drueck('run', t, 100)
m.bis(t + 8_000_000)
pruef('Programm (4 × FRD 117, FWR 20) bis HLT', m.ram[0x38] == len(prog), f'PC {m.ram[0x38]} {text(m.anzeige())!r}')
pruef('FRD-Daten richtig', all(m.cp3.ram[2 * (n - 128) + 1] == n - 120 for n in range(128, 237)) and all(m.intern.ram[2 * n + 1] == n - 120 for n in range(120, 128)))
pruef('FWR in Bank 9 angekommen (Zellen 120..139 = 0..19)', any(all(fl.m[9 * 0x2000 + s * 0x1000 + 2 * (120 + i) + 1] == i for i in range(20)) and fl.m[9 * 0x2000 + s * 0x1000 + 0x211] == 0 for s in (0, 1)))
pruef('aus Hälfte 2 oben nur das Fenster geholt', set(m.holungen) == fenster, {hex(k): v for k, v in m.holungen.items()})
pruef('Fenster oft durchlaufen', min(m.holungen.values()) > 1000, m.holungen)
pruef('Timer-Interrupts mitten im Fenster (Hälfte 2) kamen vor und gingen gut', m.int_haelften.get(2, 0) > 0 and set(m.int_haelften) <= {2, 4, 5, 6},
      m.int_haelften)
pruef('P1 danach wieder ganz high', m.p1 == 0xFF, hex(m.p1))
print('ALLES OK' if not f else f'{f} FEHLER'); sys.exit(1 if f else 0)
