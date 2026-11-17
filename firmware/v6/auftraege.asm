; =====================================================================
; Firmware 6.x, Block 1001 (0x4800–0x4FFF): Aufträge
; Was der Flash tun soll: Tasten-Aufträge (Speichern, Laden, Autoboot, Teilbereich, Blättern), SEF, PSK/FRD/FWR
; nach der Prüfung, Autoboot beim Einschalten. Die Arbeit am Flash selbst macht der Treiber in 1011
; (treiber.asm), erreichbar über Fernaufrufe fa_X in der Sprungtabelle:
;   fa_X:  ORL P1,#$20 (-> 1011)  CALL X  ANL P1,#$df (-> 1001)  RET
; Ein Fernaufruf kostet eine Stapelebene mehr als ein CALL im selben Block.
; Gleichwerte (F_*, FN_*) stehen in treiber.asm.
; =====================================================================
                .org $4800              ; Block 1001
; 5.06 s_sef: SEF xxx (aus 1101, F_ANF = xxx, S_PBANK <> 0): 6 Byte ab Sektor-Offset 0x500 + xxx der
; Programmbank -> Anzeige 0x20..0x25. S_PBANK setzt nur ein gelungenes j_laden, die Bank ist also gültig.
; Interrupt bleibt an (wie FRD).
s_sef:          MOV  R0, #S_PBANK
                MOV  A, @R0
                MOV  R0, #F_BANK
                MOV  @R0, A
                CALL fa_f_zustand
                MOV  A, R6
                MOV  R0, #F_SEKT
                MOV  @R0, A
                INC  R0
                MOV  @R0, #$05          ; F_OFH: Bilderbereich ab 0x500
                MOV  R1, #F_ANF
                MOV  A, @R1
                INC  R0
                MOV  @R0, A             ; F_OFL = xxx
                MOV  R1, #$20
                MOV  R2, #6
                CALL fa_f_lies
                JMP  zu_inc_pc

sf_ok:          CALL fa_f_da                    ; PSK/FRD/FWR/JOV nach der Prüfung: Flash da? lesen, schreiben oder laden und springen
                JNC  sf_f010
                CALL fa_f_zustand
                MOV  R0, #F_JOB
                MOV  A, @R0
                JB7  sf_schreiben
                JB6  sf_jov             ; 6.10 JOV
                CALL fa_f_frd
                JMP  sf_fertig
sf_jov:         MOV  A, R6
                JB7  sj_f003            ; leere Bank: F-003 (nicht in Nullen springen)
                CALL fa_f_frd
                MOV  R0, #F_JOB
                MOV  @R0, #$00
                MOV  R0, #F_ANF         ; weiter bei z (wie SPU: end_of_instr prüft R3). Nicht F_RAM: das zählt f_frd hoch
                MOV  A, @R0
                MOV  R0, #PC
                MOV  @R0, A
                MOV  R3, A
                JMP  zu_end_of_instr
sj_f003:        MOV  R4, #3
                JMP  k_fehler
sf_schreiben:   CALL fa_f_fwr
                JMP  sf_fertig
sf_fertig:      MOV  R0, #F_JOB
                MOV  @R0, #$00
                JMP  zu_inc_pc
sf_f010:        MOV  R4, #10
                ; weiter in k_fehler

; k_fehler: Auftrag löschen, F-0(R4) zeigen
k_fehler:       MOV  R0, #F_JOB
                MOV  @R0, #$00
                JMP  zu_show_error

; ---------------------------------------------------------------------
; 6.00 Projekte. Tasten (die Abfragen macht 1111) und Fernsteuerung mit Interrupt (NIE: $80 speichern, $04 laden,
; $08 Autoboot) geben in F_BANK die Projektnummer 1..99 (Autoboot: 0 = aus); hier wird daraus die erste Bank.
;   j_speichern  ganzes RAM ins Projekt, Start-PC = PC nach 0x213 der ersten Bank; neues Projekt: anlegen
;   j_laden      erste Bank des Projekts laden, PC = Start (0x213, FF = 0); merkt S_PBANK/S_PRES
;   k_teil       Teilbereich: F_JOB $80 RAM ab F_RAM -> Projekt ab F_ANF, $00 umgekehrt (F_ANZ Zellen)
;   j_autoboot   Autoboot-Projekt nach Bank 1 (Einstellungen, 0x000)
;   bl_suche     CAL kurz: nächstes belegtes Projekt (Name, Kurzanzeige aus dem Verzeichnis)
; Anlegen: 4 Bänke in der ersten Lücke ab Bank 4; passen nirgends 4, dann 3, 2, 1; sonst F-012 (Flash voll).
; Stapel: Fernaufrufe (fa_X) nur aus den Aufträgen selbst (Ebene 0); die Hilfen vz_* rufen den Treiber nicht.
; FNI ($20..$29) läuft ganz in 1011 (k_cal_vor); fertig: F_JOB = 0 ($EE = FNI fehlgeschlagen).
; ---------------------------------------------------------------------
                .equ VZ_RES,  $28       ; reservierte Bänke des Projekts (KBUF: nur ohne FNI)
                .equ VZ_ART,  $29       ; 1 speichern, 2 laden, 3 Teilbereich; Bit 7: noch kein Verzeichnis, Bit 6: neu angelegt,
                                        ;   Bit 5: Platz des Eintrags ist FF (direkt hineinschreiben)
                .equ VZ_N,    $2a       ; Projektnummer
                .equ VZ_PUF,  $60       ; 6 Byte neuer Kopf bzw. Eintrag (in F_NAME: Tastenaufträge schreiben keinen Namen)
                .equ VZ_S,    $68       ; Anlegen: erste Bank (Kandidat)
                .equ VZ_W,    $69       ; Anlegen: Anzahl Bänke; Blättern: Runden
                .equ VZ_I,    $6a       ; Anlegen: Eintrag 1..99
                .equ VZ_SAV,  $6c       ; 4 Byte: F_ANF, F_ANZ, F_RAM, F_JOB des Auftrags
                .equ VZ_JOB,  $6f       ; (VZ_SAV + 3)

; k_bereit: rechts „rdY“, Ende
k_bereit:       MOV  R0, #$23
                MOV  @R0, #G_R
                INC  R0
                MOV  @R0, #G_D
                INC  R0
                MOV  @R0, #G_Y
k_ende:         MOV  R0, #F_JOB
                MOV  @R0, #$00
                JMP  zu_s_ende

j_speichern:    MOV  R0, #VZ_ART                ; Projekt speichern (CAS kurz, NIE $80)
                MOV  @R0, #1
                JMP  k_projekt
j_laden:        MOV  R0, #VZ_ART                ; Projekt laden (CAL halten, NIE $04)
                MOV  @R0, #2
                JMP  k_projekt
k_teil:         MOV  R0, #VZ_ART                ; Teilbereich speichern oder laden (CAS/CAL lang)
                MOV  @R0, #3
k_projekt:      CALL fa_f_da
                JNC  kp_f010
                CALL vz_sichern         ; F_ANF, F_ANZ, F_RAM, F_JOB -> VZ_SAV; F_BANK -> VZ_N
                MOV  R0, #F_BANK
                MOV  @R0, #$00
                CALL fa_f_zustand       ; R6 = Zustand von Bank 0 (Verzeichnis)
                MOV  A, R6
                JB7  kp_leer
                CALL vz_kopf
                CALL fa_f_lies
                CALL vz_kennung
                JNC  kp_leer
                MOV  R0, #VZ_N
                MOV  A, @R0
                MOV  R3, #16
                CALL vz_adr
                MOV  R1, #F_PUF
                MOV  R2, #3
                CALL fa_f_lies          ; F_PUF: erste Bank, reserviert, Flags
                MOV  R0, #F_PUF2
                MOV  A, @R0
                XRL  A, #VZ_BELEGT
                JNZ  kp_neu
                MOV  R0, #F_PUF1
                MOV  A, @R0
                MOV  R0, #VZ_RES
                MOV  @R0, A
                MOV  R0, #F_PUF
                MOV  A, @R0
                JMP  kp_bank
kp_leer:        MOV  R0, #VZ_ART        ; noch kein Verzeichnis: alles frei (der neue Kopf macht den Rest FF)
                MOV  A, @R0
                ORL  A, #$a0
                MOV  @R0, A
                JMP  kp_nicht_ff
kp_neu:         MOV  R0, #F_PUF         ; Platz des Eintrags (Byte 16..18) noch FF?
                MOV  A, @R0
                INC  R0
                ANL  A, @R0
                INC  R0
                ANL  A, @R0
                CPL  A
                JNZ  kp_nicht_ff
                MOV  R0, #VZ_ART
                MOV  A, @R0
                ORL  A, #$20
                MOV  @R0, A
kp_nicht_ff:    MOV  R0, #VZ_ART        ; Projekt gibt es nicht: laden -> F-011, schreiben -> anlegen
                MOV  A, @R0
                ANL  A, #$1f
                XRL  A, #2
                JZ   kp_f011
                MOV  R0, #VZ_JOB      ; F_JOB: Teilbereich lesen ($00)?
                MOV  A, @R0
                JB7  kp_anl
kp_f011:        MOV  R4, #11
                JMP  k_fehler
kp_f010:        MOV  R4, #10
                JMP  k_fehler
kp_anl:         JMP  ka_anlegen

; Anlegen: erste Lücke für VZ_W Bänke ab Bank 4 (jeder belegte Eintrag, der den Kandidaten schneidet, schiebt ihn
; hinter sich; dann alle noch einmal). Passt VZ_W nicht mehr bis Bank 255: eine Bank weniger.
ka_anlegen:     MOV  R0, #VZ_W
                MOV  @R0, #4
ka_w:           MOV  R0, #VZ_S
                MOV  @R0, #4
ka_s:           MOV  R0, #VZ_S
                MOV  A, @R0
                INC  R0
                ADD  A, @R0             ; S + W
                JNC  ka_bis
                JNZ  ka_kleiner         ; über 256
ka_bis:         MOV  R0, #VZ_ART
                MOV  A, @R0
                JB7  ka_frei            ; kein Verzeichnis: alles frei
                MOV  R0, #VZ_I
                MOV  @R0, #1
ka_i:           MOV  R0, #VZ_I
                MOV  A, @R0
                MOV  R3, #16
                CALL vz_adr
                MOV  R1, #F_PUF
                MOV  R2, #3
                CALL fa_f_lies
                MOV  R0, #F_PUF2
                MOV  A, @R0
                XRL  A, #VZ_BELEGT
                JNZ  ka_n
                CALL vz_kollision
                JZ   ka_n
                DEC  A
                JZ   ka_s               ; Kandidat verschoben: alle noch einmal
                JMP  ka_kleiner         ; bis Bank 255 belegt
ka_n:           MOV  R0, #VZ_I
                INC  @R0
                MOV  A, @R0
                XRL  A, #100
                JNZ  ka_i
                JMP  ka_frei
ka_kleiner:     MOV  R0, #VZ_W
                MOV  A, @R0
                DEC  A
                MOV  @R0, A
                JNZ  ka_w
                MOV  R4, #12            ; F-012: Flash voll
                JMP  k_fehler

; Lücke gefunden: ggf. erst den Verzeichniskopf anlegen (Rest des Sektors FF), dann den Eintrag schreiben
ka_frei:        MOV  R0, #VZ_ART
                MOV  A, @R0
                JB7  ka_kopf
ka_eintrag:     MOV  R0, #VZ_ART
                MOV  A, @R0
                ORL  A, #$40            ; neu angelegt: die Bank wird gleich geleert
                MOV  @R0, A
                MOV  R0, #VZ_S          ; Eintrag Byte 16..18: erste Bank, reserviert, belegt
                MOV  A, @R0
                MOV  R1, #VZ_PUF
                MOV  @R1, A
                INC  R0
                MOV  A, @R0
                INC  R1
                MOV  @R1, A
                MOV  R0, #VZ_RES
                MOV  @R0, A
                INC  R1
                MOV  @R1, #VZ_BELEGT
                MOV  R0, #VZ_N
                MOV  A, @R0
                MOV  R3, #16
                CALL vz_adr
                MOV  R0, #VZ_ART
                MOV  A, @R0
                JB5  ka_direkt
                MOV  R1, #3             ; Platz nicht FF (Reste): ganzen Sektor neu schreiben
                MOV  R2, #$90           ; schreiben, roh (Rest bleibt)
                CALL vz_roh
                CALL fa_f_fwr           ; F_BANK = 0, R6 = Zustand von Bank 0
                JMP  ka_drin
ka_direkt:      MOV  R1, #VZ_PUF        ; FF-Platz: direkt programmieren (schnell, ohne Löschen)
                MOV  R2, #3
                CALL fa_f_prog
ka_drin:        MOV  R0, #VZ_S
                MOV  A, @R0
                JMP  kp_bank
ka_kopf:        ANL  A, #$7f            ; ab jetzt gibt es ein Verzeichnis
                MOV  @R0, A
                CLR  A                  ; Autoboot aus
                MOV  R1, #VZ_PUF
                CALL vz_kopf_puf
                CALL vz_kopf
                MOV  R1, #6
                MOV  R2, #$91           ; schreiben, roh, neu: Rest FF
                CALL vz_roh
                CALL fa_f_fwr
                CALL fa_f_zustand       ; neuer Sektor von Bank 0
                JMP  ka_eintrag

; Projekt gefunden bzw. angelegt: A = erste Bank. Jetzt die eigentliche Arbeit.
kp_bank:        MOV  R0, #F_BANK
                MOV  @R0, A
                CALL fa_f_zustand       ; R6 = Zustand der Projektbank
                MOV  R0, #VZ_ART        ; neu angelegt, aber die Bank hat noch alten Inhalt: erst leeren
                MOV  A, @R0
                JB6  kp_neu_b
kp_arbeit:      CALL vz_zurueck         ; VZ_SAV -> F_ANF, F_ANZ, F_RAM, F_JOB
                MOV  R0, #VZ_ART
                MOV  A, @R0
                ANL  A, #$1f
                DEC  A
                JZ   kb_s
                DEC  A
                JZ   kb_l
                MOV  R0, #F_JOB         ; Teilbereich
                MOV  A, @R0
                JB7  kt_schreib
                MOV  A, R6
                JB7  kb_f011            ; Bank leer
                CALL fa_f_frd
                JMP  k_bereit
kt_schreib:     CALL fa_f_fwr
                JMP  k_bereit
kb_s:           JMP  ks_speichern
kb_l:           JMP  kl_laden
kb_f011:        JMP  kp_f011
kp_neu_b:       MOV  A, R6
                JB7  kp_arbeit          ; ohnehin leer
                CALL vz_kopf            ; Fenster 0x000, Länge 0: alles wie leer
                MOV  R1, #0
                MOV  R2, #$91
                CALL vz_roh
                CALL fa_f_fwr
                CALL fa_f_zustand
                JMP  kp_arbeit

ks_speichern:   MOV  R0, #F_ANF         ; ganze Bank: Zellen 0..MEM_SIZE aus RAM 0
                MOV  @R0, #$00
                INC  R0
                MOV  R1, #MEM_SIZE
                MOV  A, @R1
                INC  A
                MOV  @R0, A
                INC  R0
                MOV  @R0, #$00
                MOV  R0, #F_JOB
                MOV  @R0, #$c0          ; schreiben, Quelle RAM, Start-PC nach 0x213 (kein Name: F_NAME ist VZ_PUF)
                CALL fa_f_fwr
                CALL k_merken           ; das RAM gehört jetzt zu diesem Projekt (PSK/FRD/FWR/SEF)
                JMP  k_bereit

kl_laden:       MOV  A, R6                      ; Bank des Projekts ins RAM laden, Start-PC setzen
                JB7  kl_f011            ; Bank leer
                MOV  R0, #F_ANF
                MOV  @R0, #$00
                INC  R0
                MOV  R1, #MEM_SIZE
                MOV  A, @R1
                INC  A
                MOV  @R0, A
                INC  R0
                MOV  @R0, #$00
                CALL fa_f_frd
                MOV  R0, #F_SEKT        ; Start-PC: Byte 0x213 der ersten Bank
                MOV  A, R6
                MOV  @R0, A
                INC  R0
                MOV  @R0, #$02
                INC  R0
                MOV  @R0, #$13
                MOV  R1, #PC
                MOV  R2, #1
                CALL fa_f_lies
                MOV  R0, #PC
                MOV  A, @R0
                CPL  A
                JNZ  kl_pc
                MOV  @R0, A             ; FF (nie gespeichert) -> 0
kl_pc:          CALL k_merken
                MOV  R0, #S_RSP
                MOV  @R0, #$00
                MOV  R0, #F_JOB
                MOV  A, @R0
                MOV  @R0, #$00
                JB6  jl_start
                SEL  MB0
                CALL print_pc
                SEL  MB1
                JMP  zu_s_ende
jl_start:       MOV  R6, #$00
                MOV  A, #$01            ; run_weiter: JNZ not_one -> Programm ab PC
                JMP  zu_run_weiter
kl_f011:        JMP  kp_f011

; Autoboot-Projekt F_BANK (RUN lang, Fernsteuerung $08; 0 = aus) -> Bank 1 (Einstellungen), Byte 0x000
j_autoboot:     CALL fa_f_da
                JNC  ja_f010
                MOV  R0, #F_BANK
                MOV  A, @R0
                MOV  @R0, #$01
                MOV  R1, #VZ_PUF
                MOV  @R1, A
                CALL fa_f_zustand
                CALL vz_kopf            ; Fenster 0x000, 1 Byte, Rest bleibt
                MOV  R1, #1
                MOV  R2, #$90
                CALL vz_roh
                CALL fa_f_fwr
                JMP  k_bereit
ja_f010:        JMP  kp_f010

; Autoboot beim Einschalten (aus s_boot): Bank 1, Byte 0x000 (00/FF = aus)
f_boot:         CALL fa_f_da
                JNC  fb_nein
                MOV  R0, #F_BANK
                MOV  @R0, #$01
                CALL fa_f_zustand
                MOV  A, R6
                JB7  fb_nein
                CALL vz_kopf
                MOV  R2, #1
                CALL fa_f_lies
                MOV  R0, #F_PUF
                MOV  A, @R0
                JZ   fb_nein
                CPL  A
                JZ   fb_nein
                CPL  A
                MOV  R0, #F_BANK
                MOV  @R0, A
                JMP  zu_boot_warte      ; „bot nn“, 2 s warten (Taste bricht ab) in 1111
fb_nein:        SEL  MB0
                CALL print_pc
                SEL  MB1
                JMP  zu_wait_key

; bl_suche (CAL kurz, aus 1111): nächstes belegtes Projekt nach F_BANK, nach 99 wieder von vorn. Name 0..5 -> F_NAME,
; Kurzanzeige -> F_PUF, beides aus dem Verzeichnis; weiter in 1111 (bl_zeige, F_BANK = Projekt). Keins: F-011.
bl_suche:       CALL fa_f_da
                JNC  bs_f010
                MOV  R0, #F_BANK
                MOV  A, @R0
                MOV  @R0, #$00
                MOV  R0, #VZ_N
                MOV  @R0, A
                CALL fa_f_zustand
                MOV  A, R6
                JB7  bs_keine
                CALL vz_kopf
                CALL fa_f_lies
                CALL vz_kennung
                JNC  bs_keine
                MOV  R0, #VZ_W
                MOV  @R0, #2            ; höchstens zwei Runden
bs_l:           MOV  R0, #VZ_N
                INC  @R0
                MOV  A, @R0
                XRL  A, #100
                JNZ  bs_pruef
                MOV  @R0, #$00
                MOV  R0, #VZ_W
                MOV  A, @R0
                DEC  A
                MOV  @R0, A
                JNZ  bs_l
                JMP  bs_keine
bs_pruef:       MOV  A, @R0
                MOV  R3, #18
                CALL vz_adr
                MOV  R1, #F_PUF
                MOV  R2, #1
                CALL fa_f_lies          ; Flags
                MOV  R0, #F_PUF
                MOV  A, @R0
                XRL  A, #VZ_BELEGT
                JNZ  bs_l
                MOV  R0, #VZ_N
                MOV  A, @R0
                MOV  R3, #0
                CALL vz_adr
                MOV  R1, #F_NAME
                MOV  R2, #6
                CALL fa_f_lies          ; Name 0..5
                MOV  R0, #VZ_N
                MOV  A, @R0
                MOV  R3, #19
                CALL vz_adr
                MOV  R1, #F_PUF
                MOV  R2, #6
                CALL fa_f_lies          ; Kurzanzeige (FF = keine)
                MOV  R0, #VZ_N
                MOV  A, @R0
                MOV  R0, #F_BANK
                MOV  @R0, A
                JMP  zu_bl_zeige
bs_keine:       MOV  R4, #11
                JMP  k_fehler
bs_f010:        JMP  kp_f010

; ---------------------------------------------------------------------
; Hilfen fürs Verzeichnis (rufen den Treiber nicht: Stapel)
; ---------------------------------------------------------------------
; vz_adr: Eintrag A (1..99), Byte R3 -> F_SEKT = R6, F_OFH:F_OFL = 0x300 + 32 (A - 1) + R3. Benutzt R0, R4.
vz_adr:         DEC  A
                MOV  R4, A
                RR   A
                RR   A
                RR   A
                ANL  A, #$1f
                ADD  A, #$03
                MOV  R0, #F_OFH
                MOV  @R0, A
                MOV  A, R4
                ANL  A, #$07
                SWAP A
                RL   A
                ADD  A, R3
                INC  R0
                MOV  @R0, A
                MOV  R0, #F_SEKT
                MOV  A, R6
                MOV  @R0, A
                RET

; vz_kopf: Adresse 0x000 (Kopf) mit F_SEKT = R6; R1 = F_PUF, R2 = 6 (zum Lesen)
vz_kopf:        MOV  R0, #F_SEKT
                MOV  A, R6
                MOV  @R0, A
                INC  R0
                MOV  @R0, #$00
                INC  R0
                MOV  @R0, #$00
                MOV  R1, #F_PUF
                MOV  R2, #6
                RET

; vz_kennung: C = 1, wenn F_PUF 0..3 = „CP1V“
vz_kennung:     MOV  R0, #F_PUF
                MOV  A, @R0
                XRL  A, #$43            ; C
                JNZ  vkn_n
                INC  R0
                MOV  A, @R0
                XRL  A, #$50            ; P
                JNZ  vkn_n
                INC  R0
                MOV  A, @R0
                XRL  A, #$31            ; 1
                JNZ  vkn_n
                INC  R0
                MOV  A, @R0
                XRL  A, #$56            ; V
                JNZ  vkn_n
                CLR  C
                CPL  C
                RET
vkn_n:          CLR  C
                RET

; vz_kopf_puf: „CP1V“, 01 (Version), A (frei, 00) ab @R1
vz_kopf_puf:    MOV  @R1, #$43
                INC  R1
                MOV  @R1, #$50
                INC  R1
                MOV  @R1, #$31
                INC  R1
                MOV  @R1, #$56
                INC  R1
                MOV  @R1, #$01
                INC  R1
                MOV  @R1, A
                RET

; vz_roh: Rohschreiben vorbereiten: Fenster ab F_OFH:F_OFL (von vz_adr/vz_kopf), R1 Byte aus VZ_PUF; F_JOB = R2
vz_roh:         MOV  R0, #F_OFH
                MOV  A, @R0
                MOV  R0, #F_ROH
                MOV  @R0, A
                MOV  R0, #F_OFL
                MOV  A, @R0
                MOV  R0, #F_ANF
                MOV  @R0, A
                INC  R0
                MOV  A, R1
                MOV  @R0, A             ; F_ANZ
                INC  R0
                MOV  @R0, #VZ_PUF       ; F_RAM
                MOV  R0, #F_JOB
                MOV  A, R2
                MOV  @R0, A
                RET

; vz_kollision: belegter Eintrag in F_PUF (erste Bank f, reserviert r) gegen den Kandidaten [VZ_S, VZ_S + VZ_W).
; A = 0: keine Überschneidung; 1: doch, VZ_S = f + r; 2: doch, und f + r reicht bis über Bank 255
vz_kollision:   MOV  R0, #VZ_S
                MOV  A, @R0
                INC  R0
                ADD  A, @R0             ; T = S + W (C: T = 256, f < T sicher)
                JC   vko_vorn
                MOV  R4, A
                MOV  R0, #F_PUF
                MOV  A, @R0
                CPL  A
                ADD  A, R4              ; C = 1, wenn f < T
                JNC  vko_nein
vko_vorn:       MOV  R0, #F_PUF
                MOV  A, @R0
                INC  R0
                ADD  A, @R0             ; e = f + r
                JC   vko_ende
                MOV  R4, A
                MOV  R0, #VZ_S
                MOV  A, @R0
                CPL  A
                ADD  A, R4              ; C = 1, wenn S < e
                JNC  vko_nein
                MOV  A, R4
                MOV  @R0, A
                MOV  A, #1
                RET
vko_ende:       MOV  A, #2
                RET
vko_nein:       CLR  A
                RET

; vz_sichern / vz_zurueck: Parameter des Auftrags (F_ANF, F_ANZ, F_RAM, F_JOB) <-> VZ_SAV; vz_sichern: F_BANK -> VZ_N
vz_sichern:     MOV  R0, #F_ANF
                MOV  R1, #VZ_SAV
                MOV  R2, #3
vzs_l:          MOV  A, @R0
                MOV  @R1, A
                INC  R0
                INC  R1
                DJNZ R2, vzs_l
                MOV  R0, #F_JOB
                MOV  A, @R0
                MOV  @R1, A
                MOV  R0, #F_BANK
                MOV  A, @R0
                MOV  R0, #VZ_N
                MOV  @R0, A
                RET
vz_zurueck:     MOV  R0, #F_ANF                 ; Auftragsparameter aus VZ_SAV zurückholen (Gegenstück zu vz_sichern)
                MOV  R1, #VZ_SAV
                MOV  R2, #3
vzz_l:          MOV  A, @R1
                MOV  @R0, A
                INC  R0
                INC  R1
                DJNZ R2, vzz_l
                MOV  A, @R1
                MOV  R0, #F_JOB
                MOV  @R0, A
                RET

; k_merken: S_PBANK = erste Bank (F_BANK), S_PRES = reservierte Bänke (für PSK/FRD/FWR/SEF des Programms)
k_merken:       MOV  R0, #F_BANK
                MOV  A, @R0
                MOV  R0, #S_PBANK
                MOV  @R0, A
                MOV  R0, #VZ_RES
                MOV  A, @R0
                MOV  R0, #S_PRES
                MOV  @R0, A
                RET

; =====================================================================
; Aufträge der Fernsteuerung per FNI (6.00 aus 1011 hierher: dort bleiben Treiber und Übertragung)
; CAL mit F_JOB <> 0 (NIE 04): $20 P-C, $21 C-P, $22/$23/$29 P-F, $24 F-P, $25 Bank komplett, $2A Verzeichnis kompakt,
; $2B Verzeichnis-Eintrag; $80/$81/$04/$08 (mit Interrupt) über job_kopf in 1111. Blöcke, Bytes, Bits: 1011 (fa_…).
; =====================================================================
; s_cal-Vorspann: Auftrag der Fernsteuerung, sonst CAL von Hand (1111)
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
                XRL  A, #$0c            ; $29 (5.03: wie $23, dazu Namensbereich 0x300..0x5FF; Bank 0 bis 0xFFF)
                JZ   kv_pf
                XRL  A, #$03            ; $2A (6.00: Verzeichnis kompakt; $26 alle Namen entfällt)
                JZ   kv_vz
                XRL  A, #$01            ; $2B (6.00: Verzeichnis-Eintrag schreiben)
                JZ   kv_ve
                MOV  A, @R0
                JB7  kv_job
                JB2  kv_job
                JB3  kv_job
                MOV  @R0, #$00          ; unbekannter Auftrag: löschen, Ende (5.03: $01 roh lesen und $10 Bank
                JMP  zu_s_ende          ;   suchen entfallen, Verzeichnis per FNI)
kv_pc:          JMP  zu_fni_pc
kv_cp:          JMP  zu_fni_cp
kv_pf:          JMP  fni_pf
kv_fp:          JMP  fni_fp
kv_vz:          JMP  fni_vz
kv_ve:          JMP  fni_ve
kv_job:         JMP  zu_job_kopf        ; 5.05: $80/$81/$04/$08 – Kopfanzeige in 1111, dann j_* in 1001
kv_tasten:      JMP  zu_s_cal_ui        ; CAL von Hand: Abfragen in 1111


; ---- Aufträge (aus k_cal_vor); $20 P-C und $21 C-P (nur RAM, keine Flash-Arbeit) liegen in 1011

; $24 Flash -> Pi
fni_fp:         CALL fa_fn_bank_pruef
                JC   ffp_ab
                CALL fa_f_da
                JNC  ffp_ab
                CALL fa_f_zustand          ; R6 = gültiger Sektor
                MOV  A, #G_F
                MOV  R4, #G_P
                CALL fa_fn_an
                CALL fa_kopf_fuellen
                CALL fa_blk_aus
                JF1  ffp_f
ffp_l:          CALL fa_fn_block
                CALL fa_fn_flash_lies
                CALL fa_blk_aus
                JF1  ffp_f
                CALL fa_anz_durch
                CALL fa_fn_weiter
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
                CALL fa_fn_anh_lies
                CALL fa_blk_aus
                JF1  ffp_f
                CALL fa_anz_durch
                MOV  R0, #FN_ZELLE
                MOV  A, @R0
                ADD  A, #8
                MOV  @R0, A
                JNZ  ffk_l
                MOV  R0, #F_ANF
                INC  @R0
                MOV  R0, #F_BANK        ; 6.00: Bank 0 (Verzeichnis) bis 0xFFF, sonst bis 0x5FF
                MOV  A, @R0
                MOV  R0, #F_ANF
                JZ   ffk_0
                MOV  A, @R0
                XRL  A, #$06
                JNZ  ffk_l
                JMP  ffp_gut
ffk_0:          MOV  A, @R0
                XRL  A, #$10
                JNZ  ffk_l
ffp_gut:        JMP  zu_fn_gut
ffp_f:          JMP  zu_fn_fehler
ffp_ab:         JMP  zu_fn_abgelehnt

; $2A (6.00) Verzeichnis kompakt -> Pi: Kopf, dann je belegtem Eintrag n fünf Blöcke [n, 0 x7] und die 32 Byte des
; Eintrags, zum Schluss [0 x8]. Ohne gültiges Verzeichnis (Bank 0 leer) gleich das Ende; „CP1V“ prüft der Pi ($24).
fni_vz:         CALL fa_f_da
                JNC  fvz_ab
                MOV  A, #G_F
                MOV  R4, #G_P
                CALL fa_fn_an
                CALL fa_kopf_fuellen
                CALL fa_blk_aus
                JF1  fvz_f
                CALL fa_f_zustand          ; Bank 0 (F_BANK vom Pi)
                MOV  R0, #F_START       ; Eintrag n
                MOV  @R0, #$00
fvz_l:          MOV  R0, #F_START
                INC  @R0
                MOV  A, @R0
                XRL  A, #100
                JZ   fvz_ende
                MOV  R0, #F_ANF         ; Byte 18: Flags
                MOV  @R0, #18
                MOV  R2, #1
                CALL fvz_lies
                MOV  R0, #F_LPUF
                MOV  A, @R0
                XRL  A, #VZ_BELEGT
                JNZ  fvz_l
                MOV  R1, #F_LPUF        ; [n, 0 x7]
                MOV  R0, #F_START
                MOV  A, @R0
                MOV  @R1, A
                MOV  R2, #7
fvz_0:          INC  R1
                MOV  @R1, #$00
                DJNZ R2, fvz_0
                CALL fn_block8
                JF1  fvz_f
                MOV  R0, #F_ANF         ; Eintrag in 4 Blöcken (Byte 0, 8, 16, 24; R5 braucht spi)
                MOV  @R0, #0
fvz_b:          MOV  R2, #8
                CALL fvz_lies
                CALL fn_block8
                JF1  fvz_f
                MOV  R0, #F_ANF
                MOV  A, @R0
                ADD  A, #8
                MOV  @R0, A
                XRL  A, #32
                JNZ  fvz_b
                CALL fa_anz_durch
                JMP  fvz_l
fvz_ende:       MOV  R1, #F_LPUF        ; Ende: [0 x8]
                MOV  R2, #8
fvz_e:          MOV  @R1, #$00
                INC  R1
                DJNZ R2, fvz_e
                CALL fn_block8
                JF1  fvz_f
                JMP  zu_fn_gut
fvz_f:          JMP  zu_fn_fehler
fvz_ab:         JMP  zu_fn_abgelehnt

; $2B (6.00) Verzeichnis-Eintrag F_START = n vom Pi (Kopf $2B, 0, 0, 16 = 4 Blöcke à 8 Byte): direkt in den freien
; (FF) Platz programmieren (f_prog, ohne Löschen). Ändern/Löschen: ganzes Verzeichnis per $29.
fni_ve:         CALL fa_f_da
                JNC  fve_ab
                CALL fa_f_zustand
                MOV  A, R6
                JB7  fve_ab             ; noch kein Verzeichnis
                MOV  A, #G_P
                MOV  R4, #G_F
                CALL fa_fn_an
                CALL fa_kopf_n
                CALL fa_blk_ein
                JF1  fve_f
                CALL fa_kopf_pruef
                JF1  fve_f
                MOV  R0, #F_ANF         ; Byte im Eintrag (R5 braucht spi)
                MOV  @R0, #0
fve_l:          MOV  R0, #FN_N
                MOV  @R0, #4
                MOV  R0, #FN_POS
                MOV  @R0, #$00
                CALL fa_blk_ein            ; -> F_LPUF
                JF1  fve_f
                MOV  R2, #0
                CALL fvz_lies           ; nur die Adresse setzen (R2 = 0: liest nichts)
                MOV  R1, #F_LPUF
                MOV  R2, #8
                CALL fa_f_prog
                CALL fa_anz_durch
                MOV  R0, #F_ANF
                MOV  A, @R0
                ADD  A, #8
                MOV  @R0, A
                XRL  A, #32
                JNZ  fve_l
                JMP  zu_fn_gut
fve_f:          JMP  zu_fn_fehler
fve_ab:         JMP  zu_fn_abgelehnt

; fvz_lies: R2 Byte (0: keins) von Byte F_ANF des Eintrags F_START (R6 = Sektor von Bank 0) nach F_LPUF; setzt dabei
; F_SEKT/F_OFH/F_OFL. Benutzt R0, R1, R3, R4.
fvz_lies:       MOV  R0, #F_START
                MOV  A, @R0
                DEC  A
                MOV  R4, A
                RR   A
                RR   A
                RR   A
                ANL  A, #$1f
                ADD  A, #$03
                MOV  R3, A              ; Offset high 0x300 + 32 (n - 1)
                MOV  A, R4
                ANL  A, #$07
                SWAP A
                RL   A
                MOV  R0, #F_ANF
                ADD  A, @R0
                MOV  R0, #FN_ZELLE
                MOV  @R0, A             ; Offset low
                MOV  R1, #F_LPUF
                MOV  A, R2
                JZ   fvl_adr
                JMP  fa_fn_anh_lies
fvl_adr:        MOV  R0, #F_SEKT
                MOV  A, R6
                MOV  @R0, A
                INC  R0
                MOV  A, R3
                MOV  @R0, A
                INC  R0
                MOV  R1, #FN_ZELLE
                MOV  A, @R1
                MOV  @R0, A
                RET

; fn_block8: 8 Byte ab F_LPUF als Block an den Pi
fn_block8:      MOV  R0, #FN_N
                MOV  @R0, #4
                MOV  R0, #FN_POS
                MOV  @R0, #$00
                JMP  fa_blk_aus


; $22 / $23 Pi -> Flash (mit Name aus F_NAME); Kopf und Blöcke holt f_fwr selbst (fw_fni_*)
fni_pf:         CALL fa_fn_bank_pruef      ; (6.00: auch Bank 0 – der Pi verwaltet das Verzeichnis)
                JC   fpf_ab
                CALL fa_f_da
                JNC  fpf_ab
                CALL fa_f_zustand
                MOV  A, #G_P
                MOV  R4, #G_F
                CALL fa_fn_an              ; T bleibt low bis nach dem Löschen
                CLR  F0                 ; F0 = alle Blöcke da
                CALL fa_f_fwr
                JF1  fpf_f
                CALL fa_fn_aus
                CALL fa_fn_links
                JMP  k_bereit        ; (6.00: F_START landet als Start-PC in 0x213, f_quelle)
fpf_f:          JMP  zu_fn_fehler
fpf_ab:         JMP  zu_fn_abgelehnt
