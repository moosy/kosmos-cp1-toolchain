"""6.20: ZUF n (49) – Akku = Zufallszahl 0..n-1 (ZUF 0: 0..255).
Zustand 16 Bit in der letzten RAM-Zelle (MEM_SIZE), Timer wird bei jedem Aufruf eingemischt, Xorshift 7/9/8."""
import sys, time
sys.path.insert(0, '.')
from sim48 import CP1, text
ROM = open('cp1v6-eeprom.bin', 'rb').read()
HLT, AKO, LDA, ABS, SPU, SPB, LIA, AIS, OVF = 1, 4, 5, 6, 9, 11, 19, 20, 26
ADDK, SUBK, VGLK, ZUF = 40, 41, 42, 49
f = 0
def pruef(n, ok, i=''):
    global f; print(('  ok   ' if ok else '  FEHL ') + n + ('' if ok else f'  [{i}]')); f += not ok
def zelle(m, n):
    chip, a = (m.intern, 2 * n) if n < 128 else (m.cp3, 2 * (n - 128))
    return chip.ram[a], chip.ram[a + 1]
def setze(m, n, w):
    chip, a = (m.intern, 2 * n) if n < 128 else (m.cp3, 2 * (n - 128))
    chip.ram[a:a + 2] = bytes(w)
def lauf(prog, ms, cp3=True, vorher=None):
    m = CP1(ROM, cp3)
    for n, w in prog.items(): setze(m, n, w)
    if vorher: vorher(m)
    t = m.us + 50_000
    m.drueck('run', t, 100)
    m.bis(t + ms * 1000, halt=None)
    return m

# --- 1. Das Verfahren selbst (Python-Abbild genau der Befehlsfolge in befehle.asm) ---
def schritt(hi, lo):
    c = hi & 1; a = (c << 7) | (lo >> 1); c = lo & 1
    hi ^= a; lo ^= c << 7               # x ^= x << 7
    lo ^= hi >> 1                       # x ^= x >> 9
    hi ^= lo                            # x ^= x << 8
    return hi, lo
def ref(x):
    x ^= (x << 7) & 0xFFFF; x ^= x >> 9; x ^= (x << 8) & 0xFFFF; return x
print('Verfahren: Xorshift 7/9/8 in 8-Bit-Schritten')
ok = all(schritt(x >> 8, x & 255) == (ref(x) >> 8, ref(x) & 255) for x in range(65536))
pruef('8-Bit-Zerlegung = 16-Bit-Xorshift für alle 65536 Zustände', ok)
x, n = (0, 1), 0
while True:
    x = schritt(*x); n += 1
    if x == (0, 1): break
pruef('Periode 65535 (alle Zustände außer 0)', n == 65535, n)

# --- 2. Im CP1: Häufigkeiten zählen ---
FERTIG = lambda m: m.ram[0x38] == 16
def zaehl_prog(nzuf, anz, runden=1):
    """runden x anz mal ZUF nzuf; Zelle 100 + Wert hochzählen (LIA/AIS über Zeiger 90); Zähler in 91/92"""
    return {0: (OVF, 0), 1: (ZUF, nzuf), 2: (ADDK, 100), 3: (ABS, 90), 4: (LIA, 90), 5: (ADDK, 1), 6: (AIS, 90),
            7: (LDA, 91), 8: (SUBK, 1), 9: (ABS, 91), 10: (VGLK, 0), 11: (SPB, 13), 12: (SPU, 1),
            13: (LDA, 92), 14: (SUBK, 1), 15: (ABS, 92), 16: (HLT, 0), 17: (0, 0),
            91: (0, anz), 92: (0, runden)}
def zaehlen(nzuf, anz, runden=1, start_ms=50, cp3=True):
    m = CP1(ROM, cp3)
    for n, w in zaehl_prog(nzuf, anz, runden).items(): setze(m, n, w)
    t = m.us + start_ms * 1000
    for r in range(runden):
        m.drueck('run', t, 100)
        m.bis(t + 60_000_000, FERTIG)
        setze(m, 91, (0, anz))
        m.ram[0x38] = 0
        t = m.us + 300_000
    h = [zelle(m, 100 + i)[1] for i in range(max(nzuf, 1))]
    return m, h

print('ZUF 6: 1200 Würfe')
t0 = time.time()
m, h = zaehlen(6, 200, 6)
dt = time.time() - t0
pruef('jeder Wurf gezählt, nichts außerhalb 0..5', sum(h) == 1200 and zelle(m, 106)[1] == 0 and zelle(m, 99)[1] == 0, f'{h} 106={zelle(m, 106)}')
e = sum(h) / 6; chi = sum((x - e) ** 2 / e for x in h)
pruef(f'gleich verteilt: {h}, Chi² = {chi:.1f} (Grenze 20,5 bei 99,9 %)', chi < 20.5, chi)
print(f'  (Simulator: {dt:.1f} s für {m.us / 1e6:.1f} s CP1-Zeit)')

print('ZUF 10 (Maske 15, Verwerfen): 1000 Würfe')
m, h = zaehlen(10, 250, 4)
e = sum(h) / 10; chi = sum((x - e) ** 2 / e for x in h)
pruef(f'0..9 gleich verteilt: {h}, Chi² = {chi:.1f} (Grenze 27,9)', sum(h) == 1000 and zelle(m, 110)[1] == 0 and chi < 27.9, chi)

print('ZUF 1: immer 0')
m, h = zaehlen(1, 100)
pruef('100 x 0', h == [100] and zelle(m, 101)[1] == 0, h)

print('ZUF 2 (Münze): 400 Würfe (Zähler je Wert bleibt unter 256)')
m, h = zaehlen(2, 200, 2)
chi = sum((x - 200) ** 2 / 200 for x in h)
pruef(f'{h}, Chi² = {chi:.1f} (Grenze 10,8)', sum(h) == 400 and chi < 10.8, chi)

# --- 3. Folgen: ZUF n, Ergebnis der Reihe nach ab Zelle 100 ablegen ---
def folge(nzuf, anz, start_ms=50, cp3=True, vorher=None):
    prog = {0: (AKO, 100), 1: (ABS, 90), 2: (ZUF, nzuf), 3: (AIS, 90), 4: (LDA, 90), 5: (ADDK, 1), 6: (ABS, 90),
            7: (VGLK, 100 + anz), 8: (SPB, 10), 9: (SPU, 2), 10: (HLT, 0)}
    m = CP1(ROM, cp3)
    for n, w in prog.items(): setze(m, n, w)
    if vorher: vorher(m)
    t = m.us + start_ms * 1000
    m.drueck('run', t, 100)
    m.bis(t + 30_000_000, lambda m: m.ram[0x38] == 11)
    return m, [zelle(m, 100 + i) for i in range(anz)]

print('ZUF 0: ganzer Bereich')
m, z = folge(0, 100)
w = [b for a, b in z]
pruef('100 Werte, alle Datum (Befehlsteil 00)', m.ram[0x38] == 11 and all(a == 0 for a, b in z), f'PC {m.ram[0x38]} {z[:5]}')
pruef(f'verschieden und über 0..255 verteilt ({len(set(w))} verschiedene, {sum(x >= 128 for x in w)} >= 128)',
      len(set(w)) >= 55 and 30 <= sum(x >= 128 for x in w) <= 70, w[:20])

print('ZUF 200: nie 200 und mehr')
m, z = folge(200, 100)
w = [b for a, b in z]
pruef(f'alle < 200 (größter {max(w)})', max(w) < 200 and len(set(w)) >= 50, w[:20])

print('Zustand in der letzten Zelle, Timer eingemischt')
m, z = folge(6, 20)
pruef('mit CP3: Zelle 255 hält den Zustand (nicht 00 00)', zelle(m, 255) != (0, 0), zelle(m, 255))
m2, z2 = folge(6, 20)
pruef('gleicher Ablauf -> gleiche Folge (Simulator reproduzierbar)', z == z2)
m3, z3 = folge(6, 20, start_ms=57)
pruef('RUN 7 ms später -> andere Folge (Timer)', z != z3, f'{[b for a, b in z]} {[b for a, b in z3]}')
m4, z4 = folge(6, 20, cp3=False)
pruef('ohne CP3: Zustand in Zelle 127', zelle(m4, 127) != (0, 0) and m4.ram[0x38] == 11, f'{zelle(m4, 127)} PC {m4.ram[0x38]}')
pruef('ohne CP3: Werte 0..5', all(a == 0 and b < 6 for a, b in z4), z4)
m5, z5 = folge(6, 20, vorher=lambda m: setze(m, 255, (0x12, 0x34)))
pruef('anderer Inhalt der Zelle 255 -> andere Folge', z5 != z, f'{[b for a, b in z5]}')
pruef('Akku danach ein Datum', m.ram[0x36] == 0)

print('Laufzeit')
prog = {0: (ZUF, 6), 1: (ZUF, 6), 2: (ZUF, 6), 3: (ZUF, 6), 4: (ZUF, 6), 5: (ZUF, 6), 6: (ZUF, 6), 7: (ZUF, 6),
        8: (ZUF, 6), 9: (ZUF, 6), 10: (HLT, 0)}
prog2 = {i: (AKO, 6) for i in range(10)}; prog2[10] = (HLT, 0)
def dauer(p):
    m = CP1(ROM)
    for n, w in p.items(): setze(m, n, w)
    t = m.us + 50_000; m.drueck('run', t, 100)
    m.bis(t + 5_000_000, lambda m: m.ram[0x38] >= 1)
    t1 = m.us
    m.bis(t1 + 5_000_000, lambda m: m.ram[0x38] == 11)
    return (m.us - t1) / 9
d1, d2 = dauer(prog), dauer(prog2)
print(f'  ZUF 6 ≈ {d1 / 1000:.2f} ms, AKO ≈ {d2 / 1000:.2f} ms pro Befehl')
pruef('ZUF unter 2 ms', d1 < 2000, (d1, d2))

print('ALLES OK' if f == 0 else f'{f} FEHLER')
sys.exit(1 if f else 0)
