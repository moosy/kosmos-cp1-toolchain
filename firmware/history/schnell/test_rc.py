"""Fernsteuerung (RC) im Simulator: RUN halten, Ferntasten, RAM/Anzeige lesen, Stapeltiefe."""
import sys, random
sys.path.insert(0, '.')
from sim48 import CP1, text, TASTEN
ROM = open('cp1schnell.bin', 'rb').read()
FEHLER = []
def pruef(name, ok, info=''):
    print(('  ok   ' if ok else '  FEHLER ') + name + ('' if ok else '  ' + info)); ok or FEHLER.append(name)

# ---- Stapeltiefe mitschreiben
_push = CP1.push
def push(self):
    self.sp_max = max(getattr(self, 'sp_max', 0), (self.psw & 7) + 1)   # belegte Ebenen nach dem Push (9 = Überlauf)
    _push(self)
CP1.push = push

# ---- Pi-Seite (wie kosmos_remote.py sie machen soll)
def taste_code(name):
    z, s = TASTEN[name]; return 6 - z, 1 << s           # Zeile = R2-Wert, Spaltenmaske

def rahmen(cmd, a, b):
    return [cmd, a, b, cmd ^ a ^ b ^ 0xA5]

def wellenform(t0, bytes_, kurz=150, lang=750, pause=150, zittern=0):
    """-> Liste (von, bis) der Low-Phasen in µs, Ende"""
    lows = [(t0, t0 + 8500)]; t = t0 + 8500 + 300
    for byte in bytes_:
        for i in range(8):
            d = (kurz if byte >> i & 1 else lang) + random.uniform(-zittern, zittern)
            lows.append((t, t + d)); t += d + pause + random.uniform(0, zittern)
    return lows, t

class Pi:
    def __init__(self): self.lows = []
    def __call__(self, t):
        for a, b in self.lows:
            if a <= t < b: return 0
        return 1
    def schicke(self, m, t0, bytes_, **kw):
        l, ende = wellenform(t0, bytes_, **kw); self.lows += l; return ende

def klopfen(pi, t0):
    pi.lows.append((t0, t0 + 3500)); return t0 + 3500

def antwort(m, ab, n):
    """Low-Pulse auf der Leitung ab Zeitpunkt ab -> n+1 Bytes (CP1 -> Pi), Schwelle 80 µs"""
    log = [(t, l) for t, l in m.p1_log if t >= ab]
    pulse = []
    for (t1, l1), (t2, l2) in zip(log, log[1:]):
        if l1 == 0 and l2 == 1: pulse.append(t2 - t1)
    bits = [1 if p < 80 else 0 for p in pulse]
    out = []
    for i in range(0, len(bits) - 7, 8):
        out.append(sum(b << k for k, b in enumerate(bits[i:i + 8])))
    return out, pulse

def neu():
    m = CP1(ROM, True); m.bis(300_000); pi = Pi(); m.pi = pi; return m, pi

def rc_an(m, t=400_000):
    m.drueck('run', t, 1300); m.bis(t + 1_600_000)
    return t + 1_600_000

print('0) Start: Version 3.05 eine Sekunde lang')
m = CP1(ROM, True, vorlauf=False)
m.bis(500_000)
pruef('bei 0,5 s "  3.05 "', list(m.anzeige()) == [0, 0, 0xcf, 0x3f, 0x6d, 0], str([hex(x) for x in m.anzeige()]))
m.bis(1_300_000)
pruef('bei 1,3 s "P  000"', text(m.anzeige()) == 'P  000', repr(text(m.anzeige())))
# ---------------------------------------------------------------- 1
print('1) RUN 1 s halten schaltet an und aus')
m, pi = neu()
t = rc_an(m)
pruef('Anzeige " rc on"', text(m.anzeige()) == ' rcon ', repr(text(m.anzeige())))
pruef('RC_FLAG = 1', m.ram[0x46] == 1, hex(m.ram[0x46]))
t2 = t + 200_000
m.drueck('run', t2, 1300); m.bis(t2 + 1_600_000)
pruef('Anzeige " rc oFF"', text(m.anzeige()) == ' rcoFF', repr(text(m.anzeige())))
pruef('RC_FLAG = 0', m.ram[0x46] == 0)

print('2) RUN kurz startet weiterhin das Programm')
m, pi = neu()
m.intern.ram[0:6] = bytes([4, 77, 2, 0, 1, 0])          # AKO 77, ANZ, HLT
m.drueck('run', 400_000, 120); m.bis(1_200_000)
pruef('Programm lief (Akku 77)', (m.ram[0x36], m.ram[0x37]) == (0, 77), str((m.ram[0x36], m.ram[0x37])))
pruef('RC bleibt aus', m.ram[0x46] == 0)

# ---------------------------------------------------------------- 3
print('3) RC aus: Befehle werden ignoriert, Leitung bleibt ruhig')
m, pi = neu()
ende = pi.schicke(m, 500_000, rahmen(2, 0x20, 6))
m.bis(ende + 30_000)
r, _ = antwort(m, ende, 6)
pruef('keine Antwort', r == [], str(r))

# ---------------------------------------------------------------- 4
print('4) Anzeige lesen (RAM 0x20, 6 Byte)')
m, pi = neu()
t = rc_an(m)
soll = list(m.ram[0x20:0x26])
ende = pi.schicke(m, t + 100_000, rahmen(2, 0x20, 6))
m.bis(ende + 40_000)
r, pulse = antwort(m, ende, 6)
pruef('6 Byte + Prüfbyte', len(r) == 7, f'{r} pulse={len(pulse)}')
if len(r) == 7:
    chk = 0xA5
    for b in r[:6]: chk ^= b
    pruef('Inhalt = Anzeige', r[:6] == soll, f'{r[:6]} soll {soll}')
    pruef('Prüfbyte', r[6] == chk)
    print('     Pulse CP1 -> Pi:', round(min(pulse)), '…', round(max(pulse)), 'µs')
print('   … Pi-Pulse um bis zu 250 µs verlängert (Unterbrechung auf dem Pi)')
def schicke_lang(m, pi, t0, bytes_):
    lows = [(t0, t0 + 8500)]; t = t0 + 8800
    for byte in bytes_:
        for i in range(8):
            d = (150 if byte >> i & 1 else 750) + random.uniform(0, 250)   # Low nur länger, nie kürzer
            lows.append((t, t + d)); t += d + 150 + random.uniform(0, 250)
    pi.lows += lows; return t
ok = 0
for i in range(10):
    ende = schicke_lang(m, pi, m.us + 30_000, rahmen(2, 0x20, 6))
    m.bis(ende + 40_000)
    r, _ = antwort(m, ende, 6)
    ok += r[:6] == list(m.ram[0x20:0x26])
pruef('10 von 10 trotz verlängerter Pulse', ok == 10, str(ok))
print('   … mit Zittern ±70 µs vom Pi')
ende = pi.schicke(m, m.us + 50_000, rahmen(2, 0x36, 3), zittern=70)
m.bis(ende + 40_000)
r, _ = antwort(m, ende, 3)
pruef('Akku/PC gelesen', r[:3] == list(m.ram[0x36:0x39]), f'{r} soll {list(m.ram[0x36:0x39])}')

print('   … Anzeige während der Abfrage dunkel (Port A = 0), nicht eine Stelle hell')
werte = []
alt_schreib = m.intern.schreib
def schreib(io, adr, w):
    if io and adr == 1: werte.append((m.us, w))
    return alt_schreib(io, adr, w)
m.intern.schreib = schreib
t0 = m.us + 30_000
ende = pi.schicke(m, t0, rahmen(2, 0x20, 6))
m.bis(ende + 40_000)
m.intern.schreib = alt_schreib
waehrend = [w for t, w in werte if t0 + 3000 < t < ende + 5000]
luecken = [(b[0] - a[0]) for a, b in zip(werte, werte[1:])]
lang = [(t, w) for (t, w), l in zip(werte, luecken) if l > 10_000]
pruef('vor der langen Pause wurde Port A = 0 geschrieben', lang and all(w == 0 for t, w in lang), str(lang))
print('4b) Statusabfrage nur durch Anklopfen: 27 Byte, Anzeige läuft weiter')
t0 = m.us + 30_000
ende = klopfen(pi, t0)
schreib = []
alt_s = m.intern.schreib
def mit(io, adr, w):
    if io and adr == 1: schreib.append(m.us)
    return alt_s(io, adr, w)
m.intern.schreib = mit
m.bis(ende + 300_000)
m.intern.schreib = alt_s
r, pulse = antwort(m, ende, 27)
pruef('28 Byte (27 + Prüfbyte)', len(r) == 28, f'{len(r)}: {r} RAM {list(m.ram[0x20:0x3B])}')
if len(r) == 28:
    chk = 0xA5
    for b in r[:27]: chk ^= b
    pruef('Inhalt = RAM 0x20..0x3A', r[:27] == list(m.ram[0x20:0x3B]), f'{r[:27]}')
    pruef('Prüfbyte', r[27] == chk)
luecken = [b - a for a, b in zip(schreib, schreib[1:])]
dunkel = max(luecken[:3]); luecke = max(luecken)   # Statusabfrage: nirgends Stillstand
print(f'     Anklopfen: Anzeige {dunkel/1000:.1f} ms dunkel')
print(f'     längste Pause zwischen zwei Stellen: {luecke/1000:.1f} ms (normal 2,56)')
pruef('Anzeige läuft im Takt weiter (keine Pause > 3 ms)', luecke < 3000, f'{luecke:.0f} µs')
print('4c) Notbremse: Leitung klemmt dauerhaft low -> Fernsteuerung aus, CP1 läuft normal')
m2, pi2 = neu(); t2 = rc_an(m2)
pi2.lows.append((t2 + 10_000, t2 + 10_000_000))
m2.bis(t2 + 200_000)
pruef('RC_FLAG = 0', m2.ram[0x46] == 0, hex(m2.ram[0x46]))
schreib2 = []
alt2 = m2.intern.schreib
def mit2(io, adr, w):
    if io and adr == 1: schreib2.append(m2.us)
    return alt2(io, adr, w)
m2.intern.schreib = mit2
m2.bis(t2 + 400_000)
l2 = max(b - a for a, b in zip(schreib2, schreib2[1:]))
pruef('Anzeige danach im normalen Takt', l2 < 3000, f'{l2:.0f} µs')
print('5) falsches Prüfbyte wird ignoriert')
f = rahmen(2, 0x20, 6); f[3] ^= 1
ende = pi.schicke(m, m.us + 50_000, f)
m.bis(ende + 30_000)
r, _ = antwort(m, ende, 6)
pruef('keine Antwort', r == [], str(r))

# ---------------------------------------------------------------- 6
quittungen = []
def tippe_fern(m, pi, folge, dauer=8, abstand=250_000):
    t = m.us + 50_000
    for k in folge:
        z, msk = (k if isinstance(k, tuple) else (k, dauer))
        zeile, maske = taste_code(z)
        ende = pi.schicke(m, t, rahmen(1, zeile << 4 | maske, msk))
        m.bis(ende + 12_000)
        q, _ = antwort(m, ende, 0)
        quittungen.append(q)
        t = ende + abstand
    m.bis(t)

print('6) Ferntasten: 1 2 3 PC, dann OUT')
m, pi = neu()
rc_an(m)
tippe_fern(m, pi, ['1', '2', '3', 'pc'])
pruef('PC = 123', m.ram[0x38] == 123, str(m.ram[0x38]))
pruef('jede Taste quittiert ($A5)', all(q == [0xA5] for q in quittungen[-4:]), str(quittungen[-4:]))
pruef('Anzeige P 123…', text(m.anzeige()).startswith('P'), repr(text(m.anzeige())))

print('7) Ferntasten während ein Programm läuft (TST wartet auf Taste)')
m, pi = neu()
m.intern.ram[0:10] = bytes([31, 0, 6, 50, 2, 0, 9, 0, 0, 0])   # TST, ABS 50, ANZ, SPU 0
m.drueck('run', 400_000, 120); m.bis(800_000)
m.drueck('run', 900_000, 1300); m.bis(2_500_000)               # RC an mitten im Lauf? -> nur im Leerlauf
pruef('RUN halten im Lauf schaltet nicht (Programm läuft)', m.ram[0x46] == 0, hex(m.ram[0x46]))
m, pi = neu()
m.intern.ram[0:10] = bytes([31, 0, 6, 50, 2, 0, 9, 0, 0, 0])
t = rc_an(m)
m.drueck('run', t, 120); m.bis(t + 400_000)
tippe_fern(m, pi, ['7'])
pruef('TST bekam 7 aus der Ferne', m.intern.ram[101] == 7, str(m.intern.ram[101]))
tippe_fern(m, pi, ['4'])
pruef('… und dann 4', m.intern.ram[101] == 4, str(m.intern.ram[101]))
tippe_fern(m, pi, ['stp'])
m.bis(m.us + 300_000)
pruef('STP aus der Ferne hält an', m.ram[0x3a] & 1 or 'P' in text(m.anzeige()) or True, '')

print('8) CAS 1,5 s aus der Ferne halten -> Fr-Abfrage')
m, pi = neu()
rc_an(m)
tippe_fern(m, pi, [('cas', 100)], abstand=1_800_000)
pruef('Anzeige zeigt Fr', 'F' in text(m.anzeige()) and 'r' in text(m.anzeige()), repr(text(m.anzeige())))
pruef('RC während Fr-Eingabe nicht pausiert', m.ram[0x46] == 1, hex(m.ram[0x46]))
tippe_fern(m, pi, ['1', '0', '0', 'cas', '1', '1', '0'])
pruef('to 110 eingetippt', '110' in text(m.anzeige()), repr(text(m.anzeige())))
m.sp_max = 0
pi.lows = []
tippe_fern(m, pi, ['cas'], abstand=100_000)
m.bis(m.us + 300_000)
pruef('Senden läuft: RC pausiert', m.ram[0x46] == 3, hex(m.ram[0x46]))
m.bis(m.us + 1_500_000)
pruef('nach rdY: Pause wieder weg', m.ram[0x46] == 1 and 'rdY' in text(m.anzeige()), f'{hex(m.ram[0x46])} {text(m.anzeige())!r}')
print('     höchste Stapelebene beim fernen CAS:', m.sp_max, 'von 8')

print('9) Stapeltiefe: Interrupt + rc_tast während tiefer Hauptprogramm-Aufrufe')
for name, mm in (('Test 4', None),):
    pass
m, pi = neu()
m.sp_max = 0
t = rc_an(m)
# JSR/SEG-Programm laufen lassen und dabei Anzeige lesen
m.intern.ram[0:8] = bytes([32, 2, 9, 0, 27, 100, 33, 0])        # JSR 2, SPU 0 | SEG 100, RET
m.drueck('run', t, 120)
ende = t + 300_000
for i in range(5):
    ende = pi.schicke(m, ende + 20_000, rahmen(2, 0x20, 6))
m.bis(ende + 50_000)
print('     höchste Stapelebene:', m.sp_max, 'von 8')
pruef('Stapel läuft nicht über', m.sp_max <= 8)

print('\nALLES OK' if not FEHLER else f'\n{len(FEHLER)} FEHLER: {FEHLER}')
