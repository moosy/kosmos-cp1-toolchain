# 5.00: Änderungen in den unteren 2 KB (beide Hälften gleich). Wird von build5.py nach den 4.x-Änderungen ausgeführt.
# Jeder neue Block endet mit .org auf die alte Folgeadresse: zu lang -> Assembler meldet „doppelt belegt“.

P4A = """
; ---- 5.00 (toter VZG-Rumpf): NIE-Antwortbyte holen, aus rt_sende (Seite 3).  A = Adresse -> A = Byte.
; RC_FLAG Bit 7: aus der 8155 lesen (Bit 1: CP3), sonst internes RAM. Benutzt R0, R3.
rs_hol:         MOV  R3, A
                MOV  R0, #RC_FLAG
                MOV  A, @R0
                JB7  rh_8155
                MOV  A, R3
                MOV  R0, A
                MOV  A, @R0
                RET
                .org $48f
"""

P4C = """
; ---- 5.00 (toter UND/ANZ-Rumpf)
                .equ LEER,    $16       ; 1 = wait_key läuft (nur das Hauptprogramm schreibt)
                .equ AUFTRAG, $17       ; $0D = Auftrag wartet (nur NIE 04 setzt, wait_key löscht)
; dp_warte: aus wait_key bei jedem Durchlauf. Trennpunkt bei Ziffer 3 setzen, Leerlauf melden (LEER = 1).
; Hat NIE 04 einen Auftrag angenommen, steht in AUFTRAG der CAL-Tastencode $0D: R0 zeigt dann dorthin,
; wait_key liest ihn wie eine Taste, löscht ihn selbst und springt über cal_handler nach k_cal_vor.
; LEER und AUFTRAG liegen in der nie benutzten 8. Stapelebene; jede Seite schreibt nur ihr eigenes Byte
; (kein Lesen-Ändern-Schreiben zwischen Hauptprogramm und Interrupt).
dp_warte:       MOV  R0, #$21           ; Ziffer 2: kein Punkt (das Eintippen schiebt den Trennpunkt sonst nach links)
                MOV  A, @R0
                ANL  A, #$7f
                MOV  @R0, A
                INC  R0                 ; Ziffer 3: Trennpunkt
                MOV  A, @R0
                ORL  A, #$80
                MOV  @R0, A
                MOV  R0, #AUFTRAG
                MOV  A, @R0
                JNZ  dw_auftrag
                DEC  R0                 ; LEER
                MOV  @R0, #$01
                MOV  R0, #$1e           ; wie bisher: R6' (Taste)
                RET
dw_auftrag:     MOV  R1, #LEER          ; kein Leerlauf mehr (R1 setzt wait_key gleich neu)
                MOV  @R1, #$00
                RET
; rh_8155: Fortsetzung von rs_hol: Byte aus der 8155 (im Interrupt; danach wie am Interrupt-Anfang)
rh_8155:        ANL  P2, #$7f           ; 8155: Speicher
                JB1  rh_cp3
rh_l:           MOV  A, R3
                MOV  R0, A
                MOVX A, @R0
                ORL  P2, #$a0           ; E/A, CP3 ab
                ANL  P2, #$ef           ; interne an
                RET
                .org $4ef
"""

P6A = """demo_9:         SEL  MB1            ; Demos (9 RUN Countdown, 8 RUN Reaktionstest) liegen ab 5.00 in Hälfte A
                JMP  s_demo9
demo_8:         SEL  MB1
                JMP  s_demo8

; ---- 5.00 NIE-Verteiler, Fortsetzung von rc_befehl (Seite 7), A = Befehl ^ 3
rb_mehr:        XRL  A, #$02            ; ^1
                JNZ  rm_1
                JMP  rb_taste           ; 01 Taste
rm_1:           XRL  A, #$05            ; ^4
                JZ   rb_auftrag         ; 04 Auftrag (Attention)
                XRL  A, #$01            ; ^5
                JZ   rb_lies_i          ; 05 interne 8155 lesen
                XRL  A, #$03            ; ^6
                JZ   rb_lies_c          ; 06 CP3 lesen
                XRL  A, #$01            ; ^7
                JZ   rb_schr_i          ; 07 interne 8155 schreiben
                XRL  A, #$0f            ; ^8
                JZ   rb_schr_c          ; 08 CP3 schreiben
                XRL  A, #$01            ; ^9
                JZ   rb_reset_s         ; 09 Reset (5.02)
                JMP  rb_ende
rb_reset_s:     JMP  rb_reset

; 07 aa ww / 08 aa ww: Byte aa der internen / CP3-8155 = ww (auch bei laufendem Programm)
rb_schr_c:      ANL  P2, #$df           ; CP3 an
                ORL  P2, #$10           ; interne ab
rb_schr_i:      ANL  P2, #$7f           ; Speicher
                MOV  R0, #RC_P1
                MOV  A, @R0
                MOV  R1, A              ; (R1 holt rb_ende zurück)
                INC  R0
                MOV  A, @R0
                MOVX @R1, A
                ORL  P2, #$a0
                ANL  P2, #$ef
                JMP  rb_quitt
                .org $6b4

"""

P6B = """; ---- 5.00: 04 jj 00 = Auftrag jj übernehmen, wenn Leerlauf (LEER) und kein Auftrag wartet (AUFTRAG = 0).
; Antwort 1 Byte = F_JOB danach (= jj: angenommen).
rb_auftrag:     MOV  R0, #AUFTRAG
                MOV  A, @R0
                JNZ  ra_antw            ; es wartet schon einer
                DEC  R0
                MOV  A, @R0
                JZ   ra_antw            ; kein Leerlauf
                INC  R0
                MOV  @R0, #$0d          ; = Taste CAL für wait_key
                MOV  R0, #RC_P1
                MOV  A, @R0
                MOV  R0, #F_JOB
                MOV  @R0, A
ra_antw:        MOV  R0, #RC_P1
                MOV  @R0, #F_JOB
                INC  R0
                MOV  @R0, #$01
                JMP  rl_start
; 05 aa nn / 06 aa nn: nn Byte ab Byte aa der internen / CP3-8155 (Zelle z: Byte 2z Befehl, 2z+1 Argument)
rb_lies_c:      MOV  R3, #$82
                JMP  rl_x
rb_lies_i:      MOV  R3, #$80
rl_x:           MOV  R0, #RC_FLAG
                MOV  A, @R0
                ORL  A, R3
                MOV  @R0, A
                JMP  rl_start
                .org $6ea

"""

RESET = """; ---- 5.02: NIE 09 = Reset wie beim Einschalten (aus dem Interrupt, auch bei laufendem Programm).
; CALL auf das RETR an 0x003 beendet den Interrupt (sonst käme nie wieder einer), dann Hälfte A und kaltstart.
rb_reset:       DIS  TCNTI
                CALL $003
                ORL  P1, #$ff           ; Hälfte A (unten in beiden Hälften gleich), Leitungen wie nach Reset
                SEL  MB1
                JMP  kaltstart
"""

def anwenden(src, rep):
    # toter VZG-Rumpf 0x47E..0x48E
    i0 = src.index("                MOV  R2, A          ; move # of millis to R2"); i1 = src.index("opcode_SPU:")
    src = src[:i0] + P4A + "\n" + src[i1:]
    # 4.03-dp_warte samt NOP-Füllung (0x4AC..0x4BC) frei
    i0 = src.index("dp_warte:       MOV  R0, #$22       ; Ziffer 3"); i1 = src.index("error_f005:     MOV  R4, #$05")
    src = src[:i0] + "rh_cp3:         ANL  P2, #$df           ; (rs_hol/rh_8155) CP3 an\n                ORL  P2, #$10           ; interne ab\n                JMP  rh_l\n" + RESET + "                .org $4bd\n\n" + src[i1:]
    # toter UND-Rest + altes opcode_ANZ (0x4C4..0x4EE)
    i0 = src.index("                JNZ  error_f005     ; Error if Accu does not contain data"); i1 = src.index("execute_sub_trampoline:")
    src = src[:i0] + P4C + "\n" + src[i1:]
    # Demos raus (nach Hälfte A), Platz für den NIE-Verteiler
    i0 = src.index("demo_9:         JMP  demo_countdown"); i1 = src.index("; Print PC\n")
    src = src[:i0] + P6A + src[i1:]
    i0 = src.index("demo_countdown:"); i1 = src.index("; Print Accumulator\n")
    src = src[:i0] + P6B + src[i1:]
    # 5.02: Reset-Taste CLR halten + STP. STP zeigt in der Sprungtabelle auf die drei freien NOPs hinter dem
    # RETR an 0x003; von dort nach Hälfte A (wait_key läuft immer in Hälfte A, Stummel NACH_UNTEN).
    a = "                .db <wait_key                ; key 'STP'"
    assert src.count(a) == 1
    src = src.replace(a, "                .db <stp_taste               ; key 'STP' (5.02: CLR halten + STP = Reset)")
    a = "                RETR                ; Interrupt entry point\n                NOP\n                NOP\n                NOP\n"
    assert src.count(a) == 1
    src = src.replace(a, "                RETR                ; Interrupt entry point (5.02: auch Ziel von CALL $003 in rb_reset)\n"
                         "stp_taste:      SEL  MB1            ; 5.02: STP-Taste -> s_stp (Hälfte A)\n                JMP  s_stp\n")
    return src
