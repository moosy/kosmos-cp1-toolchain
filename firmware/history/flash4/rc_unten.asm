; ---------------------------------------------------------------------
; Fernsteuerung (Remote Control) über P1.7 – im Timer-Interrupt
; Liegt im toten Platz der alten CAL-Routine (Seite 7, 0x712..0x7E0),
; weil der 8049 im Interrupt A11 auf 0 hält.
; Aufruf: statt  MOVD A, P4 / CLR C  im Timer-Interrupt  CALL rc_tast.
; Registerbank 1. Frei: R0, R3, A. R1 wird gesichert. R2 (Zeile) bleibt!
;
; Pi -> CP1: Anklopfen = Leitung low. Der Interrupt zählt die Takte, in denen sie low ist,
;   und wartet NICHT: 3,5 ms (1-2 Takte) = Statusabfrage (RAM 0x20..0x3A, 27 Byte),
;   8,5 ms (3 Takte) = Befehl: dann wartet er aufs Loslassen und liest 4 Byte:
;   je Bit ein Low-Puls 150 µs = 1 / 750 µs = 0 (Schwelle 460 µs), danach >= 150 µs high,
;   LSB zuerst.  Byte 4 = Byte1 ^ Byte2 ^ Byte3 ^ $A5.
;   01 zm dd: Taste. z = Zeile (2..6, R2-Wert), m = Spaltenmaske, dd = Dauer in Bildern à 15,36 ms
;   02 aa nn: nn Byte internes RAM ab aa lesen
;   03 aa ww: internes RAM aa = ww (Quittung $A5)  [4.0: Aufträge für den Flash]
; CP1 -> Pi: nach 2,6 ms Pause JE INTERRUPT EIN BYTE (Anzeige läuft weiter):
;   die Daten, dann ein Prüfbyte (XOR ^ $A5). Pulse ~43 µs = 1 / ~125 µs = 0, Pause ~43 µs
;   (der Pi misst mit kosmos_rc direkt an den GPIO-Registern).
;   Auf 01 kommt nur $A5 als Quittung.
; ---------------------------------------------------------------------
                .equ RC_FLAG,  $46      ; Bit0 = an, Bit1 = Pause (Kassette läuft), Bit2 = Antwort läuft; init löscht 0x20..0x47
                .equ RC_ZEILE, $78
                .equ RC_MASKE, $79
                .equ RC_DAUER, $7a
                .equ RC_PUF,   $7b      ; 4 Byte $7b..$7e
                .equ RC_P1,    $7c
                .equ RC_P2,    $7d
                .equ RC_P3,    $7e
                .equ RC_R1,    $7f

rc_tast:        MOV  R0, #RC_FLAG
                MOV  A, @R0
                JB0  rt_an
                MOVD A, P4
                CLR  C
                RET
rt_an:          JB2  rt_sende_t          ; Antwort läuft: ein Byte je Interrupt
                JB1  rt_taste           ; Kassette läuft: Leitung nicht anfassen
                IN   A, P1
                JB7  rt_hoch
                MOV  A, @R0             ; Leitung low: Takte zählen (Bit 4/5), nicht warten
                ADD  A, #$10
                MOV  @R0, A
                ANL  A, #$30
                XRL  A, #$30
                JNZ  rt_taste
                MOV  A, @R0             ; 3 Takte low: Befehl kommt -> zuhören
                ANL  A, #$cf
                MOV  @R0, A
                JMP  rc_dunkel          ; erst Anzeige aus (Seite 1), dann rc_befehl
rt_hoch:        MOV  A, @R0
                ANL  A, #$30
                JZ   rt_taste           ; nichts los
                MOV  A, @R0             ; nach 1-2 Takten wieder high: Statusabfrage
                ANL  A, #$cf
                ORL  A, #$04            ; Antwort läuft (ab nächstem Takt)
                MOV  @R0, A
                JMP  rc_abfrage         ; (Seite 3)
rt_taste:       MOV  R0, #RC_DAUER
                MOV  A, @R0
                JZ   rt_ohne
                MOV  R0, #RC_ZEILE
                MOV  A, @R0
                XRL  A, R2
                JNZ  rt_ohne
                MOV  R0, #RC_DAUER      ; einmal je Bild herunterzählen
                MOV  A, @R0
                DEC  A
                MOV  @R0, A
                MOV  R0, #RC_MASKE
                MOVD A, P4
                ORL  A, @R0             ; Ferntaste dazu
                CLR  C
                RET
rt_ohne:        MOVD A, P4
                CLR  C
                RET

rc_befehl:      MOV  R0, #RC_R1
                MOV  A, R1
                MOV  @R0, A
                MOV  R1, #$00           ; Anklopfen: auf High warten, max 256 x 20 µs
rb_klopf:       IN   A, P1
                JB7  rb_los
                NOP
                NOP
                DJNZ R1, rb_klopf
                MOV  R0, #RC_FLAG       ; Leitung klemmt low (z. B. P1A auf Klemme 8): Fernsteuerung aus
                MOV  @R0, #$00
                JMP  rb_ende
rb_los:         MOV  R0, #RC_PUF
rb_byte:        MOV  R3, #$08
rb_bit:         MOV  R1, #$00           ; auf Low warten, max 256 x 17,5 µs
rb_wlow:        IN   A, P1
                JB7  rb_wl2
                JMP  rb_low
rb_wl2:         NOP
                DJNZ R1, rb_wlow
                JMP  rb_ende            ; nichts mehr gekommen
rb_low:         MOV  R1, #$00           ; Low-Dauer zählen, 20 µs je Schritt
rb_lz:          INC  R1
                IN   A, P1
                JB7  rb_hoch
                MOV  A, R1
                JNZ  rb_lz
                JMP  rb_ende            ; > 5 ms low: Unsinn
rb_hoch:        MOV  A, R1
                ADD  A, #$e9            ; C = 1, wenn >= 23 Schritte (460 µs) -> Bit 0
                CPL  C
                MOV  A, @R0
                RRC  A
                MOV  @R0, A
                DJNZ R3, rb_bit
                INC  R0
                MOV  A, R0
                XRL  A, #$7f              
                JNZ  rb_byte
                MOV  R0, #RC_PUF        ; Prüfbyte
                MOV  A, @R0
                INC  R0
                XRL  A, @R0
                INC  R0
                XRL  A, @R0
                INC  R0
                XRL  A, @R0
                XRL  A, #$a5
                JNZ  rb_ende
                MOV  R0, #RC_PUF
                MOV  A, @R0
                XRL  A, #$02
                JZ   rb_lesen_t
                XRL  A, #$01            ; (A ^ 2) ^ 1 = A ^ 3
                JZ   rb_schreib_t
                XRL  A, #$02            ; = A ^ 1
                JNZ  rb_ende
                JMP  rb_taste           ; liegt auf Seite 1 (Platz)
rb_schreib_t:   JMP  rb_schreib         ; (Seite 3)

rb_lesen_t:     JMP  rl_start           ; (Seite 1)
rt_sende_t:     JMP  rt_sende           ; (Seite 3)

; Byte in A senden (rt_sende auf Seite 3 springt hierher)
rl_senden:      MOV  R0, #RC_P3
                MOV  @R0, A
                MOV  R3, #$08
rs_bit:         MOV  R0, #RC_P3
                MOV  A, @R0
                RRC  A
                MOV  @R0, A
                ANL  P1, #$7f           ; Low
                MOV  R0, #5             ; 1: 5 x 7,5 µs + ~5 µs = ~43 µs
                JC   rs_w
                MOV  R0, #16            ; 0: ~125 µs
rs_w:           NOP
                DJNZ R0, rs_w
                ORL  P1, #$80           ; High
                MOV  R0, #5             ; ~43 µs Pause (Byte ~1 ms: passt in den Interrupt-Takt)
rs_p:           NOP
                DJNZ R0, rs_p
                DJNZ R3, rs_bit
                JMP  rt_taste

rb_ende:        MOV  R0, #RC_R1
                MOV  A, @R0
                MOV  R1, A
                JMP  rt_taste
