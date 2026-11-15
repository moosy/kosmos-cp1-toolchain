"""4.0: Fernsteuerbefehl 03 (RAM schreiben) und Flash-Auftrag über die simulierte Leitung, wie kosmos_remote es macht."""
import sys
sys.path.insert(0, '.')
src = open('test_rc.py').read()
exec(src[:src.index("def rc_an")] + src[src.index("def rc_an"):].split('\n\n')[0])
from sim48 import SPIFlash
F_JOB, F_BANK, F_NAME = 0x26, 0x2c, 0x60

def befehl(m, pi, t, cmd, a, b, n_antw=0):
    ende = pi.schicke(m, t, rahmen(cmd, a, b)); m.bis(ende + 40_000)
    out, _ = antwort(m, ende, n_antw + 1); return out, m.us

fl = SPIFlash()
m = CP1(ROM, True, flash=fl); m.bis(300_000); pi = Pi(); m.pi = pi
t = rc_an(m)
print('03: Name, Bank und Auftrag schreiben')
alles_ok = True
for i, c in enumerate(b'Fernsteuerung!  '):
    out, t = befehl(m, pi, t + 20_000, 3, F_NAME + i, c)
    alles_ok &= out[:1] == [0xA5]
pruef('16 x 03 quittiert ($A5)', alles_ok)
pruef('Name im RAM', bytes(m.ram[F_NAME:F_NAME + 16]) == b'Fernsteuerung!  ', str(bytes(m.ram[F_NAME:F_NAME + 16])))
for c in (0x20, 0x22): pass
m.intern.ram[0:2] = bytes([4, 99])
out, t = befehl(m, pi, t + 20_000, 3, F_BANK, 33)
out, t = befehl(m, pi, t + 20_000, 3, F_JOB, 0x81)
r, s = taste_code('cal')
out, t = befehl(m, pi, t + 20_000, 1, r << 4 | s, 6)
m.bis(t + 3_000_000)
b = fl.m[33 * 0x2000 + 0x1000:33 * 0x2000 + 0x1000 + 0x212]
pruef('Auftrag $81 per CAL: Bank 33 mit Name gespeichert', m.ram[F_JOB] == 0 and b[0:2] == bytes([4, 99]) and b[0x200:0x210] == b'Fernsteuerung!  ' and b[0x211] == 0,
      f'{text(m.anzeige())!r} {bytes(b[0x200:0x210])}')
out, t = befehl(m, pi, m.us + 20_000, 2, F_JOB, 1, 1)
pruef('02 liest F_JOB = 0 (fertig)', out[:2] == [0, 0 ^ 0xA5], str(out))
print('ALLES OK' if not FEHLER else f'{len(FEHLER)} FEHLER: {FEHLER}')
