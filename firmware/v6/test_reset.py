"""5.02: NIE 09 = Reset wie beim Einschalten: alles RAM weg (8049 ganz, beide 8155), Version, Autoboot."""
import sys
sys.path.insert(0, '.')
from sim48 import CP1, SPIFlash, text
import random
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

ROM = open('cp1v6-eeprom.bin', 'rb').read()
FEHLER = []
def pruef(name, ok, info=''):
    print(('  ok   ' if ok else '  FEHL ') + name + (f'  [{info}]' if info else '')); ok or FEHLER.append(name)

_push = CP1.push
def push(self):
    self.sp_max = max(getattr(self, 'sp_max', 0), (self.psw & 7) + 1); _push(self)
CP1.push = push

def neu(fl=None):
    m = CP1(ROM, True, flash=fl or SPIFlash()); m.bis(m.us + 1_600_000); pi = Pi(); m.pi = pi; return m, pi

def reset(m, pi):
    ende = pi.schicke(m, m.us + 20_000, rahmen(9, 0, 0)); m.bis(ende + 2_000); return ende

def alles_leer(m):
    return all(b == 0 for b in m.intern.ram[:256]) and all(b == 0 for b in m.cp3.ram[:256])

def tippe(m, tasten, abstand=180, dauer=120):
    t = m.us + 50_000
    for k in tasten:
        k, d = k if isinstance(k, tuple) else (k, dauer)
        m.drueck(k, t, d); t += d * 1000 + abstand * 1000
    m.bis(t)

print('1) Leerlauf: Reset löscht alles')
m, pi = neu()
for i in range(256): m.intern.ram[i] = (i * 7 + 1) & 0xFF; m.cp3.ram[i] = (i * 3 + 5) & 0xFF
for a in range(0x48, 0x80): m.ram[a] = 0x5A
m.ram[0x47] = 0x5A                                 # OVF-Schalter verstellt
m.ram[0x38] = 77; m.ram[0x37] = 42
reset(m, pi); m.bis(m.us + 400_000)
pruef('Version „  6.21 “ nach dem Reset', list(m.anzeige()) == [0, 0, 0xfd, 0x5b, 0x06, 0], str([hex(x) for x in m.anzeige()]))
m.bis(m.us + 1_500_000)
pruef('beide 8155 leer', alles_leer(m), f'{bytes(m.intern.ram[:8]).hex()} {bytes(m.cp3.ram[:8]).hex()}')
pruef('internes RAM 0x20..0x7F leer bis auf Anzeige/Fernsteuerung', all(m.ram[a] == 0 for a in range(0x48, 0x60)) and m.ram[0x38] == 0 and m.ram[0x37] == 0,
      bytes(m.ram[0x36:0x60]).hex())
pruef('OVF-Schalter 0x47 wieder wie nach dem Einschalten (0)', m.ram[0x47] == 0)
pruef('Anzeige P .000, Fernsteuerung an', text(m.anzeige()) == 'P  000' and m.ram[0x46] & 1 == 1, f'{text(m.anzeige())!r} {m.ram[0x46]:02x}')
r = befehl(m, pi, 2, 0x20, 6, 6)
pruef('NIE geht danach (02)', r == list(m.ram[0x20:0x26]), str(r))
tippe(m, ['1', '2', '3', 'pc']); m.bis(m.us + 200_000)
pruef('Tasten gehen danach (PC = 123)', m.ram[0x38] == 123, str(m.ram[0x38]))

print('2) Endlosprogramm mit JSR (Interrupt tief im Stapel)')
m, pi = neu()
m.intern.ram[0:8] = bytes([32, 2, 9, 0, 9, 2, 33, 0])     # JSR 2 | SPU 2 (endlos im Unterprogramm)
m.drueck('run', m.us + 20_000, 120); m.bis(m.us + 300_000)
pruef('Programm läuft', m.ram[0x3a] & 1 == 1 or text(m.anzeige()) != 'P  000', f'{m.ram[0x3a]:02x} {text(m.anzeige())!r}')
m.sp_max = 0
reset(m, pi); m.bis(m.us + 1_800_000)
pruef('Reset holt ihn raus: alles leer, P 000', alles_leer(m) and text(m.anzeige()) == 'P  000', text(m.anzeige()))
tippe(m, ['5', 'pc']); m.bis(m.us + 200_000)
pruef('danach Tasten normal (5 PC -> F 001)', text(m.anzeige()) == 'F  001', text(m.anzeige()))
r = befehl(m, pi, 5, 0, 4, 4)
pruef('NIE 05 danach', r == [0, 0, 0, 0], str(r))

print('3) mitten in der Abfrage „Pro __“')
m, pi = neu()
tippe(m, ['cas', '0'])
reset(m, pi); m.bis(m.us + 1_800_000)
pruef('wieder P 000', text(m.anzeige()) == 'P  000', text(m.anzeige()))
r = befehl(m, pi, 4, 0x08, 0, 1)
pruef('Leerlauf erkannt: Auftrag $08 angenommen', r == [0x08], str(r))
m.bis(m.us + 5_000_000, halt=lambda mm: mm.ram[0x26] == 0)

print('4) Autoboot läuft wie beim Einschalten')
fl = SPIFlash()
m, pi = neu(fl)
m.intern.ram[0:4] = bytes([4, 42, 1, 0])          # AKO 42, HLT
tippe(m, ['cas', '0', '4', 'cas']); m.bis(m.us + 3_500_000)
tippe(m, [('run', 1300), '0', '4', 'run']); m.bis(m.us + 2_000_000)
reset(m, pi); m.bis(m.us + 1_900_000)
pruef('„bot 04“ nach dem Reset', text(m.anzeige()) == 'bot 04', text(m.anzeige()))
m.bis(m.us + 3_500_000)
pruef('Projekt 4 geladen und gelaufen (Akku 42)', m.ram[0x37] == 42, f'{m.ram[0x37]} {text(m.anzeige())!r}')

print('5) falsches Prüfbyte: kein Reset')
m, pi = neu()
m.intern.ram[10] = 99
f = rahmen(9, 0, 0); f[3] ^= 1
ende = pi.schicke(m, m.us + 20_000, f); m.bis(ende + 1_000_000)
pruef('Zelle 5 bleibt', m.intern.ram[10] == 99)
print('6) Reset-Taste: CLR halten + STP')
def akkord(m, halten='clr', dann='stp'):
    t = m.us + 50_000
    m.drueck(halten, t, 700); m.drueck(dann, t + 300_000, 150); m.bis(t + 900_000)
m, pi = neu()
m.intern.ram[10] = 99; m.cp3.ram[10] = 98
akkord(m); m.bis(m.us + 100_000)
pruef('Leerlauf: Version „6.21“ erscheint', list(m.anzeige())[2:5] == [0xfd, 0x5b, 0x06], str([hex(x) for x in m.anzeige()]))
m.bis(m.us + 1_500_000)
pruef('… und alles RAM ist weg', alles_leer(m) and text(m.anzeige()) == 'P  000', text(m.anzeige()))
m, pi = neu()
m.intern.ram[10] = 99
tippe(m, ['stp']); m.bis(m.us + 1_500_000)
pruef('STP allein: kein Reset', m.intern.ram[10] == 99 and text(m.anzeige()) == 'P  000', text(m.anzeige()))
tippe(m, [('clr', 700)]); m.bis(m.us + 1_500_000)
pruef('CLR allein: kein Reset', m.intern.ram[10] == 99)
akkord(m, 'cas', 'stp'); m.bis(m.us + 1_500_000)
pruef('CAS (gleiche Reihe wie CLR) + STP: kein Reset', m.intern.ram[10] == 99, text(m.anzeige()))
print('7) Reset-Taste bei laufendem Programm')
m, pi = neu()
m.intern.ram[0:8] = bytes([32, 2, 9, 0, 9, 2, 33, 0])     # JSR 2 | SPU 2 (endlos)
m.drueck('run', m.us + 20_000, 120); m.bis(m.us + 300_000)
akkord(m); m.bis(m.us + 1_800_000)
pruef('Programm weg, alles leer, P 000', alles_leer(m) and text(m.anzeige()) == 'P  000', text(m.anzeige()))
r = befehl(m, pi, 2, 0x20, 6, 6)
pruef('NIE danach', r == list(m.ram[0x20:0x26]), str(r))

print('\nALLES OK' if not FEHLER else f'\n{len(FEHLER)} FEHLER: {FEHLER}')
sys.exit(1 if FEHLER else 0)
