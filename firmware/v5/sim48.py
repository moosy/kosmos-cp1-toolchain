"""Kleiner 8049-Simulator für den Kosmos CP1 (Tests der schnellen Kassette).
6 MHz -> 2,5 µs je Maschinenzyklus. Bildet nach: Befehlssatz, Timer-Interrupt,
Bank-Umschaltung (PC-Bit 11, im Interrupt 0), zwei 8155 (intern, CP3),
Tastatur über MOVD A,P4 wie in asigs Emulator, Leitung P1.7 zum Pi."""

ZYKLUS_US = 2.5
ZWEI = set()
for o in (0x02, 0x03, 0x08, 0x09, 0x0A, 0x13, 0x23, 0x39, 0x3A, 0x43, 0x53, 0x80, 0x81, 0x83, 0x88, 0x89, 0x8A,
          0x90, 0x91, 0x93, 0x98, 0x99, 0x9A, 0xA3, 0xB0, 0xB1, 0xB3, 0xD3, 0xE3):
    ZWEI.add(o)
for o in range(0x0C, 0x10): ZWEI.add(o)
for o in range(0x3C, 0x40): ZWEI.add(o)
for o in range(0x8C, 0x90): ZWEI.add(o)
for o in range(0x9C, 0xA0): ZWEI.add(o)
for o in range(0xB8, 0xC0): ZWEI.add(o)
for o in range(0xE8, 0xF0): ZWEI.add(o)
for b in range(8):
    ZWEI.add(0x04 | b << 5); ZWEI.add(0x14 | b << 5); ZWEI.add(0x12 | b << 5)
for o in (0x16, 0x26, 0x36, 0x46, 0x56, 0x76, 0x86, 0x96, 0xB6, 0xC6, 0xE6, 0xF6):
    ZWEI.add(o)

TASTEN = {'0': (4, 0), '1': (4, 1), '2': (4, 2), '3': (4, 3), '4': (3, 0), '5': (3, 1), '6': (3, 2), '7': (3, 3),
          '8': (2, 0), '9': (2, 1), 'out': (2, 2), 'inp': (2, 3), 'cal': (1, 0), 'step': (1, 1), 'stp': (1, 2),
          'run': (1, 3), 'cas': (0, 0), 'clr': (0, 1), 'pc': (0, 2), 'acc': (0, 3)}


class P8155:
    def __init__(self, vorhanden=True):
        self.ram = bytearray(256); self.pa = self.pb = self.pc = 0xFF; self.da = vorhanden
        self.ziffer = [0] * 6   # was leuchtete, während Ziffer n (PCn = 0) an war: Port A, Bit 7 = Punkt (PA7)
        self.neue_zeile = False

    def schreib(self, io, adr, w):
        if not self.da: return
        if io:
            r = adr & 7
            if r == 1:
                self.pa = w
                if self.neue_zeile:   # erstes Muster nach dem Zeilenwechsel (davor nur Dunkeltasten mit 0)
                    self.neue_zeile = False
                    for n in range(6):
                        if (self.pc & 0x3F) == (0x3F & ~(1 << n)): self.ziffer[n] = w
            elif r == 2: self.pb = w
            elif r == 3: self.pc = w; self.neue_zeile = True
        else:
            self.ram[adr] = w

    def lies(self, io, adr):
        if not self.da: return 0xFF
        if io:
            return {1: self.pa, 2: self.pb, 3: self.pc}.get(adr & 7, 0xFF)
        return self.ram[adr]


class SPIFlash:
    """IS25LP016D-Modell: 2 MB, Befehle 9F 05 06 04 03 02 20. Pins: P1.0 CS#, P1.1 SCK, P1.2 SI, P1.3 SO."""
    def __init__(self, groesse=0x200000, besch_lesungen=3):
        self.m = bytearray([0xFF]) * groesse
        self.cs = 1; self.sck = 0; self.so = 1
        self.rein = 0; self.bits = 0; self.bytes = []; self.raus = []; self.wel = 0
        self.besch = 0; self.besch_lesungen = besch_lesungen
        self.log = []                  # (befehl, adresse)
        self.programmiert = 0; self.geloescht = 0

    def pins(self, p1):
        cs, sck, si = p1 & 1, (p1 >> 1) & 1, (p1 >> 2) & 1
        if cs and not self.cs: self._ende()
        if not cs and self.cs: self.bytes = []; self.bits = 0; self.rein = 0; self.raus = []; self.so = 1
        self.cs = cs
        if not cs:
            if sck and not self.sck:           # steigend: SI übernehmen
                self.rein = (self.rein << 1 | si) & 0xFF; self.bits += 1
                if self.bits == 8:
                    self.bits = 0; self.bytes.append(self.rein); self._byte()
            if not sck and self.sck:           # fallend: nächstes SO-Bit
                self._so_weiter()
        self.sck = sck

    def _so_weiter(self):
        if self.raus:
            self.so = self.raus.pop(0)
        else:
            self.so = 1

    def _gib(self, b):
        self.raus += [(b >> (7 - i)) & 1 for i in range(8)]

    def _byte(self):
        b = self.bytes; c = b[0]
        if len(b) == 1:
            if c == 0x9F: self._gib(0x9D); self._gib(0x60); self._gib(0x15)
            elif c == 0x05: self._status()
            elif c == 0x06: self.wel = 1
            elif c == 0x04: self.wel = 0
        elif c == 0x05: self._status()
        elif c == 0x03 and len(b) >= 4:
            a = (b[1] << 16 | b[2] << 8 | b[3]) + len(b) - 4
            self._gib(self.m[a % len(self.m)])
        if c in (0x03,) and len(b) == 4: self.log.append((c, b[1] << 16 | b[2] << 8 | b[3]))

    def _status(self):
        st = (1 if self.besch > 0 else 0) | (2 if self.wel else 0)
        if self.besch > 0: self.besch -= 1
        self._gib(st)

    def _ende(self):
        b = self.bytes
        if not b: return
        c = b[0]
        if c == 0x02 and len(b) >= 5:
            assert self.wel, 'PP ohne WREN'
            a = b[1] << 16 | b[2] << 8 | b[3]
            seite = a & ~0xFF
            for i, d in enumerate(b[4:]):
                x = seite | ((a + i) & 0xFF)
                self.m[x] &= d
            self.wel = 0; self.besch = self.besch_lesungen; self.programmiert += len(b) - 4
            self.log.append((c, a))
        elif c == 0x20 and len(b) == 4:
            assert self.wel, 'SE ohne WREN'
            a = (b[1] << 16 | b[2] << 8 | b[3]) & ~0xFFF
            self.m[a:a + 0x1000] = bytes([0xFF]) * 0x1000
            self.wel = 0; self.besch = self.besch_lesungen * 5; self.geloescht += 1
            self.log.append((c, a))


class CP1:
    def __init__(self, rom, cp3=True, vorlauf=True, flash=None):
        # 8 KB = EEPROM-Abbild (A12 = P1.4: 1 -> 0x1000..0x1FFF), sonst 4 KB wie bisher
        self.eeprom = len(rom) == 0x2000
        self.rom = bytearray(rom) + bytearray(max(0, 0x1000 - len(rom)))
        self.flash = flash
        self.max_sp = 0
        self.ram = bytearray(128)
        self.a = 0; self.pc = 0; self.psw = 0x08; self.f1 = 0; self.mbf = 0; self.bs = 0
        self.tf = 0; self.t = 0; self.vorteiler = 0; self.timer_an = False; self.tcnti = False; self.ei = False
        self.im_int = False; self.int_wartet = False
        self.p1 = 0xFF; self.p2 = 0xFF
        self.zyk = 0
        self.intern = P8155(); self.cp3 = P8155(cp3)
        self.tasten = []            # (taste, von_us, bis_us)
        self.pi = lambda t: 1       # Pegel, den der Pi auf P1.7 legt (1 = lässt los / high)
        self.geraet = None          # 5.00: Pi-Modell mit zwei Leitungen (t_low/d_low, tick(cp1) je Befehl)
        self.p1_log = []            # (t_us, pegel) Leitung P1.7 bei Änderung
        self._leitung_alt = 1
        self.unbekannt = None
        if vorlauf:                 # Start (Versionsanzeige 1 s) abwarten; danach zählt die Zeit ab 0
            t = 0
            while not (self.ram[0x20] == 0x73 and self.tcnti) and t < 3_000_000:
                t += 10_000; self.bis(t)
            self.zyk = 0; self.p1_log = []

    # --- Hilfen
    @property
    def us(self): return self.zyk * ZYKLUS_US

    def leitung(self):
        g = self.geraet
        return 1 if (self.p1 & 0x80) and self.pi(self.us) and not (g and g.d_low) else 0

    def takt(self):
        """Pegel von T (P1.6, Klemme 7): CP1-Latch und Pi"""
        g = self.geraet
        return 1 if (self.p1 & 0x40) and not (g and g.t_low) else 0

    def _p1(self):
        if self.flash: self.flash.pins(self.p1)

    def _log(self):
        l = self.leitung()
        if l != self._leitung_alt:
            self.p1_log.append((self.us, l)); self._leitung_alt = l

    def r(self, n): return self.ram[(0x18 if self.psw & 0x10 else 0) + n]

    def setr(self, n, v): self.ram[(0x18 if self.psw & 0x10 else 0) + n] = v & 0xFF

    def romlies(self, adr):
        return self.rom[(adr & 0xFFF) | (0x1000 if self.eeprom and self.p1 & 0x10 else 0)]

    def hol(self):
        adr = self.pc
        if self.im_int: adr &= 0x7FF
        if self.eeprom:
            b = self.rom[(adr & 0xFFF) | (0x1000 if self.p1 & 0x10 else 0)]
        else:
            b = self.rom[adr & 0xFFF]
        self.pc = (self.pc & 0x800) | ((self.pc + 1) & 0x7FF)
        return b

    def cy(self): return self.psw >> 7

    def setcy(self, c): self.psw = (self.psw & 0x7F) | (0x80 if c else 0)

    def push(self):
        sp = self.psw & 7
        self.ram[8 + 2 * sp] = self.pc & 0xFF
        self.ram[9 + 2 * sp] = (self.psw & 0xF0) | ((self.pc >> 8) & 0x0F)
        self.psw = (self.psw & 0xF8) | ((sp + 1) & 7)
        self.max_sp = max(self.max_sp, sp + 1)
        if sp + 1 > 7: raise RuntimeError(f'Stapelüberlauf bei {self.pc:#05x}')

    def pop(self, psw_auch):
        sp = (self.psw - 1) & 7
        self.psw = (self.psw & 0xF8) | sp
        lo = self.ram[8 + 2 * sp]; hi = self.ram[9 + 2 * sp]
        self.pc = ((hi & 0x0F) << 8) | lo
        if psw_auch:
            self.psw = (hi & 0xF0) | 0x08 | (self.psw & 7)

    def sprung11(self, adr11):
        b11 = 0 if self.im_int else self.mbf
        self.pc = (b11 << 11) | adr11

    def bedingt(self, cond):
        d = self.hol()
        if cond:
            self.pc = (self.pc & 0xF00) | d if False else ((self.pc - 1) & 0xF00) | d

    def add(self, v, c=0):
        r = self.a + v + c
        ac = ((self.a & 0xF) + (v & 0xF) + c) > 0xF
        self.setcy(r > 0xFF); self.psw = (self.psw & 0xBF) | (0x40 if ac else 0)
        self.a = r & 0xFF

    def movx_chips(self):
        io = bool(self.p2 & 0x80)
        chips = []
        if not self.p2 & 0x10: chips.append(self.intern)
        if not self.p2 & 0x20: chips.append(self.cp3)
        return io, chips

    def tasten_maske(self):
        zeile = 0
        for i in range(8):
            if not self.intern.pc & (1 << i):
                zeile = i; break
        m = 0
        for (k, von, bis) in self.tasten:
            if von <= self.us < bis:
                z, s = TASTEN[k]
                if z == zeile: m |= 1 << s
        return m

    # --- ein Befehl
    def schritt(self):
        if self.int_wartet and not self.im_int:
            self.int_wartet = False; self.im_int = True
            self.push(); self.pc = 7; self.zyk += 2; self._timer(2)
            return
        op = self.hol()
        z = 2 if op in ZWEI else 1
        self.ausfuehren(op)
        self.zyk += z
        self._timer(z)
        self._log()

    def _timer(self, z):
        if not self.timer_an: return
        self.vorteiler += z
        while self.vorteiler >= 32:
            self.vorteiler -= 32
            self.t = (self.t + 1) & 0xFF
            if self.t == 0:
                self.tf = 1
                if self.tcnti: self.int_wartet = True

    def ausfuehren(self, op):
        A = self.a
        lo3 = op & 7
        if op == 0x00: return
        if op == 0x02: return
        if op == 0x03: self.add(self.hol()); return
        if op & 0x1F == 0x04: d = self.hol(); self.sprung11(((op >> 5) << 8) | d); return
        if op == 0x05: self.ei = True; return
        if op == 0x07: self.a = (A - 1) & 0xFF; return
        if op == 0x08: self.a = 0xFF; return
        if op == 0x09:
            so = 0xFF if (self.flash is None or self.flash.cs) else (0xF7 | (self.flash.so << 3))
            self.a = self.p1 & (0x3F | (self.leitung() << 7) | (self.takt() << 6)) & so; return
        if op == 0x0A: self.a = self.p2; return
        if 0x0C <= op <= 0x0F: self.a = self.tasten_maske() & 0x0F; return
        if op in (0x10, 0x11): i = self.r(op & 1) & 0x7F; self.ram[i] = (self.ram[i] + 1) & 0xFF; return
        if op & 0x1F == 0x12: self.bedingt(A & (1 << (op >> 5))); return
        if op == 0x13: self.add(self.hol(), self.cy()); return
        if op & 0x1F == 0x14:
            d = self.hol(); self.push(); self.sprung11(((op >> 5) << 8) | d); return
        if op == 0x15: self.ei = False; return
        if op == 0x16: t = self.tf; self.tf = 0; self.bedingt(t); return
        if op == 0x17: self.a = (A + 1) & 0xFF; return
        if 0x18 <= op <= 0x1F: self.setr(lo3, self.r(lo3) + 1); return
        if op in (0x20, 0x21): i = self.r(op & 1) & 0x7F; self.a, self.ram[i] = self.ram[i], A; return
        if op == 0x23: self.a = self.hol(); return
        if op == 0x25: self.tcnti = True; return
        if op == 0x26: self.bedingt(True); return          # T0 = 0 angenommen
        if op == 0x27: self.a = 0; return
        if 0x28 <= op <= 0x2F: v = self.r(lo3); self.setr(lo3, A); self.a = v; return
        if op in (0x30, 0x31):
            i = self.r(op & 1) & 0x7F; v = self.ram[i]
            self.a = (A & 0xF0) | (v & 0xF); self.ram[i] = (v & 0xF0) | (A & 0xF); return
        if op == 0x35: self.tcnti = False; self.int_wartet = False; return
        if op == 0x36: self.bedingt(False); return
        if op == 0x37: self.a = A ^ 0xFF; return
        if op == 0x39: self.p1 = A; self._p1(); return
        if op == 0x3A: self.p2 = A; return
        if 0x3C <= op <= 0x3F: return
        if op in (0x40, 0x41): self.a = A | self.ram[self.r(op & 1) & 0x7F]; return
        if op == 0x42: self.a = self.t; return
        if op == 0x43: self.a = A | self.hol(); return
        if op == 0x45: self.timer_an = True; return
        if op == 0x46: self.bedingt(False); return
        if op == 0x47: self.a = ((A << 4) | (A >> 4)) & 0xFF; return
        if 0x48 <= op <= 0x4F: self.a = A | self.r(lo3); return
        if op in (0x50, 0x51): self.a = A & self.ram[self.r(op & 1) & 0x7F]; return
        if op == 0x53: self.a = A & self.hol(); return
        if op == 0x55: self.timer_an = True; self.vorteiler = 0; return
        if op == 0x56: self.bedingt(True); return
        if op == 0x57:
            c = self.cy()
            if (A & 0xF) > 9 or self.psw & 0x40:
                A += 6
                if A > 0xFF: c = 1
                A &= 0xFF
            if (A >> 4) > 9 or c:
                A += 0x60; c = 1
            self.a = A & 0xFF; self.setcy(c); return
        if 0x58 <= op <= 0x5F: self.a = A & self.r(lo3); return
        if op in (0x60, 0x61): self.add(self.ram[self.r(op & 1) & 0x7F]); return
        if op == 0x62: self.t = A; return
        if op == 0x65: self.timer_an = False; return
        if op == 0x67: c = A & 1; self.a = (A >> 1) | (self.cy() << 7); self.setcy(c); return
        if 0x68 <= op <= 0x6F: self.add(self.r(lo3)); return
        if op in (0x70, 0x71): self.add(self.ram[self.r(op & 1) & 0x7F], self.cy()); return
        if op == 0x75: return
        if op == 0x76: self.bedingt(self.f1); return
        if op == 0x77: self.a = ((A >> 1) | (A << 7)) & 0xFF; return
        if 0x78 <= op <= 0x7F: self.add(self.r(lo3), self.cy()); return
        if op in (0x80, 0x81):
            io, chips = self.movx_chips(); adr = self.r(op & 1)
            self.a = chips[0].lies(io, adr) if chips else 0xFF; return
        if op == 0x83: self.pop(False); return
        if op == 0x85: self.psw &= ~0x20 & 0xFF; return
        if op == 0x86: self.bedingt(False); return
        if op == 0x88: self.hol(); return
        if op == 0x89: self.p1 |= self.hol(); self._p1(); return
        if op == 0x8A: self.p2 |= self.hol(); return
        if 0x8C <= op <= 0x8F: return
        if op in (0x90, 0x91):
            io, chips = self.movx_chips(); adr = self.r(op & 1)
            for c in chips: c.schreib(io, adr, A)
            return
        if op == 0x93: self.pop(True); self.im_int = False; return
        if op == 0x95: self.psw ^= 0x20; return
        if op == 0x96: self.bedingt(A != 0); return
        if op == 0x97: self.setcy(0); return
        if op == 0x98: self.hol(); return
        if op == 0x99: self.p1 &= self.hol(); self._p1(); return
        if op == 0x9A: self.p2 &= self.hol(); return
        if 0x9C <= op <= 0x9F: return
        if op in (0xA0, 0xA1): self.ram[self.r(op & 1) & 0x7F] = A; return
        if op == 0xA3: self.a = self.romlies((self.pc & 0xF00) | A); return
        if op == 0xA5: self.f1 = 0; return
        if op == 0xA7: self.setcy(1 - self.cy()); return
        if 0xA8 <= op <= 0xAF: self.setr(lo3, A); return
        if op in (0xB0, 0xB1): d = self.hol(); self.ram[self.r(op & 1) & 0x7F] = d; return
        if op == 0xB3:
            seite = (self.pc - 1) & 0xF00
            self.pc = seite | self.romlies(seite | A); return
        if op == 0xB5: self.f1 ^= 1; return
        if op == 0xB6: self.bedingt(self.psw & 0x20); return
        if 0xB8 <= op <= 0xBF: self.setr(lo3, self.hol()); return
        if op == 0xC5: self.psw &= ~0x10 & 0xFF; return
        if op == 0xC6: self.bedingt(A == 0); return
        if op == 0xC7: self.a = self.psw | 0x08; return
        if 0xC8 <= op <= 0xCF: self.setr(lo3, self.r(lo3) - 1); return
        if op in (0xD0, 0xD1): self.a = A ^ self.ram[self.r(op & 1) & 0x7F]; return
        if op == 0xD3: self.a = A ^ self.hol(); return
        if op == 0xD5: self.psw |= 0x10; return
        if op == 0xD7: self.psw = A | 0x08; return
        if 0xD8 <= op <= 0xDF: self.a = A ^ self.r(lo3); return
        if op == 0xE3: self.a = self.romlies((self.pc & 0x800) | 0x300 | A); return
        if op == 0xE5: self.mbf = 0; return
        if op == 0xE6: self.bedingt(not self.cy()); return
        if op == 0xE7: self.a = ((A << 1) | (A >> 7)) & 0xFF; return
        if 0xE8 <= op <= 0xEF:
            v = (self.r(lo3) - 1) & 0xFF; self.setr(lo3, v); self.bedingt(v != 0); return
        if op in (0xF0, 0xF1): self.a = self.ram[self.r(op & 1) & 0x7F]; return
        if op == 0xF5: self.mbf = 1; return
        if op == 0xF6: self.bedingt(self.cy()); return
        if op == 0xF7: c = A >> 7; self.a = ((A << 1) | self.cy()) & 0xFF; self.setcy(c); return
        if 0xF8 <= op <= 0xFF: self.a = self.r(lo3); return
        self.unbekannt = (op, self.pc)
        raise RuntimeError(f'unbekannter Befehl {op:#04x} bei {self.pc - 1:#05x}')

    # --- Laufen
    def bis(self, t_us, halt=None):
        while self.us < t_us:
            self.schritt()
            if self.geraet: self.geraet.tick(self)
            if halt and halt(self): return True
        return False

    def drueck(self, taste, ab_us, dauer_ms=150):
        self.tasten.append((taste, ab_us, ab_us + dauer_ms * 1000))

    def anzeige(self):
        return bytes(self.ram[0x20:0x26])

    def sichtbar(self):
        """Port-A-Muster je Ziffer von links (Ziffer 5 .. 0), so wie sie leuchten (Bit 7 = Punkt)."""
        return bytes(self.intern.ziffer[5 - i] for i in range(6))


SEG = {0x3f: '0', 0x06: '1', 0x5b: '2', 0x4f: '3', 0x66: '4', 0x6d: '5', 0x7d: '6', 0x27: '7', 0x7f: '8', 0x6f: '9',
       0x39: 'C', 0x50: 'r', 0x58: 'c', 0x71: 'F', 0x78: 't', 0x5c: 'o', 0x1c: 'u', 0x5e: 'd', 0x6e: 'Y', 0x40: '-',
       0x08: '_', 0x79: 'E', 0x73: 'P', 0x77: 'A', 0x38: 'L', 0x00: ' ', 0x23: '¬', 0x63: '°', 0x54: 'n', 0x7c: 'b'}


def text(anz):
    """Bildspeicher als Text, Bit 7 (Punkt) wird übergangen."""
    return ''.join(SEG.get(b & 0x7F, '?') for b in anz)


def punkte(m):
    """Welche Ziffern (von links) einen leuchtenden Punkt haben, laut PA7 beim Multiplexen."""
    return [bool(b & 0x80) for b in m.sichtbar()]
