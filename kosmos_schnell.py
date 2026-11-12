#!/usr/bin/env python3
"""Schnelle Kassette für den Kosmos CP1 (Firmware „schnell“ ab 0x800, EEPROM-Bank JP3 = 1).

  kosmos_schnell.py recv datei.json              CP1 -> Pi (am CP1: CAS kurz = alles, CAS halten = Bereich)
  kosmos_schnell.py send datei.json [--von N] [--bis M]
                                                 Pi -> CP1 (am CP1 zuerst CAL drücken)

Auch erreichbar als  kosmos_recv.py --schnell …  bzw.  kosmos_send.py --schnell …

Leitung: GPIO 26 <-> P1.7 des 8049 (Klemme 8). Ruhe high. Bit = Low-Puls: 0,4 ms = 1, 1,2 ms = 0,
danach >= 0,4 ms high. Bytes LSB zuerst. Rahmen: $C1, erste Zelle, letzte Zelle, je Zelle Befehl +
Argument, CRC-8 (Polynom $07, Start 0) über alles davor.
JSON wie die übrigen Werkzeuge: {"000": [befehl, argument], ...}; empfangene Teilbereiche enthalten
nur die übertragenen Zellen.
"""
import json, os, sys, time

GPIO = 26
KURZ_US, LANG_US, PAUSE_US = 400, 1200, 400
BYTE_PAUSE_US = 2000          # CP1 rechnet nach jedem Byte (CRC, Speichern, Anzeige)
SCHWELLE_US = 900             # Empfang: Low-Puls kürzer = 1 (CP1 sendet 0,4–0,66 bzw. 1,2–1,47 ms)
KENNUNG = 0xC1


# ---------------------------------------------------------------- reine Logik (testbar ohne Pi)

def crc8(daten):
    c = 0
    for b in daten:
        c ^= b
        for _ in range(8):
            c = ((c << 1) ^ 0x07) & 0xFF if c & 0x80 else (c << 1) & 0xFF
    return c


def rahmen_bauen(zellen, von=None, bis=None):
    """zellen: {nr: (befehl, argument)}. Bereich lückenlos von..bis."""
    if not zellen:
        raise ValueError('keine Zellen')
    von = min(zellen) if von is None else von
    bis = max(zellen) if bis is None else bis
    if not 0 <= von <= bis <= 255:
        raise ValueError(f'Bereich {von}..{bis} ungültig')
    fehlt = [n for n in range(von, bis + 1) if n not in zellen]
    if fehlt:
        raise ValueError(f'Zellen fehlen in der Datei: {fehlt[:10]}{" …" if len(fehlt) > 10 else ""}')
    r = [KENNUNG, von, bis]
    for n in range(von, bis + 1):
        b, a = zellen[n]
        if not (0 <= b <= 255 and 0 <= a <= 255):
            raise ValueError(f'Zelle {n:03d}: Wert außerhalb 0..255')
        r += [b, a]
    return bytes(r + [crc8(r)])


def pulsplan(daten):
    """[(low_us, high_us)] je Bit; nach dem letzten Bit eines Bytes die Bytepause im High."""
    plan = []
    for b in daten:
        for i in range(8):
            plan.append([KURZ_US if b >> i & 1 else LANG_US, PAUSE_US])
        plan[-1][1] += BYTE_PAUSE_US
    return [tuple(p) for p in plan]


def lowpulse(kanten):
    """kanten: [(t_ns, pegel)] in Zeitfolge -> Liste der Low-Dauern in µs."""
    p, t_low = [], None
    for t, l in kanten:
        if l == 0 and t_low is None:
            t_low = t
        elif l == 1 and t_low is not None:
            p.append((t - t_low) / 1000); t_low = None
    return p


def bytes_aus_pulsen(pulse):
    bits = [1 if p < SCHWELLE_US else 0 for p in pulse]
    return bytes(sum(b << i for i, b in enumerate(bits[k:k + 8])) for k in range(0, len(bits) - 7, 8))


def rahmen_laenge(daten):
    """erwartete Gesamtlänge, sobald der Kopf da ist, sonst None"""
    if len(daten) < 3:
        return None
    return 3 + 2 * (daten[2] - daten[1] + 1) + 1 if daten[2] >= daten[1] else 4


def rahmen_lesen(daten):
    """-> {nr: (befehl, argument)} oder ValueError"""
    if len(daten) < 4 or daten[0] != KENNUNG:
        raise ValueError(f'kein Rahmen der schnellen Kassette (Anfang {daten[:3].hex()})')
    von, bis = daten[1], daten[2]
    if bis < von:
        raise ValueError(f'Kopf ungültig: {von}..{bis}')
    n = rahmen_laenge(daten)
    if len(daten) < n:
        raise ValueError(f'unvollständig: {len(daten)} von {n} Byte')
    if crc8(daten[:n - 1]) != daten[n - 1]:
        raise ValueError('Prüfsumme falsch')
    return {von + i: (daten[3 + 2 * i], daten[4 + 2 * i]) for i in range(bis - von + 1)}


def json_lesen(fn):
    with open(fn) as f:
        d = json.load(f)
    return {int(k): tuple(v) for k, v in d.items()}


def json_schreiben(fn, zellen):
    with open(fn, 'w') as f:
        json.dump({f'{n:03d}': list(v) for n, v in sorted(zellen.items())}, f)


# ---------------------------------------------------------------- Hardware (lgpio)

def _rt_an():
    try:
        os.sched_setscheduler(0, os.SCHED_FIFO, os.sched_param(50))
        return True
    except (PermissionError, AttributeError, OSError):
        return False


def senden(daten, vorlauf_s=0.1):
    import gc
    import lgpio
    plan = pulsplan(daten)
    h = lgpio.gpiochip_open(0)
    rt = _rt_an()
    if not rt:
        print('Hinweis: ohne Echtzeit-Priorität (mit sudo starten für sauberere Pulse).')
    ist = []
    try:
        lgpio.gpio_claim_output(h, GPIO, 1)
        time.sleep(vorlauf_s)
        gc.disable()
        ns = time.perf_counter_ns
        t = ns()
        for low, high in plan:
            lgpio.gpio_write(h, GPIO, 0)
            t0 = ns()
            ende = t0 + low * 1000
            while ns() < ende: pass
            lgpio.gpio_write(h, GPIO, 1)
            t1 = ns()
            ist.append((t1 - t0) / 1000)
            ende = t1 + high * 1000
            if high > 1500:                  # in Bytepausen schlafen (Kernel drosselt sonst Echtzeit)
                time.sleep((high - 1000) / 1e6)
            while ns() < ende: pass
    finally:
        gc.enable()
        lgpio.gpio_claim_input(h, GPIO, lgpio.SET_PULL_UP)   # Leitung freigeben
        lgpio.gpiochip_close(h)
    return ist


def empfangen(warte_s=120, still_s=1.0, fortschritt=None):
    """Kanten aufzeichnen bis der Rahmen vollständig ist oder still_s nichts kommt."""
    import lgpio
    kanten = []
    zuletzt = [0.0]

    def kante(c, g, l, t):
        kanten.append((t, l)); zuletzt[0] = time.monotonic()
    h = lgpio.gpiochip_open(0)
    try:
        lgpio.gpio_claim_alert(h, GPIO, lgpio.BOTH_EDGES, lgpio.SET_PULL_UP)
        cb = lgpio.callback(h, GPIO, lgpio.BOTH_EDGES, kante)
        t_start = time.time()
        while not kanten:
            if time.time() - t_start > warte_s:
                raise TimeoutError('keine Daten vom CP1')
            time.sleep(0.05)
        letzte_zahl = -1
        while True:
            time.sleep(0.1)
            k = list(kanten)
            daten = bytes_aus_pulsen(lowpulse(k))
            n = rahmen_laenge(daten)
            if fortschritt and len(daten) != letzte_zahl:
                fortschritt(daten); letzte_zahl = len(daten)
            if n and len(daten) >= n:
                break
            if time.monotonic() - zuletzt[0] > still_s:
                break
        cb.cancel()
    finally:
        lgpio.gpiochip_close(h)
    return kanten


# ---------------------------------------------------------------- Kommandozeile

def zahl_opt(args, name):
    if name in args:
        i = args.index(name); v = int(args[i + 1]); del args[i:i + 2]; return v
    return None


def main(argv):
    args = [a for a in argv if a != '--schnell']
    if len(args) < 2 or args[0] not in ('send', 'recv') or not args[1].endswith('.json'):
        print(__doc__); return 1
    art, fn = args[0], args[1]
    if art == 'send':
        if os.geteuid() != 0 and '--ohne-sudo' not in args:
            # Echtzeit-Priorität braucht root: ohne sie werden Pulse auf dem Pi Zero bis 0,5 ms zu lang
            # (gemessen 2026-11-12), mit ihr höchstens ~80 µs.
            os.execvp('sudo', ['sudo', '-n', sys.executable, os.path.realpath(__file__), 'send'] + args[1:])
        args = [a for a in args if a != '--ohne-sudo']
        von, bis = zahl_opt(args, '--von'), zahl_opt(args, '--bis')
        zellen = json_lesen(fn)
        daten = rahmen_bauen(zellen, von, bis)
        print(f'{fn}: Zellen {daten[1]:03d}–{daten[2]:03d}, {len(daten)} Byte, ca. '
              f'{sum(l + h for l, h in pulsplan(daten)) / 1e6:.1f} s')
        input('Am CP1 CAL drücken (Anzeige: ⊔ = Eimer offen nach oben), dann hier Enter … ')
        ist = senden(daten)
        k = [d for d, (l, _) in zip(ist, pulsplan(daten)) if l == KURZ_US]
        g = [d for d, (l, _) in zip(ist, pulsplan(daten)) if l == LANG_US]
        print(f'gesendet. Pulse kurz {min(k):.0f}–{max(k):.0f} µs, lang {min(g):.0f}–{max(g):.0f} µs')
        if max(k) > 650 or min(g) < 1000:
            print('WARNUNG: Pulse gestört – zeigt der CP1 „C Su Err“, einfach nochmal senden (am besten mit sudo).')
        print('Am CP1 sollte jetzt „rdY“ stehen.')
        return 0
    print('Am CP1 CAS drücken (kurz = alles, 1 s halten = Bereich wählen). Warte auf Daten …')

    def fort(d):
        if len(d) >= 3:
            n = (len(d) - 3) // 2
            print(f'\r  Zelle {min(d[1] + n, d[2]):03d} ({len(d)} Byte)', end='', flush=True)
    kanten = empfangen(fortschritt=fort)
    print()
    pulse = lowpulse(kanten)
    daten = bytes_aus_pulsen(pulse)
    try:
        zellen = rahmen_lesen(daten)
    except ValueError as e:
        print(f'FEHLER: {e}')
        k = [p for p in pulse if p < SCHWELLE_US]; g = [p for p in pulse if p >= SCHWELLE_US]
        if k and g:
            print(f'  Pulse kurz {min(k):.0f}–{max(k):.0f} µs, lang {min(g):.0f}–{max(g):.0f} µs')
        return 1
    json_schreiben(fn, zellen)
    print(f'{fn}: Zellen {min(zellen):03d}–{max(zellen):03d} gespeichert, Prüfsumme ok.')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
