# Kosmos CP1 – Laborbuch

Rohe Arbeitsnotizen von Claude zum CP1-Projekt mit Michael, chronologisch, mit Irrwegen. Die aufgeräumte Fassung steht
in `firmware-de.md`, das Protokoll in `../INTERNALS.md`. Abbilder der Firmware nur
privat (Copyright Kosmos, nie in ein Repo).

## Warum

Der CP1 war Michaels erster Rechner, an dem er programmieren gelernt hat. Das Original ging durch ein Gewitter an der
Gartenbahn verloren; das jetzige Gerät ist ein Ersatz. Ziel: ROM nachbauen, erweitern, mit dem Pi verbinden – ohne
den Charakter des Geräts zu verlieren.

## 2026-11-02/03 – ROM nachgebaut, Adapter entworfen

- asigs `cp1.asm` + eigener Assembler `asm48.py` ergeben bitgenau MAME `cp1-2716`. Chip im Gerät: M5L8049 „KOSMOS B“, gesockelt.
- Irrweg: eigenen 8049 per MOVP auslesen geht nicht (EA high → alles extern). ROM-Verify mit 12 V an EA: Datenblatt
  kennt den Mitsubishi nicht, EA max. 7 V → am eigenen Chip nicht versucht.
- EA-Adapterplatine v1 in KiCad (Werkbank-Rechner), bei NextPCB bestellt; Teile bei Reichelt; T48-Programmer.
- T48: Firmware 00.1.03 zu alt für minipro 0.7.4 → Update über Xgpro. **Fehler von mir:** Selbsttest `minipro -t` mit
  EN25F40 im Sockel laufen lassen (Pins „shorted“). Chip hat überlebt. Seitdem: Selbsttest nur mit leerem Sockel.
- T48-Autodetect taugt nicht (ID 0x0000); Trick: irgendein 25er-Profil mit `-D`, die Fehlermeldung nennt die echte ID.

## 2026-11-11/12 – Adapter läuft, schnelle Kassette

- Platinen da, leer durchgeklingelt: alles ok.
- Kein Kassetteninterface vorhanden: bastelpi GPIO 26 hängt direkt an Klemme 8 = P1.7. Schnelle Kassette = reine Software.
- Drahtbrücke A11 → P23 (JP2 entfällt): 4 KB, 0x800–0xFFF frei.
- Erststart: Ziffern blinkten einzeln, dann Müll, ALE 11 kHz statt 400 kHz. **Mein Entwurfsfehler:** 22 pF an XTAL1;
  der NMOS-Oszillator des MCS-48 verträgt dort nur wenige pF (Original: nur an Pin 3). Michael hat C1 entfernt.
  Lehre: Oszillatorbeschaltung bei Altchips aus Original/Datenblatt, nicht aus 8051/AVR-Gewohnheit.
- Zweiter Fehler: Tastaturspalten an P20–P23 zwingen bei Tastendruck A8–A11 auf 1 → Absturz mit EA = 1.
  Fix: 4× BAT42 auf der Stecker-Platine.
- Schnelle Kassette (Pulse 0,4/1,2 ms, Interrupt stiehlt bis 260 µs) im eigenen Simulator getestet, dann am Gerät:
  256 Zellen CP1 ↔ Pi, CRC ok.
- Neue Befehle in einem Rutsch: NEG als XOR, UND, ODR, OVF, ANZ 001 (Vorzeichen), SEG, AS1–AS3, TST, JSR/RET (Stapel
  24 Ebenen 0x48–0x5F), PSH/POP. Cheat Sheet als PDF (eigener kleiner Satz → SVG → rsvg-convert).

## 2026-11-13 – Fernsteuerung, SPI-Flash

- 3.05: Fernsteuerung im Timer-Interrupt über Klemme 8 (Statusabfrage unsichtbar, ein Byte je Interrupt), Webseite
  http://bastelpi:8049/, C-Hilfsprogramm `kosmos_rc` für das µs-Timing (Python auf dem Pi Zero zu langsam).
  Lehre: keine Ferntasten schicken, während Michael ein Programm laufen hat.
- 4.00: SPI-Flash IS25LP016D an P1.0–P1.3 als „Festplatte“ (256 Bänke, je zwei 4-KB-Sektoren im Wechsel, Verzeichnis
  in Bank 0). Code passte nicht mehr: **A12 an P1.4** (Michael trennte die Leiterbahn zu Klemme 5), zwei EEPROM-Hälften,
  Umschaltstummel mit gleichen Bytes in beiden Hälften. P24 ging nicht (schaltet die 8155 im Interrupt).
  Michael: „WIE GEIL! Es funktioniert!“
- 4.01/4.02: Bank suchen, Befehle PSK/FRD/FWR, TSE (Taste ohne Warten, VZG merkt Tasten) – Asteroiden-Spiel.

## 2026-11-14 – Trennpunkt, Plan 5.00, K78P

- 4.03: Dezimalpunkt über PA7 (Michael hat den Überspannungs-Transistor umgelegt). Zwei Punkte, weil die Original-
  Ziffernschiebung Bit 7 mitnahm → Fix in 5.00.
- Plan 5.00 im Claude-Doc mit Michael abgestimmt („erst reden, nix bauen“). Kern: CAS/CAL bedienen den Flash, die
  Kassette fliegt raus, zwei Übertragungsarten mit Michaels Namen **NIE** (normal, interrupt enabled) und **FNI**
  (fast, no interrupt). Klemme 7 umgebaut wie Klemme 8 (Z-Diode 3V3 + 1 kΩ) → zwei Leitungen, I²C-artig.
  Michael nennt es später **K78P** (Klemme-7-und-8-Protokoll).
- Warum zwei eigene Bytes LEER/AUFTRAG (0x16/0x17) statt eines Merkbits: Lese-Schreib-Wettlauf zwischen Hauptprogramm
  und Interrupt. 0x16/0x17 = 8. Ebene des 8049-Stapels, nachweislich nie belegt (Stapeltiefe-Prüfer).
- Speicher lief über → Lückenfüller `packer.py`, Prüfwerkzeuge (Ablauf, Stapeltiefe, Zyklen). Lehre: bei bedingten
  Sprüngen gilt die Seite des Operandenbytes.
- 5.00/5.01 am Gerät ok. Erster Komplettdump scheiterte: Pi startete nach Blockfehler neu, während der CP1 noch
  wiederholte, und las das alte $EE als „abgelehnt“ → F_JOB vor jedem Versuch auf 0.
- 5.02: Reset wie Einschalten (CLR halten + STP, NIE 09). Kniff: `CALL $003` im Interrupt, damit das dortige `RETR`
  den Interrupt-Zustand beendet – sonst käme nie wieder ein Interrupt. Michael: „kaltstart funktioniert sauber“.

## 2026-11-14 nachts – Editor mit Namen, Einschaltfehler, Timing

- Webseite: ein Editor + Namenstabelle (`035=display_loop`), beim Assemblieren Relabeln statt Konflikt
  (Michael: „es geht nur darum dass man sieht wo was landet“). Namen im Flash-Sektor ab 0x300 (5.03, FNI $29).
- Einschaltfehler `F 004` / „zufällige 2“ seit 5.00: internes RAM ist beim Einschalten zufällig, AUFTRAG 0x17 wurde als
  Taste geliefert. Simulator startete immer mit Nullen → nie gesehen. 5.04 löscht die Bytes; Test mit Zufalls-RAM
  (5.03: 22 von 40 Starts kaputt, 5.04: 0).
- `P-F.Err` bei langen Übertragungen am Gerät, im Simulator nie. Ursache: 40/40 µs zu knapp (CP1 fragt T nur alle
  22,5 µs ab, braucht bis ~45 µs), Pi versuchte 4×, CP1 3× → Pi taktete ins Leere, Bitgewitter auf Klemme 8 löste die
  Notbremse aus. **Mein Fehler dazwischen:** eine „T gehalten?“-Prüfung im Pi eingebaut, die jede Übertragung
  abbrach (Michael: „da funktioniert nix mehr“) – zurückgebaut. Fix: 80/100 µs, 3 Versuche. Danach keine Wiederholung
  mehr in 11 Übertragungen.
- „In Editor“ übernahm die alte Namenstabelle bei Bänken ohne Namen → nur noch die Namen der Bank.
- Rakete, Lauftext, Asteroiden mit sprechenden Labels versehen (Zellen unverändert verglichen).

## 2026-11-15 – Blättern (5.05)

- Michaels Idee beim Spielen: je Bank eine 6-stellige Anzeige, CAL kurz blättert, CAL lang lädt. Immer ab der
  niedrigsten belegten Bank, `bAn nnn` blitzt kurz, ohne eigene Anzeige der Name über eine ASCII→Segment-Tabelle.
- Platz in Hälfte B zu knapp → Kopfanzeigen nach Hälfte A verlegt, gemeinsames Unterprogramm `naechste_bank`.
- Test fand: `kopf_bank` nutzte S_SYM (0x6D), das in F_NAME liegt → „m“ im 14. Namenszeichen. Behoben.
- Am Gerät: „blättern klappt“. Rundlauf ~1,6 s (SPI-Prüfung aller Bänke).
- Frei danach: Hälfte A 144, B 52 Byte. Reserve: 2× AT28C256 (A13 an P1.5 würde Klemme 6 kosten).
- Toolchain nach GitHub gepusht (Michaels OK), dazu `INTERNALS.md` (K78P) und Schnellübersicht 5.05.

## 2026-11-15 nachmittags – Minenflug, 5.06/5.07

- Michaels Spielidee mit den Dezimalpunkten. Erst Plan, dann „go“.
- Erster Entwurf: 342 Zellen. Gepackt (Minerale im Anzeigepuffer, Geschoss „aus“ = Position außerhalb,
  verschränkte Tabellen) auf 268 – immer noch 12 zu viel, genau die Konstanten-Zellen. Michael: Befehle
  mit festem Wert → 5.06 mit `ADD #1` usw. Danach SEF (Bilder aus dem Flash), auf seinen Einwand mit
  Bank 255 als gemeinsamer Ablage in die eigene Bank verlegt; SEF 254 nachgeschoben, weil mein
  „Lauftexte geschenkt“ ohne Akku-Position nicht stimmte.
- Platzkampf in Hälfte A: Der Lückenfüller fand trotz genug freier Bytes keine Lösung. **Gefährlichster
  Fund:** Ein Build sah fertig aus, aber Hälfte A war über 0xFFF hinausgelaufen – AS/JSR/PSH/VZG lagen
  außerhalb des EEPROMs, das Bauskript prüfte nur bis 0xFFF. Gemerkt nur, weil „frei 579 Byte“ nicht
  stimmen konnte. Jetzt prüft build5.py bis 0x17FF.
- Fehler von mir: pkill mit einem Muster, das auch meine eigene Shell traf (zweimal Exit 144). Lehre:
  Prozesse per PID beenden, nicht per Muster, das im eigenen Befehl vorkommt.
- Michael wollte Minenflug in Bank 4 – dort liegt der Asteroiden-Rekord (FRD/FWR); hätte beide
  zerschossen. Jetzt Bank 8, Bank 4 heißt „Asteroiden Daten“.
- 5.07 (Bank 0 = eigene Bank bei FRD/FWR) auf Michaels Beobachtung, dass das Initialisieren so viele
  Zellen frisst. Seine Idee für die gesparten Zellen: beim Boom blinken die Punkte-LEDs (mit Relais).
- Michael nach dem Spielen: „das macht so viel Spaß, Schwierigkeitsgrad genau richtig“.
- Später vielleicht: Overlays (Spielteile per FRD nachladen), „eigene Bank + n“.

## 2026-11-16 – Plan 28C256 (Firmware 6.x)

- 5.07 hatte noch 55 Byte frei. Michael gibt Port 1 ganz für interne Zwecke frei. Damit gehen A13 an P1.5 (Klemme 6) und
  A14 an SCK des Flash (P1.1, SPI Mode 3, ruht high), und der AT28C256 hat 32 KB statt 8 KB.
- Seine Aufteilung: Die acht unteren 2-KB-Blöcke bleiben gleich (Original, Interrupt), die acht oberen sind frei
  für eigenen Code, also 18 KB statt 6 KB. Er benennt die Blöcke nach A11 A12 A13 A14 mit dem LSB zuerst: 1111 Bedienung,
  1011 Treiber, 1101 Befehle, 1001 Aufträge, 1010 Spiegel von 1011.
- Verworfen: ein dritter 8155 mit RAM-Umschaltung. Mehr Platz kommt stattdessen über Overlays aus dem Flash (Befehl JOV).
- Neues Flash-Verzeichnis: 99 Projekte statt 256 Bänken. Jedes Projekt bekommt 4 Bänke, Programme sprechen nur ihre
  eigenen Bänke an (`PSK k` relativ). 5.08 bleibt die letzte Firmware für den alten Chip.
- Versionsschema ab 6.00 (Michael): M.mf, also Architektur . Benutzerwirkung Fehlerbehebung.

## 2026-11-17 – 6.00, 6.10, 6.20 im Simulator

- **6.00:** Die Hälften wurden auf vier Blöcke verteilt. Dazu kommen die gemeinsame Sprungtabelle (`zu_X`), Fernaufrufe 1001 → 1011
  (`fa_X`) und das Verzeichnis mit `Pro`/`LdP`/`5to`/`bot`. `build6.py` braucht keinen Lückenfüller mehr.
- **Stapel (Lehre):** Der Timer-Interrupt braucht selbst 3 der 8 Ebenen, schon 5.x lag bei 7 von 8, und ein Fernaufruf kostet
  eine Ebene mehr. `build6.py` prüft jetzt jeden Pfad statisch und bricht über 7 von 8 ab. Der Simulator prüft
  die Stellen ohne Interrupt bei jedem Befehl. Treiber-Routinen bleiben deshalb flach.
- **6.10: JOV** (`PSK k / PSK n / JOV z`) und Overlay-Pakete im Pi-Assembler (`.bereich`, `>>kern`, `>>teil`, `LADE`).
- **6.20: ZUF n**, auf Michaels Wunsch ohne zusätzliche Takte im Tasteninterrupt. Bei jedem ZUF wird nur das Timer-Register
  eingemischt, weil ZUF ohnehin abhängig von Tastendrücken aufgerufen wird. Der Zustand liegt in der letzten RAM-Zelle (Michaels Idee).
  Xorshift 7/9/8 mit 16 Bit, Periode 65535. Gleichverteilung im Simulator geprüft (Chi² bei ZUF 6 und ZUF 10).
- **Fehler von mir:** ZUF 2 sah zuerst schief aus. Schuld war mein Test, dessen Zähler je Wert über 255 lief (bei OVF 0
  still modulo 256), nicht ZUF.
- **Minenflug mit Würfelrettung** (Michaels Idee): Nach jedem Absturz hüpft ein o über die Anzeige, eine Taste stoppt es,
  dreimal würfeln, ab 12 Augen erscheint „PhEU“ und Leben und Punkte bleiben, sonst „LoSt“. Das Spiel ist ein Overlay-Paket mit Kern, Spielschleife
  und Würfelteil. Dafür musste der Assembler `LADE` auch innerhalb von Teilen auflösen. Getestet nur im Simulator.
  Fehler in meinen Testskripten: „LoSt“ enthält ein o und galt als Würfel, und Segmentmuster wurden falsch zurückgelesen.
- **Doku:** Schnellübersicht 6.20, `docs/firmware6-de.md`, die Routinenliste aus den Quellen (`routinen.py`). Die Angabe
  „4 MHz“ in der alten Doku war falsch, richtig sind 6 MHz bei ALE 400 kHz (von Michael gemessen).
- **Bekannte Lücke:** INP nimmt nur Befehle bis 47 an, JOV und ZUF kommen nur über den Pi ins RAM (behoben in 6.21).

## 2026-11-17 – 6.21: JOV und ZUF eintippen

- **6.21:** INP nimmt jetzt Befehle bis 49 an. Die Grenze ist ein Byte im Original-Haken: `ADD A,#$d0` (256 − 48)
  wurde `ADD A,#$ce` (256 − 50). Ist der Befehl zu groß, läuft die Addition über (Carry) und es kommt F-004.
  Im Abbild ändern sich genau neun Bytes: dieses eine in allen acht unteren Kopien und die letzte Ziffer der Versionsanzeige.
- **Fehler im Testgerüst gefunden:** `test_bilder`, `test_imm`, `test_sef` und `test_tse` endeten auch bei Fehlern mit
  Exit-Code 0, und `alle_tests.sh` sah nur auf den Exit-Code. Ein Lauf meldete deshalb „ALLE GRÜN“, obwohl `test_imm`
  „1 FEHLER“ zeigte (der alte Test erwartete bei 48 noch F-004). Jetzt setzen alle Tests den Exit-Code, und das Skript
  verlangt zusätzlich „ALLES OK“ als letzte Zeile, in `v5/` und `v6/`. Frühere grüne Läufe sind trotzdem gültig:
  Die Logs zeigten bei jeder Reihe „ALLES OK“.

## Chips und Stände

| Firmware | SHA-256 (Anfang) | Wo |
|---|---|---|
| 6.21 | e595c1d5 | Simulator, wartet auf 28C256 |
| 6.20 | 9bd7de80 | Simulator |
| 6.10 | 1c65d5c9 | Simulator |
| 6.00 | f0c70050 | Simulator |
| 5.07 | bd35a143 | im CP1 (seit 2026-11-15) |
| 5.06 | 7bc4d312 | Rückfall |
| 5.05 | 3e404bb0 | – |
| 5.04 | fd58cbc6 | – |
| 5.02 | fc9a6fa8 | – |
| 5.01 | 8dc4cd1b | – |

## Arbeitsregeln, die sich bewährt haben

- Große Vorhaben: erst Plan mit Michael, er sagt „go“.
- Firmware nur nach Simulator-Tests (`v5/alle_tests.sh`, ab 6.x `v6/alle_tests.sh`) brennen lassen; Pi-Software erst mit passender Firmware aktivieren.
- Nichts fernsteuern, während Michael spielt oder tippt.
- Pi-Pins immer als Pin und BCM nennen.

---
*Geschrieben von Claude (KI), 2026-11-15, fortgeschrieben 2026-11-17.*
