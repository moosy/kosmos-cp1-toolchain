; =====================================================================
; Firmware 4.0: SPI-Flash (IS25LP016D) an Port 1
;   P1.0 = CS#, P1.1 = SCK, P1.2 = SI (zum Flash), P1.3 = SO (vom Flash)
; Bank b (0..255) = zwei 4-KB-Sektoren ab b * 8 KB. Im gültigen Sektor:
;   0x000..0x1FF  256 Zellen à 2 Byte
;   0x200..0x20F  Name (16 ASCII, FF = keiner)
;   0x210         Generation (+1 je Schreiben), 0x211 = 00: gültig
; Schreiben: freien Sektor löschen, alten Inhalt in 8-Byte-Stücken hinüber-
; kopieren und dabei die neuen Bytes einsetzen, zuletzt 0x211 = 00.
; Bank 0 = Verzeichnis: Zelle 0 = (00, Autoboot-Bank), Zelle n = (00, Start von Bank n).
; Stapeltiefe: höchstens 4 Ebenen unterhalb eines Einsprungs auf Ebene 0.
; =====================================================================
                .equ F_JOB,  $26        ; Auftrag (Fernsteuerung) / Betriebsart während FRD/FWR
                                        ;   Bit7 schreiben, Bit0 Name aus F_NAME, Bit1 Quelle internes RAM,
                                        ;   Bit6 nach dem Laden starten (Autoboot)
                .equ F_BANK, $2c
                .equ F_SEKT, $2d        ; $00 / $10
                .equ F_OFH,  $2e
                .equ F_OFL,  $2f
                .equ F_ANF,  $3c        ; erste Zelle in der Bank
                .equ F_ANZ,  $3d        ; Anzahl Zellen (0 = 256)
                .equ F_RAM,  $3e        ; erste Zelle im RAM bzw. interner Zeiger
                .equ F_NAME, $60        ; 16 Byte
                .equ F_NAME1,$61
                .equ F_PUF,  $70        ; 8 Byte Puffer
                .equ F_PUF1, $71
                .equ F_PUF2, $72
                .equ F_PUF3, $73
                .equ F_PUFE, $78
                .equ F_KOMPL,$90        ; 256 - F_PUF
                ; R6 (Bank 0) = alter, gültiger Sektor: $00 / $10, $80 = keiner
                .equ T_CAL, $0d
                .equ G_B, $7c
                .equ G_L, $38
                .equ G_A, $77

                .org $1800              ; obere 2 KB der Hälfte B (A12 = 0), im EEPROM 0x0800

; spi: A senden, gleichzeitig ein Byte nach A lesen (MSB zuerst). Benutzt R4, R5.
spi:            MOV  R4, #8
sp_l:           RLC  A
                JC   sp_1
                ANL  P1, #$fb
                JMP  sp_k
sp_1:           ORL  P1, #$04
sp_k:           ORL  P1, #$02           ; SCK hoch: Flash übernimmt SI
                MOV  R5, A
                IN   A, P1
                ANL  P1, #$fd           ; SCK runter
                ANL  A, #$08
                ADD  A, #$f8            ; C = SO
                MOV  A, R5
                DJNZ R4, sp_l
                RLC  A
                RET

; f_start: CS neu setzen, Befehl A senden (CS bleibt low)
f_start:        ORL  P1, #$09           ; CS hoch (beendet den letzten Befehl), SO-Latch 1
                ANL  P1, #$fc           ; CS low, SCK low
                JMP  spi

; f_cmd: Befehl A + Adresse (F_BANK, F_SEKT, F_OFH, F_OFL)
f_cmd:          CALL f_start
                MOV  R0, #F_BANK
                MOV  A, @R0
                RR   A
                RR   A
                RR   A
                ANL  A, #$1f
                CALL spi
                MOV  A, @R0
                SWAP A
                RL   A
                ANL  A, #$e0
                INC  R0
                ORL  A, @R0             ; Sektor
                INC  R0
                ORL  A, @R0             ; Offset high (0..2)
                CALL spi
                INC  R0
                MOV  A, @R0
                JMP  spi

; f_lies: R2 Byte (1..255) ab der Adresse nach @R1 (internes RAM)
f_lies:         MOV  A, #$03
                CALL f_cmd
fl_l:           CALL spi
                MOV  @R1, A
                INC  R1
                DJNZ R2, fl_l
f_aus:          ORL  P1, #$01
                RET

; f_wren: Schreiben erlauben
f_wren:         MOV  A, #$06
                CALL f_start
                JMP  f_aus

; f_warte: bis der Flash fertig ist (Status Bit 0)
f_warte:        MOV  A, #$05
                CALL f_start
fw_l:           CALL spi
                JB0  fw_l
                JMP  f_aus

; f_da: C = 1, wenn ein Flash antwortet (JEDEC-Hersteller nicht 00/FF)
f_da:           MOV  A, #$9f
                CALL f_start
                CALL spi
                ORL  P1, #$01
                JZ   fd_nein
                CPL  A
                JZ   fd_nein
                CLR  C
                CPL  C
                RET
fd_nein:        CLR  C
                RET

; f_zustand: gültigen Sektor von F_BANK suchen -> R6 ($00 / $10 / $80 = keiner)
f_zustand:      MOV  R0, #F_OFH
                MOV  @R0, #$02
                INC  R0
                MOV  @R0, #$10
                MOV  R0, #F_SEKT
                MOV  @R0, #$00
                MOV  R1, #F_PUF
                MOV  R2, #2
                CALL f_lies             ; PUF0 = Gen 0, PUF1 = gültig 0
                MOV  R0, #F_SEKT
                MOV  @R0, #$10
                MOV  R2, #2
                CALL f_lies             ; PUF2 = Gen 1, PUF3 = gültig 1
                MOV  R6, #$80
                MOV  R0, #F_PUF3
                MOV  A, @R0
                JNZ  fz_k1
                MOV  R6, #$10
fz_k1:          MOV  R0, #F_PUF1
                MOV  A, @R0
                JNZ  fz_ende            ; Sektor 0 ungültig
                MOV  A, R6
                JB7  fz_s0              ; nur Sektor 0 gültig
                MOV  R0, #F_PUF         ; beide: Sektor 1, wenn Gen 1 = Gen 0 + 1
                MOV  A, @R0
                INC  A
                MOV  R0, #F_PUF2
                XRL  A, @R0
                JZ   fz_ende
fz_s0:          MOV  R6, #$00
fz_ende:        RET

; f_ofs: Offset = 2 * F_ANF
f_ofs:          MOV  R0, #F_ANF
                MOV  A, @R0
                CLR  C
                RLC  A
                MOV  R0, #F_OFL
                MOV  @R0, A
                CLR  A
                RLC  A
                DEC  R0
                MOV  @R0, A
                RET

; f_frd: F_ANZ Zellen ab F_ANF der Bank F_BANK ins RAM ab F_RAM (leere Bank: 0). R6 von f_zustand.
f_frd:          MOV  A, R6
                MOV  R0, #F_SEKT
                MOV  @R0, A
                CALL f_ofs
                MOV  A, #$03
                CALL f_cmd
                MOV  R0, #F_ANZ
                MOV  A, @R0
                MOV  R2, A
fr_l:           MOV  R0, #F_RAM
                MOV  A, @R0
                INC  @R0
                SEL  MB0
                CALL compute_effective_address
                SEL  MB1
                CALL fr_byte
                MOVX @R1, A
                INC  R1
                CALL fr_byte
                MOVX @R1, A
                DJNZ R2, fr_l
                JMP  f_aus
fr_byte:        CALL spi
                MOV  R5, A
                MOV  A, R6
                JB7  fb_null
                MOV  A, R5
                RET
fb_null:        CLR  A
                RET

; f_neu: F_SEKT = freier Sektor
f_neu:          MOV  A, R6
                XRL  A, #$10
                ANL  A, #$10
                MOV  R0, #F_SEKT
                MOV  @R0, A
                RET

; f_fwr: Bank F_BANK neu schreiben (Betriebsart F_JOB, R6 von f_zustand)
f_fwr:          CALL f_neu
                CLR  A
                INC  R0
                MOV  @R0, A
                INC  R0
                MOV  @R0, A             ; Offset 0
                CALL f_wren
                MOV  A, #$20            ; Sektor löschen
                CALL f_cmd
                CALL f_warte
fw_stueck:      MOV  R1, #F_PUF
                MOV  R2, #8
                MOV  A, R6
                JB7  fw_leer
                MOV  R0, #F_SEKT
                MOV  @R0, A
                CALL f_lies             ; altes Stück
                JMP  fw_misch
fw_leer:        MOV  R0, #F_OFH         ; keine alte Fassung: Zellen 00, Rest FF
                MOV  A, @R0
                ADD  A, #$fe            ; C = 1 ab 0x200
                CLR  A
                JNC  fw_l0
                CPL  A
fw_l0:          MOV  @R1, A
                INC  R1
                DJNZ R2, fw_l0
fw_misch:       MOV  R1, #F_PUF
fm_l:           CALL f_quelle
                JNC  fm_w
                MOV  @R1, A
fm_w:           INC  R1
                MOV  A, R1
                XRL  A, #F_PUFE
                JNZ  fm_l
                CALL f_neu
                CALL f_wren
                MOV  A, #$02            ; Stück schreiben
                CALL f_cmd
                MOV  R1, #F_PUF
                MOV  R2, #8
fp_l:           MOV  A, @R1
                CALL spi
                INC  R1
                DJNZ R2, fp_l
                CALL f_warte
                MOV  R0, #F_OFL         ; nächstes Stück
                MOV  A, @R0
                ADD  A, #8
                MOV  @R0, A
                DEC  R0
                JNC  fw_k
                INC  @R0
fw_k:           XRL  A, #$18
                JNZ  fw_stueck
                MOV  A, @R0
                XRL  A, #$02
                JNZ  fw_stueck          ; bis 0x217
                INC  R0
                MOV  @R0, #$11          ; zuletzt: gültig
                CALL f_wren
                MOV  A, #$02
                CALL f_cmd
                CLR  A
                CALL spi
                JMP  f_warte

; f_quelle: neues Byte für Pufferstelle R1? C = 1: A = neuer Wert. Benutzt R0, R2..R5.
f_quelle:       MOV  R0, #F_OFL
                MOV  A, R1
                ADD  A, #F_KOMPL
                ADD  A, @R0
                MOV  R5, A              ; lo = Offset low
                DEC  R0
                MOV  A, @R0
                JB1  fq_meta
                RRC  A                  ; C = Offset Bit 8
                MOV  A, R5
                RRC  A                  ; Zelle in der Bank
                MOV  R0, #F_ANF
                CPL  A
                ADD  A, @R0
                CPL  A                  ; d = Zelle - F_ANF
                MOV  R4, A
                INC  R0
                MOV  A, @R0
                JZ   fq_drin            ; F_ANZ = 0: alle 256
                MOV  A, R4
                CPL  A
                ADD  A, @R0             ; C = 1, wenn d < F_ANZ
                JNC  fq_nein
fq_drin:        INC  R0
                MOV  A, @R0
                ADD  A, R4
                MOV  R4, A              ; RAM-Zelle bzw. interner Zeiger
                MOV  R0, #F_JOB
                MOV  A, @R0
                JB1  fq_intern
                MOV  A, R1
                MOV  R2, A
                MOV  A, R4
                SEL  MB0
                CALL compute_effective_address
                SEL  MB1
                MOV  A, R5
                JB0  fq_ung
                JMP  fq_x
fq_ung:         INC  R1
fq_x:           MOVX A, @R1
                XCH  A, R2
                MOV  R1, A
                MOV  A, R2
                JMP  fq_ja
fq_intern:      MOV  A, R5              ; (nur eine Zelle: Byte F_RAM + Bit 0)
                ANL  A, #$01
                ADD  A, R4
                MOV  R0, A
                MOV  A, @R0
                JMP  fq_ja
fq_meta:        MOV  A, R5
                ADD  A, #$f0
                JC   fq_gen
                MOV  R0, #F_JOB
                MOV  A, @R0
                JB0  fq_name
fq_nein:        CLR  C
                RET
fq_name:        MOV  A, R5
                ADD  A, #F_NAME
                MOV  R0, A
                MOV  A, @R0
fq_ja:          CLR  C
                CPL  C
                RET
fq_gen:         JNZ  fq_g2
                MOV  A, @R1             ; alte Generation + 1 (keine: FF + 1 = 0)
                INC  A
                JMP  fq_ja
fq_g2:          DEC  A
                JNZ  fq_nein
                MOV  A, #$ff            ; „gültig“ erst ganz am Ende
                JMP  fq_ja

; ---------------------------------------------------------------------
; Befehle 36 PSK xxx, 37 FRD xxx, 38 FWR xxx (R1 -> Argument)
;   PSK xxx: Konstante xxx auf den Stapel
;   PSK b / PSK a / PSK n / FRD r: n Zellen (0 = 256) ab Zelle a der Bank b ins RAM ab r
;   FWR r: umgekehrt. FWR auf Bank 0 -> F-003
; ---------------------------------------------------------------------
s_fbef:         DEC  R1
                MOVX A, @R1
                INC  R1
                ADD  A, #$dc
                JNZ  sf_k36
                MOVX A, @R1             ; 36 PSK
                MOV  R4, A
                JMP  za_ps_push
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
                MOV  R0, #F_BANK
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
                MOV  A, R5
                JZ   sf_ok
                MOV  R0, #F_BANK
                MOV  A, @R0
                JZ   sf_f003            ; Bank 0 nur über die Tasten
sf_ok:          CALL f_da
                JNC  sf_f010
                CALL f_zustand
                MOV  R0, #F_JOB
                MOV  A, @R0
                JB7  sf_schreiben
                CALL f_frd
                JMP  sf_fertig
sf_schreiben:   CALL f_fwr
                JMP  sf_fertig
sf_fertig:      MOV  R0, #F_JOB
                MOV  @R0, #$00
                JMP  za_inc_pc
sf_f002:        JMP  za_b_f002
sf_f009:        JMP  za_rt_f009
sf_f003:        MOV  R4, #$03
                JMP  k_fehler
sf_f010:        MOV  R4, #10
                ; weiter in k_fehler

; k_fehler: Auftrag löschen, F-0(R4) zeigen
k_fehler:       MOV  R0, #F_JOB
                MOV  @R0, #$00
                JMP  za_show_error

; ---------------------------------------------------------------------
; Tasten: nnn CAS = RAM nach Bank nnn (Start = PC), nnn CAL = Bank nnn laden,
;         nnn CAL 1 s halten = Autoboot-Bank nnn (000 = aus)
; Fernsteuerung: Pi schreibt Parameter und zuletzt F_JOB, dann CAL kurz:
;   F_JOB $01 lesen (16 Byte roh: F_BANK, F_SEKT, F_OFH, F_OFL -> F_NAME)
;         $81 speichern mit Name aus F_NAME, $04 laden, $08 Autoboot
;         $10 suchen: ab F_BANK die erste gültige Bank -> F_BANK, F_SEKT, Name in F_NAME
;             (keine mehr: F_SEKT = $80)
;   fertig: F_JOB = 0
; ---------------------------------------------------------------------
; k_zahl: 3 getippte Ziffern -> A, F_BANK. Sonst F-001.
k_zahl:         MOV  A, R6
                XRL  A, #$03
                JNZ  kz_f001
                MOV  R0, #KBUF
                MOV  R2, #$02
                SEL  MB0
                CALL digits_to_number
                SEL  MB1
                MOV  R0, #F_BANK
                MOV  @R0, A
                RET
kz_f001:        MOV  R4, #$01
                JMP  k_fehler

; k_kopf: Anzeige A R4 R5 und Bank dreistellig
k_kopf:         MOV  R3, A
                SEL  MB0
                CALL clear_display      ; (benutzt R0, R2)
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

; k_bereit: rechts „rdY“, Ende
k_bereit:       MOV  R0, #$23
                MOV  @R0, #G_R
                INC  R0
                MOV  @R0, #G_D
                INC  R0
                MOV  @R0, #G_Y
k_ende:         MOV  R0, #F_JOB
                MOV  @R0, #$00
                JMP  za_s_ende

; nnn CAS
k_cas:          CALL k_zahl
                JZ   k_f003
                MOV  R0, #F_JOB
                MOV  @R0, #$80
j_speichern:    MOV  A, #G_S
                MOV  R4, #G_T
                MOV  R5, #G_O
                CALL k_kopf             ; Sto nnn
                CALL k_flash
                MOV  R0, #F_ANF         ; ganze Bank: Zellen 0..MEM_SIZE aus RAM 0
                MOV  @R0, #$00
                INC  R0
                MOV  R1, #MEM_SIZE
                MOV  A, @R1
                INC  A
                MOV  @R0, A
                INC  R0
                MOV  @R0, #$00
                CALL f_fwr
                MOV  R0, #F_BANK        ; Verzeichnis: Zelle nnn = (00, PC)
                MOV  A, @R0
                MOV  R1, #PC
                MOV  R0, #F_NAME1
                XCH  A, @R1             ; A = PC, PC-Zelle kurz = nnn
                MOV  @R0, A
                XCH  A, @R1             ; PC zurück, A = nnn
                JMP  k_verz
; nnn CAL halten: Autoboot (auch Fernsteuerung $08)
j_autoboot:     MOV  A, #G_B
                MOV  R4, #G_O
                MOV  R5, #G_T
                CALL k_kopf             ; bot nnn
                CALL k_flash
                MOV  R0, #F_BANK
                MOV  A, @R0
                MOV  R0, #F_NAME1
                MOV  @R0, A
                CLR  A                  ; Zelle 0
k_verz:         MOV  R0, #F_ANF
                MOV  @R0, A
                INC  R0
                MOV  @R0, #$01
                INC  R0
                MOV  @R0, #F_NAME
                MOV  R0, #F_NAME
                MOV  @R0, #$00
                MOV  R0, #F_BANK
                MOV  @R0, #$00
                MOV  R0, #F_JOB
                MOV  @R0, #$82          ; schreiben, Quelle intern
                CALL f_zustand
                CALL f_fwr
                JMP  k_bereit

; k_flash: Flash da? sonst F-010. Dann f_zustand.
k_flash:        CALL f_da
                JNC  kf_f010
                JMP  f_zustand
kf_f010:        MOV  R4, #10            ; (Stapel: k_fehler springt nach show_error, der räumt nicht auf –
                JMP  k_fehler           ;  egal, wait_key läuft auf beliebiger Tiefe)
k_f003:         MOV  R4, #$03
                JMP  k_fehler

; s_cal-Vorspann: Auftrag der Fernsteuerung oder nnn CAL
k_cal_vor:      MOV  R0, #F_JOB
                MOV  A, @R0
                JZ   kv_tasten
                JB7  kv_speichern
                JB0  j_lesen
                JB2  kv_laden
                JB3  kv_auto
                JB4  j_suche
                JMP  k_ende
kv_speichern:   JMP  j_speichern
kv_laden:       JMP  j_laden
kv_auto:        JMP  j_autoboot
kv_tasten:      MOV  A, R6
                JNZ  k_cal
                JMP  za_s_cal_kass      ; ohne Zahl: Kassette wie immer
j_suche:        CALL f_da
                JNC  kf_f010
js_l:           CALL f_zustand
                MOV  A, R6
                JB7  js_weiter
                MOV  R0, #F_SEKT
                MOV  @R0, A
                INC  R0
                MOV  @R0, #$02          ; Name ab 0x200
                INC  R0
                MOV  @R0, #$00
                JMP  j_lesen
js_weiter:      MOV  R0, #F_BANK
                INC  @R0
                MOV  A, @R0
                JNZ  js_l
                MOV  R0, #F_SEKT
                MOV  @R0, #$80
                JMP  k_ende
j_lesen:        MOV  R1, #F_NAME
                MOV  R2, #16
                CALL f_lies
                JMP  k_ende

k_cal:          CALL k_zahl
                MOV  R0, #F_OFL         ; (frei) Zähler: 100 x 10 ms
                MOV  @R0, #100
kc_l:           MOV  R3, #T_CAL
                CALL tg_b
                JNC  kc_kurz
                MOV  R3, #10
                SEL  MB0
                CALL delay_millis
                SEL  MB1
                MOV  R0, #F_OFL
                MOV  A, @R0
                DEC  A
                MOV  @R0, A
                JNZ  kc_l
kc_los:         MOV  R3, #T_CAL         ; gehalten: erst loslassen
                CALL tg_b
                JC   kc_los
                JMP  j_autoboot
kc_kurz:        MOV  R0, #F_BANK
                MOV  A, @R0
                JZ   k_f003

; Bank F_BANK laden, PC = Start aus dem Verzeichnis; F_JOB Bit 6: danach starten
j_laden:        MOV  A, #G_L
                MOV  R4, #G_D
                MOV  R5, #G_A
                CALL k_kopf             ; LdA nnn
                CALL k_flash
                MOV  A, R6
                JB7  jl_f011            ; Bank leer
                MOV  R0, #F_ANF
                MOV  @R0, #$00
                INC  R0
                MOV  R1, #MEM_SIZE
                MOV  A, @R1
                INC  A
                MOV  @R0, A
                INC  R0
                MOV  @R0, #$00
                CALL f_frd
                MOV  R0, #F_BANK        ; Start: Bank 0, Zelle nnn, Byte 2
                MOV  A, @R0
                MOV  @R0, #$00
                MOV  R0, #F_ANF
                MOV  @R0, A
                CALL f_zustand
                CALL f_ofs
                MOV  R0, #F_OFL         ; Byte 2 der Zelle
                INC  @R0
                MOV  A, R6
                MOV  R0, #F_SEKT
                MOV  @R0, A
                MOV  R1, #PC
                MOV  @R1, #$00
                JB7  jl_ohne
                MOV  R2, #1
                CALL f_lies
jl_ohne:        MOV  R0, #S_RSP
                MOV  @R0, #$00
                MOV  R0, #F_JOB
                MOV  A, @R0
                MOV  @R0, #$00
                JB6  jl_start
                SEL  MB0
                CALL print_pc
                SEL  MB1
                JMP  za_s_ende
jl_start:       MOV  R6, #$00
                MOV  A, #$01            ; run_weiter: JNZ not_one -> Programm ab PC
                JMP  za_run_weiter
jl_f011:        MOV  R4, #11
                JMP  k_fehler

; Autoboot beim Einschalten (aus s_boot): Bank 0 Zelle 0 Byte 2
f_boot:         CALL f_da
                JNC  fb_nein
                MOV  R0, #F_BANK
                MOV  @R0, #$00
                CALL f_zustand
                MOV  A, R6
                JB7  fb_nein
                MOV  R0, #F_SEKT
                MOV  @R0, A
                INC  R0
                MOV  @R0, #$00
                INC  R0
                MOV  @R0, #$01
                MOV  R1, #F_BANK
                MOV  R2, #1
                CALL f_lies
                MOV  R0, #F_BANK
                MOV  A, @R0
                JZ   fb_nein
                MOV  A, #G_B
                MOV  R4, #G_O
                MOV  R5, #G_T
                CALL k_kopf             ; bot nnn, 2 s, Taste bricht ab
                MOV  R0, #S_ZAEHL
                MOV  @R0, #200
fb_w:           MOV  R3, #10
                SEL  MB0
                CALL delay_millis
                SEL  MB1
                CALL k_taste            ; irgendeine Taste gedrückt? (R6' hält sie nur ~15 ms)
                JNZ  fb_abbruch
                MOV  R0, #S_ZAEHL
                MOV  A, @R0
                DEC  A
                MOV  @R0, A
                JNZ  fb_w
                MOV  R0, #F_JOB
                MOV  @R0, #$40
                JMP  j_laden
fb_abbruch:     CALL k_taste            ; loslassen abwarten, Taste verwerfen
                JNZ  fb_abbruch
                MOV  R0, #$1e
                MOV  @R0, #$00
fb_nein:        SEL  MB0
                CALL print_pc
                SEL  MB1
                JMP  za_wait_key

; tg_b: C = 1, wenn der Interrupt die Taste R3 noch als gedrückt führt (Kopie von taste_gedrueckt)
tg_b:           MOV  R0, #$30
                MOV  R2, #6
tgb_l:          MOV  A, @R0
                XRL  A, R3
                JZ   tgb_ja
                INC  R0
                DJNZ R2, tgb_l
                CLR  C
                RET
tgb_ja:         CLR  C
                CPL  C
                RET

; k_taste: A <> 0, wenn der Interrupt irgendeine Taste als gedrückt führt (0x30..0x35)
k_taste:        MOV  R0, #$30
                MOV  R2, #6
                CLR  A
kt_l:           ORL  A, @R0
                INC  R0
                DJNZ R2, kt_l
                RET

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
                JMP  za_inc_pc
