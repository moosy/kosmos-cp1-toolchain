import sys, json
sys.path.insert(0, '.')
from sim48 import CP1, text
import kosmos_schnell as ks
exec(open('test_schnell.py').read().split('t_start = time.time()')[0])

class Rec(CP1):
    def __init__(s, *a, **k):
        super().__init__(*a, **k); s.isr = []; s.anz = []; s._la = None
    def schritt(s):
        if s.int_wartet and not s.im_int: s.isr_start = s.us
        war = s.im_int
        super().schritt()
        if war and not s.im_int: s.isr.append((round(s.isr_start), round(s.us - s.isr_start)))
        a = list(s.ram[0x20:0x26])
        if a != s._la: s.anz.append((round(s.us), a)); s._la = a

def neu_rec(cp3=True):
    m = Rec(ROM, cp3); m.bis(300_000)
    for n in range(256):
        chip, a = (m.intern, 2 * n) if n < 128 else (m.cp3, 2 * (n - 128))
        chip.ram[a] = n % 100; chip.ram[a + 1] = 255 - n
    return m

def paket(m, titel, info, t0, t1, tasten, pi_bytes=None):
    anz = [(t, a) for t, a in m.anz if t0 - 1 <= t <= t1]
    vor = [a for t, a in m.anz if t < t0]
    if vor: anz.insert(0, (t0, vor[-1]))
    kanten = [(round(t), l) for t, l in m.p1_log if t0 <= t <= t1]
    return dict(titel=titel, info=info, t0=t0, t1=t1, anzeige=anz, kanten=kanten,
                isr=[i for i in m.isr if t0 <= i[0] <= t1],
                tasten=[(k, a, b) for k, a, b in tasten], richtung=pi_bytes)

out = []
# 1) CAS halten, 035..060
m = neu_rec(); tasten = [('cas', 400_000, 1_700_000)]
t = 1_900_000
for k in ('0', '3', '5', 'cas', '0', '6', '0', 'cas'):
    tasten.append((k, t, t + 140_000)); t += 450_000
for k, a, b in tasten: m.tasten.append((k, a, b))
warte_text(m, 'rdY', t + 10_000_000); m.bis(m.us + 600_000)
by, _ = dekodiere(m.p1_log, 400_000)
out.append(paket(m, 'CAS halten: Zellen 035–060 senden', f'CP1 → Pi, {len(by)} Byte, Kopf {by[1]:03d}–{by[2]:03d}, CRC {by[-1]:02X}', 300_000, round(m.us), tasten, 'cp1'))
# 2) CAL: 200..255
m = neu_rec()
neu_daten = [(7, 200 + i) for i in range(56)]
rahmen = list(ks.rahmen_bauen({200 + i: v for i, v in enumerate(neu_daten)}))
tasten = [('cal', 400_000, 550_000)]; m.tasten += tasten
ende = sende_pi(m, 1_500_000, rahmen, jitter=60)
m.bis(ende + 600_000)
out.append(paket(m, 'CAL: Bibliothek in Zellen 200–255 laden', f'Pi → CP1, {len(rahmen)} Byte, Rest des Speichers bleibt', 300_000, round(m.us), tasten, 'pi'))
# 3) CAL mit Prüfsummenfehler
m = neu_rec()
r2 = ks.rahmen_bauen({10 + i: (1, i) for i in range(8)}); r2 = list(r2[:-1]) + [r2[-1] ^ 0x21]
tasten = [('cal', 400_000, 550_000)]; m.tasten += tasten
ende = sende_pi(m, 1_200_000, r2)
m.bis(ende + 600_000)
out.append(paket(m, 'CAL mit falscher Prüfsumme', 'Pi → CP1, 8 Zellen, letztes Byte verfälscht', 300_000, round(m.us), tasten, 'pi'))
json.dump(out, open('viz.json', 'w'), separators=(',', ':'))
for p in out: print(p['titel'], (p['t1'] - p['t0']) / 1e6, 's', len(p['anzeige']), 'Anzeigen', len(p['kanten']), 'Kanten', len(p['isr']), 'ISR', 'ISR-Dauer max', max(d for _, d in p['isr']))
import os; print(os.path.getsize('viz.json'), 'Byte')
