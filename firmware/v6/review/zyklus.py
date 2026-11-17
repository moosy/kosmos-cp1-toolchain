import sys, runpy, io, contextlib
sys.argv = ['fluss.py', sys.argv[1], sys.argv[2]]
src = open('../review/fluss.py').read().split('# --- Stapeltiefe')[0]
g = {}
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(src, 'fluss', 'exec'), g)
rom, sym, v, ZWEI, BED, wurzeln = g['rom'], g['sym'], g['v'], g['ZWEI'], g['BED'], g['wurzeln']
inv = {}
for k, a in sym.items(): inv.setdefault(a, k)
def aufrufe(pc0, half0, mb0, isr):
    out = set(); seen = set(); st = [(pc0, half0, mb0)]
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
                out.add((((op & 0xE0) << 3) | b2 | (0 if isr else mb << 11), half, mb)); pc = nxt; continue
            if op in BED: st.append((((pc + 1) & 0xF00) | b2, half, mb)); pc = nxt; continue
            if op in (0x83, 0x93, 0xB3): break
            pc = nxt
    return out
# Zyklus suchen per DFS
farbe = {}; pfad = []
def name(k): return inv.get(v(k[0], k[1]), hex(v(k[0], k[1])))
def dfs(k):
    farbe[k] = 1; pfad.append(k)
    for z in aufrufe(*k, False):
        if farbe.get(z) == 1:
            i = pfad.index(z); print('Zyklus:', ' -> '.join(name(x) for x in pfad[i:] + [z])); sys.exit()
        if z not in farbe: dfs(z)
    farbe[k] = 2; pfad.pop()
sys.setrecursionlimit(10000)
for a, h, m, i in wurzeln:
    if not i and (a, h, m) not in farbe: dfs((a, h, m))
print('kein Zyklus')
