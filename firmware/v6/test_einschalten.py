"""5.04: Einschalten mit zufälligem internem RAM (wie am echten 8049): danach immer sauber „P 000“.
Bis 5.03 lieferte wait_key Zufall aus AUFTRAG (0x17) als Taste: F 004, einzelne Ziffern, Abstürze."""
import sys, random
sys.path.insert(0, '.')
from sim48 import CP1, SPIFlash, text
ROM = open('cp1v6-eeprom.bin', 'rb').read()
schlecht = []
for seed in range(40):
    rnd = random.Random(seed)
    m = CP1(ROM, True, vorlauf=False, flash=SPIFlash())
    for a in range(0x80): m.ram[a] = rnd.randrange(256)
    try:
        m.bis(2_500_000); t = text(m.anzeige())
    except RuntimeError as e:
        t = f'Absturz ({e})'
    if t != 'P  000' or m.ram[0x17] != 0: schlecht.append((seed, t))   # 0x17 AUFTRAG leer (0x16 LEER = 1 im Leerlauf)
print(('  ok   ' if not schlecht else '  FEHL ') + f'40 Starts mit Zufalls-RAM: {40 - len(schlecht)} sauber', schlecht[:5])
print('ALLES OK' if not schlecht else f'{len(schlecht)} FEHLER'); sys.exit(1 if schlecht else 0)
