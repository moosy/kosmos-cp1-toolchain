# kosmos-cp1-toolchain
Toolchain for the 1980s Kosmos-CP1 learning computer

This is a toolchain for owners of the brilliant Kosmos CP1 learning computer.
See https://de.wikipedia.org/wiki/Kosmos_CP1 for details.
A comprehensive collection of documentation can be found at 
http://www.8bit-homecomputermuseum.at/computer/kosmos_computer_praxis_cp1.html .

This toolchain consists of the following tools:

kosmos_recv.py filename.json
----------------------------

A python script that can transfer the contents of the CP1 memory to a .json file.
It is designed to run on a raspberry pi, where one GPIO Pin (I use GPIO 26) has to 
be connected to Pin 8 at Port 1 of the CP1.

Beware: The CP1 is a 5V device, therefore the voltage to the raspi has to be limited.
It turns out a simple zener diode with a resistor does the job:
                     
GPIO: --------o-----[1 kOhm]------ Port 1/8
              |
            -----,
              ^     Zener diode 3,3 V
             / \
            -----
              |
GND:  --------o-------------------- GND 

After the script has been started, press CAS on your CP1.
Note the CP1 will wait 16 seconds before starting the transfer.

The transfer will take about 3,5 mins or 7 mins with memory expansion installed.
This cannot be sped up, because the CP1 determines the speed of communication.


kosmos_send.py filename.json
----------------------------

The counter part of kosmos_recv.py. Sends a compatible .json file data to the CP1.
After starting the script, press CAL on your CP1.

The data is received and written to the file.
If you don't have a memory extension installed, you might have to press CAS and STP
after the CP1 is ready, because the script still waits for the rest of the data.


kosmos_json_show.py filename.json
---------------------------------

Shows the content of the .json file in a decent way and shows the opcodes.


kosmos_disasm.php [-i] [-c] [-d] [-o] filename.json
---------------------------------------------------

Disassembles the .json file and creates a .koa assembly language file
Options:
       -c show code
       -d show description
       -i show inline numerics
       -o create filename.koa

By default, kosmos_disasm only shows the assembly-tokens and the labels it
has detected. Line numbers are omitted if possible:

kosmos_disasm.php lichtband.json

>label_1:

  001 LIA adresse_1
      ABS wert_4
      AKO 255
      SUB wert_4
      P2A 000
      VZG 030
      LDA adresse_1
      VGL wert_2
      SPB label_2
      ADD wert_1
      ABS adresse_1
      SPU label_1

>label_2:
      SUB wert_1
      ABS adresse_1
      VGL wert_3
      [...]

With -c option you can additionally display the decimal codes entered in the CP1 
including all line numbers.

kosmos_disasm.php lichtband.json -c

>label_1:

  001 LIA adresse_1           |  001: 19.067
      ABS wert_4              |  002: 06.070
      AKO 255                 |  003: 04.255
      SUB wert_4              |  004: 08.070
      P2A 000                 |  005: 18.000
      VZG 030                 |  006: 03.030
      LDA adresse_1           |  007: 05.067
      VGL wert_2              |  008: 10.068
      SPB label_2             |  009: 11.013
      ADD wert_1              |  010: 07.051
      ABS adresse_1           |  011: 06.067
      SPU label_1             |  012: 09.001

>label_2:
      SUB wert_1              |  013: 08.051
      ABS adresse_1           |  014: 06.067
      VGL wert_3              |  015: 10.069
      [...]


With -d option you can display the explanation of every command (in german):

kosmos_disasm.php lichtband.json -c -d

>label_1:

  001 LIA adresse_1           |  001: 19.067  |  Akku mit Inhalt der Zelle laden, deren Adresse unter 67 (adresse_1) steht
      ABS wert_4              |  002: 06.070  |  Akku-Inhalt in Zelle 70 (wert_4) speichern
      AKO 255                 |  003: 04.255  |  Konstante 255 in den Akku laden
      SUB wert_4              |  004: 08.070  |  Vom Akku Inhalt von Zelle 70 (wert_4) subtrahieren
      P2A 000                 |  005: 18.000  |  Akku-Inhalt an Klemme 0 von Port 2 legen (000 = alle)
      VZG 030                 |  006: 03.030  |  Verzögern um 30 ms
      LDA adresse_1           |  007: 05.067  |  Inhalt von Zelle 67 (adresse_1) in den Akku laden
      VGL wert_2              |  008: 10.068  |  Prüfen, ob Akku gleich Inhalt von Zelle 68 (wert_2) ist
      SPB label_2             |  009: 11.013  |  Wenn ja, springe zu Adresse 13 (label_2)
      ADD wert_1              |  010: 07.051  |  Zum Akku Inhalt von Zelle 51 (wert_1) addieren
      ABS adresse_1           |  011: 06.067  |  Akku-Inhalt in Zelle 67 (adresse_1) speichern
      SPU label_1             |  012: 09.001  |  Springe zu Adresse 1 (label_1)

>label_2:
      SUB wert_1              |  013: 08.051  |  Vom Akku Inhalt von Zelle 51 (wert_1) subtrahieren
      ABS adresse_1           |  014: 06.067  |  Akku-Inhalt in Zelle 67 (adresse_1) speichern
      VGL wert_3              |  015: 10.069  |  Prüfen, ob Akku gleich Inhalt von Zelle 69 (wert_3) ist
      [...]


Option -o writes the disassembled text into a .koa file.

