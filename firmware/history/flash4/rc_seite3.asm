; Fernsteuerung, Teil 3: im toten Platz der alten CAS-Sende-Routine (Seite 3, 0x3BD..0x3F2)
; je Interrupt ein Byte (R3, R0, A frei; R1 bleibt unberührt)
rt_sende:       MOV  R0, #RC_P2
                MOV  A, @R0
                JZ   rs_ende
                DEC  A
                MOV  @R0, A
                MOV  R0, #RC_P1
                MOV  A, @R0
                INC  @R0
                MOV  R0, A
                MOV  A, @R0             ; Datenbyte
                MOV  R0, #RC_PUF
                XCH  A, @R0             ; Prüfbyte mitführen
                XRL  A, @R0
                XCH  A, @R0             ; @R0 = Prüfbyte neu, A = Datenbyte
                JMP  rl_senden
rs_ende:        MOV  R0, #RC_FLAG       ; zuletzt das Prüfbyte
                MOV  A, @R0
                ANL  A, #$fb
                MOV  @R0, A
                MOV  R0, #RC_PUF
                MOV  A, @R0
                JMP  rl_senden

; Statusabfrage vorbereiten (aus rt_hoch): RAM 0x20..0x3A, ab dem nächsten Takt je ein Byte
rc_abfrage:     MOV  R0, #RC_P1
                MOV  @R0, #$20
                MOV  R0, #RC_P2
                MOV  @R0, #27
                MOV  R0, #RC_PUF
                MOV  @R0, #$a5
                JMP  rt_taste

; 03 aa ww: ein Byte ins interne RAM (aus rc_befehl, R1 wird in rb_ende zurückgeholt)
rb_schreib:     MOV  R0, #RC_P1
                MOV  A, @R0
                MOV  R1, A
                INC  R0                 ; RC_P2
                MOV  A, @R0
                MOV  @R1, A
                JMP  rb_quitt           ; (Seite 1) nur Prüfbyte
