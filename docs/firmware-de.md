# Kosmos CP1 – Firmware und EA-Adapter

Bastelprojekt (seit 2026-11-02): die Firmware des 8049 im CP1 verstehen und eine Variante mit schnellerer Kassettenroutine bauen. Weg dahin: ein Adapter, der den 8049 über EA = High seinen Code aus einem EEPROM holen lässt. Toolchain und Kassettenleitung zum bastelpi: siehe [bastelpi.md](bastelpi.md).

## Stand 2026-11-03

| Was | Stand |
|---|---|
| Firmware-Listing nachgebaut | fertig, bitgenau `cp1-2716.bin` (siehe unten) |
| Adapterplatine v1 | 5 Stück von NextPCB da (2026-11-11), sauber gefertigt; leere Platine nach Netzliste durchgeklingelt (VCC↔GND offen, Versorgung, DB0/DB7, ALE, /PSEN, LA0/LA7, P20/P22, Jumper, Quarz): alles ok |
| Bauteile | bei Reichelt bestellt (Liste unten) |
| Programmer | XGecu T48 mit Adaptern und SOIC-8-Klemme (DollaTek, Amazon), Software Xgpro unter Windows |
| EEPROM-Abbild Bank 0 | fertig auf Michaels Werkbank-Rechner, Sicherung auf Michaels Rechnern (seit 2026-11-04, im Backup; nicht im Repo, Copyright) |
| Schnelle Kassettenroutine | Firmware + Pi-Werkzeug geschrieben, im eigenen Simulator getestet (2026-11-12); Test am Gerät offen |
| Firmware im Gerät | **5.07** seit 2026-11-15 (Flash-Tasten, NIE/FNI, Reset, Namen, Blättern, Befehle mit festem Wert, SEF-Bilder, eigene Bank), siehe unten; 5.06 Rückfall |

## Hardware im CP1 (Foto Michael, 2026-11-03)

- CPU: **Mitsubishi M5L8049-136P-6 „KOSMOS B“** (1983, 6-MHz-Version), **gesockelt** → ohne Löten herausnehmen.
- RAM/IO Hauptplatine: NEC D8155HC-2 (Zellen 0–127). Zellen 128–255: CP3-Nachbau mit NEC D8155C.
- **Pin 1** = bei lesbarer Schrift unten links neben der Kerbe (auf Michaels Foto, das auf dem Kopf steht: oben rechts). Vor dem Herausziehen Sockel mit Edding an Pin 1 markieren.
- Unser Listing ist der **2716-Stand**, der Chip trägt **Kosmos B**. Unterschiede unbekannt (siehe Offen).

## Quellen

- **Kommentiertes ROM-Listing:** `cp1.asm` von Andreas Signer im Emulator-Projekt https://github.com/asig/kosmos-cp1 (dort auch `docs/schaltplan.pdf` und Datenblätter 8048/8155). Code © 1983 Franckh'sche Verlagshandlung, Kommentare © 2017 Signer.
- **MAME-Treiber** `src/mame/skeleton/cp1.cpp` kennt zwei Firmware-Stände. „Not working“ heißt dort nur, dass die MAME-Emulation (Tastatur, Anzeige) unfertig ist; beide Stände liefen auf echten CP1:

| MAME-Name | Herkunft | CRC32 | SHA1 |
|---|---|---|---|
| `cp1-kosmos-b.rom` | Mask-ROM im 8049 | `fea8a2b2` | `c987b79a7b90fcbd58b66a69e95913f2655a1f0d` |
| `cp1-2716.bin` | 2716-EPROM, CP1 mit 8039 statt 8049 | `3a2caf0e` | `ff4befcf82a664950186d3af1843fdef70d2209f` |

## Firmware nachgebaut (2026-11-02)

`cp1.asm` mit dem eigenen Assembler [`kosmos-cp1/asm48.py`](kosmos-cp1/asm48.py) übersetzt ergibt **bitgenau `cp1-2716.bin`** (alle 2 KB, alle 239 Labels wie in Signers `cp1.sym`). Er läuft auf CP1-Hardware (8039 = 8049 ohne ROM, ein 8049 mit EA = High verhält sich gleich) und in asigs Emulator.

```
python3 asm48.py cp1.asm cp1.bin      # → sha1 ff4befcf…
```

`asm48.py` ist ein eigener kleiner MCS-48-Assembler (Syntax wie asm48 von SourceForge: `.org`, `.equ`, `.db`, `$hex`, `<label`). Der SourceForge-asm48 wurde bewusst nicht gebaut (fremder Code); der bitgenaue Treffer ist der Test des eigenen.

Firmware-Binaries kommen nicht ins Repo (Copyright Kosmos); sie lassen sich jederzeit aus `cp1.asm` neu bauen.

### EEPROM-Abbild

AT28C64B = 8 KB = 4 Bänke à 2 KB, Bank = A12/A11 (Jumper JP3/JP2).

| Bank | JP3 (A12) | JP2 (A11) | Adressen im EEPROM | Inhalt v1 |
|---|---|---|---|---|
| 0 | 1-2 | 1-2 | 0x0000–0x07FF | Original (2716-Stand) |
| 1 | 1-2 | 2-3 | 0x0800–0x0FFF | leer, später schnelle Kassette |
| 2 | 2-3 | 1-2 | 0x1000–0x17FF | leer |
| 3 | 2-3 | 2-3 | 0x1800–0x1FFF | leer |

Bauen: `cp1.bin` (2 KB) + 6 KB 0xFF = 8192 Byte. v1: sha1 `0797f5b0a98868f5178d6228131ff7d1563bfa85`. Leere Bank gewählt → 8049 läuft durch 0xFF, nichts geht kaputt, Anzeige bleibt tot.

## Kassette laut ROM

- **Hardware (Michael, 2026-11-11):** Es gibt **kein Kassetteninterface**. Der bastelpi (GPIO 26) hängt direkt an **Klemme 8 von Port 1 = P1.7 (DIP 34, am Adapter J1.14)** des 8049, wo sonst das Kassetteninterface CP2 säße (Datenleitung laut CP2-Anleitung; Klemmen 1–8 = P1.0–P1.7). **Klemme 7 = P1.6 (DIP 33)** ist beim CP2 nur die Steuerleitung Senden/Empfangen, das ROM setzt sie nach der Übertragung auf 0 V; der Pi braucht sie nicht. Laut Anleitung beim Speichern zuerst 16 s Kontrollton (Klemme 8 high), Bit = 1/3 + 2/3, steigende Flanke beendet das Bit (CP2-Anleitung ohne Schaltplan liegt bei Michael; nachbauen nicht geplant). Kein RC-Glied o. Ä. dazwischen; die Geschwindigkeit begrenzt nur die Software (ROM-Zeiten bzw. Linux-Timing auf dem Pi).
- **CAS (CP1 → Pi), `save_memory`:** je Bit Low + High, 30 + 60 ms bzw. 60 + 30 ms = 90 ms/Bit, ~11 Bit/s; voller Speicher (512 Byte) ≈ 6 min.
- **CAL (Pi → CP1), `cassette_read_bit`:** tastet alle 2 ms ab, 4 ms Störfilter je Flanke, entscheidet nur nach dem Verhältnis Low/High (je mindestens 3 Zählschritte). `kosmos_send.py` sendet 15 + 30 ms = 45 ms/Bit; Untergrenze geschätzt ~12 + 24 ms (nicht getestet).
- Beim Start löscht `init` per `clear_ram` beide 8155 gleichzeitig: RAM bei angehaltenem 8049 von außen zu befüllen geht deshalb nicht. Direkter Buszugriff von außen auch nicht (MCS-48 hat kein Bus-Request); Live-Zugriff ginge nur durch Nachbilden eines 8155 (RP2040-PIO-Idee, siehe Offen).

## EA-Adapterplatine v1

Dateien in `kosmos-cp1/adapter/`:

| Datei | Inhalt |
|---|---|
| `cp1adapter.py` | erzeugt auf Michaels Werkbank-Rechner (KiCad 10.0.7, `python3 cp1adapter.py`) die Platine: Platzierung, Netzliste, eigener Gitter-Router, GND-Flächen beidseitig. DRC: 0 Fehler, 0 offene Verbindungen |
| `cp1-adapter.kicad_pcb` | Ergebnis (KiCad 10) |
| `cp1-adapter-gerber.zip` | Fertigungsdaten (so bei NextPCB bestellt) |
| `top.png` | 3D-Ansicht oben |
| `cp1schaltplan.py`, `schaltplan.pdf/.svg` | Schaltplan mit Linien aus derselben Netzliste (U2/U3 als logische Symbole, GND/VCC als Symbole) |

Arbeitsstand auf Michaels Werkbank-Rechner (dort auch DRC-Bericht und das EEPROM-Abbild).

### Schaltung

- **U1** 8049 im Präzisionssockel; alle Pins 1:1 an J1, außer **XTAL1/2 (DIP 2/3)** → Quarz Y1 6 MHz + C2 22 pF an XTAL2 direkt auf der Platine (Quarz über 15 cm Flachband schwingt unsicher). **C1 (XTAL1) NICHT bestücken** (Fehler im Entwurf, 2026-11-12 gefunden): Der NMOS-Oszillator der MCS-48 verträgt an XTAL1 nur wenige pF; mit 22 pF schwang der Quarz nicht, der 8049 kroch mit ~165 kHz (ALE 11 kHz statt 400 kHz; Anzeige baut Ziffern einzeln blinkend auf, dann Müll, dann dunkel). Kosmos-Original: Quarz zwischen Pin 2/3, nur 22 pF an Pin 3. und **EA (DIP 7)** → JP1. Diese drei Adern sind am Adapter offen.
- **U2** 74HCT573: D0–7 = DB0–7, LE = ALE, /OE = GND, Q0–7 → EEPROM A0–A7. HCT statt HC wegen der NMOS-Pegel des 8049.
- **U3** AT28C64B: I/O0–7 = DB0–7, A8–A10 = P20–P22, A11/A12 = JP2/JP3, /CE = /OE = /PSEN, /WE fest VCC (8049 kann nie schreiben), RDY und NC offen.
- VDD (DIP 26) nur durchgereicht, nicht mit VCC verbunden. C3–C5 100 nF an U1–U3, C6 10 µF am Eingang.
- **Umbau A11 an P23 (Entscheidung Michael, 2026-11-11):** JP2 wird **nicht bestückt**; Drahtbrücke vom **mittleren JP2-Pad (A11, = U3 Pin 23)** zu **U1 Pin 24 (P23, = J1.34)**. Grund: Das ROM ist voll (frei nur 6 Byte bei 0x7C7); so adressiert der 8049 wie ein 8039-System 4 KB: 0x000–0x7FF Original, 0x800–0xFFF frei für schnelle Kassette + Anzeige (Einsprung per `SEL MB1`/`JMP`). Das Original setzt PC-Bit 11 nie → A11 = 0, läuft unverändert. Bänke damit nur noch über JP3 (A12): 2 × 4 KB. Das Abbild v1 bleibt gültig (0x800–0xFFF = 0xFF, wird nie erreicht). Klingeln: U3.23 ↔ U1.24 piept, U3.23 ↔ GND/VCC offen. Noch im Listing prüfen: P23 auf der CP1-Platine frei? Anzeige-Multiplex per Interrupt oder Schleife?
- **Dioden in P20–P23 (Entwurfsfehler, 2026-11-12 gefunden und behoben):** Die CP1-Tastaturspalten hängen an P20–P23 (je 1 kΩ gegen GND, Zeilen = Digit-Leitungen über BC328 hart auf +5 V). Mit EA = 1 sind P20–P23 aber A8–A11 beim Befehlsabruf → jede gedrückte Taste zwingt eine Adressleitung auf 1, Absturz bei Tastendruck (JP1 = ROM lief einwandfrei). Lösung auf der **Stecker-Platine**: Bahnen U1 Pin 21–24 → J1 40/38/36/34 oben ~6 mm neben dem U1-Stift aufgetrennt, je eine **BAT42** (Schottky) darüber, Anode J1-Seite (8049/EEPROM), Kathode/Ring zum U1-Stift (CP1). Taste gedrückt → Diode sperrt; Lesen 0 über 1 kΩ + ~0,3 V, Lesen 1 über internen Pullup. Skizze: `kosmos-cp1/cp1-stecker-dioden.png`. Für eine v2 gleich auf den Adapter.
- **JP1 EA:** 1-2 = Masken-ROM (Original), 2-3 = EEPROM. **Nur im ausgeschalteten Zustand umstecken.** Mit 1-2 bleibt /PSEN dauerhaft high, das EEPROM ist still → der Adapter kann dauerhaft drinbleiben.
- Ablauf je Befehlsabruf: 8049 legt Adresse auf DB0–7 + P20–22, ALE-Impuls → 573 hält A0–A7 → /PSEN low → EEPROM legt das Byte auf DB0–7. AT28C64B-15 (150 ns) und HCT573 sind bei 6 MHz reichlich schnell.

### Kabel und Stecker zum CP1

J1 ist ein Wannenstecker 2×20. Belegung wie bei einem DIP-Pfostenstecker: **J1-Pin = 2·DIP − 1 (DIP 1–20) bzw. 2·(41 − DIP) (DIP 21–40)**, also Ader 1 → DIP 1, Ader 2 → DIP 40, Ader 3 → DIP 2 …

Ein DIP-40-Pfostenstecker (IDC) ist in Deutschland kaum zu bekommen (Reichelt führt keinen; DigiKey CNC Tech 3040-40-00 o. ä. nur mit hohem Versand). Gewählte Lösung: **eine der übrigen Adapterplatinen als Stecker**:

- Nur bestücken: **Präzisions-Stiftleiste (rund) von unten** in die 40 U1-Löcher (2× 20 aus BKL 10120540), Stifte zeigen nach unten, oben verlöten; **J1** normal von oben. Sonst nichts.
- Auf dieser Platine sind U1-Pads und J1 schon 1:1 verdrahtet. Kabel **J1 ↔ J1** mit zwei Pfostenbuchsen in gleicher Lage (rote Ader an beiden Enden Pin 1) → jeder DIP-Pin landet wieder auf demselben DIP-Pin. DIP 2/3/7 enden auf der Stecker-Platine an unbestückten Footprints = offen, wie gewollt.
- Die Stecker-Platine (92 × 76 mm) liegt flach über der CP1-Platine. Zu wenig Luft über 8155/Widerständen → einen oder zwei GS 40P als Abstandshalter dazwischen. Ein GS 40P kann auch dauerhaft als Sockelschoner im CP1-Sockel bleiben.
- **Zuschnitt (2026-11-11, Michael):** Stecker-Platine war 5 mm zu breit → links entlang der äußeren J1-Bestückungslinie, oben (C6 weg) und rechts dicht neben U1 abgedremelt (volle Drehzahl, gratfrei). Gegen die Netzliste geprüft: alle J1↔U1-Verbindungen inkl. VCC liegen im Rest; **unten nicht kürzen** – GND J1.39→U1.20 läuft auf Höhe JP1 (y 169,85). Klingeltest danach ok.
- Notlösung ohne Platine: GS 40P als Stecker, Adern einzeln in die Kontakte löten (Ader 2k−1 → DIP k, Ader 2k → DIP 41−k; Adern 3, 5, 13 weglassen), mit Heißkleber sichern.

**Vor dem ersten Einstecken durchklingeln:** Stift DIP 1 ↔ Adapter-U1 Pin 1, DIP 40 ↔ U1 Pin 40, DIP 20 (GND) ↔ U1 Pin 20; Stichproben DB0 (12) und ALE (11). Kein Durchgang zwischen Nachbarpins.

### Warum kein ZIF-Sockel

Geplant war ein ZIF-40 für U1. Der bei Reichelt erhältliche 3M Textool (TEX 40 = 240-1280) ist knapp 78 mm lang und ragt laut KiCad-Footprint 23 mm (Hebelseite) bzw. 7 mm über die Pinreihen hinaus → er stünde auf JP1 und fast auf C3 (Layout war vor der Maßprüfung bestellt). Unnötig obendrein: Der 8049 zieht dauerhaft auf den Adapter um, das Original-ROM gibt es per JP1. → normaler GS 40P. Für eine v2: Footprint `Socket:DIP_Socket-40_W11.9mm_W12.7mm_W15.24mm_W17.78mm_W18.5mm_3M_240-1280-00-0602J` nehmen, dann prüft der DRC den Platz mit.

### Bauteile (Reichelt, bestellt 2026-11-03)

| Ref | Anz. | Artikel-Nr. | Teil |
|---|---|---|---|
| U1 | 3 | GS 40P | IC-Sockel 40-pol., gedreht, 15,24 mm (Adapter + Abstandshalter/Sockelschoner + Reserve) |
| U2 | 2 | 74HCT 573 | Octal D-Latch, DIL-20 |
| U2 | 2 | GS 20P | IC-Sockel 20-pol., 7,62 mm |
| U3 | 2 | 28C64-150 | AT28C64B-15PU (**nicht 28C256**: Pin 1/26 wären A14/A13 und hingen offen) |
| U3 | 2 | GS 28P | IC-Sockel 28-pol., 15,24 mm |
| Y1 | 1 | 6,0000-HC49U-S | Quarz 6 MHz, HC-49/U-S (RM 4,88) |
| C2 (C1 nicht bestücken!) | 5 | KERKO 22P | 22 pF NP0, RM 2,5 |
| C3–C5 | 5 | Z5U-2,5 100N | 100 nF, RM 2,5 |
| C6 | 4 | RAD 10/35 | Elko 10 µF/35 V, Ø 5 mm, RM 2,0 (Plus an das eckige Pad) |
| J1 | 3 | WSL 40G | Wannenstecker 40-pol. gerade (Adapter + Stecker-Platine + Reserve) |
| Kabel | 3 | PFL 40 | Pfostenbuchse 40-pol. mit Zugentlastung |
| Kabel | 1 | AWG 28-40G 3M | Flachbandkabel 40-pol., 1,27 mm (davon 10–15 cm) |
| Stecker | 1 | BKL 10120540 | Präzisions-Stiftleiste 40-pol., rund (in 2× 20 brechen) |
| JP1–3 | 1 | MPE 087-1-020 | Stiftleiste 1×20, eckig (3× 3 abbrechen) |
| JP1–3 | 10 | JUMPER 2,54 SW | Kurzschlussbrücke |

Werkzeug: Lötkolben, Multimeter mit Durchgangsprüfer, Schraubstock (Pfostenbuchsen aufpressen), IC-Zieher oder kleiner Schraubendreher.

## Bauanleitung (wenn das Material da ist)

1. **Programmer testen:** Xgpro nur von xgecu.com laden (erkennt Nachbauten). T48 anschließen, wird erkannt? Leeren AT28C64B lesen (0xFF), `cp1-eeprom-v1.bin` schreiben, verifizieren, beschriften „Bank 0 Original“.
2. **Adapter bestücken**, flach zuerst: C2–C5 (**C1 frei lassen**) → Sockel U1–U3 (Kerbe nach Bestückungsdruck) → Quarz → C6 (Polung!) → JP1–3 → J1 (Nase nach Druck). ICs noch nicht stecken.
3. **Stecker-Platine:** Präzisions-Stiftleisten von unten in U1, J1 von oben, sonst nichts.
4. **Kabel:** ca. 20 cm (Michael 2026-11-11; bis ~20 cm unkritisch, > 30 cm nicht – nur je eine GND/VCC-Ader, Übersprechen ALE//RD//WR auf DB), zwei PFL 40 im Schraubstock aufpressen, rote Ader beide Seiten Pin 1, Zugentlastung drauf.
5. **Durchklingeln** (siehe oben) und Sichtprüfung auf Lötbrücken; VCC ↔ GND am Adapter darf keinen Kurzschluss zeigen.
6. **CP1 ausschalten**, Pin 1 am CP1-Sockel markieren, 8049 vorsichtig abwechselnd an beiden Enden heraushebeln, in U1 des Adapters (Kerbe!). 74HCT573 in U2, EEPROM in U3.
7. **Erster Test mit JP1 = 1-2 (Masken-ROM):** Stecker-Platine in den CP1-Sockel, Kabel dran, einschalten. Läuft der CP1 wie vorher, stimmen Kabel, Quarz und Versorgung.
8. **Zweiter Test mit JP1 = 2-3 (EEPROM), JP2/JP3 = 1-2 (Bank 0):** ausschalten, umstecken, einschalten. Läuft er wieder normal, kommt der Code aus dem EEPROM. Kleines Programm eintippen und per CAS/CAL über den bastelpi speichern und laden.
9. Fehlerbilder: nichts in der Anzeige mit JP1 = 1-2 → Kabel/Quarz/Versorgung; Ziffern bauen sich einzeln blinkend auf, dann Müll → Takt zu langsam, ALE an U1 Pin 11 messen (Soll 400 kHz), C1 muss fehlen; nur mit 2-3 → Latch, EEPROM, /PSEN, Bank-Jumper, EEPROM-Inhalt.

## Schnelle Kassette – Pflichtenheft (Entwurf 2026-11-11, Michael)

Eigener Code in 0x800–0xFFF (A11 an P23), Einsprung aus den CAS-/CAL-Stellen des Originals; Original-Routinen (Anzeige, Tasten) per `SEL MB0`/`CALL` mitbenutzen.

- **Übertragung** direkt über P1.7 (Klemme 8) wie das Original nach dem Verhältnisprinzip (1/3 : 2/3, steigende Flanke beendet das Bit), aber im ms-/µs-Bereich; kein 16-s-Kontrollton, nur kurzer Vorlauf. Klemme 7 (P1.6) am Ende auf 0 V wie im Original.
- **Reihenfolge aufsteigend** 000 → 255 (statt Original 127 → 0, dann 255 → 128).
- **CAS kurz:** alles speichern. **CAS halten:** Teilspeichern – Anzeige `C Fr ___`, drei Ziffern tippen (z. B. 035), CAS kurz → `C to ___`, tippen (z. B. 139), CAS → Zellen 035–139 werden gesendet.
- **Header** vor den Daten: Kennung/Version, erste Zelle, letzte Zelle (beide 0–255, damit passt auch „alle 256“); danach die Zellen (je 2 Byte wie im Original), am Ende **Prüfsumme** (Vorschlag CRC-8 über Header + Daten).
- **CAL:** wertet den Header aus und schreibt genau an die angegebenen Zellen; Rest des Speichers bleibt unverändert (→ Unterprogramm-Bibliothek nachladen, ohne das Programm zu überschreiben).
- **Anzeige:** siehe „Stand Firmware“ unten (Eimer-Symbole statt C).
- **Pi:** `kosmos_recv.py`/`kosmos_send.py --schnell` mit µs-Timing auf GPIO 26; empfangene Teilbereiche als JSON nur mit diesen Zellen; senden mit `--von/--bis`.
- **Entschieden (Michael, 2026-11-11):** CAS „halten“ = **1 s** (eigenes Tastenlesen). Ohne Speichererweiterung Grenzen **auf 127 begrenzen**. „to“ < „Fr“ → **tauschen**. Prüfsummenfehler → Anzeige **`C Su Err`**. **STP bricht alles ab** (Eingabe und laufende Übertragung).
- **Befund Listing + Schaltplan (2026-11-11):**
  - **Anzeige und Tastatur laufen komplett im Timer-Interrupt** (`timer`, alle 2,56 ms eine Stelle; 6 Stellen ≈ 65 Hz). Anzeige = Segmentbytes in VRAM `0x20–0x25` (gfedcba, z. B. `C` = 0x39, `o` = 0x5c) einfach hineinschreiben. STP setzt im Interrupt STATUS (`0x3a`) Bit 0 → Abbruch = Bit 0 abfragen. Gehaltene Taste: Interrupt merkt je Zeile den Tastencode in `0x30–0x35`, solange sie gedrückt bleibt (CAS = 0x11) → „1 s halten“ = 1 s lang dort 0x11 finden. Letzte Taste in `0x44`, Tasteneingang über R6' (`0x1e`) und `wait_key`.
  - Speichererweiterung: `MEM_SIZE` (`0x3b`) = 0x7f ohne, 0xff mit CP3. Zellen = 2 Byte; Zelle n liegt im 8155 bei 2·n (n ≥ 128: CP3-8155, `compute_effective_address` wählt den Baustein).
  - Original-CAS: 15 s Vorlauf (60 × 250 ms), dann je 8155 256 Byte in der Reihenfolge 0, 255, 254 … 1 (DJNZ) – daher das „Rückwärtszählen“. Interrupts bleiben dabei an.
  - **Interrupts:** laut MCS-48-Handbuch wird PC-Bit 11 während der Interruptroutine auf 0 gehalten, `RETR` kehrt korrekt in den oberen Bereich zurück → Code in 0x800–0xFFF darf mit eingeschaltetem Interrupt laufen.
  - **P23:** Tastatur-Spalte (wie P20–P22, alle vier mit 1 kΩ nach Masse, gelesen per `MOVD A,P4`). P20–P22 tragen bei externem ROM schon A8–A10, P23 als A11 verhält sich genauso → unbedenklich. Kassette: Klemme 7 = P1.6 „Cass W/R“ (DIP 33), Klemme 8 = P1.7 „Cass Data“ (DIP 34).
  - **Timing-Plan:** Interrupt an lassen (Anzeige + STP gratis); er stiehlt je 2,56 ms bis ~150 µs. Verhältnis-Codierung verträgt das, Start mit ~0,5 / 1,0 ms je Bit (≈ 650 Bit/s, voller Speicher ≈ 7 s statt 6 min), dann am Gerät ausloten.

### Stand Firmware schnelle Kassette (2026-11-12)

Quelltext und Werkzeuge in [`kosmos-cp1/schnell/`](kosmos-cp1/schnell/) (eigener Code; das Kosmos-ROM und die Binaries bleiben draußen):

| Datei | Inhalt |
|---|---|
| `schnell.asm` | eigener Code ab 0x800 (CAS/CAL, Eingabe Fr/to, Anzeige, CRC-8) |
| `build.py` | baut `cp1schnell.asm` = asigs `cp1.asm` mit umgebogenem `cas_handler`/`cal_handler` (je `SEL MB1 / JMP / NOP`, 4 Byte) + `schnell.asm`, übersetzt mit `asm48.py` (4 KB), prüft: im Original-Bereich nur umgebogene Einsprünge anders (INP-Grenze 0x11F: `ADD A,#$dc` statt `#$e7`, damit sich Befehle bis 35 eintippen lassen – sonst F 004; CAS 0x1C4, Tabelle ANZ 0x402, NEG + toter NEG-Rest 0x4A6–0x4BC mit `anz_neu`, UND 0x4C1, error_f006 0x505, opcode_inv 0x659, CAL 0x70E; dazu 0x4DF im toten UND-Rest), pc_handler 0x0B5 (PC gesetzt → JSR-Stapel leeren), alle übrigen Sprungmarken an alter Stelle |
| `sim48.py` | eigener 8049-Simulator (Befehlssatz, Timer-Interrupt, PC-Bit 11 / Interrupt, zwei 8155, Tastatur wie asigs Emulator, Leitung P1.7) |
| `test_schnell.py` | 10 Testgruppen im Simulator: CAS kurz (alles, mit/ohne CP3), Anzeige, CAS halten mit Fr/to, CLR, Tauschen, Begrenzung 127, CAL Teilbereich (Rest bleibt), CRC-Fehler und falscher Kopf → `C Su Err`, STP in jeder Phase, Zittern ±150 µs, Rundreise CP1 → CP1. **Alle grün.** |

Binaries und Abbilder liegen nur privat.

- **Leitung (endgültig):** Ruhe high; Bit = Low-Puls, **0,4 ms = 1, 1,2 ms = 0**, danach ≥ 0,4 ms high (Länge egal, darin rechnet der CP1). Bytes LSB zuerst. Rahmen `$C1`, erste, letzte Zelle, je Zelle Befehl + Argument, CRC-8 (Polynom $07, Start 0). Grund für die Spreizung: Der Timer-Interrupt (Anzeige/Tastatur) hält alle 2,56 ms **bis ~260 µs** an (im Simulator gemessen: gesendete Pulse 0,41–0,66 bzw. 1,22–1,47 ms). CP1 entscheidet beim Lesen bei 0,72 ms, der Pi beim Empfangen bei 0,9 ms.
- **Pi → CP1:** zuerst **CAL** drücken, dann senden. Nach jedem Byte ≥ 2 ms Pause (CP1 rechnet CRC, speichert, zeigt an).
- **Dauer:** voller Speicher (516 Byte) **6,1 s** statt ~6 min; 56 Zellen laden 1,4 s.
- **EEPROM-Abbild v2** (`cp1-eeprom-v2.bin`, 8 KB, sha1 `d37841d2…`): 0x0000–0x07FF Original, 0x0800–0x0FFF leer, **0x1000–0x1FFF schnelle Fassung** (4 KB, sha1 `52719bb3…`). **JP3 = 0: Original, JP3 = 1: schnell.** Setzt die Drahtbrücke A11 → P23 voraus (ohne sie hängt A11 offen).
- **Anzeige (Michael, 2026-11-12):** Ganz links statt `C` (ist schon „9 OUT“ = E/A-Position) die **Eimer-Symbole des Originals**: `⊓` (0x23) für CAS, `⊔` (0x1C) für CAL, **sofort beim Drücken** und bis zum Ende (`⊓ SE 035`, `⊔ rc 200`, `⊔ Su Err`, `⊓   rdY`). CAS halten: rechts nach ¼/½/¾ s `_` `__` `___`, nach 1 s `⊓ Fr ___` (tippen möglich), dann `⊓ to ___`. Striche und `rdY` in der **rechten Dreiergruppe** (Stellen 3–5), weil die Anzeige am Gerät als `8 88 888` gruppiert ist. **Visualisierung** der Simulator-Abläufe (Anzeige, Tasten, P1.7, Interrupts): privates Artifact https://claude.ai/artifact/4n3WnG1droMvtLoYJ9yz8z, erzeugt mit `export_viz.py` + `viz_vorlage.html`.
- **Befehlserweiterungen (Michael, 2026-11-12, Code ab 0xD00):** **NEG xxx** = Akku XOR xxx (Maske direkt im Befehl; **NEG 000 wirkt wie NEG 001**, also wie das Original 0↔1), **UND xxx** bitweise, neu **ODR xxx (25)** = Akku OR Zelle xxx bitweise. Fehler wie im Original (Akku/Zelle kein Datum → F-005, Adresse ungültig → F-003, Befehl 00/26–99 → F-002). Einsprung: erste 3 Byte von `opcode_NEG`/`opcode_UND` und 4 Byte von `opcode_inv` (prüft dort auf 25) umgebogen. `test_befehle.py`: 25 Fälle grün; Gegenprobe mit dem Original-ROM scheitert genau an den neuen Fällen (Werte > 1, ODR), alle 0/1-Fälle und Fehler gleich → abwärtskompatibel. Assembler/Disassembler der Toolchain kennen ODR und zeigen das NEG-Argument (Commit 3da6e31, lokal).
- **OVF und ANZ 001 (Michael, 2026-11-12):** **26 OVF x**: x = 0 schaltet F-006 ab, ADD/SUB rechnen dann modulo 256 (255 + 1 = 0, 0 − 1 = 255); sonst an. Schalter in RAM **0x47** (init löscht 0x20–0x47 → nach dem Einschalten „an“, bleibt bis Reset). **Bewusst nicht von RUN zurückgesetzt** (Michael: wer beim Debuggen mittendrin neu startet, soll das OVF-Aus nicht verlieren). Cheat Sheet: Claude-Doc https://claude.ai/artifact/7oGjUJgkzXwGs9qReSAKLG. Druckfassung (2 Seiten A4 zum Laminieren): `kosmos-cp1/cheatsheet/cp1-schnelluebersicht.pdf`, erzeugt mit `python3 satz.py` (Inhalt in `inhalt.py`; eigener Tabellensatz → SVG → `rsvg-convert`, weil auf dem Rechner weder LuaLaTeX/luaotfload noch XeLaTeX-Format noch Helvetica-Metriken für pdfLaTeX installiert sind). Umsetzung: `error_f006` springt nach 0xD00; das Ergebnis modulo 256 liegt dort in A, R0 zeigt auf den Akku. **02 ANZ 001**: 128–255 als `A  -128` … `A  -001` (Stellen 1/2 „ -“ statt „00“), sonst wie bisher; Tabelleneintrag 02 zeigt auf `anz_neu` im toten NEG-Rest (0x4A9). `test_befehle.py` um 15 Fälle erweitert (alle grün, Gegenprobe Original nur bei den neuen Fällen anders). Toolchain-Commit 107d8b0 (lokal): OVF, ANZ mit Argument.
- **SEG (27, Michael, 2026-11-12, Code ab 0xE00):** **SEG xxx** schreibt die Werte der Zellen xxx … xxx+5 als Segmentmuster (a = 1 … g = 64, Punkt = 128) auf Stelle 1–6; **SEG 255** löscht. Erst alle 6 Zellen prüfen (Puffer RAM 0x70–0x75), dann schreiben: Fehler lassen die Anzeige stehen. xxx+5 über Speicherende → F 003, Zelle kein Datum → F 005. R7 (E/A-Zeiger) bleibt unberührt. HLT zeigt wie im Original danach den PC (bewusst so gelassen; Bild stehen lassen = mit SPU auf sich selbst enden). Einsprung über `s_inv` (Befehl > 24). 11 neue Tests grün; Toolchain-Commit e49f11d (lokal).
- **AS1–AS3 (28–30, Michael, 2026-11-12, Code ab 0xF00):** schreiben Hunderter/Zehner/Einer des Akkus als Segmentmuster nach Zelle xxx (`00.mmm`, direkt SEG-tauglich; Akku 234: AS2 → Muster für 3). Ziffern über `itoa` des Originals, Muster aus eigener Tabelle per `MOVP` (gleiche Seite, MOVP3 aus Bank 1 bewusst vermieden). Führende Null = `0`. Akku kein Datum → F 005, Adresse ungültig → F 003. Einsprung über `s_inv` (28–30). 10 neue Tests grün; End-to-End: Pi-Assembler → Simulator zeigt `  L197`. Toolchain-Commit 06fd1cc (lokal).
- **TST (31, Michael, 2026-11-12):** **TST 000** wartet auf eine Zifferntaste, Akku = 0–9. Grundlage: Der Timer-Interrupt legt jeden neuen Tastendruck auch im Programmlauf in R6' (RAM 0x1E); TST löscht das zuerst (ein Druck vor dem TST zählt nicht) und wartet dann. Andere Tasten werden übergangen. **STP** (STATUS Bit 0): PC wird nicht erhöht, Sprung nach `end_of_instr` → hält wie üblich an, RUN macht beim TST weiter. Argument ist für später frei (Idee: TST 001 ohne Warten). 10 neue Tests grün; Demo vom Pi-Assembler (TST → AS3 → SEG) zeigt die gedrückte Ziffer. Toolchain-Commit 515d0d3 (lokal).
- **JSR/RET (32/33, Michael, 2026-11-12):** Rücksprungstapel im internen RAM: 24 Ebenen 0x48–0x5F, Zeiger **0x45** (init löscht 0x20–0x47 → nach dem Einschalten leer). JSR: PC+1 auf den Stapel, dann wie SPU (PC und R3 setzen, `end_of_instr`). RET: oberste Adresse zurück. **F 008** = Stapel voll, **F 009** = RET ohne JSR; JSR in Zelle 255 → F 003 (kein Rücksprung möglich). **„xxx PC“ über die Tastatur leert den Stapel** (Einsprung in `pc_handler` statt `MOV R6,#0 / JMP wait_key`), RUN allein nicht – sonst bliebe nach F 008 oder einem Abbruch im Unterprogramm der Stapel bis zum Ausschalten voll; STP im Unterprogramm + RUN geht weiter. Internes RAM danach frei: 0x46, 0x78–0x7F; oberer ROM-Bereich noch 774 Byte frei (Seitenenden). 10 neue Tests grün; Pi-Assembler-Demo `1 + 5 + 5` per JSR zeigt `A 00 011`. Toolchain-Commit 7687169 (lokal), Disassembler setzt bei JSR Sprungmarken.
- **PSH/POP (34/35, Michael, 2026-11-12):** Akku auf denselben Stapel wie JSR/RET (zusammen 24 Ebenen; F 008 voll, F 009 leer). PSH verlangt ein Datum im Akku (Befehlsteil 00), sonst F 005 – ein Befehl kann per `LDA` einer Befehlszelle im Akku stehen (selbstmodifizierende Programme), dafür bräuchte es 2 Stapelplätze; bewusst wie die Rechenbefehle abgelehnt. POP setzt den Akku auf 00.xxx. 9 neue Tests grün (u. a. LIFO, Akku über JSR gerettet, 23 PSH + JSR geht, 24 + JSR → F 008). Pi-Demo `AKO 42 / PSH / JSR / POP / ANZ` → `A 00 042`. Toolchain-Commit b0503db (lokal). Oberer ROM-Bereich danach ~720 Byte frei.
- **Pi-Seite (2026-11-12):** `kosmos_schnell.py` in moosy/kosmos-cp1-toolchain (Commit 32197eb auf dem bastelpi, **noch nicht gepusht**), aufrufbar als `kosmos_recv.py --schnell datei.json` bzw. `kosmos_send.py --schnell datei.json [--von N] [--bis M]`; Kopie hier in `kosmos-cp1/schnell/`. Empfang über lgpio-Flankenmeldungen (Kernel-Zeitstempel), Schwelle 0,9 ms; JSON nur mit den übertragenen Zellen. Senden per Busy-Wait mit **SCHED_FIFO** – gemessen auf dem Pi Zero W: ohne Echtzeit bis **+0,5 ms** zu lange Pulse (würde Bits kippen), mit Echtzeit höchstens **+76 µs**; deshalb startet sich `send` selbst mit `sudo -n` neu (`--ohne-sudo` zum Abschalten). In Bytepausen kurzer Schlaf wegen der RT-Drosselung des Kernels (95 %). `test_pi.py`: Werkzeug-Logik gegen den simulierten CP1 (Empfang 256 Zellen, Senden 020–060 mit ±120 µs Zittern, ganze Datei, Lücken-/CRC-Fehler) – alles grün. Hardware laut README: GPIO 26 – 1 kΩ – P1.7, 3,3-V-Zener am Pi.
- **Noch zu tun:** am Gerät testen (erst Adapter mit JP3 = 0, dann JP3 = 1), Pulslängen ausloten; Push der Toolchain nach GitHub (Michael fragen).

## Offen

1. **Schnelle Kassettenroutine** in Bank 1: nur `save_memory`/`cassette_read_bit` ändern, Rest wie Original; `kosmos_send.py`/`kosmos_recv.py` auf dem bastelpi mit Schalter für den schnellen Modus. Vorher Grenzen der Original-Routine mit dem bastelpi ausmessen.
2. **Eigenen 8049 auslesen** (Vergleich mit MAME „kosmos-b“ und dem 2716-Stand): **nicht** per Routine im EEPROM – mit EA = High holt der 8049 *alle* Programmzugriffe extern, auch `MOVP`/`MOVP3`; mit EA = Low läuft nur das Masken-ROM. Weg wäre der ROM-Verify-Modus aus dem Intel-Datenblatt (EA auf erhöhte Spannung, Adresse anlegen, Byte auf DB lesen) mit eigener kleiner Schaltung, oder ein Programmer, der 8049 lesen kann (beim T48 in der Xgpro-Liste nachsehen). Korrektur zu einer Aussage im Chat vom 2026-11-03. **Ergebnis Datenblatt (Mitsubishi Single-Chip 8-Bit Vol. 2, 1986, M5L8049-XXXP-6):** kein Verify-Modus beschrieben, EA „normally maintained at 0 V“, Absolute Maximum Ratings Eingänge −0,5…7 V. Intels 12-V-Verify (z. B. Projekt „8049 Spy“) ist für den Mitsubishi-Chip also nicht abgesichert → **nicht am eigenen Chip versuchen**; wenn überhaupt, erst an einem Opfer-M5L8049. Nutzen gering, „kosmos-b“ ist in MAME schon gedumpt.
3. Später vielleicht: 8155 der CP3-Platine durch einen RP2040 (PIO, Pegelwandler 74LVC245) nachbilden, für Live-Zugriff auf die Zellen 128–255.
4. Verworfen: EEPROM-Programmierer aus dem Funduino Uno + 74HC595 (Plan vom 2026-11-02) – ersetzt durch den T48.

*Erstellt mit Unterstützung von Claude (Anthropic) mit Claude Code. Stand: 2026-11-14.*

## Gerätetest 2026-11-12 (Michael, echter CP1)

- Adapter: nach Entfernen von C1 und den BAT42 in P20–P23 laufen JP1 = ROM, JP1 = EEPROM/JP3 = 0 (Original) und JP3 = 1 (schnell) einwandfrei. EEPROM v2 (sha256 39d6b25b…) mit T48 auf Michaels Werkbank-Rechner gebrannt, Rücklesen identisch.
- Speichererweiterung (selbstgebaute zweite 8155) wird erkannt → CAS kurz sendet 256 Zellen (516 Byte) in ~7 s.
- Schnelle Kassette CP1 → Pi und Pi → CP1, jeweils voll (000–255) und Teilbereich (100–110), alles mit CRC ok, Inhalte geprüft (Blinker in 000–006, Zelle 200 bleibt beim Teilladen unverändert). Pulse am Gerät: CP1 sendet kurz ~0,41 ms / lang 1,22–1,5 ms; Pi sendet kurz 435–515 µs / lang 1233–1304 µs. Keine Anpassung der Schwellen nötig.
- Bedienung: Der Pi-Empfänger wartet nur 120 s ab Start – erst starten, dann CAS. Beim Senden erst CAL am CP1, dann Enter am Pi.
- Noch nicht am Gerät geprüft: neue Befehle 25–35 im Einzelnen.
- Toolchain-Commits (32197eb … 93368e8) am 2026-11-13 nach GitHub gepusht (Freigabe Michael).

## Fernsteuerung und Versionsanzeige (Firmware 3.05, 2026-11-13)

Idee Michael: Der bastelpi drückt Tasten und liest die Anzeige, egal was der CP1 gerade tut. Am Gerät getestet, seit 3.05 ist die Statusabfrage unsichtbar.

**Bedienung:** Beim Einschalten zeigt Bank 1 eine Sekunde `  3.05 ` (Bank 0 = Original, ohne Version). **RUN 1 s halten** = Fernsteuerung an/aus (`rc on` / `rc oFF`); RUN kurz startet wie immer (jetzt beim Loslassen). Nach jedem Einschalten neu aktivieren (init löscht das Flag). Webseite **http://bastelpi:8049/** (Dienst `kosmos-remote`, s. [bastelpi.md](bastelpi.md)): Live-Anzeige, Akku, PC, Tastatur wie am Gerät (gehalten so lange wie gedrückt), Quelltext assemblieren + laden (drückt selbst CAL), Speicher holen (drückt selbst CAS) als Listing/JSON. Kommandozeile: `kosmos_remote.py anzeige | taste 0 0 0 pc run | laden x.json | speichern x.json [--von --bis]` (geht über den Server, wenn er läuft).

**Warum so:** /INT, T0, T1 sind auf der CP1-Platine fest verdrahtet (Schaltplan Handbuch S. 137) → kein freier Interrupt. Stattdessen fragt der Timer-Interrupt (alle 2,56 ms, Anzeige-Multiplex + Tastatur) P1.7 ab. Interrupt-Code muss in 0x000–0x7FF liegen (der 8049 hält A11 im Interrupt auf 0) – dort ist das Original voll; Platz kam aus den in Bank 1 toten alten Kassettenroutinen: Seite 7 (alte CAL, 0x712–0x7E0), Seite 1 (alte CAS, 0x1C8–0x1FE), Seite 3 (alte CAS-Senderoutine `save_memory`, 0x3BD–0x3F2). Danach sind dort nur noch ~20 Byte frei.

**Einhängen:** im Timer-Interrupt `MOVD A, P4 / CLR C` → `CALL rc_tast` (2 Byte); `run_handler` → `SEL MB1 / JMP s_run` (3 Byte, Rücksprung `run_weiter`); Ende von init `CALL clear_ram / EN TCNTI / STRT T` → `SEL MB1 / JMP s_boot / NOP`. `s_cas` (ab Sendebeginn, Fr/to-Eingabe geht noch fern) und `s_cal` setzen Pause-Bit 1, `s_ende` löscht es.

**RAM:** `RC_FLAG` 0x46 (Bit0 an, Bit1 Pause/Kassette, Bit2 Antwort läuft, Bit4/5 Klopf-Takte; init löscht), 0x78 Zeile, 0x79 Maske, 0x7A Dauer der Ferntaste, 0x7B–0x7E Puffer/Prüfbyte/Zeiger/Anzahl, 0x7F Sicherung R1. Stapel höchstens 5 von 8 Ebenen (Simulator).

**Protokoll** (eine Leitung, beide Seiten ziehen nur nach low):
- Anklopfen = Leitung low. Der Interrupt zählt nur die Takte, in denen sie low ist, und wartet nicht. 3,5 ms (1–2 Takte) = **Statusabfrage**: Antwort RAM 0x20–0x3A (Anzeige, Tastenpuffer, Akku 0x36/37, PC 0x38, Status 0x3A). 8,5 ms (3 Takte) = **Befehl**: Anzeige aus (Port A = 0), auf Loslassen warten, 4 Byte lesen: Low 150 µs = 1 / 750 µs = 0 (Schwelle 460 µs), 150 µs high, LSB zuerst, Byte 4 = B1^B2^B3^$A5. `01 zm dd` Taste (Zeile 2..6 im oberen Nibble, Spaltenmaske, Dauer in Bildern à 15,36 ms), `02 aa nn` RAM lesen.
- **Antwort je Interrupt ein Byte** (~1 ms, passt in den Takt → Anzeige läuft normal weiter): Daten, dann Prüfbyte XOR ^ $A5; Low ~43 µs = 1 / ~125 µs = 0, ~43 µs high. Auf `01` nur das Prüfbyte als Quittung.
- Ferntaste: Die Firmware mischt die Spaltenmaske bei der Tastaturabfrage der passenden Zeile dazu → für die Firmware ein echter Tastendruck (Entprellen, CAS halten, TST, STP …). Tastencode k: Zeile = (k+7)/4, Bit = (k+7)%4; Ziffer d = d+1, OUT 11, INP 12, CAL 13, STEP 14, STP 15, RUN 16, CAS 17, CLR 18, PC 19, ACC 20.
- **Notbremse:** Bleibt die Leitung > 5 ms nach dem dritten Takt low (z. B. Programm mit P1A auf Klemme 8), schaltet die Fernsteuerung ab.

**Pi-Seite:** `kosmos_rc` (C, `/dev/gpiomem`, SCHED_FIFO) macht Anklopfen, Senden und Abtasten – Python liest auf dem Pi Zero ~28 µs je `gpio_read` (lgpio) bzw. ~8 µs über gpiomem, zu grob; Flankenmeldungen von lgpio gingen bei schnellen Antworten verloren (Kernel-Puffer). Ohne Echtzeit verpasste der Pi jede vierte Antwort, mit Echtzeit 100/100. `kosmos_remote.py` hält den Prozess als Pipe, wiederholt Abfragen, prüft vor einem Tasten-Wiederholversuch die Restdauer (0x7A), damit nichts doppelt gedrückt wird. Der Server belegt GPIO 26; `--schnell` der alten Werkzeuge geht nur bei gestopptem Dienst.

**Weg dorthin (Lehren):** 3.00 erst Antwort am Stück → Anzeige blitzte (eine Stelle ~30 ms an) → 3.02 Dunkelschalten → 3.03 Antwort ein Byte je Interrupt (Takt gedehnt, Flimmern) → 3.04 kurze Antwortpulse (Byte passt in den Takt) → 3.05 Anklopfen ohne Warten. Dazwischen: Notbremse löste aus, weil Python beim Anklopfen per `sleep` verschlief; Quittung + Schwelle 460 µs gegen vom Pi verlängerte Pulse; `delay_millis` benutzt R2 (Schleifenzähler der Versionsanzeige hing).

**Getestet am Gerät (3.05):** 60/60 Statusabfragen bei 5/s während laufendem Programm, Tastenfolgen korrekt; Michael: „Abfragen ist unsichtbar, das kurze Dunkelschalten beim Tastendruck wirkt wie eine Bestätigung“. Noch nicht am Gerät: Laden/Speichern über die Webseite, CAS halten aus der Ferne (im Simulator ok).

**Dateien:** Quellen in `firmware/history/schnell/` (`rc_unten.asm`, `rc_seite1.asm`, `rc_seite3.asm`, `build.py`, `test_rc.py` u. a.) und `Repo-Wurzel` (`kosmos_remote.py`, `kosmos_remote.html`, `kosmos_rc.c`, `kosmos-remote.service`); Toolchain-Commit f792fbe (GitHub). Abbilder nur auf Michaels Rechnern (`cp1-eeprom-v3.05.bin` a05df70f…, Bank 1 `cp1schnell-3.05.bin` d1a7967a…) und bastelpi `~/cp1-firmware/schnell/`, gebrannt mit dem T48 . Michael hatte zwei EEPROMs: v3.05 im CP1, v3.04 als Rückfallebene (seit 4.0 beide mit 4.x, siehe unten).

## SPI-Flash als „Festplatte“ (Firmware 4.0x, 2026-11-13)

**Idee (Michael):** Programme und Daten dauerhaft im CP1 ablegen. Das EEPROM selbst kann der 8049 nicht beschreiben: /WE liegt fest an +5 V, /CE und /OE hängen an /PSEN. Außerdem liefert der AT28C64B während seines Schreibzyklus (bis 10 ms) nur Status statt Code, und genau aus ihm holt der 8049 seine Befehle. Deshalb ein eigener SPI-Flash an Portpins, der per Software angesteuert wird.

**Hardware (Michael, aufgebaut):**
- IS25LP016D (2 MB, 3,3 V, SOIC-8 auf Adapter), Rest aus der Frankenstein-Bestellung.
- An den Port-1-Klemmen 1–4: P1.0 = CS#, P1.1 = SCK, P1.2 = SI, P1.3 = SO.
- Versorgung: 5 V → 56 Ω → Z-Diode 3V3, dazu 10 µF und 100 nF. Ausgelegt auf ~30 mA Querstrom, weil der Flash beim Löschen bis ~25 mA zieht.
- CS#, SCK und SI über je 4,7 kΩ. Die Schutzdioden des Flash leiten den Überschuss ab, die Z-Diode nimmt den Strom auf (ein Regler könnte das nicht).
- SO über 1,5 kΩ zum 8049, denn 3,3 V gelten am TTL-Eingang sicher als 1.
- WP# und HOLD# an 3,3 V.

**A12 per Software (Bank-Switching):** Der Flash-Code (~620 Byte) passte nicht mehr in die oberen 2 KB, dort waren nur noch ~290 Byte frei.
- Der 8049 adressiert nur 4 KB, die höchste Leitung beim Code-Holen ist A11 auf P23. Deshalb treibt jetzt **P1.4 die Leitung A12**.
- Umbau: Leiterbahn an Pin 31 zur Klemme 5 aufgetrennt, CPU-Seite an JP3 Mitte, Jumper ab. Das ist das Gegenstück zur Drahtbrücke A11 → P23 an JP2 vom 2026-11-11.
- P24 ging nicht: P24–P27 schalten die 8155 und werden vom Interrupt alle 2,56 ms umgeschaltet.
- Michaels Wunsch: Klemme 7 (P1.6) bleibt frei, er führt sie auf den CAS-Header.

**Aufteilung des EEPROMs:**
- Hälfte A (A12 = 1, EEPROM 0x1000–0x1FFF, nach Reset aktiv) enthält die bisherigen Erweiterungen.
- Hälfte B (EEPROM 0x0000–0x0FFF) enthält den Flash-Code, ~960 Byte sind dort noch frei.
- Die unteren 2 KB sind in beiden Hälften gleich. Ein Interrupt kann jederzeit kommen, und Hälfte B ruft Original-Routinen auf. Effektiv sind es also 6 KB.
- Umgeschaltet wird in Stummeln ab 0xFBB, die in beiden Hälften dieselben Bytes haben: `ANL/ORL P1,#$10`, `NOP`, `JMP ziel`. Das `NOP` fängt einen um einen Befehl verspäteten Wechsel ab.
- `pruef4.py` stellt sicher, dass Code nur über diese Stummel zwischen den Hälften springt.
- `OUT P1A` (Einsprung `s_p1aus`) hält P1.0–P1.4 und P1.7 auf 1. Ein Programm kann also weder den Flash anwählen noch die Hälfte wechseln.
- Spätere Erweiterung ohne neue Platine: AT28C256 in denselben Sockel. Pin 1 (A14) und Pin 26 (A13) sind auf der Platine frei; A13 → P1.5, A14 → GND.

**Speicherformat:**
- 256 Bänke à 256 Zellen (512 Byte). Bank b belegt die beiden 4-KB-Sektoren ab b · 8 KB im Wechsel.
- Im Sektor: 0x000–0x1FF Zellen, 0x200–0x20F Name (16 ASCII, FF = keiner), 0x210 Generation, 0x211 = 00 gültig.
- **Warum zwei Sektoren:** Ein Flash setzt Bits nur durch Löschen ganzer 4-KB-Sektoren wieder auf 1. Ein FWR mitten in einer Bank würde sonst den Rest löschen, und zum Puffern ist das RAM des CP1 zu klein (es ist genau eine Bank groß).
- Ablauf beim Schreiben:
  - den freien Sektor löschen,
  - den alten Inhalt in 8-Byte-Stücken hinüberkopieren und dabei die neuen Bytes einsetzen,
  - die Generation auf alt + 1 setzen,
  - zuletzt 0x211 = 00 schreiben.
- Ein Stromausfall mittendrin lässt die alte Fassung gültig. Sind beide Sektoren gültig, gewinnt der, dessen Generation um 1 höher ist.
- **Bank 0 = Verzeichnis:** Zelle 0 = (00, Autoboot-Bank), Zelle n = (00, Startadresse von Bank n). Der Bereich ist mit FRD lesbar, FWR darauf gibt F-003.
- Dauer: Schreiben ~0,6 s, Speichern mit Verzeichnis-Eintrag ~1,3 s, 256 Zellen lesen ~0,2 s.

**Bedienung (immer 3 Ziffern):**
- `nnn CAS`: RAM nach Bank nnn sichern, Start = PC. Anzeige `5to nnn`, danach `5to rdY`.
- `nnn CAL`: Bank laden, PC = Start (`LdA nnn`, dann `P xxx`).
- `nnn` + CAL 1 s halten: Autoboot (`bot rdY`), `000` schaltet ihn aus.
- Beim Einschalten nach der Version: `bot nnn` für 2 s, jede Taste bricht ab, sonst wird geladen und gestartet. Den Abbruch prüft die Firmware alle 10 ms über die Tastenzustände 0x30–0x35, denn R6' hält eine Taste nur ~15 ms.
- Fehler: F-010 kein Flash (JEDEC-Hersteller 00/FF), F-011 Bank leer, F-003, F-001.

**Befehle:**
- `36 PSK xxx`: Konstante auf den gemeinsamen Stapel von JSR/PSH (Michaels Wahl statt `PSH xxx`).
- `37 FRD xxx` / `38 FWR xxx`: holen Anzahl (0 = 256), erste Zelle in der Bank und Bank vom Stapel und lesen bzw. schreiben ab RAM-Zelle xxx.
- Prüfungen: weniger als 3 Werte → F-009, Bereich über 255 bzw. MEM_SIZE → F-003.

**Fernsteuerung:**
- Neuer Befehl `03 aa ww` = internes RAM schreiben. Er brauchte 9 + 6 Byte in den unteren 2 KB und nutzt das Quittungsende von rb_taste mit.
- Flash-Arbeit dauert zu lange für den Interrupt. Darum legt der Pi stattdessen einen Auftrag ab: Parameter F_BANK 0x2C, F_SEKT 0x2D, F_OFH/F_OFL 0x2E/0x2F, Name 0x60–0x6F, zuletzt F_JOB 0x26. Dann drückt er ferngesteuert CAL.
- Aufträge: $01 16 Byte roh lesen, $81 speichern mit Name, $04 laden, $08 Autoboot, $10 nächste belegte Bank suchen (seit 4.01, damit das Verzeichnis nicht 255 Einzelabfragen braucht).
- Das geht nur, wenn kein Programm läuft. Webseite: Bereich „Flash“. CLI: `kosmos_remote.py flash | flash-speichern | flash-laden | autoboot`.

**RAM-Belegung:**
- F_JOB 0x26, F_BANK/F_SEKT/F_OFH/F_OFL 0x2C–0x2F (bisher frei).
- F_ANF/F_ANZ/F_RAM 0x3C–0x3E (atoi-Puffer, nur kurz genutzt).
- Name 0x60–0x6F und Puffer 0x70–0x77 (S_-Variablen, nur kurz genutzt).
- R6 als alter Sektor.
- Stapeltiefe höchstens 6 von 8 (der Simulator meldet einen Überlauf).

**Simulator:** `sim48.py` kennt jetzt das 8-KB-Abbild mit A12 = P1.4 (auch für MOVP/JMPP) und ein SPI-Flash-Modell. Das Modell kennt 9F, 05, 06, 03, 02 und 20, prüft WREN, programmiert per UND, löscht 4-KB-Sektoren und meldet beim Programmieren und Löschen kurz „beschäftigt“.

**Tests (alle grün):**
- `test_flash.py`: FRD/FWR, Teilbereiche, Sektorwechsel, Fehler, Tasten, Autoboot mit Abbruch, Aufträge, Bänke suchen, P1-Schutz.
- `test_rc4.py`: 03 und ein Auftrag über die simulierte Leitung.
- `test_remote_flash.py`: die Pi-Logik gegen den Simulator.
- Dazu die bisherigen Reihen test_befehle, test_schnell, test_rc und test_pi.

**Lehren:**
- spi benutzt R4/R5. Die Betriebsart nach f_zustand in R5 zu halten machte aus FRD ein FWR, das Nullen schrieb. Jetzt steckt sie in F_JOB Bit 7.
- `clear_display` benutzt R2.
- Ein Testfall hat getippt, während `bot` lief. Die erste Taste brach den Autoboot korrekt ab, und es fehlte eine Ziffer.

**Am Gerät:** 4.00 läuft (Michael: „WIE GEIL! Es funktioniert!“). 4.01 (Suchauftrag) läuft ebenfalls, die Webseite mit Flash-Bereich klappte am Gerät auf Anhieb (Michael, 2026-11-13: „Funktioniert super! Auf Anhieb!“).

**Dateien:**
- Quellen in `firmware/history/flash4/`. Gebaut wird mit `AUS=… python3 flash4/build4.py` aus `cp1.asm` (nicht im Repo) plus `schnell4.asm` (= schnell.asm ohne Seiten-`.org`, eingepasst durch den neuen `.seite`-Automatismus in build4.py/asm48.py), `stummel_a/b.asm` und `flash.asm`.
- Abbilder nur auf Michaels Rechnern und Michaels Werkbank-Rechner: `cp1-eeprom-v4.00.bin` 7ec4b2ee…, `cp1-eeprom-v4.01.bin` b4aa3688…
- EEPROMs: das frühere v3.04-Exemplar trägt 4.00, das frühere v3.05-Exemplar 4.01. Mit dem A12-Draht laufen nur noch 4.x-Abbilder sicher (ältere fassen P1.4 bei `OUT P1A` an).
- Toolchain: f93cf8e (PSK/FRD/FWR, Flash auf Webseite/CLI, README), lokal auf bastelpi, Push nach Gerätetest und Michaels OK.

**Lauftext-Beispiel und Su-Err-Fix (2026-11-13):** Bank 2 = `beispiele/lauftext.koa` (24 Zellen), Bank 3 = `beispiele/lauftext-text.json` (Text als Segmentmuster); das Programm holt je 6 Zeichen mit FRD und zeigt sie mit SEG. Dabei fiel Michaels Beobachtung „beim ersten Mal oft Su Err“ auf: `laden` drückte CAL und gab die Leitung 0,3 s frei; eine Statusabfrage der Live-Anzeige (3,5 ms low) wirkte auf den wartenden CP1 wie ein kaputtes erstes Bit. Mein erster Versuch speicherte deshalb unbemerkt den RAM-Inhalt (Rakete) als Bank 3 – korrigiert und per Rücklesen geprüft. Fix (Toolchain 52a09ad): RLock, Leitung von CAL/CAS bis zum Ende belegt, `laden` prüft `rdY` und versucht es bis zu dreimal, sonst Fehler.

**Firmware 4.02 und Spiel „Asteroiden“ (2026-11-13/14):** Michaels Spielidee: Asteroiden `o` (unten, 92) oder `°` (oben, 99) fliegen von links auf das Schiff an Stelle 6, das mit 8/2 zwischen oben `‾` (1), Mitte `-` (64) und unten `_` (8) wechselt. Mitte wird immer getroffen, oben überlebt `o`, unten überlebt `°`. Die Segmentbilder passen dazu: beide Asteroiden enthalten g, `o` enthält d, `°` enthält a. Rechnerisch: sicher genau dann, wenn Schiff + 2 · Zeile = 2.
- **39 TSE 000** (neu): Akku = Ziffer der seit dem letzten TSE gedrückten Taste, sonst 255; wartet nicht. Nötig, weil der Interrupt eine neue Taste nur ~15 ms in R6' meldet. Deshalb merkt sich **VZG** (jetzt in Hälfte A, Einsprung über 3 Byte am Anfang von opcode_VZG) bei jedem 1-ms-Schritt neue Ziffern in RAM 0x44 und löscht R6', damit nichts doppelt zählt. Die Schleife ist auf 413 Zyklen abgezählt: gemessen 1,1374 ms je Schritt gegenüber 1,1347 ms im Original (beide mit Interrupt). INP nimmt jetzt Befehle bis 39 an.
- Tests: `flash4/test_tse.py` und alle bisherigen Reihen grün. Abbild `cp1-eeprom-v4.02.bin` cc0409be…, gebrannt auf das frühere 4.00-Exemplar; 4.01 ist Rückfallebene.
- Spiel: `beispiele/asteroid.koa` (176 Zellen, braucht CP3) = Bank 6 „Asteroiden“. Bank 4 hält Rekord (Zelle 0) und Zufallswert (Zelle 1, LCG x · 5 + 3, oberes Bit = Zeile) über das Ausschalten hinweg; FWR nach jedem Crash. Das Tempo steigt pro Ausweicher von 25 auf 8 · 10 ms je Schritt. Im Simulator überlebte ein automatischer Spieler 60 s, ohne Eingriff kracht es am ersten Asteroiden. Am Gerät läuft es (Michael spielte schon, Anzeige `Pu 001`).

## Trennpunkt, Firmware 4.03 (2026-11-14)

**Hardware (Michael):** Im Schaltplan lag der DP-Pin der Anzeigen auf Masse, und am 8155-Port A hing an PA7 die Überspannungsanzeige (BC238C mit Z12). Michael hat die Masse-Leiterbahn zum DP aufgetrennt, alle DP-Pins verbunden, Z12 entfernt und den Transistor über seinen 1 kΩ an **PA7 = 8155 Pin 28** gelegt. Der CP1-Schaltplan nennt hier Pin 20, das ist falsch (Michael: „lass pa7“).

**Firmware:** Der Interrupt schreibt das ganze VRAM-Byte auf Port A, Bit 7 ist also der Punkt der jeweiligen Stelle. Der Trennpunkt soll nur im Normalbetrieb leuchten, nicht bei SEG, ANZ oder AS1–AS3. Deshalb setzt ihn `dp_warte` in `wait_key` (statt `MOV R0,#$1e`, im toten NEG-Rest 0x4AC): Bit 7 in VRAM 0x22 (Stelle 3) setzen. Programme schreiben ihre Anzeige selbst und sehen ihn nicht.
- 4.03 (9a683ad3…) war gebrannt. Beim Tippen schob die Original-Ziffernschiebung Bit 7 von 0x22 nach 0x21, und es leuchteten zwei Punkte (Michael). Fix: `dp_warte` löscht auch Bit 7 von 0x21. Dieser Stand steckt als 4.04 (a318ac12…) in `flash4/build4.py` und war nie im Gerät; der Fix ging direkt in 5.00 ein.

## Firmware 5.00/5.01: Flash-Tasten, NIE und FNI (2026-11-14)

Plan mit Michael abgestimmt (Claude-Doc https://claude.ai/artifact/HyhqoycXaXoaXhEcyQzBw6, Abschnitt „Stand“ = was beim Bauen anders wurde). Michaels Vorgaben: „erst reden, nix bauen“, dann „alles so machen“.

**Bedienung am Gerät:** CAS/CAL bedienen den Flash, die schnelle Kassette ist raus.
- CAS kurz `bAn ___` → ganzes RAM in die Bank, Start = PC (`5to rdY`). CAS lang (1 s): `Fr`, `to`, `bAn`, `d5t` (Ziel in der Bank); Verzeichnis bleibt.
- CAL kurz `bAn ___` → Bank laden, PC = Start. CAL lang: `bAn`, `Fr`, `to`, `d5t` (Ziel im RAM), PC bleibt (`LdA rdY`).
- RUN lang: `bot ___` = Autoboot (000 = aus). RUN kurz wie im Original. Fernsteuerung ist immer an (RC_FLAG = 1 beim Start).
- Version beim Einschalten `5.01`; Demos 8/9 RUN liegen jetzt in Hälfte A.

**Zwei Übertragungsarten (Michaels Namen):**
- **NIE** (normal, interrupt enabled), Klemme 8: im Timer-Interrupt, unbemerkt, auch bei laufendem Programm. Bits jetzt 50/150 µs statt 150/750 µs (Schwelle 5 × 20 µs, `ADD A,#$fb`; Antworten Zähler 6/19/6). Michaels Frage, ob NIE konservativer codiert sein müsse: nein, die zeitkritische Seite läuft im CP1-Interrupt, den nichts unterbricht; Pi-Jitter fangen Prüfbyte und Wiederholung.
  - `01` Taste, `02`/`03` 8049-RAM lesen/schreiben, `04 jj 00` Auftrag (Attention statt des alten CAL-Tricks), `05`/`06 aa nn` Bytes der internen/CP3-8155 lesen, `07`/`08 aa ww` ein Byte schreiben (Zelle z = Byte 2z, 2z+1).
  - Annahme von `04` nur im Leerlauf: `wait_key` setzt LEER (0x16), die Abfragen löschen es. Der Interrupt legt den CAL-Code in AUFTRAG (0x17), den `wait_key` wie eine Taste liefert. **Warum zwei eigene Bytes:** ein Merkbit in RC_FLAG gab einen Lese-Schreib-Wettlauf zwischen Hauptprogramm und Interrupt. 0x16/0x17 ist die 8. Stapelebene, die nachweislich nie belegt wird (höchstens 7 von 8, `review/tiefe.py`). Läuft ein Programm, wird abgelehnt (Michael: „ablehnen. wenn ein programm läuft dann dauert das“).
- **FNI** (fast, no interrupt): ganze Bänke oder Teile, 8155 oder Flash. Interrupt aus, Anzeige rechts `Q-Z` aus C (CP1-RAM), P (Pi), F (Flash), etwa 66 Hz eigener Anzeige-Durchlauf. I²C-artig: **T = Klemme 7 (P1.6, Pin 35 = BCM 19)** als Takt, **D = Klemme 8 (P1.7, Pin 37 = BCM 26)**.
  - Der Pi zieht T ≥ 40 µs low, der CP1 hält T fest, solange er beschäftigt ist (Flash löschen), danach T ≥ 40 µs high. D low = 0, LSB zuerst.
  - Kopf [jj, Bank, Anfang, Anzahl] + CRC-8 ($07), dann Blöcke an 4-Zellen-Grenzen + CRC-8, nach jedem Block ein Quittungsbit des Empfängers (1 gut, 0 wiederholen), 3 Versuche. Ergebnis in F_JOB: 0 ok, $EE Fehler.
  - Aufträge: $20 Pi → 8155, $21 8155 → Pi, $22/$23 Pi → Flash (mit Name), $24 Flash → Pi, **$25** Bank komplett mit Bankkopf, **$26** alle Namen (5.01). Annahme eines FNI-Auftrags = „T geht low“ (die `04`-Antwort ginge beim Umschalten verloren).
  - Verzeichnis = `$24` von Bank 0 + `$26`: ein FNI-Durchgang. Michael wollte „die zig aufträge weg haben, da jeder einzelne das display zucken lässt“.
- **Klemme 7 umgebaut (Michael):** wie Klemme 8, GPIO-Knoten mit Z-Diode 3V3 nach GND und 1 kΩ zur Klemme (vorher 1 kΩ + 1N4148 nur Richtung CP1). Beide Seiten ziehen nur low. `OUT P1A` hält jetzt P1.0–P1.4, P1.6 und P1.7 auf 1, Programmen bleibt Klemme 6.

**Speicher:** Die Hälften liefen beim Bauen über. Abhilfe: Lückenfüller `packer.py` (verschiebt Absätze, die mit einer Marke beginnen und unbedingt enden und nur innere bedingte Sprünge haben, in Seitenlücken; Sicherheitsprüfung: kein `.seite` nach durchfallendem Code), FNI-Bits in die Byte-Schleifen eingebettet (sonst Stapel 8/8). Prüfwerkzeuge in `v5/review/` (Ablauf, Stapeltiefe, Ketten, Zyklen). Lehre: bei bedingten Sprüngen gilt die Seite des Operandenbytes (pc + 1); asm48 und sim48 konnten das schon, der Ablaufverfolger nicht.

**Am Gerät:** 5.00 (43bc93f4…) auf das frühere 4.02-Exemplar gebrannt, lief: Webseite, FNI laden/speichern, Tasten (Michael: „sonst alles bestens“). Gemessen: Klemme 7 in beide Richtungen ok. **5.01** (8dc4cd1b…) auf das frühere 4.03-Exemplar, seit dem Abend im CP1; 5.00 ist Rückfall. Verzeichnis per FNI 3,4 s, Bank komplett, `kosmos_send/recv` je ~4 s (davon ~2 s Python-Start auf dem Pi Zero), Rücklesen byte-gleich.

**Pi-Seite (`fernsteuerung/`):** `kosmos_rc` (C) macht NIE und FNI (`F <E|A|K|N> anf anz kopf [daten]`). `kosmos_remote.py`: Aufträge über `03` + `04`, `fni()`, Zellen per NIE, Bank sichern/einspielen, CLI `zelle`, `bank-sichern`, `bank-einspielen`. Webseite: Sichern pro Bank, JSON direkt in eine Bank, Zellen-Panel (lesen/ändern, „mitlaufen“). `kosmos_send.py`/`kosmos_recv.py` gehen standardmäßig über FNI (`--kassette` alte Kassette, `--schnell` Firmware 3.05–4.x).
- Fehler beim ersten Komplettdump am Gerät: Ein Block scheiterte, der Pi startete neu, während der CP1 noch im FNI wiederholte, und las danach das alte $EE als „abgelehnt“. Fix: F_JOB vor jedem Versuch auf 0, nach einem Fehler warten, bis der CP1 wieder per NIE antwortet.

**Tests (`v5/alle_tests.sh`, alle grün):** test_befehle, test_tse, test_ui5 (Tasten), test_nie5 (NIE inkl. Stapeltiefe, Zittern, Ablehnung), test_fni (FNI mit Pi-Modell `pi_fni.py`, Störungen, Abbruch), test_flash5 (FRD/FWR, Sektorwechsel, Aufträge mit Interrupt, P1-Schutz), test_remote5 (kosmos_remote.py gegen den Simulator). Die 4.x-Reihen für Kassette und alte Fernsteuerung sind mit 5.x überholt (liegen in `flash4/`).

**Dateien:** Quellen `firmware/v5/`, gebaut mit `python3 v5/build5.py` aus `cp1.asm` (nicht im Repo, Copyright). Abbilder nur auf Michaels Rechnern und Michaels Werkbank-Rechner. Toolchain-Commit auf bastelpi folgt, **Push erst nach Michaels OK**.

## Reset, Firmware 5.02 (2026-11-14)

Michaels Wunsch: ein Reset, nach dem „alles weg ist, was beim Einschalten auch weg ist (also alles RAM)“, dazu ein Hotkey „analog Strg-Alt-Entf“.
- **Am Gerät: CLR halten, dann STP.** In der Sprungtabelle zeigt STP auf die drei bisher freien NOPs hinter dem `RETR` an 0x003 (`SEL MB1`, `JMP s_stp`). `s_stp` in Hälfte A prüft den Tastenzustand der Reihe CAS/CLR/PC/ACC (RAM 0x35 = 18 heißt CLR gedrückt) und springt zum Kaltstart, sonst wie bisher nach `wait_key`. Das geht immer: Bei laufendem Programm hält STP es an und landet in `wait_key`. Der Interrupt merkt sich je Tastaturreihe nur eine Taste, deshalb müssen die Tasten in verschiedenen Reihen liegen (CAS + STP löst nichts aus).
- **Vom Pi: NIE `09 00 00`**, auch bei laufendem Programm (Webseite „Reset“, `kosmos_remote.py reset`). Im Interrupt: `DIS TCNTI`, `CALL $003` (das `RETR` beendet den Interrupt, sonst käme nie wieder einer), `ORL P1,#$FF` (Hälfte A, Leitungen wie nach Reset), `SEL MB1`, `JMP kaltstart`. 8 Byte in der Lücke 0x4B2, der Verteiler wuchs um 6 Byte (Lücke 0x6AD).
- **kaltstart:** Timer aus, PSW = 0 (Stapel leer, RB0), F0/F1 aus, internes RAM 0x01–0x7F = 0, P2 = FF, `JMP 0`. Das Original-`init` löscht dann beide 8155 (`clear_ram`), es folgen Version und Autoboot wie beim Einschalten.
- **Warum Software:** Ein Hardware-Reset (GPIO an RESET, Pin 4) hätte das 8155-RAM nicht gelöscht; das tut erst `init`.
- Tests: `v5/test_reset.py` (Leerlauf, Endlosprogramm mit JSR, mitten in `bAn ___`, Autoboot, falsches Prüfbyte, CLR+STP, Gegenproben STP/CLR/CAS+STP allein), `test_remote5.py` mit `reset()`.
- Am Gerät: 5.02 (fc9a6fa8…) auf das frühere 5.00-Exemplar gebrannt, 5.01 ist Rückfall. Reset vom Pi getestet: `5.02`, danach Autoboot Bank 2 (Lauftext). Toolchain-Commit 02322ef lokal, Push nach Michaels OK.

## Editor mit Namen, Firmware 5.03/5.04 (2026-11-14 nachts)

Michaels Wünsche: der Disassembler soll hinter jedem Label die Zeilennummer zeigen, die Webseite **ein** Code-Fenster zum Holen, Ändern und Zurückspielen haben, und sprechende Labels/Werte sollen über eine Zuweisungstabelle („035=display_loop“) kommen, die beim Schreiben in die Flashbank im freien Bereich mitgespeichert wird. Zu Zeilennummern: „keinen Konflikt, sondern ein Relabeln … es geht nur darum, dass man sieht, wo was landet.“ 40 Namen fand er knapp, 1 s längeres Schreiben „kein Problem“.

**Pi-Seite:**
- `kosmos_disasm.php -n namen.txt`: Namen statt `label_N`/`wert_N`, jede benannte Zelle bekommt eine Marke. Jede Markenzeile zeigt ihre Zelle (`>display_loop:  035`).
- `kosmos_asm.php`: ignoriert den Rest der Markenzeile wie bisher, setzt in der Ausgabe (und mit `-r`) die aktuelle Nummer ein; mehrere Marken an einer Zelle gehen jetzt (vorher ging die erste verloren). Alle Beispielprogramme übersetzen byte-gleich wie vorher.
- Webseite: ein Editor + Namensfenster. Holen aus dem CP1, aus einer Bank („In Editor“) oder Datei; „Assemblieren“ setzt die Nummern neu und baut die Tabelle aus den Marken (plus Handeinträge ohne Marke); „In CP1 laden“, „Editor speichern“ (direkt in die Bank, RAM bleibt), .koa (Namen als `// 035=name`) und .json. Entwurf bleibt im Browser (localStorage).

**Firmware 5.03:**
- Namensbereich 0x300–0x5FF jedes Bank-Sektors (768 Byte, je Eintrag Länge, Zelle, Name; FF = Ende; ~70 Namen à 8 Zeichen). Byte 0x212 = 00 markiert eine Bank mit Namen; nur dann kopiert das Schreiben bis 0x5FF (~1,7 s länger), sonst wie bisher bis 0x217 (Bänke ohne Namen genauso schnell wie 5.02). Ein CAS am Gerät behält die Namen.
- FNI `$29` = `$23` + Namensbereich (nach den Zellen 96 Blöcke à 8); `$25` liefert jetzt 0x200–0x5FF (128 Blöcke à 8).
- Platz: Hälfte B war 35 Byte zu voll. Dafür entfallen die Aufträge `$01` (16 Byte roh) und `$10` (Bank suchen), seit das Verzeichnis per FNI kommt; die 2-s-Warteschleife des Autoboots (`bot nnn`) liegt jetzt in Hälfte A (neuer Stummel `boot_warte`, Stummel ab 0xFB6; build5.py liest den Anfang aus stummel_a.asm). `$29` statt `$27`, weil dann `ANL A,#$09` das Namens-Bit 3 ohne Zusatzbefehl mitnimmt. Der Namensbereich beginnt bei 0x300 statt 0x220, das spart die 16-Bit-Vergleiche.
- Vorsicht: Unter 5.02 würde `$29` als Autoboot-Auftrag (Bit 3) laufen. Pi-Software nur zusammen mit ≥ 5.03.

**Firmware 5.04 – Einschaltfehler (seit 5.00):** Michael sah nach der Versionsanzeige oft `F 004` oder eine „zufällige 2“, der Kaltstart (CLR+STP) lief sauber. Ursache: Beim Einschalten ist das interne RAM des 8049 zufällig, `init` löscht nur 0x20–0x47. Steht in AUFTRAG (0x17) etwas, liefert `wait_key` das als Tastencode → Ziffern, F 001/F 004, Sprünge ins Leere. Fix: `s_boot` löscht 0x16/0x17 und 0x48–0x7F. Der Simulator startete immer mit Nullen; neu `test_einschalten.py` mit Zufalls-RAM (5.03: 22 von 40 Starts kaputt, 5.04: 0).

**FNI-Timing am Gerät (Lehre):** Ganze Bänke mit Namen brachen am Gerät oft mit `P-F.Err` ab, im Simulator nie. Der CP1 läuft mit 6 MHz (Zyklus 2,5 µs, ALE 400 kHz) und fragt T in `t_takt` nur alle 6 Zyklen = 15 µs ab; bis er T festhält, können ~30 µs vergehen. (Hier stand bis 2026-11-17 „4 MHz, 3,75 µs, 22,5/45 µs“ – falsch gerechnet; Michael hat 6 MHz und ALE 400 kHz gemessen. Die Folgerung bleibt: 40 µs waren zu knapp.) Mit T low 40 µs las der Pi D manchmal, bevor der CP1 es gesetzt hatte; mit T high 40 µs verpasste der CP1 manchmal das kurze High (die Leitung steigt nach dem Loslassen nur über den schwachen Pull-up des 8049) und lag dann ein Bit zurück. Der Pi versuchte außerdem 4×, der CP1 3× → nach dem Aufgeben des CP1 „raste“ der Pi ohne Gegenstelle durch und meldete OK; das Bitgewitter auf Klemme 8 schaltete danach per Notbremse die Fernsteuerung ab. Fix nur am Pi (`kosmos_rc.c`): T low 80 µs, T high 100 µs, 3 Versuche, Wiederholungen auf stderr (Journal). Danach 7× lesen und 4× schreiben mit bis zu 40 Namen ohne eine Wiederholung; ganze Bank ~5–6 s.
- Mein Zwischenversuch, im Takt zu prüfen, ob der CP1 T festhält, war falsch gedacht: in den Byte-Schleifen ist der CP1 oft schon fertig und lässt T für das nächste Bit los, während der Pi noch zieht. Die Prüfung brach jede Übertragung ab. Lehre: erst das Timing verstehen, dann eingreifen.

**Am Gerät:** 5.03 (dcb628fb…) auf das frühere 5.01-Exemplar, 5.04 (fd58cbc6…) auf das frühere 5.02-Exemplar; 5.04 im CP1, 5.03 Rückfall. Rakete (Bank 1) und Lauftext (Bank 2) haben sprechende Namen (Zellen unverändert, verglichen). Bank 7 „Namenstest“ ist Testbank. Toolchain-Commits bis 558561b lokal auf bastelpi, Push nach Michaels OK.

## Bänke durchblättern, Firmware 5.05 (2026-11-15)

Michaels Idee beim Spielen: zu jeder Bank eine 6-stellige CP1-Anzeige speichern, mit CAL durch die Bänke rotieren, lang drücken lädt. Entscheidungen: immer ab der niedrigsten belegten Bank, `bAn nnn` blitzt kurz auf, ohne eigene Anzeige der Name über eine Buchstabentabelle („die Tabelle kann man auch für andere Dinge brauchen“).
- **Bedienung:** CAL kurz → `bAn nnn` ~0,4 s, dann Anzeige oder Name; CAL kurz = nächste Bank (nach der letzten von vorn; dieser Schritt ~1,6 s, weil der CP1 alle Bänke dazwischen per SPI prüft, ~6 ms je Bank), CAL 1 s = laden, Ziffer = normale Eingabe `bAn __n` (die Ziffer wird in R6' zurückgelegt und von `bank_frage` wie frisch getippt gelesen), STP = Abbruch. Teilbereich (CAL lang aus dem Leerlauf) unverändert.
- **Ablage:** eigene Anzeige = 6 Segmentbytes bei 0x5F8–0x5FD (Ende des Namensbereichs, damit die schon gespeicherten Namenslisten gültig bleiben); FF = keine. Webseite: Feld „Anzeige“ mit Vorschau (leer = so, wie die Firmware den Namen zeigt).
- **asc_seg** (Hälfte A, mit `.seite` und MOVP-Tabelle 0x20..0x5F, Kleinbuchstaben wie große): ASCII → 7 Segmente, allgemein nutzbar.
- **Platz:** Banksuche + Lesen brauchte ~60 Byte in Hälfte B (23 frei). Die Kopfanzeigen (`5to/LdA/bot nnn`, früher `k_kopf` in B) zeigt jetzt Hälfte A, bevor sie nach B springt (`kopf_5to/lda/bot/ban`); Aufträge des Pi mit Interrupt gehen über `job_kopf` in A. Die Banksuche ist ein gemeinsames Unterprogramm `naechste_bank` (auch für `$26`). Stummel ab 0xFA7 (`bl_suche`, `job_kopf`, `bl_zeige` neu). Danach frei: A 144, B 52 Byte.
- **Fehler, den der Test fand:** `kopf_bank` merkte sich das erste Zeichen zuerst in S_SYM (0x6D) – das liegt in F_NAME, und `$81` (Speichern mit Name) bekam ein „m“ ins 14. Zeichen. Jetzt direkt in den Anzeigespeicher wie früher.
- Tests: `test_blaettern.py` neu, `test_ui5` angepasst; alle grün. Am Gerät: 5.05 (3e404bb0…) auf das frühere 5.03-Exemplar, 5.04 Rückfall; Blättern klappt (Michael).
- 2026-11-15: Toolchain bis 30d16c3 nach GitHub gepusht (Michaels OK), dazu `INTERNALS.md` (englisch, hier als `kosmos-cp1/INTERNALS.md`): K78P = Klemme-7-und-8-Protokoll (Michaels Name), NIE/FNI, Aufträge, Flash-Aufbau. Schnellübersicht `cheatsheet/` auf 5.05 (Seite 2 jetzt Flash über die Tasten, Seite 3 Flash im Programm + Pi + K78P). Laborbuch auf moosy.net (Rubrik Laborbücher, Buch „Kosmos CP1“).
- Michael hat 2× AT28C256 (32 KB) da. Einbau erst, wenn Platz gebraucht wird: A13 an P1.5 (Klemme 6, die letzte freie Klemme für Programme), A14 auf GND → 4 Hälften à 4 KB.

## Befehle mit festem Wert, Bilder, eigene Bank – Firmware 5.06/5.07 (2026-11-15)

Anlass: Michaels Spielidee „Minenflug“ (Schiff `°`/`o` mit 2/4/6/8, Minerale = Dezimalpunkte, Geschosse von der fernen Seite, LED-Balken Punkte an Port 2, Leben an Port 4, LOW-aktiv) passte mit 342 Zellen nicht in 256. Daraus wurden drei Firmware-Erweiterungen, alle auf Michaels Vorschlag oder mit seinem „go“.

**5.06 – Befehle 40–46 mit festem Wert** (Michaels Idee: „Varianten mit festem Wert, damit wir nicht so viele Zellen für Konstanten verbrutzeln“): `ADD # SUB # VGL # VGR # VKL # UND # ODR #` = Befehle 40–46, Assembler-Schreibweise `ADD #1`. Sie springen in die Original-Routinen hinter deren Zellenprüfung (`add_imm`, `vgl_imm`, `vgr_imm`, `vkl_imm` – nur Marken in cp1.asm, keine Bytes geändert); dort liest `MOVX A,@R1` dann das Argument des Befehls selbst. OVF, Vergleichsergebnis und F 005 wie bei den Zellen-Varianten. `test_imm.py`: 105 Vergleichsfälle, 40 Zufallsfälle gegen die Zellen-Variante.

**5.06 – SEF xxx (47), Bilder aus dem Flash** (Michaels Idee, erst mit fester Bilderbank 255; auf seine Frage „wenn mehrere Programme Bank 255 nutzen, kommen sie sich in die Quere“ dann so): Bilder liegen im Sektor der **eigenen** Bank (0x500–0x5F7, von oben, die Namen wachsen von unten dagegen), nicht in den 256 Zellen. Die Firmware merkt sich beim Laden einer Bank deren Nummer in S_PBANK = 0x5F (dafür hat der JSR/PSH-Stapel 23 statt 24 Ebenen). SEF xxx liest 6 Byte ab 0x500 + xxx, ~12 ms. `SEF 254` = Position aus dem Akku (Lauftext-Schleife – ohne das wäre mein Versprechen „Lauftexte geschenkt“ falsch gewesen, das Argument ist fest), `SEF 248` = eigene Blätter-Anzeige, `SEF 255` löscht, ohne eigene Bank dunkel. Webseite: Feld „Bilder“ (`titel=MInEn`, `#1,2,3`), Assembler löst `SEF titel`, `SEF lauf+3`, `ADD #lauf` auf, Bilder stehen als `@name`-Einträge in der Namensliste und kommen mit „In Editor“ zurück.

**5.07 – FRD/FWR mit Bank 000 = eigene Bank** (Michaels Beobachtung: „sehr viele Zellen, um Speicherstellen zu initialisieren – kann man die nicht aus der Bank neu laden?“): `PSK 0 / PSK erste / PSK n / FRD erste` lädt alle Startwerte zurück (Minenflug: 4 statt 18 Zellen). FWR in die eigene Bank kopiert den ganzen Sektor (mit Namen und Bildern, im Simulator einige Sekunden) – für Rekorde am Spielende. Ohne eigene Bank F 003 (FRD auf Bank 0 las vorher das Verzeichnis).

**Platz:** Hälfte A lief mehrfach über, obwohl rechnerisch genug frei war – der Lückenfüller verschiebt nur Absätze, deren bedingte Sprünge in ihnen bleiben, und die Seite ab 0xF00 (MOVP-Tabelle der AS-Befehle) ließ davor 70 Byte ungenutzt. Abhilfen: `s_imm` in kleine Absätze geteilt, POP mit eigenem Sprung (verschiebbar), ASCII-Tabelle der Blätter-Anzeige erst ab „,“ (spart 14 Byte; `( ) " ' $` bleiben dunkel), Bank-0-Prüfung von SEF nach Hälfte A. **Fehler im Bauskript gefunden:** lief Hälfte A über 0xFFF hinaus, landete der Rest still außerhalb des EEPROMs (Prüfung sah nur bis 0xFFF) – ein Build wäre beinahe „fertig“ gewesen, ohne AS/JSR/PSH/VZG. `build5.py` prüft jetzt bis 0x17FF; 5.05 war nicht betroffen (nachgeprüft). Frei danach: A 39, B 16 Byte.

**Minenflug** (Bank 8, `examples/minenflug.koa` im Toolchain-Repo): 254 Zellen, Bilder `titel`/`explo`/`ende`, Start/Neustart per `PSK 0 … FRD`, beim Crash blinken die Punkte-LEDs dreimal (Michael: „da sind auch Relais dran, das klickt so schön“) und die Punkte bis zum Extraleben sind weg. Tempo ¼ s pro Stelle, schneller je Extraleben bis Untergrenze. Im Simulator mit einem Bot gespielt (Ausweichen, Sammeln, LEDs, Neustart, Stapel sauber). Michael: „das macht so viel Spaß, Schwierigkeitsgrad genau richtig“. Bank 4 heißt jetzt „Asteroiden Daten“ (Rekord von Asteroiden; Minenflug sollte erst dorthin – hätte den Rekord zerschossen).

**Am Gerät:** 5.06 (7bc4d312…) auf das frühere 5.04-Exemplar, 5.07 (bd35a143…) auf das frühere 5.05-Exemplar; 5.07 im CP1, 5.06 Rückfall. Alle 13 Testreihen grün (neu: test_imm, test_sef, test_bilder). Michaels nächste Idee (später): Overlays – nur die aktuelle Schleife im RAM, Spielteile per FRD nachladen; dafür wäre „eigene Bank + n“ praktisch.
