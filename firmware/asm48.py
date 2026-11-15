#!/usr/bin/env python3
"""Kleiner MCS-48-Assembler (8048/8049) für cp1.asm: asm48.py quelle.asm ausgabe.bin [--fill 0xff] [--size 0x800]
Syntax wie asm48: .org/.equ/.db, Zahlen $hex oder dezimal, <label = Low-Byte, Kommentare mit ;"""
import re, sys

R = {f'R{i}': i for i in range(8)}
RI = {'@R0': 0, '@R1': 1}
EINFACH = {
    'NOP': 0x00, 'RET': 0x83, 'RETR': 0x93, 'CLR A': 0x27, 'CPL A': 0x37, 'DA A': 0x57, 'SWAP A': 0x47,
    'RL A': 0xE7, 'RLC A': 0xF7, 'RR A': 0x77, 'RRC A': 0x67, 'INC A': 0x17, 'DEC A': 0x07,
    'CLR C': 0x97, 'CPL C': 0xA7, 'CLR F0': 0x85, 'CPL F0': 0x95, 'CLR F1': 0xA5, 'CPL F1': 0xB5,
    'IN A,P1': 0x09, 'IN A,P2': 0x0A, 'INS A,BUS': 0x08, 'OUTL BUS,A': 0x02, 'OUTL P1,A': 0x39, 'OUTL P2,A': 0x3A,
    'JMPP @A': 0xB3, 'MOVP A,@A': 0xA3, 'MOVP3 A,@A': 0xE3, 'MOV A,PSW': 0xC7, 'MOV PSW,A': 0xD7,
    'MOV A,T': 0x42, 'MOV T,A': 0x62, 'STRT T': 0x55, 'STRT CNT': 0x45, 'STOP TCNT': 0x65,
    'EN TCNTI': 0x25, 'DIS TCNTI': 0x35, 'EN I': 0x05, 'DIS I': 0x15, 'SEL RB0': 0xC5, 'SEL RB1': 0xD5,
    'SEL MB0': 0xE5, 'SEL MB1': 0xF5, 'ENT0 CLK': 0x75,
}
# Befehl A,x mit Basis für Rr, @Ri, #d
ALU = {'ADD': (0x68, 0x60, 0x03), 'ADDC': (0x78, 0x70, 0x13), 'ANL': (0x58, 0x50, 0x53),
       'ORL': (0x48, 0x40, 0x43), 'XRL': (0xD8, 0xD0, 0xD3), 'MOV': (0xF8, 0xF0, 0x23),
       'XCH': (0x28, 0x20, None), 'XCHD': (None, 0x30, None)}
SPRUNG = {'JC': 0xF6, 'JNC': 0xE6, 'JZ': 0xC6, 'JNZ': 0x96, 'JT0': 0x36, 'JNT0': 0x26, 'JT1': 0x56,
          'JNT1': 0x46, 'JF0': 0xB6, 'JF1': 0x76, 'JTF': 0x16, 'JNI': 0x86}
SPRUNG.update({f'JB{b}': (b << 5) | 0x12 for b in range(8)})


def zahl(s, sym):
    s = s.strip()
    if s.startswith('<'):
        return zahl(s[1:], sym) & 0xFF
    if s.startswith('>'):
        return zahl(s[1:], sym) >> 8
    if s.startswith('$'):
        return int(s[1:], 16)
    if re.fullmatch(r'[0-9]+', s):
        return int(s)
    if s in sym:
        return sym[s]
    raise KeyError(s)


def befehl(m, ops, pc, sym):
    """Bytes eines Befehls; sym darf im 1. Durchlauf unvollständig sein"""
    o = [x.upper() if x.upper() in R or x.upper() in RI or x.upper() in ('A', 'C', 'T', 'BUS', 'PSW') or
         re.fullmatch(r'P[1-7]', x.upper()) else x for x in ops]
    k = (m + ' ' + ','.join(o)).strip()
    if k in EINFACH:
        return [EINFACH[k]]
    w = lambda s: zahl(s, sym)
    if m in ('JMP', 'CALL'):
        a = w(ops[0])
        return [((a >> 8) & 7) << 5 | (0x04 if m == 'JMP' else 0x14), a & 0xFF]
    if m in SPRUNG or m == 'DJNZ':
        if m == 'DJNZ':
            op, ziel = 0xE8 + R[o[0]], ops[1]
        else:
            op, ziel = SPRUNG[m], ops[0]
        a = w(ziel)
        if (a >> 8) != ((pc + 1) >> 8):
            raise ValueError(f'Sprungziel {a:#x} nicht in der Seite von {pc:#x}')
        return [op, a & 0xFF]
    if m in ALU and len(o) == 2 and o[0] == 'A':
        r, i, imm = ALU[m]
        if o[1] in R and r is not None:
            return [r + R[o[1]]]
        if o[1] in RI:
            return [i + RI[o[1]]]
        if imm is not None:
            v = o[1][1:] if o[1].startswith('#') else o[1]
            return [imm, w(v) & 0xFF]
    if m == 'MOV':
        if o[0] in R and o[1] == 'A':
            return [0xA8 + R[o[0]]]
        if o[0] in RI and o[1] == 'A':
            return [0xA0 + RI[o[0]]]
        if o[0] in R and o[1].startswith('#'):
            return [0xB8 + R[o[0]], w(o[1][1:]) & 0xFF]
        if o[0] in RI and o[1].startswith('#'):
            return [0xB0 + RI[o[0]], w(o[1][1:]) & 0xFF]
    if m == 'INC':
        if o[0] in R:
            return [0x18 + R[o[0]]]
        if o[0] in RI:
            return [0x10 + RI[o[0]]]
    if m == 'DEC' and o[0] in R:
        return [0xC8 + R[o[0]]]
    if m in ('ANL', 'ORL') and o[0] in ('BUS', 'P1', 'P2') and o[1].startswith('#'):
        base = {'ANL': 0x98, 'ORL': 0x88}[m] + ('BUS', 'P1', 'P2').index(o[0])
        return [base, w(o[1][1:]) & 0xFF]
    if m == 'MOVX':
        if o[0] == 'A' and o[1] in RI:
            return [0x80 + RI[o[1]]]
        if o[0] in RI and o[1] == 'A':
            return [0x90 + RI[o[0]]]
    if m == 'MOVD':
        if o[0] == 'A':
            return [0x0C + int(o[1][1]) - 4]
        return [0x3C + int(o[0][1]) - 4]
    if m in ('ANLD', 'ORLD'):
        return [{'ANLD': 0x9C, 'ORLD': 0x8C}[m] + int(o[0][1]) - 4]
    raise ValueError(f'unbekannt: {k}')


def zeilen(quelle):
    for nr, z in enumerate(open(quelle, encoding='latin-1'), 1):
        z = z.split(';', 1)[0].rstrip()
        lab = None
        mt = re.match(r'^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$', z.strip())
        rest = z.strip()
        if mt:
            lab, rest = mt.group(1), mt.group(2)
        if not rest:
            yield nr, lab, None, []
            continue
        teile = rest.split(None, 1)
        ops = [x.strip() for x in teile[1].split(',')] if len(teile) > 1 else []
        yield nr, lab, teile[0].upper(), ops


def assembliere(quelle, fill, size):
    sym, rom = {}, None
    for durchlauf in (1, 2):
        pc, rom, belegt = 0, bytearray([fill]) * size, set()
        for nr, lab, m, ops in zeilen(quelle):
            if lab:
                if durchlauf == 1:
                    if lab in sym:
                        raise ValueError(f'Zeile {nr}: {lab} doppelt')
                    sym[lab] = pc
            if m is None:
                continue
            if m == '.EQU':
                sym[ops[0]] = zahl(ops[1], sym)
                continue
            if m == '.ORG':
                pc = zahl(ops[0], sym)
                continue
            if m == '.SEITE':           # auf den Anfang der nächsten Seite (falls nicht schon dort)
                pc = (pc + 0xFF) & ~0xFF
                continue
            try:
                if m == '.DB':
                    b = []
                    for x in ops:
                        try:
                            b.append(zahl(x, sym) & 0xFF)
                        except KeyError:
                            if durchlauf == 2:
                                raise
                            b.append(0)
                else:
                    try:
                        b = befehl(m, ops, pc, sym)
                    except (KeyError, ValueError):
                        if durchlauf == 2:
                            raise
                        # 1. Durchlauf: nur die Länge zählt
                        if m in SPRUNG or m in ('JMP', 'CALL', 'DJNZ'):
                            b = [0, 0]
                        else:
                            b = befehl(m, [x if not x.startswith(('#', '<')) else '#0' for x in ops], pc, {})
            except Exception as e:
                raise SystemExit(f'Zeile {nr}: {m} {",".join(ops)}: {e}')
            for x in b:
                if durchlauf == 2:
                    if pc in belegt:
                        raise SystemExit(f'Zeile {nr}: Adresse {pc:#x} doppelt belegt')
                    belegt.add(pc)
                    rom[pc] = x
                pc += 1
    return rom, sym


if __name__ == '__main__':
    a = sys.argv[1:]
    fill = int(a[a.index('--fill') + 1], 0) if '--fill' in a else 0x00
    size = int(a[a.index('--size') + 1], 0) if '--size' in a else 0x800
    rom, sym = assembliere(a[0], fill, size)
    open(a[1], 'wb').write(rom)
    if '--sym' in a:
        for n, v in sorted(sym.items(), key=lambda x: -x[1]):
            print(f'{v:08X}\t{n}')
