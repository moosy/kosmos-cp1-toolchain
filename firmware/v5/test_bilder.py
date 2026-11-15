"""5.06: Bilder für SEF über die Pi-Seite: Bildertabelle -> Namensbereich -> Firmware zeigt sie; Assembler „SEF name“."""
import sys, os
hier = os.path.dirname(os.path.abspath(__file__))
for p in (os.path.join(hier, '..', '..'), hier): sys.path.insert(0, p)
from sim48 import CP1, SPIFlash, text
import kosmos_remote as kr
ROM = open(os.path.join(hier, 'cp1v5-eeprom.bin'), 'rb').read()
f = 0
def pruef(n, ok, i=''):
    global f; print(('  ok   ' if ok else '  FEHL ') + n + ('' if ok else f'  [{i}]')); f += not ok

bilder = kr.bilder_lesen('titel=MInEn\nexplo=#255,254,252,248,240,224\nlauf=  HALLO CP1  \nleer=\n')
pruef('Bilder gelesen', [n for n, _ in bilder] == ['titel', 'explo', 'lauf', 'leer'] and len(bilder[2][1]) == 13 and len(bilder[3][1]) == 6)
namen = {i: f'name_{i}' for i in range(0, 60)}
nb = kr.namen_bytes(namen, kr.anzeige_aus_text('SPACE'), bilder)
pruef('768 Byte', len(nb) == 768, len(nb))
pruef('Namen kommen zurück', kr.namen_aus_bytes(nb) == namen)
pruef('Bilder kommen zurück', kr.bilder_aus_bytes(nb) == bilder, kr.bilder_aus_bytes(nb))
pruef('Anzeige kommt zurück', kr.anzeige_aus_bytes(nb) == kr.anzeige_aus_text('SPACE'))
pruef('Bildertext Rundlauf', kr.bilder_lesen(kr.bilder_text(bilder)) == bilder, kr.bilder_text(bilder))
try:
    kr.namen_bytes({i: f'ein_sehr_langer_name_{i}' for i in range(30)}, None, bilder); pruef('zu voll erkannt', False)
except ValueError as e:
    pruef('Namen + Bilder zu groß: Fehlermeldung', 'voll' in str(e), e)

quelle = '>start:\nSEF titel\nVZG 250\nSEF lauf+3\n>halt:\nSPU halt\nSEF explo\n'
r = kr.assemblieren(quelle, '', kr.bilder_text(bilder))
_, pos = kr.bilder_layout(bilder)
pruef('SEF name -> Position', r['zellen'][0] == (47, pos['titel']) and r['zellen'][2] == (47, pos['lauf'] + 3), (r['zellen'][0], pos))
pruef('Quelltext behält die Namen', 'SEF titel' in r['quelltext'] and 'SEF lauf+3' in r['quelltext'])
lst = kr.disasm({k: v for k, v in r['zellen'].items() if k < 5}, None, bilder)
pruef('Disassembler zeigt SEF titel / lauf+3', 'SEF titel' in lst and 'SEF lauf+3' in lst, lst)

# Firmware: Sektor bauen, laden, SEF zeigen
fl = SPIFlash()
s = bytearray([0xFF]) * 0x1000
for n in range(256): s[2*n:2*n+2] = bytes(r['zellen'].get(n, (0, 0)))
s[0x200:0x210] = b'Bildertest      '; s[0x210] = 0; s[0x211] = 0; s[0x212] = 0
s[0x300:0x600] = nb
fl.m[9 * 0x2000: 9 * 0x2000 + 0x1000] = s
m = CP1(ROM, True, flash=fl); m.bis(m.us + 1_500_000)
m.ram[0x2c] = 9; m.ram[0x26] = 4; m.drueck('cal', m.us + 1000, 100); m.bis(m.us + 1_500_000)
m.drueck('run', m.us + 1000, 100); m.bis(m.us + 200_000)
pruef('Gerät zeigt titel', bytes(m.anzeige()) == bilder[0][1], [hex(x) for x in m.anzeige()])
m.bis(m.us + 500_000)
pruef('dann lauf+3 (Lauftext-Schritt)', bytes(m.anzeige()) == bilder[2][1][3:9], ([hex(x) for x in m.anzeige()], text(m.anzeige())))
print('ALLES OK' if not f else f'{f} FEHLER')
