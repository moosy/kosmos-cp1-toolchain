# Inhalt des Cheat Sheets für Firmware 6.20 (28C256) (wird von satz.py ausgeführt). Anzeigen im Raster "X YY ZZZ" wie am Gerät (8 88 888).

def seite1(s):
    s.titel('Kosmos CP1 · Schnellübersicht', 'Firmware 6.20 · Stand 17.11.2026')
    s.absatz('Firmware 6.20 auf dem AT28C256 im EA-Adapter (beim Einschalten 1 s `  6.20 `). Neu oder geändert: ★')
    s.balken('Funktionstasten')
    s.tabelle([17, 0], [
        ['**RUN**', 'Programmlauf starten (★ beim Loslassen). ★ **1 s halten:** Autoboot-Projekt wählen (`bot __`, Seite 2).'],
        ['**STP**', 'Programmlauf stoppen, Inhalt von Zelle 000 wird angezeigt. ★ **CLR halten + STP:** Reset.'],
        ['**STEP**', 'Einzelschritt: ein Befehl wird ausgeführt.'],
        ['**ACC · CLR**', 'Akku-Inhalt anzeigen · Anzeige löschen.'],
        ['**PC**', 'Programmzähler anzeigen; drei Ziffern + PC stellt ihn ein.'],
        ['**OUT**', 'Drei Ziffern + OUT: Zelle anwählen und anzeigen; weiteres OUT zeigt die nächste.'],
        ['**INP**', 'Fünf Ziffern + INP: Zelleninhalt eingeben. ★ Befehle bis 47 erlaubt (Original: bis 24); 48 JOV und 49 ZUF nur über den Pi.'],
        ['**9 OUT**', 'Stand des Ein-/Ausgabezeigers anzeigen (`C   nnn`).'],
        ['★ **CAS/CAL**', 'Speicher in ein Projekt im Flash sichern · Projekte durchblättern und laden (Seite 2). Ersetzt die Kassette.'],
    ])
    s.balken('Befehlsliste')
    s.tabelle([13, 22, 0], [
        ['HLT', '01.000', 'Halt.'],
        ['ANZ', '02.000', 'Akku-Inhalt anzeigen.'],
        ['★ ANZ', '02.001', 'Akku mit Vorzeichen: 0–127 wie bisher, 128–255 als `A  - 128` … `A  - 001`.'],
        ['VZG', '03.xxx', 'Verzögern um xxx Millisekunden.'],
        ['AKO', '04.xxx', 'Konstante xxx in den Akku laden.'],
        ['LDA', '05.xxx', 'Inhalt von Zelle xxx in den Akku laden.'],
        ['ABS', '06.xxx', 'Akku-Inhalt in Zelle xxx speichern.'],
        ['ADD', '07.xxx', 'Inhalt von Zelle xxx zum Akku addieren. ★ Mit OVF 000 ohne F 006: 255 + 1 = 0.'],
        ['SUB', '08.xxx', 'Inhalt von Zelle xxx vom Akku abziehen. ★ Mit OVF 000 ohne F 006: 0 − 1 = 255.'],
        ['SPU', '09.xxx', 'Unbedingt auf Adresse xxx springen.'],
        ['VGL', '10.xxx', 'Prüfen, ob Akku gleich Inhalt von Zelle xxx.'],
        ['SPB', '11.xxx', 'Bedingt auf Adresse xxx springen.'],
        ['VGR', '12.xxx', 'Prüfen, ob Akku größer als Inhalt von Zelle xxx.'],
        ['VKL', '13.xxx', 'Prüfen, ob Akku kleiner als Inhalt von Zelle xxx.'],
        ['★ NEG', '14.xxx', 'Akku bitweise XOR xxx. **NEG 000 wirkt wie NEG 001** (0 ↔ 1 wie im Original). 197 NEG 255 = 058.'],
        ['★ UND', '15.xxx', 'Akku bitweise UND Inhalt von Zelle xxx. 197 UND 060 = 004.'],
        ['P1E', '16.00x / .000', 'Klemme x von Port 1 (0/1) bzw. alle Klemmen als Dezimalzahl in den Akku.'],
        ['P1A', '17.00x / .000', '★ **Ohne Wirkung:** Port 1 gehört ganz der Firmware (Flash, EEPROM-Adressen A13/A14, Pi).'],
        ['P2A', '18.00x / .000', 'Wie P1A, für Port 2.'],
        ['LIA', '19.xxx', 'Akku indirekt laden (aus der Zelle, deren Adresse in xxx steht).'],
        ['AIS', '20.xxx', 'Akku indirekt speichern (in die Zelle, deren Adresse in xxx steht).'],
        ['SIU', '21.xxx', 'Indirekt unbedingt springen (auf die Adresse, die in xxx steht).'],
        ['P3E–P5A *', '22–24.00x', 'Wie P1E für Port 3 · wie P2A für Port 4 und 5 (Port 5 nur Klemmen 1–6, dezimal 000–063).'],
        ['★ ODR', '25.xxx', 'Akku bitweise ODER Inhalt von Zelle xxx. 197 ODR 060 = 253.'],
        ['★ OVF', '26.000 / .001', 'Überlauf aus (ADD/SUB modulo 256, kein F 006) / wieder an. Beim Einschalten an, RUN ändert nichts.'],
        ['★ SEG', '27.xxx', 'Zellen xxx … xxx+5 als Segmentmuster auf Stelle 1–6 (Werte S. 2). **SEG 255** löscht.'],
        ['★ AS', '28–30.xxx', '**AS1 / AS2 / AS3:** Hunderter / Zehner / Einer des Akkus als Segmentmuster in Zelle xxx (234: AS2 → 3).'],
        ['★ TST', '31.000', 'Auf eine Zifferntaste warten, Ziffer 0–9 in den Akku. STP hält an, RUN macht beim TST weiter.'],
        ['★ JSR', '32.xxx', 'Unterprogramm ab Adresse xxx aufrufen;  **RET 33.000** springt hinter das letzte JSR zurück.'],
        ['★ PSH', '34.000', 'Akku auf den Stapel legen;  **POP 35.000** holt den obersten Wert in den Akku.'],
        ['★ PSK', '36–39.xxx', '**PSK** Konstante auf den Stapel. **FRD/FWR** Flash ab RAM-Zelle xxx (S. 3). **TSE** Taste ohne Warten.'],
        ['★ JOV', '48.xxx', '**PSK k** / **PSK n** / **JOV z**: n Zellen ab z aus Bank k des Projekts nach z laden, dort weiter (Overlays, S. 3).'],
        ['★ ZUF', '49.xxx', 'Zufallszahl 0 … xxx−1 in den Akku (**ZUF 000**: 0–255). Zustand in der letzten Zelle (255 bzw. 127).'],
        ['★ #', '40–46.xxx', '**ADD # SUB # VGL # VGR # VKL # UND # ODR #**: fester Wert xxx statt Zelle, z. B. **ADD #1**.'],
        ['★ SEF', '47.xxx', 'Wie SEG, aber aus den Bildern der eigenen Bank (Flash, S. 3). **SEF 255** löscht.'],
    ])
    s.y += 3
    s.absatz('* nur mit Speichererweiterung.  Akku/Zellen müssen Daten sein (00.xxx), sonst F 005.  JSR/PSH: ein Stapel, 22 Ebenen, „xxx PC“ leert ihn.', FARBE['grau'])


def seite2(s):
    s.titel('Kosmos CP1 · Projekte über die Tasten', 'Projekt 01–99 · CLR löscht · STP bricht ab')
    s.balken('★ CAS: Speicher in ein Projekt sichern')
    s.tabelle([50, 0], [
        ['`020 PC`, dann CAS', '`Pro __`: Projektnummer tippen, CAS bestätigt. Start des Projekts = PC (hier 020).'],
        ['`5to 07` → `5to rdY`', 'ganzer Speicher in Projekt 07. Gibt es das Projekt noch nicht, legt der CP1 es an (4 Bänke, erste freie Lücke). '
                                 'Die alte Fassung bleibt bis zum Schluss gültig, Name, Bilder und Labels bleiben.'],
        ['CAS **1 s halten**', '`Fr ___` `to ___` (Zellen im Speicher), `Pro __`, `d5t ___` (erste Zelle in der Bank). Rest der Bank bleibt.'],
    ])
    s.balken('★ CAL: Projekte durchblättern und laden')
    s.tabelle([50, 0], [
        ['CAL', '`Pro 02` blitzt kurz, dann zeigt das Projekt seine Kurzanzeige (z. B. `rAkEtE`), sonst den Namensanfang.'],
        ['CAL nochmal', 'nächstes Projekt; nach dem letzten wieder von vorn.'],
        ['CAL **1 s halten**', 'dieses Projekt laden: `LdP 02`, dann `P   020` (PC = Start). **RUN** startet.'],
        ['Ziffern', 'Projekt direkt wählen (`Pro _5`), CAL lädt.'],
        ['CAL 1 s im Leerlauf', 'Teilbereich: `Pro __`, `Fr ___` `to ___` (Zellen der ersten Bank), `d5t ___` (Ziel im Speicher). PC bleibt.'],
    ])
    s.balken('★ RUN 1 s: Autoboot · ★ Reset')
    s.tabelle([50, 0], [
        ['`bot __`, `09` RUN', 'beim Einschalten Projekt 09 laden und starten (`bot rdY`). **00** schaltet ab.'],
        ['Einschalten', '`  6.20 `, dann `bot 09` für 2 s: **jede Taste bricht ab**, sonst wird geladen und gestartet.'],
        ['**CLR halten + STP**', 'Reset wie Aus- und Einschalten: Speicher, Stapel, OVF weg; dann Version und Autoboot. Auch im Programmlauf.'],
    ])
    s.balken('★ SEG: eigene Zeichen auf der Anzeige')
    y0 = s.y + 12
    h = s.segbild(RAND + 52, y0)
    x2 = RAND + 210
    zeilen = [
        '**SEG xxx** schreibt die Werte der Zellen xxx … xxx+5 auf die Stellen 1–6.',
        'Wert = Summe der Segmente, z. B. `C` = 1 + 8 + 16 + 32 = **57**.',
        'Die Zellen müssen Daten sein (00.xxx), sonst F 005. **SEG 255** löscht.',
        'Zahlen: **AS1/AS2/AS3** schreiben die Ziffern des Akkus als Muster.',
        '**HLT** zeigt danach den PC. Bild stehen lassen: mit SPU auf sich selbst enden.',
    ]
    yy = y0 - 4
    for t in zeilen:
        for z in umbrechen(t, W - RAND - x2):
            s.zeile(x2, yy + GR, z); yy += LH
        yy += 3
    s.y = max(y0 + h, yy) + 3
    s.tabelle([20, 0], [
        ['Ziffern', '0=63    1=6    2=91    3=79    4=102    5=109    6=125    7=39    8=127    9=111'],
        ['Zeichen', 'A=119    b=124    C=57    c=88    d=94    E=121    F=113    H=118    L=56    o=92    P=115    r=80    t=120    u=28    Y=110    -=64    _=8'],
    ])
    s.balken('★ Kniffe mit dem Stapel')
    s.tabelle([38, 0], [
        ['Akku retten', '**PSH** vor dem **JSR**, **POP** danach.'],
        ['Berechneter Sprung', '**AKO 020** / **PSH** / **RET** springt nach 020 (ungültig: F 003). Nach **TST** = Sprungtabelle.'],
        ['Eigene Adresse', '**JSR** auf den nächsten Befehl, dann **POP**: Akku = Adresse hinter dem JSR.'],
        ['Rücksprung verbiegen', 'Im Unterprogramm **POP** / **ADD** / **PSH** / **RET**: z. B. Datenzellen hinter dem JSR überspringen.'],
    ])
    s.balken('Fehleranzeigen')
    s.tabelle([17, 0], [
        ['`F   001`', 'Zu wenig oder zu viele Ziffern (INP braucht 3 oder 5, PC und OUT keine oder 3; Ausnahme 9 OUT).'],
        ['`F   002`', 'Programm trifft auf ein Datum (00.xxx) oder einen unbekannten Befehl (★ 50–99, Original: 25–99).'],
        ['`F   003`', 'Ungültige Adresse im Programmlauf: PC über 127 bzw. 255, oder Zelle, die es nicht gibt. ★ Flash: Bank k außerhalb des Projekts, Bereich über 255, kein Projekt, JOV aus leerer Bank. Projekt 00.'],
        ['`F   004`', 'Ungültig eingetippt: Adresse über 255, OUT über das Speicherende hinaus, ★ Befehl über 47 (Original: über 24).'],
        ['`F   005`', 'Akku oder Zelle enthält einen Befehl statt eines Datums (ADD, SUB, VGL, UND, ★ ODR, ★ SEG, ★ AS1–3, ★ PSH, Ports …).'],
        ['`F   006`', 'Ergebnis von ADD über 255 oder von SUB unter 0. ★ Abschaltbar mit OVF 000.'],
        ['`F   007`', 'Fehlerhafte Werte von der Kassette (nur Original-Firmware).'],
        ['`F   008`', '★ Stapel voll: mehr als 22 JSR/PSH ohne RET/POP (z. B. Endlos-Rekursion).'],
        ['`F   009`', '★ RET, POP, FRD/FWR auf leerem Stapel.'],
        ['`F   010`', '★ Kein Flash antwortet.   ★ **F 011:** Projekt gibt es nicht.   ★ **F 012:** Flash voll (kein Platz für ein neues Projekt).'],
    ])
    s.y += 2
    s.absatz('Nach F 002, F 003, F 005, F 006, F 008 und F 009 zeigt PC die Stelle, an der das Programm abgebrochen hat.', FARBE['grau'])


def seite3(s):
    s.titel('Kosmos CP1 · Flash im Programm, Pi', '99 Projekte · Bank = 256 Zellen')
    s.balken('★ Im Programm: PSK, FRD, FWR')
    s.tabelle([50, 0], [
        ['`PSK 001` · `PSK 123` · `PSK 010`', 'Bank **des eigenen Projekts** (0 = erste), erste Zelle in der Bank, Anzahl (000 = 256) auf den Stapel …'],
        ['`FRD 080`', '… und lesen: Zellen 123–132 der zweiten Projektbank ins RAM 080–089. Leere Bank liefert 00.000.'],
        ['`FWR 080`', '… bzw. schreiben: RAM 080–089 in die Bank (ca. 0,6 s). Übrige Zellen der Bank bleiben.'],
        ['`PSK 000`', 'erste Bank des Projekts: Startwerte neu laden, Rekord speichern. Statt PSK geht auch **AKO** / **PSH**.'],
        ['Grenzen', 'Bank nur innerhalb des Projekts (meist 0–3), Bereich bis Zelle 255, RAM bis 127 bzw. 255, sonst F 003; Stapel leer → F 009.'],
    ])
    s.balken('★ JOV: Overlays – Programme größer als der Speicher')
    s.tabelle([62, 0], [
        ['`PSK 002` · `PSK 080` · `JOV 040`', '80 Zellen ab Zelle 040 aus Bank 2 des Projekts nach 040 laden und dort weitermachen (~1 ms je Zelle).'],
        ['Am Pi: `.bereich 040-219`', 'Quelltext mit `>>kern` (fest), `>>teil 1 spiel`, `>>teil 2 wuerfel`; **LADE spiel** wird zu PSK/PSK/JOV.'],
        ['Regel', 'LADE nie aus einem Unterprogramm im wechselnden Bereich (der Rücksprung zeigt sonst ins neue Teil).'],
    ])
    s.balken('★ Am Pi (bastelpi): Fernsteuerung immer an')
    s.tabelle([112, 0], [
        ['**http://bastelpi:8049/**', 'Anzeige, Tasten, Zellen (auch live im Lauf), Editor mit Namenstabelle, Flash-Verzeichnis, Reset.'],
        ['Editor', 'Holen (CP1, Projekt, Datei) → ändern → **Assemblieren** → **In CP1 laden** oder ins Projekt speichern (mit Namen, Bildern, Kurzanzeige).'],
        ['~kosmos_remote.py laden|speichern prog.json~', 'Speicher ↔ Datei per FNI (ca. 1 s), keine Taste am CP1 nötig.'],
        ['~kosmos_remote.py taste 0 0 0 pc run~', 'Tasten drücken (cal:1500 = 1,5 s halten).'],
        ['~kosmos_remote.py flash~ · ~autoboot 9~ ', 'Projektverzeichnis (Nummer, Bänke, Name, Kurzanzeige) · Autoboot-Projekt.'],
        ['~projekt-sichern 8 x.cp1~ · ~projekt-einspielen x.cp1 [8]~', 'ganzes Projekt als Datei (alle Bänke, Labels, Bilder) und zurück.'],
        ['~paket spiel.koa spiel.cp1~', 'Quelltext, auch Overlay-Paket, als Projektdatei; dann projekt-einspielen.'],
        ['~kosmos_remote.py zelle 35~ · ~reset~', 'Zelle lesen/setzen, auch im Programmlauf · Reset wie CLR + STP.'],
        ['~kosmos_asm.php~ · ~kosmos_disasm.php -n namen.txt~', 'Assembler · Disassembler mit Namen (`035=display_loop`).'],
    ])
    s.balken('★ TSE: Tasten abfragen, ohne zu warten (für Spiele)')
    s.tabelle([62, 0], [
        ['`TSE` (39.000)', 'Akku = Ziffer, die seit dem letzten TSE gedrückt wurde, sonst **255**. Auch während **VZG** gedrückte Tasten zählen.'],
        ['`TSE` · `VGL acht` · `SPB hoch`', 'Typische Abfrage in der Spielschleife.'],
        ['`ZUF 006` · `ADD #1`', 'Würfel 1–6. Bei jedem ZUF wird der Timer eingemischt: wann Tasten gedrückt werden, macht den Zufall.'],
    ])
    s.balken('★ SEF: Bilder und Lauftexte aus der eigenen Bank (nicht im RAM)')
    s.tabelle([62, 0], [
        ['Webseite, Feld **Bilder**', '`titel=MInEn`, `lauf=  HALLO CP1  ` (beliebig lang), `#1,2,3` = Segmentwerte. **Editor speichern** legt sie in die Bank.'],
        ['`SEF titel` · `SEF lauf+3`', '6 Stellen ab dem Bild (+3: ab dem 4. Zeichen), ~12 ms. Aus der ersten Bank des Projekts.'],
        ['`SEF 254` · `SEF 248` · `SEF 255`', 'Position aus dem Akku (Lauftext unten) · Blätter-Anzeige der Bank · Anzeige löschen.'],
        ['`000` AKO 0 · ABS pos', 'Lauftext: Position auf 0'],
        ['`002` LDA pos · ADD #lauf · SEF 254 · VZG 250', 'Bildanfang + Position zeigen, ¼ s warten'],
        ['`006` LDA pos · ADD #1 · ABS pos · VGL #7', 'eine Stelle weiter; Textlänge − 6 erreicht?'],
        ['`010` SPB 000 · SPU 002', 'dann von vorn, sonst weiter (12 Zellen für jede Textlänge)'],
    ])
    s.y += 2
    s.absatz('Hardware: IS25LP016D an Port 1, Klemme 1 = CS, 2 = Takt (zugleich A14 des EEPROMs), 3 = Daten hin, 4 = Daten zurück; '
             'Klemme 5 (P1.4) = A12, Klemme 6 (P1.5) = A13, Klemme 7/8 = Pi (Pin 35 = BCM 19 / Pin 37 = BCM 26). '
             'Jede Bank liegt doppelt im Wechsel: ein Stromausfall beim Schreiben verliert nie die alte Fassung.', FARBE['grau'])


SEITEN = [seite1, seite2, seite3]
