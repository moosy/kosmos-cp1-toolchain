import sys, runpy, io, contextlib, functools
ziel = sys.argv[3]
sys.argv = ['fluss.py', sys.argv[1], sys.argv[2]]
with contextlib.redirect_stdout(io.StringIO()):
    g = runpy.run_path('../review/fluss.py')
rom, sym, v, ZWEI, BED = g['rom'], g['sym'], g['v'], g['ZWEI'], g['BED']
inv = {}
for k, a in sym.items(): inv.setdefault(a, k)
@functools.lru_cache(None)
def kette(pc0, half0, mb0):
    best = (0, ()); seen = set(); st = [(pc0, half0, mb0)]
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
            if op & 0x1F == 0x04: pc = ((op & 0xE0) << 3) | b2 | (mb << 11); continue
            if op & 0x1F == 0x14:
                z = ((op & 0xE0) << 3) | b2 | (mb << 11)
                d, p = kette(z, half, mb)
                if d + 1 > best[0]: best = (d + 1, (inv.get(v(z, half), hex(v(z, half))),) + p)
                pc = nxt; continue
            if op in BED: st.append((((pc + 1) & 0xF00) | b2, half, mb)); pc = nxt; continue
            if op in (0x83, 0x93, 0xB3): break
            pc = nxt
    return best
a = sym[ziel]
h, m, pc = ('A', 0, a) if a < 0x800 else (('A', 1, a) if a < 0x1000 else ('B', 1, a - 0x1000))
print(kette(pc, h, m))
