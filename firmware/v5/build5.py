# Firmware 5.x: wie build.py, Bank 1 aus BANK1 (Text), RC-Teile aus v4/
import os
AUS=os.environ.get('AUS','v5/cp1v5')
RC_UNTEN=os.environ.get('RC_UNTEN','v5/rc_unten.asm')
RC_SEITE3=os.environ.get('RC_SEITE3','v5/rc_seite3.asm')
BANK1=''.join(open(f,encoding='utf-8').read()+'\n' for f in os.environ.get('BANK1','v5/schnell5.asm,v5/stummel_a.asm,v5/flash5.asm,v5/stummel_b.asm').split(','))
# baut cp1schnell.asm aus cp1.asm + schnell.asm, assembliert, vergleicht mit dem Original
import sys, re, subprocess, hashlib
src=open('cp1.asm',encoding='latin-1').read()
def rep(a,b):
    global src
    assert src.count(a)==1, a
    src=src.replace(a,b)
rep("cas_handler:    CALL clear_display\n                CALL clear_access_ram_extension_status_bit\n",
    "cas_handler:    SEL  MB1            ; -> schnelle Kassette (0x800)\n                JMP  s_cas\n                NOP\n")
rep("cal_handler:    CALL clear_display\n                CALL clear_access_ram_extension_status_bit\n",
    "cal_handler:    SEL  MB1            ; -> schnelle Kassette (0x800)\n                JMP  s_cal\n                NOP\n")
# je genau so viele Bytes wie im Original ersetzen (sonst verschiebt sich alles dahinter)
rep("opcode_UND:     MOV  R0, #ACCU      ; Load Accu's MSB...\n                MOV  A, @R0         ; ... into A\n",
    "opcode_UND:     SEL  MB1            ; -> UND bitweise (0xD00)\n                JMP  s_und\n")
rep(".db  <opcode_ANZ             ; opcode 02: ANZ", ".db  <anz_neu               ; opcode 02: ANZ -> 0xD00 (ANZ 001 mit Vorzeichen)")
# 4.03: Punkt-Leitung an PA7 (Michael: Überspannungs-Treiber an 8155 Pin 28, alle DP verbunden, Trennung nicht mehr fest).
# Der Trennpunkt ist nicht mehr fest verdrahtet: wait_key (Leerlauf, Normalbetrieb) setzt Bit 7 bei Ziffer 3.
# SEG/ANZ/laufende Programme laufen nicht durch wait_key -> dort nur Punkte, die das Programm selbst setzt.
DP_ISR = """dp_warte:       MOV  R0, #$22       ; Ziffer 3: Trennpunkt (Bit 7 -> PA7) im Normalbetrieb
                MOV  A, @R0
                ORL  A, #$80
                MOV  @R0, A
                MOV  R0, #$1e       ; wie bisher: R6' (Taste)
                RET
"""
# alter NEG-Rumpf (23 Byte) ist tot, seit NEG nach 0xD00 springt: dort anz_neu, Rest NOP
i0 = src.index("opcode_NEG:"); i1 = src.index("error_f005:     MOV  R4, #$05")
src = src[:i0] + "opcode_NEG:     SEL  MB1            ; -> NEG mit Maske (0xD00)\n                JMP  s_neg\nanz_neu:        SEL  MB1            ; -> ANZ (0xD00)\n                JMP  s_anz\nneg_was_zero:\nneg_done:\n" + DP_ISR + "                NOP\n" * 8 + "\n" + src[i1:]
rep("error_f006:     MOV  R4, #$06\n                JMP  show_error     ; F-006\n",
    "error_f006:     SEL  MB1            ; -> OVF-Schalter (0xD00)\n                JMP  s_f006\n                NOP\n")
rep("ADD  A, #$e7        ; add (256 - 25) to check for max opcode",
    "ADD  A, #$d0        ; (256 - 48): INP nimmt Befehle bis 47 an (5.06: 40..46 mit festem Wert, 47 SEF)")
# 5.06: Marken hinter den Zellenprüfungen von ADD/VGL/VGR/VKL für die Befehle mit festem Wert (nur Marken, Bytes gleich)
rep("                JF1  execute_sub_trampoline ; if F1 is set, it's a SUB\n",
    "add_imm:        JF1  execute_sub_trampoline ; if F1 is set, it's a SUB\n")
rep("                MOVX A, @R1         ; Load operand cell content LSB\n                XRL  A, @R0         ; Compare to Accu LSB\n",
    "vgl_imm:        MOVX A, @R1         ; Load operand cell content LSB\n                XRL  A, @R0         ; Compare to Accu LSB\n")
rep("                MOVX A, @R1         ; Load operand cell content LSB\n                JZ   vgl_end        ; if zero, no need to compare\n",
    "vkl_imm:        MOVX A, @R1         ; Load operand cell content LSB\n                JZ   vgl_end        ; if zero, no need to compare\n")
rep("                MOV  A, @R0         ; Load Accu LSB\n                JZ   vgl_end        ; If zero, it can't be greater than anything\n",
    "vgr_imm:        MOV  A, @R0         ; Load Accu LSB\n                JZ   vgl_end        ; If zero, it can't be greater than anything\n")
rep("                MOV  @R0, A         ; store entered number in PC\n                MOV  R6, #$00       ; reset # of entered digits\n                JMP  wait_key\n",
    "                MOV  @R0, A         ; store entered number in PC\n                SEL  MB1            ; -> PC gesetzt: JSR-Stapel leeren (0xF00)\n                JMP  s_pcset\n                NOP\n")
rep("opcode_inv:     MOV  R4, #$02       ; F-002\n                JMP  show_error\n",
    "opcode_inv:     SEL  MB1            ; -> Befehl 25 ODR oder F-002 (0xD00)\n                JMP  s_inv\n                NOP\n")
rep("wait_key:       MOV  R0, #$1e       ; Wait for key press: 0x1e is R6', used in interrupt\n",
    "wait_key:       CALL dp_warte       ; 4.03: Trennpunkt setzen, R0 = 0x1e (2 Byte gegen 2 Byte)\n")
# Fernsteuerung: Hook im Timer-Interrupt (2 Byte gegen 2 Byte)
rep("                MOVD A, P4          ; ????? write to lower nibble of port 2, then read from it? why not just read from it?\n                CLR  C\n",
    "                CALL rc_tast        ; Fernsteuerung: P1.7 abfragen, Ferntaste dazumischen (liest MOVD A, P4; CLR C)\n")
# toter Rest der alten CAL-Routine (0x712..0x7E0) -> Fernsteuerung im Interrupt
i0 = src.index("                MOV  R0, #VRAM      ; Set left-most digit...\n                MOV  @R0, #$1c")
i1 = src.index("; Clear result of last comparison in status byte")
src = src[:i0] + open(RC_UNTEN,encoding='utf-8').read() + "\n                .org $7e1\n" + src[i1:]
# toter Rest der alten CAS-Routine (0x1C8..0x1FE) -> Fernsteuerung Teil 2
i0 = src.index("                MOV  R0, #VRAM      ; Set left-most digit...\n                MOV  @R0, #$23")
i1 = src.index("out_handler:\n")
src = src[:i0] + open('v5/rc_seite1.asm',encoding='utf-8').read() + "\n                .org $1ff\n" + src[i1:]
rep("                JMP  save_done\n\ncas_handler:", "                JMP  wait_key       ; (tot)\n\ncas_handler:")
# VZG: in Hälfte A warten und dabei Zifferntasten für TSE merken (3 Byte gegen 3 Byte)
rep("opcode_VZG:     MOVX A, @R1         ; load operand into A\n                JZ   end_VZG        ; if zero, no delay necessary\n",
    "opcode_VZG:     SEL  MB1            ; -> VZG mit Tastengedächtnis (Hälfte A)\n                JMP  s_vzg\n")
# OUT P1A: interne Leitungen schützen (3 Byte gegen 3 Byte)
rep("write_to_p1:    OUTL P1, A          ; write byte to 8049 port 1\n                JMP  inc_pc\n",
    "write_to_p1:    SEL  MB1            ; -> P1.0-P1.4, P1.7 bleiben 1 (Hälfte A)\n                JMP  s_p1aus\n")
# Start: Firmware-Version 1 s zeigen (4 Byte gegen 4 Byte)
rep("                CALL clear_ram\n                EN   TCNTI          ; enable Timer/Counter interrupts\n                STRT T              ; and start the timer\n",
    "                SEL  MB1            ; -> Version zeigen, dann wie bisher (0xE00)\n                JMP  s_boot\n                NOP\n")
# tote alte CAS-Sende-Routine (0x3BD..0x3F2) -> Fernsteuerung Teil 3
i0 = src.index("save_memory:\n                MOV  R1, #$00")
i1 = src.index("clear_access_ram_extension_status_bit:\n")
src = src[:i0] + open(RC_SEITE3,encoding='utf-8').read() + "\n                .org $3f3\n\n" + src[i1:]
# RUN: 1 s halten schaltet die Fernsteuerung (3 Byte gegen 3 Byte)
rep("run_handler:    MOV  A, R6          ; Load # of entered digits\n                XRL  A, #$01        ; is it 1?\n                JNZ  not_one        ; jump if not.\n",
    "run_handler:    SEL  MB1            ; -> RUN halten = Fernsteuerung an/aus (0xE00)\n                JMP  s_run\nrun_weiter:     JNZ  not_one        ; jump if not.\n")
import importlib.util as _iu, sys as _s
_s.path.insert(0,'v5'); import unten5
src = unten5.anwenden(src, rep)
src += "\n" + BANK1
open(AUS+'.asm','w',encoding='latin-1',errors='replace').write(src)
sys.path.insert(0,'.'); import asm48
# Seiten einpassen: bedingter Sprung über eine Seitengrenze -> Absatz (Block bis zur Leerzeile) auf die nächste Seite.
# 5.00: dazu ein Lückenfüller (packer.py): kleine verschiebbare Absätze wandern vor eine Lücke.
start_b1 = src.count('\n', 0, src.index(BANK1[:200])) + 1
import packer, re as _re

def _fit(text, groesse):
    for runde in range(80):
        open(AUS+'.asm','w',encoding='latin-1',errors='replace').write(text)
        try:
            r, s = asm48.assembliere(AUS+'.asm',0xff,groesse); return text, r, s
        except SystemExit as e:
            m=_re.match(r'Zeile (\d+): .*Sprungziel', str(e))
            if not m: raise
            z=text.split('\n'); n=int(m.group(1))-1
            assert n>=start_b1, e
            while n>start_b1 and z[n-1].strip(): n-=1
            if z[n].strip()=='.seite': raise SystemExit(f'Absatz passt in keine Seite: {e}')
            z.insert(n,'                .seite'); text='\n'.join(z)
    raise SystemExit('kein Ende')

def _pcs(text, sym):
    """pc vor jeder Zeile"""
    out=[]; pc=0
    for nr, lab, m, ops in asm48.zeilen_text(text) if hasattr(asm48,'zeilen_text') else []:
        pass
    z=text.split('\n'); pc=0; res=[0]*(len(z)+1)
    for nr, lab, m, ops in asm48.zeilen(AUS+'.asm'):
        res[nr-1]=pc
        if m is None or m=='.EQU': continue
        if m=='.ORG': pc=asm48.zahl(ops[0],sym); res[nr-1]=pc; continue
        if m=='.SEITE': pc=(pc+0xff)&~0xff; continue
        pc+= len(ops) if m=='.DB' else len(asm48.befehl(m,ops,pc,sym))
    return res

ST = int(re.search(r'\.org \$([0-9a-f]+)', open('v5/stummel_a.asm').read()).group(1), 16)   # Stummel-Anfang (gen_stummel.py)
basis = src
for packrunde in range(40):
    weit = basis.replace(f'                .org ${ST:x}\n',f'                .org ${ST+0x2000:x}\n',1).replace(f'                .org ${ST+0x1000:x}\n',f'                .org ${ST+0x3000:x}\n',1)
    gefittet, rom, sym = _fit(weit, 0x4000)
    a_ende = max([v for k,v in sym.items() if 0x800<=v<0x1000 and not k.startswith(('za_','zb_'))] + [0])
    b_ende = max([v for k,v in sym.items() if 0x1800<=v<ST+0x2000 and not k.startswith('b_')] + [0])
    code_a = max([i for i in range(0x800,0x1800) if rom[i]!=0xff]+[0]); code_b = max([i for i in range(0x1800,ST+0x2000) if rom[i]!=0xff]+[0])
    # 5.06: code_a sucht bis 0x17FF – Code jenseits 0xFFF fiel vorher still aus dem EEPROM
    zu_viel = [h for h, e, g in (('A', code_a, ST), ('B', code_b, ST+0x1000)) if e >= g]
    if not zu_viel: break
    z = gefittet.split('\n'); pcs = _pcs(gefittet, sym)
    luecken = []
    for n, l in enumerate(z):
        if l.strip() == '.seite' and n >= start_b1:
            pc = pcs[n]; luecke = ((pc + 0xff) & ~0xff) - pc
            haelfte = 'A' if 0x800 <= pc < 0x1000 else 'B' if pc >= 0x1800 else None
            if haelfte in zu_viel and luecke:
                k = n + 1
                while k < len(z) and not packer._zerlege(z[k])[0]: k += 1
                if k < len(z): luecken.append((luecke, haelfte, packer._zerlege(z[k])[0]))
    zb = basis.split('\n')
    getan = False
    for luecke, haelfte, marke in sorted(luecken, reverse=True):
        ziel = next(i for i, l in enumerate(zb) if packer._zerlege(l)[0] == marke)
        while ziel > 0 and zb[ziel-1].strip(): ziel -= 1
        bereich_ende = next(i for i, l in enumerate(zb) if i > ziel and (f'.org ${ST:x}' in l if haelfte == 'A' else f'.org ${ST+0x1000:x}' in l))
        kand = [(g, a, e) for a, e, g in packer.verschiebbare(zb, ziel, bereich_ende, asm48) if a > ziel and g <= luecke]
        if not kand: continue
        g, a, e = max(kand)
        block = zb[a:e]
        zb = zb[:a] + zb[e:]
        zb = zb[:ziel] + block + [''] + zb[ziel:]
        basis = '\n'.join(zb); getan = True
        print(f'  Lückenfüller: {packer._zerlege(block[0])[0] or block[0].strip()[:20]} ({g} Byte) vor {marke} (Lücke {luecke})')
        break
    if not getan: raise SystemExit(f'Hälfte {zu_viel} zu voll (A bis {code_a:#x}, B bis {code_b:#x}, Grenze {ST:#x}/{ST+0x1000:#x}), kein passender Absatz für die Lücken')
src, rom, sym = _fit(basis, int(os.environ.get('GROESSE','0x2000'),0))
open(AUS+'.bin','wb').write(rom)
# Sicherung: vor jeder eingefügten .seite muss der Code unbedingt enden (sonst liefe er in die FF-Lücke)
_z = open(AUS+'.asm',encoding='latin-1').read().split('\n')
for _n, _l in enumerate(_z):
    if _l.strip().lower() == '.seite' and _n >= start_b1:
        _k = _n - 1
        while _k > 0 and (not _z[_k].split(';')[0].strip() or _z[_k].split(';')[0].strip().endswith(':')): _k -= 1
        _code = _z[_k].split(';')[0].strip()
        _mn = _code.split(':')[-1].split()[0].upper() if _code.split(':')[-1].split() else ''
        if _mn not in ('JMP', 'RET', 'RETR', 'JMPP', '.DB', '.SEITE', '.ORG'):
            raise SystemExit(f'.seite nach durchlaufendem Code (Zeile {_k+1}: {_z[_k].strip()})')
orig,_=asm48.assembliere('cp1.asm',0x00,0x800)
d=[i for i in range(0x800) if rom[i]!=orig[i]]
print('Unterschiede im Original-Bereich:',[hex(i) for i in d])
frei_a=sum(1 for i in range(0x800,0x1000) if rom[i]==0xff); frei_b=sum(1 for i in range(0x1800,0x2000) if rom[i]==0xff)
print(f'frei (FF, grob): Hälfte A {frei_a}, Hälfte B {frei_b}')
# Sprungprüfung: aus B nur nach B, nach unten (<0x800) oder in Stummel za_*; aus A nie nach B
import re as _r
for nr,lab,m,ops in asm48.zeilen(AUS+'.asm'):
    pass
eeprom = bytes(rom[0:0x800]) + bytes(rom[0x1800:0x2000]) + bytes(rom[0:0x1000])
open(AUS+'-eeprom.bin','wb').write(eeprom)
open(AUS+'.sym','w').write('\n'.join(f'{v:04x} {k}' for k,v in sorted(sym.items(),key=lambda x:x[1])))
