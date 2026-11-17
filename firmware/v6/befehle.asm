; =====================================================================
; Firmware 6.x, Block 1101 (0x5800–0x5FFF): Befehle
; Alle Befehls-Erweiterungen der Firmware (bis 5.08 in Hälfte A). Einsprünge aus dem Original über die
; Sprungtabelle (zu_s_neg usw.); zurück ins Original über zu_inc_pc / zu_show_error / … (schaltet auf 1111).
; Gleichwerte (S_*, F_*) stehen in bedienung.asm bzw. treiber.asm (Flash).
; =====================================================================
                .org $5800              ; Block 1101
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
s_neg:          MOV  R0, #ACCU                  ; 14 NEG xxx: Akku XOR xxx
                MOV  A, @R0
                JNZ  b_f005             ; Akku muss ein Datum sein
                MOVX A, @R1             ; Maske = Argument
                JNZ  sn_ok
                MOV  A, #$01            ; NEG 000 = NEG 001 (Original: 0 <-> 1)
sn_ok:          INC  R0
                XRL  A, @R0
                MOV  @R0, A
                JMP  zu_inc_pc

s_und:          CALL b_operand          ; 15 UND xxx: Akku UND Zelle xxx (b_operand: A = Zelle, R0 -> Akku LSB, F1 = Fehler)
                JF1  b_fehler
su_imm:         ANL  A, @R0
                MOV  @R0, A
                JMP  zu_inc_pc

s_oder:         CALL b_operand                  ; 25 ODR xxx: Akku ODER Zelle xxx
                JF1  b_fehler
so_imm:         ORL  A, @R0
                MOV  @R0, A
                JMP  zu_inc_pc

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
                JMP  zu_inc_pc
so_aus:         MOV  @R0, #$01
                JMP  zu_inc_pc

; s_f006: Einsprung aus error_f006 (ADD/SUB-Überlauf). A = Ergebnis modulo 256, R0 -> Akku LSB.
s_f006:         MOV  R4, A
                MOV  R1, #S_OVFAUS
                MOV  A, @R1
                JZ   sf_fehler
                MOV  A, R4
                MOV  @R0, A             ; Überlauf aus: umgebrochenes Ergebnis speichern
                JMP  zu_inc_pc
sf_fehler:      MOV  R4, #$06           ; F-006 wie das Original
                JMP  zu_show_error

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
                SEL  MB1
                JMP  zu_inc_pc
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
                SEL  MB1
                JMP  zu_inc_pc

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

b_fehler:       MOV  A, R4                      ; Fehler aus b_operand zeigen: R4 = 3 -> F-003, sonst F-005
                XRL  A, #$03
                JZ   b_f003
b_f005:
                JMP  zu_error_f005
b_f003:
                JMP  zu_error_f003
b_f002:         MOV  R4, #$02           ; F-002 wie das Original
                JMP  zu_show_error

; 27 SEG xxx (R1 -> Argument). R7 (E/A-Zeiger des Originals) bleibt unberührt.
s_seg:          MOVX A, @R1
                MOV  R0, #S_SEGZ
                MOV  @R0, A             ; aktuelle Zelle
                CPL  A
                JNZ  sg_zellen
                SEL  MB0                ; SEG 255: Anzeige löschen
                CALL clear_display
                SEL  MB1
                JMP  zu_inc_pc
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
                JMP  zu_inc_pc
sg_f003:
                JMP  zu_error_f003
sg_f005:
                JMP  zu_error_f005


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
                JMP  zu_inc_pc
as_f003:
                JMP  zu_error_f003
as_f005:
                JMP  zu_error_f005

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
                JMP  zu_inc_pc
tst_stp:        MOV  R0, #PC            ; PC nicht erhöhen: end_of_instr hält wegen STP an
                MOV  A, @R0
                MOV  R3, A
                JMP  zu_end_of_instr

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
                JMP  zu_end_of_instr
js_f003:
                JMP  zu_error_f003
js_f008:        MOV  R4, #$08
                JMP  zu_show_error

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
rt_f009:        MOV  R4, #$09
                JMP  zu_show_error

; PC über die Tastatur gesetzt (Einsprung aus pc_handler statt MOV R6,#0 / JMP wait_key)
s_pcset:        MOV  R0, #S_RSP
                MOV  @R0, #$00          ; Neustart: Rücksprungstapel leeren
                MOV  R6, #$00
                JMP  zu_wait_key

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
                JMP  zu_inc_pc
ps_f005:
                JMP  zu_error_f005

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
                JMP  zu_inc_pc
po_f009:        JMP  rt_f009            ; 5.06: eigener Sprung, damit der Lückenfüller POP verschieben darf

; OUT P1A: 6.00 ganz ohne Wirkung – P1.5 ist jetzt A13, P1.1 (SCK) A14; alle Bits bleiben 1
; Einsprung aus write_to_p1 (SEL MB1 / JMP zu_s_p1aus statt OUTL P1, A / JMP inc_pc)
s_p1aus:        MOV  R1, #LAST_BYTE_P1  ; 6.00: Port 1 gehört ganz der Firmware (Flash, A12–A14, FNI, NIE).
                MOV  @R1, #$ff          ; Nichts nach P1 schreiben: jedes Bit von P1.1/P1.4/P1.5 wechselte den Block.
                JMP  zu_inc_pc

; 03 VZG xxx: xxx ms warten (wie das Original ~1 ms je Schritt) und dabei neue Zifferntasten für TSE merken.
; Der Interrupt meldet eine neue Taste nur ~15 ms lang in R6' (0x1E).
                .equ T_SPEICHER, $44    ; zuletzt gedrückte Zifferntaste (Code 1..10) für TSE; sonst egal
s_vzg:          MOVX A, @R1                     ; 03 VZG xxx mit Tastengedächtnis für TSE
                JZ   sv_ende
                MOV  R5, A
sv_l:           MOV  R4, #200           ; 2 + 200 x 2 + t_merk 9 + 2 = 413 Zyklen (Original: 412)
sv_w:           DJNZ R4, sv_w
                CALL t_merk
                DJNZ R5, sv_l
sv_ende:
                JMP  zu_inc_pc

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
; 36 PSK / 37 FRD / 38 FWR: Parameter prüfen (5.00 hier, Flash-Arbeit ab sf_ok in 1001)
; 6.10: 48 JOV z (Jump OVerlay): PSK k / PSK n / JOV z – n Zellen (0 = 256) ab Zelle z aus Bank k des Projekts an
; dieselbe Stelle ins RAM, dann weiter bei z (wie SPU). Projektbank (SEF, PSK 0) bleibt. Leere Bank, Überlauf, k zu
; groß, kein Projekt -> F-003. JSR-Rücksprünge bleiben stehen: JOV nur aus dem festen Kern bzw. auf oberster Ebene.
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
sf_gem:         MOV  R2, #3             ; drei Werte vom Stapel (JOV: R5 = $40, R2 = 2)
sf_gem2:        MOVX A, @R1
                MOV  R0, #F_RAM
                MOV  @R0, A
                MOV  R0, #F_ANF         ; (JOV: Zelle in der Bank = Zelle im RAM)
                MOV  @R0, A
                MOV  R0, #F_JOB
                MOV  A, R5
                MOV  @R0, A
                MOV  R0, #S_RSP
                MOV  A, R2
                CPL  A
                INC  A
                ADD  A, @R0             ; C = 1, wenn genug Werte da sind
                JNC  sf_f009
                MOV  @R0, A
                ADD  A, #S_RSTAPEL
                MOV  R1, A
                MOV  A, @R1             ; 6.00: Bank k relativ zum Projekt (0 = erste), k < reservierte Bänke
                MOV  R0, #S_PRES
                CPL  A
                ADD  A, @R0             ; C = 1, wenn k < S_PRES (kein Projekt: S_PRES = 0 -> nie)
                JNC  sf_f003
                MOV  A, @R1
                MOV  R0, #S_PBANK
                ADD  A, @R0
                MOV  R0, #F_BANK
                MOV  @R0, A
                INC  R1
                MOV  A, R5
                JB6  sf_anz             ; JOV: kein Wert für die Zelle in der Bank
                MOV  A, @R1
                MOV  R0, #F_ANF
                MOV  @R0, A
                INC  R1
sf_anz:         MOV  A, @R1
                MOV  R0, #F_ANZ
                MOV  @R0, A
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
                JMP  zu_sf_ok           ; Flash-Arbeit in 1001
sf_f002:        JMP  s_imm              ; 5.06: Befehl 40..46 mit festem Wert, sonst F-002 (A = Befehl - 39)
sf_f009:        JMP  rt_f009
sf_f003:        MOV  R0, #F_JOB
                MOV  @R0, #$00
                MOV  R4, #$03
                JMP  zu_show_error

; 39 TSE 000: Akku = Ziffer der seit dem letzten TSE gedrückten Zifferntaste, sonst 255 (wartet nicht)
s_tse:          MOV  R0, #$1e           ; gerade eben gedrückt? (wie t_merk in 1111)
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
                JMP  zu_inc_pc

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
im_add:
                JMP  zu_add_imm

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
im_gl:          SEL  MB1
                JMP  zu_vgl_imm         ; 42 VGL

im_v2:          XRL  A, #$01            ; A = R5 ^ 2: R5 = 3?
                JZ   im_gr
                JMP  zu_vkl_imm            ; 44 VKL
im_gr:
                JMP  zu_vgr_imm            ; 43 VGR

; 5.06 SEF xxx (47): 6 Byte ab xxx im Bilderbereich (Sektor 0x500..0x5FD) der Bank, aus der das Programm geladen
; wurde (S_PBANK, 0 = keine -> dunkel), auf die Anzeige; SEF 248 = eigene Blätter-Anzeige; SEF 254 = Position
; aus dem Akku (Lauftexte, Animationen); SEF 255 löscht.
; A = Befehl - 47 (aus s_imm), R1 -> Argument. Das Lesen macht 1001 (s_sef) mit F_ANF = xxx.
s_sefa:         JNZ  sa_jov
                MOVX A, @R1
                CPL  A
                JZ   sa_leer            ; SEF 255
                DEC  A
                JZ   sa_akku            ; SEF 254: Position aus dem Akku
                JMP  s_sefc
sa_f002:        JMP  b_f002
sa_jov:         DEC  A                  ; 6.10: 48 JOV
                JNZ  sa_zuf
                MOV  R5, #$40
                MOV  R2, #2
                JMP  sf_gem2
sa_zuf:         DEC  A                  ; 6.20: 49 ZUF
                JNZ  sa_f002
                JMP  s_zuf
sa_leer:        JMP  s_sefl
sa_akku:        JMP  s_sefk

s_sefc:         INC  A                  ; wieder xxx
                CPL  A
                JMP  s_sefb
s_sefk:         MOV  R0, #ACCU_LSB
                MOV  A, @R0
                JMP  s_sefb

s_sefb:         MOV  R0, #F_ANF                 ; SEF mit Bildadresse in A: ohne Programmprojekt dunkel, sonst Block 1001 (s_sef)
                MOV  @R0, A
                MOV  R0, #S_PBANK       ; keine Programmbank (getippt, vom Pi): dunkel
                MOV  A, @R0
                JZ   sb_leer
                JMP  zu_s_sef
sb_leer:        JMP  s_sefl

s_sefl:         SEL  MB0                        ; SEF ohne Programmprojekt: Anzeige löschen
                CALL clear_display
                SEL  MB1
                JMP  zu_inc_pc

; ---------------------------------------------------------------------
; 6.20: 49 ZUF n – Akku = Zufallszahl 0..n-1 (ZUF 0: 0..255). Zustand: 16 Bit in der letzten RAM-Zelle (MEM_SIZE,
; mit CP3 Zelle 255; Befehlsteil = High, Argument = Low). Jeder Aufruf mischt den Timer (läuft ständig, Zeitpunkt
; hängt an den Tastendrücken) ins Low-Byte; Zustand 0 -> 1. Dann Xorshift 7/9/8 (Periode 65535), Ergebnis High-Byte
; mit der kleinsten Maske 2^k-1 >= n-1, Werte >= n verworfen (neuer Schritt) -> gleichverteilt.
; R1 -> Argument. Register: R1 Zelle, R2 Low, R4 High, R5 n, R3 Maske, R0 n-1 bzw. Kandidat.
; ---------------------------------------------------------------------
s_zuf:          MOVX A, @R1             ; n
                MOV  R5, A
                MOV  R0, #MEM_SIZE
                MOV  A, @R0
                SEL  MB0
                CALL compute_effective_address  ; R1 -> letzte Zelle (Befehlsteil), R3 weg
                SEL  MB1
                MOVX A, @R1
                MOV  R4, A              ; High
                INC  R1
                MOVX A, @R1
                MOV  R2, A              ; Low
                MOV  A, T
                XRL  A, R2
                MOV  R2, A
                ORL  A, R4
                JNZ  zf_m
                INC  R2                 ; Zustand 0 -> 1 (Xorshift bliebe sonst bei 0)
zf_m:           MOV  A, R5
                DEC  A
                MOV  R0, A              ; n - 1 (n = 0 -> 255)
                MOV  R3, #0
zf_ml:          MOV  A, R3              ; Maske verdoppeln, bis sie n - 1 abdeckt
                CPL  A
                ANL  A, R0
                JZ   zf_wurf
                MOV  A, R3
                ADD  A, R3
                INC  A
                MOV  R3, A
                JMP  zf_ml
zf_wurf:        MOV  A, R4              ; x ^= x << 7
                RRC  A                  ; C = High Bit 0
                MOV  A, R2
                RRC  A                  ; A = High.0 | Low >> 1, C = Low Bit 0
                XRL  A, R4
                MOV  R4, A
                CLR  A
                RRC  A                  ; A = Low.0 << 7
                XRL  A, R2
                MOV  R2, A
                MOV  A, R4              ; x ^= x >> 9
                CLR  C
                RRC  A
                XRL  A, R2
                MOV  R2, A
                XRL  A, R4              ; x ^= x << 8
                MOV  R4, A
                ANL  A, R3
                MOV  R0, A              ; Kandidat
                MOV  A, R5
                JZ   zf_gut             ; ZUF 0: alles gilt
                MOV  A, R0
                CPL  A
                ADD  A, R5              ; C = 1, wenn Kandidat < n
                JNC  zf_wurf
zf_gut:         MOV  A, R2              ; Zustand zurück in die Zelle
                MOVX @R1, A
                DEC  R1
                MOV  A, R4
                MOVX @R1, A
                MOV  A, R0
                MOV  R3, A
                MOV  R0, #ACCU
                MOV  @R0, #$00
                INC  R0
                MOV  A, R3
                MOV  @R0, A
                JMP  zu_inc_pc
