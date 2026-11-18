# Firmware 6.x – Routinen je Block

Erzeugt von `firmware/v6/routinen.py` aus den Quelltexten und der Symboltabelle des Builds. Adressen sind EEPROM-Adressen (28C256, A14 = 1 im Betrieb). Nur Routinen, keine Sprungmarken innerhalb einer Routine. Überblick und Regeln stehen in `docs/firmware6-de.md`.

## Block 1111 – Bedienung: Tasten CAS/CAL/RUN, Start, Version, Anzeige der Eingaben

Quelle `firmware/v6/bedienung.asm`, 32 Routinen.

| Adresse | Routine | Zweck |
|---|---|---|
| 7800 | `s_cas` | CAS: kurz = ganzes RAM in eine Bank, lang = Teilbereich |
| 7841 | `s_f003` | F-003 im Original zeigen |
| 784A | `s_cal` | CAL: erst die Aufträge der Fernsteuerung (1011, k_cal_vor), dann hierher (s_cal_ui) |
| 784C | `s_cal_ui` | CAL von der Tastatur: kurz blättern, lang Teilbereich laden |
| 788A | `teil_anzahl` | F_ANZ = to - Fr + 1 (256 -> 0), R4 = dst + to - Fr; C = 1 bei Überlauf über 255 |
| 789D | `proj_frage` | Fragen |
| 78B4 | `fr_to_frage` | „Fr ___“, „to ___“, Grenze A; Vorgabe 0 .. Grenze; danach geordnet. F1 = STP |
| 78DB | `dst_frage` | „d5t ___“, Grenze A, Vorgabe Fr. F1 = STP |
| 78EE | `leer_weg` | kein Leerlauf mehr (LEER = 0; wait_key setzt es wieder), damit NIE 04 abgelehnt wird |
| 7900 | `halten` | Taste R3 1 s gehalten? C = 1. Nach 1/4, 1/2, 3/4 s rechts _ __ ___. |
| 793F | `s_ende` | Ende |
| 7955 | `taste_gedrueckt` | Hilfen |
| 7965 | `kopf_zeigen` | Anzeige S_SYM R2 R5 und leere Ziffern |
| 7978 | `zeichen_rechts` | R2 (0..3) mal Zeichen R5 in die rechte Dreiergruppe (8 88 888), Rest dunkel |
| 798A | `bereich_ordnen` | erste/letzte tauschen, falls nötig |
| 7A00 | `eingabe` | Anzeige S_SYM R2 R5 "___", bis zu 3 Ziffern (6.00: Grenze < 100 -> " __", 2 Ziffern), CAS/CAL/RUN übernimmt. |
| 7A96 | `ei_zwei` | C = 1, wenn S_GRENZE < 100 (Projektnummer: zwei Ziffern). Benutzt R1, A. |
| 7A9D | `s_run` | RUN: kurz = wie immer (beim Loslassen); 1 s halten = Autoboot-Projekt (bot __, 00 = aus) |
| 7AC5 | `kopf_5to` | Kopfanzeigen (5.05, 6.00 Projekte): „5to nn“, „LdP nn“, „bot nn“, „Pro nn“ mit F_BANK = Projektnummer |
| 7ACD | `kopf_ldp` | „LdP nn“ |
| 7AD5 | `kopf_bot` | „bot nn“ |
| 7ADD | `kopf_pro` | „Pro nn“ |
| 7AFD | `job_kopf` | Aufträge der Fernsteuerung mit Interrupt ($80/$81 speichern, $04 laden, $08 Autoboot) – |
| 7B10 | `bl_zeige` | F_BANK = Projekt, F_NAME 0..5 = Name, F_PUF 0..5 = Kurzanzeige (FF = keine). |
| 7C00 | `asc_seg` | ab 0x80 dunkel |
| 7C46 | `boot_warte` | 2 s warten, jede Taste bricht ab. |
| 7C72 | `bw_taste` | A <> 0, wenn der Interrupt irgendeine Taste als gedrückt führt (0x30..0x35) |
| 7C7C | `kaltstart` | wie Einschalten. Timer aus, PSW = 0 (Stapel leer, RB0), F0/F1 aus, |
| 7C8D | `s_stp` | 5.02 Reset-Taste: STP aus wait_key. Hält dabei jemand CLR (Tastenzustand Reihe CAS/CLR/PC/ACC = 0x35, |
| 7C99 | `s_boot` | Start: „ 5.02 “ 1 s lang, dann P 000 wie im Original |
| 7D00 | `s_demo8` | Original-Demos, ab 5.00 hier oben (Platz unten für die Fernsteuerung): |
| 7D43 | `s_demo9` | Original-Demo 9 RUN: Countdown 9 … 0 |

## Block 1101 – Befehle: alle neuen und geänderten CP1-Befehle

Quelle `firmware/v6/befehle.asm`, 36 Routinen.

| Adresse | Routine | Zweck |
|---|---|---|
| 5800 | `s_neg` | 14 NEG xxx: Akku XOR xxx |
| 580F | `s_und` | 15 UND xxx: Akku UND Zelle xxx (b_operand: A = Zelle, R0 -> Akku LSB, F1 = Fehler) |
| 5817 | `s_oder` | 25 ODR xxx: Akku ODER Zelle xxx |
| 581F | `s_inv` | Befehl > 24 aus step_handler (R1 gerade: zeigt aufs Befehlsbyte) oder Befehl 00 (R1 ungerade) |
| 5875 | `s_ovf` | 26 OVF x: Schalter in RAM 0x47 (vom Original beim Einschalten gelöscht -> Standard „an“) |
| 5882 | `s_f006` | Einsprung aus error_f006 (ADD/SUB-Überlauf). A = Ergebnis modulo 256, R0 -> Akku LSB. |
| 5890 | `s_anz` | Befehl 02 ANZ (Tabelleneintrag zeigt auf anz_neu). R1 -> Argument. |
| 58BF | `b_operand` | Akku und Zelle xxx prüfen. A = Wert der Zelle, R0 -> Akku LSB. |
| 58DB | `b_fehler` | Fehler aus b_operand zeigen: R4 = 3 -> F-003, sonst F-005 |
| 5900 | `s_seg` | 27 SEG xxx (R1 -> Argument). R7 (E/A-Zeiger des Originals) bleibt unberührt. |
| 5A0A | `s_as` | 28..30 AS1..AS3 xxx (R1 -> Argument, S_ASY = 1..3) |
| 5A42 | `s_tst` | 31 TST 000: Zifferntaste abwarten. Der Timer-Interrupt legt jede neue Taste in R6' (RAM 0x1E) ab, |
| 5A67 | `s_jsr` | 32 JSR xxx (R1 -> Argument): wie SPU, vorher PC+1 auf den Stapel |
| 5A8B | `s_ret` | 33 RET: oberste Adresse vom Stapel |
| 5A9C | `s_pcset` | PC über die Tastatur gesetzt (Einsprung aus pc_handler statt MOV R6,#0 / JMP wait_key) |
| 5AA4 | `s_psh` | 34 PSH: Akku (Datum) auf den Stapel |
| 5ABE | `s_pop` | 35 POP: oberster Wert in den Akku |
| 5AD3 | `s_p1aus` | OUT P1A: 6.00 ganz ohne Wirkung – P1.5 ist jetzt A13, P1.1 (SCK) A14; alle Bits bleiben 1 |
| 5AD9 | `s_vzg` | 03 VZG xxx mit Tastengedächtnis für TSE |
| 5AE7 | `t_merk` | neue Zifferntaste aus R6' nach T_SPEICHER (und R6' löschen, damit sie nicht doppelt zählt) |
| 5B00 | `s_fbef` | 36 PSK / 37 FRD / 38 FWR: Parameter prüfen (5.00 hier, Flash-Arbeit ab sf_ok in 1001) |
| 5B18 | `sf_fwr` | 38 FWR |
| 5B70 | `s_tse` | 39 TSE 000: Akku = Ziffer der seit dem letzten TSE gedrückten Zifferntaste, sonst 255 (wartet nicht) |
| 5B99 | `s_imm` | Befehle 40..46 = ADD/SUB/VGL/VGR/VKL/UND/ODR mit festem Wert (Argument statt Zelle). |
| 5BA9 | `im_f002` | 47 SEF, sonst F-002 (A = Befehl - 47) |
| 5BAD | `im_d2` | 5.06 (kleine Absätze, damit der Lückenfüller sie verteilen kann) |
| 5BB8 | `im_d3` | A = R5 - 5, C = 1 bei 45/46 |
| 5BC6 | `im_vgl` | 5.06 Vergleiche mit festem Wert (R5 = 2 VGL, 3 VGR, 4 VKL) |
| 5BD6 | `im_v2` | A = R5 ^ 2: R5 = 3? |
| 5BDE | `s_sefa` | 5.06 SEF xxx (47): 6 Byte ab xxx im Bilderbereich (Sektor 0x500..0x5FD) der Bank, aus der das Programm geladen |
| 5BEB | `sa_jov` | 6.10: 48 JOV |
| 5BF4 | `sa_zuf` | 6.20: 49 ZUF |
| 5BFD | `s_sefc` | wieder xxx |
| 5C06 | `s_sefb` | SEF mit Bildadresse in A: ohne Programmprojekt dunkel, sonst Block 1001 (s_sef) |
| 5C12 | `s_sefl` | SEF ohne Programmprojekt: Anzeige löschen |
| 5C18 | `s_zuf` | 6.20: 49 ZUF n – Akku = Zufallszahl 0..n-1 (ZUF 0: 0..255). Zustand: 16 Bit in der letzten RAM-Zelle (MEM_SIZE, |

## Block 1001 – Aufträge: was mit dem Flash geschehen soll (Projekte, SEF, PSK/FRD/FWR/JOV, Autoboot)

Quelle `firmware/v6/auftraege.asm`, 32 Routinen.

| Adresse | Routine | Zweck |
|---|---|---|
| 4800 | `s_sef` | SEF xxx (aus 1101, F_ANF = xxx, S_PBANK <> 0): 6 Byte ab Sektor-Offset 0x500 + xxx der |
| 481C | `sf_ok` | PSK/FRD/FWR/JOV nach der Prüfung: Flash da? lesen, schreiben oder laden und springen |
| 484F | `k_fehler` | Auftrag löschen, F-0(R4) zeigen |
| 4855 | `k_bereit` | rechts „rdY“, Ende |
| 4865 | `j_speichern` | Projekt speichern (CAS kurz, NIE $80) |
| 486B | `j_laden` | Projekt laden (CAL halten, NIE $04) |
| 4871 | `k_teil` | Teilbereich speichern oder laden (CAS/CAL lang) |
| 4900 | `ka_anlegen` | Anlegen: erste Lücke für VZ_W Bänke ab Bank 4 (jeder belegte Eintrag, der den Kandidaten schneidet, schiebt ihn |
| 494C | `ka_frei` | Lücke gefunden: ggf. erst den Verzeichniskopf anlegen (Rest des Sektors FF), dann den Eintrag schreiben |
| 499E | `kp_bank` | Projekt gefunden bzw. angelegt: A = erste Bank. Jetzt die eigentliche Arbeit. |
| 49E5 | `ks_speichern` | ganze Bank: Zellen 0..MEM_SIZE aus RAM 0 |
| 4A00 | `kl_laden` | Bank des Projekts ins RAM laden, Start-PC setzen |
| 4A44 | `j_autoboot` | Autoboot-Projekt F_BANK (RUN lang, Fernsteuerung $08; 0 = aus) -> Bank 1 (Einstellungen), Byte 0x000 |
| 4A60 | `j_leeren` | $30 (6.22, Fernsteuerung): Bank F_BANK leeren (beide Sektoren löschen). Der Pi leert damit die reservierten Bänke, |
| 4A68 | `f_boot` | Autoboot beim Einschalten (aus s_boot): Bank 1, Byte 0x000 (00/FF = aus) |
| 4A8F | `bl_suche` | nächstes belegtes Projekt nach F_BANK, nach 99 wieder von vorn. Name 0..5 -> F_NAME, |
| 4AF9 | `vz_adr` | Hilfen fürs Verzeichnis (rufen den Treiber nicht: Stapel) |
| 4B12 | `vz_kopf` | Adresse 0x000 (Kopf) mit F_SEKT = R6; R1 = F_PUF, R2 = 6 (zum Lesen) |
| 4B21 | `vz_kennung` | C = 1, wenn F_PUF 0..3 = „CP1V“ |
| 4B3F | `vz_kopf_puf` | „CP1V“, 01 (Version), A (frei, 00) ab @R1 |
| 4B50 | `vz_roh` | Rohschreiben vorbereiten: Fenster ab F_OFH:F_OFL (von vz_adr/vz_kopf), R1 Byte aus VZ_PUF; F_JOB = R2 |
| 4B67 | `vz_kollision` | belegter Eintrag in F_PUF (erste Bank f, reserviert r) gegen den Kandidaten [VZ_S, VZ_S + VZ_W). |
| 4B8F | `vz_sichern` | / vz_zurueck: Parameter des Auftrags (F_ANF, F_ANZ, F_RAM, F_JOB) <-> VZ_SAV; vz_sichern: F_BANK -> VZ_N |
| 4BA6 | `vz_zurueck` | Auftragsparameter aus VZ_SAV zurückholen (Gegenstück zu vz_sichern) |
| 4BB7 | `k_merken` | S_PBANK = erste Bank (F_BANK), S_PRES = reservierte Bänke (für PSK/FRD/FWR/SEF des Programms) |
| 4C00 | `k_cal_vor` | s_cal-Vorspann: Auftrag der Fernsteuerung, sonst CAL von Hand (1111) |
| 4C4A | `fni_fp` | $24 Flash -> Pi |
| 4D00 | `fni_vz` | $2A (6.00) Verzeichnis kompakt -> Pi: Kopf, dann je belegtem Eintrag n fünf Blöcke [n, 0 x7] und die 32 Byte des |
| 4D6B | `fni_ve` | $2B (6.00) Verzeichnis-Eintrag F_START = n vom Pi (Kopf $2B, 0, 0, 16 = 4 Blöcke à 8 Byte): direkt in den freien |
| 4DB0 | `fvz_lies` | R2 Byte (0: keins) von Byte F_ANF des Eintrags F_START (R6 = Sektor von Bank 0) nach F_LPUF; setzt dabei |
| 4DDC | `fn_block8` | 8 Byte ab F_LPUF als Block an den Pi |
| 4E00 | `fni_pf` | $22 / $23 Pi -> Flash (mit Name aus F_NAME); Kopf und Blöcke holt f_fwr selbst (fw_fni_*) |

## Block 1011 – Treiber: wie der Flash gelesen und geschrieben wird, FNI zum Pi

Quelle `firmware/v6/treiber.asm`, 50 Routinen.

| Adresse | Routine | Zweck |
|---|---|---|
| 6800 | `spi` | A senden, gleichzeitig ein Byte nach A lesen (MSB zuerst). Benutzt R4, R5. |
| 681A | `f_start` | CS neu setzen, Befehl A senden (CS bleibt low) |
| 6820 | `f_cmd` | Befehl A + Adresse (F_BANK, F_SEKT, F_OFH, F_OFL) |
| 683B | `f_lies` | R2 Byte (1..255) ab der Adresse nach @R1 (internes RAM) |
| 6848 | `f_wren` | Schreiben erlauben |
| 684E | `f_warte` | bis der Flash fertig ist (Status Bit 0) |
| 6858 | `f_da` | C = 1, wenn ein Flash antwortet (JEDEC-Hersteller nicht 00/FF) |
| 686A | `f_zustand` | gültigen Sektor von F_BANK suchen -> R6 ($00 / $10 / $80 = keiner) |
| 68A9 | `f_ofs` | Offset = 2 * F_ANF |
| 68B6 | `f_cea` | wie compute_effective_address im Original (A = Zelle -> R1 = Adresse im 8155, P2 wählt den 8155, |
| 68D4 | `f_frd` | F_ANZ Zellen ab F_ANF der Bank F_BANK ins RAM ab F_RAM (leere Bank: 0). R6 von f_zustand. |
| 68F3 | `fr_byte` | ein Byte vom Flash lesen; leere Bank (R6 Bit 7) liefert 00 |
| 68FD | `f_neu` | F_SEKT = freier Sektor |
| 6906 | `f_prog` | R2 Byte ab @R1 (internes RAM) an F_BANK/F_SEKT/F_OFH/F_OFL programmieren, ohne zu löschen: nur |
| 6914 | `f_fwr` | Bank F_BANK neu schreiben (Betriebsart F_JOB, R6 von f_zustand) |
| 698D | `fw_kopf` | FNI-Teile von f_fwr (gleiche Stapelebene: RET verlässt f_fwr mit F1 = 1) |
| 6A00 | `fw_ende` | 5.03 (eigener Absatz, f_fwr passt sonst in keine Seite): A = Offset low, R0 = F_OFH. |
| 6A3B | `f_quelle` | neues Byte für Pufferstelle R1? C = 1: A = neuer Wert. Benutzt R0, R2..R5. |
| 6B00 | `fq_roh` | Byte im Fenster F_ROH:F_ANF .. + F_ANZ - 1 aus dem internen RAM ab F_RAM. |
| 6B51 | `fn_anh_lies` | R2 Byte ab Offset R3:FN_ZELLE aus dem gültigen Sektor (R6) nach @R1 (leere Bank: FF) |
| 6B68 | `fni_pc` | FNI-Übertragung (6.10 wieder hier): $20 P-C, $21 C-P und die Hilfen der FNI-Aufträge (Anzeige Q-Z, Leitungen, |
| 6B91 | `fni_cp` | $21 8155 -> Pi |
| 6BB7 | `fn_abgelehnt` | FNI abgelehnt: F_JOB = $EE, Ende |
| 6BBD | `fn_gut` | FNI fertig: Leitungen frei, rechts „rdY“ |
| 6BC3 | `fn_fehler` | FNI fehlgeschlagen: Leitungen frei, rechts „Err“ |
| 6BD7 | `fn_an` | Anzeige Q-Z (A = Q, R4 = Z) rechts, Interrupt aus, D los, T festhalten (= Auftrag übernommen) |
| 6BF2 | `fn_aus` | Leitungen los, Fernsteuer-Puffer aufräumen, Interrupt wieder an |
| 6BFE | `fn_links` | Anzeige leeren, Q-Z nach links (0x20..0x22) |
| 6C17 | `fn_ram_pruef` | C = 1, wenn F_ANF .. F_ANF+F_ANZ-1 über 255 oder über MEM_SIZE reicht |
| 6C22 | `fn_bank_pruef` | A = letzte Zelle, C = 1: über 255 |
| 6C2A | `zellen_ram` | FN_N Zellen ab FN_ZELLE <-> Puffer F_LPUF. F0 = 0: Puffer -> RAM, F0 = 1: RAM -> Puffer |
| 6C5B | `kopf_fuellen` | jj, Bank, erste Zelle, Anzahl |
| 6C71 | `anz_durch` | Stellen 3..5 (0x23..0x25) je ~0,7 ms von Hand zeigen, danach dunkel (Interrupt ist aus). |
| 6C99 | `fn_block` | FN_N = Zellen von FN_ZELLE bis zur nächsten 4er-Grenze bzw. bis zur letzten Zelle; FN_POS = 0 |
| 6CC2 | `fn_weiter` | FN_ZELLE += FN_N; C = 1, wenn das die letzte war |
| 6CD6 | `fn_flash_lies` | FN_N Zellen ab FN_ZELLE der Bank (R6 = Sektor, leer: 0) -> F_LPUF |
| 6CFB | `kopf_n` | 4 Byte = „2 Zellen“ ab Puffer |
| 6D04 | `kopf_pruef` | empfangener Kopf = eigene Parameter? sonst F1 = 1 |
| 6D14 | `kp_eins` | ein Byte des empfangenen Kopfs (@R1) mit @R0 vergleichen; ungleich -> F1 = 1 |
| 6D1C | `blk_ein` | [ohne Interrupt] (nur FNI) |
| 6D4B | `blk_aus` | [ohne Interrupt] (nur FNI) |
| 6D70 | `blk_anfang` | CRC 0, R1 = F_LPUF + FN_POS, FN_BZ = 2 * FN_N |
| 6D82 | `blk_nochmal` | noch ein Versuch? C = 1 und F1 = 1: nein |
| 6D8E | `byte_ein` | (Bits direkt hier: eine Stapelebene weniger) |
| 6DA4 | `byte_aus` | A bleibt, R5 = A |
| 6DBB | `fn_crc` | CRC-8 (Polynom $07) mit A weiterrechnen. A bleibt, R5 = A. Benutzt R0, R2. |
| 6DCC | `bit_ein` | ein Bit vom Pi -> C. F1 = Zeit um. |
| 6DD5 | `bit_aus` | C an den Pi. F1 = Zeit um. |
| 6DDF | `t_takt` | T loslassen, auf T high, dann auf T low (Pi) warten, T festhalten. Je ~200 ms, sonst F1 = 1. |
| 6DFF | `f_leeren` | Bank F_BANK leeren – beide Sektoren löschen, danach meldet f_zustand $80 (leer). Ohne das |

## Block 0xxx – Original mit Haken, Fernsteuerung im Interrupt

Die unteren acht 2-KB-Blöcke sind gleich: das Kosmos-Original (nicht im Repo) mit Haken, die per `SEL MB1` / `JMP` in die oberen Blöcke springen, und der Fernsteuerung (NIE) in toten Resten alter Routinen.

### `rc_unten.asm` → 0x712–0x7E0 (tote alte CAL-Routine)

| Adresse | Routine | Zweck |
|---|---|---|
| 0712 | `rc_tast` | Haken im Timer-Interrupt: P1.7 abfragen, Ferntaste dazumischen |
| 0757 | `rc_befehl` | NIE: Befehl vom Pi empfangen (anklopfen, Bytes messen) |
| 07B0 | `rb_lesen_t` | (Seite 1) |
| 07B4 | `rl_senden` | Byte in A senden (rt_sende auf Seite 3 springt hierher) |
| 07D4 | `rb_ende` | NIE-Empfang beenden, R1 zurück |

### `rc_seite1.asm` → 0x1C8–0x1FE (tote alte CAS-Routine)

| Adresse | Routine | Zweck |
|---|---|---|
| 01C8 | `rb_taste` | Befehl 01 zm dd: Ferntaste merken |
| 01E5 | `rc_dunkel` | Vor dem Befehl alle Segmente aus: die Anzeige wird kurz gleichmäßig dunkler, |
| 01EB | `rl_start` | Antwort vorbereiten: RC_P1 = Adresse, RC_P2 = Anzahl |

### `rc_seite3.asm` → 0x3BD–0x3F2 (tote alte Kassetten-Senderoutine)

| Adresse | Routine | Zweck |
|---|---|---|
| 03BD | `rt_sende` | je Interrupt ein Byte (R3, R0, A frei; R1 bleibt unberührt) |
| 03DC | `rc_abfrage` | Statusabfrage vorbereiten (aus rt_hoch): RAM 0x20..0x3A, ab dem nächsten Takt je ein Byte |
| 03EA | `rb_schreib` | 03 aa ww: ein Byte ins interne RAM (aus rc_befehl, R1 wird in rb_ende zurückgeholt) |

## Sprungtabelle (60 Einträge: 39 Sprünge zu_X, 21 Fernaufrufe fa_X; in jedem oberen Block an derselben Stelle)

`zu_X` wechselt in den Block von X und springt (JMP). `fa_X` ist ein Fernaufruf von 1001 nach 1011: `ORL P1,#$20` / `CALL X` / `ANL P1,#$df` / `RET`, kostet eine Stapelebene.

`zu_add_imm`, `zu_bl_suche`, `zu_bl_zeige`, `zu_boot_warte`, `zu_end_of_instr`, `zu_error_f003`, `zu_error_f005`, `zu_f_boot`, `zu_inc_pc`, `zu_j_autoboot`, `zu_j_laden`, `zu_j_speichern`, `zu_job_kopf`, `zu_k_cal_vor`, `zu_k_teil`, `zu_run_weiter`, `zu_s_anz`, `zu_s_cal_ui`, `zu_s_f006`, `zu_s_inv`, `zu_s_neg`, `zu_s_p1aus`, `zu_s_pcset`, `zu_s_sef`, `zu_s_und`, `zu_s_vzg`, `zu_sf_ok`, `zu_show_error`, `zu_vgl_imm`, `zu_vgr_imm`, `zu_vkl_imm`, `zu_wait_key`, `zu_fn_abgelehnt`, `zu_fn_fehler`, `zu_fn_gut`, `zu_fni_cp`, `zu_fni_pc`, `zu_k_bereit`, `zu_s_ende`, `fa_anz_durch`, `fa_blk_aus`, `fa_blk_ein`, `fa_f_da`, `fa_f_frd`, `fa_f_fwr`, `fa_f_leeren`, `fa_f_lies`, `fa_f_prog`, `fa_f_zustand`, `fa_fn_an`, `fa_fn_anh_lies`, `fa_fn_aus`, `fa_fn_bank_pruef`, `fa_fn_block`, `fa_fn_flash_lies`, `fa_fn_links`, `fa_fn_weiter`, `fa_kopf_fuellen`, `fa_kopf_n`, `fa_kopf_pruef`

