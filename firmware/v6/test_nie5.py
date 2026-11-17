"""5.00: NIE (Fernsteuerung im Interrupt) mit 50/150-µs-Bits: Status, Tasten, 02/03, Attention 04, Zellen 05..08."""
import sys, random
sys.path.insert(0, '.')
from sim48 import CP1, SPIFlash, text, TASTEN
from pi_fni import FNIPi
ROM = open('cp1v6-eeprom.bin', 'rb').read()
FEHLER = []
def pruef(name, ok, info=''):
    print(('  ok   ' if ok else '  FEHL ') + name + (f'  [{info}]' if info else '')); ok or FEHLER.append(name)

_push = CP1.push
def push(self):
    self.sp_max = max(getattr(self, 'sp_max', 0), (self.psw & 7) + 1)
    _push(self)
CP1.push = push

def rahmen(cmd, a, b):
    return [cmd, a, b, cmd ^ a ^ b ^ 0xA5]

def wellenform(t0, bytes_, kurz=50, lang=150, pause=50, zittern=0, rnd=random.Random(3)):
    lows = [(t0, t0 + 8500)]; t = t0 + 8500 + 300
    for byte in bytes_:
        for i in range(8):
            d = (kurz if byte >> i & 1 else lang) + rnd.uniform(-zittern, zittern)
            lows.append((t, t + d)); t += d + pause + rnd.uniform(0, zittern)
    return lows, t

class Pi:
    def __init__(self): self.lows = []
    def __call__(self, t):
        for a, b in self.lows[-40:]:
            if a <= t < b: return 0
        return 1
    def schicke(self, m, t0, bytes_, **kw):
        l, ende = wellenform(t0, bytes_, **kw); self.lows += l; return ende

def antwort(m, ab, n):
    log = [(t, l) for t, l in m.p1_log if t >= ab]
    pulse = [t2 - t1 for (t1, l1), (t2, l2) in zip(log, log[1:]) if l1 == 0 and l2 == 1]
    bits = [1 if p < 100 else 0 for p in pulse]
    out = [sum(b << k for k, b in enumerate(bits[i:i + 8])) for i in range(0, len(bits) - 7, 8)]
    return out, pulse

def befehl(m, pi, cmd, a, b, n=0, **kw):
    """-> Datenbytes (Prüfbyte geprüft) oder None"""
    ende = pi.schicke(m, m.us + 20_000, rahmen(cmd, a, b), **kw)
    m.bis(ende + 6_000 + 3_000 * (n + 1))
    r, _ = antwort(m, ende, n)
    if len(r) < n + 1: return None
    chk = 0xA5
    for x in r[:n]: chk ^= x
    return r[:n] if chk == r[n] else None

def neu(cp3=True, flash=None):
    m = CP1(ROM, cp3, flash=flash or SPIFlash()); m.bis(m.us + 100_000); pi = Pi(); m.pi = pi; return m, pi

def zelle(m, n, b=None, a=None):
    chip, adr = (m.intern, 2 * n) if n < 128 else (m.cp3, 2 * (n - 128))
    if b is None: return chip.ram[adr], chip.ram[adr + 1]
    chip.ram[adr] = b; chip.ram[adr + 1] = a

def taste(m, pi, name, dauer=8):
    z, s = TASTEN[name]
    return befehl(m, pi, 1, (6 - z) << 4 | (1 << s), dauer)

print('1) Fernsteuerung ist von Anfang an an; Status durch Anklopfen')
m, pi = neu()
pruef('RC_FLAG = 1', m.ram[0x46] & 1 == 1, hex(m.ram[0x46]))
t0 = m.us + 20_000
pi.lows.append((t0, t0 + 3500)); m.bis(t0 + 3500 + 100_000)
r, pulse = antwort(m, t0 + 3500, 27)
pruef('27 Byte Status (RAM 0x20..)', len(r) >= 28 and r[:6] == list(m.ram[0x20:0x26]), f'{len(r)} {r[:6]}')
print(f'     Pulse CP1 -> Pi: {round(min(pulse))} … {round(max(pulse))} µs')
pruef('Pulse ~50 und ~150 µs', min(pulse) > 35 and max(pulse) < 175 and any(p < 80 for p in pulse) and any(p > 120 for p in pulse), f'{min(pulse):.0f}..{max(pulse):.0f}')

print('2) 02: RAM lesen, auch mit gestörten Pi-Pulsen')
r = befehl(m, pi, 2, 0x36, 4, 4)
pruef('Akku/PC lesen', r == list(m.ram[0x36:0x3a]), str(r))
r = befehl(m, pi, 2, 0x20, 6, 6, zittern=25)
pruef('mit Zittern ±25 µs', r == list(m.ram[0x20:0x26]), str(r))
r = befehl(m, pi, 2, 0x20, 6, 6, kurz=75, lang=150)
pruef('kurze Pulse bis 75 µs gedehnt (Pi unterbrochen)', r == list(m.ram[0x20:0x26]), str(r))
f = rahmen(2, 0x20, 6); f[3] ^= 1
ende = pi.schicke(m, m.us + 20_000, f); m.bis(ende + 30_000)
pruef('falsches Prüfbyte: keine Antwort', antwort(m, ende, 6)[0] == [])

print('3) 01 Tasten, 03 RAM schreiben')
for k in ['1', '2', '3', 'pc']:
    taste(m, pi, k); m.bis(m.us + 250_000)
pruef('PC = 123 aus der Ferne', m.ram[0x38] == 123, str(m.ram[0x38]))
befehl(m, pi, 3, 0x2C, 99)
pruef('03: RAM 0x2C = 99', m.ram[0x2C] == 99)

print('4) 04 Attention: Auftrag nur im Leerlauf')
befehl(m, pi, 3, 0x2C, 0)                         # F_BANK = 0
r = befehl(m, pi, 4, 0x08, 0, 1)                  # $08: Autoboot (Bank 0 = aus)
pruef('angenommen: Antwort = $08', r == [0x08], str(r))
m.bis(m.us + 5_000_000, halt=lambda mm: mm.ram[0x26] == 0)
pruef('Auftrag lief (F_JOB = 0, „bot rdY“)', m.ram[0x26] == 0 and text(m.anzeige()) == 'botrdY', f'{m.ram[0x26]:02x} {text(m.anzeige())}')
r = befehl(m, pi, 4, 0x08, 0, 1)
r2 = befehl(m, pi, 4, 0x04, 0, 1)
pruef('zweiter Auftrag gleich danach: erst angenommen, der nächste abgelehnt', r == [0x08] and r2 is not None and r2 != [0x04], f'{r} {r2}')
m.bis(m.us + 5_000_000, halt=lambda mm: mm.ram[0x26] == 0)
m2, pi2 = neu()
m2.intern.ram[0:10] = bytes([31, 0, 6, 50, 2, 0, 9, 0, 0, 0])   # TST, ABS 50, ANZ, SPU 0
m2.drueck('run', m2.us + 20_000, 120); m2.bis(m2.us + 400_000)
r = befehl(m2, pi2, 4, 0x08, 0, 1)
pruef('Programm läuft: abgelehnt (Antwort = altes F_JOB)', r == [0] and m2.ram[0x26] == 0, str(r))
m3, pi3 = neu()
m3.drueck('cas', m3.us + 20_000, 120); m3.bis(m3.us + 400_000)
r = befehl(m3, pi3, 4, 0x08, 0, 1)
pruef('in der Abfrage „bAn ___“: abgelehnt', r == [0], f'{r} {text(m3.anzeige())}')

print('5) 05..08: Zellen lesen/schreiben, auch während ein Programm läuft')
m, pi = neu()
m.intern.ram[0:8] = bytes([5, 50, 2, 0, 9, 0, 0, 0])            # LDA 50, ANZ, SPU 0
zelle(m, 50, 0, 7); zelle(m, 200, 3, 44)
m.drueck('run', m.us + 20_000, 120); m.bis(m.us + 300_000)
r = befehl(m, pi, 5, 100, 4, 4)
pruef('05: Zellen 50/51 (Bytes 100..103) aus der internen 8155', r == list(m.intern.ram[100:104]), str(r))
r = befehl(m, pi, 6, 144, 2, 2)
pruef('06: Zelle 200 aus der CP3', r == [3, 44], str(r))
befehl(m, pi, 7, 101, 99); m.bis(m.us + 100_000)
pruef('07: Zelle 50 = 99 -> laufendes Programm zeigt 99', zelle(m, 50) == (0, 99) and m.ram[0x37] == 99, f'{zelle(m, 50)} Akku {m.ram[0x37]}')
befehl(m, pi, 8, 145, 55)
pruef('08: CP3-Zelle 200 Argument = 55', zelle(m, 200) == (3, 55), str(zelle(m, 200)))
pruef('Programm läuft weiter, Anzeige zeigt Akku', text(m.anzeige()).endswith('099'), text(m.anzeige()))
r = befehl(m, pi, 2, 0x20, 6, 6)
pruef('danach wieder internes RAM (02)', r == list(m.ram[0x20:0x26]), str(r))

print('6) Stapeltiefe: Zellen lesen während JSR/SEG im Programm')
m, pi = neu()
m.sp_max = 0
m.intern.ram[0:8] = bytes([32, 2, 9, 0, 27, 100, 33, 0])        # JSR 2, SPU 0 | SEG 100, RET
m.drueck('run', m.us + 20_000, 120); m.bis(m.us + 200_000)
for i in range(6):
    befehl(m, pi, 5, 0, 8, 8)
print('     höchste Stapelebene:', m.sp_max, 'von 8')
pruef('höchstens 7 Ebenen (0x16/0x17 bleiben frei)', m.sp_max <= 7, str(m.sp_max))

print('7) ganzer Weg: 03 Parameter + 04 Auftrag + FNI P-C')
m, pi = neu()
for adr, w in ((0x2C, 0), (0x3C, 20), (0x3D, 8)): befehl(m, pi, 3, adr, w)
daten = bytes(range(1, 17))
m.geraet = FNIPi('ein', (0x20, 0, 20, 8), daten)
ende = pi.schicke(m, m.us + 20_000, rahmen(4, 0x20, 0))   # bei FNI: Annahme = T geht low (keine Antwort)
m.bis(ende + 100_000, halt=lambda mm: mm.takt() == 0)
pruef('04 angenommen: T geht low', m.takt() == 0 and m.ram[0x26] == 0x20, f'T={m.takt()} F_JOB={m.ram[0x26]:02x}')
m.bis(m.us + 2_000_000, halt=lambda mm: mm.ram[0x26] == 0 and mm.geraet.fertig)
pruef('Zellen 20..27 angekommen, F_JOB = 0', b''.join(bytes(zelle(m, n)) for n in range(20, 28)) == daten and m.ram[0x26] == 0, f'{m.geraet.fehler}')
m.geraet = None
r = befehl(m, pi, 2, 0x20, 6, 6)
pruef('danach NIE wieder normal', r == list(m.ram[0x20:0x26]), str(r))
print('\nALLES OK' if not FEHLER else f'\n{len(FEHLER)} FEHLER: {FEHLER}')
sys.exit(1 if FEHLER else 0)
