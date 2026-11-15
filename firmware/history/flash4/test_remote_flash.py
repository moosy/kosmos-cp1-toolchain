import sys, types
sys.path.insert(0, 'cp1/v4'); sys.path.insert(0, 'remote')
sys.modules['lgpio'] = types.ModuleType('lgpio')
from sim48 import CP1, SPIFlash, text
import kosmos_remote as kr
ROM = open('cp1/v4/cp1v4-eeprom.bin', 'rb').read()
fl = SPIFlash()
m = CP1(ROM, flash=fl)
class Sim(kr.Leitung):
    def __init__(self): self.lock = kr.threading.RLock()
    def schreib(self, adr, w): m.ram[adr] = w
    def ram(self, adr, n): m.bis(m.us + 150_000); return bytes(m.ram[adr:adr + n])
    def taste(self, name, ms=100): m.drueck(name, m.us + 10_000, ms); m.bis(m.us + 10_000 + ms * 1000 + 60_000)
    def anzeige(self): return {'text': kr.segtext(bytes(m.ram[0x20:0x26]))}
kr.time.sleep = lambda s: m.bis(m.us + s * 1e6)
L = Sim(); f = 0
def pruef(n, ok, i=''):
    global f; print(('  ok   ' if ok else '  FEHL ') + n, '' if ok else i); f += not ok
pruef('leeres Flash', L.flash_verzeichnis() == {'autoboot': 0, 'baenke': []}, str(L.flash_verzeichnis()))
for n, (b, a) in enumerate([(4, 7), (2, 0), (1, 0)]): m.intern.ram[2*n:2*n+2] = bytes([b, a])
L.flash_speichern(12, 'Rakete', 0)
for n, (b, a) in enumerate([(4, 8), (2, 0), (1, 0)]): m.intern.ram[2*n:2*n+2] = bytes([b, a])
L.flash_speichern(3, 'Zähler äöü', 1)
L.flash_speichern(200, '', None)
v = L.flash_verzeichnis()
pruef('drei Bänke mit Namen und Start', v['baenke'] == [{'bank': 3, 'name': 'Z?hler ???', 'start': 1}, {'bank': 12, 'name': 'Rakete', 'start': 0},
      {'bank': 200, 'name': '', 'start': 1}], str(v))
L.flash_autoboot(12)
pruef('Autoboot 12', L.flash_verzeichnis()['autoboot'] == 12)
L.flash_laden(12)
pruef('laden: Zelle 0 = 04.007, PC 0', bytes(m.intern.ram[0:2]) == bytes([4, 7]) and m.ram[0x38] == 0)
try: L.flash_laden(99); pruef('leere Bank -> Fehler', False)
except kr.FlashFehler as e: pruef('leere Bank -> F-011', 'F-011' in str(e), str(e))
print('ALLES OK' if not f else f'{f} FEHLER')
