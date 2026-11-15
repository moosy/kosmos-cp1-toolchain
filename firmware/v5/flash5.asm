; =====================================================================
; Firmware 4.0/5.00: SPI-Flash (IS25LP016D) an Port 1, ab 5.00 dazu FNI (siehe unten)
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
                                        ;   Bit2 Quelle Leitung (FNI, intern $84/$85), Bit6 nach dem Laden starten
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
f_fwr:          CLR  F1                 ; (5.00: FNI meldet Fehler in F1)
                CALL f_neu
                CLR  A
                INC  R0
                MOV  @R0, A
                INC  R0
                MOV  @R0, A             ; Offset 0
                CALL f_wren
                MOV  A, #$20            ; Sektor löschen
                CALL f_cmd
                CALL f_warte
                MOV  R0, #F_JOB         ; FNI ($22/$23): jetzt erst bereit, Kopf holen
                MOV  A, @R0
                JB5  fw_kopf
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
fw_misch:       MOV  R0, #F_JOB         ; FNI: passt der nächste Block in dieses Stück?
                MOV  A, @R0
                JB2  fw_fni
fw_mischen:     MOV  R1, #F_PUF
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
fw_k:           JMP  fw_ende

; FNI-Teile von f_fwr (gleiche Stapelebene: RET verlässt f_fwr mit F1 = 1)
fw_kopf:        CALL kopf_n
                CALL blk_ein
                JF1  fw_abbruch
                CALL kopf_pruef
                JF1  fw_abbruch
                MOV  R0, #F_JOB         ; ab jetzt: schreiben, Quelle Leitung (+ Name bei $23)
                MOV  A, @R0
                ANL  A, #$09            ; $22 -> $84, $23 -> $85, $29 -> $8D (Bit 3: Namensbereich vom Pi)
                ORL  A, #$84
                MOV  @R0, A
                JMP  fw_stueck
fw_fni:         JF0  fw_anh             ; alle Zellen-Blöcke schon da
                MOV  R0, #F_OFH
                MOV  A, @R0
                JB1  fw_weiter          ; ab 0x200: Name/Generation
                RRC  A
                MOV  R0, #F_OFL
                MOV  A, @R0
                RRC  A                  ; erste Zelle des Stücks
                MOV  R3, A
                MOV  R0, #FN_ZELLE
                MOV  A, @R0
                ANL  A, #$fc
                XRL  A, R3
                JNZ  fw_weiter          ; der nächste Block gehört zu einem späteren Stück
                CALL fn_block
                MOV  R0, #FN_ZELLE
                MOV  A, @R0
                ANL  A, #$03
                RL   A
                MOV  R0, #FN_POS
                MOV  @R0, A
                CALL blk_ein
                JF1  fw_abbruch
                CALL anz_durch
                CALL fn_weiter
                JNC  fw_weiter
                CLR  F0
                CPL  F0
fw_weiter:      JMP  fw_mischen
fw_abbruch:     RET
; 5.03: bei $29 (F_JOB Bit 3) holt jedes Stück ab 0x300 einen 8-Byte-Block vom Pi (Namensbereich)
fw_anh:         MOV  R0, #F_JOB
                MOV  A, @R0
                JB3  fwa_1
                JMP  fw_mischen
fwa_1:          MOV  R0, #F_OFH
                MOV  A, @R0
                ADD  A, #$fd            ; C = 1 ab 0x300
                JNC  fw_weiter
                MOV  R0, #FN_POS
                MOV  @R0, #$00
                MOV  R0, #FN_N
                MOV  @R0, #4
                CALL blk_ein
                JF1  fw_abbruch
                CALL anz_durch
                JMP  fw_mischen

; 5.03 (eigener Absatz, f_fwr passt sonst in keine Seite): A = Offset low, R0 = F_OFH.
; Nach dem Stück 0x210..0x217 entscheidet Byte 0x212 (00 = Bank hat Namen, setzt $29), ob 0x218..0x5FF mit muss.
fw_ende:        JZ   fw_k3
                XRL  A, #$18
                JNZ  fwe_s
                MOV  A, @R0
                XRL  A, #$02
                JNZ  fwe_s
                MOV  R0, #F_PUF2        ; eben geschriebenes Byte 0x212
                MOV  A, @R0
                JZ   fwe_s              ; Namen: weiter bis 0x5FF
                JMP  fw_fertig
fw_k3:          MOV  A, @R0
                XRL  A, #$06
                JZ   fw_fertig
fwe_s:          JMP  fw_stueck
fw_fertig:      MOV  R0, #F_OFH
                MOV  @R0, #$02
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
                JB2  fq_anh             ; 0x400..0x7FF
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
                JB2  fq_leitung
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
fq_leitung:     MOV  A, R5              ; FNI: Byte im Stück = Byte im Blockpuffer
                ANL  A, #$07
                ADD  A, #F_LPUF
                MOV  R0, A
                MOV  A, @R0
                JMP  fq_ja
fq_intern:      MOV  A, R5              ; (nur eine Zelle: Byte F_RAM + Bit 0)
                ANL  A, #$01
                ADD  A, R4
                MOV  R0, A
                MOV  A, @R0
                JMP  fq_ja
fq_meta:        JB0  fq_anh             ; 0x300..0x3FF
                MOV  A, R5
                ADD  A, #$f0
                JC   fq_gen
                MOV  R0, #F_JOB
                MOV  A, @R0
                JB0  fq_name
fq_nein:        CLR  C
                RET
fq_anh:         MOV  R0, #F_JOB         ; Namensbereich: bei $29 vom Pi, sonst bleibt der alte Inhalt
                MOV  A, @R0
                JB3  fq_leitung
                CLR  C
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
                JNZ  fq_g3
                MOV  A, #$ff            ; „gültig“ erst ganz am Ende
                JMP  fq_ja
fq_g3:          DEC  A                  ; 5.03: 0x212 = 00 bei $29 (Bank hat Namen), sonst alter Wert
                JNZ  fq_nein
                MOV  R0, #F_JOB
                MOV  A, @R0
                JB3  fq_g4
                JMP  fq_nein
fq_g4:          CLR  A
                JMP  fq_ja

; ---------------------------------------------------------------------
; Befehle 36 PSK xxx, 37 FRD xxx, 38 FWR xxx (R1 -> Argument)
;   PSK xxx: Konstante xxx auf den Stapel
;   PSK b / PSK a / PSK n / FRD r: n Zellen (0 = 256) ab Zelle a der Bank b ins RAM ab r
;   FWR r: umgekehrt. FWR auf Bank 0 -> F-003
; ---------------------------------------------------------------------
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
sf_f010:        MOV  R4, #10
                ; weiter in k_fehler

; k_fehler: Auftrag löschen, F-0(R4) zeigen
k_fehler:       MOV  R0, #F_JOB
                MOV  @R0, #$00
                JMP  za_show_error

; ---------------------------------------------------------------------
; Tasten (5.00): die Abfragen bAn/Fr/to/d5t macht Hälfte A, hier nur die Flash-Arbeit:
;   j_speichern  ganzes RAM nach F_BANK (F_JOB = $80), Start = PC ins Verzeichnis
;   j_laden      Bank F_BANK laden, PC = Start
;   j_autoboot   Autoboot-Bank F_BANK (0 = aus)
;   k_teil       F_ANZ Zellen: F_JOB $80 RAM ab F_RAM -> Bank ab F_ANF, $00 umgekehrt
; Fernsteuerung: Pi schreibt Parameter und zuletzt F_JOB, dann CAL kurz:
;   F_JOB $01 lesen (16 Byte roh: F_BANK, F_SEKT, F_OFH, F_OFL -> F_NAME)
;         $81 speichern mit Name aus F_NAME, $04 laden, $08 Autoboot
;         $10 suchen: ab F_BANK die erste gültige Bank -> F_BANK, F_SEKT, Name in F_NAME
;             (keine mehr: F_SEKT = $80)
;         $20 Fast-Load (Pi -> RAM), $02 Fast-Save (RAM S_ERSTE..S_LETZTE -> Pi), beide in Hälfte A
;   FNI: $20 P-C, $21 C-P, $22/$23 P-F, $24 F-P, $25 Bank komplett (F-P + Kopf), $26 alle Namen
;   fertig: F_JOB = 0 ($EE = FNI fehlgeschlagen)
; ---------------------------------------------------------------------
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

; ganzes RAM nach F_BANK (F_JOB = $80 bzw. $81 mit Name)
j_speichern:    CALL k_flash            ; (5.05: „5to nnn“ zeigt Hälfte A)
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
; Autoboot-Bank F_BANK (RUN lang, Fernsteuerung $08)
j_autoboot:     CALL k_flash            ; (5.05: „bot nnn“ zeigt Hälfte A)
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

; s_cal-Vorspann: Auftrag der Fernsteuerung, sonst CAL von Hand (Hälfte A)
k_cal_vor:      MOV  R0, #F_JOB
                MOV  A, @R0
                JZ   kv_tasten
                XRL  A, #$20            ; FNI nach Wert (Bitabfragen unten passen nicht für $21/$23)
                JZ   kv_pc
                XRL  A, #$01            ; $21
                JZ   kv_cp
                XRL  A, #$03            ; $22
                JZ   kv_pf
                XRL  A, #$01            ; $23
                JZ   kv_pf
                XRL  A, #$07            ; $24
                JZ   kv_fp
                XRL  A, #$01            ; $25 (Bank komplett: wie $24, dazu der Bankkopf)
                JZ   kv_fp
                XRL  A, #$03            ; $26 (alle Namen)
                JZ   kv_nm
                XRL  A, #$0f            ; $29 (5.03: wie $23, dazu Namensbereich 0x300..0x5FF)
                JZ   kv_pf
                MOV  A, @R0
                JB7  kv_job
                JB2  kv_job
                JB3  kv_job
                JMP  k_ende             ; (5.03: $01 roh lesen und $10 Bank suchen entfallen, Verzeichnis per FNI)
kv_pc:          JMP  fni_pc
kv_cp:          JMP  fni_cp
kv_pf:          JMP  fni_pf
kv_fp:          JMP  fni_fp
kv_nm:          JMP  fni_nm
kv_job:         JMP  za_job_kopf        ; 5.05: $80/$81/$04/$08 – Kopfanzeige in Hälfte A, dann j_*
kv_tasten:      JMP  za_s_cal_ui        ; CAL von Hand: Abfragen in Hälfte A

; k_teil: Teilbereich (CAS lang / CAL lang), Parameter aus Hälfte A
k_teil:         CALL k_flash            ; (5.05: „LdA/5to nnn“ zeigt Hälfte A)
                MOV  R0, #F_JOB
                MOV  A, @R0
                JB7  kt_schreib
                MOV  A, R6
                JB7  jl_f011            ; Bank leer
                CALL f_frd
                JMP  k_bereit
kt_schreib:     CALL f_fwr
                JMP  k_bereit

; Bank F_BANK laden, PC = Start aus dem Verzeichnis; F_JOB Bit 6: danach starten
j_laden:        CALL k_flash            ; (5.05: „LdA nnn“ zeigt Hälfte A)
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
                JMP  za_boot_warte      ; „bot nnn“, 2 s warten (Taste bricht ab) in Hälfte A      ; 5.03: 2 s warten (Taste bricht ab) in Hälfte A
fb_nein:        SEL  MB0
                CALL print_pc
                SEL  MB1
                JMP  za_wait_key



; =====================================================================
; FNI (fast, no interrupt), 5.00: Pi <-> 8155 / Flash, Timer-Interrupt aus, getaktet
;   T = P1.6 (Klemme 7, Pi Pin 35 = BCM 19): Takt. Der Pi zieht T low; der CP1 hält T selbst low,
;       solange er nicht bereit ist (wie I2C-Clock-Stretching). Keine Seite ist zeitkritisch.
;   D = P1.7 (Klemme 8, Pi Pin 37 = BCM 26): Daten, low = 0, LSB zuerst.
; Ein Bit: CP1 lässt T los, wartet auf T high, dann auf T low (vom Pi), hält T fest, liest bzw. setzt D.
;   Der Pi legt D vor der fallenden Flanke an (CP1 empfängt) bzw. liest D nach der steigenden (CP1 sendet).
; Kopf: jj, Bank, erste Zelle, Anzahl, CRC-8. Danach Blöcke an 4er-Zellgrenzen (je Zelle 2 Byte), CRC-8;
;   nach jedem Block (auch dem Kopf) ein Quittungsbit des Empfängers: 1 gut, 0 nochmal (3 Versuche).
; Ergebnis F_JOB: 0 gut, $EE Fehler. Anzeige Q-Z (P Pi, C 8155, F Flash), danach rdY bzw. Err.
; Zwischenwerte: KBUF 0x27..0x2A (im Leerlauf frei), Anzeige 0x20/0x21 (während FNI dunkel),
; Blockpuffer 0x78..0x7F (Bereich der Fernsteuerung; der Interrupt ist aus, RC_DAUER danach 0).
; =====================================================================
                .equ FN_ZELLE, $27      ; nächste Zelle
                .equ FN_N,     $28      ; Zellen im Block
                .equ FN_VERS,  $29      ; Versuche
                .equ FN_POS,   $2a      ; Byte-Position im Puffer
                .equ FN_BZ,    $20      ; Bytezähler / erwartete CRC
                .equ FN_CRC,   $21
                .equ F_LPUF,   $78      ; 8 Byte
                .equ F_START,  $3e      ; P-F: Startadresse fürs Verzeichnis, 255 = nicht ändern (= F_RAM)
                .equ G_P,      $73

; ---- Aufträge (aus k_cal_vor)
; $20 Pi -> 8155
fni_pc:         CALL fn_ram_pruef
                JC   fpc_ab
                MOV  A, #G_P
                MOV  R4, #G_C
                CALL fn_an
                CALL kopf_n
                CALL blk_ein
                JF1  fpc_f
                CALL kopf_pruef
                JF1  fpc_f
fpc_l:          CALL fn_block
                CALL blk_ein
                JF1  fpc_f
                CLR  F0
                CALL zellen_ram
                CALL anz_durch
                CALL fn_weiter
                JNC  fpc_l
                JMP  fn_gut
fpc_f:          JMP  fn_fehler
fpc_ab:         JMP  fn_abgelehnt

; $21 8155 -> Pi
fni_cp:         CALL fn_ram_pruef
                JC   fcp_ab
                MOV  A, #G_C
                MOV  R4, #G_P
                CALL fn_an
                CALL kopf_fuellen
                CALL blk_aus
                JF1  fcp_f
fcp_l:          CALL fn_block
                CLR  F0
                CPL  F0
                CALL zellen_ram
                CALL blk_aus
                JF1  fcp_f
                CALL anz_durch
                CALL fn_weiter
                JNC  fcp_l
                JMP  fn_gut
fcp_f:          JMP  fn_fehler
fcp_ab:         JMP  fn_abgelehnt

; $24 Flash -> Pi
fni_fp:         CALL fn_bank_pruef
                JC   ffp_ab
                CALL f_da
                JNC  ffp_ab
                CALL f_zustand          ; R6 = gültiger Sektor
                MOV  A, #G_F
                MOV  R4, #G_P
                CALL fn_an
                CALL kopf_fuellen
                CALL blk_aus
                JF1  ffp_f
ffp_l:          CALL fn_block
                CALL fn_flash_lies
                CALL blk_aus
                JF1  ffp_f
                CALL anz_durch
                CALL fn_weiter
                JNC  ffp_l
                MOV  R0, #F_JOB
                MOV  A, @R0
                XRL  A, #$25
                JNZ  ffp_gut
                MOV  R0, #FN_ZELLE      ; $25: 0x200..0x5FF (Name, Generation, gültig, Namensbereich) als 128 Blöcke à 8
                MOV  @R0, #$00
                MOV  R0, #F_ANF         ; (nach den Zellen frei) Offset high 2..5
                MOV  @R0, #$02
                MOV  R0, #FN_N
                MOV  @R0, #4
ffk_l:          MOV  R0, #FN_POS
                MOV  @R0, #$00
                MOV  R1, #F_LPUF
                MOV  R2, #8
                MOV  R0, #F_ANF
                MOV  A, @R0
                MOV  R3, A
                CALL fn_anh_lies
                CALL blk_aus
                JF1  ffp_f
                CALL anz_durch
                MOV  R0, #FN_ZELLE
                MOV  A, @R0
                ADD  A, #8
                MOV  @R0, A
                JNZ  ffk_l
                MOV  R0, #F_ANF
                INC  @R0
                MOV  A, @R0
                XRL  A, #$06
                JNZ  ffk_l
ffp_gut:        JMP  fn_gut
ffp_f:          JMP  fn_fehler
ffp_ab:         JMP  fn_abgelehnt

; $26 alle Namen: für jede gültige Bank 1..255 drei Blöcke [Bank, 0, Name 0..5] [Name 6..13] [Name 14..15],
; zum Schluss ein Block aus 8 Nullen (Bank 0 = Ende). Anzeige F-P.
fni_nm:         CALL f_da
                JNC  fnm_ab
                MOV  A, #G_F
                MOV  R4, #G_P
                CALL fn_an
                CALL kopf_fuellen
                CALL blk_aus
                JF1  fnm_f
                MOV  R0, #F_BANK
                MOV  @R0, #$00
fnm_l:          CALL naechste_bank
                JNC  fnm_ende
                MOV  R1, #F_LPUF
                MOV  R0, #F_BANK
                MOV  A, @R0
                MOV  @R1, A
                INC  R1
                MOV  @R1, #$00
                INC  R1
                MOV  R0, #FN_ZELLE
                MOV  @R0, #$00
                MOV  R2, #6
                CALL fn_kopf_lies       ; Name 0..5
                CALL fnm_block8
                JF1  fnm_f
                MOV  R1, #F_LPUF
                MOV  R0, #FN_ZELLE
                MOV  @R0, #$06
                MOV  R2, #8
                CALL fn_kopf_lies       ; Name 6..13
                CALL fnm_block8
                JF1  fnm_f
                MOV  R1, #F_LPUF
                MOV  R0, #FN_ZELLE
                MOV  @R0, #$0e
                MOV  R2, #2
                CALL fn_kopf_lies       ; Name 14, 15
                MOV  R0, #FN_N
                MOV  @R0, #1
                CALL fnm_blk
                JF1  fnm_f
                CALL anz_durch
                JMP  fnm_l
fnm_ende:       MOV  R1, #F_LPUF        ; Ende: Bank 0
                MOV  R2, #8
fnm_0:          MOV  @R1, #$00
                INC  R1
                DJNZ R2, fnm_0
                CALL fnm_block8
                JF1  fnm_f
                JMP  fn_gut
fnm_block8:     MOV  R0, #FN_N
                MOV  @R0, #4
fnm_blk:        MOV  R0, #FN_POS
                MOV  @R0, #$00
                JMP  blk_aus
fnm_f:          JMP  fn_fehler
fnm_ab:         JMP  fn_abgelehnt

; 5.05 naechste_bank: ab F_BANK + 1 die nächste gültige Bank (R6 = Sektor) -> C = 1; über 255 hinaus: F_BANK = 0, C = 0
naechste_bank:  MOV  R0, #F_BANK
                INC  @R0
                MOV  A, @R0
                CLR  C
                JZ   nb_raus
                CALL f_zustand
                MOV  A, R6
                JB7  naechste_bank
                CLR  C
                CPL  C
nb_raus:        RET

; 5.05 bl_suche (CAL kurz, Hälfte A): nächste belegte Bank nach F_BANK, nach der letzten wieder von vorn.
; Name 0..5 -> F_NAME, eigene Anzeige (0x5F8..0x5FD) -> F_PUF, weiter in Hälfte A (bl_zeige). Keine: F-011.
bl_suche:       CALL k_flash
                CALL naechste_bank
                JC   bs_da
                CALL naechste_bank      ; von vorn
                JNC  bs_keine
bs_da:          MOV  R0, #FN_ZELLE
                MOV  @R0, #$00
                MOV  R1, #F_NAME
                MOV  R2, #6
                CALL fn_kopf_lies       ; Name 0..5
                MOV  R0, #FN_ZELLE
                MOV  @R0, #$f8
                MOV  R3, #$05
                MOV  R1, #F_PUF
                MOV  R2, #6
                CALL fn_anh_lies        ; Anzeige 0x5F8..0x5FD (FF = keine)
                JMP  za_bl_zeige
bs_keine:       MOV  R4, #11
                JMP  k_fehler

; fn_kopf_lies: R2 Byte ab 0x200 + FN_ZELLE aus dem gültigen Sektor (R6) nach @R1 (leere Bank: FF)
fn_kopf_lies:   MOV  R3, #$02           ; Name ab 0x200
fn_anh_lies:    MOV  A, R6              ; R2 Byte ab Offset R3:FN_ZELLE nach R1 (keine Fassung: FF)
                JB7  fkl_leer
                MOV  R0, #F_SEKT
                MOV  @R0, A
                MOV  R0, #FN_ZELLE
                MOV  A, @R0
                MOV  R0, #F_OFL
                MOV  @R0, A
                DEC  R0
                MOV  A, R3
                MOV  @R0, A
                JMP  f_lies
fkl_leer:       MOV  @R1, #$ff
                INC  R1
                DJNZ R2, fkl_leer
                RET

; $22 / $23 Pi -> Flash (mit Name aus F_NAME); Kopf und Blöcke holt f_fwr selbst (fw_fni_*)
fni_pf:         MOV  R0, #F_BANK
                MOV  A, @R0
                JZ   fpf_ab       ; Bank 0 nur über die anderen Aufträge
                CALL fn_bank_pruef
                JC   fpf_ab
                CALL f_da
                JNC  fpf_ab
                CALL f_zustand
                MOV  A, #G_P
                MOV  R4, #G_F
                CALL fn_an              ; T bleibt low bis nach dem Löschen
                CLR  F0                 ; F0 = alle Blöcke da
                CALL f_fwr
                JF1  fpf_f
                CALL fn_aus
                CALL fn_links
                MOV  R0, #F_START       ; Verzeichnis-Eintrag?
                MOV  A, @R0
                CPL  A
                JZ   fpf_ohne
                CPL  A
                MOV  R0, #F_NAME1
                MOV  @R0, A
                MOV  R0, #F_BANK
                MOV  A, @R0
                JMP  k_verz             ; schreibt Bank 0, dann rdY
fpf_ohne:       JMP  k_bereit
fpf_f:          JMP  fn_fehler
fpf_ab:         JMP  fn_abgelehnt

fn_abgelehnt:   MOV  R0, #F_JOB
                MOV  @R0, #$ee
                JMP  za_s_ende

; ---- Ende
fn_gut:         CALL fn_aus
                CALL fn_links
                JMP  k_bereit           ; rechts rdY, F_JOB = 0
fn_fehler:      CALL fn_aus
                CALL fn_links
                MOV  R0, #$23
                MOV  @R0, #G_E
                INC  R0
                MOV  @R0, #G_R
                INC  R0
                MOV  @R0, #G_R
                MOV  R0, #F_JOB
                MOV  @R0, #$ee
                JMP  za_s_ende

; fn_an: Anzeige Q-Z (A = Q, R4 = Z) rechts, Interrupt aus, D los, T festhalten (= Auftrag übernommen)
fn_an:          MOV  R0, #$23
                MOV  @R0, A
                INC  R0
                MOV  @R0, #G_MI
                INC  R0
                MOV  A, R4
                MOV  @R0, A
                DIS  TCNTI
                STOP TCNT
                MOV  R0, #RC_FLAG       ; angefangene NIE-Antwort (z. B. auf 04) verwerfen: der Interrupt ist aus,
                MOV  @R0, #$01          ;  hier gibt es keinen Wettlauf. Für den Pi heißt „T low“: angenommen.
                ORL  P1, #$80
                ANL  P1, #$bf
                MOV  R0, #F_ANF
                MOV  A, @R0
                MOV  R0, #FN_ZELLE
                MOV  @R0, A
                JMP  anz_durch

; fn_aus: Leitungen los, Fernsteuer-Puffer aufräumen, Interrupt wieder an
fn_aus:         ORL  P1, #$c0
                MOV  R0, #RC_DAUER
                MOV  @R0, #$00
                MOV  A, #$e0
                MOV  T, A
                STRT T
                EN   TCNTI
                RET

; fn_links: Anzeige leeren, Q-Z nach links (0x20..0x22)
fn_links:       MOV  R0, #$23
                MOV  A, @R0
                MOV  R4, A
                INC  R0
                MOV  A, @R0
                MOV  R5, A
                INC  R0
                MOV  A, @R0
                MOV  R3, A
                SEL  MB0
                CALL clear_display      ; (benutzt R0, R2)
                SEL  MB1
                MOV  R0, #VRAM
                MOV  A, R4
                MOV  @R0, A
                INC  R0
                MOV  A, R5
                MOV  @R0, A
                INC  R0
                MOV  A, R3
                MOV  @R0, A
                RET

; anz_durch: Stellen 3..5 (0x23..0x25) je ~0,7 ms von Hand zeigen, danach dunkel (Interrupt ist aus).
; Benutzt R0..R3. Lässt die 8155 im Speicher-Modus zurück.
anz_durch:      ORL  P2, #$80           ; 8155: E/A
                ANL  P2, #$ef           ; interne
                MOV  R1, #$23
                MOV  R3, #$fb           ; Zeilenmaske Stelle 3 (wie im Interrupt: 0x25 = $fe)
ad_l:           MOV  R0, #$01
                CLR  A
                MOVX @R0, A             ; Segmente aus
                MOV  R0, #$03
                MOV  A, R3
                MOVX @R0, A             ; Stelle wählen
                MOV  R0, #$01
                MOV  A, @R1
                MOVX @R0, A             ; Muster
                MOV  R2, #140
ad_w:           DJNZ R2, ad_w
                INC  R1
                MOV  A, R3
                RR   A
                MOV  R3, A
                MOV  A, R1
                XRL  A, #$26
                JNZ  ad_l
                MOV  R0, #$01
                CLR  A
                MOVX @R0, A
                ANL  P2, #$7f           ; Speicher
                RET

; ---- Prüfungen: C = 1, wenn die Zellen F_ANF .. F_ANF + F_ANZ - 1 nicht passen
fn_ram_pruef:   CALL fn_bank_pruef
                JC   frp_r
                MOV  R3, A
                MOV  R0, #MEM_SIZE
                MOV  A, @R0
                CPL  A
                ADD  A, R3              ; C = 1: letzte > MEM_SIZE
frp_r:          RET
fn_bank_pruef:  MOV  R0, #F_ANZ         ; A = letzte Zelle, C = 1: über 255
                MOV  A, @R0
                DEC  A
                MOV  R0, #F_ANF
                ADD  A, @R0
                RET

; ---- Blockeinteilung
; fn_block: FN_N = Zellen von FN_ZELLE bis zur nächsten 4er-Grenze bzw. bis zur letzten Zelle; FN_POS = 0
fn_block:       MOV  R0, #FN_ZELLE
                MOV  A, @R0
                ANL  A, #$03
                CPL  A
                ADD  A, #$05            ; 4 - (Zelle & 3)
                MOV  R2, A
                MOV  R0, #F_ANF
                MOV  A, @R0
                INC  R0
                ADD  A, @R0
                DEC  A                  ; letzte Zelle
                MOV  R3, A
                MOV  R0, #FN_ZELLE
                MOV  A, @R0
                CPL  A
                INC  A
                ADD  A, R3              ; r = letzte - Zelle
                INC  A                  ; r + 1 (0 = 256)
                JZ   fbl_ok
                MOV  R3, A
                CPL  A
                ADD  A, R2              ; C = 1: n > r + 1
                JNC  fbl_ok
                MOV  A, R3
                MOV  R2, A
fbl_ok:         MOV  R0, #FN_N
                MOV  A, R2
                MOV  @R0, A
                MOV  R0, #FN_POS
                MOV  @R0, #$00
                RET
; fn_weiter: FN_ZELLE += FN_N; C = 1, wenn das die letzte war
fn_weiter:      MOV  R0, #FN_N
                MOV  A, @R0
                MOV  R0, #FN_ZELLE
                ADD  A, @R0
                MOV  @R0, A
                MOV  R0, #F_ANF
                MOV  A, @R0
                INC  R0
                ADD  A, @R0
                MOV  R0, #FN_ZELLE
                XRL  A, @R0
                CLR  C
                JNZ  fwt_n
                CPL  C
fwt_n:          RET

; zellen_ram: FN_N Zellen ab FN_ZELLE <-> Puffer F_LPUF. F0 = 0: Puffer -> RAM, F0 = 1: RAM -> Puffer
zellen_ram:     MOV  R0, #FN_POS
                MOV  @R0, #$00
zra_l:          MOV  R0, #FN_POS
                MOV  A, @R0
                MOV  R0, #FN_ZELLE
                ADD  A, @R0
                SEL  MB0
                CALL compute_effective_address  ; -> R1, wählt den 8155
                SEL  MB1
                MOV  R0, #FN_POS
                MOV  A, @R0
                RL   A
                ADD  A, #F_LPUF
                MOV  R0, A
                JF0  zra_hol
                MOV  A, @R0
                MOVX @R1, A
                INC  R0
                INC  R1
                MOV  A, @R0
                MOVX @R1, A
                JMP  zra_w
zra_hol:         MOVX A, @R1
                MOV  @R0, A
                INC  R0
                INC  R1
                MOVX A, @R1
                MOV  @R0, A
zra_w:          MOV  R0, #FN_POS
                INC  @R0
                MOV  A, @R0
                MOV  R0, #FN_N
                XRL  A, @R0
                JNZ  zra_l
                MOV  R0, #FN_POS
                MOV  @R0, #$00
                RET

; fn_flash_lies: FN_N Zellen ab FN_ZELLE der Bank (R6 = Sektor, leer: 0) -> F_LPUF
fn_flash_lies:  MOV  A, R6
                JB7  ffl_leer
                MOV  R0, #F_SEKT
                MOV  @R0, A
                MOV  R0, #FN_ZELLE
                MOV  A, @R0
                CLR  C
                RLC  A
                MOV  R0, #F_OFL
                MOV  @R0, A
                CLR  A
                RLC  A
                DEC  R0
                MOV  @R0, A
                MOV  R1, #F_LPUF
                MOV  R0, #FN_N
                MOV  A, @R0
                ADD  A, @R0
                MOV  R2, A
                JMP  f_lies
ffl_leer:       MOV  R1, #F_LPUF
                MOV  R2, #8
ffl_l:          MOV  @R1, #$00
                INC  R1
                DJNZ R2, ffl_l
                RET

; ---- Kopf
kopf_fuellen:   MOV  R1, #F_LPUF        ; jj, Bank, erste Zelle, Anzahl
                MOV  R0, #F_JOB
                MOV  A, @R0
                MOV  @R1, A
                INC  R1
                MOV  R0, #F_BANK
                MOV  A, @R0
                MOV  @R1, A
                INC  R1
                MOV  R0, #F_ANF
                MOV  A, @R0
                MOV  @R1, A
                INC  R1
                INC  R0
                MOV  A, @R0
                MOV  @R1, A
kopf_n:         MOV  R0, #FN_POS        ; 4 Byte = „2 Zellen“ ab Puffer
                MOV  @R0, #$00
                MOV  R0, #FN_N
                MOV  @R0, #2
                RET
; kopf_pruef: empfangener Kopf = eigene Parameter? sonst F1 = 1
kopf_pruef:     MOV  R1, #F_LPUF
                MOV  R0, #F_JOB
                CALL kp_eins
                MOV  R0, #F_BANK
                CALL kp_eins
                MOV  R0, #F_ANF
                CALL kp_eins
                MOV  R0, #F_ANZ
kp_eins:        MOV  A, @R1
                INC  R1
                XRL  A, @R0
                JZ   kp_ok
                CLR  F1
                CPL  F1
kp_ok:          RET

; ---- Blöcke: 2 * FN_N Byte ab F_LPUF + FN_POS, CRC, Quittungsbit; 3 Versuche. F1 = Fehler.
blk_ein:        MOV  R0, #FN_VERS
                MOV  @R0, #3
be_neu:         CALL blk_anfang
be_b:           CALL byte_ein
                JF1  be_raus
                MOV  @R1, A
                INC  R1
                MOV  R0, #FN_BZ
                MOV  A, @R0
                DEC  A
                MOV  @R0, A
                JNZ  be_b
                MOV  R0, #FN_CRC        ; erwartete CRC merken
                MOV  A, @R0
                MOV  R0, #FN_BZ
                MOV  @R0, A
                CALL byte_ein
                JF1  be_raus
                MOV  R0, #FN_BZ
                XRL  A, @R0
                CLR  C
                JNZ  be_falsch
                CPL  C
                JMP  bit_aus            ; 1 = gut
be_falsch:      CALL bit_aus            ; 0 = nochmal
                JF1  be_raus
                CALL blk_nochmal
                JNC  be_neu
be_raus:        RET

blk_aus:        MOV  R0, #FN_VERS
                MOV  @R0, #3
ba_neu:         CALL blk_anfang
ba_b:           MOV  A, @R1
                INC  R1
                CALL byte_aus
                JF1  ba_raus
                MOV  R0, #FN_BZ
                MOV  A, @R0
                DEC  A
                MOV  @R0, A
                JNZ  ba_b
                MOV  R0, #FN_CRC
                MOV  A, @R0
                CALL byte_aus
                JF1  ba_raus
                CALL bit_ein            ; Quittung vom Pi
                JF1  ba_raus
                JC   ba_raus            ; 1 = gut
                CALL blk_nochmal
                JNC  ba_neu
ba_raus:        RET

; blk_anfang: CRC 0, R1 = F_LPUF + FN_POS, FN_BZ = 2 * FN_N
blk_anfang:     MOV  R0, #FN_CRC
                MOV  @R0, #$00
                MOV  R0, #FN_POS
                MOV  A, @R0
                ADD  A, #F_LPUF
                MOV  R1, A
                MOV  R0, #FN_N
                MOV  A, @R0
                ADD  A, @R0
                MOV  R0, #FN_BZ
                MOV  @R0, A
                RET
; blk_nochmal: noch ein Versuch? C = 1 und F1 = 1: nein
blk_nochmal:    MOV  R0, #FN_VERS
                MOV  A, @R0
                DEC  A
                MOV  @R0, A
                CLR  C
                JNZ  bn_ja
                CLR  F1
                CPL  F1
                CPL  C
bn_ja:          RET

; ---- Bytes (CRC-8 in FN_CRC mitrechnen). F1 = Zeit um.
byte_ein:       CLR  F1                 ; (Bits direkt hier: eine Stapelebene weniger)
                MOV  R3, #8
bye_l:          CALL t_takt
                JF1  bye_r
                ORL  P1, #$80           ; D loslassen: der Pi bestimmt D
                NOP
                NOP
                IN   A, P1
                RLC  A                  ; C = D
                MOV  A, R5
                RRC  A
                MOV  R5, A
                DJNZ R3, bye_l
                MOV  A, R5
                JMP  fn_crc
bye_r:          RET

byte_aus:       CALL fn_crc             ; A bleibt, R5 = A
                CLR  F1
                MOV  R3, #8
bya_l:          MOV  A, R5
                RRC  A
                MOV  R5, A
                CALL t_takt             ; C bleibt
                JF1  bya_r
                JC   bya_1
                ANL  P1, #$7f
                JMP  bya_w
bya_1:          ORL  P1, #$80
bya_w:          DJNZ R3, bya_l
bya_r:          RET

; fn_crc: CRC-8 (Polynom $07) mit A weiterrechnen. A bleibt, R5 = A. Benutzt R0, R2.
fn_crc:         MOV  R5, A
                MOV  R0, #FN_CRC
                XRL  A, @R0
                MOV  R2, #8
fc_l:           CLR  C
                RLC  A
                JNC  fc_w
                XRL  A, #$07
fc_w:           DJNZ R2, fc_l
                MOV  @R0, A
                MOV  A, R5
                RET

; ---- Bits
; bit_ein: ein Bit vom Pi -> C. F1 = Zeit um.
bit_ein:        CALL t_takt
                ORL  P1, #$80           ; D loslassen: der Pi bestimmt D
                NOP
                NOP
                IN   A, P1
                RLC  A
                RET
; bit_aus: C an den Pi. F1 = Zeit um.
bit_aus:        CALL t_takt
                JC   bta_1
                ANL  P1, #$7f
                RET
bta_1:          ORL  P1, #$80
                RET
; t_takt: T loslassen, auf T high, dann auf T low (Pi) warten, T festhalten. Je ~200 ms, sonst F1 = 1.
; Benutzt R2, R4, A; C bleibt.
t_takt:         ORL  P1, #$40
                MOV  R2, #52
tt_h:           MOV  R4, #$00
tt_h1:          IN   A, P1
                JB6  tt_hoch
                DJNZ R4, tt_h1
                DJNZ R2, tt_h
                JMP  tt_um
tt_hoch:        MOV  R2, #52
tt_l:           MOV  R4, #$00
tt_l1:          IN   A, P1
                JB6  tt_w
                ANL  P1, #$bf           ; T festhalten
                RET
tt_w:           DJNZ R4, tt_l1
                DJNZ R2, tt_l
tt_um:          CLR  F1
                CPL  F1
                RET
