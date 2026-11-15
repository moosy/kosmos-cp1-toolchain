# Inhalt des Cheat Sheets (wird von satz.py ausgeführt). Anzeigen im Raster "X YY ZZZ" wie am Gerät (8 88 888).

def seite1(s):
    s.titel('Kosmos CP1 · Schnellübersicht', 'Firmware 5.05 · Stand 15.11.2026')
    s.absatz('Gilt für die Firmware 5.05 im EA-Adapter (zeigt beim Einschalten 1 s lang `  5.05 `). '
             'Neu oder geändert gegenüber dem Original: ★')
    s.balken('Funktionstasten')
    s.tabelle([17, 0], [
        ['**RUN**', 'Programmlauf starten (★ beim Loslassen). ★ **1 s halten:** Autoboot-Bank wählen (`bot ___`, Seite 2).'],
        ['**STP**', 'Programmlauf stoppen, Inhalt von Zelle 000 wird angezeigt. ★ **CLR halten + STP:** Reset.'],
        ['**STEP**', 'Einzelschritt: ein Befehl wird ausgeführt.'],
        ['**ACC**', 'Akku-Inhalt anzeigen.'],
        ['**CLR**', 'Anzeige löschen.'],
        ['**PC**', 'Programmzähler anzeigen; drei Ziffern + PC stellt ihn ein.'],
        ['**OUT**', 'Drei Ziffern + OUT: Zelle anwählen und anzeigen; weiteres OUT zeigt die nächste.'],
        ['**INP**', 'Fünf Ziffern + INP: Zelleninhalt eingeben. ★ Befehle bis 39 erlaubt (Original: bis 24).'],
        ['**9 OUT**', 'Stand des Ein-/Ausgabezeigers anzeigen (`C   nnn`).'],
        ['★ **CAS**', 'Speicher in eine Flash-Bank sichern (Seite 2). Ersetzt die Kassette.'],
        ['★ **CAL**', 'Flash-Bänke durchblättern und laden (Seite 2).'],
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
        ['P1A', '17.00x / .000', 'Akku (0/1) an Port 1 Klemme x bzw. dezimalen Akku als Dualzahl an Port 1. ★ Nur Klemme 6 frei.'],
        ['P2A', '18.00x / .000', 'Wie P1A, für Port 2.'],
        ['LIA', '19.xxx', 'Akku indirekt laden (aus der Zelle, deren Adresse in xxx steht).'],
        ['AIS', '20.xxx', 'Akku indirekt speichern (in die Zelle, deren Adresse in xxx steht).'],
        ['SIU', '21.xxx', 'Indirekt unbedingt springen (auf die Adresse, die in xxx steht).'],
        ['P3E *', '22.00x / .000', 'Wie P1E, für Port 3.'],
        ['P4A *', '23.00x / .000', 'Wie P1A, für Port 4.'],
        ['P5A *', '24.00x / .000', 'Wie P1A, für Port 5 (nur Klemmen 1–6, dezimal 000–063).'],
        ['★ ODR', '25.xxx', 'Akku bitweise ODER Inhalt von Zelle xxx. 197 ODR 060 = 253.'],
        ['★ OVF', '26.000\n26.001', 'Überlauf aus: ADD/SUB rechnen modulo 256, kein F 006.\n'
                                  'Überlauf wieder an. Nach dem Einschalten immer an; gilt bis zum Ausschalten, auch über RUN hinweg.'],
        ['★ SEG', '27.xxx\n27.255', 'Zellen xxx … xxx+5 als Segmentmuster auf Stelle 1–6 anzeigen (Werte auf der Rückseite).\nAnzeige löschen.'],
        ['★ AS', '28–30.xxx', '**AS1 / AS2 / AS3:** Hunderter / Zehner / Einer des Akkus als Segmentmuster in Zelle xxx (234: AS2 → 3).'],
        ['★ TST', '31.000', 'Auf eine Zifferntaste warten, Ziffer 0–9 in den Akku. STP hält an, RUN macht beim TST weiter.'],
        ['★ JSR', '32.xxx', 'Unterprogramm ab Adresse xxx aufrufen;  **RET 33.000** springt hinter das letzte JSR zurück.'],
        ['★ PSH', '34.000', 'Akku auf den Stapel legen;  **POP 35.000** holt den obersten Wert in den Akku.'],
        ['★ PSK', '36–39.xxx', '**PSK** Konstante auf den Stapel. **FRD/FWR** Flash ab RAM-Zelle xxx (S. 3). **TSE** Taste ohne Warten.'],
    ])
    s.y += 3
    s.absatz('* nur mit Speichererweiterung.   NEG, UND, ODR, SEG, AS1–3, PSH: Akku bzw. Zellen müssen Daten sein (00.xxx), sonst F 005.\n'
             'JSR/RET/PSH/POP teilen sich einen Stapel mit 24 Ebenen. „xxx PC“ über die Tastatur leert ihn, RUN allein nicht.', FARBE['grau'])


def seite2(s):
    s.titel('Kosmos CP1 · Flash über die Tasten', 'immer 3 Ziffern · CLR löscht · STP bricht ab')
    s.balken('★ CAS: Speicher in eine Bank sichern')
    s.tabelle([50, 0], [
        ['`020 PC`, dann CAS', '`bAn ___`: Bank tippen, CAS bestätigt. Start der Bank = PC (hier 020).'],
        ['`5to 007` → `5to rdY`', 'ganzer Speicher in Bank 007 (gut 1 s). Die alte Fassung bleibt bis zum Schluss gültig, Name und Namen bleiben.'],
        ['CAS **1 s halten**', '`Fr ___` `to ___` (Zellen im Speicher), `bAn ___`, `d5t ___` (erste Zelle in der Bank). Rest der Bank und Verzeichnis bleiben.'],
    ])
    s.balken('★ CAL: Bänke durchblättern und laden')
    s.tabelle([50, 0], [
        ['CAL', '`bAn 001` blitzt kurz, dann zeigt die Bank ihre Anzeige (z. B. `rAKEtE`): eigene von der Webseite, sonst den Namensanfang.'],
        ['CAL nochmal', 'nächste belegte Bank; nach der letzten wieder von vorn (dieser Schritt ~1,6 s).'],
        ['CAL **1 s halten**', 'diese Bank laden: `LdA 001`, dann `P   020` (PC = Start). **RUN** startet.'],
        ['Ziffern', 'Bank direkt wählen (`bAn __7`), CAL lädt.'],
        ['CAL 1 s im Leerlauf', 'Teilbereich: `bAn ___`, `Fr ___` `to ___` (Zellen der Bank), `d5t ___` (Ziel im Speicher). PC bleibt, `LdA rdY`.'],
    ])
    s.balken('★ RUN 1 s: Autoboot · ★ Reset')
    s.tabelle([50, 0], [
        ['`bot ___`, `007` RUN', 'beim Einschalten Bank 007 laden und starten (`bot rdY`). **000** schaltet ab.'],
        ['Einschalten', '`  5.05 `, dann `bot 007` für 2 s: **jede Taste bricht ab**, sonst wird geladen und gestartet.'],
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
    s.balken('Fehleranzeigen')
    s.tabelle([17, 0], [
        ['`F   001`', 'Zu wenig oder zu viele Ziffern (INP braucht 3 oder 5, PC und OUT keine oder 3; Ausnahme 9 OUT).'],
        ['`F   002`', 'Programm trifft auf ein Datum (00.xxx) oder einen unbekannten Befehl (★ 40–99, Original: 25–99).'],
        ['`F   003`', 'Ungültige Adresse im Programmlauf: PC über 127 bzw. 255, oder Zelle, die es nicht gibt. ★ Bank 000 oder Bereich über 255 beim Flash.'],
        ['`F   004`', 'Ungültig eingetippt: Adresse über 255, OUT über das Speicherende hinaus, ★ Befehl über 39 (Original: über 24).'],
        ['`F   005`', 'Ungültiger Operand bei ADD, SUB, VGL, NEG, UND, ★ ODR, ★ SEG, ★ AS1–3, ★ PSH, P1E, P1A, P2A, P3E, P4A, P5A: im Akku oder in der Zelle steht ein Befehl statt eines Datums. ★ NEG und UND nehmen jetzt alle Werte 0–255.'],
        ['`F   006`', 'Ergebnis von ADD über 255 oder von SUB unter 0. ★ Abschaltbar mit OVF 000.'],
        ['`F   007`', 'Fehlerhafte Werte von der Kassette (nur Original-Firmware).'],
        ['`F   008`', '★ Stapel voll: mehr als 24 JSR/PSH ohne RET/POP (z. B. Endlos-Rekursion).'],
        ['`F   009`', '★ RET, POP, FRD/FWR auf leerem Stapel.'],
        ['`F   010`', '★ Kein Flash antwortet.   ★ **F 011:** Bank leer.'],
    ])
    s.y += 2
    s.absatz('Nach F 002, F 003, F 005, F 006, F 008 und F 009 zeigt PC die Stelle, an der das Programm abgebrochen hat.', FARBE['grau'])


def seite3(s):
    s.titel('Kosmos CP1 · Flash im Programm, Pi', '256 Bänke à 256 Zellen · Bank 0 = Verzeichnis')
    s.balken('★ Im Programm: PSK, FRD, FWR')
    s.tabelle([50, 0], [
        ['`PSK 005` · `PSK 123` · `PSK 010`', 'Bank, erste Zelle in der Bank, Anzahl (000 = 256) auf den Stapel legen …'],
        ['`FRD 080`', '… und lesen: Zellen 123–132 von Bank 5 ins RAM 080–089. Leere Bank liefert 00.000.'],
        ['`FWR 080`', '… bzw. schreiben: RAM 080–089 in die Bank (ca. 0,6 s). Übrige Zellen der Bank bleiben.'],
        ['Werte rechnen', 'Statt PSK geht auch **AKO** / **PSH** (z. B. Banknummer aus einer Zelle oder nach TST).'],
        ['Grenzen', 'Bank + Bereich bis Zelle 255, RAM bis 127 bzw. 255, **FWR auf Bank 0 → F 003**, Stapel leer → F 009.'],
    ])
    s.balken('★ Bank 0: Verzeichnis (mit FRD lesbar)')
    s.tabelle([50, 0], [
        ['Zelle 000', '00.nnn = Autoboot-Bank (000 = aus)'],
        ['Zelle nnn', '00.sss = Startadresse von Bank nnn (beim Sichern mit CAS eingetragen)'],
        ['Name', '16 Zeichen je Bank, dazu Namenstabelle (Labels) und eigene 6-stellige Anzeige: nur über die Webseite, CAS behält sie.'],
    ])
    s.balken('★ Am Pi (bastelpi): Fernsteuerung immer an')
    s.tabelle([112, 0], [
        ['**http://bastelpi:8049/**', 'Anzeige, Tasten, Zellen (auch live im Lauf), Editor mit Namenstabelle, Flash-Verzeichnis, Reset.'],
        ['Editor', 'Holen (CP1, Bank, Datei) → ändern → **Assemblieren** → **In CP1 laden** oder **Editor speichern** (direkt in die Bank, mit Namen und Anzeige).'],
        ['~kosmos_remote.py laden|speichern prog.json~', 'Speicher ↔ Datei per FNI (ca. 1 s), keine Taste am CP1 nötig.'],
        ['~kosmos_remote.py taste 0 0 0 pc run~', 'Tasten drücken (cal:1500 = 1,5 s halten).'],
        ['~kosmos_remote.py flash~ · ~bank-sichern 6 a.json~', 'Verzeichnis · Bank direkt in eine Datei (Speicher bleibt).'],
        ['~kosmos_remote.py zelle 35~ · ~reset~', 'Zelle lesen/setzen, auch im Programmlauf · Reset wie CLR + STP.'],
        ['~kosmos_asm.php~ · ~kosmos_disasm.php -n namen.txt~', 'Assembler · Disassembler mit Namen (`035=display_loop`).'],
    ])
    s.balken('★ Klemme 7 und 8: so redet der Pi mit dem CP1')
    s.tabelle([50, 0], [
        ['**NIE** (Klemme 8)', 'im Interrupt, unbemerkt, auch im Programmlauf: Anzeige, Tasten, Zellen, Reset.'],
        ['**FNI** (Klemme 7 + 8)', 'getaktet, Interrupt aus: ganze Bereiche und Bänke. Rechts `P-C` `C-P` `P-F` `F-P`, dann `rdY` bzw. `Err`. '
                                  'Nur wenn der CP1 auf Tasten wartet, ein laufendes Programm wird nie gestört.'],
    ])
    s.balken('★ Kniffe mit dem Stapel')
    s.tabelle([38, 0], [
        ['Akku retten', '**PSH** vor dem **JSR**, **POP** danach.'],
        ['Berechneter Sprung', '**AKO 020** / **PSH** / **RET** springt nach 020 (ungültig: F 003). Nach **TST** = Sprungtabelle.'],
        ['Eigene Adresse', '**JSR** auf den nächsten Befehl, dann **POP**: Akku = Adresse hinter dem JSR.'],
        ['Rücksprung verbiegen', 'Im Unterprogramm **POP** / **ADD** / **PSH** / **RET**: z. B. Datenzellen hinter dem JSR überspringen.'],
    ])
    s.balken('★ TSE: Tasten abfragen, ohne zu warten (für Spiele)')
    s.tabelle([62, 0], [
        ['`TSE` (39.000)', 'Akku = Ziffer, die seit dem letzten TSE gedrückt wurde, sonst **255**. Auch während **VZG** gedrückte Tasten zählen.'],
        ['`TSE` · `VGL acht` · `SPB hoch`', 'Typische Abfrage in der Spielschleife (Beispiel: Asteroiden in Bank 6, Rekord in Bank 4).'],
    ])
    s.balken('★ Beispiel: Lauftext (Bank 2 = Programm, Bank 3 = Text als Segmentmuster)')
    s.tabelle([62, 0], [
        ['`000` AKO 000 · ABS pos', 'Position auf 0'],
        ['`002` PSK 003 · LDA pos · PSH · PSK 006', 'Bank 3, ab Zelle pos, 6 Zellen …'],
        ['`006` FRD buf · SEG buf · VZG 250', '… ins RAM holen, als Segmente zeigen, ¼ s warten'],
        ['`009` LDA pos · ADD eins · ABS pos', 'eine Stelle weiter'],
        ['`012` VGL ende · SPB start · SPU loop', 'am Textende (Länge − 5) von vorn'],
    ])
    s.absatz('Der Text darf bis zu 256 Zeichen lang sein, obwohl das Programm nur 24 Zellen braucht: er liegt im Flash, nicht im RAM. '
             'Vorn und hinten je 6 Leerzeichen (Muster 0), dann läuft er sauber ein und aus.', FARBE['grau'])
    s.y += 2
    s.absatz('Hardware: IS25LP016D an Port 1, Klemme 1 = CS, 2 = Takt, 3 = Daten hin, 4 = Daten zurück; Klemme 5 (P1.4) schaltet A12 '
             'des EEPROMs, Klemme 7/8 = Pi (Pin 35 = BCM 19 / Pin 37 = BCM 26). Jede Bank liegt doppelt im Wechsel: ein Stromausfall beim Schreiben verliert nie die alte Fassung.', FARBE['grau'])


SEITEN = [seite1, seite2, seite3]
