; =====================================================================
; Firmware 6.x, Block 1111 (0x7800–0x7FFF): Bedienung – Start nach Reset (P1 = FF)
; (bis 5.08 „Hälfte A“; die Befehle liegen seit 6.00 in Block 1101, befehle.asm)
; Michael Moosbauer / Claude, 2026-11
;
; Tasten (Einsprung aus dem Original: cas_handler/cal_handler/run_handler
;   sind auf SEL MB1 / JMP s_cas bzw. s_cal bzw. s_run umgebogen):
;   6.00: Projekte 01..99 statt Bänken (Verzeichnis in Bank 0, siehe treiber.asm)
;   CAS kurz  Pro __                  -> ganzes RAM ins Projekt (neu: anlegen), Start = PC
;   CAS lang  Fr ___ to ___ Pro __ d5t ___ -> Zellen Fr..to ins Projekt ab dst
;   CAL kurz  Projekte durchblättern (Name/Kurzanzeige); CAL halten lädt („LdP nn“), Ziffern: Pro __
;   CAL lang  Pro __ Fr ___ to ___ d5t ___ -> Zellen Fr..to des Projekts ins RAM ab dst
;   RUN lang  bot __                  -> Autoboot-Projekt (00 = aus)
;   Eingabe: bis 3 Ziffern (Projekt: 2), CAS/CAL/RUN übernimmt, CLR löscht, STP bricht ab.
;   Die Flash-Arbeit machen Block 1001 (auftraege.asm, Aufträge) und 1011 (treiber.asm, Treiber und FNI),
;   erreicht über die Sprungtabelle (zu_…).
;
; Fast-Load / Fast-Save zum Pi (Aufträge der Fernsteuerung, F_JOB $20 / $02, Code in 1011):
;   Der Timer-Interrupt ist dabei AUS (Anzeige steht auf „-“, Tasten und Fernsteuerung taub).
;   Leitung P1.7, Ruhepegel high, ein Bit = Low-Puls: 50 µs = 1, 150 µs = 0, LSB zuerst.
;   Rahmen: $C1, erste Zelle, letzte Zelle, je Zelle 2 Byte (Befehl, Argument),
;   CRC-8 (Polynom $07, Start 0) über alles davor.
;   Laden: der CP1 meldet sich alle ~20 ms mit einem 100-µs-Low (bereit), bis der Pi sendet (max. 2 s).
;   Senden: der CP1 wartet 50 ms (der Pi hört dann schon zu) und sendet.
;   Ergebnis in F_JOB: 0 = gut, $EE = Fehler.
;
; Regel: Aufruf einer Original-Routine immer  SEL MB0 / CALL x / SEL MB1
; =====================================================================

                .equ S_CRC,     $60     ; laufende CRC
                .equ S_ZELLE,   $61     ; aktuelle Zelle
                .equ S_LETZTE,  $62     ; letzte Zelle (Fr..to, Fast-Save: vom Pi)
                .equ S_ERSTE,   $63     ; erste Zelle
                .equ S_DST,     $64     ; d5t
                .equ S_GRENZE,  $65     ; Eingabe: größter Wert
                .equ S_FLAG,    $66     ; gehaltene Taste (halten)
                .equ S_ZAHL,    $67     ; Eingabe: Wert
                .equ S_ANZ,     $68     ; Eingabe: Anzahl Ziffern
                .equ S_ZAEHL,   $69     ; Schleifenzähler
                .equ S_TMP,     $6a
                .equ S_SOLL,    $6b     ; erwartete CRC
                .equ S_CRCT,    $6c     ; Zwischenspeicher crc_dazu
                .equ S_SYM,     $6d     ; Zeichen ganz links
                .equ S_SEGZ,    $6e     ; SEG: aktuelle Zelle
                .equ S_SEGN,    $6f     ; SEG: Stelle 0..5
                .equ S_SEGPUF,  $70     ; SEG: 6 Byte Puffer (0x70..0x75)
                .equ S_PB1,     $71     ; Fast-Load/-Save: Zelle (Befehl)
                .equ S_PB2,     $72     ; Fast-Load/-Save: Zelle (Argument)
                .equ S_ASY,     $76     ; AS1..AS3: Stelle 1..3
                .equ S_ASZ,     $77     ; AS: Ziffer
                .equ S_RSP,     $45     ; JSR/RET: Stapelzeiger 0..24 (init löscht 0x20..0x47)
                .equ S_RSTAPEL, $48     ; JSR/RET: Rücksprungadressen 0x48..0x5F
                .equ RTIEFE,    22      ; 6.00: 22 Ebenen (0x48..0x5D), dahinter das Projekt des Programms:
                .equ S_PRES,    $5e     ;   reservierte Bänke (PSK k: k < S_PRES), 0 = kein Projekt
                .equ S_PBANK,   $5f     ;   erste Bank (SEF, PSK 0)
                .equ S_OVFAUS,  $47     ; 1 = Überlauf aus (OVF 000); init löscht 0x20..0x47

                ; ohne Interrupt: Sendeschleife 5 µs je Schritt, Messschleife 15 µs je Schritt
                .equ KURZ,      10      ; 50 µs (Bit 1)
                .equ LANG,      30      ; 150 µs (Bit 0)
                .equ PAUSE,     10      ; 50 µs High nach jedem Bit
                .equ SCHWELLE,  7       ; Low-Zählschritte à 15 µs: bis 6 (~95 µs) = Bit 1

                .equ T_STP,     $0f
                .equ T_CAS,     $11
                .equ T_CLR,     $12
                .equ T_RUN,     $10

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
                .equ G_CAS, $23         ; ⊓ Eimer wird ausgeschüttet (CP1 -> Pi)
                .equ G_CAL, $1c         ; ⊔ Eimer wird gefüllt (Pi -> CP1)
                .equ G_MI, $40          ; -
                .equ G_UN, $08          ; _
                .equ G_N,  $54          ; n

                .org $7800              ; Block 1111 (Start nach Reset, P1 = FF)

; ---------------------------------------------------------------------
; CAS: kurz = ganzes RAM in eine Bank, lang = Teilbereich
; ---------------------------------------------------------------------
s_cas:          CALL leer_weg
                MOV  R3, #T_CAS
                CALL halten
                JC   sc_lang
                CALL proj_frage
                JF1  s_abbruch
                JZ   s_f003             ; Projekt 0 gibt es nicht
                MOV  R0, #F_JOB
                MOV  @R0, #$80
                CALL kopf_5to
                JMP  zu_j_speichern
sc_lang:        MOV  R0, #MEM_SIZE
                MOV  A, @R0
                CALL fr_to_frage        ; Fr ___ to ___ (RAM)
                JF1  s_abbruch
                CALL proj_frage
                JF1  s_abbruch
                JZ   s_f003
                MOV  A, #$ff
                CALL dst_frage          ; d5t ___ (Zelle in der Bank)
                JF1  s_abbruch
                MOV  R0, #S_ERSTE       ; RAM ab Fr
                MOV  A, @R0
                MOV  R0, #F_RAM
                MOV  @R0, A
                MOV  R0, #S_DST         ; Bank ab dst
                MOV  A, @R0
                MOV  R0, #F_ANF
                MOV  @R0, A
                CALL teil_anzahl        ; F_ANZ, C = 1: dst + Anzahl über 255
                JC   s_f003
                MOV  R0, #F_JOB
                MOV  @R0, #$80          ; schreiben, Quelle RAM
                CALL kopf_5to
                JMP  zu_k_teil

s_f003:         SEL  MB0                        ; F-003 im Original zeigen
                JMP  error_f003
s_abbruch:      SEL  MB0
                CALL clear_display
                SEL  MB1
                JMP  s_ende

; ---------------------------------------------------------------------
; CAL: erst die Aufträge der Fernsteuerung (1011, k_cal_vor), dann hierher (s_cal_ui)
; ---------------------------------------------------------------------
s_cal:          JMP  zu_k_cal_vor
s_cal_ui:       CALL leer_weg                   ; CAL von der Tastatur: kurz blättern, lang Teilbereich laden
                MOV  R3, #T_CAL
                CALL halten
                JC   cl_lang
                MOV  R0, #F_BANK        ; 5.05: CAL kurz = Projekte durchblättern, ab dem niedrigsten belegten
                MOV  @R0, #$00
                JMP  zu_bl_suche
cl_lang:        CALL proj_frage
                JF1  s_abbruch
                MOV  A, #$ff
                CALL fr_to_frage        ; Fr ___ to ___ (Zellen der Bank)
                JF1  s_abbruch
                MOV  R0, #MEM_SIZE
                MOV  A, @R0
                CALL dst_frage          ; d5t ___ (RAM)
                JF1  s_abbruch
                MOV  R0, #S_ERSTE       ; Bank ab Fr
                MOV  A, @R0
                MOV  R0, #F_ANF
                MOV  @R0, A
                MOV  R0, #S_DST         ; RAM ab dst
                MOV  A, @R0
                MOV  R0, #F_RAM
                MOV  @R0, A
                CALL teil_anzahl        ; C = 1: dst + Anzahl über 255
                JC   s_f003
                MOV  R0, #MEM_SIZE      ; letzte RAM-Zelle (R4) <= MEM_SIZE?
                MOV  A, @R0
                CPL  A
                ADD  A, R4
                JC   s_f003
                MOV  R0, #F_JOB
                MOV  @R0, #$00          ; lesen
                CALL kopf_ldp
                JMP  zu_k_teil

; teil_anzahl: F_ANZ = to - Fr + 1 (256 -> 0), R4 = dst + to - Fr; C = 1 bei Überlauf über 255
teil_anzahl:    MOV  R0, #S_ERSTE
                MOV  A, @R0
                CPL  A
                INC  A
                MOV  R0, #S_LETZTE
                ADD  A, @R0             ; to - Fr (Fr <= to)
                MOV  R4, A
                INC  A
                MOV  R0, #F_ANZ
                MOV  @R0, A
                MOV  R0, #S_DST
                MOV  A, @R0
                ADD  A, R4
                MOV  R4, A
                RET

; ---------------------------------------------------------------------
; Fragen
; ---------------------------------------------------------------------
; proj_frage: „Pro __“ -> F_BANK (6.00: Projektnummer 1..99) und A (Vorgabe 0), F1 = STP
proj_frage:     MOV  R0, #F_BANK
                MOV  @R0, #$00
                MOV  A, #99
                MOV  R1, #S_GRENZE
                MOV  @R1, A
                MOV  R1, #S_SYM
                MOV  @R1, #G_P
                MOV  R2, #G_R
                MOV  R5, #G_O
                CALL eingabe
                MOV  R0, #F_BANK
                MOV  A, @R0
                RET

; fr_to_frage: „Fr ___“, „to ___“, Grenze A; Vorgabe 0 .. Grenze; danach geordnet. F1 = STP
fr_to_frage:    MOV  R1, #S_GRENZE
                MOV  @R1, A
                MOV  R0, #S_LETZTE
                MOV  @R0, A
                MOV  R0, #S_ERSTE
                MOV  @R0, #$00
                MOV  R1, #S_SYM
                MOV  @R1, #G_F
                MOV  R2, #G_R
                MOV  R5, #$00
                CALL eingabe
                JF1  ft_raus
                MOV  R1, #S_SYM
                MOV  @R1, #G_T
                MOV  R2, #G_O
                MOV  R5, #$00
                MOV  R0, #S_LETZTE
                CALL eingabe
                JF1  ft_raus
                JMP  bereich_ordnen
ft_raus:        RET

; dst_frage: „d5t ___“, Grenze A, Vorgabe Fr. F1 = STP
dst_frage:      MOV  R1, #S_GRENZE
                MOV  @R1, A
                MOV  R0, #S_ERSTE
                MOV  A, @R0
                MOV  R0, #S_DST
                MOV  @R0, A
                MOV  R1, #S_SYM
                MOV  @R1, #G_D
                MOV  R2, #G_S
                MOV  R5, #G_T
                JMP  eingabe

; leer_weg: kein Leerlauf mehr (LEER = 0; wait_key setzt es wieder), damit NIE 04 abgelehnt wird
leer_weg:       MOV  R0, #LEER          ; (nur schreiben: der Interrupt liest LEER nur)
                MOV  @R0, #$00
                RET

; halten: Taste R3 1 s gehalten? C = 1. Nach 1/4, 1/2, 3/4 s rechts _ __ ___.
; Kurzes Drücken lässt die Anzeige in Ruhe (RUN kurz).
halten:         MOV  R0, #S_FLAG
                MOV  A, R3
                MOV  @R0, A
                MOV  R0, #S_TMP
                MOV  @R0, #$00
hl_stufe:       MOV  R0, #S_ZAEHL
                MOV  @R0, #25
hl_w:           MOV  R3, #10
                SEL  MB0
                CALL delay_millis
                SEL  MB1
                MOV  R0, #S_FLAG
                MOV  A, @R0
                MOV  R3, A
                CALL taste_gedrueckt
                JNC  hl_kurz
                MOV  R0, #S_ZAEHL
                MOV  A, @R0
                DEC  A
                MOV  @R0, A
                JNZ  hl_w
                MOV  R0, #S_TMP
                MOV  A, @R0
                JNZ  hl_mehr
                SEL  MB0                ; nach 1/4 s: Anzeige frei machen
                CALL clear_display
                SEL  MB1
hl_mehr:        MOV  R0, #S_TMP
                INC  @R0
                MOV  A, @R0
                MOV  R2, A
                MOV  R5, #G_UN
                CALL zeichen_rechts
                MOV  R0, #S_TMP
                MOV  A, @R0
                XRL  A, #4
                JNZ  hl_stufe
                CLR  C
                CPL  C
                RET
hl_kurz:        CLR  C
                RET

; ---------------------------------------------------------------------
; Ende
; ---------------------------------------------------------------------
s_ende:         ORL  P1, #$c0           ; Leitungen D und T in Ruhe (high)
                MOV  R0, #RC_FLAG       ; Fernsteuerung wieder an, falls die Leitung mal klemmte (nur wenn aus:
                MOV  A, @R0             ;  dann fasst der Interrupt RC_FLAG nicht an)
                JNZ  se_rc
                MOV  @R0, #$01
se_rc:
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
; Hilfen
; ---------------------------------------------------------------------
; taste_gedrueckt: C = 1, wenn der Interrupt die Taste R3 noch als gehalten führt.
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

; kopf_zeigen: Anzeige S_SYM R2 R5 und leere Ziffern
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
bo_ok:          CLR  F1
                RET

; eingabe: Anzeige S_SYM R2 R5 "___", bis zu 3 Ziffern (6.00: Grenze < 100 -> " __", 2 Ziffern), CAS/CAL/RUN übernimmt.
; R0 = Zielvariable (wird bei 0 Ziffern nicht geändert = Vorgabe).
; Wert wird auf S_GRENZE begrenzt. CLR löscht die Eingabe. F1 = STP.
eingabe:        MOV  R1, #S_TMP
                MOV  A, R0
                MOV  @R1, A             ; Ziel merken
                CALL kopf_zeigen
ei_neu:         MOV  R0, #S_ANZ
                MOV  @R0, #$00
                MOV  R0, #S_ZAHL
                MOV  @R0, #$00
                MOV  R0, #$25
                MOV  @R0, #G_UN
                DEC  R0
                MOV  @R0, #G_UN
                DEC  R0
                CALL ei_zwei
                JC   ei_taste           ; zweistellig: Stelle 3 bleibt dunkel
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
                XRL  A, #T_CAL
                JZ   ei_fertig
                MOV  A, R2
                XRL  A, #T_RUN
                JZ   ei_fertig
                MOV  A, R2
                ADD  A, #$f5            ; Ziffern = Codes 1..10
                JC   ei_taste           ; Code >= 11: andere Taste
                MOV  A, R2
                JZ   ei_taste
                DEC  R2                 ; R2 = Ziffer 0..9
                CALL ei_zwei            ; C = 1: zweistellig (fängt eine Stelle weiter rechts an)
                CLR  A
                RLC  A
                MOV  R0, #S_ANZ
                ADD  A, @R0
                XRL  A, #3
                JZ   ei_taste           ; Stellen voll
                ; Ziffer anzeigen an Stelle 3 + Anzahl (zweistellig: 4 + Anzahl)
                XRL  A, #3
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
                MOV  R0, #S_GRENZE      ; begrenzen
                MOV  A, @R0
                CPL  A
                ADD  A, R5              ; C = 1, wenn Wert > Grenze
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
; ei_zwei: C = 1, wenn S_GRENZE < 100 (Projektnummer: zwei Ziffern). Benutzt R1, A.
ei_zwei:        MOV  R1, #S_GRENZE
                MOV  A, @R1
                ADD  A, #$9c            ; C = 1 ab 100
                CPL  C
                RET

; ---------------------------------------------------------------------
; RUN: kurz = wie immer (beim Loslassen); 1 s halten = Autoboot-Projekt (bot __, 00 = aus)
; Einsprung aus run_handler (SEL MB1 / JMP s_run), zurück nach run_weiter.
; ---------------------------------------------------------------------
s_run:          CALL leer_weg           ; R6 bleibt
                MOV  R3, #T_RUN
                CALL halten             ; R6 (getippte Ziffern) bleibt
                JNC  sr_kurz
                MOV  R0, #F_BANK
                MOV  @R0, #$00
                MOV  R1, #S_GRENZE
                MOV  @R1, #99
                MOV  R1, #S_SYM
                MOV  @R1, #G_B
                MOV  R2, #G_O
                MOV  R5, #G_T
                CALL eingabe            ; bot __
                JF1  sr_abbr
                CALL kopf_bot
                JMP  zu_j_autoboot
sr_abbr:        JMP  s_abbruch
sr_kurz:        MOV  A, R6              ; verdrängter Original-Code von run_handler
                XRL  A, #$01
                SEL  MB0
                JMP  run_weiter

; ---------------------------------------------------------------------
; Kopfanzeigen (5.05, 6.00 Projekte): „5to nn“, „LdP nn“, „bot nn“, „Pro nn“ mit F_BANK = Projektnummer
; ---------------------------------------------------------------------
kopf_5to:       MOV  A, #G_S
                MOV  R4, #G_T
                MOV  R5, #G_O
                JMP  kopf_bank
kopf_ldp:       MOV  A, #G_L                    ; „LdP nn“
                MOV  R4, #G_D
                MOV  R5, #G_P
                JMP  kopf_bank
kopf_bot:       MOV  A, #G_B                    ; „bot nn“
                MOV  R4, #G_O
                MOV  R5, #G_T
                JMP  kopf_bank
kopf_pro:       MOV  A, #G_P                    ; „Pro nn“
                MOV  R4, #G_R
                MOV  R5, #G_O
kopf_bank:      MOV  R3, A                  ; (nicht über S_SYM: 0x6D liegt in F_NAME, den $81 noch braucht)
                SEL  MB0
                CALL clear_display      ; benutzt R0, R2
                SEL  MB1
                MOV  R0, #VRAM
                MOV  A, R3
                MOV  @R0, A
                INC  R0
                MOV  A, R4
                MOV  @R0, A
                INC  R0
                MOV  A, R5
                MOV  @R0, A
                MOV  R0, #F_BANK        ; zweistellig an Stelle 4/5 (F0 = 1: ohne Hunderter)
                MOV  R6, #3
                CLR  F0
                CPL  F0
                SEL  MB0
                CALL print_value
                SEL  MB1
                RET

; 5.05 job_kopf: Aufträge der Fernsteuerung mit Interrupt ($80/$81 speichern, $04 laden, $08 Autoboot) –
; erst die Kopfanzeige, dann die Arbeit in 1001
job_kopf:       MOV  R0, #F_JOB
                MOV  A, @R0
                JB7  jk_s
                JB2  jk_l
                CALL kopf_bot
                JMP  zu_j_autoboot
jk_s:           CALL kopf_5to
                JMP  zu_j_speichern
jk_l:           CALL kopf_ldp
                JMP  zu_j_laden

; ---------------------------------------------------------------------
; 5.05 bl_zeige (aus bl_suche, 1001): F_BANK = Projekt, F_NAME 0..5 = Name, F_PUF 0..5 = Kurzanzeige (FF = keine).
; Erst „Pro nn“ ~0,4 s, dann die Anzeige (sonst der Name über asc_seg). CAL kurz: nächstes Projekt,
; CAL halten: laden. Ziffer: normale Eingabe „Pro _n“. STP: Abbruch.
; ---------------------------------------------------------------------
bl_zeige:       CALL kopf_pro
                MOV  R0, #F_PUF
                MOV  A, @R0
                INC  A
                JNZ  bz_bereit          ; eigene Anzeige
                MOV  R0, #F_NAME
                MOV  A, @R0
                INC  A
                JZ   bz_bereit          ; kein Name: F_PUF bleibt FF, „Pro nn“ bleibt stehen
                MOV  R1, #F_PUF
bz_l:           MOV  A, @R0
                CALL asc_seg
                MOV  @R1, A
                INC  R0
                INC  R1
                MOV  A, R1
                XRL  A, #$76            ; F_PUF + 6
                JNZ  bz_l
bz_bereit:      MOV  R0, #S_ZAEHL       ; „Pro nn“ aufblitzen, Tasten dabei schon annehmen
                MOV  @R0, #40
bz_w:           MOV  R3, #10
                SEL  MB0
                CALL delay_millis
                SEL  MB1
                MOV  R0, #$1e
                MOV  A, @R0
                JNZ  bz_taste
                MOV  R0, #S_ZAEHL
                MOV  A, @R0
                DEC  A
                MOV  @R0, A
                JNZ  bz_w
                MOV  R0, #F_PUF
                MOV  A, @R0
                INC  A
                JZ   bz_t
                MOV  R1, #VRAM
bz_c:           MOV  A, @R0
                MOV  @R1, A
                INC  R0
                INC  R1
                MOV  A, R1
                XRL  A, #$26            ; VRAM + 6
                JNZ  bz_c
bz_t:           MOV  R0, #$1e           ; auf eine Taste warten
                MOV  A, @R0
                JZ   bz_t
bz_taste:       MOV  @R0, #$00
                MOV  R2, A
                XRL  A, #T_CAL
                JZ   bz_cal
                MOV  A, R2
                XRL  A, #T_STP
                JZ   bz_stp
                MOV  A, R2
                ADD  A, #$f5            ; Ziffern = Codes 1..10
                JC   bz_t
                MOV  A, R2
                JZ   bz_t
                MOV  @R0, A             ; Ziffer zurücklegen: die Eingabe liest sie wie frisch getippt
                CALL proj_frage
                JF1  bz_stp
                JZ   bz_f003
                JMP  bz_laden
bz_cal:         MOV  R3, #T_CAL
                CALL halten
                JC   bz_laden
                JMP  zu_bl_suche        ; kurz: nächstes Projekt
bz_laden:       CALL kopf_ldp
                JMP  zu_j_laden
bz_stp:         JMP  s_abbruch
bz_f003:        JMP  s_f003

; ---------------------------------------------------------------------
; 5.05 asc_seg: ASCII-Zeichen A -> 7-Segment-Muster A (Kleinbuchstaben wie große, Unbekanntes dunkel).
; Allgemein nutzbar (Bank-Namen beim Blättern, später vielleicht ein Befehl).
; ---------------------------------------------------------------------
                .seite
asc_seg:        JB7  asg_leer            ; ab 0x80 dunkel
                JB6  asg_buchst          ; 0x40..0x7F: Kleinbuchstaben wie große
asg_tab:         ADD  A, #$d4            ; i = Zeichen - 0x2C (5.06: Tabelle erst ab „,“, davor dunkel)
                JNC  asg_leer
                ADD  A, #<asg_tabelle
                MOVP A, @A
                RET
asg_buchst:      ANL  A, #$df            ; 0x60..0x7F -> 0x40..0x5F
                JMP  asg_tab
asg_leer:        CLR  A
                RET
asg_tabelle:     .db $80, $40, $80, $52                        ; , - . /
                .db $3f, $06, $5b, $4f, $66, $6d, $7d, $07    ; 0..7
                .db $7f, $6f, $00, $00, $00, $48, $00, $53    ; 8 9 : ; < = > ?
                .db $00, $77, $7c, $39, $5e, $79, $71, $3d    ; @ A b C d E F G
                .db $76, $06, $1e, $75, $38, $37, $54, $5c    ; H I J K L M n o
                .db $73, $67, $50, $6d, $78, $3e, $1c, $3e    ; P q r S t U v W
                .db $76, $6e, $5b, $39, $64, $0f, $23, $08    ; X Y Z [ \ ] ^ _

; ---------------------------------------------------------------------
; 5.03 boot_warte (aus f_boot, 1001, Anzeige „bot nnn“ steht schon): 2 s warten, jede Taste bricht ab.
; Den Abbruch prüft die Firmware alle 10 ms über die Tastenzustände 0x30..0x35 (R6' hält eine Taste nur ~15 ms).
; ---------------------------------------------------------------------
boot_warte:     CALL kopf_bot           ; (5.05: Anzeige hier statt in Hälfte B)
                MOV  R0, #S_ZAEHL
                MOV  @R0, #200
bw_l:           MOV  R3, #10
                SEL  MB0
                CALL delay_millis
                SEL  MB1
                CALL bw_taste
                JNZ  bw_abbruch
                MOV  R0, #S_ZAEHL
                MOV  A, @R0
                DEC  A
                MOV  @R0, A
                JNZ  bw_l
                MOV  R0, #F_JOB
                MOV  @R0, #$40
                CALL kopf_ldp
                JMP  zu_j_laden
bw_abbruch:     CALL bw_taste           ; loslassen abwarten, Taste verwerfen
                JNZ  bw_abbruch
                MOV  R0, #$1e
                MOV  @R0, #$00
                SEL  MB0
                CALL print_pc
                JMP  wait_key
; bw_taste: A <> 0, wenn der Interrupt irgendeine Taste als gedrückt führt (0x30..0x35)
bw_taste:       MOV  R0, #$30
                MOV  R2, #6
                CLR  A
bw_t:           ORL  A, @R0
                INC  R0
                DJNZ R2, bw_t
                RET

; ---------------------------------------------------------------------
; 5.02 kaltstart (von NIE 09): wie Einschalten. Timer aus, PSW = 0 (Stapel leer, RB0), F0/F1 aus,
; ganzes internes RAM 0x01..0x7F = 0, Ports high, dann init (löscht beide 8155, Version, Autoboot).
; ---------------------------------------------------------------------
kaltstart:      STOP TCNT
                DIS  TCNTI
                DIS  I
                CLR  A
                MOV  PSW, A
                CLR  F0
                CLR  F1
                MOV  R0, #$7f
ks_l:           MOV  @R0, A
                DJNZ R0, ks_l
                ORL  P2, #$ff
                SEL  MB0
                JMP  $000

; 5.02 Reset-Taste: STP aus wait_key. Hält dabei jemand CLR (Tastenzustand Reihe CAS/CLR/PC/ACC = 0x35,
; Code 18), Kaltstart; sonst wie bisher zurück nach wait_key.
s_stp:          MOV  R0, #$35
                MOV  A, @R0
                XRL  A, #18
                JNZ  s_stp_w
                JMP  kaltstart
s_stp_w:        SEL  MB0
                JMP  wait_key

; ---------------------------------------------------------------------
; Start: „  5.02 “ 1 s lang, dann P 000 wie im Original
; Einsprung am Ende von init statt  CALL clear_ram / EN TCNTI / STRT T
; ---------------------------------------------------------------------
s_boot:         MOV  R0, #$7f           ; 5.03b: beim Einschalten ist das interne RAM zufällig. init löscht nur
sb_r:           MOV  @R0, #$00          ; 0x20..0x47; LEER/AUFTRAG (0x16/0x17) und 0x48..0x7F hier wie beim
                DEC  R0                 ; Kaltstart leeren (sonst liefert wait_key Zufall als Taste)
                MOV  A, R0
                XRL  A, #$47
                JNZ  sb_r
                MOV  R0, #$17
                MOV  @R0, #$00
                DEC  R0
                MOV  @R0, #$00
                SEL  MB0
                CALL clear_ram
                CALL clear_display      ; P 000 von vorhin weg
                SEL  MB1
                MOV  R0, #RC_FLAG       ; 5.00: Fernsteuerung immer an
                MOV  @R0, #$01
                EN   TCNTI
                STRT T
                MOV  R0, #$22           ; VRAM: _ _6.22 _ (Version M.mf: Architektur . Benutzer Fehler)
                MOV  @R0, #$fd          ; 6 mit Punkt
                INC  R0
                MOV  @R0, #$5b          ; 2
                INC  R0
                MOV  @R0, #$5b          ; 2   (Version 6.22)
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
                JMP  zu_f_boot

; ---------------------------------------------------------------------
; Original-Demos, ab 5.00 hier oben (Platz unten für die Fernsteuerung):
;   8 RUN Reaktionstest, 9 RUN Countdown. Einsprung demo_8 / demo_9 (SEL MB1 / JMP).
; ---------------------------------------------------------------------
s_demo8:        SEL  MB0
                CALL clear_display
                CALL clear_access_ram_extension_status_bit
                SEL  MB1
                MOV  R0, #$43           ; Wartezeit in s (wird jedes Mal 1 größer, danach Reaktionszeit mod 8)
                INC  @R0
                MOV  A, @R0
dr_w:           MOV  R4, #$04
dr_w2:          MOV  R3, #$fa
                SEL  MB0
                CALL delay_millis
                SEL  MB1
                DJNZ R4, dr_w2
                DEC  A
                JNZ  dr_w
                CLR  C
dr_l:           MOV  R0, #$05           ; R5 zeigen
                MOV  R5, A
                MOV  R6, #$02
                SEL  MB0
                CALL print_value
                SEL  MB1
                MOV  R1, #STATUS
                MOV  A, @R1
                JB0  dr_stp
                MOV  A, R5
                ADD  A, #$01
                JC   dr_fertig
                MOV  R3, #$01
                SEL  MB0
                CALL delay_millis
                SEL  MB1
                JMP  dr_l
dr_stp:         SEL  MB0
                CALL clear_access_ram_extension_status_bit
                SEL  MB1
dr_fertig:      MOV  R6, #$00
                MOV  R0, #$43
                MOV  A, R5
                ANL  A, #$07
                MOV  @R0, A
                CLR  C
                SEL  MB0
                JMP  wait_key

s_demo9:        SEL  MB0                        ; Original-Demo 9 RUN: Countdown 9 … 0
                CALL clear_display
                MOV  R3, #$ff
                CALL delay_millis
                MOV  R3, #$ff
                CALL delay_millis
                SEL  MB1
                MOV  R1, #$09
                MOV  R4, #$0a
dc_l:           MOV  R6, #$ff           ; print_digit schreibt nach VRAM+1+R6 und zählt R6 hoch: alle 6 Stellen
                MOV  R5, #6
dc_z:           MOV  A, R1
                SEL  MB0
                CALL print_digit        ; benutzt R0, R3
                SEL  MB1
                DJNZ R5, dc_z
                MOV  R3, #$ff
                SEL  MB0
                CALL delay_millis
                MOV  R3, #$ff
                CALL delay_millis
                SEL  MB1
                DEC  R1
                DJNZ R4, dc_l
                MOV  R6, #$00
                SEL  MB0
                JMP  wait_key
