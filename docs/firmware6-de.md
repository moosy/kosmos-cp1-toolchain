# Kosmos CP1 – Firmware 6.x (AT28C256)

Stand 2026-11-18, Firmware **6.22**, alle 20 Testreihen grün. **Seit 2026-11-18 im CP1** auf dem AT28C256 (zuerst 6.21, am selben Tag 6.22). Rückfall: 6.21 auf einem zweiten 28C256, 5.08 auf dem alten AT28C64B (nur mit dem alten Flash-Format).

- Routinenliste mit Adressen: [`firmware6-routinen-de.md`](firmware6-routinen-de.md) (erzeugt)
- Bedienung zum Ausdrucken: [`cp1-schnelluebersicht-6.pdf`](../cp1-schnelluebersicht-6.pdf), drei Seiten
- Vorgeschichte bis 5.07: [`firmware-de.md`](firmware-de.md), Protokolle NIE/FNI: [`INTERNALS.md`](../INTERNALS.md)

## Versionen

Ab 6.00 gilt das Schema **M.mf**:

- **M** steht für die Architektur, also EEPROM, Blockaufteilung und Flash-Format.
- **m** zählt Änderungen, die man als Benutzer merkt, etwa neue Befehle oder Tasten.
- **f** zählt Fehlerbehebungen.

| Version | Neu |
|---|---|
| 6.00 | 28C256 mit 16 Blöcken. Projekte 01–99 statt Bänken, Verzeichnis in Bank 0. Bedienung `Pro`/`LdP`/`5to`/`bot`. Statische Stapelprüfung beim Bauen. |
| 6.10 | **48 JOV** lädt ein Overlay und springt hinein. Die FNI-Hilfen liegen wieder in 1011. |
| 6.20 | **49 ZUF**, Zufallszahl (Xorshift 16 Bit, Timer eingemischt). |
| 6.21 | INP nimmt Befehle bis 49 an, JOV und ZUF lassen sich also auch eintippen. |
| 6.22 | **Bank leeren:** neuer Auftrag `$30`, und ein neu angelegtes Projekt bekommt alle reservierten Bänke leer. |

## Warum ein neuer Chip

Der AT28C64B hat 8 KB. Davon belegt das Original mit Interrupt und Fernsteuerung die unteren 2 KB. Für eigenen Code blieben zwei 2-KB-Hälften, und in 5.07 waren davon zusammen noch **55 Byte** frei.

Der AT28C256 hat 32 KB. Michael hat dafür Port 1 ganz für interne Zwecke freigegeben. Damit kommen zwei weitere Adressleitungen dazu:

| EEPROM | kommt von | Bemerkung |
|---|---|---|
| A11 | MB0/MB1 (Speicherbank des 8049) | wie im Original |
| A12 | P1.4 (Klemme 5) | seit 4.0x |
| A13 | P1.5 (Klemme 6) | neu: **P1A hat in 6.x keine Wirkung** mehr |
| A14 | P1.1 = SCK des Flash (Klemme 2) | neu: im Betrieb immer 1. SPI läuft in Mode 3, SCK ruht high. |

Am 28C256 ist Pin 1 = A14 und Pin 26 = A13.

A14 ist gleichzeitig die Taktleitung des SPI-Flash. Solange SCK für ein Bit auf 0 geht, liest der 8049 aus der unteren Hälfte des EEPROMs. Dort liegt deshalb eine Kopie des Treiberblocks (1010 = Spiegel von 1011), und `spi` läuft in beiden Hälften Byte für Byte gleich weiter.

## Blockaufteilung

Ein Block ist 2 KB groß. Sein Name besteht aus den vier Adressbits **A11 A12 A13 A14, LSB zuerst** (Michaels Schreibweise). Block `1 a b c` liegt bei `0x800 + a·0x1000 + b·0x2000 + c·0x4000`. Assembler-Adresse und EEPROM-Adresse sind dieselbe.

| Block | EEPROM | Inhalt | Quelle | frei (6.20) |
|---|---|---|---|---|
| 0xxx | 8 × gleich | Kosmos-Original mit Haken, Timer-Interrupt, Fernsteuerung NIE | `cp1.asm` (nicht im Repo) + `rc_*.asm` + `unten5.py` | – |
| **1111** | 0x7800–0x7FFF | **Bedienung**: Start nach Reset (P1 = FF), Tasten CAS/CAL/RUN, Eingaben, Version, Autoboot-Wartezeit | `bedienung.asm` | 596 Byte |
| **1101** | 0x5800–0x5FFF | **Befehle**: alle neuen und geänderten CP1-Befehle (NEG … ZUF) | `befehle.asm` | 778 Byte |
| **1001** | 0x4800–0x4FFF | **Aufträge**: *was* mit dem Flash geschehen soll (Projekte, Blättern, SEF, PSK/FRD/FWR/JOV, Autoboot) | `auftraege.asm` | 349 Byte |
| **1011** | 0x6800–0x6FFF | **Treiber**: *wie* der Flash gelesen und geschrieben wird (`spi`, `f_*`), FNI zum Pi | `treiber.asm` | 386 Byte |
| 1010 | 0x2800–0x2FFF | Spiegel von 1011 (SCK-Fenster) | gebaut | – |
| 1000, 1100, 1110 | | Reserve, erst bei Platznot | | 6 KB |

Die Trennung zwischen 1001 und 1011 ist Absicht. Wer wissen will, was CAS tut, liest 1001. Wer wissen will, wie ein Sektor geschrieben wird, liest 1011.

### Wechsel zwischen den Blöcken: die Sprungtabelle

`build6.py` erzeugt oben in jedem Block 1xxx dieselbe Sprungtabelle, Byte für Byte gleich. Im Moment hat sie 59 Einträge (39 Sprünge `zu_X`, 20 Fernaufrufe `fa_X`) und 353 Byte. Der Build meldet nur die 39 Sprungziele. Nur dort wird der Block gewechselt. Das geht, weil der nächste Befehl nach dem Umschalten von P1 schon aus dem anderen Block kommt, und zwar an derselben Stelle.

- **`zu_X`** springt nach X, egal in welchem Block X liegt:
  `ORL P1,#$30` (→ 1111) `[ANL P1,#maske]` (→ Zielblock) `JMP X`.
  Liegt X unten im Original, steht dort `SEL MB0 / JMP X`.
- **`fa_X`** ist ein *Fernaufruf* von 1001 in den Treiber 1011:
  `ORL P1,#$20 / CALL X / ANL P1,#$df / RET`.
  Das kostet **eine Stapelebene mehr** als ein CALL im selben Block.
- **Regeln:**
  - Ins Original geht es per JMP nur aus 1111, denn die Haken des Originals springen direkt nach 1111. Aus den anderen Blöcken geht das nur über `zu_X`.
  - CALL ins Original ist überall erlaubt, weil RET in denselben Block zurückkommt.
  - Original-Routinen ruft man immer mit `SEL MB0 / CALL x / SEL MB1` auf.

### Stapelprüfung

Der 8049 hat 8 Stapelebenen, und der Timer-Interrupt braucht selbst 3 davon (`rc_tast` → RETR beim NIE-Reset). Schon 5.x stand bei 7 von 8.

`build6.py` verfolgt deshalb beim Bauen statisch jeden Pfad. Die Grenze liegt bei **höchstens 7 von 8 Ebenen**, eine bleibt Reserve. Wird sie überschritten, bricht der Build ab.

Am tiefsten geht es heute in `s_sef`: `fa_f_zustand > f_zustand > f_cmd > f_start > Interrupt` = 7.

Steht an einer Marke `[ohne Interrupt]` (`blk_ein`, `blk_aus`, FNI), rechnet die Prüfung den Interrupt dort heraus. `sim48` prüft das zur Laufzeit bei jedem Befehl gegen `cp1v6.ohneint`.

Folge für neue Treiber-Routinen: Sie müssen flach bleiben. Deshalb lesen `f_zustand` und `fw_stueck` selbst und nicht über `f_lies`, und `f_cea` ist eine flache Kopie von `compute_effective_address`.

## Internes RAM (8049, 128 Byte), Belegung der Erweiterung

| Adresse | Name | Inhalt |
|---|---|---|
| 0x16 / 0x17 | LEER / AUFTRAG | Leerlauf-Merker, Auftrag der Fernsteuerung |
| 0x20–0x25 | VRAM | Anzeige, Stellen 1–6 |
| 0x26 | F_JOB | Auftrag bzw. Betriebsart während FRD/FWR. Fertig: 0 = gut, $EE = Fehler |
| 0x2C–0x2F | F_BANK, F_SEKT, F_OFH, F_OFL | Flash-Adresse |
| 0x36 / 0x37 | ACCU / ACCU_LSB | Akku: Befehlsteil (0 = Datum) und Wert |
| 0x38 | PC | Programmzähler |
| 0x3B | MEM_SIZE | letzte gültige Zelle (127 oder 255) |
| 0x3C–0x3E | F_ANF, F_ANZ, F_RAM | erste Zelle in der Bank, Anzahl (0 = 256), erste Zelle im RAM |
| 0x44 | T_SPEICHER | zuletzt gedrückte Zifferntaste für TSE |
| 0x45 | S_RSP | Stapelzeiger JSR/PSH |
| 0x47 | S_OVFAUS | 1 = Überlauf aus (OVF 000) |
| 0x48–0x5D | S_RSTAPEL | Stapel, **22 Ebenen** |
| 0x5E | S_PRES | reservierte Bänke des geladenen Projekts (PSK k: k < S_PRES), 0 = kein Projekt |
| 0x5F | S_PBANK | erste Bank des geladenen Projekts (SEF, PSK 0) |
| 0x60–0x6F | F_NAME / S_… | Name (16 Byte) bzw. Arbeitszellen der Bedienung |
| 0x70–0x7F | F_PUF, F_LPUF, RC_… | Puffer, Fernsteuerung |

Die vollständige Liste steht in den `.equ`-Zeilen von `bedienung.asm` und `treiber.asm`.

## Flash (IS25LP016D, 2 MB = 256 Bänke)

- Jede **Bank** besteht aus zwei 4-KB-Sektoren im Wechsel. Beim Schreiben kommt der neue Inhalt in den freien Sektor, und erst ganz zum Schluss wird er gültig. Ein Stromausfall verliert deshalb nie die alte Fassung.
- Aufbau des gültigen Sektors:

| Offset | Inhalt |
|---|---|
| 0x000–0x1FF | 256 Zellen à 2 Byte |
| 0x200–0x20F | Name (16 ASCII) |
| 0x210 / 0x211 | Generation / 00 = gültig |
| 0x212 | 00 = Bank hat Namensbereich |
| 0x213 | **Start-PC** (6.00) |
| 0x300–0x5FF | Namensbereich: Labels und eigene Kurzanzeige, ab 0x500 die Bilder für SEF |

- **Bank 0 = Verzeichnis.**
  - 0x000 enthält „CP1V“, 0x004 die Version 01.
  - Ab 0x300 stehen 99 Einträge à 32 Byte. Ein Eintrag enthält Name (16), erste Bank, reservierte Bänke, Flags (FE belegt, FF frei) und die Kurzanzeige (6 Segmentbytes).
  - Neue Einträge schreibt der CP1 direkt in freien Platz (FF), ohne zu löschen. Löschen macht der Pi.
- **Bank 1** enthält die Einstellungen: 0x000 ist das Autoboot-Projekt, 00 = aus.
- **Bänke 2–3** sind frei für später. **Projekte** liegen ab Bank 4.
- **Anlegen:**
  - Ein neues Projekt bekommt 4 Bänke in der ersten passenden Lücke. Gibt es keine, bekommt es weniger, und wenn gar nichts frei ist, kommt **F-012**.
  - Programme benutzen nur Bänke im eigenen Projekt: `PSK k` mit k < Anzahl, sonst F-003.
- **Leeren (6.22):** Eine Bank ist leer, wenn keiner ihrer Sektoren gültig ist. Ein gesetztes Byte wird im Flash nur durch Löschen wieder FF, also heißt Leeren: beide Sektoren löschen (`f_leeren`, je 45–300 ms).
  - Legt der CP1 ein Projekt neu an (CAS, `$80`), leert er alle reservierten Bänke (`kp_neu_b`). Bis 6.21 wurde nur die erste neu geschrieben, in den übrigen blieben alte Inhalte stehen. Nach dem Umstieg von 5.x waren das alte 5.x-Bänke, die `projekt-sichern` dann mit exportierte und die `JOV` geladen hätte.
  - Der Pi leert mit dem Auftrag **`$30`** (`j_leeren`, ohne Datenübertragung, Ende mit `F_JOB = 0`) nach `projekt-einspielen` die reservierten Bänke, die das Projekt nicht belegt. Von Hand: `kosmos_remote.py bank-leeren 6 7`, Bank 0–3 nur mit `--auch-system`.
  - Warum `$30` und nicht `$2C`: Unbekannte Aufträge prüft der Verteiler danach nach Bits (Bit 7 speichern, Bit 3 Autoboot, Bit 2 laden). Ein 6.21 hätte `$2C` als „Projekt laden“ ausgeführt und das RAM überschrieben. `$30` hat keins dieser Bits, ältere Firmware verwirft ihn ohne Wirkung.

## Befehle, die 6.x dazubringt

| Nr. | Befehl | Wirkung | Routine |
|---|---|---|---|
| 36–38 | PSK / FRD / FWR | wie 5.x, aber **Bank k relativ zum Projekt** (PSK 0 = erste Bank) | `s_fbef` → `sf_ok` (1001) |
| 48 | **JOV z** | `PSK k / PSK n / JOV z`: n Zellen (0 = 256) ab z aus Bank k des Projekts an dieselbe Stelle ins RAM, dann weiter bei z. Leere Bank, Überlauf, k zu groß oder kein Projekt → F-003. | `sa_jov` (1101) → `sf_jov` (1001) |
| 49 | **ZUF n** | Akku = Zufallszahl 0 … n−1, `ZUF 0` = 0–255. Zustand: 16 Bit in der **letzten RAM-Zelle** (255 bzw. 127). Bei jedem Aufruf wird das Timer-Register eingemischt. Xorshift 7/9/8, Periode 65535, Werte ≥ n werden verworfen. Dauert ~0,9 ms. | `s_zuf` (1101) |
| 50–99 | | F-002 | |

**Eintippen:** Seit 6.21 nimmt INP Befehle bis 49 an, JOV und ZUF gehen also auch über die Tastatur. Die Grenze steckt im Original-Haken `ADD A,#$ce` (256 − 50) in `build6.py`. In 6.20 stand dort `#$d0`, und INP nahm nur Befehle bis 47.

### Overlays mit JOV

`kosmos_remote.py paket` macht aus einem Quelltext mit Teilen eine Projektdatei, und zwar eine Bank je Teil:

```
.bereich 040-219          wechselnder Bereich
>>kern                    fest, Bank 0 des Projekts (auch alles vor dem ersten >>teil)
      …
      LADE spiel          -> PSK 1 / PSK Länge / JOV 040
>>teil 1 spiel            Bank 1, beginnt am Bereichsanfang
      …
>>teil 2 wuerfel
      …
      LADE spiel          auch aus einem Teil heraus
```

**Regel (nicht geprüft):** Nie `LADE` aus einem Unterprogramm aufrufen, das selbst im wechselnden Bereich liegt. Der Rücksprung auf dem JSR-Stapel zeigt danach in Code, den es nicht mehr gibt.

Beispiele: `examples/beispiel-overlay.koa`, `examples/minenflug-wuerfel.koa` (Minenflug mit Würfelrettung, zwei Teile).

## Bedienung (Kurzfassung, Einzelheiten in der Schnellübersicht)

| Taste | kurz | 1 s halten |
|---|---|---|
| CAS | `Pro __` → ganzes RAM ins Projekt, Start = PC; ein neues Projekt wird angelegt | `Fr ___ to ___ Pro __ d5t ___` speichert einen Teilbereich |
| CAL | Projekte durchblättern (`Pro nn`, dann Kurzanzeige), Ziffern wählen direkt | lädt das gezeigte Projekt (`LdP nn`), im Leerlauf: `Pro __ Fr ___ to ___ d5t ___` lädt einen Teilbereich |
| RUN | Start | `bot __` Autoboot-Projekt, 00 = aus |

Beim Einschalten erscheint 1 s lang `6.22`, dann 2 s lang `bot nn`. Jede Taste bricht den Autoboot ab.

## Bauen und testen

```sh
cd firmware
cp /pfad/zu/cp1.asm .        # Kosmos-Original (asig, bitgleich zu MAME cp1-2716), nicht im Repo
python3 v6/build6.py         # -> v6/cp1v6-eeprom.bin (32 KB), cp1v6.sym, cp1v6.ohneint
sh v6/alle_tests.sh          # 19 Testreihen im Simulator (sim48), mit PROJEKTE=<Ordner mit .cp1> 20
                             # grün nur, wenn jede Reihe mit Exit-Code 0 und „ALLES OK“ endet
python3 v6/routinen.py > ../docs/firmware6-routinen-de.md
```

- **Erwarteter Hash** (SHA-256 des Abbilds), Anfang: 6.00 `f0c70050c6eeee32`, 6.10 `1c65d5c9d65e7161`, 6.20 `9bd7de80ba731d48`, 6.21 `e595c1d5c3480317`, **6.22 `3c306906ce87cb37`**.
- **Pi-Software 6.x:** liegt im Hauptordner des Repos (`kosmos_remote.py`, `.html`, `kosmos_rc.c`, Assembler und Disassembler mit ZUF/JOV/LADE) und läuft so auf bastelpi.
  - Die Fassung für 5.07 liegt in `firmware/v5/pi/`. Die 5.x-Tests nehmen sie von dort, `kosmos_schnell.py` teilen sich beide.

## Offen

- `bank-leeren` meldet auch bei älterer Firmware „geleert“: Sie verwirft `$30`, und der Pi kann das nicht unterscheiden.
- Die LADE-Regel prüft der Assembler nicht.
- `projekt-einspielen` löscht einen schon gesetzten Autoboot nicht.
- Lädt der Pi ein Programm, schreibt er alle 256 Zellen. Dabei wird auch die ZUF-Zelle 0, was harmlos ist: ZUF macht aus 0 eine 1.
