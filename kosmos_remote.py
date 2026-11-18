#!/usr/bin/env python3
"""Fernsteuerung für den Kosmos CP1, Firmware 6.00 (Projekte; für 5.x: kosmos_remote.py.v5): GPIO 26 <-> P1.7 (Klemme 8), GPIO 19 <-> P1.6 (Klemme 7).

Die Fernsteuerung ist immer an. Befehle:

  kosmos_remote.py serve [--port 8049]      Webseite + Schnittstelle (hält die Leitungen)
  kosmos_remote.py anzeige                   Anzeige als Text
  kosmos_remote.py taste 0 0 0 pc run        Tasten drücken (Name[:ms], z. B. cas:1500)
  kosmos_remote.py reset                     Kaltstart wie Einschalten: alles RAM weg (Firmware 5.02)
  kosmos_remote.py laden datei.json          Zellen ins RAM des CP1 (FNI, ~1 s)
  kosmos_remote.py speichern datei.json [--von N --bis M]   RAM des CP1 in eine Datei (FNI)
  kosmos_remote.py zelle N [B A]             Zelle N lesen bzw. auf B.A setzen (auch bei laufendem Programm)
  kosmos_remote.py flash                     Projektverzeichnis (Nummer, Bänke, Name, Kurzanzeige, Autoboot)
  kosmos_remote.py flash-speichern 12 "Rakete" [--start 20]   RAM des CP1 ins Projekt 12 (neu: der CP1 legt es an)
  kosmos_remote.py flash-laden 12            Projekt 12 ins RAM, PC = Start
  kosmos_remote.py autoboot 12               beim Einschalten Projekt 12 starten (0 = aus)
  kosmos_remote.py projekt-einspielen datei.cp1 [12]   Projektdatei ins Flash (ohne Nummer: erster freier Platz)
  kosmos_remote.py projekt-loeschen 12       Projekt 12 aus dem Verzeichnis nehmen
  kosmos_remote.py bank-leeren 6 [7 …]       Bänke leeren (Firmware 6.22: beide Sektoren löschen); 0..3 nur mit --auch-system
  kosmos_remote.py paket spiel.koa spiel.cp1 [--name N] [--start S] [--bilder b.txt]   Quelltext (auch Overlay-Paket
                                             mit .bereich / >>kern / >>teil k name / LADE name) als Projektdatei
  kosmos_remote.py bank-sichern 12 datei.json            Bank 12 direkt in eine Datei (RAM bleibt; Namen -> datei.json.namen)
  kosmos_remote.py bank-einspielen 12 datei.json ["Name"] [--start 20] [--namen datei.namen]   Datei direkt in Bank 12
                                             (--namen: Zuweisungstabelle „035=name“ mit in die Bank, Firmware 5.03)
  kosmos_remote.py projekt-sichern 8 minenflug.cp1 [--quelltext x.koa]   Projekt 8 komplett als Projektdatei
  kosmos_remote.py alle-sichern ordner/      jedes Projekt als Projektdatei ordner/NN-name.cp1
                                             (je Bank: Zellen, Labels, Bilder, Kurzanzeige, roh; dazu Start, Autoboot)

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
  $25 Bank komplett -> Pi (Zellen + 0x200..0x5FF; Bank 0 bis 0xFFF), $29 Pi -> Flash mit Name und Namensbereich
  (Bank 0: ganzes Verzeichnis), 6.00: $2A Verzeichnis kompakt -> Pi, $2B Verzeichnis-Eintrag direkt ($26 entfällt).
  Parameter: F_BANK 0x2C, F_ANF 0x3C, F_ANZ 0x3D (0 = 256), F_START 0x3E, Name 0x60..0x6F; fertig: F_JOB 0 / $EE.
Weitere Aufträge (Interrupt an): $04 Projekt laden, $08 Autoboot, $80 RAM -> Projekt (F_BANK = Projektnummer).
6.22: $30 Bank F_BANK leeren (ohne Übertragung, fertig: F_JOB 0; ältere Firmware verwirft $30). Aufträge gehen nur, wenn der CP1 auf Tasten wartet.
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
S_PBANK = 0x5f                            # 6.00: erste Bank des Projekts, aus dem das Programm stammt (SEF, PSK 0)
S_PRES = 0x5e                             # 6.00: reservierte Bänke des Projekts (PSK k < S_PRES)


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
        Geprüft an der Versionsanzeige („5.“ oder „6.“ in Stelle 3); -> Anzeige-Text"""
        with self.lock:
            for v in range(VERSUCHE):
                self._rc(rahmen(9, 0, 0).hex(), 0)
                time.sleep(0.3)
                try:
                    a = self.anzeige()
                except KeineAntwort:
                    continue
                if a['seg'][2] & 0x7F in (0x6D, 0x7D) and a['seg'][1] == 0 and a['seg'][0] == 0:
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
        if re.fullmatch(r'F\s*\.?\d{3}', text):           # nur die Fehleranzeige „F  .0nn“ – nicht z. B. ein stehen
            nr = int(text[-3:])                              #   gebliebenes „F-P.rdY“ (6.22: $30 ändert die Anzeige nicht)
            raise FlashFehler({10: 'F-010: kein Flash gefunden', 11: 'F-011: Bank ist leer',
                               3: 'F-003: Bank/Bereich ungültig', 1: 'F-001'}.get(nr, f'Fehler {text}'))

    # ------------------------------------------------ FNI (Interrupt des CP1 aus, getaktet)
    def fni(self, job, anf, anz, bank=0, daten=b'', start=255, name=None, versuche=3):
        """Großer Block: job $20..$2B. anz = Zellen (256 -> 0). -> empfangene Bytes (2 je Zelle, bei $25 + Bankkopf,
        Bank 0 bis 0xFFF; bei $2A je belegtem Eintrag 33 Byte: n + Eintrag)"""
        n = anz & 0xFF
        werte = {F_BANK: bank, F_ANF: anf & 0xFF, F_ANZ: n, F_START: start & 0xFF}
        if name is not None:
            werte.update({F_NAME + i: c for i, c in enumerate(name.encode('latin-1', 'replace')[:16].ljust(16, b' '))})
        richtung = {0x20: 'E', 0x22: 'E', 0x23: 'E', 0x29: 'E', 0x2B: 'E', 0x25: 'K', 0x2A: 'V'}.get(job, 'A')
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

    # ------------------------------------------------ 6.00: Projekte und Verzeichnis
    # Bank 0 = Verzeichnis („CP1V“, Version; Eintrag n = 1..99 ab 0x300 + 32 (n - 1): 0..15 Name, 16 erste Bank,
    # 17 reservierte Bänke, 18 Flags FE = belegt / FF = frei, 19..24 Kurzanzeige), Bank 1 = Einstellungen (0x000 Autoboot),
    # Projekte ab Bank 4, Start-PC in 0x213 der ersten Projektbank. Der CP1 legt beim Speichern selbst an (4 Bänke);
    # Löschen und Ändern macht der Pi (ganzes Verzeichnis neu, $29), neue Einträge schreibt er direkt ($2B).
    def verzeichnis(self):
        """-> {'vorhanden', 'autoboot', 'projekte': [{'nr', 'name', 'bank', 'res', 'anzeige'}]} ($24 Kopf, $2A Einträge)"""
        with self.lock:
            kopf = self.fni(0x24, 0, 3, bank=0)
            if kopf[:4] != b'CP1V':
                return {'vorhanden': False, 'autoboot': 0, 'projekte': []}
            roh = self.fni(0x2A, 0, 0, bank=0)
            ab = self.fni(0x24, 0, 1, bank=1)[0]
        pr = []
        for i in range(0, len(roh), 33):
            n, e = roh[i], roh[i + 1:i + 33]
            pr.append(eintrag_aus_bytes(n, e))
        return {'vorhanden': True, 'autoboot': 0 if ab == 0xFF else ab, 'projekte': pr}

    flash_verzeichnis = verzeichnis

    def verzeichnis_roh(self):
        """ganzer Verzeichnis-Sektor 0x000..0xFFF ($25 Bank 0, ~12 s)"""
        d = self.fni(0x25, 0, 0, bank=0)
        if len(d) != 0x1000: raise FlashFehler(f'Verzeichnis: {len(d)} statt 4096 Byte – Firmware 6.00?')
        return d

    def verzeichnis_schreiben(self, roh):
        """ganzen Verzeichnis-Sektor schreiben ($29 Bank 0: Zellenbereich + 0x300..0xFFF, ~10 s)"""
        roh = bytearray(roh)
        roh[0:6] = b'CP1V' + bytes([1, 0])
        zellen = {i: (roh[2 * i], roh[2 * i + 1]) for i in range(256)}
        self.fni(0x29, 0, 0, bank=0, daten=bytes(roh[0:0x200]) + bytes(roh[0x300:0x1000]), name='Verzeichnis')

    def verzeichnis_anlegen(self):
        """leeres Verzeichnis (alle Einträge frei); vorhandene Einträge gehen verloren"""
        roh = bytearray([0xFF]) * 0x1000
        roh[0:0x200] = bytes(0x200)
        self.verzeichnis_schreiben(roh)

    def eintrag_schreiben(self, nr, eintrag, v=None):
        """Eintrag nr (32 Byte) ins Verzeichnis: nur 1 -> 0 nötig: direkt ($2B), sonst ganzes Verzeichnis neu"""
        if not 1 <= nr <= 99: raise ValueError('Projekt 1..99')
        v = v or self.verzeichnis()
        if not v['vorhanden']:
            self.verzeichnis_anlegen(); v = {'vorhanden': True, 'projekte': []}
        alt = next((eintrag_bytes(e) for e in v['projekte'] if e['nr'] == nr), b'\xff' * 32)
        if all(n & a == n for n, a in zip(eintrag, alt)):
            self.fni(0x2B, 0, 16, bank=0, daten=bytes(eintrag), start=nr)
        else:
            roh = bytearray(self.verzeichnis_roh())
            roh[0x300 + 32 * (nr - 1):0x320 + 32 * (nr - 1)] = eintrag
            self.verzeichnis_schreiben(roh)

    def projekt_loeschen(self, nr):
        """Eintrag frei (FF); die Bänke bleiben im Flash, bis ein neues Projekt sie belegt"""
        roh = bytearray(self.verzeichnis_roh())
        roh[0x300 + 32 * (nr - 1):0x320 + 32 * (nr - 1)] = b'\xff' * 32
        self.verzeichnis_schreiben(roh)

    def flash_speichern(self, nr, name='', start=None):
        """RAM des CP1 ins Projekt nr (Auftrag $80: der CP1 legt neue Projekte selbst an), Name ins Verzeichnis"""
        werte = {F_BANK: nr}
        if start is not None: werte[0x38] = start          # PC = Startadresse
        self.auftrag(0x80, werte, frist_s=15)
        if name:
            v = self.verzeichnis()
            e = next(e for e in v['projekte'] if e['nr'] == nr)
            if (e['name'] or '') != name:
                self.eintrag_schreiben(nr, eintrag_bytes(dict(e, name=name)), v)

    def flash_laden(self, nr):
        self.auftrag(0x04, {F_BANK: nr})

    def flash_autoboot(self, nr):
        self.auftrag(0x08, {F_BANK: nr}, frist_s=10)

    def bank_leeren(self, bank):
        """Bank leeren ($30, Firmware 6.22): beide Sektoren gelöscht, danach gilt die Bank als leer.
        Ältere Firmware verwirft $30 ohne Wirkung (keins der Bits 7/3/2, die sie als speichern/Autoboot/laden liest)."""
        self.auftrag(0x30, {F_BANK: bank & 0xFF}, frist_s=10)

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
        mit = len(meta) >= 0x400 and meta[0x12] == 0
        namen = namen_aus_bytes(meta[0x100:0x400]) if mit else {}
        anzeige = anzeige_aus_bytes(meta[0x100:0x400]) if mit else None
        bilder = bilder_aus_bytes(meta[0x100:0x400]) if mit else []
        return {'zellen': self._zellen(d[:512], 0), 'name': name_text(meta[:16]), 'namen': namen, 'anzeige': anzeige,
                'bilder': bilder, 'roh': bytes(meta)}

    def projekt_sichern(self, nr, quelltext=None):
        """Projekt nr komplett: Verzeichnis-Eintrag + jede belegte Bank ($25) -> Projekt (dict, Format 1)"""
        with self.lock:
            v = self.verzeichnis()
            e = next((e for e in v['projekte'] if e['nr'] == nr), None)
            if e is None: raise FlashFehler(f'Projekt {nr} gibt es nicht')
            ks_ = [self.bank_komplett(e['bank'] + k) for k in range(e['res'])]
        while len(ks_) > 1 and ks_[-1]['roh'][0x11] != 0: ks_.pop()          # leere Bänke am Ende weglassen
        return projekt_aus_baenken(ks_, e, v['autoboot'] == nr, quelltext)

    def projekt_bank(self, nr):
        """-> Verzeichnis-Eintrag von Projekt nr oder None"""
        return next((e for e in self.verzeichnis()['projekte'] if e['nr'] == nr), None)

    def editor_speichern(self, nr, zellen, name=None, start=None, namen=None, anzeige=None, bilder=None):
        """Editor-Programm in die erste Bank von Projekt nr (neu: anlegen, 4 Bänke); Name/Kurzanzeige ins Verzeichnis.
        start None: bestehender Start bleibt (neu: 0)"""
        if not 1 <= nr <= 99: raise ValueError('Projekt 1..99')
        with self.lock:
            v = self.verzeichnis()
            pr = {e['nr']: e for e in v['projekte']}
            if nr in pr:
                erste, res = pr[nr]['bank'], pr[nr]['res']
            else:
                erste, res = luecke_suchen(pr.values(), 4, 1)
                if start is None: start = 0
            name = (name or (pr[nr]['name'] if nr in pr else '') or '')[:16]
            r = self.bank_einspielen(erste, zellen, name, start, namen, anzeige, bilder)
            e = {'nr': nr, 'name': name or None, 'bank': erste, 'res': res,
                 'anzeige': list(anzeige) if anzeige else (pr[nr]['anzeige'] if nr in pr else None)}
            if nr not in pr or eintrag_bytes(pr[nr]) != eintrag_bytes(e):
                self.eintrag_schreiben(nr, eintrag_bytes(e), v)
        return dict(r, projekt=nr)

    def projekt_einspielen(self, p, nr=None):
        """Projektdatei ins Flash: nr (1..99, sonst erster freier Platz); neues Projekt: max(4, Bänke) reservieren.
        Bänke mit Name, Labels, Bildern, Kurzanzeige, Start; dann Verzeichnis-Eintrag, ggf. Autoboot. -> nr"""
        projekt_pruefen(p)
        with self.lock:
            v = self.verzeichnis()
            pr = {e['nr']: e for e in v['projekte']}
            if nr is None:
                nr = next((n for n in range(1, 100) if n not in pr), None)
                if nr is None: raise FlashFehler('alle 99 Projektplätze belegt')
            n_b = len(p['baenke'])
            if nr in pr:
                erste, res = pr[nr]['bank'], pr[nr]['res']
                if n_b > res: raise FlashFehler(f'Projekt {nr} hat nur {res} Bänke reserviert, die Datei braucht {n_b}')
            else:
                erste, res = luecke_suchen(pr.values(), max(4, n_b), n_b)
            name = (p.get('name') or '')[:16]
            for k, b in enumerate(p['baenke']):
                z = {i: tuple(c) for i, c in enumerate(b['zellen'])}
                namen = {int(a): n for a, n in b.get('labels', {}).items()}
                bilder = [(x['name'], bytes(x['segmente'])) for x in b.get('bilder', [])]
                an = bytes(b['anzeige']) if b.get('anzeige') else None
                self.bank_einspielen(erste + k, z, name, int(p['start']) if k == 0 else None, namen, an, bilder)
            for k in range(n_b, res):                       # 6.22: reservierte, aber unbenutzte Bänke leeren
                self.bank_leeren(erste + k)                 #   (sonst bleiben dort alte Inhalte stehen)
            an0 = p['baenke'][0].get('anzeige')
            e = {'nr': nr, 'name': name or None, 'bank': erste, 'res': res, 'anzeige': list(an0) if an0 else None}
            if nr not in pr or eintrag_bytes(pr[nr]) != eintrag_bytes(e):
                self.eintrag_schreiben(nr, eintrag_bytes(e), v)
            if p.get('autoboot'): self.flash_autoboot(nr)
        return nr

    def bank_sichern(self, bank, von=0, bis=255):
        """Bank direkt aus dem Flash; das RAM des CP1 bleibt unberührt. Ganze Bank: Komplettdump ($25) mit Name.
        -> (zellen, name)"""
        if (von, bis) == (0, 255):
            k = self.bank_komplett(bank)
            return k['zellen'], k['name']
        return self._zellen(self.fni(0x24, von, bis - von + 1, bank=bank), von), None

    def bank_einspielen(self, bank, zellen, name=None, start=None, namen=None, anzeige=None, bilder=None):
        """Zellen direkt in eine Bank (FNI $22/$23); Rest der Bank bleibt; start != None -> Start-PC (6.00: 0x213).
        namen (dict, auch leer) -> $29 (5.03): Namensbereich 0x300..0x5FF wird mitgeschrieben (Name dann Pflicht)"""
        if not 4 <= bank <= 255: raise ValueError('Bank 4..255 (0..3: Verzeichnis, Einstellungen)')
        von, bis = min(zellen), max(zellen)
        daten = self._bytes(zellen, von, bis)
        if namen is not None or anzeige is not None or bilder:
            job, daten, name = 0x29, daten + namen_bytes(namen or {}, anzeige, bilder), (name or '')
        else:
            job = 0x23 if name is not None else 0x22
        self.fni(job, von, bis - von + 1, bank=bank, daten=daten, start=255 if start is None else start, name=name)
        return {'bank': bank, 'von': von, 'bis': bis}


NAME_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


# ------------------------------------------------ Projektdatei (.cp1, JSON, Format 1)
# Ein Projekt = eine oder mehrere Bänke (Index 0 = eigene Bank, PSK 0; k = k-te Bank des Projekts).
# Je Bank: alle 256 Zellen [Befehl, Argument], Labels, Bilder, eigene Blätter-Anzeige und als Netz der ganze
# Zusatzbereich 0x200..0x5FF roh (hex). Generation/gültig/Banknummer sind Sache des Flashs (Herkunft nur zur Info:
# gesichert, aus_baenken, ggf. firmware und angepasst). Programme sprechen weitere Bänke nur relativ an (PSK k).
PROJEKT_FORMAT, PROJEKT_VERSION = 'cp1-projekt', 1


def projekt_aus_baenken(ks_, e, autoboot=False, quelltext=None, firmware=None):
    """bank_komplett()-Ergebnisse (erste Bank zuerst) + Verzeichnis-Eintrag e -> Projekt (Format 1)"""
    def bank(k):
        return {'zellen': [list(k['zellen'][i]) for i in range(256)],
                'labels': {f'{a:03d}': n for a, n in sorted(k['namen'].items())},
                'bilder': [{'name': n, 'segmente': list(b)} for n, b in k['bilder']],
                'anzeige': list(k['anzeige']) if k['anzeige'] else None,
                'roh': bytes(k['roh']).hex()}
    st = ks_[0]['roh'][0x13]
    p = {'format': PROJEKT_FORMAT, 'version': PROJEKT_VERSION,
         'name': (e.get('name') or ks_[0]['name'] or '').rstrip(), 'start': 0 if st == 0xFF else st,
         'autoboot': bool(autoboot), 'baenke': [bank(k) for k in ks_],
         'herkunft': {'gesichert': time.strftime('%Y-%m-%d %H:%M'), 'projekt': e['nr'],
                      'aus_baenken': [e['bank'] + i for i in range(len(ks_))], 'reserviert': e['res']}}
    if e.get('anzeige') and not p['baenke'][0]['anzeige']: p['baenke'][0]['anzeige'] = list(e['anzeige'])
    if firmware: p['herkunft']['firmware'] = firmware
    if quelltext: p['quelltext'] = quelltext
    return p


def eintrag_aus_bytes(n, e):
    """32 Byte Verzeichnis-Eintrag -> {'nr', 'name', 'bank', 'res', 'anzeige'}"""
    nm = bytes(e[0:16])
    return {'nr': n, 'name': None if nm[0] == 0xFF else nm.split(b'\xff')[0].decode('latin-1').rstrip(),
            'bank': e[16], 'res': e[17], 'anzeige': None if e[19] == 0xFF else list(e[19:25])}


def eintrag_bytes(e):
    """{'name', 'bank', 'res', 'anzeige'} -> 32 Byte (belegt)"""
    b = bytearray([0xFF]) * 32
    if e.get('name'): b[0:16] = e['name'].encode('latin-1', 'replace')[:16].ljust(16)
    b[16], b[17], b[18] = e['bank'], e['res'], 0xFE
    if e.get('anzeige'): b[19:25] = bytes(e['anzeige'])
    return bytes(b)


def luecke_suchen(projekte, wunsch, mindestens):
    """erste Lücke ab Bank 4 für wunsch Bänke, sonst weniger (bis mindestens) -> (erste Bank, Anzahl); wie die Firmware"""
    belegt = [(e['bank'], e['bank'] + e['res']) for e in projekte]
    for w in range(wunsch, mindestens - 1, -1):
        s = 4
        while s + w <= 256:
            stoss = [b for a, b in belegt if a < s + w and s < b]
            if not stoss: return s, w
            s = max(stoss)
    raise FlashFehler('Flash voll: keine Lücke für das Projekt')


def projekt_pruefen(p):
    """Format prüfen; lesbare Felder müssen zum Rohbereich passen (verlustfrei). -> p, sonst ValueError"""
    if p.get('format') != PROJEKT_FORMAT or p.get('version') != PROJEKT_VERSION:
        raise ValueError(f"kein Projekt im Format {PROJEKT_FORMAT} {PROJEKT_VERSION}")
    if not 0 <= int(p['start']) <= 255: raise ValueError('start 0..255')
    if not p.get('baenke'): raise ValueError('keine Bank')
    for i, b in enumerate(p['baenke']):
        z = b['zellen']
        if len(z) != 256 or any(len(c) != 2 or not all(0 <= x <= 255 for x in c) for c in z):
            raise ValueError(f'Bank {i}: 256 Zellen [Befehl, Argument] 0..255 erwartet')
        roh = bytes.fromhex(b.get('roh', ''))
        if roh:
            if len(roh) != 0x400: raise ValueError(f'Bank {i}: roh muss 0x200..0x5FF sein (1024 Byte)')
            if roh[0x12] == 0:
                ns = roh[0x100:0x400]
                if {f'{a:03d}': n for a, n in sorted(namen_aus_bytes(ns).items())} != b['labels'] or \
                   [{'name': n, 'segmente': list(x)} for n, x in bilder_aus_bytes(ns)] != b['bilder']:
                    raise ValueError(f'Bank {i}: Labels/Bilder passen nicht zum Rohbereich')
    return p


def projekt_text(p):
    """JSON, gut lesbar: je Zeile 8 Zellen"""
    def z_text(zellen):
        zeilen = [', '.join(f'[{b},{a}]' for b, a in zellen[i:i + 8]) for i in range(0, 256, 8)]
        return '[\n' + ',\n'.join(f'        {z}' for z in zeilen) + '\n      ]'
    platz = {}
    q = json.loads(json.dumps(p))
    for i, b in enumerate(q['baenke']):
        platz[f'@@Z{i}@@'] = z_text(b['zellen']); b['zellen'] = f'@@Z{i}@@'
        if b.get('anzeige') is not None: platz[f'@@A{i}@@'] = json.dumps(b['anzeige']); b['anzeige'] = f'@@A{i}@@'
        for j, x in enumerate(b['bilder']):
            platz[f'@@B{i}_{j}@@'] = json.dumps(x['segmente']); x['segmente'] = f'@@B{i}_{j}@@'
    t = json.dumps(q, indent=2, ensure_ascii=False)
    for k, v in platz.items(): t = t.replace(f'"{k}"', v)
    assert json.loads(t) == json.loads(json.dumps(p))
    return t + '\n'


def projekt_lesen(fn):
    return projekt_pruefen(json.load(open(fn, encoding='utf-8')))


def projekt_dateiname(nr, name):
    n = re.sub(r'[^A-Za-z0-9äöüÄÖÜß_-]+', '_', (name or '').strip()).strip('_') or 'ohne_name'
    return f'{nr:02d}-{n}.cp1'


def namen_lesen(text):
    """Zuweisungstabelle „035=display_loop“ (eine je Zeile) -> {035: 'display_loop'}; Unpassendes wird übergangen"""
    out = {}
    for z in (text or '').splitlines():
        m = re.match(r'^\s*(\d{1,3})\s*=\s*(\S+)\s*$', z)
        if m and int(m.group(1)) <= 255 and NAME_RE.match(m.group(2)):
            out[int(m.group(1))] = m.group(2)
    return out


NAMEN_PLATZ = 0x300                       # 5.03: Namensbereich 0x300..0x5FF jedes Bank-Sektors


ANZEIGE_POS = 0x2F8                       # 5.05: eigene 6-stellige Anzeige der Bank bei 0x5F8..0x5FD


BILD_BASIS = 0x200                        # 5.06: SEF xxx liest Sektor 0x500 + xxx = Namensbereich + 0x200 + xxx


def bilder_layout(bilder):
    """[(name, bytes)] -> (Anfang im Namensbereich, {name: SEF-Position}). Die Bilder liegen lückenlos direkt vor der
    eigenen Anzeige (0x5F8), die Namen wachsen von unten (0x300) dagegen."""
    gesamt = sum(len(b) for _, b in bilder)
    if gesamt > ANZEIGE_POS - BILD_BASIS:
        raise ValueError(f'Bilder zu groß: {gesamt} Byte, Platz für {ANZEIGE_POS - BILD_BASIS}')
    anfang, pos, n = ANZEIGE_POS - gesamt, {}, ANZEIGE_POS - gesamt
    for name, b in bilder:
        pos[name] = n - BILD_BASIS; n += len(b)
    return anfang, pos


def namen_bytes(namen, anzeige=None, bilder=None):
    """{adresse: name} (+ 6 Segmentbytes Anzeige, + Bilder [(name, bytes)]) -> 768 Byte: je Eintrag Länge, Adresse,
    Name (ASCII), Bilder als Einträge „@name“ mit ihrer SEF-Position; FF = Ende. Bilder liegen vor 0x5F8;
    die letzten 8 Byte: Anzeige (6 Byte, FF = keine) + FF FF"""
    bilder = bilder or []
    anfang, pos = bilder_layout(bilder)
    eintraege = [(a & 0xFF, n.encode('ascii')[:63]) for a, n in sorted(namen.items())] + \
                [(pos[n], b'@' + n.encode('ascii')[:62]) for n, _ in bilder]
    out = bytearray()
    for a, b in eintraege:
        if len(out) + 2 + len(b) > anfang - 1:
            raise ValueError(f'Namensbereich voll ({anfang} Byte neben {ANZEIGE_POS - anfang} Byte Bildern) – '
                             f'ab {b.decode()} passt nichts mehr')
        out += bytes([len(b), a]) + b
    out += b'\xff' * (anfang - len(out))
    for _, b in bilder: out += b
    anz = bytes(anzeige)[:6] if anzeige else b'\xff' * 6
    return bytes(out) + anz.ljust(6, b'\x00') + b'\xff\xff'


def bilder_aus_bytes(d):
    """Namensbereich -> [(name, bytes)] in Positionsreihenfolge"""
    eintr, i = [], 0
    d = bytes(d[:ANZEIGE_POS])
    while i + 2 <= len(d) and 1 <= d[i] <= 63:
        n, a = d[i], d[i + 1]
        roh = d[i + 2:i + 2 + n]
        if roh[:1] == b'@':
            try:
                name = roh[1:].decode('ascii')
                if NAME_RE.match(name): eintr.append((a, name))
            except UnicodeDecodeError:
                pass
        i += 2 + n
    eintr.sort()
    out = []
    for k, (a, name) in enumerate(eintr):
        ende = eintr[k + 1][0] if k + 1 < len(eintr) else ANZEIGE_POS - BILD_BASIS
        out.append((name, d[BILD_BASIS + a:BILD_BASIS + ende]))
    return out


def bild_aus_text(text):
    """„MInEn“ (wie das Anzeige-Feld, „.“ = Punkt der Stelle davor, beliebig lang) oder „#118,121,56“ -> Bytes,
    mindestens 6 (mit dunklen Stellen aufgefüllt)"""
    text = text.rstrip('\r\n')                # Leerzeichen zählen (Lauftexte)
    if text.strip().startswith('#'):
        text = text.strip()
        werte = [int(x) for x in re.split(r'[,\s]+', text[1:].strip()) if x]
        if any(not 0 <= w <= 255 for w in werte): raise ValueError(f'Bild {text}: Werte 0..255')
        out = werte
    else:
        out = []
        for ch in text:
            if ch == '.' and out and not out[-1] & 0x80:
                out[-1] |= 0x80; continue
            out.append(SEG_ZEICHEN.get(ch, SEG_ZEICHEN.get(ch.upper(), 0)))
    return bytes(out + [0] * max(0, 6 - len(out)))


def bild_text(b):
    t = text_aus_anzeige(b)
    for v in (t.rstrip(' '), t):
        if '?' not in v and bild_aus_text(v) == bytes(b): return v
    return '#' + ','.join(str(x) for x in b)


def bilder_lesen(text):
    """Zeilen „name=MInEn“ / „name=#1,2,3“ -> [(name, bytes)]"""
    out, gesehen = [], set()
    for z in (text or '').splitlines():
        if not z.strip() or z.strip().startswith('//'): continue
        name, _, wert = z.lstrip().partition('=')
        name = name.strip().lstrip('@')
        if not NAME_RE.match(name) or not _: raise ValueError(f'Bild „{z}“: erwartet name=Text')
        if name in gesehen: raise ValueError(f'Bild {name} doppelt')
        gesehen.add(name); out.append((name, bild_aus_text(wert)))
    return out


def bilder_text(bilder):
    return ''.join(f'{n}={bild_text(b)}\n' for n, b in bilder)


SEF_RE = re.compile(r'^(\s*(?:\d{1,3}:?\s+)?(?:SEF|AKO|PSK|(?:ADD|SUB|VGL|VGR|VKL|UND|ODR)\s*#)\s*)([A-Za-z_]\w*)(?:\+(\d+))?',
                    re.I | re.M)                # Bildnamen als Wert: SEF titel, AKO lauf, ADD #lauf, SEF lauf+3


def sef_aufloesen(quelltext, bilder):
    """„SEF titel“ / „SEF titel+3“ / „ADD #lauf“ -> Position im Bilderbereich (für den Assembler)"""
    if not bilder: return quelltext
    _, pos = bilder_layout(bilder)
    def ersetze(m):
        if m.group(2) not in pos: return m.group(0)
        return m.group(1) + str(pos[m.group(2)] + int(m.group(3) or 0))
    return SEF_RE.sub(ersetze, quelltext)


def sef_benennen(listing, bilder):
    """Disassembler-Ausgabe: „SEF 230“ -> „SEF titel“ (bzw. titel+3)"""
    if not bilder: return listing
    _, pos = bilder_layout(bilder)
    starts = sorted((p, n, len(b)) for (n, b), p in zip(bilder, [pos[n] for n, _ in bilder]))
    def ersetze(m):
        x = int(m.group(2))
        for p, n, l in starts:
            if p <= x < p + l: return m.group(1) + (n if x == p else f'{n}+{x - p}') + ' ' * max(0, 3 - len(n))
        return m.group(0)
    return re.sub(r'(SEF )(\d{3})', ersetze, listing)


def anzeige_aus_bytes(d):
    """-> 6 Segmentbytes der eigenen Anzeige oder None"""
    a = bytes(d[ANZEIGE_POS:ANZEIGE_POS + 6])
    return a if len(a) == 6 and a[0] != 0xFF else None


# Zeichen -> 7 Segmente (wie asc_seg der Firmware, hier mit Klein-/Großbuchstaben, wo das Gerät sie kann)
SEG_ZEICHEN = {' ': 0, '-': 0x40, '_': 0x08, '=': 0x48, '.': 0x80, ',': 0x80, '?': 0x53, "'": 0x20, '"': 0x22,
               '(': 0x39, ')': 0x0f, '[': 0x39, ']': 0x0f, '/': 0x52, '\\': 0x64, '^': 0x23, '$': 0x6d,
               '0': 0x3f, '1': 0x06, '2': 0x5b, '3': 0x4f, '4': 0x66, '5': 0x6d, '6': 0x7d, '7': 0x07, '8': 0x7f, '9': 0x6f,
               'A': 0x77, 'B': 0x7c, 'C': 0x39, 'D': 0x5e, 'E': 0x79, 'F': 0x71, 'G': 0x3d, 'H': 0x76, 'I': 0x06,
               'J': 0x1e, 'K': 0x75, 'L': 0x38, 'M': 0x37, 'N': 0x54, 'O': 0x3f, 'P': 0x73, 'Q': 0x67, 'R': 0x50,
               'S': 0x6d, 'T': 0x78, 'U': 0x3e, 'V': 0x1c, 'W': 0x3e, 'X': 0x76, 'Y': 0x6e, 'Z': 0x5b,
               'b': 0x7c, 'c': 0x58, 'd': 0x5e, 'h': 0x74, 'i': 0x04, 'n': 0x54, 'o': 0x5c, 'r': 0x50, 't': 0x78, 'u': 0x1c}


def anzeige_aus_text(text, wie_firmware=False):
    """Text -> 6 Segmentbytes; „.“ setzt den Punkt der Stelle davor. Unbekanntes: dunkel.
    wie_firmware: so, wie asc_seg (5.05) einen Banknamen ohne eigene Anzeige zeigt (nur Großbuchstaben, O = o,
    jedes Zeichen eine Stelle)"""
    if wie_firmware:
        # 5.06: Tabelle der Firmware beginnt bei „,“ – Zeichen davor (Leer ! " # $ % & ' ( ) * +) bleiben dunkel
        return bytes(([0 if c < ',' else 0x5c if c == 'O' else 0x80 if c in '.,' else SEG_ZEICHEN.get(c, 0)
                       for c in text.upper()] + [0] * 6)[:6])
    out = []
    for ch in text:
        if ch == '.' and out and not out[-1] & 0x80:
            out[-1] |= 0x80; continue
        out.append(SEG_ZEICHEN.get(ch, SEG_ZEICHEN.get(ch.upper(), 0)))
    return bytes((out + [0] * 6)[:6])


def text_aus_anzeige(seg):
    rueck = {}
    for ch, v in sorted(SEG_ZEICHEN.items(), key=lambda kv: (not kv[0].isupper(), not kv[0].islower(), not kv[0].isdigit())):
        rueck.setdefault(v, ch)                 # Buchstaben vor Ziffern vor Zeichen
    return ''.join(rueck.get(b & 0x7F, '?') + ('.' if b & 0x80 else '') for b in seg)


def namen_aus_bytes(d):
    namen, i = {}, 0
    d = d[:ANZEIGE_POS]
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


def disasm(zellen, namen=None, bilder=None):
    """Listing; namen {adresse: name} ersetzen label_N/wert_N, bilder [(name, bytes)] die Zahlen hinter SEF"""
    return sef_benennen(_disasm(zellen, namen), bilder)


def _disasm(zellen, namen=None):
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


def assemblieren(quelltext, namen_alt='', bilder_text_=''):
    """Assemblieren + Relabel: Zeilennummern in den Markenzeilen des Quelltexts auf die echten Adressen setzen
    (sonst bleibt der Text, wie er ist). Zuweisungstabelle = Marken des Quelltexts + Einträge von Hand, deren
    Name keine Marke ist. -> dict(zellen, quelltext, namen, von, bis)"""
    bilder = bilder_lesen(bilder_text_)
    zellen, ausgabe = asm(sef_aufloesen(quelltext, bilder))
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
    return {'zellen': zellen, 'quelltext': '\n'.join(zeilen), 'namen': namen, 'bilder': bilder,
            'von': 0, 'bis': max(belegt or [0])}



# ------------------------------------------------ 6.10: Overlay-Pakete (JOV)
# Quelltext mit Abschnitten:
#   .bereich 128-255        wechselnder Bereich (Pflicht, sobald es Teile gibt)
#   >>kern                  fester Teil (auch alles vor dem ersten >>teil); liegt in Bank 0 des Projekts
#   >>teil 1 asteroiden     Teil für Bank 1 des Projekts, beginnt am Bereichsanfang; Name optional
#   LADE asteroiden         -> PSK 1 / PSK Länge des Teils / JOV Bereichsanfang (auch LADE 1; im Kern und in Teilen)
# Namen des Kerns gelten überall, Namen eines Teils nur dort (sie dürfen in jedem Teil gleich heißen).
# Regel (nicht geprüft): JOV/LADE nie aus einem Unterprogramm, das im wechselnden Bereich liegt.
PAKET_RE = re.compile(r'^\s*(\.bereich|>>kern|>>teil)\b', re.I | re.M)


def ist_paket(quelltext):
    return bool(PAKET_RE.search(quelltext or ''))


def _code_zeile(z):
    t = z.strip()
    return bool(t) and not t.startswith('//') and not t.startswith('>')


def _adressen(zeilen, start):
    """Adressen der Befehlszeilen wie der PHP-Assembler (Zahl vorn = feste Adresse, sonst +1) -> [adresse]"""
    out, letzte = [], start - 1
    for z in zeilen:
        if not _code_zeile(z): continue
        erstes = z.strip().split()[0].rstrip(':')
        letzte = int(erstes) if erstes.isdigit() else letzte + 1
        out.append(letzte)
    return out


def paket_zerlegen(quelltext):
    """-> (bereich (a, b) oder None, kern-Zeilen, [(k, name, zeilen)])"""
    bereich, kern, teile, ziel = None, [], [], None
    for z in quelltext.split('\n'):
        t = z.strip()
        m = re.match(r'^\.bereich\s+(\d+)\s*-\s*(\d+)\s*$', t, re.I)
        if m:
            bereich = (int(m.group(1)), int(m.group(2)))
            if not 0 < bereich[0] <= bereich[1] <= 255: raise ValueError(f'.bereich {t}: 1..255, Anfang <= Ende')
            continue
        if re.match(r'^>>kern\s*$', t, re.I):
            ziel = None; continue
        m = re.match(r'^>>teil\s+(\d+)(?:\s+([A-Za-z_]\w*))?\s*$', t, re.I)
        if m:
            k = int(m.group(1))
            if not 1 <= k <= 254: raise ValueError(f'>>teil {k}: Bank 1..254 des Projekts')
            if any(x[0] == k for x in teile): raise ValueError(f'>>teil {k} doppelt')
            teile.append((k, m.group(2) or f'teil{k}', [])); ziel = teile[-1][2]; continue
        if t.startswith('>>'): raise ValueError(f'unbekannter Abschnitt: {t}')
        (kern if ziel is None else ziel).append(z)
    if teile and bereich is None: raise ValueError('Teile brauchen „.bereich a-b“')
    return bereich, kern, teile


def _lade_aufloesen(zeilen, teile, laengen, anfang):
    """LADE name / LADE k -> PSK k / PSK n / JOV anfang (feste Adresse vorn bleibt an der ersten Zeile)"""
    namen = {n.lower(): k for k, n, _ in teile}
    out = []
    for z in zeilen:
        m = re.match(r'^(\s*)(\d{1,3}:?\s+)?LADE\s+(\w+)\s*(//.*)?$', z, re.I)
        if not m: out.append(z); continue
        w = m.group(3)
        k = int(w) if w.isdigit() else namen.get(w.lower())
        if k is None or k not in laengen: raise ValueError(f'LADE {w}: Teil unbekannt')
        out += [f'{m.group(1)}{m.group(2) or ""}PSK {k}', f'{m.group(1)}PSK {laengen[k] & 0xFF}', f'{m.group(1)}JOV {anfang}']
    return out


def _marken(ausgabe):
    out = {}
    for z in ausgabe.splitlines():
        m = re.match(r'^>([^\s:]+):\s+(\d{3})\s*$', z)
        if m: out[m.group(1)] = int(m.group(2))
    return out


def paket_assemblieren(quelltext, namen_alt='', bilder_text_=''):
    """Overlay-Paket -> dict(baenke [{zellen, namen}], bereich, teile [{k, name, laenge}], zellen/namen (= Kern),
    quelltext (Marken mit Adressen), bilder, von, bis)"""
    bereich, kern, teile = paket_zerlegen(quelltext)
    bilder = bilder_lesen(bilder_text_)
    a, b = bereich or (256, 255)
    vorlaeufig = {k: 0 for k, _, _ in teile}
    kern_q = sef_aufloesen('\n'.join(_lade_aufloesen(kern, teile, vorlaeufig, a)), bilder)
    for adr in _adressen(kern_q.split('\n'), 0):
        if a <= adr <= b: raise ValueError(f'Kern belegt Zelle {adr:03d} im wechselnden Bereich {a:03d}–{b:03d}')
        if adr > 255: raise ValueError('Kern länger als 256 Zellen')
    kz, kaus = asm(kern_q)
    kern_marken = _marken(kaus)
    # Längen aller Teile vorab (LADE wird immer zu 3 Zeilen), damit auch Teile andere Teile laden können
    laengen = {}
    for k, name, zeilen in teile:
        if not [z for z in zeilen if _code_zeile(z)]: raise ValueError(f'Teil {name} ist leer')
        tq = _lade_aufloesen(zeilen, teile, vorlaeufig, a)
        i = next(i for i, z in enumerate(tq) if _code_zeile(z))
        if not tq[i].strip().split()[0].rstrip(':').isdigit(): tq[i] = f'{a:03d} ' + tq[i].strip()
        laengen[k] = max(_adressen(tq, a)) - a + 1
    ergebnis_teile, teil_marken = [], {}
    for k, name, zeilen in teile:
        tq = sef_aufloesen('\n'.join(_lade_aufloesen(zeilen, teile, laengen, a)), bilder).split('\n')
        i = next(i for i, z in enumerate(tq) if _code_zeile(z))
        erstes = tq[i].strip().split()[0].rstrip(':')
        if erstes.isdigit() and int(erstes) != a: raise ValueError(f'Teil {name} muss bei {a:03d} beginnen')
        if not erstes.isdigit(): tq[i] = f'{a:03d} ' + tq[i].strip()
        adr = _adressen(tq, a)
        if min(adr) < a or max(adr) > b:
            raise ValueError(f'Teil {name} passt nicht in {a:03d}–{b:03d} (reicht von {min(adr):03d} bis {max(adr):03d})')
        eigene = {m.group(2) for z in tq for m in [MARKE_RE.match(z)] if m}
        doppelt = eigene & set(kern_marken)
        if doppelt: raise ValueError(f'Teil {name}: Namen auch im Kern: {", ".join(sorted(doppelt))}')
        tz, taus = asm(kern_q + '\n' + '\n'.join(tq))
        tm = {n: v for n, v in _marken(taus).items() if n in eigene}
        teil_marken[k] = tm
        ergebnis_teile.append({'k': k, 'name': name, 'laenge': laengen[k],
                               'zellen': {n: tz[n] if a <= n <= b else (0, 0) for n in range(256)}})
    kern_q = sef_aufloesen('\n'.join(_lade_aufloesen(kern, teile, laengen, a)), bilder)
    kz, kaus = asm(kern_q)
    kern_marken = _marken(kaus)
    # Quelltext: Marken auf ihre Adressen setzen (Kern und je Teil)
    zeilen, abschnitt = [], None
    for z in quelltext.split('\n'):
        t = z.strip()
        m = re.match(r'^>>teil\s+(\d+)', t, re.I)
        if m: abschnitt = int(m.group(1))
        elif re.match(r'^>>kern\s*$', t, re.I): abschnitt = None
        mm = MARKE_RE.match(z)
        tab = kern_marken if abschnitt is None else teil_marken.get(abschnitt, {})
        if mm and mm.group(2) in tab:
            z = mm.group(1) + f'>{mm.group(2)}:'.ljust(28) + f'{tab[mm.group(2)]:03d}'
        zeilen.append(z)
    knamen = {v: n for n, v in kern_marken.items() if NAME_RE.match(n)}
    for adr, n in namen_lesen(namen_alt).items():
        if n not in kern_marken and adr not in knamen: knamen[adr] = n
    baenke = {0: {'zellen': kz, 'namen': knamen}}
    for t in ergebnis_teile:
        baenke[t['k']] = {'zellen': t['zellen'], 'namen': {**knamen, **{v: n for n, v in teil_marken[t['k']].items() if NAME_RE.match(n)}}}
    hoechste = max(baenke)
    liste = [baenke.get(i, {'zellen': {n: (0, 0) for n in range(256)}, 'namen': {}}) for i in range(hoechste + 1)]
    belegt = [n for n, v in kz.items() if v != (0, 0)]
    return {'baenke': liste, 'bereich': bereich, 'teile': [{k: t[k] for k in ('k', 'name', 'laenge')} for t in ergebnis_teile],
            'zellen': kz, 'namen': knamen, 'quelltext': '\n'.join(zeilen), 'bilder': bilder,
            'von': 0, 'bis': max(belegt or [0])}


def paket_projekt(quelltext, name, start=0, namen_alt='', bilder_text_='', anzeige=None):
    """Overlay-Paket (oder gewöhnliches Programm) -> Projekt (dict, Format 1) mit Kern in Bank 0 und Teilen in 1, 2, …"""
    r = paket_assemblieren(quelltext, namen_alt, bilder_text_) if ist_paket(quelltext) else \
        dict(assemblieren(quelltext, namen_alt, bilder_text_), baenke=None)
    baenke = r['baenke'] or [{'zellen': r['zellen'], 'namen': r['namen']}]
    p = {'format': PROJEKT_FORMAT, 'version': PROJEKT_VERSION, 'name': name, 'start': start, 'autoboot': False,
         'baenke': [], 'quelltext': r['quelltext'],
         'herkunft': {'gesichert': time.strftime('%Y-%m-%d %H:%M'), 'assembliert': True}}
    for i, b in enumerate(baenke):
        p['baenke'].append({'zellen': [list(b['zellen'].get(n, (0, 0))) for n in range(256)],
                            'labels': {f'{a:03d}': n for a, n in sorted(b['namen'].items())},
                            'bilder': [{'name': n, 'segmente': list(x)} for n, x in r['bilder']] if i == 0 else [],
                            'anzeige': list(anzeige) if anzeige and i == 0 else None})
    return p


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
                    paket = ist_paket(req['quelltext'])
                    r = (paket_assemblieren if paket else assemblieren)(req['quelltext'], req.get('namen', ''), req.get('bilder', ''))
                    return self.antwort(200, {'quelltext': r['quelltext'], 'namen': namen_text(r['namen']),
                                              'bilder': bilder_text(r['bilder']),
                                              'zellen': {f'{k:03d}': list(v) for k, v in sorted(r['zellen'].items())},
                                              'bis': r['bis'], 'teile': r.get('teile', []), 'bereich': r.get('bereich')})
                if self.path == '/api/anzeige_vorschau':
                    return self.antwort(200, {'seg': list(anzeige_aus_text(req.get('text', ''), bool(req.get('wie_firmware'))))})
                if self.path == '/api/disasm':
                    z = {int(k): tuple(v) for k, v in req['zellen'].items()}
                    return self.antwort(200, {'listing': disasm(z, namen_lesen(req.get('namen', '')), bilder_lesen(req.get('bilder', '')))})
                if self.path == '/api/laden':
                    if 'quelltext' in req:
                        r = assemblieren(req['quelltext'], req.get('namen', ''), req.get('bilder', ''))
                        zellen = {n: v for n, v in r['zellen'].items() if n <= r['bis']}   # bis zur letzten belegten Zelle
                    else:
                        zellen = {int(k): tuple(v) for k, v in req['zellen'].items()}
                    voll = {i: zellen.get(i, (0, 0)) for i in range(min(zellen), max(zellen) + 1)}
                    r = leitung.laden(voll)
                    if req.get('projekt'):          # 6.00: SEF/FRD/FWR beziehen sich auf dieses Projekt
                        e = leitung.projekt_bank(int(req['projekt']))
                        if e:
                            leitung.schreib(S_PBANK, e['bank']); leitung.schreib(S_PRES, e['res'])
                            r['projekt_bank'] = e['bank']
                    return self.antwort(200, r)
                if self.path == '/api/speichern':
                    z = leitung.speichern(req.get('von'), req.get('bis'))
                    return self.antwort(200, {'zellen': {f'{k:03d}': list(v) for k, v in sorted(z.items())},
                                              'listing': disasm(z, namen_lesen(req.get('namen', '')), bilder_lesen(req.get('bilder', '')))})
                if self.path == '/api/flash/speichern':
                    nr = int(req['projekt'])
                    if not 1 <= nr <= 99: raise ValueError('Projekt 1..99')
                    st = req.get('start')
                    leitung.flash_speichern(nr, req.get('name', ''), None if st in (None, '') else int(st) & 255)
                    return self.antwort(200, {'ok': True})
                if self.path == '/api/flash/laden':
                    leitung.flash_laden(int(req['projekt']))
                    return self.antwort(200, {'ok': True})
                if self.path == '/api/flash/autoboot':
                    leitung.flash_autoboot(int(req['projekt']) % 100)
                    return self.antwort(200, {'ok': True})
                if self.path == '/api/projekt/einspielen':
                    return self.antwort(200, {'nr': leitung.projekt_einspielen(projekt_pruefen(req['projekt']), req.get('nr'))})
                if self.path == '/api/projekt/loeschen':
                    leitung.projekt_loeschen(int(req['projekt']))
                    return self.antwort(200, {'ok': True})
                if self.path == '/api/bank/leeren':
                    leitung.bank_leeren(int(req['bank']))
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
                if self.path == '/api/projekt/editor':          # 6.00: erste Bank des Projekts in den Editor
                    e = leitung.projekt_bank(int(req['projekt']))
                    if e is None: raise FlashFehler(f"Projekt {int(req['projekt'])} gibt es nicht")
                    k = leitung.bank_komplett(e['bank'])
                    namen = k['namen'] or namen_lesen(req.get('namen', ''))
                    an = k['anzeige'] or (bytes(e['anzeige']) if e['anzeige'] else None)
                    st = k['roh'][0x13]
                    return self.antwort(200, {'projekt': e['nr'], 'bank': e['bank'], 'name': e['name'] or k['name'],
                                              'start': 0 if st == 0xFF else st,
                                              'namen': namen_text(namen), 'namen_aus_bank': bool(k['namen']),
                                              'anzeige': text_aus_anzeige(an) if an else '', 'bilder': bilder_text(k['bilder']),
                                              'zellen': {f'{a:03d}': list(v) for a, v in k['zellen'].items()},
                                              'listing': disasm(k['zellen'], namen, k['bilder'])})
                if self.path == '/api/projekt/editor_speichern' and ist_paket(req.get('quelltext', '')):
                    nr = int(req['projekt']); st = req.get('start'); an = (req.get('anzeige') or '').strip()
                    alt = leitung.projekt_bank(nr)
                    name = req.get('name') or (alt['name'] if alt else '') or ''
                    if st in (None, ''):
                        st = leitung.bank_komplett(alt['bank'])['roh'][0x13] if alt else 0
                        st = 0 if st == 0xFF else st
                    p = paket_projekt(req['quelltext'], name, int(st) & 255, req.get('namen', ''), req.get('bilder', ''),
                                      anzeige_aus_text(an) if an else None)
                    leitung.projekt_einspielen(p, nr)
                    e = leitung.projekt_bank(nr)
                    return self.antwort(200, {'projekt': nr, 'bank': e['bank'], 'baenke': len(p['baenke'])})
                if self.path == '/api/projekt/editor_speichern':
                    z = {int(k): tuple(v) for k, v in req['zellen'].items()}
                    st = req.get('start')
                    nm, an = req.get('namen'), (req.get('anzeige') or '').strip()
                    r = leitung.editor_speichern(int(req['projekt']), z, req.get('name') or None,
                                                 None if st in (None, '') else int(st) & 255,
                                                 None if nm is None else namen_lesen(nm),
                                                 anzeige_aus_text(an) if an else None, bilder_lesen(req.get('bilder', '')))
                    return self.antwort(200, r)
                if self.path == '/api/bank/sichern':
                    b = int(req['bank'])
                    k = leitung.bank_komplett(b)
                    namen = k['namen'] or namen_lesen(req.get('namen', ''))     # Namen aus der Bank haben Vorrang
                    return self.antwort(200, {'bank': b, 'name': k['name'], 'namen': namen_text(namen), 'namen_aus_bank': bool(k['namen']),
                                              'anzeige': text_aus_anzeige(k['anzeige']) if k['anzeige'] else '',
                                              'bilder': bilder_text(k['bilder']),
                                              'zellen': {f'{a:03d}': list(v) for a, v in k['zellen'].items()},
                                              'listing': disasm(k['zellen'], namen, k['bilder'])})
                if self.path == '/api/projekt/sichern':
                    return self.antwort(200, leitung.projekt_sichern(int(req['projekt']), req.get('quelltext')))
                if self.path == '/api/bank/einspielen':
                    z = {int(k): tuple(v) for k, v in req['zellen'].items()}
                    st = req.get('start')
                    nm, an = req.get('namen'), (req.get('anzeige') or '').strip()
                    r = leitung.bank_einspielen(int(req['bank']), z, req.get('name') or None,
                                                None if st in (None, '') else int(st) & 255,
                                                None if nm is None else namen_lesen(nm),
                                                anzeige_aus_text(an) if an else None,
                                                bilder_lesen(req.get('bilder', '')))
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
    if cmd in ('projekt-sichern', 'alle-sichern'):
        qt = None
        if '--quelltext' in rest:
            i = rest.index('--quelltext'); qt = open(rest[i + 1], encoding='utf-8').read(); rest = rest[:i] + rest[i + 2:]
        leitung = None if srv else Leitung()
        def hole(nr):
            p = ueber_server('/api/projekt/sichern', {'projekt': nr, 'quelltext': qt}, port=port, timeout=300) if srv \
                else leitung.projekt_sichern(nr, qt)
            return projekt_pruefen(p)
        def schreibe(p, fn):
            tmp = fn + '.neu'; open(tmp, 'w', encoding='utf-8').write(projekt_text(p)); os.replace(tmp, fn)
            h = p['herkunft']
            print(f"Projekt {h['projekt']:02d} „{p['name']}“ (Bänke {', '.join(f'{x:03d}' for x in h['aus_baenken'])})"
                  f" Start {p['start']:03d}{' Autoboot' if p['autoboot'] else ''}: "
                  f"{sum(len(b['labels']) for b in p['baenke'])} Labels, {sum(len(b['bilder']) for b in p['baenke'])} Bilder -> {fn}")
        if cmd == 'projekt-sichern':
            schreibe(hole(int(rest[0])), rest[1]); return 0
        os.makedirs(rest[0], exist_ok=True)
        v = ueber_server('/api/flash', port=port) if srv else leitung.verzeichnis()
        for e in v['projekte']:
            schreibe(hole(e['nr']), os.path.join(rest[0], projekt_dateiname(e['nr'], e['name'])))
        print(f"{len(v['projekte'])} Projekte gesichert."); return 0
    if cmd == 'paket':
        q = open(rest[0], encoding='utf-8').read()
        opt = lambda n, d=None: rest[rest.index(n) + 1] if n in rest else d
        bt = open(opt('--bilder')).read() if opt('--bilder') else ''
        name = opt('--name', os.path.splitext(os.path.basename(rest[0]))[0])
        p = paket_projekt(q, name, int(opt('--start', 0)), '', bt)
        open(rest[1], 'w', encoding='utf-8').write(projekt_text(p))
        r = paket_assemblieren(q, '', bt) if ist_paket(q) else None
        teile = ', '.join(f"Teil {t['k']} {t['name']} {t['laenge']} Zellen" for t in r['teile']) if r else 'ohne Teile'
        print(f"{rest[0]} -> {rest[1]}: Kern bis {(r or assemblieren(q))['bis']:03d}; {teile}"); return 0
    if cmd == 'projekt-einspielen':
        p = projekt_lesen(rest[0]); nr = int(rest[1]) if len(rest) > 1 else None
        nr = ueber_server('/api/projekt/einspielen', {'projekt': p, 'nr': nr}, port=port, timeout=600)['nr'] if srv \
            else Leitung().projekt_einspielen(p, nr)
        print(f"{rest[0]} -> Projekt {nr:02d} „{p['name']}“"); return 0
    if cmd == 'projekt-loeschen':
        nr = int(rest[0])
        if srv: ueber_server('/api/projekt/loeschen', {'projekt': nr}, port=port, timeout=300)
        else: Leitung().projekt_loeschen(nr)
        print(f'Projekt {nr:02d} gelöscht (die Bänke werden bei Bedarf neu vergeben)'); return 0
    if cmd == 'bank-leeren':
        alle = '--auch-system' in rest
        baenke = [int(a) for a in rest if a != '--auch-system']
        if not baenke: print('bank-leeren: welche Bank?'); return 2
        if any(b < 4 for b in baenke) and not alle:
            print('Bank 0..3 sind Verzeichnis und Einstellungen – nur mit --auch-system'); return 2
        for b in baenke:
            if srv: ueber_server('/api/bank/leeren', {'bank': b}, port=port)
            else: Leitung().bank_leeren(b)
            print(f'Bank {b:03d} geleert')
        return 0
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
            v = ueber_server('/api/flash', port=port) if srv else Leitung().verzeichnis()
            if not v['vorhanden']:
                print('noch kein Verzeichnis (Firmware 6.00 legt es beim ersten Speichern an)'); return 0
            print(f"Autoboot: {v['autoboot'] or 'aus'}")
            for e in v['projekte']:
                print(f"  {e['nr']:02d}  Bänke {e['bank']:03d}–{e['bank'] + e['res'] - 1:03d}  {e['name'] or ''}"
                      f"{'  [' + text_aus_anzeige(e['anzeige']) + ']' if e['anzeige'] else ''}")
            return 0
        if cmd == 'flash-speichern':
            st = int(rest[rest.index('--start') + 1]) if '--start' in rest else None
            name = next((a for a in rest[1:] if not a.isdigit() and a != '--start'), '')
            obj = {'projekt': zahl(0), 'name': name, 'start': st}
            if srv: ueber_server('/api/flash/speichern', obj, port=port, timeout=300)
            else: Leitung().flash_speichern(obj['projekt'], name, st)
            print(f"RAM in Projekt {obj['projekt']:02d} gespeichert"); return 0
        if cmd == 'flash-laden':
            if srv: ueber_server('/api/flash/laden', {'projekt': zahl(0)}, port=port)
            else: Leitung().flash_laden(zahl(0))
            print(f'Projekt {zahl(0):02d} geladen'); return 0
        if cmd == 'autoboot':
            if srv: ueber_server('/api/flash/autoboot', {'projekt': zahl(0)}, port=port)
            else: Leitung().flash_autoboot(zahl(0))
            print('Autoboot', f'Projekt {zahl(0):02d}' if zahl(0) else 'aus'); return 0
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
