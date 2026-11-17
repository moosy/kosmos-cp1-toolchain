"""5.x/6.00: SPI-Flash im Simulator: PSK/FRD/FWR, Sektorwechsel, Fehler, Projekte und Verzeichnis (Aufträge $04/$08/$80,
Anlegen, Lücken, Flash voll, Umstieg von 5.x), OUT P1A. (Tasten: test_ui5.py, FNI: test_fni.py, NIE: test_nie5.py)
Die ersten Teile laufen mit einem „Projekt über alles“ (S_PBANK = 0, S_PRES = 255): Bank k = k wie bis 5.08."""
import sys, time
sys.path.insert(0, '.')
from sim48 import CP1, SPIFlash, text
import verz6
ROM = open('cp1v6-eeprom.bin', 'rb').read()
PSK, FRD, FWR, HLT, AKO, ANZ, LDA = 36, 37, 38, 1, 4, 2, 5
fehler = 0
def pruef(name, ok, info=''):
    global fehler
    print(('  ok   ' if ok else '  FEHL ') + name + (f'  [{info}]' if info else ''))
    if not ok: fehler += 1

S_PRES, S_PBANK = 0x5e, 0x5f
def maschine(flash, prog=(), daten={}, cp3=True, projekt=(0, 255)):
    m = CP1(ROM, cp3, flash=flash)
    if projekt: m.ram[S_PBANK], m.ram[S_PRES] = projekt
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
def fehlerlauf_p(prog, projekt):
    m = maschine(fl, prog, {}, True, projekt); return run(m, 2000)
pruef('6.00: ohne Projekt (S_PRES = 0) -> F-003', fehlerlauf_p([(PSK, 0), (PSK, 1), (PSK, 1), (FWR, 50), (HLT, 0)], (0, 0)) == 'F  003')
pruef('6.00: Projekt mit 4 Bänken, PSK 4 -> F-003', fehlerlauf_p([(PSK, 4), (PSK, 1), (PSK, 1), (FRD, 50), (HLT, 0)], (40, 4)) == 'F  003')
m = maschine(fl, [(PSK, 3), (PSK, 0), (PSK, 1), (FWR, 50), (HLT, 0)], {50: 123}, projekt=(40, 4)); run(m, 4000)
pruef('6.00: Projekt ab Bank 40, PSK 3 -> Bank 43', verz6.gueltig(fl, 43) is not None and verz6.gueltig(fl, 43)[0:2] == bytes([0, 123]))
pruef('Adresse + Anzahl > 256 -> F-003', fehlerlauf([(PSK, 1), (PSK, 250), (PSK, 7), (FRD, 50), (HLT, 0)]) == 'F  003')
pruef('Anzahl 256 ab 1 -> F-003', fehlerlauf([(PSK, 1), (PSK, 1), (PSK, 0), (FRD, 0), (HLT, 0)]) == 'F  003')
pruef('RAM-Ende über 255 -> F-003', fehlerlauf([(PSK, 1), (PSK, 0), (PSK, 10), (FRD, 250), (HLT, 0)]) == 'F  003')
pruef('ohne CP3: RAM über 127 -> F-003', fehlerlauf([(PSK, 1), (PSK, 0), (PSK, 10), (FRD, 120), (HLT, 0)], cp3=False) == 'F  003')
pruef('nur 2 Werte auf dem Stapel -> F-009', fehlerlauf([(PSK, 1), (PSK, 0), (FRD, 50), (HLT, 0)]) == 'F  009')
pruef('kein Flash -> F-010', fehlerlauf([(PSK, 1), (PSK, 0), (PSK, 1), (FRD, 50), (HLT, 0)], flash=None) == 'F  010')
akku = maschine(fl, [(PSK, 200), (34 + 1, 0), (HLT, 0)])
run(akku, 1500)
pruef('PSK 200 / POP -> Akku 200', (akku.ram[0x36], akku.ram[0x37]) == (0, 200))

print('6.00 Projekte: Aufträge mit Interrupt (Parameter direkt ins RAM, dann CAL = was AUFTRAG an wait_key liefert)')
F_JOB, F_BANK, F_NAME, PC = 0x26, 0x2c, 0x60, 0x38
def auftrag(m, job, n, frist=8_000_000):
    m.ram[F_BANK] = n; m.ram[F_JOB] = job
    t = tippe(m, ['cal']); m.bis(t + frist, halt=lambda mm: mm.ram[F_JOB] == 0 and mm.us > t + 300_000)
    m.bis(m.us + 200_000)
    return text(m.anzeige())
fl2 = SPIFlash()
m = maschine(fl2, [(AKO, 77), (HLT, 0)], projekt=None); m.ram[PC] = 1
t0 = m.us; anz = auftrag(m, 0x80, 3)
v = verz6.lesen(fl2)
pruef('$80 Projekt 3 in leeren Flash: „5to rdY“, Verzeichnis angelegt', anz == '5tordY' and v is not None and v['autoboot'] == 0, f'{anz!r} {v}')
pruef('… Projekt 3 = Bank 4, 4 Bänke reserviert, ohne Name', v and v['projekte'] == {3: {'bank': 4, 'res': 4, 'name': None, 'anzeige': None}}, str(v))
b4 = verz6.gueltig(fl2, 4)
pruef('… Bank 4: Zellen und Start-PC 1 (0x213)', b4 is not None and b4[0:4] == bytes([AKO, 77, 1, 0]) and b4[0x213] == 1, b4 and b4[0x210:0x214].hex())
pruef('… S_PBANK/S_PRES = 4/4 (das RAM gehört jetzt zu Projekt 3)', (m.ram[S_PBANK], m.ram[S_PRES]) == (4, 4))
print(f'   (erstes Speichern mit Verzeichnis anlegen: {(m.us - t0) / 1e6:.1f} s Simulationszeit)')
m = maschine(fl2, [(AKO, 88), (HLT, 0)], projekt=None); m.ram[PC] = 0
t0 = m.us; auftrag(m, 0x80, 7)
v = verz6.lesen(fl2)
pruef('$80 Projekt 7: Bank 8 (hinter Projekt 3)', v and v['projekte'].get(7, {}).get('bank') == 8 and len(v['projekte']) == 2, str(v))
print(f'   (neues Projekt anlegen: {(m.us - t0) / 1e6:.1f} s Simulationszeit)')
m = maschine(fl2, [(AKO, 79), (HLT, 0)], projekt=None); m.ram[PC] = 0
t0 = m.us; auftrag(m, 0x81, 3)
v = verz6.lesen(fl2); b4 = verz6.gueltig(fl2, 4)
pruef('$81 in bestehendes Projekt 3: Bank 4 neu, Verzeichnis gleich', b4[0:2] == bytes([AKO, 79]) and b4[0x213] == 0 and v['projekte'][3]['bank'] == 4 and len(v['projekte']) == 2)
pruef('… schreibt keinen Namen mehr (6.00: Namen verwaltet der Pi)', b4[0x200:0x210] == b'\xff' * 16)
print(f'   (bestehendes Projekt speichern: {(m.us - t0) / 1e6:.1f} s Simulationszeit)')
m3 = maschine(fl2, projekt=None)
anz = auftrag(m3, 4, 7)
pruef('$04 Projekt 7: laden, PC = Start, S_PBANK/S_PRES = 8/4', zelle(m3, 0) == (AKO, 88) and m3.ram[PC] == 0 and (m3.ram[S_PBANK], m3.ram[S_PRES]) == (8, 4), f'{anz!r} {zelle(m3, 0)}')
m3b = maschine(fl2, [(PSK, 1), (PSK, 0), (PSK, 1), (FWR, 20), (PSK, 1), (PSK, 0), (PSK, 1), (FRD, 21), (HLT, 0)], {20: 55}, projekt=None)
auftrag(m3b, 4, 7)
for n, w in enumerate([(PSK, 1), (PSK, 0), (PSK, 1), (FWR, 20), (PSK, 1), (PSK, 0), (PSK, 1), (FRD, 21), (HLT, 0)]): zelle(m3b, n, *w)
zelle(m3b, 20, 0, 55); m3b.ram[PC] = 0
anz = run(m3b, 4000)
b9 = verz6.gueltig(fl2, 9)
pruef('nach dem Laden: PSK 1 = zweite Bank des Projekts (Bank 9)', b9 is not None and b9[0:2] == bytes([0, 55]) and zelle(m3b, 21) == (0, 55), f'{anz!r} {zelle(m3b, 21)}')
anz = auftrag(maschine(fl2, projekt=None), 4, 5, 3_000_000)
pruef('$04 Projekt 5 (gibt es nicht) -> F-011', anz == 'F  011', anz)
anz = auftrag(m3, 8, 7)
pruef('$08 Projekt 7: Autoboot in Bank 1 (Einstellungen)', anz == 'botrdY' and verz6.lesen(fl2)['autoboot'] == 7, repr(anz))
anz = auftrag(m3, 8, 0)
pruef('$08 0: Autoboot aus, Projekte bleiben', verz6.lesen(fl2)['autoboot'] == 0 and len(verz6.lesen(fl2)['projekte']) == 2)

print('6.00 Anlegen: Lücken, kleiner, Flash voll')
fl3 = SPIFlash()
verz6.anlegen(fl3, {1: {'bank': 4, 'res': 4}, 2: {'bank': 12, 'res': 4}})
auftrag(maschine(fl3, [(AKO, 1)], projekt=None), 0x80, 9)
pruef('Lücke 8..11 zwischen zwei Projekten wird genommen', verz6.lesen(fl3)['projekte'][9]['bank'] == 8, str(verz6.lesen(fl3)['projekte']))
verz6.anlegen(fl3, {1: {'bank': 4, 'res': 249}, 2: {'bank': 253, 'res': 1}})
auftrag(maschine(fl3, [(AKO, 1)], projekt=None), 0x80, 5)
p5 = verz6.lesen(fl3)['projekte'].get(5)
pruef('nur noch 2 Bänke frei (254, 255): Projekt bekommt 2', p5 == {'bank': 254, 'res': 2, 'name': None, 'anzeige': None}, str(p5))
anz = auftrag(maschine(fl3, [(AKO, 1)], projekt=None), 0x80, 6)
pruef('Flash voll -> F-012, Verzeichnis unverändert', anz == 'F  012' and 6 not in verz6.lesen(fl3)['projekte'], anz)

print('6.00 Umstieg: Flash von 5.x (Bank 0 ohne „CP1V“, alte Bank 4 mit Namensbereich)')
fl4 = SPIFlash()
alt0 = verz6.sektor_leer(); alt0[0:4] = bytes([0, 6, 0, 8])                       # altes Verzeichnis (00, Start)
verz6.setzen(fl4, 0, alt0)
verz6.setzen(fl4, 4, verz6.projektbank(bytes([4, 1]) * 256, 'Alt', meta=b'\x01\x02' * 100), welcher=1)
pruef('… vorher: kein Verzeichnis', verz6.lesen(fl4) is None)
anz = auftrag(maschine(fl4, [(AKO, 42), (HLT, 0)], projekt=None), 0x80, 1)
v = verz6.lesen(fl4); b4 = verz6.gueltig(fl4, 4)
pruef('Speichern legt den Kopf an, Rest des Verzeichnisses frei', v is not None and list(v['projekte']) == [1], str(v))
pruef('alte Bank 4 geleert: kein alter Name, kein Namensbereich, Rest 00', b4[0:4] == bytes([AKO, 42, 1, 0]) and b4[0x200:0x213] != b'Alt' and b4[0x200] == 0xFF and b4[0x212] == 0xFF and b4[300:0x200] == bytes(0x200 - 300), b4[0x200:0x214].hex())
s0 = verz6.gueltig(fl4, 0)
pruef('Verzeichnis-Sektor: Zellenbereich außer dem Kopf 00, ab 0x300 FF außer Eintrag 1', s0[6:0x200] == bytes(0x1FA) and all(b == 0xFF for b in s0[0x320:0x1000]), s0[0:8].hex())
anz = auftrag(maschine(fl4, projekt=None), 8, 1)
pruef('Autoboot 1', verz6.lesen(fl4)['autoboot'] == 1)
fl5 = SPIFlash(); verz6.setzen(fl5, 0, alt0)
t0 = None
m5 = maschine(fl5, projekt=None); t0 = m5.us
anz = auftrag(m5, 8, 3)
e = verz6.gueltig(fl5, 1)
pruef('Autoboot ohne Verzeichnis: nur Bank 1, Verzeichnis bleibt unberührt', e is not None and e[0] == 3 and verz6.lesen(fl5) is None, repr(anz))
print(f'   (Autoboot setzen: {(m5.us - t0) / 1e6:.1f} s Simulationszeit)')

print('OUT P1A (6.00): Port 1 bleibt ganz bei der Firmware')
P1A = 17
m = maschine(fl, [(AKO, 0), (P1A, 0), (HLT, 0)])
run(m, 1500)
pruef('P1 = 0xff nach OUT 0', m.p1 == 0xff and m.ram[0x3f] == 0xff, hex(m.p1))
m = maschine(fl, [(AKO, 0), (P1A, 6), (HLT, 0)])
run(m, 1500)
pruef('P1 = 0xff nach OUT 0 an Pin 6', m.p1 == 0xff, hex(m.p1))
print(f'größte Stapeltiefe Auftrag $04: {m3.max_sp}; Schreiben einer Bank ~{dauer_ms:.0f} ms Simulationszeit (mit Start)')
print('ALLES OK' if not fehler else f'{fehler} FEHLER'); sys.exit(1 if fehler else 0)
