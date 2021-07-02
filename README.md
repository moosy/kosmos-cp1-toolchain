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

```                     
GPIO: --------o-----[1 kOhm]------ Port 1/8
              |
            -----,
              ^     Zener diode 3,3 V
             / \
            -----
              |
GND:  --------o-------------------- GND 
```

After the script has been started, press CAS on your CP1.
Note the CP1 will wait 16 seconds before starting the transfer.

The transfer will take about 3,5 mins or 7 mins with memory expansion installed.
This cannot be sped up, because the CP1 determines the speed of communication.

The data is received and written to the file.
If you don't have a memory extension installed, you might have to press CAS and STP
after the CP1 is ready, because the script still waits for the rest of the data.



kosmos_send.py filename.json
----------------------------

The counterpart of kosmos_recv.py. Sends a compatible .json file data to the CP1.
After starting the script, press CAL on your CP1.

This transfer is somewhat faster, because we control the transmission. If
errors occur, try to increase the time_base - Parameter in the script.
Mine works fine wirh 15, 33 is the original speed.



kosmos_json_show.py filename.json
---------------------------------

Shows the content of the .json file in a decent way and shows the opcodes.



kosmos_disasm.php [-i] [-c] [-d] [-o] filename.json
---------------------------------------------------

Disassembles the .json file and creates a .koa assembly language file

Options:

```
       -c show code
       -d show description
       -i show inline numerics
       -o create filename.koa
```

By default, kosmos_disasm only shows the assembly-tokens and the labels it
has detected. Line numbers are omitted if possible:

```
user@machine:# kosmos_disasm.php lichtband.json

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

```
With -c option you can additionally display the decimal codes entered in the CP1 
including all line numbers.


```
user@machine:# kosmos_disasm.php lichtband.json -c

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

```

With -d option you can display the explanation of every command (in german):


```
user@machine:# kosmos_disasm.php lichtband.json -c -d

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

```

Option -o writes the disassembled text into a .koa file.



kosmos_asm.php [-i] [-c] [-d] [-o] [-s] [-r] filename.koa
---------------------------------------------------------

Options:  
```          
          -c show code
          -d show description
          -i show inline numerics
          -o create filename.json
          -s create filename.json and start transfer to CP1
          -r rewrite (beautify) input file
```

This is the CP1 assembler. You can just begin using the CP1 mnemonics and either numeric or symbolic parameters.
If you use symbolic parameters you have to declare them somewhere with an leading '>'.
You don't have to specify line numbers at all, if you do the assembler will try to assign them as you specified them.
Data values are marked with the mnemonic '#'.

Example:

```
AKO 0
>loop:
ANZ
VZG 250
ADD one
SPU loop

>one:
# 1
```

If you call the kosmos_asm.php it will output this:

```
user@machine:# kosmos_asm.php example.koa

      AKO 000

>loop:
      ANZ
      VZG 250
      ADD one
      SPU loop

>one:
      # 001
```

As you see the assembler beautified your code. You don't see any assembled code because you neither told the
assembler to display it nor to write it to file. 

With the -c option you see the code:

```
user@machine:# kosmos_asm.php example.koa -c
      AKO 000                 |  000: 04.000

>loop:
      ANZ                     |  001: 02.000
      VZG 250                 |  002: 03.250
      ADD one                 |  003: 07.005
      SPU loop                |  004: 09.001

>one:
      # 001                   |  005: 00.001
```

If you add the -d option you get a (german) explanation of every command:

```
user@machine:# kosmos_asm.php example.koa -c -d

      AKO 000                 |  000: 04.000  |  Konstante 000 in den Akku laden

>loop:
      ANZ                     |  001: 02.000  |  Akku-Inhalt anzeigen
      VZG 250                 |  002: 03.250  |  Verzögern um 250 ms
      ADD one                 |  003: 07.005  |  Zum Akku Inhalt von Zelle 005 (one) addieren
      SPU loop                |  004: 09.001  |  Springe zu Adresse 001 (loop)

>one:
      # 001                   |  005: 00.001  |  Datenwert 001

```

You can see the real values of the symbolic constants and the line number in the code section.
Alternatively, you can tell the assembler to display them inline with the -i option:

```
user@machine:# kosmos_asm.php example.koa -i

 (000) AKO 000

>loop:
 (001) ANZ
 (002) VZG 250
 (003) ADD one (005)
 (004) SPU loop (001)

>one:
 (005) # 001

```

Bracketed line numbers are auto-assigned by the assembler.

If you like the beautified output, you can use the -r option to rewrite your source file with the beautified version.

Note: You can add comments by starting a line with '//'. These comments are preserved by the assembler.
You can add comments at the end of each line starting with '//' as well, but these are NOT preserved in the
beautified output. It is recommended to use dedicated comment lines for this reason.

With the -o option you can tell the assembler to write a .json file for further use, e.g. for writing it
to the CP1. If you use the -s option, the kosmos_send.py tool is invoked automatically and the 
transfer to the CP1 begins.


Installation and Prerequisites
------------------------------

Installation is pretty straightforward: Just copy the files to any location on your raspberry pi filesystem
(recommended: /usr/local/bin) and set the execution flags (e.g. with chmod +x *.php *.py).
If you don't ust /usr/local/bin you might want to adapt the path at the end
of the kosmos_asm.php:

```
if ($send) passthru("/usr/local/bin/kosmos_send.py $fo");
                     ^^^^^^^^^^^^^^^
```


The standard raspberian os distribution should contain anything you need, perhaps except from the php-package
which needs to be installed manually:

```
user@machine:# apt-get update
user@machine:# apt-get install php
```

