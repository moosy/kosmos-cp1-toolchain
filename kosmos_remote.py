#!/usr/bin/env python3
"""Fernsteuerung für den Kosmos CP1 (Firmware „schnell“, EEPROM-Bank JP3 = 1) über GPIO 26 <-> P1.7.

Am CP1 einmal RUN 1 s halten -> „rc on“. Dann:

  kosmos_remote.py serve [--port 8049]      Webseite + Schnittstelle (hält die Leitung)
  kosmos_remote.py anzeige                   Anzeige als Text
  kosmos_remote.py taste 0 0 0 pc run        Tasten drücken (Name[:ms], z. B. cas:1500)
  kosmos_remote.py laden datei.json          CAL drücken und senden
  kosmos_remote.py speichern datei.json [--von N --bis M]   CAS drücken und empfangen

Läuft der Server, gehen die übrigen Befehle über ihn (http://localhost:PORT), sonst direkt.

Protokoll (Pi -> CP1): Anklopfen = Leitung low; der Timer-Interrupt des CP1 zählt die Takte (2,56 ms)
und hält dafür nicht an. 3,5 ms = Statusabfrage: der CP1 schickt RAM 0x20..0x3A (Anzeige, Akku, PC,
Status). 8,5 ms = Befehl: der CP1 wartet aufs Loslassen; nach 300 µs kommen 4 Byte: je Bit Low-Puls,
150 µs high, LSB zuerst; Byte 4 = B1 ^ B2 ^ B3 ^ $A5. (Bit 1 = 150 µs, Bit 0 = 750 µs, Schwelle 460 µs.)
  01 zm dd   Taste: z = Tastaturzeile (2..6), m = Spaltenmaske, dd = Dauer in Bildern à 15,36 ms
  02 aa nn   nn Byte internes RAM ab aa lesen
Antwort nach 2,6 ms, JE INTERRUPT EIN BYTE (die Anzeige des CP1 läuft dabei weiter): die Daten,
dann ein Prüfbyte (XOR ^ $A5); Pulse ~43 µs = 1 / ~125 µs = 0. Auf 01 kommt nur $A5 als Quittung.
Senden und Messen macht das C-Hilfsprogramm kosmos_rc direkt an den GPIO-Registern (Python ist dafür
auf dem Pi Zero zu langsam); es läuft als Unterprozess mit Echtzeitpriorität.
Beide Seiten ziehen nur nach low (Open-Drain); der Pi lässt die Leitung sonst los.
"""
import json, os, sys, threading, time, subprocess, tempfile, math

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import kosmos_schnell as ks

GPIO = 26
PORT = 8049
KLOPF_US, NACH_KLOPF_US = 3500, 300   # > 2,56 ms Interrupt-Takt; ab 5,1 ms low schaltet der CP1 die Fernsteuerung ab
EINS_US, NULL_US, LUECKE_US = 150, 750, 150     # CP1-Schwelle 460 µs: ein unterbrochener Pi macht Pulse nur länger
SCHWELLE_US = 80                                 # Antwort CP1 -> Pi: ~43 / ~125 µs (misst kosmos_rc)
VERSUCHE = 4
BILD_MS = 15.36

# Tastencodes der Firmware: Ziffer d = d + 1, OUT 11, INP 12, CAL 13, STEP 14, STP 15, RUN 16, CAS 17, CLR 18, PC 19, ACC 20
CODES = {str(d): d + 1 for d in range(10)}
CODES.update(out=11, inp=12, cal=13, step=14, stp=15, run=16, cas=17, clr=18, pc=19, acc=20)

SEG = {0x3f: '0', 0x06: '1', 0x5b: '2', 0x4f: '3', 0x66: '4', 0x6d: '5', 0x7d: '6', 0x27: '7', 0x07: '7',
       0x7f: '8', 0x6f: '9', 0x77: 'A', 0x7c: 'b', 0x39: 'C', 0x58: 'c', 0x5e: 'd', 0x79: 'E', 0x71: 'F',
       0x3d: 'G', 0x76: 'H', 0x38: 'L', 0x54: 'n', 0x5c: 'o', 0x73: 'P', 0x50: 'r', 0x78: 't', 0x3e: 'U',
       0x1c: 'u', 0x6e: 'Y', 0x40: '-', 0x08: '_', 0x00: ' ', 0x23: '⊓', 0x63: '°', 0x53: '?'}


def taste_zm(name):
    k = CODES[name.lower()]
    zeile, bit = (k + 7) // 4, (k + 7) % 4
    return zeile << 4 | 1 << bit


def rahmen(cmd, a, b):
    return bytes([cmd, a, b, cmd ^ a ^ b ^ 0xA5])


def pulse_rahmen(daten):
    """-> [(low_us, high_us)] nach dem Anklopfen"""
    plan = []
    for byte in daten:
        for i in range(8):
            plan.append((EINS_US if byte >> i & 1 else NULL_US, LUECKE_US))
    return plan


def segtext(seg):
    out = ''
    for b in seg:
        out += SEG.get(b & 0x7f, '?') + ('.' if b & 0x80 else '')
    return out


class KeineAntwort(Exception):
    pass


class Leitung:
    """Hält GPIO 26: in Ruhe als Eingang mit Flankenmeldung, zum Senden kurz als Ausgang."""

    def __init__(self):
        import lgpio
        self.lg = lgpio
        self.h = lgpio.gpiochip_open(0)
        self.kanten = []
        self.lock = threading.Lock()
        self._eingang()
        rc = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'kosmos_rc')
        self.rc = subprocess.Popen([rc], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        self.rc_rt = self.rc.stdout.readline().split()[-1] == 'rt'
        if not self.rc_rt:
            print('Hinweis: kosmos_rc ohne Echtzeitpriorität – Fernsteuerung unzuverlässig', flush=True)
        self.cb = lgpio.callback(self.h, GPIO, lgpio.BOTH_EDGES, lambda c, g, l, t: self.kanten.append((t, l)))

    def _eingang(self):
        try:
            self.lg.gpio_free(self.h, GPIO)
        except Exception:
            pass
        self.lg.gpio_claim_alert(self.h, GPIO, self.lg.BOTH_EDGES, self.lg.SET_PULL_UP)

    def _ausgang(self):
        self.lg.gpio_free(self.h, GPIO)
        self.lg.gpio_claim_output(self.h, GPIO, 1)

    @staticmethod
    def _rt(an):
        try:
            if an:
                os.sched_setscheduler(0, os.SCHED_FIFO, os.sched_param(50))
            else:
                os.sched_setscheduler(0, os.SCHED_OTHER, os.sched_param(0))
            return True
        except (PermissionError, OSError, AttributeError):
            return False

    def _pulse(self, plan, vorlauf=None, schlaf_ok=False, abtasten=0):
        """plan: [(low_us, high_us)], vorlauf: (low_us, high_us) zum Anklopfen. -> gemessene Low-Längen"""
        import gc
        lg, h = self.lg, self.h
        ns = time.perf_counter_ns
        ist = []
        self._ausgang()
        rt = self._rt(True)
        gc.disable()
        try:
            for low, high in ([vorlauf] if vorlauf else []) + plan:
                lg.gpio_write(h, GPIO, 0)
                t0 = ns(); ende = t0 + low * 1000
                if low > 1500 and not schlaf_ok:      # Anklopfen nie verschlafen (CP1 hält > 5 ms low für Defekt)
                    pass
                elif low > 1500:
                    time.sleep((low - 1000) / 1e6)
                while ns() < ende: pass
                lg.gpio_write(h, GPIO, 1)
                t1 = ns(); ist.append((t1 - t0) / 1000)
                ende = t1 + high * 1000
                if high > 1500:
                    time.sleep((high - 1000) / 1e6)
                while ns() < ende: pass
            if abtasten:
                lg.gpio_free(h, GPIO)
                lg.gpio_claim_input(h, GPIO, lg.SET_PULL_UP)
                self.abgetastet = self._abtasten(abtasten)
        finally:
            gc.enable()
            if rt: self._rt(False)
            self._eingang()
        return ist

    def _abtasten(self, bits):
        """Antwort des CP1 durch Pegelabfrage messen (Flankenmeldungen gehen auf dem Pi Zero verloren).
        -> Low-Längen in µs"""
        lg, h = self.lg, self.h
        ns = time.perf_counter_ns
        ende = ns() + int((0.012 + bits * 0.0008) * 1e9)     # Bytes kommen je Interrupt, mit Pausen
        lows = []; alt = 1; t_low = 0
        while ns() < ende and len(lows) < bits:
            v = lg.gpio_read(h, GPIO)
            if v != alt:
                t = ns()
                if v == 0: t_low = t
                else: lows.append((t - t_low) / 1000)
                alt = v
        return lows

    # ------------------------------------------------ Fernsteuerung
    def befehl(self, cmd, a, b, antwort=0):
        """ein Versuch; -> antwort Datenbyte (Prüfbyte wird geprüft)"""
        with self.lock:
            bits = (antwort + 1) * 8
            lows = self._rc(rahmen(cmd, a, b).hex(), bits)
            if len(lows) < bits:
                raise KeineAntwort(f'{len(lows)} von {bits} Bits – ist am CP1 „rc on“ (RUN 1 s halten)?')
            werte = [1 if p < SCHWELLE_US else 0 for p in lows[:bits]]
            daten = [sum(b << i for i, b in enumerate(werte[j:j + 8])) for j in range(0, bits, 8)]
            chk = 0xA5
            for d in daten[:-1]: chk ^= d
            if chk != daten[-1]:
                raise KeineAntwort('Prüfbyte falsch')
            return bytes(daten[:-1])

    def _lows(self):
        k = list(self.kanten); out = []
        for (t1, l1), (t2, l2) in zip(k, k[1:]):
            if l1 == 0 and l2 == 1:
                out.append((t2 - t1) / 1000)
        return out

    def status(self):
        """nur Anklopfen -> RAM 0x20..0x3A, ohne die Anzeige zu stören"""
        for v in range(VERSUCHE):
            with self.lock:
                bits = 28 * 8
                daten = self._dekodieren(self._rc('-', bits), bits)
            if daten is not None:
                return daten
            time.sleep(0.02)
        raise KeineAntwort('keine Statusantwort – ist am CP1 „rc on“ (RUN 1 s halten)?')

    def _rc(self, auftrag, bits):
        self.rc.stdin.write(f'{auftrag} {bits}\n')
        return [int(x) for x in self.rc.stdout.readline().split()[1:]]

    @staticmethod
    def _dekodieren(lows, bits):
        if len(lows) < bits: return None
        werte = [1 if p < SCHWELLE_US else 0 for p in lows[:bits]]
        daten = [sum(b << i for i, b in enumerate(werte[j:j + 8])) for j in range(0, bits, 8)]
        chk = 0xA5
        for d in daten[:-1]: chk ^= d
        return bytes(daten[:-1]) if chk == daten[-1] else None

    def ram(self, adr, n):
        for v in range(VERSUCHE):
            try:
                return self.befehl(2, adr, n, antwort=n)
            except KeineAntwort:
                if v == VERSUCHE - 1: raise
                time.sleep(0.02)

    def anzeige(self):
        r = self.status()
        seg = r[0:6]
        return {'seg': list(seg), 'text': segtext(seg), 'akku': r[0x16] << 8 | r[0x17], 'pc': r[0x18], 'status': r[0x1a]}

    def taste(self, name, ms=100):
        bilder = max(2, min(255, math.ceil(ms / BILD_MS)))
        t0 = time.monotonic()
        for v in range(VERSUCHE):
            try:
                self.befehl(1, taste_zm(name), bilder)
                break
            except KeineAntwort:
                # Quittung verloren? Wenn die Ferntaste schon läuft, nicht nochmal drücken (sonst doppelt)
                try:
                    if self.befehl(2, 0x7a, 1, antwort=1)[0]:
                        break
                except KeineAntwort:
                    pass
                if v == VERSUCHE - 1: raise
                t0 = time.monotonic()
        rest = bilder * BILD_MS / 1000 + 0.06 - (time.monotonic() - t0)   # gehalten + loslassen sehen
        if rest > 0: time.sleep(rest)

    def tasten(self, folge):
        """folge: ['1', '2', 'pc', 'cas:1500']"""
        for t in folge:
            name, _, ms = t.partition(':')
            self.taste(name, int(ms) if ms else 100)

    # ------------------------------------------------ Kassette aus der Ferne
    def laden(self, zellen, von=None, bis=None):
        daten = ks.rahmen_bauen(zellen, von, bis)
        self.taste('cal')
        time.sleep(0.3)
        with self.lock:
            ist = self._pulse(ks.pulsplan(daten), schlaf_ok=True)
        return {'von': daten[1], 'bis': daten[2], 'bytes': len(daten),
                'kurz': [round(min(ist)), round(max(i for i in ist if i < 800))]}

    def speichern(self, von=None, bis=None, warte_s=40):
        if von is None:
            self.taste('cas')
        else:
            self.taste('cas', 1300)
            time.sleep(0.3)
            self.tasten(list(f'{von:03d}') + ['cas'] + list(f'{bis:03d}'))
            self.kanten.clear()
            self.taste('cas')
        with self.lock:
            self.kanten.clear()
            frist = time.monotonic() + warte_s
            while not self.kanten and time.monotonic() < frist:
                time.sleep(0.05)
            if not self.kanten:
                raise KeineAntwort('CP1 sendet nicht')
            letzte = (len(self.kanten), time.monotonic())
            while True:
                time.sleep(0.1)
                daten = ks.bytes_aus_pulsen(ks.lowpulse(list(self.kanten)))
                n = ks.rahmen_laenge(daten)
                if n and len(daten) >= n: break
                if len(self.kanten) != letzte[0]:
                    letzte = (len(self.kanten), time.monotonic())
                elif time.monotonic() - letzte[1] > 1.0:
                    break
        return ks.rahmen_lesen(daten)


# ---------------------------------------------------------------- Server

def disasm(zellen):
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
        json.dump({f'{n:03d}': list(v) for n, v in sorted(zellen.items())}, f)
    try:
        return subprocess.run(['php', os.path.join(os.path.dirname(os.path.realpath(__file__)), 'kosmos_disasm.php'), f.name],
                              capture_output=True, text=True, timeout=20).stdout
    finally:
        os.unlink(f.name)


def asm(quelltext):
    d = tempfile.mkdtemp()
    src = os.path.join(d, 'prog.koa')
    open(src, 'w').write(quelltext)
    r = subprocess.run(['php', os.path.join(os.path.dirname(os.path.realpath(__file__)), 'kosmos_asm.php'), '-o', src],
                       capture_output=True, text=True, timeout=20, cwd=d)
    js = [os.path.join(d, n) for n in os.listdir(d) if n.endswith('.json')]
    if not js:
        raise ValueError((r.stdout + r.stderr).strip() or 'Assembler lieferte nichts')
    return {int(k): tuple(v) for k, v in json.load(open(js[0])).items()}, r.stdout


def serve(port):
    from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
    leitung = Leitung()
    seite = open(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'kosmos_remote.html'), 'rb').read()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass

        def antwort(self, code, obj, typ='application/json'):
            body = obj if isinstance(obj, bytes) else json.dumps(obj).encode()
            self.send_response(code)
            self.send_header('Content-Type', typ + ('; charset=utf-8' if 'text' in typ or 'json' in typ else ''))
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            try:
                pfad, _, query = self.path.partition('?')
                if pfad in ('/', '/index.html'):
                    return self.antwort(200, seite, 'text/html')
                if pfad == '/api/anzeige':
                    return self.antwort(200, leitung.anzeige())
                return self.antwort(404, {'fehler': 'unbekannt'})
            except KeineAntwort as e:
                return self.antwort(503, {'fehler': str(e)})

        def do_POST(self):
            try:
                n = int(self.headers.get('Content-Length', 0))
                req = json.loads(self.rfile.read(n) or b'{}')
                if self.path == '/api/taste':
                    leitung.tasten(req['tasten'])
                    return self.antwort(200, {'ok': True})
                if self.path == '/api/laden':
                    if 'quelltext' in req:
                        zellen, meldung = asm(req['quelltext'])
                        belegt = [n for n, v in zellen.items() if v != (0, 0)]   # der Assembler liefert alle 256 Zellen
                        zellen = {n: v for n, v in zellen.items() if n <= max(belegt or [0])}
                    else:
                        zellen = {int(k): tuple(v) for k, v in req['zellen'].items()}
                    voll = {i: zellen.get(i, (0, 0)) for i in range(min(zellen), max(zellen) + 1)}
                    r = leitung.laden(voll)
                    return self.antwort(200, r)
                if self.path == '/api/speichern':
                    z = leitung.speichern(req.get('von'), req.get('bis'))
                    return self.antwort(200, {'zellen': {f'{k:03d}': list(v) for k, v in sorted(z.items())},
                                              'listing': disasm(z)})
                if self.path == '/api/ram':
                    return self.antwort(200, {'daten': list(leitung.ram(int(req['adr']), int(req['n'])))})
                return self.antwort(404, {'fehler': 'unbekannt'})
            except KeineAntwort as e:
                return self.antwort(503, {'fehler': str(e)})
            except (ValueError, KeyError) as e:
                return self.antwort(400, {'fehler': str(e)})

    srv = ThreadingHTTPServer(('', port), H)
    print(f'Kosmos-Fernsteuerung auf http://{os.uname().nodename}:{port}/', flush=True)
    srv.serve_forever()


def ueber_server(pfad, obj=None, port=PORT, timeout=120):
    import urllib.request
    url = f'http://127.0.0.1:{port}{pfad}'
    data = None if obj is None else json.dumps(obj).encode()
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def server_laeuft(port=PORT):
    import socket
    s = socket.socket(); s.settimeout(0.3)
    try:
        s.connect(('127.0.0.1', port)); return True
    except OSError:
        return False
    finally:
        s.close()


def main(argv):
    if not argv:
        print(__doc__); return 1
    port = int(argv[argv.index('--port') + 1]) if '--port' in argv else PORT
    cmd, rest = argv[0], [a for a in argv[1:] if a != '--port' and a != str(port)]
    if cmd == 'serve':
        serve(port); return 0
    srv = server_laeuft(port)
    if cmd == 'anzeige':
        a = ueber_server('/api/anzeige', port=port) if srv else Leitung().anzeige()
        print(a['text']); return 0
    if cmd == 'taste':
        if srv: ueber_server('/api/taste', {'tasten': rest}, port=port)
        else: Leitung().tasten(rest)
        return 0
    if cmd == 'laden':
        z = ks.json_lesen(rest[0])
        if srv:
            r = ueber_server('/api/laden', {'zellen': {f'{k:03d}': list(v) for k, v in z.items()}}, port=port)
        else:
            r = Leitung().laden({i: z.get(i, (0, 0)) for i in range(min(z), max(z) + 1)})
        print(f"geladen: Zellen {r['von']:03d}–{r['bis']:03d}"); return 0
    if cmd == 'speichern':
        von = int(rest[rest.index('--von') + 1]) if '--von' in rest else None
        bis = int(rest[rest.index('--bis') + 1]) if '--bis' in rest else None
        if srv:
            r = ueber_server('/api/speichern', {'von': von, 'bis': bis}, port=port)
            z = {int(k): tuple(v) for k, v in r['zellen'].items()}
        else:
            z = Leitung().speichern(von, bis)
        ks.json_schreiben(rest[0], z)
        print(f'{rest[0]}: Zellen {min(z):03d}–{max(z):03d} gespeichert.'); return 0
    print(__doc__); return 1


if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv[1:]))
    except KeineAntwort as e:
        print('Keine Antwort vom CP1:', e); sys.exit(2)
