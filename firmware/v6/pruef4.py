# Sprünge zwischen den Hälften prüfen: A-Code (0x800-0xFFF) darf nicht nach B (0x1800+) springen,
# B-Code nur nach B, in die za_-Stummel oder (nach SEL MB0) nach unten.
import sys, re
sys.path.insert(0, '.')
import asm48
quelle = sys.argv[1] if len(sys.argv) > 1 else 'v4/cp1v4.asm'
rom, sym = asm48.assembliere(quelle, 0xff, 0x2000)
pc = 0; fehler = 0; mb = 1
for nr, lab, m, ops in asm48.zeilen(quelle):
    if lab and pc >= 0x800: mb = 1
    if m is None: continue
    if m == 'SEL' and ops[0] in ('MB0', 'MB1'): mb = int(ops[0][2])
    if m == '.EQU': continue
    if m == '.ORG': pc = asm48.zahl(ops[0], sym); continue
    if m == '.SEITE': pc = (pc + 0xff) & ~0xff; continue
    n = len(ops) if m == '.DB' else len(asm48.befehl(m, ops, pc, sym))
    if m in ('JMP', 'CALL') and ops[0] in sym:
        z = sym[ops[0]]
        if 0x800 <= pc < 0x1000:
            ok = z < 0x1000 and (z >= 0x800 or mb == 0)
            if 0xf00 <= pc and ops[0] in [k for k in sym if sym[k] >= 0x1800]: ok = True   # Stummel A -> Ziel B (gleiche Bytes)
        elif pc >= 0x1800:
            ok = z >= 0x1800 or (z < 0x800 and mb == 0) or ops[0].startswith('za_') or (pc >= 0x1f00 and (z < 0x1000))
        else:
            ok = True
        if not ok:
            print(f'Zeile {nr}: {pc:#06x} {m} {ops[0]} -> {z:#06x}'); fehler += 1
    pc += n
print('Sprungprüfung:', 'ok' if not fehler else f'{fehler} Fehler')
sys.exit(1 if fehler else 0)
