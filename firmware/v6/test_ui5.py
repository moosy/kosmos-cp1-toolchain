"""5.00/6.00: Tasten CAS/CAL kurz und lang mit Projekten, RUN lang (Autoboot), Demos 8/9 RUN, Start mit 6.00."""
import sys
sys.path.insert(0, '.')
from sim48 import CP1, SPIFlash, text
import verz6
ROM = open('cp1v6-eeprom.bin', 'rb').read()
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
    s0, s1 = fl.m[b * 0x2000: b * 0x2000 + 0x1000], fl.m[b * 0x2000 + 0x1000: b * 0x2000 + 0x2000]
    g0, g1 = s0[0x211] == 0, s1[0x211] == 0
    if g0 and g1: return s1 if (s0[0x210] + 1) & 0xFF == s1[0x210] else s0
    return s1 if g1 else s0 if g0 else None

def tippe(m, tasten, abstand=180, dauer=120):
    t = m.us + 50_000
    for k in tasten:
        if isinstance(k, tuple): k, d = k
        else: d = dauer
        m.drueck(k, t, d); t += d * 1000 + abstand * 1000
    m.bis(t)

def warte(m, ms):
    m.bis(m.us + ms * 1000)

print('Start')
m0 = CP1(ROM, True, vorlauf=False, flash=SPIFlash()); m0.bis(500_000)
pruef('Version „  6.22 “ (Punkt nach der 6)', list(m0.anzeige()) == [0, 0, 0xfd, 0x5b, 0x5b, 0], str([hex(x) for x in m0.anzeige()]))
m0.bis(1_500_000)
pruef('Fernsteuerung immer an (RC_FLAG Bit 0)', m0.ram[0x46] & 1 == 1, hex(m0.ram[0x46]))

fl = SPIFlash()
m = CP1(ROM, True, flash=fl)
for n in range(0, 20): zelle(m, n, 0, n + 1)
zelle(m, 5, 4, 77); m.ram[0x38] = 3          # PC = 3

print('CAS kurz: Pro __, 4 CAS -> ganzes RAM ins (neue) Projekt 4, Start = PC')
tippe(m, ['cas'])
pruef('Abfrage „Pro __“ (6.00: zweistellig)', text(m.anzeige()) == 'Pro __', text(m.anzeige()))
tippe(m, ['4']); 
pruef('erste Ziffer links wie bei drei Stellen: „Pro 4_“', text(m.anzeige()) == 'Pro 4_', text(m.anzeige()))
tippe(m, ['cas']); warte(m, 3500)
v = verz6.lesen(fl)
pruef('Projekt 4 angelegt: Bank 4, 4 Bänke', v is not None and v['projekte'].get(4, {}).get('bank') == 4 and v['projekte'][4]['res'] == 4, str(v))
s = verz6.gueltig(fl, 4)
pruef('Bank 4 = RAM, Start-PC 003 (0x213)', s is not None and bytes(s[0:40]) == b''.join(bytes(zelle(m, n)) for n in range(20)) and s[0x213] == 3, '' if s is None else s[0:12].hex())
pruef('Anzeige „5to rdY“', text(m.anzeige()) == '5tordY', text(m.anzeige()))

print('CAS kurz mit Projekt 00 -> F-003, STP bricht ab, dritte Ziffer zählt nicht')
tippe(m, ['cas', '0', '0', 'cas']); warte(m, 300)
pruef('F-003', text(m.anzeige()) == 'F  003', text(m.anzeige()))
tippe(m, ['cas', '1', '2', '3'])
pruef('nur zwei Ziffern: „Pro 12“', text(m.anzeige()) == 'Pro 12', text(m.anzeige()))
tippe(m, ['stp']); warte(m, 300)
pruef('STP: Anzeige leer, wieder Tasten', text(m.anzeige()).strip() == '', text(m.anzeige()))

print('CAS lang: Fr 010 to 012 Pro 06 d5t 100')
tippe(m, [('cas', 1300)])
pruef('Abfrage „Fr ___“', text(m.anzeige()) == 'Fr ___', text(m.anzeige()))
tippe(m, ['0', '1', '0', 'cas'])
pruef('Abfrage „to ___“', text(m.anzeige()) == 'to ___', text(m.anzeige()))
tippe(m, ['0', '1', '2', 'cas'])
pruef('Abfrage „Pro __“', text(m.anzeige()) == 'Pro __', text(m.anzeige()))
tippe(m, ['0', '6', 'cas'])
pruef('Abfrage „d5t ___“', text(m.anzeige()) == 'd5t___', text(m.anzeige()))
tippe(m, ['1', '0', '0', 'cas']); warte(m, 3500)
v = verz6.lesen(fl)
pruef('Projekt 6 angelegt hinter Projekt 4: Bank 8', v['projekte'].get(6, {}).get('bank') == 8, str(v['projekte']))
s = verz6.gueltig(fl, 8)
pruef('Bank 8 Zellen 100..102 = RAM 10..12, sonst 0, kein Start', s is not None and bytes(s[200:206]) == b''.join(bytes(zelle(m, n)) for n in range(10, 13)) and bytes(s[0:200]) == bytes(200) and s[0x213] == 0xFF,
      '' if s is None else s[198:208].hex())
pruef('Anzeige „5to rdY“', text(m.anzeige()) == '5tordY', text(m.anzeige()))

print('CAS lang: Vorgaben (nur CAS drücken): ganzes RAM -> Projekt 07 ab Zelle 0')
tippe(m, [('cas', 1300), 'cas', 'cas', '0', '7', 'cas', 'cas']); warte(m, 4000)
v = verz6.lesen(fl); s = verz6.gueltig(fl, v['projekte'].get(7, {}).get('bank', 0))
pruef('Projekt 7 (Bank 12) = RAM 0..255', v['projekte'].get(7, {}).get('bank') == 12 and s is not None and bytes(s[0:40]) == b''.join(bytes(zelle(m, n)) for n in range(20)), str(v['projekte']))

print('CAS lang: dst + Anzahl über 255 -> F-003')
tippe(m, [('cas', 1300), '0', '0', '0', 'cas', '0', '1', '0', 'cas', '0', '8', 'cas', '2', '5', '0', 'cas']); warte(m, 400)
pruef('F-003', text(m.anzeige()) == 'F  003', text(m.anzeige()))

print('CAL kurz: blättern, dann Projekt 4 per Ziffer laden')
for n in range(0, 20): zelle(m, n, 0, 0)
m.ram[0x38] = 0
tippe(m, ['cal']); warte(m, 150)
pruef('CAL kurz blättert, erstes Projekt „Pro 04“', text(m.anzeige()) == 'Pro 04', text(m.anzeige()))
tippe(m, ['0', '4', 'cal']); warte(m, 2000)
pruef('RAM wieder da', [zelle(m, n) for n in range(4, 7)] == [(0, 5), (4, 77), (0, 7)], str([zelle(m, n) for n in range(4, 7)]))
pruef('PC = 003, Anzeige „P 003“', m.ram[0x38] == 3 and text(m.anzeige()) == 'P  003', f'{m.ram[0x38]} {text(m.anzeige())}')
pruef('S_PBANK/S_PRES = 4/4', (m.ram[0x5f], m.ram[0x5e]) == (4, 4))

print('CAL lang: Pro 06, Fr 100, to 102, d5t 050')
tippe(m, [('cal', 1300)])
pruef('Abfrage „Pro __“', text(m.anzeige()) == 'Pro __', text(m.anzeige()))
tippe(m, ['0', '6', 'cal', '1', '0', '0', 'cal', '1', '0', '2', 'cal', '0', '5', '0', 'cal']); warte(m, 2000)
pruef('RAM 50..52 = Projekt 6 Zellen 100..102', [zelle(m, n) for n in range(50, 53)] == [zelle(m, n) for n in range(10, 13)], str([zelle(m, n) for n in range(50, 53)]))
pruef('PC bleibt 003, Anzeige „LdP rdY“', m.ram[0x38] == 3 and text(m.anzeige()) == 'LdPrdY', f'{m.ram[0x38]} {text(m.anzeige())}')

print('CAL: Projekt, das es nicht gibt -> F-011')
tippe(m, ['cal', '9', '9', 'cal']); warte(m, 1500)
pruef('F-011', text(m.anzeige()) == 'F  011', text(m.anzeige()))

print('RUN lang: bot 04 -> Autoboot; RUN kurz startet weiter das Programm')
tippe(m, [('run', 1300)])
pruef('Abfrage „bot __“', text(m.anzeige()) == 'bot __', text(m.anzeige()))
tippe(m, ['0', '4', 'run']); warte(m, 2000)
pruef('Bank 1 (Einstellungen) Autoboot 4, „bot rdY“', verz6.lesen(fl)['autoboot'] == 4 and text(m.anzeige()) == 'botrdY', text(m.anzeige()))
m2 = CP1(ROM, True, vorlauf=False, flash=fl); m2.bis(1_900_000)
pruef('Einschalten: „bot 04“', text(m2.anzeige()) == 'bot 04', text(m2.anzeige()))
m2.bis(5_000_000)
pruef('danach geladen und gestartet', zelle(m2, 5) == (4, 77) and m2.ram[0x38] != 3 or text(m2.anzeige()) != 'bot 04', f'{text(m2.anzeige())} PC {m2.ram[0x38]}')
tippe(m, [('run', 1300), '0', 'run']); warte(m, 2000)
pruef('bot 0 schaltet aus', verz6.lesen(fl)['autoboot'] == 0)
m3 = CP1(ROM, True, flash=SPIFlash())
zelle(m3, 0, 4, 42); zelle(m3, 1, 1, 0)           # AKO 42, HLT
tippe(m3, ['run']); warte(m3, 400)
pruef('RUN kurz: Programm läuft (AKO 42, HLT)', m3.ram[0x37] == 42 and text(m3.anzeige()).startswith('P'), f'{m3.ram[0x37]} {text(m3.anzeige())}')

print('Demos 8 RUN / 9 RUN (jetzt in Hälfte A)')
m4 = CP1(ROM, True, flash=SPIFlash())
tippe(m4, ['9', 'run']); warte(m4, 700)
pruef('9 RUN: Countdown zeigt sechsmal dieselbe Ziffer', len(set(text(m4.anzeige()))) == 1 and text(m4.anzeige())[0] in '98', text(m4.anzeige()))
warte(m4, 6000)
pruef('… und endet', text(m4.anzeige()) == '000000', text(m4.anzeige()))
m5 = CP1(ROM, True, flash=SPIFlash())
tippe(m5, ['8', 'run']); warte(m5, 1100)
z1 = text(m5.anzeige()); warte(m5, 60); z2 = text(m5.anzeige())
pruef('8 RUN: Reaktionstest zählt hoch', z1 != z2 and z2.strip().isdigit(), f'{z1!r} -> {z2!r}')
warte(m5, 600)
pruef('nach ~255 ms Ende bei 255', text(m5.anzeige()) == '   255', text(m5.anzeige()))
m5 = CP1(ROM, True, flash=SPIFlash())
tippe(m5, ['8', 'run']); warte(m5, 1050)
tippe(m5, ['stp']); warte(m5, 100)
z3 = text(m5.anzeige()); warte(m5, 300)
pruef('STP hält ihn an (Reaktionszeit bleibt stehen)', text(m5.anzeige()) == z3, f'{z3!r} {text(m5.anzeige())!r}')
print('ALLES OK' if not fehler else f'{fehler} FEHLER'); sys.exit(1 if fehler else 0)
