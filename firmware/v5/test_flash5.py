"""5.x: SPI-Flash im Simulator: PSK/FRD/FWR, Sektorwechsel, Fehler, Aufträge mit Interrupt ($01/$04/$08/$10/$80/$81),
OUT P1A. (Tasten CAS/CAL/RUN: test_ui5.py, FNI: test_fni.py, NIE: test_nie5.py)"""
import sys, time
sys.path.insert(0, '.')
from sim48 import CP1, SPIFlash, text
ROM = open('cp1v5-eeprom.bin', 'rb').read()
PSK, FRD, FWR, HLT, AKO, ANZ, LDA = 36, 37, 38, 1, 4, 2, 5
fehler = 0
def pruef(name, ok, info=''):
    global fehler
    print(('  ok   ' if ok else '  FEHL ') + name + (f'  [{info}]' if info else ''))
    if not ok: fehler += 1

def maschine(flash, prog=(), daten={}, cp3=True):
    m = CP1(ROM, cp3, flash=flash)
    for n, (b, a) in list(enumerate(prog)) + [(z, (0, w)) for z, w in daten.items()]:
        zelle(m, n, b, a)
    return m

def zelle(m, n, b=None, a=None):
    chip, adr = (m.intern, 2 * n) if n < 128 else (m.cp3, 2 * (n - 128))
    if b is None: return chip.ram[adr], chip.ram[adr + 1]
    chip.ram[adr] = b; chip.ram[adr + 1] = a

def tippe(m, tasten, ab=None, abstand=200, dauer=120):
    t = m.us + 50_000 if ab is None else ab
    for k in tasten:
        if isinstance(k, tuple): k, d = k
        else: d = dauer
        m.drueck(k, t, d); t += d * 1000 + abstand * 1000
    return t

def run(m, bis_ms=3000):
    t = tippe(m, ['run'])
    m.bis(t + bis_ms * 1000)
    return text(m.anzeige())

def bank(fl, b, s):
    return fl.m[b * 0x2000 + s * 0x1000: b * 0x2000 + s * 0x1000 + 0x1000]

fl = SPIFlash()
print('FWR: Zellen 50..52 -> Bank 5, Zellen 10..12')
m = maschine(fl, [(PSK, 5), (PSK, 10), (PSK, 3), (FWR, 50), (HLT, 0)], {50: 11, 51: 22})
zelle(m, 52, 7, 33)
t0 = time.time(); anz = run(m, 4000)
s1 = bank(fl, 5, 1)
pruef('läuft durch (HLT)', fl.geloescht == 1 and anz.startswith('P'), f'{anz!r}, {time.time()-t0:.1f} s Sim, max SP {m.max_sp}')
pruef('Sektor 1 gültig, Gen 0', s1[0x211] == 0 and s1[0x210] == 0, f'{s1[0x210]:02x} {s1[0x211]:02x}')
pruef('Zellen 10..12 = 00 11 / 00 22 / 07 33', s1[20:26] == bytes([0, 11, 0, 22, 7, 33]), s1[18:28].hex())
pruef('Rest 00, Name FF', s1[0:20] == bytes(20) and s1[26:0x200] == bytes(0x200 - 26) and s1[0x200:0x210] == b'\xff' * 16)
dauer_ms = m.us / 1000
print('FRD zurück in eine frische Maschine')
m = maschine(fl, [(PSK, 5), (PSK, 9), (PSK, 5), (FRD, 70), (HLT, 0)])
run(m, 2000)
pruef('RAM 70..74 = 0 / 11 / 22 / 07.033 / 0', [zelle(m, n) for n in range(70, 75)] == [(0, 0), (0, 11), (0, 22), (7, 33), (0, 0)],
      str([zelle(m, n) for n in range(70, 75)]))
print('FWR nur Zelle 11 (andere bleiben), Sektorwechsel')
m = maschine(fl, [(PSK, 5), (PSK, 11), (PSK, 1), (FWR, 60), (HLT, 0)], {60: 99})
run(m, 4000)
s0, s1 = bank(fl, 5, 0), bank(fl, 5, 1)
pruef('Sektor 0 gültig, Gen 1', s0[0x211] == 0 and s0[0x210] == 1, f'{s0[0x210]:02x} {s0[0x211]:02x}')
pruef('Zellen 10..12 = 00 11 / 00 99 / 07 33', s0[20:26] == bytes([0, 11, 0, 99, 7, 33]), s0[18:28].hex())
m = maschine(fl, [(PSK, 5), (PSK, 11), (PSK, 1), (FRD, 80), (HLT, 0)])
run(m, 2000)
pruef('FRD liest die neue Fassung (99)', zelle(m, 80) == (0, 99), str(zelle(m, 80)))
print('Dritte Fassung: wieder Sektor 1, Gen 2')
m = maschine(fl, [(PSK, 5), (PSK, 12), (PSK, 1), (FWR, 60), (HLT, 0)], {60: 1})
run(m, 4000)
s1 = bank(fl, 5, 1)
pruef('Sektor 1 Gen 2, Zellen 00 11 / 00 99 / 00 01', s1[0x210] == 2 and s1[0x211] == 0 and s1[20:26] == bytes([0, 11, 0, 99, 0, 1]), s1[18:28].hex())
m = maschine(fl, [(PSK, 5), (PSK, 10), (PSK, 3), (FRD, 80), (HLT, 0)])
run(m, 2000)
pruef('FRD: neueste Fassung', [zelle(m, n) for n in (80, 81, 82)] == [(0, 11), (0, 99), (0, 1)], str([zelle(m, n) for n in (80, 81, 82)]))
print('Ganze Bank, Anzahl 0 = 256')
m = maschine(fl, [(PSK, 9), (PSK, 0), (PSK, 0), (FWR, 0), (HLT, 0)])
for n in range(5, 256): zelle(m, n, 0, n)
run(m, 5000)
s1 = bank(fl, 9, 1)
pruef('Bank 9: 256 Zellen = RAM', all(s1[2 * n + 1] == n for n in range(5, 256)) and s1[0:2] == bytes([PSK, 9]), s1[0:12].hex())
print('Leere Bank liest 0')
m = maschine(fl, [(PSK, 77), (PSK, 0), (PSK, 3), (FRD, 100), (HLT, 0)], {100: 5, 101: 6, 102: 7})
run(m, 2000)
pruef('Bank 77 leer -> 0', [zelle(m, n) for n in (100, 101, 102)] == [(0, 0)] * 3)
print('Fehler')
def fehlerlauf(prog, daten={}, flash=fl, cp3=True):
    m = maschine(flash, prog, daten, cp3); return run(m, 2000)
pruef('FWR Bank 0 -> F-003', fehlerlauf([(PSK, 0), (PSK, 1), (PSK, 1), (FWR, 50), (HLT, 0)]) == 'F  003')
pruef('Adresse + Anzahl > 256 -> F-003', fehlerlauf([(PSK, 1), (PSK, 250), (PSK, 7), (FRD, 50), (HLT, 0)]) == 'F  003')
pruef('Anzahl 256 ab 1 -> F-003', fehlerlauf([(PSK, 1), (PSK, 1), (PSK, 0), (FRD, 0), (HLT, 0)]) == 'F  003')
pruef('RAM-Ende über 255 -> F-003', fehlerlauf([(PSK, 1), (PSK, 0), (PSK, 10), (FRD, 250), (HLT, 0)]) == 'F  003')
pruef('ohne CP3: RAM über 127 -> F-003', fehlerlauf([(PSK, 1), (PSK, 0), (PSK, 10), (FRD, 120), (HLT, 0)], cp3=False) == 'F  003')
pruef('nur 2 Werte auf dem Stapel -> F-009', fehlerlauf([(PSK, 1), (PSK, 0), (FRD, 50), (HLT, 0)]) == 'F  009')
pruef('kein Flash -> F-010', fehlerlauf([(PSK, 1), (PSK, 0), (PSK, 1), (FRD, 50), (HLT, 0)], flash=None) == 'F  010')
akku = maschine(fl, [(PSK, 200), (34 + 1, 0), (HLT, 0)])
run(akku, 1500)
pruef('PSK 200 / POP -> Akku 200', (akku.ram[0x36], akku.ram[0x37]) == (0, 200))

print('Aufträge mit Interrupt (Parameter direkt ins RAM, dann CAL = was AUFTRAG an wait_key liefert)')
F_JOB, F_BANK, F_SEKT, F_OFH, F_OFL, F_NAME = 0x26, 0x2c, 0x2d, 0x2e, 0x2f, 0x60
m = maschine(fl, [(AKO, 77), (HLT, 0)])
m.ram[0x38] = 0
m.ram[F_NAME:F_NAME + 16] = b'Rakete          '
m.ram[F_BANK] = 12; m.ram[F_JOB] = 0x81
t = tippe(m, ['cal']); m.bis(t + 5_000_000)
s = bank(fl, 12, 1)
pruef('Auftrag $81: Bank 12 mit Name', m.ram[F_JOB] == 0 and s[0x200:0x210] == b'Rakete          ' and s[0:2] == bytes([AKO, 77]),
      f'{text(m.anzeige())!r} {bytes(s[0x200:0x210])}')
m.ram[F_BANK] = 12; m.ram[F_JOB] = 1
t = tippe(m, ['cal']); m.bis(t + 1_000_000)
pruef('Auftrag $01 gibt es nicht mehr (5.03): nichts passiert, F_JOB = 0', m.ram[F_JOB] == 0, f'{m.ram[F_JOB]:02x}')
m2 = maschine(fl, [(AKO, 78), (HLT, 0)])
m2.ram[F_BANK] = 12; m2.ram[F_JOB] = 0x80
t = tippe(m2, ['cal']); m2.bis(t + 5_000_000)
s = bank(fl, 12, 0)
pruef('Speichern ohne Name behält den Namen', s[0x200:0x210] == b'Rakete          ' and s[0:2] == bytes([AKO, 78]) and s[0x211] == 0)
m3 = maschine(fl)
m3.ram[F_BANK] = 12; m3.ram[F_JOB] = 4
t = tippe(m3, ['cal']); m3.bis(t + 2_000_000)
pruef('Auftrag $04: laden', zelle(m3, 0) == (AKO, 78) and m3.ram[F_JOB] == 0, repr(text(m3.anzeige())))
m3.ram[F_BANK] = 0; m3.ram[F_JOB] = 8
t = tippe(m3, ['cal']); m3.bis(t + 4_000_000)
pruef('Auftrag $08 Bank 0: Autoboot aus', m3.ram[F_JOB] == 0 and text(m3.anzeige()) == 'botrdY', repr(text(m3.anzeige())))

print('Belegte Bänke im Flash (früher Auftrag $10, jetzt nur noch FNI $26)')
gueltig = [b for b in range(1, 40) if bank(fl, b, 0)[0x211] == 0 or bank(fl, b, 1)[0x211] == 0]
pruef('5, 9, 12 belegt', gueltig == [5, 9, 12], str(gueltig))
print('OUT P1A schützt P1.0-P1.4, P1.6 (FNI-Takt) und P1.7')
P1A = 17
m = maschine(fl, [(AKO, 0), (P1A, 0), (HLT, 0)])
run(m, 1500)
pruef('P1 = 0xdf nach OUT 0', m.p1 == 0xdf and m.ram[0x3f] == 0xdf, hex(m.p1))
print(f'größte Stapeltiefe Auftrag $04: {m3.max_sp}; Schreiben einer Bank ~{dauer_ms:.0f} ms Simulationszeit (mit Start)')
print('ALLES OK' if not fehler else f'{fehler} FEHLER'); sys.exit(1 if fehler else 0)
