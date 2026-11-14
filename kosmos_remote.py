#!/usr/bin/env python3
"""Fernsteuerung für den Kosmos CP1, Firmware 5.03: GPIO 26 <-> P1.7 (Klemme 8), GPIO 19 <-> P1.6 (Klemme 7).

Die Fernsteuerung ist immer an. Befehle:

  kosmos_remote.py serve [--port 8049]      Webseite + Schnittstelle (hält die Leitungen)
  kosmos_remote.py anzeige                   Anzeige als Text
  kosmos_remote.py taste 0 0 0 pc run        Tasten drücken (Name[:ms], z. B. cas:1500)
  kosmos_remote.py reset                     Kaltstart wie Einschalten: alles RAM weg (Firmware 5.02)
  kosmos_remote.py laden datei.json          Zellen ins RAM des CP1 (FNI, ~1 s)
  kosmos_remote.py speichern datei.json [--von N --bis M]   RAM des CP1 in eine Datei (FNI)
  kosmos_remote.py zelle N [B A]             Zelle N lesen bzw. auf B.A setzen (auch bei laufendem Programm)
  kosmos_remote.py flash                     Flash-Verzeichnis (Bank, Start, Name, Autoboot)
  kosmos_remote.py flash-speichern 12 "Rakete" [--start 20]   RAM des CP1 nach Bank 12
  kosmos_remote.py flash-laden 12            Bank 12 ins RAM, PC = Start
  kosmos_remote.py autoboot 12               beim Einschalten Bank 12 starten (0 = aus)
  kosmos_remote.py bank-sichern 12 datei.json            Bank 12 direkt in eine Datei (RAM bleibt; Namen -> datei.json.namen)
  kosmos_remote.py bank-einspielen 12 datei.json ["Name"] [--start 20] [--namen datei.namen]   Datei direkt in Bank 12
                                             (--namen: Zuweisungstabelle „035=name“ mit in die Bank, Firmware 5.03)

Läuft der Server, gehen die übrigen Befehle über ihn (http://localhost:PORT), sonst direkt.

Zwei Übertragungsarten (die Bits macht das C-Hilfsprogramm kosmos_rc direkt an den GPIO-Registern):
NIE (im Interrupt des CP1, unbemerkt): Anklopfen = Klemme 8 low. 3,5 ms = Statusabfrage (RAM 0x20..0x3A);
  8,5 ms = Befehl: 4 Byte, je Bit Low 50 µs = 1 / 150 µs = 0, danach 50 µs high, LSB zuerst;
  Byte 4 = B1 ^ B2 ^ B3 ^ $A5. Antwort je Interrupt-Takt ein Byte, Pulse ~50/~150 µs, dann Prüfbyte.
  01 zm dd Taste · 02 aa nn RAM lesen · 03 aa ww RAM schreiben · 04 jj 00 Auftrag starten (nur im Leerlauf)
  05/06 aa nn  nn Byte ab Byte aa der internen / CP3-8155 · 07/08 aa ww  Byte aa = ww  (Zelle z: Byte 2z, 2z+1)
  09 00 00  Reset wie Einschalten (5.02, keine Antwort)
FNI (Interrupt des CP1 aus, sichtbar „Q-Z“): getaktet über Klemme 7, Daten auf Klemme 8, Blöcke mit CRC.
  Aufträge: $20 Pi -> 8155, $21 8155 -> Pi, $22/$23 Pi -> Flash (mit Name), $24 Flash -> Pi,
  $25 Bank komplett -> Pi (Zellen + 0x200..0x5FF: Name, Generation, gültig, Namensbereich), $26 alle Namen -> Pi,
  $29 Pi -> Flash mit Name und Namensbereich 0x300..0x5FF (5.03; $01 und $10 entfallen).
  Parameter: F_BANK 0x2C, F_ANF 0x3C, F_ANZ 0x3D (0 = 256), F_START 0x3E, Name 0x60..0x6F; fertig: F_JOB 0 / $EE.
Weitere Aufträge (Interrupt an): $04 Bank laden, $08 Autoboot, $80/$81 RAM -> Bank (mit Name). Aufträge gehen nur, wenn der CP1 auf Tasten wartet.
"""
import json, os, re, sys, threading, time, subprocess, tempfile, math

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import kosmos_schnell as ks          # (nur noch die JSON-Hilfen)

GPIO = 26
PORT = 8049
SCHWELLE_US = 100                                # Antwort CP1 -> Pi: ~50 / ~150 µs (misst kosmos_rc)
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


def segtext(seg):
    out = ''
    for b in seg:
        out += SEG.get(b & 0x7f, '?') + ('.' if b & 0x80 else '')
    return out


F_JOB, F_BANK, F_SEKT, F_OFH, F_OFL, F_NAME = 0x26, 0x2c, 0x2d, 0x2e, 0x2f, 0x60
F_ANF, F_ANZ, F_START, MEM_SIZE = 0x3c, 0x3d, 0x3e, 0x3b


def name_text(b):
    if all(x == 0xFF for x in b): return ''
    return bytes(x if 32 <= x < 127 else 63 for x in b).decode('ascii').rstrip()


class FlashFehler(Exception):
    pass


class KeineAntwort(Exception):
    pass


class Leitung:
    """Hält die Leitungen über kosmos_rc (D = GPIO 26, T = GPIO 19); der Lock gilt für ganze Abläufe."""

    def __init__(self):
        self.lock = threading.RLock()
        rc = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'kosmos_rc')
        self.rc = subprocess.Popen([rc], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        self.rc_rt = self.rc.stdout.readline().split()[-1] == 'rt'
        if not self.rc_rt:
            print('Hinweis: kosmos_rc ohne Echtzeitpriorität – Übertragung unzuverlässig', flush=True)

    # ------------------------------------------------ Fernsteuerung
    def befehl(self, cmd, a, b, antwort=0):
        """ein Versuch; -> antwort Datenbyte (Prüfbyte wird geprüft)"""
        with self.lock:
            bits = (antwort + 1) * 8
            lows = self._rc(rahmen(cmd, a, b).hex(), bits)
            if len(lows) < bits:
                raise KeineAntwort(f'{len(lows)} von {bits} Bits – läuft der CP1 mit Firmware 5.00?')
            werte = [1 if p < SCHWELLE_US else 0 for p in lows[:bits]]
            daten = [sum(b << i for i, b in enumerate(werte[j:j + 8])) for j in range(0, bits, 8)]
            chk = 0xA5
            for d in daten[:-1]: chk ^= d
            if chk != daten[-1]:
                raise KeineAntwort('Prüfbyte falsch')
            return bytes(daten[:-1])

    def status(self):
        """nur Anklopfen -> RAM 0x20..0x3A, ohne die Anzeige zu stören"""
        for v in range(VERSUCHE):
            with self.lock:
                bits = 28 * 8
                daten = self._dekodieren(self._rc('-', bits), bits)
            if daten is not None:
                return daten
            time.sleep(0.02)
        raise KeineAntwort('keine Statusantwort – ist der CP1 an (Firmware 5.00)?')

    def _fni_zeile(self, zeile):
        self.rc.stdin.write(zeile + '\n')
        return self.rc.stdout.readline().split()

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

    def reset(self):
        """NIE 09 (Firmware 5.02): Kaltstart wie beim Einschalten, alles RAM weg, danach Version und Autoboot.
        Geprüft an der Versionsanzeige („5.“ in Stelle 3); -> Anzeige-Text"""
        with self.lock:
            for v in range(VERSUCHE):
                self._rc(rahmen(9, 0, 0).hex(), 0)
                time.sleep(0.3)
                try:
                    a = self.anzeige()
                except KeineAntwort:
                    continue
                if a['seg'][2] & 0x7F == 0x6D and a['seg'][1] == 0 and a['seg'][0] == 0:
                    return a['text']
            raise KeineAntwort('kein Reset erkannt – Firmware ab 5.02?')

    def tasten(self, folge):
        """folge: ['1', '2', 'pc', 'cas:1500']"""
        for t in folge:
            name, _, ms = t.partition(':')
            self.taste(name, int(ms) if ms else 100)

    # ------------------------------------------------ Flash (Firmware 4.01)
    def schreib(self, adr, wert):
        """Befehl 03: ein Byte ins interne RAM des CP1 (Quittung = nur Prüfbyte)"""
        for v in range(VERSUCHE):
            try:
                self.befehl(3, adr, wert); return
            except KeineAntwort:
                if v == VERSUCHE - 1: raise
                time.sleep(0.02)

    def auftrag(self, job, werte=None, frist_s=8):
        """Parameter mit 03 schreiben, Auftrag mit 04 starten, warten bis F_JOB wieder 0 ist."""
        with self.lock:
            return self._auftrag(job, werte, frist_s)

    def _starten(self, job, werte):
        for adr, w in (werte or {}).items():
            self.schreib(adr, w)
        for v in range(VERSUCHE):
            try:
                r = self.befehl(4, job, 0, antwort=1)[0]
                break
            except KeineAntwort:
                if v == VERSUCHE - 1: raise
                time.sleep(0.05)
                if self.ram(F_JOB, 1)[0] == job: return     # Antwort verloren, Auftrag aber angenommen
        if r != job:
            raise FlashFehler('der CP1 nimmt keinen Auftrag an – läuft gerade ein Programm oder eine Eingabe? (erst STP)')

    def _auftrag(self, job, werte, frist_s):
        self._starten(job, werte)
        ende = time.monotonic() + frist_s
        while time.monotonic() < ende:
            time.sleep(0.15)
            try:
                if self.ram(F_JOB, 1)[0] == 0: break
            except KeineAntwort:
                pass
        else:
            raise FlashFehler('Auftrag nicht fertig geworden')
        text = self.anzeige()['text']
        if text.startswith('F'):
            nr = int(text[-3:]) if text[-3:].isdigit() else 0
            raise FlashFehler({10: 'F-010: kein Flash gefunden', 11: 'F-011: Bank ist leer',
                               3: 'F-003: Bank/Bereich ungültig', 1: 'F-001'}.get(nr, f'Fehler {text}'))

    # ------------------------------------------------ FNI (Interrupt des CP1 aus, getaktet)
    def fni(self, job, anf, anz, bank=0, daten=b'', start=255, name=None, versuche=3):
        """Großer Block: job $20..$26. anz = Zellen (256 -> 0). -> empfangene Bytes (2 je Zelle, bei $25 + Bankkopf,
        bei $26 je Bank 18 Byte: Bank, 0, Name)"""
        n = anz & 0xFF
        werte = {F_BANK: bank, F_ANF: anf & 0xFF, F_ANZ: n, F_START: start & 0xFF}
        if name is not None:
            werte.update({F_NAME + i: c for i, c in enumerate(name.encode('latin-1', 'replace')[:16].ljust(16, b' '))})
        richtung = {0x20: 'E', 0x22: 'E', 0x23: 'E', 0x29: 'E', 0x25: 'K', 0x26: 'N'}.get(job, 'A')
        kopf = bytes([job, bank, anf & 0xFF, n]).hex()
        letzter = ''
        with self.lock:
            for v in range(versuche):
                self.schreib(F_JOB, 0)                          # alter Stand ($EE) darf nicht als Ablehnung gelten
                for adr, w in werte.items():
                    self.schreib(adr, w)
                self._rc(rahmen(4, job, 0).hex(), 0)            # Attention; die Annahme ist „T geht low“
                antwort = self._fni_zeile(f'F {richtung} {anf & 0xFF} {n} {kopf} {daten.hex() if richtung == "E" else ""}')
                time.sleep(0.05)
                job_jetzt = None
                for _ in range(20):
                    try:
                        job_jetzt = self.ram(F_JOB, 1)[0]
                        if job_jetzt in (0, 0xEE): break        # antwortet erst wieder, wenn der CP1 FNI verlassen hat
                    except KeineAntwort:
                        pass
                    time.sleep(0.1)
                if antwort[:1] == ['OK'] and job_jetzt == 0:
                    return bytes.fromhex(antwort[1]) if len(antwort) > 1 else b''
                letzter = ' '.join(antwort[1:]) or '?'
                if letzter == 'nicht_angenommen' and job_jetzt not in (job, 0xEE):
                    raise FlashFehler('der CP1 nimmt keinen Auftrag an – läuft gerade ein Programm oder eine Eingabe? (erst STP)')
                if letzter == 'nicht_angenommen' and job_jetzt == 0xEE:
                    raise FlashFehler('der CP1 lehnt ab: Bereich/Bank ungültig oder kein Flash')
                time.sleep(0.3)
        raise KeineAntwort(f'FNI fehlgeschlagen ({letzter})')

    def zellen_lesen(self, von, anzahl):
        """NIE 05/06: Zellen lesen, auch während ein Programm läuft -> {n: (befehl, argument)}"""
        out = {}
        n = von
        while n < von + anzahl:
            chip, basis = (6, 128) if n >= 128 else (5, 0)
            k = min(von + anzahl, basis + 128, n + 32) - n
            for v in range(VERSUCHE):
                try:
                    d = self.befehl(chip, 2 * (n - basis), 2 * k, antwort=2 * k); break
                except KeineAntwort:
                    if v == VERSUCHE - 1: raise
            for i in range(k): out[n + i] = (d[2 * i], d[2 * i + 1])
            n += k
        return out

    def zelle_schreiben(self, n, befehl_, argument):
        """NIE 07/08: Zelle n = befehl.argument (auch während ein Programm läuft)"""
        chip, basis = (8, 128) if n >= 128 else (7, 0)
        for adr, w in ((2 * (n - basis), befehl_), (2 * (n - basis) + 1, argument)):
            for v in range(VERSUCHE):
                try:
                    self.befehl(chip, adr, w & 0xFF); break
                except KeineAntwort:
                    if v == VERSUCHE - 1: raise

    def flash_verzeichnis(self):
        """-> {'autoboot': n, 'baenke': [{'bank', 'name', 'start'}]}: Bank 0 per FNI + alle Namen per FNI"""
        with self.lock:
            verz = self.fni(0x24, 0, 0, bank=0)           # Bank 0: Zelle 0 = Autoboot, Zelle n = Start von Bank n
            namen = self.fni(0x26, 0, 0)
        baenke = []
        for i in range(0, len(namen), 18):
            b = namen[i]
            baenke.append({'bank': b, 'name': name_text(namen[i + 2:i + 18]), 'start': verz[2 * b + 1]})
        return {'autoboot': verz[1], 'baenke': baenke}

    def flash_speichern(self, bank, name='', start=None):
        werte = {F_NAME + i: c for i, c in enumerate(name.encode('latin-1', 'replace')[:16].ljust(16, b' '))}
        if start is not None: werte[0x38] = start          # PC = Startadresse
        werte[F_BANK] = bank
        self.auftrag(0x81, werte, frist_s=10)

    def flash_laden(self, bank):
        self.auftrag(0x04, {F_BANK: bank})

    def flash_autoboot(self, bank):
        self.auftrag(0x08, {F_BANK: bank}, frist_s=10)

    # ------------------------------------------------ Programm-RAM und Bänke über FNI
    @staticmethod
    def _bytes(zellen, von, bis):
        return b''.join(bytes(zellen.get(i, (0, 0))) for i in range(von, bis + 1))

    @staticmethod
    def _zellen(daten, von):
        return {von + i: (daten[2 * i], daten[2 * i + 1]) for i in range(len(daten) // 2)}

    def laden(self, zellen, von=None, bis=None):
        """Zellen ins RAM des CP1 (FNI $20); Lücken = 00.000"""
        von = min(zellen) if von is None else von
        bis = max(zellen) if bis is None else bis
        self.fni(0x20, von, bis - von + 1, daten=self._bytes(zellen, von, bis))
        return {'von': von, 'bis': bis, 'bytes': 2 * (bis - von + 1)}

    def speichern(self, von=None, bis=None):
        """RAM des CP1 lesen (FNI $21) -> {n: (befehl, argument)}"""
        with self.lock:
            if von is None: von = 0
            if bis is None: bis = self.ram(MEM_SIZE, 1)[0]
            return self._zellen(self.fni(0x21, von, bis - von + 1), von)

    def bank_komplett(self, bank):
        """Ganze Bank direkt aus dem Flash ($25, RAM bleibt): 256 Zellen, dahinter 0x200..0x5FF.
        -> {'zellen', 'name', 'namen'}; namen nur, wenn Byte 0x212 = 00 (5.03, Namensbereich ab 0x300)"""
        d = self.fni(0x25, 0, 0, bank=bank)
        meta = d[512:]
        namen = namen_aus_bytes(meta[0x100:0x400]) if len(meta) >= 0x400 and meta[0x12] == 0 else {}
        return {'zellen': self._zellen(d[:512], 0), 'name': name_text(meta[:16]), 'namen': namen}

    def bank_sichern(self, bank, von=0, bis=255):
        """Bank direkt aus dem Flash; das RAM des CP1 bleibt unberührt. Ganze Bank: Komplettdump ($25) mit Name.
        -> (zellen, name)"""
        if (von, bis) == (0, 255):
            k = self.bank_komplett(bank)
            return k['zellen'], k['name']
        return self._zellen(self.fni(0x24, von, bis - von + 1, bank=bank), von), None

    def bank_einspielen(self, bank, zellen, name=None, start=None, namen=None):
        """Zellen direkt in eine Bank (FNI $22/$23); Rest der Bank bleibt; start != None -> Verzeichnis.
        namen (dict, auch leer) -> $29 (5.03): Namensbereich 0x300..0x5FF wird mitgeschrieben (Name dann Pflicht)"""
        if not 1 <= bank <= 255: raise ValueError('Bank 1..255')
        von, bis = min(zellen), max(zellen)
        daten = self._bytes(zellen, von, bis)
        if namen is not None:
            job, daten, name = 0x29, daten + namen_bytes(namen), (name or '')
        else:
            job = 0x23 if name is not None else 0x22
        self.fni(job, von, bis - von + 1, bank=bank, daten=daten, start=255 if start is None else start, name=name)
        return {'bank': bank, 'von': von, 'bis': bis}


NAME_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


def namen_lesen(text):
    """Zuweisungstabelle „035=display_loop“ (eine je Zeile) -> {035: 'display_loop'}; Unpassendes wird übergangen"""
    out = {}
    for z in (text or '').splitlines():
        m = re.match(r'^\s*(\d{1,3})\s*=\s*(\S+)\s*$', z)
        if m and int(m.group(1)) <= 255 and NAME_RE.match(m.group(2)):
            out[int(m.group(1))] = m.group(2)
    return out


NAMEN_PLATZ = 0x300                       # 5.03: Namensbereich 0x300..0x5FF jedes Bank-Sektors


def namen_bytes(namen):
    """{adresse: name} -> 768 Byte: je Eintrag Länge, Adresse, Name (ASCII); Rest FF (Länge FF = Ende)"""
    out = bytearray()
    for a, n in sorted(namen.items()):
        b = n.encode('ascii')[:63]
        if len(out) + 2 + len(b) > NAMEN_PLATZ - 1:
            raise ValueError(f'Namensbereich voll ({NAMEN_PLATZ} Byte) – ab {a:03d}={n} passt nichts mehr')
        out += bytes([len(b), a & 0xFF]) + b
    return bytes(out) + b'\xff' * (NAMEN_PLATZ - len(out))


def namen_aus_bytes(d):
    namen, i = {}, 0
    while i + 2 <= len(d) and 1 <= d[i] <= 63:
        n, a = d[i], d[i + 1]
        try:
            name = bytes(d[i + 2:i + 2 + n]).decode('ascii')
        except UnicodeDecodeError:
            break
        if NAME_RE.match(name): namen[a] = name
        i += 2 + n
    return namen


def namen_text(namen):
    return ''.join(f'{a:03d}={n}\n' for a, n in sorted(namen.items()))


def _php(name):
    return os.path.join(os.path.dirname(os.path.realpath(__file__)), name)


def disasm(zellen, namen=None):
    """Listing; namen {adresse: name} ersetzen label_N/wert_N"""
    d = tempfile.mkdtemp()
    try:
        js = os.path.join(d, 'prog.json')
        json.dump({f'{n:03d}': list(v) for n, v in sorted(zellen.items())}, open(js, 'w'))
        args = ['php', _php('kosmos_disasm.php')]
        if namen:
            open(os.path.join(d, 'namen.txt'), 'w').write(namen_text(namen))
            args += ['-n', os.path.join(d, 'namen.txt')]
        return subprocess.run(args + [js], capture_output=True, text=True, timeout=20).stdout
    finally:
        subprocess.run(['rm', '-rf', d])


def asm(quelltext):
    """-> (zellen 0..255, Ausgabe des Assemblers mit aktuellen Zeilennummern an den Marken)"""
    d = tempfile.mkdtemp()
    try:
        src = os.path.join(d, 'prog.koa')
        open(src, 'w').write(quelltext)
        r = subprocess.run(['php', _php('kosmos_asm.php'), '-o', src], capture_output=True, text=True, timeout=20, cwd=d)
        js = [os.path.join(d, n) for n in os.listdir(d) if n.endswith('.json')]
        if not js:
            raise ValueError((r.stdout + r.stderr).strip() or 'Assembler lieferte nichts')
        return {int(k): tuple(v) for k, v in json.load(open(js[0])).items()}, r.stdout
    finally:
        subprocess.run(['rm', '-rf', d])


MARKE_RE = re.compile(r'^(\s*)>([^\s:]+):.*$')


def assemblieren(quelltext, namen_alt=''):
    """Assemblieren + Relabel: Zeilennummern in den Markenzeilen des Quelltexts auf die echten Adressen setzen
    (sonst bleibt der Text, wie er ist). Zuweisungstabelle = Marken des Quelltexts + Einträge von Hand, deren
    Name keine Marke ist. -> dict(zellen, quelltext, namen, von, bis)"""
    zellen, ausgabe = asm(quelltext)
    marken = {}
    for z in ausgabe.splitlines():
        m = re.match(r'^>([^\s:]+):\s+(\d{3})\s*$', z)
        if m: marken[m.group(1)] = int(m.group(2))
    zeilen = []
    for z in quelltext.split('\n'):
        m = MARKE_RE.match(z)
        if m and m.group(2) in marken:
            z = m.group(1) + f'>{m.group(2)}:'.ljust(28) + f'{marken[m.group(2)]:03d}'
        zeilen.append(z)
    namen = {a: n for n, a in marken.items() if NAME_RE.match(n)}
    for a, n in namen_lesen(namen_alt).items():
        if n not in marken and a not in namen:
            namen[a] = n
    belegt = [n for n, v in zellen.items() if v != (0, 0)]
    return {'zellen': zellen, 'quelltext': '\n'.join(zeilen), 'namen': namen,
            'von': 0, 'bis': max(belegt or [0])}


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
                if pfad == '/api/flash':
                    return self.antwort(200, leitung.flash_verzeichnis())
                return self.antwort(404, {'fehler': 'unbekannt'})
            except (KeineAntwort, FlashFehler) as e:
                return self.antwort(503, {'fehler': str(e)})

        def do_POST(self):
            try:
                n = int(self.headers.get('Content-Length', 0))
                req = json.loads(self.rfile.read(n) or b'{}')
                if self.path == '/api/taste':
                    leitung.tasten(req['tasten'])
                    return self.antwort(200, {'ok': True})
                if self.path == '/api/assemblieren':
                    r = assemblieren(req['quelltext'], req.get('namen', ''))
                    return self.antwort(200, {'quelltext': r['quelltext'], 'namen': namen_text(r['namen']),
                                              'zellen': {f'{k:03d}': list(v) for k, v in sorted(r['zellen'].items())},
                                              'bis': r['bis']})
                if self.path == '/api/disasm':
                    z = {int(k): tuple(v) for k, v in req['zellen'].items()}
                    return self.antwort(200, {'listing': disasm(z, namen_lesen(req.get('namen', '')))})
                if self.path == '/api/laden':
                    if 'quelltext' in req:
                        r = assemblieren(req['quelltext'], req.get('namen', ''))
                        zellen = {n: v for n, v in r['zellen'].items() if n <= r['bis']}   # bis zur letzten belegten Zelle
                    else:
                        zellen = {int(k): tuple(v) for k, v in req['zellen'].items()}
                    voll = {i: zellen.get(i, (0, 0)) for i in range(min(zellen), max(zellen) + 1)}
                    r = leitung.laden(voll)
                    return self.antwort(200, r)
                if self.path == '/api/speichern':
                    z = leitung.speichern(req.get('von'), req.get('bis'))
                    return self.antwort(200, {'zellen': {f'{k:03d}': list(v) for k, v in sorted(z.items())},
                                              'listing': disasm(z, namen_lesen(req.get('namen', '')))})
                if self.path == '/api/flash/speichern':
                    b = int(req['bank'])
                    if not 1 <= b <= 255: raise ValueError('Bank 1..255')
                    st = req.get('start')
                    leitung.flash_speichern(b, req.get('name', ''), None if st in (None, '') else int(st) & 255)
                    return self.antwort(200, {'ok': True})
                if self.path == '/api/flash/laden':
                    leitung.flash_laden(int(req['bank']))
                    return self.antwort(200, {'ok': True})
                if self.path == '/api/flash/autoboot':
                    leitung.flash_autoboot(int(req['bank']) & 255)
                    return self.antwort(200, {'ok': True})
                if self.path == '/api/reset':
                    return self.antwort(200, {'text': leitung.reset()})
                if self.path == '/api/ram':
                    return self.antwort(200, {'daten': list(leitung.ram(int(req['adr']), int(req['n'])))})
                if self.path == '/api/zellen':
                    z = leitung.zellen_lesen(int(req['von']), int(req.get('anzahl', 1)))
                    return self.antwort(200, {'zellen': {f'{k:03d}': list(v) for k, v in z.items()}})
                if self.path == '/api/zelle':
                    leitung.zelle_schreiben(int(req['zelle']), int(req['befehl']), int(req['argument']))
                    return self.antwort(200, {'ok': True})
                if self.path == '/api/bank/sichern':
                    b = int(req['bank'])
                    k = leitung.bank_komplett(b)
                    namen = k['namen'] or namen_lesen(req.get('namen', ''))     # Namen aus der Bank haben Vorrang
                    return self.antwort(200, {'bank': b, 'name': k['name'], 'namen': namen_text(namen), 'namen_aus_bank': bool(k['namen']),
                                              'zellen': {f'{a:03d}': list(v) for a, v in k['zellen'].items()},
                                              'listing': disasm(k['zellen'], namen)})
                if self.path == '/api/bank/einspielen':
                    z = {int(k): tuple(v) for k, v in req['zellen'].items()}
                    st = req.get('start')
                    nm = req.get('namen')
                    r = leitung.bank_einspielen(int(req['bank']), z, req.get('name') or None,
                                                None if st in (None, '') else int(st) & 255,
                                                None if nm is None else namen_lesen(nm))
                    return self.antwort(200, r)
                return self.antwort(404, {'fehler': 'unbekannt'})
            except (KeineAntwort, FlashFehler) as e:
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
    if cmd == 'reset':
        r = ueber_server('/api/reset', {}, port=port)['text'] if srv else Leitung().reset()
        print('Reset:', r); return 0
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
    if cmd == 'zelle':
        n = int(rest[0])
        if len(rest) >= 3:
            obj = {'zelle': n, 'befehl': int(rest[1]), 'argument': int(rest[2])}
            if srv: ueber_server('/api/zelle', obj, port=port)
            else: Leitung().zelle_schreiben(n, obj['befehl'], obj['argument'])
            print(f"Zelle {n:03d} = {obj['befehl']:02d}.{obj['argument']:03d}"); return 0
        z = ueber_server('/api/zellen', {'von': n, 'anzahl': 1}, port=port)['zellen'] if srv else \
            {f'{k:03d}': list(v) for k, v in Leitung().zellen_lesen(n, 1).items()}
        b, a = z[f'{n:03d}']
        print(f'Zelle {n:03d} = {b:02d}.{a:03d}'); return 0
    if cmd == 'bank-sichern':
        b = int(rest[0])
        if srv:
            r = ueber_server('/api/bank/sichern', {'bank': b}, port=port)
            z, name, namen = {int(k): tuple(v) for k, v in r['zellen'].items()}, r.get('name'), namen_lesen(r.get('namen', ''))
        else:
            k = Leitung().bank_komplett(b); z, name, namen = k['zellen'], k['name'], k['namen']
        ks.json_schreiben(rest[1], z)
        if namen:
            open(rest[1] + '.namen', 'w').write(namen_text(namen))
        print(f'Bank {b:03d}' + (f' „{name}“' if name else '') + f' -> {rest[1]}' + (f' (+ {len(namen)} Namen in {rest[1]}.namen)' if namen else '')); return 0
    if cmd == 'bank-einspielen':
        b = int(rest[0]); z = ks.json_lesen(rest[1])
        st = int(rest[rest.index('--start') + 1]) if '--start' in rest else None
        nd = rest[rest.index('--namen') + 1] if '--namen' in rest else None
        name = next((a for a in rest[2:] if a not in ('--start', '--namen', str(st), nd)), None)
        nt = open(nd).read() if nd else None
        obj = {'bank': b, 'zellen': {f'{k:03d}': list(v) for k, v in z.items()}, 'name': name, 'start': st, 'namen': nt}
        if srv: ueber_server('/api/bank/einspielen', obj, port=port)
        else: Leitung().bank_einspielen(b, z, name, st, None if nt is None else namen_lesen(nt))
        print(f'{rest[1]} -> Bank {b:03d}'); return 0
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
    if cmd.startswith('flash') or cmd == 'autoboot':
        zahl = lambda i: int(rest[i])
        if cmd == 'flash':
            v = ueber_server('/api/flash', port=port) if srv else Leitung().flash_verzeichnis()
            print(f"Autoboot: {v['autoboot'] or 'aus'}")
            for e in v['baenke']:
                print(f"  {e['bank']:03d}  Start {e['start']:03d}  {e['name']}")
            return 0
        if cmd == 'flash-speichern':
            st = int(rest[rest.index('--start') + 1]) if '--start' in rest else None
            name = next((a for a in rest[1:] if not a.isdigit() and a != '--start'), '')
            obj = {'bank': zahl(0), 'name': name, 'start': st}
            if srv: ueber_server('/api/flash/speichern', obj, port=port)
            else: Leitung().flash_speichern(obj['bank'], name, st)
            print(f"Bank {obj['bank']:03d} gespeichert"); return 0
        if cmd == 'flash-laden':
            if srv: ueber_server('/api/flash/laden', {'bank': zahl(0)}, port=port)
            else: Leitung().flash_laden(zahl(0))
            print(f'Bank {zahl(0):03d} geladen'); return 0
        if cmd == 'autoboot':
            if srv: ueber_server('/api/flash/autoboot', {'bank': zahl(0)}, port=port)
            else: Leitung().flash_autoboot(zahl(0))
            print('Autoboot', f'Bank {zahl(0):03d}' if zahl(0) else 'aus'); return 0
    print(__doc__); return 1


def cli(argv):
    """main() mit lesbaren Fehlermeldungen (auch für kosmos_send.py / kosmos_recv.py)"""
    import urllib.error
    try:
        return main(argv)
    except KeineAntwort as e:
        print('Keine Antwort vom CP1:', e); return 2
    except FlashFehler as e:
        print('Flash:', e); return 3
    except urllib.error.HTTPError as e:
        try: print('Fehler:', json.load(e)['fehler'])
        except Exception: print('Server:', e)
        return 2


if __name__ == '__main__':
    sys.exit(cli(sys.argv[1:]))
