"""Pi-Seite von FNI (5.00) als Modell für den Simulator: Takt-Meister auf T (P1.6), Daten auf D (P1.7).

So soll es auch kosmos_rc (C) machen:
  Start:  auf T low warten (CP1 hat den Auftrag übernommen), dann auf T high (bereit).
  Bit:    auf T high warten (CP1 bereit) -> D setzen (nur wenn der Pi sendet, sonst loslassen)
          -> T low -> mindestens LOW_US warten -> T los -> (der CP1 hält T, bis er fertig ist).
          Nach T high mindestens HIGH_US warten, bevor T wieder low geht (der CP1 muss das High sehen).
          Empfängt der Pi, liest er D, sobald T wieder high ist (vor dem nächsten Bit).
  Kopf:   jj, Bank, erste Zelle, Anzahl, CRC-8; Blöcke an 4er-Zellgrenzen (2 Byte je Zelle) + CRC-8;
          nach jedem Block ein Quittungsbit des Empfängers (1 gut, 0 nochmal).
"""
import random

LOW_US = 80          # Mindestdauer T low (der CP1 fragt alle 15 µs ab)
HIGH_US = 100        # T high, bevor der Pi wieder zieht (der CP1 muss das High sicher sehen)
FRIST_US = 3_000_000 # so lange wartet der Pi höchstens auf T (der CP1 hält T z. B. beim Flash-Kopieren)


def crc8(daten, crc=0):
    for b in daten:
        crc ^= b
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


def bloecke(anf, anz):
    """[(erste Zelle, Anzahl)] an 4er-Grenzen; anz = 0 heißt 256"""
    n = anz or 256
    out, c = [], anf
    while n:
        k = min(4 - (c & 3), n)
        out.append((c, k)); c = (c + k) & 0xFF; n -= k
    return out


class Zeitueberschreitung(Exception):
    pass


class FNIPi:
    """Ein Auftrag. richtung 'ein' = Pi sendet (P-C, P-F), 'aus' = Pi empfängt (C-P, F-P).
    kopf = (jj, bank, anf, anz); daten = Bytes (2 je Zelle) beim Senden.
    stoerung: {'crc': {blocknr: anzahl}} kaputte CRC senden / falsch quittieren, 'abbruch_nach': blocknr,
              'zittern': µs zufällige Pausen (Pi unterbrochen), 'kopf': anderer Kopf."""

    def __init__(self, richtung, kopf, daten=b'', stoerung=None, seed=1):
        self.richtung, self.kopf, self.daten = richtung, kopf, bytes(daten)
        self.st = stoerung or {}
        self.rnd = random.Random(seed)
        self.t_low = False; self.d_low = False
        self.empfangen = bytearray(); self.fertig = False; self.fehler = None
        self.versuche = {}
        self._gen = self._ablauf(); self._warte = None; self._bis = 0
        self.bits = 0

    # --- Simulator-Anbindung
    def tick(self, m):
        if self.fertig: return
        self.m = m
        while True:
            w = self._warte
            if w is not None:
                if w[0] == 'zeit':
                    if m.us < w[1]: return
                elif w[0] == 'bed':
                    if not w[1]():
                        if m.us > w[2]:
                            self.fehler = 'Zeit um'; self.fertig = True; self.t_low = self.d_low = False; return
                        return
            try:
                self._warte = next(self._gen)
            except StopIteration:
                self.fertig = True; self.t_low = self.d_low = False; return

    def _zeit(self, us):
        return ('zeit', self.m.us + us)

    def _bis_t(self, pegel):
        return ('bed', lambda: self.m.takt() == pegel, self.m.us + FRIST_US)

    def _zittern(self):
        z = self.st.get('zittern', 0)
        return self._zeit(self.rnd.uniform(0, z)) if z and self.rnd.random() < 0.05 else self._zeit(0)

    # --- Bits
    def _bit_senden(self, bit):
        yield self._bis_t(1)
        yield self._zeit(HIGH_US)
        yield self._zittern()
        self.d_low = not bit
        self.t_low = True
        yield self._zeit(LOW_US)
        yield self._zittern()
        self.t_low = False
        self.bits += 1

    def _bit_lesen(self, ziel):
        yield self._bis_t(1)
        yield self._zeit(HIGH_US)
        self.d_low = False
        yield self._zittern()
        self.t_low = True
        yield self._zeit(LOW_US)
        self.t_low = False
        yield self._bis_t(1)               # der CP1 hat D gesetzt und lässt T los
        ziel.append(self.m.leitung())
        self.bits += 1

    def _byte_senden(self, b):
        for i in range(8):
            yield from self._bit_senden(b >> i & 1)

    def _byte_lesen(self, ziel):
        bits = []
        for i in range(8):
            yield from self._bit_lesen(bits)
        ziel.append(sum(b << i for i, b in enumerate(bits)))

    # --- Blöcke
    def _block_senden(self, nr, daten):
        for v in range(4):
            crc = crc8(daten)
            if self.st.get('crc', {}).get(nr, 0) > self.versuche.get(nr, 0):
                crc ^= 0x55
            self.versuche[nr] = self.versuche.get(nr, 0) + 1
            for b in daten: yield from self._byte_senden(b)
            yield from self._byte_senden(crc)
            q = []
            yield from self._bit_lesen(q)
            if q[0]: return True
        return False

    def _block_lesen(self, nr, n):
        for v in range(4):
            got = []
            for i in range(n + 1): yield from self._byte_lesen(got)
            ok = crc8(got[:-1]) == got[-1]
            if ok and self.st.get('crc', {}).get(nr, 0) > self.versuche.get(nr, 0):
                ok = False                 # Pi meldet absichtlich „nochmal“
            self.versuche[nr] = self.versuche.get(nr, 0) + 1
            yield from self._bit_senden(1 if ok else 0)
            if ok:
                self.empfangen += bytes(got[:-1]); return True
        return False

    def _ablauf(self):
        yield self._bis_t(0)               # Auftrag übernommen (CP1 hält T)
        jj, bank, anf, anz = self.st.get('kopf', self.kopf)
        kopf = bytes([jj, bank, anf, anz])
        if self.richtung == 'ein':
            if not (yield from self._block_senden(-1, kopf)):
                self.fehler = 'Kopf'; return
            pos = 0
            for nr, (c, k) in enumerate(bloecke(self.kopf[2], self.kopf[3])):
                if self.st.get('abbruch_nach') == nr:
                    self.fehler = 'abgebrochen'; return
                if not (yield from self._block_senden(nr, self.daten[pos:pos + 2 * k])):
                    self.fehler = f'Block {nr}'; return
                pos += 2 * k
            for i in range(pos, len(self.daten), 8):   # 5.03 ($29): Namensbereich 0x300..0x5FF in 8-Byte-Blöcken
                if not (yield from self._block_senden(2000 + i, self.daten[i:i + 8])):
                    self.fehler = f'Namensblock {i}'; return
        elif self.richtung == 'namen':
            if not (yield from self._block_lesen(-1, 4)):
                self.fehler = 'Kopf'; return
            self.empfangen = bytearray(); self.namen = []
            nr = 0
            while True:
                vorher = len(self.empfangen)
                if not (yield from self._block_lesen(nr, 8)): self.fehler = 'Namen'; return
                rec = self.empfangen[vorher:]
                if rec[0] == 0: break
                if not (yield from self._block_lesen(nr + 1, 8)): self.fehler = 'Namen'; return
                if not (yield from self._block_lesen(nr + 2, 2)): self.fehler = 'Namen'; return
                rec = self.empfangen[vorher:]
                self.namen.append((rec[0], bytes(rec[2:18])))
                nr += 3
        else:
            got = bytearray()
            if not (yield from self._block_lesen(-1, 4)):
                self.fehler = 'Kopf'; return
            if bytes(self.empfangen[:4]) != kopf:
                self.fehler = f'Kopf falsch {bytes(self.empfangen[:4]).hex()}'
            self.empfangen = bytearray()
            for nr, (c, k) in enumerate(bloecke(self.kopf[2], self.kopf[3])):
                if self.st.get('abbruch_nach') == nr:
                    self.fehler = 'abgebrochen'; return
                if not (yield from self._block_lesen(nr, 2 * k)):
                    self.fehler = f'Block {nr}'; return
            if self.richtung == 'komplett':      # 5.03: 0x200..0x5FF (Name, Generation, gültig, Namensbereich) in 128 Blöcken à 8
                for n in range(128):
                    if not (yield from self._block_lesen(1000 + n, 8)):
                        self.fehler = 'Bankkopf'; return
        yield self._bis_t(1)
