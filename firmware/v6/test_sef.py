"""5.06/6.00: SEF xxx (47) = 6 Byte ab xxx im Bilderbereich (Sektor 0x500..0x5FD) der Bank, aus der das Programm
geladen wurde (S_PBANK 0x5F). SEF 248 = eigene Blätter-Anzeige, SEF 255 löscht, ohne Programmbank dunkel."""
import sys
sys.path.insert(0, '.')
from sim48 import CP1, SPIFlash, text
import verz6
ROM = open('cp1v6-eeprom.bin', 'rb').read()
HLT, AKO, ABS, SPU, VZG, PSH, SEF, LDA, ADD, PSK, FRD, FWR = 1, 4, 6, 9, 3, 34, 47, 5, 7, 36, 37, 38
F_JOB, F_BANK, S_PBANK = 0x26, 0x2c, 0x5f
f = 0
def pruef(n, ok, i=''):
    global f; print(('  ok   ' if ok else '  FEHL ') + n + ('' if ok else f'  [{i}]')); f += not ok
BILD1 = [0x76, 0x79, 0x38, 0x38, 0x3f, 0x80]      # HELLO.
BILD2 = [0x40, 0x40, 0x08, 0x08, 0x01, 0x01]
EIGEN = [0x6d, 0x73, 0x77, 0x39, 0x79, 0x00]      # SPACE
def bank_anlegen(fl, b, prog):
    s = bytearray([0xFF]) * 0x1000
    for n in range(256): s[2*n:2*n+2] = bytes(prog[n]) if n < len(prog) else b'\x00\x00'
    s[0x200:0x210] = b'Bildertest      '; s[0x210] = 0; s[0x211] = 0; s[0x212] = 0
    s[0x500:0x50C] = bytes(BILD1 + BILD2); s[0x5F8:0x5FE] = bytes(EIGEN)
    fl.m[b * 0x2000: b * 0x2000 + 0x1000] = s
def geladen(prog, bankn=9):
    fl = SPIFlash(); bank_anlegen(fl, bankn, prog)
    verz6.setzen(fl, 0, verz6.verzeichnis({3: {'bank': bankn, 'res': 4}}))   # 6.00: Projekt 3 ab Bank 9
    m = CP1(ROM, True, flash=fl)
    m.bis(m.us + 1_500_000)                        # Version vorbei
    m.ram[F_BANK] = 3; m.ram[F_JOB] = 4            # wie der Pi: Projekt 3 laden
    m.drueck('cal', m.us + 1000, 100); m.bis(m.us + 1_500_000)
    return m
def starte(m, ms=400):
    m.drueck('run', m.us + 1000, 100); m.bis(m.us + ms * 1000)

m = geladen([(SEF, 0), (SPU, 1)])
pruef('nach dem Laden: Programmbank 9', m.ram[S_PBANK] == 9, m.ram[S_PBANK])
starte(m); pruef('SEF 0 zeigt Bild 1', list(m.anzeige()) == BILD1, [hex(x) for x in m.anzeige()])
m = geladen([(SEF, 6), (SPU, 1)]); starte(m)
pruef('SEF 6 zeigt Bild 2', list(m.anzeige()) == BILD2, [hex(x) for x in m.anzeige()])
m = geladen([(SEF, 3), (SPU, 1)]); starte(m)
pruef('SEF 3: Lauftext-Schritt (Byte für Byte)', list(m.anzeige()) == BILD1[3:] + BILD2[:3], [hex(x) for x in m.anzeige()])
m = geladen([(SEF, 248), (SPU, 1)]); starte(m)
pruef('SEF 248 = eigene Blätter-Anzeige', list(m.anzeige()) == EIGEN, [hex(x) for x in m.anzeige()])
m = geladen([(AKO, 3), (SEF, 254), (SPU, 2)]); starte(m)
pruef('SEF 254: Position aus dem Akku (3)', list(m.anzeige()) == BILD1[3:] + BILD2[:3], [hex(x) for x in m.anzeige()])
# Lauftext-Schleife: Position 0, 1, 2 ... mit SEF 254
m = geladen([(AKO, 0), (ABS, 60), (LDA, 60), (SEF, 254), (VZG, 50), (LDA, 60), (ADD, 61), (ABS, 60), (SPU, 2)])
m.intern.ram[122:124] = bytes([0, 1])
m.drueck('run', m.us + 1000, 100); folge = []
for _ in range(60):
    m.bis(m.us + 20_000); a = list(m.anzeige())
    if not folge or folge[-1] != a: folge.append(a)
soll = [(BILD1 + BILD2)[i:i+6] for i in range(0, 4)]
pruef('Lauftext-Schleife schiebt Byte für Byte', any(folge[k:k+4] == soll for k in range(len(folge))), folge[:6])
m = geladen([(SEF, 0), (SEF, 255), (SPU, 2)]); starte(m)
pruef('SEF 255 löscht', list(m.anzeige()) == [0] * 6, [hex(x) for x in m.anzeige()])
m = geladen([(AKO, 77), (SEF, 0), (ABS, 50), (HLT, 0)]); starte(m)
pruef('Akku bleibt, Programm läuft weiter', m.intern.ram[101] == 77 and m.ram[0x38] == 4, (m.intern.ram[101], m.ram[0x38]))
# 22 Stapelebenen (6.00) lassen Projekt und Programmbank in Ruhe
m = geladen([(AKO, 1)] + [(PSH, 0)] * 22 + [(SEF, 6), (HLT, 0)]); starte(m, 800)
pruef('22 x PSH: Programmbank und Projektgröße bleiben, SEF geht', m.ram[S_PBANK] == 9 and m.ram[0x5e] == 4 and list(m.anzeige())[:6] != BILD1 and m.ram[0x45] == 22, (m.ram[S_PBANK], m.ram[0x45], text(m.anzeige())))
# getipptes Programm (nie aus einer Bank geladen): dunkel, läuft weiter
fl = SPIFlash(); bank_anlegen(fl, 9, [])
m = CP1(ROM, True, flash=fl)
for n, (b, a) in enumerate([(SEF, 0), (ABS, 50), (HLT, 0)]): m.intern.ram[2*n:2*n+2] = bytes([b, a])
m.bis(m.us + 1_500_000); starte(m)
pruef('ohne Programmbank: dunkel, läuft weiter', m.ram[0x38] == 3 and m.ram[S_PBANK] == 0, (m.ram[0x38], text(m.anzeige())))
# 6.00: FRD/FWR mit PSK 0 = erste Bank des Projekts (Startwerte neu laden, Rekord speichern)
prog = [(PSK, 0), (PSK, 20), (PSK, 3), (FRD, 20), (HLT, 0)] + [(0, 0)] * 15 + [(0, 11), (0, 22), (0, 33)]
m = geladen(prog)
for n in (20, 21, 22): m.intern.ram[2*n+1] = 99            # Variablen „verstellt“
starte(m, 600)
pruef('FRD PSK 0: Startwerte aus der ersten Bank des Projekts zurück', [m.intern.ram[2*n+1] for n in (20, 21, 22)] == [11, 22, 33] and m.ram[0x38] == 5,
      ([m.intern.ram[2*n+1] for n in (20, 21, 22)], text(m.anzeige())))
prog = [(PSK, 0), (PSK, 30), (PSK, 1), (FWR, 30), (HLT, 0)] + [(0, 0)] * 25 + [(0, 7)]
m = geladen(prog); m.intern.ram[61] = 123; starte(m, 8000)
sek = m.flash.m[9 * 0x2000: 9 * 0x2000 + 0x2000]
gueltig = [sek[s * 0x1000 + 60:s * 0x1000 + 62] for s in (0, 1) if sek[s * 0x1000 + 0x211] == 0]
pruef('FWR PSK 0: Rekord in die erste Bank des Projekts', m.ram[0x38] == 5 and bytes([0, 123]) in gueltig, (text(m.anzeige()), gueltig))
fl = SPIFlash(); m = CP1(ROM, True, flash=fl)
for n, (b, a) in enumerate([(PSK, 0), (PSK, 0), (PSK, 1), (FRD, 50), (HLT, 0)]): m.intern.ram[2*n:2*n+2] = bytes([b, a])
m.bis(m.us + 1_500_000); starte(m, 600)
pruef('FRD ohne Projekt: F 003', text(m.anzeige()).endswith('003'), text(m.anzeige()))
# Tempo
m = geladen([(SEF, 0), (SEF, 6)] * 10 + [(HLT, 0)])
m.drueck('run', m.us + 1000, 100); t = m.us; t_ende = None
while m.us < t + 3_000_000:
    m.bis(m.us + 1000)
    if m.ram[0x38] == 21: t_ende = m.us; break
dauer = (t_ende - t - 100_000) / 20000 if t_ende else None
pruef(f'SEF dauert {dauer:.1f} ms' if dauer else 'SEF Dauer', dauer is not None and dauer < 15, dauer)
print('ALLES OK' if not f else f'{f} FEHLER')
sys.exit(1 if f else 0)
