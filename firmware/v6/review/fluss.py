# Statischer Ablauf über das virtuelle 8-KB-Abbild (unten 0x000-0x7FF, A oben 0x800-0xFFF, B oben 0x1800-0x1FFF)
import sys, re, collections
sys.path.insert(0, sys.argv[1]); import asm48
quelle = sys.argv[2]
rom, sym = asm48.assembliere(quelle, 0xff, 0x2000)
src = open(quelle, encoding='latin-1').read()
ZWEI = {0x03,0x13,0x23,0x43,0x53,0xD3,0x88,0x89,0x8A,0x98,0x99,0x9A,0xB0,0xB1} | set(range(0xB8,0xC0)) \
     | {0x12,0x32,0x52,0x72,0x92,0xB2,0xD2,0xF2,0x16,0x26,0x36,0x46,0x56,0x76,0x86,0x96,0xB6,0xC6,0xE6,0xF6} | set(range(0xE8,0xF0)) \
     | {x for x in range(0x04,0x100,0x20)} | {x for x in range(0x14,0x100,0x20)}
BED = {0x12,0x32,0x52,0x72,0x92,0xB2,0xD2,0xF2,0x16,0x26,0x36,0x46,0x56,0x76,0x86,0x96,0xB6,0xC6,0xE6,0xF6} | set(range(0xE8,0xF0))
def v(pc, half):            # virtuelle Adresse
    return pc if pc < 0x800 else (pc if half == 'A' else pc + 0x1000)
erreicht = set(); wurzeln = []
def wurzel(adr, half, mb, isr=False): wurzeln.append((adr, half, mb, isr))
wurzel(0x000, 'A', 0); wurzel(0x007, 'A', 0, True); wurzel(0x007, 'B', 0, True); wurzel(0x003, 'A', 0, True)
# Tabellen: .db <label  -> Ziel in derselben Seite, beide Hälften
for lab in re.findall(r'\.db\s+<\s*(\w+)', src, re.I):
    if lab in sym:
        a = sym[lab]
        if a < 0x800: wurzel(a, 'A', 0); wurzel(a, 'B', 0)
        elif a < 0x1000: wurzel(a, 'A', 1)
        else: wurzel(a - 0x1000, 'B', 1)
gesehen = set(); ziele_unbek = []
stapel = list(wurzeln)
while stapel:
    pc, half, mb, isr = stapel.pop()
    while True:
        key = (pc, half, mb, isr)
        if key in gesehen: break
        gesehen.add(key)
        a = v(pc, half); op = rom[a]
        n = 2 if op in ZWEI else 1
        for i in range(n): erreicht.add(v(pc + i, half))
        nxt = pc + n
        b2 = rom[v(pc + 1, half)] if n == 2 else None
        if op == 0xE5: mb = 0
        elif op == 0xF5: mb = 1
        if op == 0x99 and b2 & 0x10 == 0: half = 'B'          # ANL P1: A12 = 0
        if op == 0x89 and b2 & 0x10: half = 'A'               # ORL P1: A12 = 1
        if op & 0x1F == 0x04:                                  # JMP
            pc = ((op & 0xE0) << 3) | b2 | (0 if isr else mb << 11); continue
        if op & 0x1F == 0x14:                                  # CALL
            stapel.append((((op & 0xE0) << 3) | b2 | (0 if isr else mb << 11), half, mb, isr))
            pc = nxt; continue
        if op in BED:
            stapel.append((((pc + 1) & 0xF00) | b2, half, mb, isr)); pc = nxt; continue
        if op in (0x83, 0x93): break
        if op == 0xB3: ziele_unbek.append((pc, half)); break  # JMPP
        pc = nxt
# Ergebnis: nicht erreichte Bytes, die keine .db-Daten sind
daten = set(); pcv = 0
for nr, lab, m, ops in asm48.zeilen(quelle):
    if m is None or m == '.EQU': continue
    if m == '.ORG': pcv = asm48.zahl(ops[0], sym); continue
    if m == '.SEITE': pcv = (pcv + 0xff) & ~0xff; continue
    k = len(ops) if m == '.DB' else len(asm48.befehl(m, ops, pcv, sym))
    if m == '.DB': daten.update(range(pcv, pcv + k))
    pcv += k
def bereiche(von, bis):
    out = []; i = von
    while i < bis:
        if i not in erreicht and i not in daten and rom[i] != 0xff:
            j = i
            while j < bis and j not in erreicht and j not in daten and rom[j] != 0xff: j += 1
            out.append((i, j - i)); i = j
        else: i += 1
    return out
inv = collections.defaultdict(list)
for k, a in sym.items(): inv[a].append(k)
for name, von, bis in (('unten', 0, 0x800), ('A oben', 0x800, 0x1000), ('B oben', 0x1800, 0x2000)):
    b = bereiche(von, bis); print(f'{name}: {sum(n for _, n in b)} Byte nicht erreicht (ohne .db/FF)')
    for a, n in b:
        if n >= 2: print(f'   {a:#06x} {n:4d}  {",".join(inv.get(a, []))}')
print('JMPP-Stellen:', [(hex(p), h) for p, h in sorted(set(ziele_unbek))])

# --- Stapeltiefe statisch: je Einsprung (Unterprogramm) die tiefste Aufrufkette bis RET
import functools
sys.setrecursionlimit(10000)
@functools.lru_cache(None)
def tiefe(pc0, half0, mb0, isr):
    """größte zusätzliche Stapeltiefe ab Einsprung (ohne den eigenen CALL)"""
    best = 0; seen = set(); st = [(pc0, half0, mb0)]
    while st:
        pc, half, mb = st.pop()
        while (pc, half, mb) not in seen:
            seen.add((pc, half, mb))
            op = rom[v(pc, half)]; n = 2 if op in ZWEI else 1
            b2 = rom[v(pc + 1, half)] if n == 2 else None; nxt = pc + n
            if op == 0xE5: mb = 0
            elif op == 0xF5: mb = 1
            if op == 0x99 and b2 & 0x10 == 0: half = 'B'
            if op == 0x89 and b2 & 0x10: half = 'A'
            if op & 0x1F == 0x04: pc = ((op & 0xE0) << 3) | b2 | (0 if isr else mb << 11); continue
            if op & 0x1F == 0x14:
                z = ((op & 0xE0) << 3) | b2 | (0 if isr else mb << 11)
                best = max(best, 1 + tiefe(z, half, mb, isr)); pc = nxt; continue
            if op in BED: st.append((((pc + 1) & 0xF00) | b2, half, mb)); pc = nxt; continue
            if op in (0x83, 0x93, 0xB3): break
            pc = nxt
    return best
haupt = max(tiefe(a, h, m, i) for a, h, m, i in wurzeln if not i)
isr_t = max(tiefe(a, h, m, i) for a, h, m, i in wurzeln if i)
print(f'Stapel: Hauptprogramm bis {haupt} Ebenen, Interrupt 1 + {isr_t} -> zusammen {haupt + 1 + isr_t} von 8')
