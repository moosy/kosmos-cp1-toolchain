"""5.00: FNI (Interrupt aus, getaktet über T = P1.6 / D = P1.7) im Simulator mit Pi-Modell."""
import sys, time
sys.path.insert(0, '.')
from sim48 import CP1, SPIFlash, text
from pi_fni import FNIPi, crc8, bloecke
ROM = open('cp1v5-eeprom.bin', 'rb').read()
F_JOB, F_BANK, F_ANF, F_ANZ, F_START, F_NAME, RC_FLAG = 0x26, 0x2C, 0x3C, 0x3D, 0x3E, 0x60, 0x46
fehler = 0
def pruef(name, ok, info=''):
    global fehler
    print(('  ok   ' if ok else '  FEHL ') + name + (f'  [{info}]' if info else ''))
    if not ok: fehler += 1

def zelle(m, n, b=None, a=None):
    chip, adr = (m.intern, 2 * n) if n < 128 else (m.cp3, 2 * (n - 128))
    if b is None: return chip.ram[adr], chip.ram[adr + 1]
    chip.ram[adr] = b; chip.ram[adr + 1] = a

def bank(fl, b):
    """gültiger Sektor von Bank b (Generation beachten)"""
    s0, s1 = fl.m[b * 0x2000: b * 0x2000 + 0x1000], fl.m[b * 0x2000 + 0x1000: b * 0x2000 + 0x2000]
    g0, g1 = s0[0x211] == 0, s1[0x211] == 0
    if g0 and g1: return s1 if (s0[0x210] + 1) & 0xFF == s1[0x210] else s0
    return s1 if g1 else s0 if g0 else None

def auftrag(m, jj, bank_=0, anf=0, anz=0, start=255, name=None, pi=None, frist_ms=4000):
    """wie NIE 03 (Parameter) + 04 jj: Parameter setzen, Auftrag als wartend markieren"""
    m.ram[F_BANK] = bank_; m.ram[F_ANF] = anf; m.ram[F_ANZ] = anz; m.ram[F_START] = start
    if name is not None: m.ram[F_NAME:F_NAME + 16] = name.encode().ljust(16, b'\xff')[:16]
    m.ram[F_JOB] = jj; m.ram[0x17] = 0x0D        # wie NIE 04: AUFTRAG = Taste CAL
    m.geraet = pi
    t0 = m.us
    m.bis(m.us + frist_ms * 1000, halt=lambda mm: mm.ram[F_JOB] in (0, 0xEE) and (pi is None or pi.fertig) and mm.tcnti)
    m.bis(m.us + 30_000)
    return (m.us - t0) / 1000

fl = SPIFlash()
m = CP1(ROM, True, flash=fl)
m.bis(m.us + 100_000)

print('P-C: Pi -> 8155, 40 Zellen ab 10 (nicht an 4er-Grenze)')
daten = bytes((7 * i + 3) & 0xFF for i in range(80))
pi = FNIPi('ein', (0x20, 0, 10, 40), daten)
ms = auftrag(m, 0x20, 0, 10, 40, pi=pi)
ram = b''.join(bytes(zelle(m, n)) for n in range(10, 50))
pruef('Zellen 10..49 angekommen', ram == daten, f'{ram[:8].hex()}')
pruef('F_JOB = 0, Pi ohne Fehler', m.ram[F_JOB] == 0 and pi.fehler is None, f'{m.ram[F_JOB]:02x} {pi.fehler}')
pruef('Anzeige „P-C rdY“, Interrupt wieder an', text(m.anzeige()) == 'P-CrdY' and m.tcnti, text(m.anzeige()))
pruef('Zelle 9 und 50 unberührt', zelle(m, 9) == (0, 0) and zelle(m, 50) == (0, 0))
print(f'     {ms:.0f} ms Simulationszeit für 40 Zellen, {pi.bits} Bits')

print('C-P: 8155 -> Pi, Zellen 3..12')
for n in range(3, 13): zelle(m, n, n, 100 + n)
pi = FNIPi('aus', (0x21, 0, 3, 10))
auftrag(m, 0x21, 0, 3, 10, pi=pi)
erw = b''.join(bytes([n, 100 + n]) for n in range(3, 13))
pruef('Pi hat die Zellen', bytes(pi.empfangen) == erw and pi.fehler is None, f'{bytes(pi.empfangen).hex()} {pi.fehler}')
pruef('F_JOB = 0, „C-P rdY“', m.ram[F_JOB] == 0 and text(m.anzeige()) == 'C-PrdY', text(m.anzeige()))

print('P-F: Pi -> Flash Bank 7, Zellen 100..109, Name, Start 20 ins Verzeichnis')
d7 = bytes([0, 11, 4, 22, 0, 33, 7, 44, 0, 55, 0, 66, 1, 77, 0, 88, 0, 99, 0, 111])
pi = FNIPi('ein', (0x23, 7, 100, 10), d7)
ms = auftrag(m, 0x23, 7, 100, 10, start=20, name='Testbank', pi=pi)
s = bank(fl, 7)
pruef('Bank gültig, Zellen 100..109', s is not None and bytes(s[200:220]) == d7, '' if s is None else s[198:222].hex())
pruef('Rest der Bank 00, Name „Testbank“', s is not None and bytes(s[0:200]) == bytes(200) and bytes(s[0x200:0x208]) == b'Testbank', '' if s is None else bytes(s[0x200:0x210]))
v = bank(fl, 0)
pruef('Verzeichnis: Bank 0 Zelle 7 = 00.020', v is not None and bytes(v[14:16]) == bytes([0, 20]), '' if v is None else v[12:18].hex())
pruef('F_JOB = 0, „P-F rdY“', m.ram[F_JOB] == 0 and text(m.anzeige()) == 'P-FrdY' and pi.fehler is None, f'{text(m.anzeige())} {pi.fehler}')
print(f'     {ms:.0f} ms Simulationszeit')

print('F-P: Flash Bank 7 -> Pi, Zellen 98..111')
pi = FNIPi('aus', (0x24, 7, 98, 14))
auftrag(m, 0x24, 7, 98, 14, pi=pi)
pruef('Pi hat 00-Zellen + Daten', bytes(pi.empfangen) == bytes(4) + d7 + bytes(4) and pi.fehler is None, f'{bytes(pi.empfangen).hex()} {pi.fehler}')

print('P-F über eine vorhandene Bank: Rest bleibt erhalten, ohne Verzeichnis (Start 255)')
pi = FNIPi('ein', (0x22, 7, 102, 1), bytes([9, 9]))
auftrag(m, 0x22, 7, 102, 1, start=255, pi=pi)
s = bank(fl, 7)
pruef(f'nur Zelle 102 neu, Name bleibt (Pi: {pi.fehler}, F_JOB {m.ram[F_JOB]:02x})', s is not None and bytes(s[200:220]) == d7[:4] + bytes([9, 9]) + d7[6:] and bytes(s[0x200:0x208]) == b'Testbank',
      '' if s is None else s[200:220].hex())
v = bank(fl, 0)
pruef('Verzeichnis unverändert', bytes(v[14:16]) == bytes([0, 20]))

print('ganze Bank: P-F (256 Zellen) und F-P zurück')
voll = bytes((i * 13 + 5) & 0xFF for i in range(512))
pi = FNIPi('ein', (0x22, 9, 0, 0), voll)
ms_w = auftrag(m, 0x22, 9, 0, 0, pi=pi, frist_ms=8000)
pi2 = FNIPi('aus', (0x24, 9, 0, 0))
ms_r = auftrag(m, 0x24, 9, 0, 0, pi=pi2, frist_ms=8000)
pruef('zurückgelesen = geschrieben', bytes(pi2.empfangen) == voll and pi.fehler is None and pi2.fehler is None, f'{pi.fehler} {pi2.fehler}')
print(f'     schreiben {ms_w:.0f} ms, lesen {ms_r:.0f} ms Simulationszeit')
pi = FNIPi('ein', (0x20, 0, 0, 0), voll)
ms_c = auftrag(m, 0x20, 0, 0, 0, pi=pi, frist_ms=8000)
pruef('P-C ganze 256 Zellen (mit CP3)', b''.join(bytes(zelle(m, n)) for n in range(256)) == voll and m.ram[F_JOB] == 0, f'{pi.fehler}')
print(f'     {ms_c:.0f} ms Simulationszeit')

print('Störungen')
pi = FNIPi('ein', (0x20, 0, 20, 12), daten[:24], stoerung={'crc': {1: 2}})
auftrag(m, 0x20, 0, 20, 12, pi=pi)
pruef('Block 1 zweimal kaputt -> wiederholt, gut', m.ram[F_JOB] == 0 and pi.fehler is None and pi.versuche.get(1) == 3, f'{m.ram[F_JOB]:02x} {pi.versuche}')
pi = FNIPi('ein', (0x20, 0, 20, 12), daten[:24], stoerung={'crc': {1: 3}})
auftrag(m, 0x20, 0, 20, 12, pi=pi)
pruef('dreimal kaputt -> Abbruch, F_JOB = $EE, „P-C Err“', m.ram[F_JOB] == 0xEE and text(m.anzeige()) == 'P-CErr' and m.tcnti, f'{m.ram[F_JOB]:02x} {text(m.anzeige())}')
for n in range(3, 13): zelle(m, n, n, 100 + n)
pi = FNIPi('aus', (0x21, 0, 3, 10), stoerung={'crc': {0: 1}})
auftrag(m, 0x21, 0, 3, 10, pi=pi)
pruef('C-P: Pi meldet einmal „nochmal“ -> CP1 wiederholt', m.ram[F_JOB] == 0 and bytes(pi.empfangen) == erw, f'{m.ram[F_JOB]:02x}')
pi = FNIPi('ein', (0x20, 0, 0, 40), daten, stoerung={'abbruch_nach': 3})
t = auftrag(m, 0x20, 0, 0, 40, pi=pi)
pruef('Pi bricht ab -> CP1 nach Zeitgrenze $EE, Interrupt an', m.ram[F_JOB] == 0xEE and m.tcnti, f'{m.ram[F_JOB]:02x} nach {t:.0f} ms')
pi = FNIPi('ein', (0x20, 0, 10, 40), daten, stoerung={'kopf': (0x20, 0, 11, 40)})
auftrag(m, 0x20, 0, 10, 40, pi=pi)
pruef('falscher Kopf -> $EE', m.ram[F_JOB] == 0xEE, f'{m.ram[F_JOB]:02x}')
pi = FNIPi('ein', (0x20, 0, 200, 60), bytes(120))
m2 = CP1(ROM, False, flash=SPIFlash()); m2.bis(m2.us + 100_000)
auftrag(m2, 0x20, 0, 200, 60, pi=pi, frist_ms=500)
pruef('ohne CP3: Zellen 200.. -> sofort abgelehnt ($EE)', m2.ram[F_JOB] == 0xEE, f'{m2.ram[F_JOB]:02x}')
pi = FNIPi('ein', (0x22, 0, 0, 4), bytes(8))
auftrag(m, 0x22, 0, 0, 4, pi=pi, frist_ms=500)
pruef('P-F auf Bank 0 -> abgelehnt', m.ram[F_JOB] == 0xEE)
pi = FNIPi('ein', (0x20, 0, 30, 30), daten[:60], stoerung={'zittern': 3000}, seed=5)
auftrag(m, 0x20, 0, 30, 30, pi=pi)
ram = b''.join(bytes(zelle(m, n)) for n in range(30, 60))
pruef('Pi-Unterbrechungen bis 3 ms -> trotzdem richtig', ram == daten[:60] and m.ram[F_JOB] == 0, f'{pi.fehler}')

print('$25 Bank komplett (Zellen + Kopf) und $26 alle Namen')
pi = FNIPi('komplett', (0x25, 7, 0, 0))
auftrag(m, 0x25, 7, 0, 0, pi=pi, frist_ms=8000)
s = bank(fl, 7)
pruef('Zellen + 0x200..0x5FF (Name, Generation, gültig, Namensbereich)', bytes(pi.empfangen) == bytes(s[0:0x600]) and pi.fehler is None, f'{pi.fehler} {bytes(pi.empfangen[0x200:0x212]).hex()}')
pi = FNIPi('komplett', (0x25, 50, 0, 0))
auftrag(m, 0x25, 50, 0, 0, pi=pi, frist_ms=8000)
pruef('leere Bank: Zellen 00, Rest FF', bytes(pi.empfangen) == bytes(512) + b'\xff' * 0x400, bytes(pi.empfangen[0x1fe:0x210]).hex())
pi = FNIPi('namen', (0x26, 0, 0, 0))
ms = auftrag(m, 0x26, 0, 0, 0, pi=pi, frist_ms=8000)
erw = [(b, bytes(bank(fl, b)[0x200:0x210])) for b in range(1, 256) if bank(fl, b) is not None]
pruef('alle Namen: Bänke 7 und 9 (Testbank, ohne Name)', pi.fehler is None and pi.namen == erw and [b for b, _ in pi.namen] == [7, 9], f'{pi.fehler} {pi.namen}')
print(f'     alle Namen: {ms:.0f} ms Simulationszeit')
print('5.03: $29 Pi -> Flash mit Name und Namensbereich 0x300..0x5FF')
sys.path.insert(0, '../../remote'); sys.path.insert(0, '../fernsteuerung')
from kosmos_remote import namen_bytes, namen_aus_bytes
namen = {0: 'start', 5: 'schleife', 100: 'punkte', 255: 'ende'} | {i: f'n{i:03d}_langername' for i in range(10, 50)}
nb = namen_bytes(namen)
zd = bytes((3 * i + 1) & 0xFF for i in range(512))
pi = FNIPi('ein', (0x29, 20, 0, 0), zd + nb)
ms = auftrag(m, 0x29, 20, 0, 0, start=7, name='Mit Namen', pi=pi, frist_ms=15000)
s = bank(fl, 20)
pruef('Zellen, Name, Merker 0x212 = 00, Namensbereich', s is not None and bytes(s[:512]) == zd and bytes(s[0x200:0x209]) == b'Mit Namen'
      and s[0x212] == 0 and bytes(s[0x300:0x600]) == nb and m.ram[F_JOB] == 0 and pi.fehler is None,
      f'{pi.fehler} {m.ram[F_JOB]:02x} {None if s is None else bytes(s[0x210:0x214]).hex()}')
print(f'     $29 ganze Bank + {len(namen)} Namen: {ms:.0f} ms')
pi = FNIPi('komplett', (0x25, 20, 0, 0))
auftrag(m, 0x25, 20, 0, 0, pi=pi, frist_ms=8000)
pruef('$25 liefert die Namen zurück', namen_aus_bytes(bytes(pi.empfangen[0x300:0x600])) == namen and pi.empfangen[0x212] == 0, f'{pi.fehler}')
pi = FNIPi('ein', (0x23, 20, 10, 4), bytes(8))
ms = auftrag(m, 0x23, 20, 10, 4, name='Mit Namen', pi=pi, frist_ms=15000)
s = bank(fl, 20)
pruef('$23 danach (ohne Namen): Namen bleiben, Zellen 10..13 = 0', bytes(s[0x300:0x600]) == nb and s[0x212] == 0 and bytes(s[20:28]) == bytes(8) and bytes(s[:20]) == zd[:20], f'{ms:.0f} ms')
print(f'     $23 4 Zellen in Bank mit Namen (kopiert bis 0x5FF): {ms:.0f} ms')
pi = FNIPi('ein', (0x23, 21, 0, 4), bytes(8))
ms0 = auftrag(m, 0x23, 21, 0, 4, name='Ohne', pi=pi, frist_ms=15000)
ms1 = auftrag(m, 0x23, 21, 0, 4, name='Ohne', pi=FNIPi('ein', (0x23, 21, 0, 4), bytes(8)), frist_ms=15000)
pruef('Bank ohne Namen: Merker FF, Namensbereich FF, schnell', bank(fl, 21)[0x212] == 0xFF and bytes(bank(fl, 21)[0x300:0x600]) == b'\xff' * 0x300, f'{ms1:.0f} ms')
print(f'     $23 4 Zellen in Bank ohne Namen: {ms1:.0f} ms')
pi = FNIPi('ein', (0x29, 20, 0, 4), bytes(8) + namen_bytes({}))
auftrag(m, 0x29, 20, 0, 4, name='Mit Namen', pi=pi, frist_ms=15000)
pruef('$29 mit leerer Tabelle löscht die Namen', bytes(bank(fl, 20)[0x300:0x600]) == b'\xff' * 0x300 and m.ram[F_JOB] == 0, f'{pi.fehler}')
print('danach normale Bedienung: PC-Taste')
m.drueck('pc', m.us + 50_000, 120); m.bis(m.us + 400_000)
pruef('Anzeige P…', text(m.anzeige()).startswith('P'), text(m.anzeige()))
print('ALLES OK' if not fehler else f'{fehler} FEHLER'); sys.exit(1 if fehler else 0)
