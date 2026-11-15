; =====================================================================
; Firmware 5.00, Hälfte A (0x800–0xFFF bei A12 = 1)
; Michael Moosbauer / Claude, 2026-11
;
; Tasten (Einsprung aus dem Original: cas_handler/cal_handler/run_handler
;   sind auf SEL MB1 / JMP s_cas bzw. s_cal bzw. s_run umgebogen):
;   CAS kurz  bAn ___                 -> ganzes RAM in die Bank, Start = PC
;   CAS lang  Fr ___ to ___ bAn ___ d5t ___ -> Zellen Fr..to in die Bank ab dst
;   CAL kurz  bAn ___                 -> Bank laden, PC = Start
;   CAL lang  bAn ___ Fr ___ to ___ d5t ___ -> Zellen Fr..to der Bank ins RAM ab dst
;   RUN lang  bot ___                 -> Autoboot-Bank (000 = aus)
;   Eingabe: bis 3 Ziffern, CAS/CAL/RUN übernimmt, CLR löscht, STP bricht ab.
;   Die Flash-Arbeit selbst macht Hälfte B (flash5.asm), erreicht über die Stummel.
;
; Fast-Load / Fast-Save zum Pi (Aufträge der Fernsteuerung, F_JOB $20 / $02, Code in Hälfte B):
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
                .equ RTIEFE,    23      ; 5.06: 23 Ebenen, 0x5F = S_PBANK (Bank des Programms für SEF)
                .equ S_PBANK,   $5f
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

                .org $800

; ---------------------------------------------------------------------
; CAS: kurz = ganzes RAM in eine Bank, lang = Teilbereich
; ---------------------------------------------------------------------
s_cas:          CALL leer_weg
                MOV  R3, #T_CAS
                CALL halten
                JC   sc_lang
                CALL bank_frage
                JF1  s_abbruch
                JZ   s_f003             ; Bank 0 = Verzeichnis
                MOV  R0, #F_JOB
                MOV  @R0, #$80
                CALL kopf_5to
                JMP  zb_j_speichern
sc_lang:        MOV  R0, #MEM_SIZE
                MOV  A, @R0
                CALL fr_to_frage        ; Fr ___ to ___ (RAM)
                JF1  s_abbruch
                CALL bank_frage
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
                JMP  zb_k_teil

s_f003:         SEL  MB0
                JMP  error_f003
s_abbruch:      SEL  MB0
                CALL clear_display
                SEL  MB1
                JMP  s_ende

; ---------------------------------------------------------------------
; CAL: erst die Aufträge der Fernsteuerung (Hälfte B), dann hierher (s_cal_ui)
; ---------------------------------------------------------------------
s_cal:          JMP  zb_k_cal_vor
s_cal_ui:       CALL leer_weg
                MOV  R3, #T_CAL
                CALL halten
                JC   cl_lang
                MOV  R0, #F_BANK        ; 5.05: CAL kurz = Bänke durchblättern, ab der niedrigsten belegten
                MOV  @R0, #$00
                JMP  zb_bl_suche
cl_lang:        CALL bank_frage
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
                CALL kopf_lda
                JMP  zb_k_teil

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
; bank_frage: „bAn ___“ -> F_BANK und A (Vorgabe 0), F1 = STP
bank_frage:     MOV  R0, #F_BANK
                MOV  @R0, #$00
                MOV  A, #$ff
                MOV  R1, #S_GRENZE
                MOV  @R1, A
                MOV  R1, #S_SYM
                MOV  @R1, #G_B
                MOV  R2, #G_A
                MOV  R5, #G_N
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

; eingabe: Anzeige S_SYM R2 R5 "___", bis zu 3 Ziffern, CAS/CAL/RUN übernimmt.
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
su_imm:         ANL  A, @R0
                MOV  @R0, A
                SEL  MB0
                JMP  inc_pc

s_oder:         CALL b_operand
                JF1  b_fehler
so_imm:         ORL  A, @R0
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
                JMP  s_fbef          ; 36..38 PSK/FRD/FWR, sonst F-002
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
; RUN: kurz = wie immer (beim Loslassen); 1 s halten = Autoboot-Bank (bot ___, 000 = aus)
; Einsprung aus run_handler (SEL MB1 / JMP s_run), zurück nach run_weiter.
; ---------------------------------------------------------------------
s_run:          CALL leer_weg           ; R6 bleibt
                MOV  R3, #T_RUN
                CALL halten             ; R6 (getippte Ziffern) bleibt
                JNC  sr_kurz
                MOV  R0, #F_BANK
                MOV  @R0, #$00
                MOV  R1, #S_GRENZE
                MOV  @R1, #$ff
                MOV  R1, #S_SYM
                MOV  @R1, #G_B
                MOV  R2, #G_O
                MOV  R5, #G_T
                CALL eingabe            ; bot ___
                JF1  sr_abbr
                CALL kopf_bot
                JMP  zb_j_autoboot
sr_abbr:        JMP  s_abbruch
sr_kurz:        MOV  A, R6              ; verdrängter Original-Code von run_handler
                XRL  A, #$01
                SEL  MB0
                JMP  run_weiter

; ---------------------------------------------------------------------
; 5.05 Kopfanzeigen (früher k_kopf in Hälfte B): „5to nnn“, „LdA nnn“, „bot nnn“, „bAn nnn“ mit F_BANK
; ---------------------------------------------------------------------
kopf_5to:       MOV  A, #G_S
                MOV  R4, #G_T
                MOV  R5, #G_O
                JMP  kopf_bank
kopf_lda:       MOV  A, #G_L
                MOV  R4, #G_D
                MOV  R5, #G_A
                JMP  kopf_bank
kopf_bot:       MOV  A, #G_B
                MOV  R4, #G_O
                MOV  R5, #G_T
                JMP  kopf_bank
kopf_ban:       MOV  A, #G_B
                MOV  R4, #G_A
                MOV  R5, #G_N
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
                MOV  R0, #F_BANK
                MOV  R6, #2
                CLR  F0
                SEL  MB0
                CALL print_value
                SEL  MB1
                RET

; 5.05 job_kopf: Aufträge der Fernsteuerung mit Interrupt ($80/$81 speichern, $04 laden, $08 Autoboot) –
; erst die Kopfanzeige, dann die Arbeit in Hälfte B
job_kopf:       MOV  R0, #F_JOB
                MOV  A, @R0
                JB7  jk_s
                JB2  jk_l
                CALL kopf_bot
                JMP  zb_j_autoboot
jk_s:           CALL kopf_5to
                JMP  zb_j_speichern
jk_l:           CALL kopf_lda
                JMP  zb_j_laden

; ---------------------------------------------------------------------
; 5.05 bl_zeige (aus bl_suche, Hälfte B): F_BANK = Bank, F_NAME 0..5 = Name, F_PUF 0..5 = eigene Anzeige (FF = keine).
; Erst „bAn nnn“ ~0,4 s, dann die Anzeige (sonst der Name über asc_seg). CAL kurz: nächste Bank,
; CAL halten: laden. Ziffer: normale Eingabe „bAn __n“. STP: Abbruch.
; ---------------------------------------------------------------------
bl_zeige:       CALL kopf_ban
                MOV  R0, #F_PUF
                MOV  A, @R0
                INC  A
                JNZ  bz_bereit          ; eigene Anzeige
                MOV  R0, #F_NAME
                MOV  A, @R0
                INC  A
                JZ   bz_bereit          ; kein Name: F_PUF bleibt FF, „bAn nnn“ bleibt stehen
                MOV  R1, #F_PUF
bz_l:           MOV  A, @R0
                CALL asc_seg
                MOV  @R1, A
                INC  R0
                INC  R1
                MOV  A, R1
                XRL  A, #$76            ; F_PUF + 6
                JNZ  bz_l
bz_bereit:      MOV  R0, #S_ZAEHL       ; „bAn nnn“ aufblitzen, Tasten dabei schon annehmen
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
                CALL bank_frage
                JF1  bz_stp
                JZ   bz_f003
                JMP  bz_laden
bz_cal:         MOV  R3, #T_CAL
                CALL halten
                JC   bz_laden
                JMP  zb_bl_suche        ; kurz: nächste Bank
bz_laden:       CALL kopf_lda
                JMP  zb_j_laden
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
; 5.03 boot_warte (aus f_boot, Hälfte B, Anzeige „bot nnn“ steht schon): 2 s warten, jede Taste bricht ab.
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
                CALL kopf_lda
                JMP  zb_j_laden
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
                MOV  R0, #$22           ; VRAM: _ _5.00 _
                MOV  @R0, #$ed          ; 5 mit Punkt
                INC  R0
                MOV  @R0, #$3f          ; 0
                INC  R0
                MOV  @R0, #$07          ; 7   (Version 5.07)
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
                JZ   po_f009            ; Stapel leer
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
po_f009:        JMP  rt_f009            ; 5.06: eigener Sprung, damit der Lückenfüller POP verschieben darf

; OUT P1A: P1.0-P1.4 (Flash, A12), P1.6 (FNI-Takt) und P1.7 (Fernsteuerung) bleiben 1; frei nur Klemme 6
; Einsprung aus write_to_p1 (SEL MB1 / JMP s_p1aus statt OUTL P1, A / JMP inc_pc)
s_p1aus:        ORL  A, #$df            ; 5.00: auch P1.6 (Klemme 7 = FNI-Takt) bleibt 1
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

s_demo9:        SEL  MB0
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

; ---------------------------------------------------------------------
; 36 PSK / 37 FRD / 38 FWR: Parameter prüfen (5.00 hier, Flash-Arbeit ab sf_ok in Hälfte B)
; ---------------------------------------------------------------------
s_fbef:         DEC  R1
                MOVX A, @R1
                INC  R1
                ADD  A, #$dc
                JNZ  sf_k36
                MOVX A, @R1             ; 36 PSK
                MOV  R4, A
                JMP  ps_push
sf_k36:         DEC  A
                MOV  R5, #$00
                JZ   sf_gem             ; 37 FRD
                DEC  A
                JZ   sf_fwr
                DEC  A
                JNZ  sf_f002
                JMP  s_tse              ; 39 TSE
sf_fwr:         MOV  R5, #$80           ; 38 FWR
sf_gem:         MOVX A, @R1
                MOV  R0, #F_RAM
                MOV  @R0, A
                MOV  R0, #F_JOB
                MOV  A, R5
                MOV  @R0, A
                MOV  R0, #S_RSP         ; drei Werte vom Stapel
                MOV  A, @R0
                ADD  A, #$fd
                JNC  sf_f009
                MOV  @R0, A
                ADD  A, #S_RSTAPEL
                MOV  R1, A
                MOV  A, @R1
                JNZ  sf_bank            ; 5.07: Bank 0 = eigene Bank (aus der das Programm geladen wurde)
                MOV  R0, #S_PBANK
                MOV  A, @R0
sf_bank:        MOV  R0, #F_BANK
                MOV  @R0, A
                INC  R1
                MOV  A, @R1
                MOV  R0, #F_ANF
                MOV  @R0, A
                INC  R1
                MOV  A, @R1
                INC  R0
                MOV  @R0, A             ; F_ANZ
                DEC  A                  ; n - 1
                MOV  R4, A
                DEC  R0
                ADD  A, @R0             ; F_ANF + n - 1 > 255?
                JC   sf_f003
                MOV  A, R4
                MOV  R0, #F_RAM
                ADD  A, @R0
                JC   sf_f003
                MOV  R4, A              ; letzte RAM-Zelle
                MOV  R0, #MEM_SIZE
                MOV  A, @R0
                CPL  A
                ADD  A, R4
                JC   sf_f003
                MOV  R0, #F_BANK
                MOV  A, @R0
                JZ   sf_f003            ; keine eigene Bank (5.07; Verzeichnis nur über die Tasten)
                JMP  zb_sf_ok           ; Flash-Arbeit in Hälfte B
sf_f002:        JMP  s_imm              ; 5.06: Befehl 40..46 mit festem Wert, sonst F-002 (A = Befehl - 39)
sf_f009:        JMP  rt_f009
sf_f003:        MOV  R0, #F_JOB
                MOV  @R0, #$00
                MOV  R4, #$03
                SEL  MB0
                JMP  show_error

; 39 TSE 000: Akku = Ziffer der seit dem letzten TSE gedrückten Zifferntaste, sonst 255 (wartet nicht)
s_tse:          MOV  R0, #$1e           ; gerade eben gedrückt? (wie t_merk in Hälfte A)
                MOV  A, @R0
                JZ   ts_sp
                ADD  A, #$f5
                JC   ts_sp
                MOV  A, @R0
                MOV  @R0, #$00
                MOV  R0, #$44
                MOV  @R0, A
ts_sp:          MOV  R0, #$44
                MOV  A, @R0
                MOV  @R0, #$00
                MOV  R4, A
                JZ   ts_keine
                ADD  A, #$f5
                JC   ts_keine           ; z. B. noch der RUN-Code vom Start
                MOV  A, R4
                DEC  A                  ; Code 1..10 -> Ziffer 0..9
                JMP  ts_akku
ts_keine:       MOV  A, #$ff
ts_akku:        MOV  R0, #ACCU
                MOV  @R0, #$00
                INC  R0
                MOV  @R0, A
                SEL  MB0
                JMP  inc_pc

; 5.06 s_imm: Befehle 40..46 = ADD/SUB/VGL/VGR/VKL/UND/ODR mit festem Wert (Argument statt Zelle).
; Aus s_fbef: A = Befehl - 39 (>= 1), R1 -> Argument. Akku muss ein Datum sein (sonst F-005).
; Springt in die Original-Routinen hinter deren Zellenprüfung: dort liest MOVX A,@R1 den Wert,
; und R1 zeigt hier eben auf das Argument im Befehl. R0 -> Akku LSB.
s_imm:          ADD  A, #$f8            ; Befehl - 47: C = 1 bei 47 und mehr
                JC   im_f002
                ADD  A, #$07            ; Befehl - 40 = 0..6
                MOV  R5, A
                MOV  R0, #ACCU
                MOV  A, @R0
                JNZ  im_f005
                INC  R0                 ; R0 -> Akku LSB
                CLR  F1                 ; F1 = SUB wie im Original
                JMP  im_d2
im_f002:        JMP  s_sefa             ; 47 SEF, sonst F-002 (A = Befehl - 47)
im_f005:        JMP  b_f005

; 5.06 (kleine Absätze, damit der Lückenfüller sie verteilen kann)
im_d2:          MOV  A, R5
                JZ   im_add             ; 40 ADD
                DEC  A
                JZ   im_sub             ; 41 SUB
                JMP  im_d3
im_sub:         CPL  F1
im_add:         SEL  MB0
                JMP  add_imm

im_d3:          ADD  A, #$fc            ; A = R5 - 5, C = 1 bei 45/46
                JNC  im_v0              ; 42..44
                JZ   im_und             ; 45 UND
                MOVX A, @R1             ; 46 ODR: fester Wert
                JMP  so_imm
im_und:         MOVX A, @R1
                JMP  su_imm
im_v0:          JMP  im_vgl

; 5.06 Vergleiche mit festem Wert (R5 = 2 VGL, 3 VGR, 4 VKL)
im_vgl:         SEL  MB0
                CALL clear_comparison_result    ; benutzt R0, A
                MOV  R0, #ACCU_LSB
                MOV  A, R5
                XRL  A, #$02
                JZ   im_gl
                SEL  MB1
                JMP  im_v2
im_gl:          JMP  vgl_imm            ; 42 VGL (MBF = 0)

im_v2:          XRL  A, #$01            ; A = R5 ^ 2: R5 = 3?
                JZ   im_gr
                SEL  MB0
                JMP  vkl_imm            ; 44 VKL
im_gr:          SEL  MB0
                JMP  vgr_imm            ; 43 VGR

; 5.06 SEF xxx (47): 6 Byte ab xxx im Bilderbereich (Sektor 0x500..0x5FD) der Bank, aus der das Programm geladen
; wurde (S_PBANK, 0 = keine -> dunkel), auf die Anzeige; SEF 248 = eigene Blätter-Anzeige; SEF 254 = Position
; aus dem Akku (Lauftexte, Animationen); SEF 255 löscht.
; A = Befehl - 47 (aus s_imm), R1 -> Argument. Das Lesen macht Hälfte B (s_sef) mit F_ANF = xxx.
s_sefa:         JNZ  sa_f002
                MOVX A, @R1
                CPL  A
                JZ   sa_leer            ; SEF 255
                DEC  A
                JZ   sa_akku            ; SEF 254: Position aus dem Akku
                JMP  s_sefc
sa_f002:        JMP  b_f002
sa_leer:        JMP  s_sefl
sa_akku:        JMP  s_sefk

s_sefc:         INC  A                  ; wieder xxx
                CPL  A
                JMP  s_sefb
s_sefk:         MOV  R0, #ACCU_LSB
                MOV  A, @R0
                JMP  s_sefb

s_sefb:         MOV  R0, #F_ANF
                MOV  @R0, A
                MOV  R0, #S_PBANK       ; keine Programmbank (getippt, vom Pi): dunkel
                MOV  A, @R0
                JZ   sb_leer
                JMP  zb_s_sef
sb_leer:        JMP  s_sefl

s_sefl:         SEL  MB0
                CALL clear_display
                JMP  inc_pc
