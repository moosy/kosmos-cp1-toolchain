"""Tests der schnellen Kassette im Simulator: python3 test_schnell.py"""
import sys, random, bisect, time
sys.path.insert(0, '.')
from sim48 import CP1, text

ROM = open('cp1schnell.bin', 'rb').read()
fehler = 0


def pruef(name, ok, info=''):
    global fehler
    print(('  ok   ' if ok else '  FEHL ') + name + (f'  [{info}]' if info else ''))
    if not ok: fehler += 1


def crc8(daten):
    c = 0
    for b in daten:
        c ^= b
        for _ in range(8):
            c = ((c << 1) ^ 0x07) & 0xFF if c & 0x80 else (c << 1) & 0xFF
    return c


def neu(cp3=True):
    m = CP1(ROM, cp3)
    m.bis(300_000)                                   # Start, clear_ram
    for n in range(256):                             # Testprogramm: Zelle n = (n % 100, 255 - n)
        chip, a = (m.intern, 2 * n) if n < 128 else (m.cp3, 2 * (n - 128))
        chip.ram[a] = n % 100; chip.ram[a + 1] = 255 - n
    return m


def zelle(m, n):
    chip, a = (m.intern, 2 * n) if n < 128 else (m.cp3, 2 * (n - 128))
    return chip.ram[a], chip.ram[a + 1]


def dekodiere(log, ab):
    """Low-Pulse aus dem P1.7-Log: < 0,75 ms = 1, sonst 0. Liefert Bytes."""
    pulse = []
    for (t0, l0), (t1, l1) in zip(log, log[1:]):
        if t0 >= ab and l0 == 0 and l1 == 1:
            pulse.append(t1 - t0)
    bits = [1 if p < 900 else 0 for p in pulse]
    by = [sum(b << i for i, b in enumerate(bits[k:k + 8])) for k in range(0, len(bits) - len(bits) % 8, 8)]
    return by, pulse


def warte_text(m, ziel, bis_us):
    m.bis(bis_us, halt=lambda mm: ziel in text(mm.anzeige()))
    return text(m.anzeige())


def sende_pi(m, ab_us, daten, kurz=400, lang=1200, pause=400, byte_pause=2000, jitter=0, seed=1):
    """Pi legt die Bytes ab ab_us auf die Leitung (Low = Bit)."""
    rnd = random.Random(seed)
    kanten = []; t = ab_us
    for b in daten:
        for i in range(8):
            d = kurz if b >> i & 1 else lang
            d += rnd.uniform(-jitter, jitter)
            kanten.append((t, t + d)); t += d + pause + rnd.uniform(0, jitter)
        t += byte_pause
    starts = [k[0] for k in kanten]

    def pegel(tu):
        i = bisect.bisect_right(starts, tu) - 1
        return 0 if i >= 0 and kanten[i][0] <= tu < kanten[i][1] else 1
    m.pi = pegel
    return t


t_start = time.time()
print('1) CAS kurz: alles speichern (mit CP3)')
m = neu()
m.drueck('cas', 400_000, 150)
ab = 400_000
end = warte_text(m, 'rdY', 30_000_000)
pruef('Anzeige ⊓  rdY am Ende', end == '¬  rdY', end)
by, pulse = dekodiere(m.p1_log, ab)
pruef('Kennung $C1, 000..255', by[:3] == [0xC1, 0, 255], str(by[:3]))
erwartet = [0xC1, 0, 255] + [x for n in range(256) for x in zelle(m, n)]
pruef('Daten = Speicher', by[:-1] == erwartet, f'{len(by)} Byte')
pruef('CRC stimmt', by[-1] == crc8(by[:-1]))
kurz = [p for p in pulse if p < 900]; lang = [p for p in pulse if p >= 900]
pruef('Pulslängen', max(kurz) < 750 and min(lang) > 1150, f'kurz {min(kurz):.0f}–{max(kurz):.0f}, lang {min(lang):.0f}–{max(lang):.0f} µs')
t_daten = m.p1_log[-1][0] - m.p1_log[0][0]
print(f'     Dauer der Übertragung: {t_daten / 1e6:.2f} s für {len(by)} Byte')

print('2) Anzeige während des Sendens')
m = neu()
m.drueck('cas', 400_000, 150)
gesehen = set()
m.bis(4_000_000, halt=lambda mm: gesehen.add(text(mm.anzeige())) and False)
pruef('⊓ sofort, Anlauf - -- --- rechts', {'¬     ', '¬  -  ', '¬  -- ', '¬  ---'} <= gesehen, str(sorted(gesehen))[:120])
pruef('⊓ SE 0xx während Senden', any(g.startswith('¬5E0') for g in gesehen), str([g for g in gesehen if g.startswith('¬5E')][:3]))

print('3) CAS halten: Teilbereich 035..139, CLR und Tauschen')
m = neu()
m.drueck('cas', 400_000, 1300)
t = 1_900_000
halt_gesehen = []
m.bis(1_350_000, halt=lambda mm: (text(mm.anzeige()) not in halt_gesehen and halt_gesehen.append(text(mm.anzeige()))) and False)
pruef('Halten: ⊓, dann _ __ ___ rechts', [g for g in halt_gesehen if g.startswith('¬  ')][-3:] == ['¬  _  ', '¬  __ ', '¬  ___'] or
      all(x in halt_gesehen for x in ('¬     ', '¬  _  ', '¬  __ ', '¬  ___')), str(halt_gesehen))
pruef('Anzeige ⊓ Fr ___', warte_text(m, '¬Fr___', t) == '¬Fr___')
for k in ('1', '3', 'clr', '0', '3', '5'):       # 13 tippen, CLR, 035
    m.drueck(k, t, 120); t += 300_000
m.bis(t)
pruef('Anzeige ⊓ Fr 035', text(m.anzeige()) == '¬Fr035', text(m.anzeige()))
m.drueck('cas', t, 120); t += 300_000
pruef('Anzeige ⊓ to ___', warte_text(m, '¬to___', t) == '¬to___', text(m.anzeige()))
for k in ('1', '3', '9'):
    m.drueck(k, t, 120); t += 300_000
m.drueck('cas', t, 120); ab = t
end = warte_text(m, 'rdY', t + 10_000_000)
by, _ = dekodiere(m.p1_log, ab)
pruef('Kopf 035..139', by[:3] == [0xC1, 35, 139], str(by[:3]))
pruef('105 Zellen + CRC', len(by) == 3 + 2 * 105 + 1 and by[-1] == crc8(by[:-1]), str(len(by)))

m = neu()
m.drueck('cas', 400_000, 1300); t = 1_900_000
for k in ('2', '0', '0', 'cas', '0', '1', '0', 'cas'):
    m.drueck(k, t, 120); t += 300_000
ab = t - 300_000
warte_text(m, 'rdY', t + 10_000_000)
by, _ = dekodiere(m.p1_log, ab)
pruef('200 / 010 getauscht -> 010..200', by[:3] == [0xC1, 10, 200], str(by[:3]))

print('4) ohne Speichererweiterung: Grenze 127')
m = neu(cp3=False)
pruef('MEM_SIZE = 127', m.ram[0x3b] == 0x7f)
m.drueck('cas', 400_000, 1300); t = 1_900_000
for k in ('1', '0', '0', 'cas', '2', '0', '0', 'cas'):
    m.drueck(k, t, 120); t += 300_000
ab = t - 300_000
warte_text(m, 'rdY', t + 10_000_000)
by, _ = dekodiere(m.p1_log, ab)
pruef('100..200 -> 100..127', by[:3] == [0xC1, 100, 127], str(by[:3]))
m2 = neu(cp3=False)
m2.drueck('cas', 400_000, 150)
warte_text(m2, 'rdY', 30_000_000)
by, _ = dekodiere(m2.p1_log, 400_000)
pruef('CAS kurz -> 000..127', by[:3] == [0xC1, 0, 127] and len(by) == 3 + 256 + 1, f'{by[:3]} {len(by)}')

print('5) CAL: Teilbereich 200..255 laden, Rest bleibt')
m = neu()
vorher = [zelle(m, n) for n in range(256)]
neu_daten = [(7, 200 + i) for i in range(56)]
rahmen = [0xC1, 200, 255] + [x for z in neu_daten for x in z]
rahmen.append(crc8(rahmen))
m.drueck('cal', 400_000, 150)
ende_pi = sende_pi(m, 1_400_000, rahmen, jitter=80)
gesehen = set()
m.bis(ende_pi + 200_000, halt=lambda mm: gesehen.add(text(mm.anzeige())) and False)
end = text(m.anzeige())
pruef('Anzeige ⊔  rdY', end == 'u  rdY', end)
pruef('⊔ + Warte-Striche rechts', 'u  ---' in gesehen, str(sorted(gesehen))[:100])
pruef('⊔ rc 2xx gesehen', any(g.startswith('urc2') for g in gesehen))
pruef('Zellen 200..255 neu', [zelle(m, n) for n in range(200, 256)] == neu_daten)
pruef('Zellen 0..199 unverändert', [zelle(m, n) for n in range(200)] == vorher[:200])
print(f'     Dauer: {(ende_pi - 1_400_000) / 1e6:.2f} s für {len(rahmen)} Byte')

print('6) CAL mit falscher CRC -> C Su Err')
m = neu()
r2 = rahmen[:-1] + [rahmen[-1] ^ 0x55]
m.drueck('cal', 400_000, 150)
ende_pi = sende_pi(m, 800_000, r2)
m.bis(ende_pi + 200_000)
pruef('Anzeige C Su Err', text(m.anzeige()) == 'u5uErr', text(m.anzeige()))

print('7) CAL: falscher Kopf (letzte > 127 ohne CP3) -> Fehler')
m = neu(cp3=False)
m.drueck('cal', 400_000, 150)
ende_pi = sende_pi(m, 800_000, rahmen)
m.bis(ende_pi + 200_000)
pruef('Anzeige C Su Err', text(m.anzeige()) == 'u5uErr', text(m.anzeige()))

print('8) STP bricht ab')
m = neu()
m.drueck('cas', 400_000, 150); m.drueck('stp', 2_500_000, 150)
m.bis(3_500_000)
n_kanten = len(m.p1_log)
m.bis(5_000_000)
pruef('Senden gestoppt, Anzeige leer', text(m.anzeige()).strip() == '' and len(m.p1_log) == n_kanten, text(m.anzeige()))
m = neu()
m.drueck('cal', 400_000, 150); m.drueck('stp', 1_500_000, 150)
m.bis(2_500_000)
pruef('CAL-Warten gestoppt', text(m.anzeige()).strip() == '', text(m.anzeige()))
m = neu()
m.drueck('cas', 400_000, 1300); m.drueck('1', 1_900_000, 120); m.drueck('stp', 2_300_000, 120)
m.bis(3_000_000)
pruef('Eingabe gestoppt', text(m.anzeige()).strip() == '', text(m.anzeige()))
# danach geht der CP1 normal weiter: Taste PC zeigt P...
m.drueck('pc', 3_100_000, 120); m.bis(3_600_000)
pruef('danach normale Bedienung (PC)', text(m.anzeige()).startswith('P'), text(m.anzeige()))

print('9) CAL mit Störungen: Jitter ±150 µs auf jeder Flanke')
m = neu()
m.drueck('cal', 400_000, 150)
ende_pi = sende_pi(m, 800_000, rahmen, kurz=400, lang=1200, jitter=150, seed=7)
m.bis(ende_pi + 200_000)
pruef('trotzdem rdY', text(m.anzeige()) == 'u  rdY', text(m.anzeige()))

print('10) Rundreise: senden, in zweiten CP1 laden')
a = neu()
a.drueck('cas', 400_000, 150)
warte_text(a, 'rdY', 30_000_000)
by, _ = dekodiere(a.p1_log, 400_000)
b = CP1(ROM); b.bis(300_000)
b.drueck('cal', 400_000, 150)
ende_pi = sende_pi(b, 800_000, by)
b.bis(ende_pi + 200_000)
pruef('B: rdY und Speicher gleich A', text(b.anzeige()) == 'u  rdY' and
      all(zelle(a, n) == zelle(b, n) for n in range(256)), text(b.anzeige()))

print(f'\n{"ALLES OK" if fehler == 0 else f"{fehler} FEHLER"}  ({time.time() - t_start:.0f} s Rechenzeit)')
sys.exit(1 if fehler else 0)
