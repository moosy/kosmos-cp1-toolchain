; =====================================================================
; Schnelle Kassette für den Kosmos CP1 (Bereich 0x800–0xFFF, A11 = P23)
; Michael Moosbauer / Claude, 2026-11
;
; Einsprung aus dem Original: cas_handler / cal_handler sind auf
;   SEL MB1 / JMP s_cas bzw. s_cal / NOP   umgebogen (je 4 Byte).
; Rücksprung: SEL MB0 / JMP wait_key.
;
; Regel: Aufruf einer Original-Routine immer  SEL MB0 / CALL x / SEL MB1
; (RET kehrt dank 12-Bit-Stack von selbst nach oben zurück, das
;  Bank-Flipflop aber nicht).
;
; Leitung: P1.7 (Klemme 8). Ruhepegel high. Ein Bit = Low-Puls, danach
; mindestens PAUSE high. Kurzer Low-Puls (KURZ) = 1, langer (LANG) = 0.
; Die Länge des High-Teils ist egal (darin wird gerechnet).
; Bytes LSB zuerst.
;
; Rahmen: $C1, erste Zelle, letzte Zelle, je Zelle 2 Byte (Befehl,
; Argument), CRC-8 (Polynom $07, Start 0) über alles davor.
; =====================================================================

                .equ S_CRC,     $60     ; laufende CRC
                .equ S_ZELLE,   $61     ; aktuelle Zelle
                .equ S_LETZTE,  $62     ; letzte Zelle
                .equ S_ERSTE,   $63     ; erste Zelle
                .equ S_B1,      $64     ; Puffer Befehl
                .equ S_B2,      $65     ; Puffer Argument
                .equ S_FLAG,    $66     ; 1 = STP gedrückt
                .equ S_ZAHL,    $67     ; Eingabe: Wert
                .equ S_ANZ,     $68     ; Eingabe: Anzahl Ziffern
                .equ S_ZAEHL,   $69     ; Schleifenzähler
                .equ S_TMP,     $6a
                .equ S_SOLL,    $6b     ; erwartete CRC
                .equ S_CRCT,    $6c     ; Zwischenspeicher crc_dazu
                .equ S_SYM,     $6d     ; Symbol ganz links (Eimer: CAS / CAL)
                .equ S_SEGZ,    $6e     ; SEG: aktuelle Zelle
                .equ S_SEGN,    $6f     ; SEG: Stelle 0..5
                .equ S_SEGPUF,  $70     ; SEG: 6 Byte Puffer (0x70..0x75)
                .equ S_ASY,     $76     ; AS1..AS3: Stelle 1..3
                .equ S_ASZ,     $77     ; AS: Ziffer
                .equ S_RSP,     $45     ; JSR/RET: Stapelzeiger 0..24 (init löscht 0x20..0x47)
                .equ S_RSTAPEL, $48     ; JSR/RET: Rücksprungadressen 0x48..0x5F
                .equ RTIEFE,    24
                .equ S_OVFAUS,  $47     ; 1 = Überlauf aus (OVF 000); init löscht 0x20..0x47

                ; Der Timer-Interrupt (Anzeige, Tastatur) hält alle 2,56 ms bis ~260 µs an:
                ; gesendete Pulse werden bis dahin länger, gemessene bis dahin kürzer.
                .equ KURZ,      80      ; 80 * 5 µs = 0,4 ms (Bit 1)
                .equ LANG,      240     ; 1,2 ms (Bit 0)
                .equ PAUSE,     80      ; 0,4 ms High nach jedem Bit
                .equ SCHWELLE,  48      ; Low-Zählschritte à 15 µs: < 48 (0,72 ms) = Bit 1

                .equ T_STP,     $0f
                .equ T_CAS,     $11
                .equ T_CLR,     $12

                ; Segmente (gfedcba)
                .equ G_C,  $39
                .equ G_S,  $6d
                .equ G_E,  $79
                .equ G_R,  $50
                .equ G_KC, $58          ; c
                .equ G_F,  $71
                .equ G_T,  $78          ; t
                .equ G_O,  $5c          ; o
                .equ G_U,  $1c          ; u
                .equ G_D,  $5e          ; d
                .equ G_Y,  $6e
                .equ G_CAS, $23         ; ⊓ Eimer wird ausgeschüttet (wie Original-CAS)
                .equ G_CAL, $1c         ; ⊔ Eimer wird gefüllt (wie Original-CAL)
                .equ G_MI, $40          ; -
                .equ G_UN, $08          ; _
                .equ G_N,  $54          ; n

                .org $800

; ---------------------------------------------------------------------
; CAS: speichern
; ---------------------------------------------------------------------
s_cas:          MOV  A, R6
                JZ   s_cas_kass
                JMP  zb_k_cas
s_cas_kass:     SEL  MB0
                CALL clear_display
                CALL clear_access_ram_extension_status_bit
                SEL  MB1
                ORL  P1, #$c0           ; CassData = 1, CassWR = 1 (wie Original)
                MOV  R0, #S_SYM
                MOV  @R0, #G_CAS
                CALL symbol_zeigen      ; sofort ⊓
                MOV  R0, #S_FLAG
                MOV  @R0, #$00
                ; Alles als Vorgabe
                MOV  R0, #S_ERSTE
                MOV  @R0, #$00
                MOV  R0, #MEM_SIZE
                MOV  A, @R0
                MOV  R0, #S_LETZTE
                MOV  @R0, A
                ; CAS 1 s gehalten? 4 Stufen à 25 x 10 ms: nach 1/4, 1/2, 3/4 s rechts _ __ ___, nach 1 s Eingabe
                MOV  R0, #S_TMP
                MOV  @R0, #$00
sc_stufe:       MOV  R0, #S_ZAEHL
                MOV  @R0, #25
sc_halt:        MOV  R3, #10
                SEL  MB0
                CALL delay_millis
                SEL  MB1
                CALL taste_cas_gedrueckt
                JNC  sc_senden          ; losgelassen: kurz = alles
                MOV  R0, #S_ZAEHL
                MOV  A, @R0
                DEC  A
                MOV  @R0, A
                JNZ  sc_halt
                MOV  R0, #S_TMP
                INC  @R0
                MOV  A, @R0
                MOV  R2, A
                MOV  R5, #G_UN
                CALL zeichen_rechts
                MOV  R0, #S_TMP
                MOV  A, @R0
                XRL  A, #4
                JNZ  sc_stufe
                ; gehalten: Teilbereich abfragen
                MOV  R2, #G_F
                MOV  R5, #G_R
                MOV  R0, #S_ERSTE
                CALL eingabe
                JF1  sc_abbr
                MOV  R2, #G_T
                MOV  R5, #G_O
                MOV  R0, #S_LETZTE
                CALL eingabe
                JF1  sc_abbr
                CALL bereich_ordnen

sc_senden:
                MOV  R0, #RC_FLAG       ; ab hier gehört die Leitung der Kassette (Fr/to-Eingabe ging noch fern), solange die Leitung Daten trägt
                MOV  A, @R0
                ORL  A, #$02
                MOV  @R0, A
                CALL anlauf             ; - -- ---
                JF1  sc_abbr
                MOV  R2, #G_S
                MOV  R5, #G_E
                CALL kopf_zeigen        ; C SE
                MOV  R0, #S_CRC
                MOV  @R0, #$00
                MOV  A, #$c1
                CALL sende_byte
                MOV  R0, #S_ERSTE
                MOV  A, @R0
                CALL sende_byte
                MOV  R0, #S_LETZTE
                MOV  A, @R0
                CALL sende_byte
                MOV  R0, #S_ERSTE
                MOV  A, @R0
                MOV  R0, #S_ZELLE
                MOV  @R0, A
sc_zelle:       CALL zelle_zeigen
                MOV  R0, #STATUS
                MOV  A, @R0
                JB0  sc_abbr
                MOV  R0, #S_ZELLE
                MOV  A, @R0
                SEL  MB0
                CALL compute_effective_address  ; -> R1, wählt den 8155
                SEL  MB1
                MOVX A, @R1
                MOV  R0, #S_B1
                MOV  @R0, A
                INC  R1
                MOVX A, @R1
                MOV  R0, #S_B2
                MOV  @R0, A
                MOV  R0, #S_B1
                MOV  A, @R0
                CALL sende_byte
                MOV  R0, #S_B2
                MOV  A, @R0
                CALL sende_byte
                CALL naechste_zelle
                JNC  sc_zelle
                MOV  R0, #S_CRC
                MOV  A, @R0
                CALL sende_byte
                JMP  s_fertig
sc_abbr:        JMP  s_abbruch

; ---------------------------------------------------------------------
; CAL: laden
; ---------------------------------------------------------------------
s_cal:          JMP  zb_k_cal_vor
s_cal_kass:     SEL  MB0
                CALL clear_display
                CALL clear_access_ram_extension_status_bit
                SEL  MB1
                MOV  R0, #RC_FLAG       ; Fernsteuerung pausiert, solange die Leitung Daten trägt
                MOV  A, @R0
                ORL  A, #$02
                MOV  @R0, A
                ANL  P1, #$bf           ; CassWR = 0 (wie Original)
                ORL  P1, #$80           ; CassData = 1: Eingang
                MOV  R0, #S_SYM
                MOV  @R0, #G_CAL
                CALL symbol_zeigen      ; sofort ⊔
                MOV  R0, #S_FLAG
                MOV  @R0, #$00
                MOV  R0, #S_CRC
                MOV  @R0, #$00
                ; auf das erste Bit warten, dabei - -- --- kreisen lassen
                MOV  R0, #S_ZAEHL
                MOV  @R0, #$00
cl_warte:       CALL striche            ; Stufe S_ZAEHL anzeigen, weiterzählen
                MOV  R2, #64            ; ~250 ms
                CALL warte_flanke
                JNC  cl_los             ; Flanke da
                MOV  R0, #S_FLAG
                MOV  A, @R0
                JNZ  cl_abbr
                JMP  cl_warte
cl_los:         CLR  F1
                CALL miss_bit           ; erstes Bit von $C1
                JF1  cl_fehler_stp
                CALL bit_rein
                MOV  R3, #7
                CALL lies_rest          ; restliche 7 Bit, rechnet CRC mit
                JF1  cl_fehler_stp
                XRL  A, #$c1
                JNZ  cl_fehl
                CALL lies_byte
                JF1  cl_fehler_stp
                MOV  R0, #S_ERSTE
                MOV  @R0, A
                MOV  R0, #S_ZELLE
                MOV  @R0, A
                CALL lies_byte
                JF1  cl_fehler_stp
                MOV  R0, #S_LETZTE
                MOV  @R0, A
                ; Kopf prüfen: erste <= letzte <= MEM_SIZE
                MOV  R0, #MEM_SIZE
                MOV  A, @R0
                CPL  A
                MOV  R0, #S_LETZTE
                ADD  A, @R0             ; C = 1, wenn letzte > MEM_SIZE
                JC   cl_fehl
                MOV  R0, #S_LETZTE
                MOV  A, @R0
                CPL  A
                MOV  R0, #S_ERSTE
                ADD  A, @R0             ; C = 1, wenn erste > letzte
                JC   cl_fehl
                MOV  R2, #G_R
                MOV  R5, #G_KC
                CALL kopf_zeigen        ; C rc
cl_zelle:       CALL zelle_zeigen
                CALL lies_byte
                JF1  cl_fehler_stp
                MOV  R0, #S_B1
                MOV  @R0, A
                CALL lies_byte
                JF1  cl_fehler_stp
                MOV  R0, #S_B2
                MOV  @R0, A
                MOV  R0, #S_ZELLE
                MOV  A, @R0
                SEL  MB0
                CALL compute_effective_address
                SEL  MB1
                MOV  R0, #S_B1
                MOV  A, @R0
                MOVX @R1, A
                INC  R1
                MOV  R0, #S_B2
                MOV  A, @R0
                MOVX @R1, A
                CALL naechste_zelle
                JNC  cl_zelle
                ; Prüfsumme
                MOV  R0, #S_CRC
                MOV  A, @R0
                MOV  R0, #S_SOLL
                MOV  @R0, A             ; erwartete CRC merken
                CALL lies_byte          ; (rechnet die CRC weiter, egal)
                JF1  cl_fehler_stp
                MOV  R0, #S_SOLL
                XRL  A, @R0
                JNZ  cl_fehl
                JMP  s_fertig

cl_fehler_stp:  MOV  R0, #S_FLAG
                MOV  A, @R0
                JNZ  cl_abbr
cl_fehl:        JMP  s_fehler
cl_abbr:        JMP  s_abbruch

; ---------------------------------------------------------------------
; Ende: rdY / C Su Err / Abbruch
; ---------------------------------------------------------------------
s_fertig:       CALL symbol_zeigen
                MOV  R0, #$23           ; VRAM+3: rechte Dreiergruppe (8 88 888)
                MOV  @R0, #G_R
                INC  R0
                MOV  @R0, #G_D
                INC  R0
                MOV  @R0, #G_Y
                JMP  s_ende

s_fehler:       MOV  R0, #S_SYM
                MOV  A, @R0
                MOV  R0, #VRAM
                MOV  @R0, A
                INC  R0
                MOV  @R0, #G_S
                INC  R0
                MOV  @R0, #G_U
                INC  R0
                MOV  @R0, #G_E
                INC  R0
                MOV  @R0, #G_R
                INC  R0
                MOV  @R0, #G_R
                JMP  s_ende

s_abbruch_stp:
s_abbruch:      SEL  MB0
                CALL clear_display
                SEL  MB1

s_ende:         ORL  P1, #$80           ; Leitung in Ruhe (high)
                MOV  R0, #RC_FLAG       ; Fernsteuerung weiter
                MOV  A, @R0
                ANL  A, #$fd
                MOV  @R0, A
                ANL  P1, #$bf           ; Klemme 7 auf 0 V wie im Original
                SEL  MB0
                CALL clear_access_ram_extension_status_bit  ; löscht das STP-Bit
                CLR  A
                CALL compute_effective_address  ; internen 8155 wählen, Bit 4 weg
                CLR  F0
                CLR  F1
                CLR  C
                MOV  R6, #$00
                JMP  wait_key

; ---------------------------------------------------------------------
; Senden
; ---------------------------------------------------------------------
; sende_byte: A senden, CRC mitrechnen. Benutzt R0, R2, R3, R4, R5.
sende_byte:     MOV  R5, A
                CALL crc_dazu
                MOV  R3, #8
sb_bit:         MOV  A, R5
                RRC  A
                MOV  R5, A
                ANL  P1, #$7f           ; Low
                MOV  R4, #KURZ
                JC   sb_l
                MOV  R4, #LANG
sb_l:           DJNZ R4, sb_l
                ORL  P1, #$80           ; High
                MOV  R4, #PAUSE
sb_h:           DJNZ R4, sb_h
                DJNZ R3, sb_bit
                RET

; crc_dazu: CRC-8 (Polynom $07) mit A weiterrechnen. Benutzt R0, R2; A bleibt erhalten.
crc_dazu:       MOV  R0, #S_CRCT
                MOV  @R0, A
                MOV  R0, #S_CRC
                XRL  A, @R0
                MOV  R2, #8
cd_bit:         CLR  C
                RLC  A
                JNC  cd_weiter
                XRL  A, #$07
cd_weiter:      DJNZ R2, cd_bit
                MOV  @R0, A
                MOV  R0, #S_CRCT
                MOV  A, @R0
                RET

; ---------------------------------------------------------------------
; Empfangen
; ---------------------------------------------------------------------
; warte_flanke: wartet bis zu R2 x 3,84 ms auf Low. C = 0: Low da.
; C = 1: Zeitüberschreitung oder STP (dann S_FLAG = 1). Benutzt R0, R2, R4.
warte_flanke:   MOV  R4, #$00
wf_i:           IN   A, P1
                JB7  wf_h
                CLR  C
                RET
wf_h:           DJNZ R4, wf_i
                MOV  R0, #STATUS
                MOV  A, @R0
                JB0  wf_stp
                DJNZ R2, warte_flanke
                CLR  C
                CPL  C
                RET
wf_stp:         MOV  R0, #S_FLAG
                MOV  @R0, #$01
                CLR  C
                CPL  C
                RET

; miss_bit: Leitung ist low; Länge messen. C = Bit, F1 = Fehler (zu lang).
miss_bit:       MOV  R4, #$ff
mb_l:           IN   A, P1
                JB7  mb_e
                DJNZ R4, mb_l
                CLR  F1
                CPL  F1
                RET
mb_e:           MOV  A, R4
                ADD  A, #SCHWELLE       ; C = 1, wenn kurz (Bit 1)
                RET

; bit_rein: C von rechts... (LSB zuerst): R5 = R5 >> 1 | C << 7
bit_rein:       MOV  A, R5
                RRC  A
                MOV  R5, A
                RET

; lies_byte: ein Byte nach A, CRC mitrechnen. F1 = Fehler/STP.
lies_byte:      MOV  R3, #8
lies_rest:      CLR  F1
lb_bit:         MOV  R2, #4             ; ~15 ms Zeit für die nächste Flanke
                CALL warte_flanke
                JC   lb_fehler
                CALL miss_bit
                JF1  lb_raus
                CALL bit_rein
                DJNZ R3, lb_bit
                MOV  A, R5
                CALL crc_dazu
                RET
lb_fehler:      CLR  F1
                CPL  F1
lb_raus:        RET

; ---------------------------------------------------------------------
; Hilfen
; ---------------------------------------------------------------------
; taste_cas_gedrueckt: C = 1, wenn der Interrupt CAS noch als gehalten führt.
taste_cas_gedrueckt:
                MOV  R3, #T_CAS
taste_gedrueckt:
                MOV  R0, #$30
                MOV  R2, #6
tc_l:           MOV  A, @R0
                XRL  A, R3
                JZ   tc_ja
                INC  R0
                DJNZ R2, tc_l
                CLR  C
                RET
tc_ja:          CLR  C
                CPL  C
                RET

; naechste_zelle: C = 1, wenn S_ZELLE die letzte war, sonst S_ZELLE + 1.
naechste_zelle: MOV  R0, #S_LETZTE
                MOV  A, @R0
                MOV  R0, #S_ZELLE
                XRL  A, @R0
                JZ   nz_ende
                INC  @R0
                CLR  C
                RET
nz_ende:        CLR  C
                CPL  C
                RET

; kopf_zeigen: Anzeige "C" R2 R5 und leere Ziffern
kopf_zeigen:    MOV  A, R2
                MOV  R4, A              ; clear_display braucht R2
                SEL  MB0
                CALL clear_display
                SEL  MB1
                MOV  R1, #S_SYM
                MOV  A, @R1
                MOV  R0, #VRAM
                MOV  @R0, A
                INC  R0
                MOV  A, R4
                MOV  @R0, A
                INC  R0
                MOV  A, R5
                MOV  @R0, A
                RET

; zelle_zeigen: S_ZELLE dreistellig an Stelle 3..5
zelle_zeigen:   MOV  R0, #S_ZELLE
                MOV  R6, #2
                CLR  F0
                SEL  MB0
                CALL print_value
                SEL  MB1
                RET

; striche: S_ZAEHL mod 3 + 1 Striche in der rechten Dreiergruppe, S_ZAEHL weiterzählen
striche:        MOV  R0, #S_ZAEHL
                MOV  A, @R0
                INC  A
                XRL  A, #4
                JNZ  st_ok
                MOV  A, #5              ; 4 -> 1
st_ok:          XRL  A, #4              ; A = 1..3
                MOV  @R0, A
                MOV  R2, A
                MOV  R5, #G_MI
                JMP  zeichen_rechts

; zeichen_rechts: R2 (0..3) mal Zeichen R5 in die rechte Dreiergruppe (8 88 888), Rest dunkel
zeichen_rechts: MOV  R0, #$23           ; VRAM+3
                MOV  R3, #3
zr_l:           MOV  A, R2
                JZ   zr_leer
                MOV  A, R5
                MOV  @R0, A
                DEC  R2
                JMP  zr_w
zr_leer:        MOV  @R0, #$00
zr_w:           INC  R0
                DJNZ R3, zr_l
                RET

; symbol_zeigen: Anzeige leeren, Symbol S_SYM ganz links
symbol_zeigen:  SEL  MB0
                CALL clear_display
                SEL  MB1
                MOV  R0, #S_SYM
                MOV  A, @R0
                MOV  R0, #VRAM
                MOV  @R0, A
                RET

; anlauf: - -- --- je 250 ms, STP bricht ab (F1)
anlauf:         CLR  F1
                CALL symbol_zeigen      ; Fr/to weg, ⊓ bleibt
                MOV  R0, #S_ZAEHL
                MOV  @R0, #$00
                MOV  R0, #S_TMP
                MOV  @R0, #3
an_l:           CALL striche
                MOV  R3, #250
                SEL  MB0
                CALL delay_millis
                SEL  MB1
                MOV  R0, #STATUS
                MOV  A, @R0
                JB0  an_stp
                MOV  R0, #S_TMP
                MOV  A, @R0
                DEC  A
                MOV  @R0, A
                JNZ  an_l
                RET
an_stp:         CPL  F1
                RET

; bereich_ordnen: erste/letzte tauschen, falls nötig
bereich_ordnen: MOV  R0, #S_LETZTE
                MOV  A, @R0
                CPL  A
                MOV  R0, #S_ERSTE
                ADD  A, @R0             ; C = 1, wenn erste > letzte
                JNC  bo_ok
                MOV  A, @R0             ; A = erste
                MOV  R1, #S_LETZTE
                XCH  A, @R1             ; letzte = erste, A = alte letzte
                MOV  @R0, A
bo_ok:          RET

; eingabe: Anzeige "C" R2 R5 "___", bis zu 3 Ziffern, CAS übernimmt.
; R0 = Zielvariable (wird bei 0 Ziffern nicht geändert = Vorgabe).
; Wert wird auf MEM_SIZE begrenzt. CLR löscht die Eingabe. F1 = STP.
eingabe:        MOV  R1, #S_TMP
                MOV  A, R0
                MOV  @R1, A             ; Ziel merken
                CALL kopf_zeigen
ei_neu:         MOV  R0, #S_ANZ
                MOV  @R0, #$00
                MOV  R0, #S_ZAHL
                MOV  @R0, #$00
                MOV  R0, #$23
                MOV  @R0, #G_UN
                INC  R0
                MOV  @R0, #G_UN
                INC  R0
                MOV  @R0, #G_UN
ei_taste:       MOV  R0, #$1e           ; R6' des Interrupts: neue Taste
                MOV  A, @R0
                JZ   ei_taste
                MOV  @R0, #$00
                MOV  R2, A              ; Tastencode
                XRL  A, #T_STP
                JZ   ei_stp
                MOV  A, R2
                XRL  A, #T_CLR
                JZ   ei_neu
                MOV  A, R2
                XRL  A, #T_CAS
                JZ   ei_fertig
                MOV  A, R2
                ADD  A, #$f5            ; Ziffern = Codes 1..10
                JC   ei_taste           ; Code >= 11: andere Taste
                MOV  A, R2
                JZ   ei_taste
                DEC  R2                 ; R2 = Ziffer 0..9
                MOV  R0, #S_ANZ
                MOV  A, @R0
                XRL  A, #3
                JZ   ei_taste           ; schon 3 Ziffern
                ; Ziffer anzeigen an Stelle 3 + Anzahl
                MOV  A, @R0
                ADD  A, #2
                MOV  R6, A
                MOV  A, R2
                SEL  MB0
                CALL print_digit        ; benutzt R0, R3, R6
                SEL  MB1
                MOV  R0, #S_ANZ
                INC  @R0
                ; Wert = Wert * 10 + Ziffer, Überlauf -> 255
                MOV  R0, #S_ZAHL
                MOV  A, @R0
                MOV  R5, A              ; t
                ADD  A, R5              ; 2t
                JC   ei_voll
                MOV  R4, A
                ADD  A, R4              ; 4t
                JC   ei_voll
                ADD  A, R5              ; 5t
                JC   ei_voll
                MOV  R4, A
                ADD  A, R4              ; 10t
                JC   ei_voll
                ADD  A, R2
                JC   ei_voll
                MOV  @R0, A
                JMP  ei_taste
ei_voll:        MOV  @R0, #$ff
                JMP  ei_taste
ei_fertig:      MOV  R0, #S_ANZ
                MOV  A, @R0
                JZ   ei_ende            ; nichts getippt: Vorgabe bleibt
                MOV  R0, #S_ZAHL
                MOV  A, @R0
                MOV  R5, A
                ; auf MEM_SIZE begrenzen
                MOV  R0, #MEM_SIZE
                MOV  A, @R0
                CPL  A
                ADD  A, R5              ; C = 1, wenn Wert > MEM_SIZE
                JNC  ei_ok
                MOV  A, @R0
                MOV  R5, A
ei_ok:          MOV  R0, #S_TMP
                MOV  A, @R0
                MOV  R0, A
                MOV  A, R5
                MOV  @R0, A
ei_ende:        CLR  F1
                RET
ei_stp:         CLR  F1
                CPL  F1
                RET

; =====================================================================
; Befehlserweiterungen (Michael, 2026-11-12)
;   14 NEG xxx  Akku = Akku XOR xxx (Maske direkt im Befehl); NEG 000 wirkt wie NEG 001
;   15 UND xxx  Akku = Akku AND Zelle xxx, bitweise
;   25 ODR xxx  Akku = Akku OR  Zelle xxx, bitweise (neu)
;   26 OVF x    x = 0: Überlauf aus (255 + 1 = 0, 0 - 1 = 255, kein F-006), sonst an (Standard)
;   02 ANZ 001  Akku vorzeichenbehaftet anzeigen: 128..255 als -128..-001
;   27 SEG xxx  Zellen xxx..xxx+5 als Segmentmuster auf Stelle 1..6 (a=1 b=2 c=4 d=8 e=16 f=32 g=64);
;               SEG 255 löscht die Anzeige. Erst alle 6 Zellen prüfen, dann schreiben.
;   28 AS1 xxx  Hunderter des Akkus als Segmentmuster nach Zelle xxx (00.mmm)
;   29 AS2 xxx  Zehner, 30 AS3 xxx Einer (234: AS1 -> '2', AS2 -> '3', AS3 -> '4')
;   31 TST 000  wartet auf eine Zifferntaste, Akku = 0..9; andere Tasten zählen nicht, STP hält an
;               (PC bleibt auf TST, RUN macht dort weiter)
;   32 JSR xxx  Unterprogramm: Rücksprungadresse (PC+1) auf den Stapel, Sprung nach xxx
;   33 RET 000  Rücksprung an die zuletzt gemerkte Adresse
;               Stapel: 24 Ebenen in RAM 0x48..0x5F, Zeiger 0x45 (init löscht ihn -> leer).
;               Stapel voll -> F 008, RET ohne JSR -> F 009.
;               PC über die Tastatur setzen (3 Ziffern + PC) leert den Stapel; RUN allein nicht.
;   34 PSH 000  Akku auf denselben Stapel (Datum, sonst F 005), 35 POP 000 oberster Wert in den Akku
; Einsprung: opcode_NEG / opcode_UND / opcode_inv sind auf SEL MB1 / JMP / NOP umgebogen.
; Beim Einsprung zeigt R1 auf das Argument des Befehls (bei opcode_inv aus step_handler
; auf das Befehlsbyte, aus dispatch_opcode für Befehl 00 auf das Argument).
; Fehler wie im Original: Akku oder Zelle kein Datum (Befehlsteil <> 00) -> F-005,
; Adresse ungültig -> F-003, unbekannter Befehl -> F-002.
; =====================================================================
s_neg:          MOV  R0, #ACCU
                MOV  A, @R0
                JNZ  b_f005             ; Akku muss ein Datum sein
                MOVX A, @R1             ; Maske = Argument
                JNZ  sn_ok
                MOV  A, #$01            ; NEG 000 = NEG 001 (Original: 0 <-> 1)
sn_ok:          INC  R0
                XRL  A, @R0
                MOV  @R0, A
                SEL  MB0
                JMP  inc_pc

s_und:          CALL b_operand          ; A = Zelle xxx, R0 -> Akku LSB, F1 = Fehler
                JF1  b_fehler
                ANL  A, @R0
                MOV  @R0, A
                SEL  MB0
                JMP  inc_pc

s_oder:         CALL b_operand
                JF1  b_fehler
                ORL  A, @R0
                MOV  @R0, A
                SEL  MB0
                JMP  inc_pc

; s_inv: Befehl > 24 aus step_handler (R1 gerade: zeigt aufs Befehlsbyte) oder Befehl 00 (R1 ungerade)
s_inv:          MOV  A, R1
                JB0  b_f002             ; Befehl 00 (Datum ausgeführt)
                MOVX A, @R1
                XRL  A, #25
                JZ   si_oder
                MOVX A, @R1
                ADD  A, #$e4            ; Befehl - 28
                JNC  si_kein_as         ; < 28
                MOV  R5, A              ; 0..
                ADD  A, #$fd            ; >= 3 -> Befehl > 30
                JC   si_ab31
                MOV  A, R5
                INC  A                  ; y = 1..3
                MOV  R0, #S_ASY
                MOV  @R0, A
                INC  R1
                JMP  s_as
si_ab31:        MOVX A, @R1
                XRL  A, #31
                JZ   si_tst
                MOVX A, @R1
                XRL  A, #32
                JZ   si_jsr
                MOVX A, @R1
                XRL  A, #33
                JZ   si_ret
                MOVX A, @R1
                XRL  A, #34
                JZ   si_psh
                MOVX A, @R1
                XRL  A, #35
                JZ   si_pop
                INC  R1
                JMP  zb_s_fbef          ; 36..38 PSK/FRD/FWR, sonst F-002
si_pop:         JMP  s_pop
si_psh:         JMP  s_psh
si_ret:         INC  R1
                JMP  s_ret
si_jsr:         INC  R1
                JMP  s_jsr
si_tst:         INC  R1
                JMP  s_tst
si_kein_as:     MOVX A, @R1
                XRL  A, #27
                JZ   si_seg
                MOVX A, @R1
                XRL  A, #26
                JNZ  b_f002
                INC  R1                 ; wie dispatch_opcode: R1 -> Argument
                JMP  s_ovf
si_seg:         INC  R1
                JMP  s_seg
si_oder:        INC  R1
                JMP  s_oder

; 26 OVF x: Schalter in RAM 0x47 (vom Original beim Einschalten gelöscht -> Standard „an“)
s_ovf:          MOVX A, @R1
                MOV  R0, #S_OVFAUS
                JZ   so_aus
                MOV  @R0, #$00
                SEL  MB0
                JMP  inc_pc
so_aus:         MOV  @R0, #$01
                SEL  MB0
                JMP  inc_pc

; s_f006: Einsprung aus error_f006 (ADD/SUB-Überlauf). A = Ergebnis modulo 256, R0 -> Akku LSB.
s_f006:         MOV  R4, A
                MOV  R1, #S_OVFAUS
                MOV  A, @R1
                JZ   sf_fehler
                MOV  A, R4
                MOV  @R0, A             ; Überlauf aus: umgebrochenes Ergebnis speichern
                SEL  MB0
                JMP  inc_pc
sf_fehler:      SEL  MB0
                MOV  R4, #$06           ; F-006 wie das Original
                JMP  show_error

; s_anz: Befehl 02 ANZ (Tabelleneintrag zeigt auf anz_neu). R1 -> Argument.
s_anz:          MOVX A, @R1
                XRL  A, #$01
                JNZ  sa_normal
                MOV  R0, #ACCU
                MOV  A, @R0
                JNZ  sa_normal          ; Befehl im Akku: wie bisher
                INC  R0
                MOV  A, @R0
                JB7  sa_neg
sa_normal:      SEL  MB0
                CALL print_accu         ; RET kommt hierher zurück, MBF bleibt 0
                JMP  inc_pc
sa_neg:         CPL  A
                INC  A                  ; Betrag: 255 -> 1, 128 -> 128
                MOV  R0, #S_TMP
                MOV  @R0, A
                SEL  MB0
                CALL print_accu         ; A, 00, Wert
                SEL  MB1
                MOV  R0, #S_TMP
                MOV  R6, #2
                CLR  F0
                SEL  MB0
                CALL print_value        ; Betrag an Stelle 3..5
                MOV  R0, #$21
                MOV  @R0, #$00          ; "00" -> " -"
                INC  R0
                MOV  @R0, #G_MI
                JMP  inc_pc

; b_operand: Akku und Zelle xxx prüfen. A = Wert der Zelle, R0 -> Akku LSB.
; F1 = 1 bei Fehler, dann R4 = Fehlernummer.
b_operand:      CLR  F1
                MOV  R0, #ACCU
                MOV  A, @R0
                JNZ  bo_f005
                SEL  MB0
                CALL check_and_load_effective_address  ; R1 -> Zelle, F0 = ungültig
                SEL  MB1
                JF0  bo_f003
                MOVX A, @R1             ; Befehlsteil der Zelle
                JNZ  bo_f005
                INC  R1
                MOVX A, @R1             ; Wert
                MOV  R0, #ACCU_LSB
                RET
bo_f005:        MOV  R4, #$05
                CPL  F1
                RET
bo_f003:        MOV  R4, #$03
                CPL  F1
                RET

b_fehler:       MOV  A, R4
                XRL  A, #$03
                JZ   b_f003
b_f005:         SEL  MB0
                JMP  error_f005
b_f003:         SEL  MB0
                JMP  error_f003
b_f002:         SEL  MB0
                MOV  R4, #$02           ; F-002 wie das Original
                JMP  show_error

; 27 SEG xxx (R1 -> Argument). R7 (E/A-Zeiger des Originals) bleibt unberührt.
s_seg:          MOVX A, @R1
                MOV  R0, #S_SEGZ
                MOV  @R0, A             ; aktuelle Zelle
                CPL  A
                JNZ  sg_zellen
                SEL  MB0                ; SEG 255: Anzeige löschen
                CALL clear_display
                JMP  inc_pc
sg_zellen:      MOV  A, @R0
                ADD  A, #5
                JC   sg_f003            ; xxx + 5 > 255
                MOV  R4, A              ; letzte Zelle
                MOV  R0, #MEM_SIZE
                MOV  A, @R0
                CPL  A
                ADD  A, R4              ; C = 1, wenn letzte > MEM_SIZE
                JC   sg_f003
                MOV  R0, #S_SEGN
                MOV  @R0, #0            ; Stelle 0..5
sg_l:           MOV  R0, #S_SEGZ
                MOV  A, @R0
                SEL  MB0
                CALL compute_effective_address  ; R1 -> Zelle (Befehlsteil)
                SEL  MB1
                MOVX A, @R1
                JNZ  sg_f005            ; kein Datum
                INC  R1
                MOVX A, @R1             ; Segmentmuster
                MOV  R2, A
                MOV  R0, #S_SEGN
                MOV  A, @R0
                ADD  A, #S_SEGPUF
                MOV  R0, A
                MOV  A, R2
                MOV  @R0, A             ; puffern
                MOV  R0, #S_SEGZ
                INC  @R0
                MOV  R0, #S_SEGN
                INC  @R0
                MOV  A, @R0
                XRL  A, #6
                JNZ  sg_l
                MOV  R0, #S_SEGPUF      ; alle gültig: Puffer -> Anzeige
                MOV  R1, #VRAM
                MOV  R2, #6
sg_k:           MOV  A, @R0
                MOV  @R1, A
                INC  R0
                INC  R1
                DJNZ R2, sg_k
                SEL  MB0
                JMP  inc_pc
sg_f003:        SEL  MB0
                JMP  error_f003
sg_f005:        SEL  MB0
                JMP  error_f005

; ---------------------------------------------------------------------
; RUN: kurz = wie immer (beim Loslassen); 1 s halten = Fernsteuerung an/aus
; Einsprung aus run_handler (SEL MB1 / JMP s_run), zurück nach run_weiter.
; ---------------------------------------------------------------------
                .equ T_RUN, $10
s_run:          MOV  R0, #S_ZAEHL
                MOV  @R0, #100
sr_l:           MOV  R0, #$34           ; Tastenzustand der RUN-Zeile
                MOV  A, @R0
                XRL  A, #T_RUN
                JNZ  sr_kurz
                MOV  R3, #10
                SEL  MB0
                CALL delay_millis
                SEL  MB1
                MOV  R0, #S_ZAEHL
                MOV  A, @R0
                DEC  A
                MOV  @R0, A
                JNZ  sr_l
                MOV  R0, #RC_FLAG       ; umschalten, Pause weg
                MOV  A, @R0
                CPL  A
                ANL  A, #$01
                MOV  @R0, A
                MOV  R0, #RC_DAUER      ; keine Ferntaste hängt
                MOV  @R0, #$00
                ORL  P1, #$80           ; Leitung loslassen
                SEL  MB0
                CALL clear_display
                SEL  MB1
                MOV  R0, #$21           ; " rc on" / " rc oFF"
                MOV  @R0, #G_R
                INC  R0
                MOV  @R0, #G_KC
                INC  R0
                MOV  @R0, #G_O
                INC  R0
                MOV  R1, #RC_FLAG
                MOV  A, @R1
                JB0  sr_on
                MOV  @R0, #G_F
                INC  R0
                MOV  @R0, #G_F
                JMP  sr_los
sr_on:          MOV  @R0, #G_N
sr_los:         MOV  R0, #$34           ; warten, bis RUN losgelassen ist
                MOV  A, @R0
                XRL  A, #T_RUN
                JZ   sr_los
                MOV  R6, #$00
                SEL  MB0
                JMP  wait_key
sr_kurz:        MOV  A, R6              ; verdrängter Original-Code von run_handler
                XRL  A, #$01
                SEL  MB0
                JMP  run_weiter

; ---------------------------------------------------------------------
; Start: „  3.05 “ 1 s lang, dann P 000 wie im Original
; Einsprung am Ende von init statt  CALL clear_ram / EN TCNTI / STRT T
; ---------------------------------------------------------------------
s_boot:         SEL  MB0
                CALL clear_ram
                CALL clear_display      ; P 000 von vorhin weg
                SEL  MB1
                EN   TCNTI
                STRT T
                MOV  R0, #$22           ; VRAM: _ _3.05 _
                MOV  @R0, #$e6          ; 4 mit Punkt
                INC  R0
                MOV  @R0, #$3f          ; 0
                INC  R0
                MOV  @R0, #$66          ; 4   (Version 4.04)
                MOV  R0, #S_ZAEHL       ; 4 x 250 ms (delay_millis braucht R2 und R3)
                MOV  @R0, #4
sb_w:           MOV  R3, #250
                SEL  MB0
                CALL delay_millis
                SEL  MB1
                MOV  R0, #S_ZAEHL
                MOV  A, @R0
                DEC  A
                MOV  @R0, A
                JNZ  sb_w
                JMP  zb_f_boot

                .seite
; Segmentmuster der Ziffern 0..9 (wie Seite 3 des Originals), mit MOVP aus dieser Seite gelesen
as_tab:         .db  $3f, $06, $5b, $4f, $66, $6d, $7d, $27, $7f, $6f

; 28..30 AS1..AS3 xxx (R1 -> Argument, S_ASY = 1..3)
s_as:           MOV  R0, #ACCU
                MOV  A, @R0
                JNZ  as_f005            ; Akku muss ein Datum sein
                INC  R0
                MOV  A, @R0
                SEL  MB0
                CALL itoa               ; A = Hunderter, R4 = Zehner, R2 = Einer
                SEL  MB1
                MOV  R5, A
                MOV  R0, #S_ASY
                MOV  A, @R0
                XRL  A, #2
                JZ   as_zehner
                MOV  A, @R0
                XRL  A, #3
                JZ   as_einer
                MOV  A, R5              ; AS1
                JMP  as_ziffer
as_zehner:      MOV  A, R4
                JMP  as_ziffer
as_einer:       MOV  A, R2
as_ziffer:      MOV  R0, #S_ASZ
                MOV  @R0, A
                SEL  MB0
                CALL check_and_load_effective_address  ; R1 -> Zielzelle, F0 = ungültig
                SEL  MB1
                JF0  as_f003
                MOV  R0, #S_ASZ
                MOV  A, @R0
                MOVP A, @A              ; Muster aus as_tab (gleiche Seite)
                MOV  R2, A
                CLR  A
                MOVX @R1, A             ; Befehlsteil 00
                INC  R1
                MOV  A, R2
                MOVX @R1, A             ; Muster
                SEL  MB0
                JMP  inc_pc
as_f003:        SEL  MB0
                JMP  error_f003
as_f005:        SEL  MB0
                JMP  error_f005

; 31 TST 000: Zifferntaste abwarten. Der Timer-Interrupt legt jede neue Taste in R6' (RAM 0x1E) ab,
; auch während ein Programm läuft; STP setzt außerdem STATUS Bit 0.
s_tst:          MOV  R0, #$1e
                MOV  @R0, #$00          ; alte Tastendrücke verwerfen
tst_l:          MOV  R0, #STATUS
                MOV  A, @R0
                JB0  tst_stp
                MOV  R0, #$1e
                MOV  A, @R0
                JZ   tst_l
                MOV  @R0, #$00
                MOV  R2, A
                ADD  A, #$f5            ; Code >= 11: keine Ziffer
                JC   tst_l
                DEC  R2                 ; Codes 1..10 = Ziffern 0..9
                MOV  R0, #ACCU
                MOV  @R0, #$00
                INC  R0
                MOV  A, R2
                MOV  @R0, A
                SEL  MB0
                JMP  inc_pc
tst_stp:        MOV  R0, #PC            ; PC nicht erhöhen: end_of_instr hält wegen STP an
                MOV  A, @R0
                MOV  R3, A
                SEL  MB0
                JMP  end_of_instr

; 32 JSR xxx (R1 -> Argument): wie SPU, vorher PC+1 auf den Stapel
s_jsr:          MOV  R0, #S_RSP
                MOV  A, @R0
                XRL  A, #RTIEFE
                JZ   js_f008            ; Stapel voll
                MOV  R0, #PC
                MOV  A, @R0
                INC  A                  ; Rücksprung = nächster Befehl
                JZ   js_f003            ; JSR in Zelle 255: kein Rücksprung möglich
                MOV  R4, A
                MOV  R0, #S_RSP
                MOV  A, @R0
                INC  @R0
                ADD  A, #S_RSTAPEL
                MOV  R0, A
                MOV  A, R4
                MOV  @R0, A
                MOVX A, @R1             ; Ziel
js_setze:       MOV  R0, #PC
                MOV  @R0, A
                MOV  R3, A              ; end_of_instr prüft R3 (wie SPU)
                SEL  MB0
                JMP  end_of_instr
js_f003:        SEL  MB0
                JMP  error_f003
js_f008:        SEL  MB0
                MOV  R4, #$08
                JMP  show_error

; 33 RET: oberste Adresse vom Stapel
s_ret:          MOV  R0, #S_RSP
                MOV  A, @R0
                JZ   rt_f009            ; Stapel leer
                DEC  A
                MOV  @R0, A
                ADD  A, #S_RSTAPEL
                MOV  R0, A
                MOV  A, @R0
                JMP  js_setze
rt_f009:        SEL  MB0
                MOV  R4, #$09
                JMP  show_error

; PC über die Tastatur gesetzt (Einsprung aus pc_handler statt MOV R6,#0 / JMP wait_key)
s_pcset:        MOV  R0, #S_RSP
                MOV  @R0, #$00          ; Neustart: Rücksprungstapel leeren
                MOV  R6, #$00
                SEL  MB0
                JMP  wait_key

; 34 PSH: Akku (Datum) auf den Stapel
s_psh:          MOV  R0, #ACCU
                MOV  A, @R0
                JNZ  ps_f005            ; Befehl im Akku
                INC  R0
                MOV  A, @R0
                MOV  R4, A
ps_push:        MOV  R0, #S_RSP
                MOV  A, @R0
                XRL  A, #RTIEFE
                JZ   js_f008            ; Stapel voll
                MOV  A, @R0
                INC  @R0
                ADD  A, #S_RSTAPEL
                MOV  R0, A
                MOV  A, R4
                MOV  @R0, A
                SEL  MB0
                JMP  inc_pc
ps_f005:        SEL  MB0
                JMP  error_f005

; 35 POP: oberster Wert in den Akku
s_pop:          MOV  R0, #S_RSP
                MOV  A, @R0
                JZ   rt_f009            ; Stapel leer
                DEC  A
                MOV  @R0, A
                ADD  A, #S_RSTAPEL
                MOV  R0, A
                MOV  A, @R0
                MOV  R0, #ACCU
                MOV  @R0, #$00
                INC  R0
                MOV  @R0, A
                SEL  MB0
                JMP  inc_pc

; OUT P1A: P1.0-P1.4 (Flash, A12) und P1.7 (Kassette/Fernsteuerung) bleiben 1
; Einsprung aus write_to_p1 (SEL MB1 / JMP s_p1aus statt OUTL P1, A / JMP inc_pc)
s_p1aus:        ORL  A, #$9f
                MOV  R1, #LAST_BYTE_P1
                MOV  @R1, A
                OUTL P1, A
                SEL  MB0
                JMP  inc_pc

; 03 VZG xxx: xxx ms warten (wie das Original ~1 ms je Schritt) und dabei neue Zifferntasten für TSE merken.
; Der Interrupt meldet eine neue Taste nur ~15 ms lang in R6' (0x1E).
                .equ T_SPEICHER, $44    ; zuletzt gedrückte Zifferntaste (Code 1..10) für TSE; sonst egal
s_vzg:          MOVX A, @R1
                JZ   sv_ende
                MOV  R5, A
sv_l:           MOV  R4, #200           ; 2 + 200 x 2 + t_merk 9 + 2 = 413 Zyklen (Original: 412)
sv_w:           DJNZ R4, sv_w
                CALL t_merk
                DJNZ R5, sv_l
sv_ende:        SEL  MB0
                JMP  inc_pc

; t_merk: neue Zifferntaste aus R6' nach T_SPEICHER (und R6' löschen, damit sie nicht doppelt zählt)
t_merk:         MOV  R0, #$1e
                MOV  A, @R0
                JZ   tm_r
                ADD  A, #$f5            ; Code >= 11: keine Ziffer
                JC   tm_r
                MOV  A, @R0
                MOV  @R0, #$00
                MOV  R0, #T_SPEICHER
                MOV  @R0, A
tm_r:           RET
