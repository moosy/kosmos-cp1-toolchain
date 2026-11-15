; Fernsteuerung, Teil 2: im toten Platz der alten CAS-Routine (Seite 1, 0x1C8..0x1FE)
; Befehl 01 zm dd: Ferntaste merken
rb_taste:       MOV  R0, #RC_P1
                MOV  A, @R0
                ANL  A, #$0f
                MOV  R0, #RC_MASKE
                MOV  @R0, A
                MOV  R0, #RC_P1
                MOV  A, @R0
                SWAP A
                ANL  A, #$0f
                MOV  R0, #RC_ZEILE
                MOV  @R0, A
                MOV  R0, #RC_P2
                MOV  A, @R0
                MOV  R0, #RC_DAUER
                MOV  @R0, A
rb_quitt:       MOV  R0, #RC_P2         ; Quittung: 0 Datenbyte, nur das Prüfbyte
                MOV  @R0, #$00
                JMP  rl_start

; Vor dem Befehl alle Segmente aus: die Anzeige wird kurz gleichmäßig dunkler,
; statt dass eine Stelle ~30 ms lang hell stehen bleibt (8155 ist im Interrupt schon gewählt).
rc_dunkel:      CLR  A
                MOV  R0, #$01           ; Port A = Segmente
                MOVX @R0, A
                JMP  rc_befehl

; Antwort vorbereiten: RC_P1 = Adresse, RC_P2 = Anzahl
rl_start:       MOV  R0, #RC_PUF
                MOV  @R0, #$a5          ; Prüfbyte
                MOV  R0, #RC_FLAG
                MOV  A, @R0
                ORL  A, #$04            ; ab dem nächsten Interrupt senden
                MOV  @R0, A
                MOV  R1, #40            ; 0,4 ms: kosmos_rc schaltet sofort auf Empfang
rl_w:           NOP
                NOP
                DJNZ R1, rl_w
                JMP  rb_ende

