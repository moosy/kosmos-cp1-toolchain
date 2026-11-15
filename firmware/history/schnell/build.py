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
# alter NEG-Rumpf (23 Byte) ist tot, seit NEG nach 0xD00 springt: dort anz_neu, Rest NOP
i0 = src.index("opcode_NEG:"); i1 = src.index("error_f005:     MOV  R4, #$05")
src = src[:i0] + "opcode_NEG:     SEL  MB1            ; -> NEG mit Maske (0xD00)\n                JMP  s_neg\nanz_neu:        SEL  MB1            ; -> ANZ (0xD00)\n                JMP  s_anz\nneg_was_zero:\nneg_done:\n" + "                NOP\n" * 17 + "\n" + src[i1:]
rep("error_f006:     MOV  R4, #$06\n                JMP  show_error     ; F-006\n",
    "error_f006:     SEL  MB1            ; -> OVF-Schalter (0xD00)\n                JMP  s_f006\n                NOP\n")
rep("ADD  A, #$e7        ; add (256 - 25) to check for max opcode",
    "ADD  A, #$dc        ; (256 - 36): INP nimmt Befehle bis 35 an (ODR, OVF, SEG, AS1-3, TST, JSR, RET, PSH, POP)")
rep("                MOV  @R0, A         ; store entered number in PC\n                MOV  R6, #$00       ; reset # of entered digits\n                JMP  wait_key\n",
    "                MOV  @R0, A         ; store entered number in PC\n                SEL  MB1            ; -> PC gesetzt: JSR-Stapel leeren (0xF00)\n                JMP  s_pcset\n                NOP\n")
rep("opcode_inv:     MOV  R4, #$02       ; F-002\n                JMP  show_error\n",
    "opcode_inv:     SEL  MB1            ; -> Befehl 25 ODR oder F-002 (0xD00)\n                JMP  s_inv\n                NOP\n")
# Fernsteuerung: Hook im Timer-Interrupt (2 Byte gegen 2 Byte)
rep("                MOVD A, P4          ; ????? write to lower nibble of port 2, then read from it? why not just read from it?\n                CLR  C\n",
    "                CALL rc_tast        ; Fernsteuerung: P1.7 abfragen, Ferntaste dazumischen (liest MOVD A, P4; CLR C)\n")
# toter Rest der alten CAL-Routine (0x712..0x7E0) -> Fernsteuerung im Interrupt
i0 = src.index("                MOV  R0, #VRAM      ; Set left-most digit...\n                MOV  @R0, #$1c")
i1 = src.index("; Clear result of last comparison in status byte")
src = src[:i0] + open('rc_unten.asm',encoding='utf-8').read() + "\n                .org $7e1\n" + src[i1:]
# toter Rest der alten CAS-Routine (0x1C8..0x1FE) -> Fernsteuerung Teil 2
i0 = src.index("                MOV  R0, #VRAM      ; Set left-most digit...\n                MOV  @R0, #$23")
i1 = src.index("out_handler:\n")
src = src[:i0] + open('rc_seite1.asm',encoding='utf-8').read() + "\n                .org $1ff\n" + src[i1:]
rep("                JMP  save_done\n\ncas_handler:", "                JMP  wait_key       ; (tot)\n\ncas_handler:")
# Start: Firmware-Version 1 s zeigen (4 Byte gegen 4 Byte)
rep("                CALL clear_ram\n                EN   TCNTI          ; enable Timer/Counter interrupts\n                STRT T              ; and start the timer\n",
    "                SEL  MB1            ; -> Version zeigen, dann wie bisher (0xE00)\n                JMP  s_boot\n                NOP\n")
# tote alte CAS-Sende-Routine (0x3BD..0x3F2) -> Fernsteuerung Teil 3
i0 = src.index("save_memory:\n                MOV  R1, #$00")
i1 = src.index("clear_access_ram_extension_status_bit:\n")
src = src[:i0] + open('rc_seite3.asm',encoding='utf-8').read() + "\n                .org $3f3\n\n" + src[i1:]
# RUN: 1 s halten schaltet die Fernsteuerung (3 Byte gegen 3 Byte)
rep("run_handler:    MOV  A, R6          ; Load # of entered digits\n                XRL  A, #$01        ; is it 1?\n                JNZ  not_one        ; jump if not.\n",
    "run_handler:    SEL  MB1            ; -> RUN halten = Fernsteuerung an/aus (0xE00)\n                JMP  s_run\nrun_weiter:     JNZ  not_one        ; jump if not.\n")
src += "\n" + open('schnell.asm',encoding='utf-8').read()
open('cp1schnell.asm','w',encoding='latin-1',errors='replace').write(src)
sys.path.insert(0,'.'); import asm48
rom,sym=asm48.assembliere('cp1schnell.asm',0xff,0x1000)
open('cp1schnell.bin','wb').write(rom)
orig,_=asm48.assembliere('cp1.asm',0x00,0x800)
d=[i for i in range(0x800) if rom[i]!=orig[i]]
print('Unterschiede im Original-Bereich:',[hex(i) for i in d])
ende=max(i for i in range(0x800,0x1000) if rom[i]!=0xff)
print(f'eigener Code: 0x800..{ende:#x} = {ende-0x7ff} Byte')
open('cp1schnell.sym','w').write('\n'.join(f'{v:04x} {k}' for k,v in sorted(sym.items(),key=lambda x:x[1])))
