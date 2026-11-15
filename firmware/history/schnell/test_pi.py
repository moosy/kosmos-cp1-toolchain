"""Pi-Werkzeug (kosmos_schnell.py, reine Logik) gegen den simulierten CP1 testen."""
import sys, random, bisect
sys.path.insert(0, '.')
from sim48 import CP1, text
import kosmos_schnell as ks
exec(open('test_schnell.py').read().split('t_start = time.time()')[0].split('def sende_pi')[0])
fehler = 0
def pruef(name, ok, info=''):
    global fehler
    print(('  ok   ' if ok else '  FEHL ') + name + (f'  [{info}]' if info else ''))
    if not ok: fehler += 1

def pi_wellenform(m, ab, plan, jitter=0, seed=3):
    rnd = random.Random(seed); kanten = []; t = ab
    for low, high in plan:
        low += rnd.uniform(-jitter, jitter); kanten.append((t, t + low)); t += low + high
    starts = [k[0] for k in kanten]
    def pegel(tu):
        i = bisect.bisect_right(starts, tu) - 1
        return 0 if i >= 0 and kanten[i][0] <= tu < kanten[i][1] else 1
    m.pi = pegel
    return t

print('A) recv: CP1 sendet alles, Pi dekodiert')
m = neu(); m.drueck('cas', 400_000, 150); warte_text(m, 'rdY', 30_000_000)
kanten = [(int(t * 1000), l) for t, l in m.p1_log]
z = ks.rahmen_lesen(ks.bytes_aus_pulsen(ks.lowpulse(kanten)))
pruef('256 Zellen = Speicher', z == {n: zelle(m, n) for n in range(256)})
ks.json_schreiben('/tmp/claude-1106/-home-benutzer-moosy/75f83826-78f5-4948-9d9c-8f85afc10ac3/scratchpad/t.json', z)
z2 = ks.json_lesen('/tmp/claude-1106/-home-benutzer-moosy/75f83826-78f5-4948-9d9c-8f85afc10ac3/scratchpad/t.json')
pruef('JSON hin und zurück', z2 == z)

print('B) send: Pi sendet Bereich 020..060 mit Zittern ±120 µs')
quelle = {n: (n % 37, (3 * n) & 255) for n in range(256)}
daten = ks.rahmen_bauen(quelle, 20, 60)
m = neu(); vorher = {n: zelle(m, n) for n in range(256)}
m.drueck('cal', 400_000, 150)
ende = pi_wellenform(m, 1_000_000, ks.pulsplan(daten), jitter=120)
m.bis(ende + 200_000)
pruef('rdY', text(m.anzeige()) == 'u  rdY', text(m.anzeige()))
pruef('Zellen 20..60 neu, Rest gleich', all(zelle(m, n) == (quelle[n] if 20 <= n <= 60 else vorher[n]) for n in range(256)))
print(f'     Dauer {(ende - 1_000_000) / 1e6:.2f} s für {len(daten)} Byte')

print('C) send: ganze Datei (256 Zellen)')
daten = ks.rahmen_bauen(quelle)
m = neu(); m.drueck('cal', 400_000, 150)
ende = pi_wellenform(m, 1_000_000, ks.pulsplan(daten), jitter=50)
m.bis(ende + 200_000)
pruef('rdY + alles gleich', text(m.anzeige()) == 'u  rdY' and all(zelle(m, n) == quelle[n] for n in range(256)), text(m.anzeige()))
print(f'     Dauer {(ende - 1_000_000) / 1e6:.2f} s')

print('D) Fehlerfälle der Logik')
try: ks.rahmen_bauen({1: (1, 2), 3: (1, 2)}); pruef('Lücke erkannt', False)
except ValueError as e: pruef('Lücke erkannt', True, str(e))
d = bytearray(ks.rahmen_bauen(quelle, 0, 3)); d[5] ^= 1
try: ks.rahmen_lesen(bytes(d)); pruef('CRC-Fehler erkannt', False)
except ValueError as e: pruef('CRC-Fehler erkannt', True, str(e))
print('ALLES OK' if not fehler else f'{fehler} FEHLER'); sys.exit(1 if fehler else 0)
