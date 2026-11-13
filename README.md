# kosmos-cp1-toolchain
Toolchain for the 1980s Kosmos-CP1 learning computer.

This is a toolchain for owners of the brilliant Kosmos-CP1 learning computer.
See https://de.wikipedia.org/wiki/Kosmos_CP1 for details.
A comprehensive collection of documentation can be found at 
http://www.8bit-homecomputermuseum.at/computer/kosmos_computer_praxis_cp1.html.

Quick reference (German, 3 pages A4, firmware 4.02 with all extensions): [cp1-schnelluebersicht.pdf](cp1-schnelluebersicht.pdf)

This toolchain consists of the following tools:

kosmos_recv.py filename.json
----------------------------

A python script that can transfer the contents of the CP1 memory to a JSON file.
It is designed to run on a Raspberry Pi, where one GPIO pin (I use GPIO 26) has to 
be connected to pin 8 on port 1 of the CP1.
The Python scripts use gpiozero and work with both gpiozero 1.x and 2.x
(gpiozero 2.0, shipped with Raspberry Pi OS bookworm and trixie, only accepts keyword arguments).

Beware: The CP1 is a 5V device, therefore the voltage to the Raspberry Pi must be limited!
It turns out a simple Zener diode with a resistor does the job:

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
Note that the CP1 waits 16 seconds before starting the transfer.

The transfer takes about 3.5 min. or 7 min. with memory expansion installed.
This cannot be accelerated as the CP1 determines the speed of the communication.

The data is received and written to the file.
If you do not have a memory extension installed, you may need to press CAS and STP
after the CP1 is ready, because the script is still waiting for the rest of the data.



kosmos_send.py filename.json
----------------------------

This is the counterpart to the kosmos_recv.py file. It sends compatible JSON file data to the CP1.
After you have started the script, press the CAL button on your CP1.

This transfer is a bit faster because we control the transfer. If
errors occur, try increasing the time_base parameter in the script.
Mine works fine with 15; a value of 33 is the original speed.



Fast cassette: --schnell
------------------------

```
kosmos_recv.py --schnell filename.json
kosmos_send.py --schnell filename.json [--von N] [--bis M]
```

Needs the CP1 running the "schnell" firmware (own code in 0x800-0xFFF, see the
EA adapter project: 8049 with EA = high, AT28C64B, A11 wired to P23). With it, the
whole memory (256 cells) is transferred in about 6-8 seconds instead of 7 minutes.

On the CP1:
- CAS: the bucket symbol ⊓ appears at once. Released: send all cells (000-127 or 000-255
  with expansion). Held: `_ __ ___` builds up on the right, after 1 s the display shows
  `⊓ Fr ___`; type the first cell, CAS, then `⊓ to ___`, type the last cell, CAS. Only this
  range is sent. CLR clears the input, STP aborts.
- CAL: the open bucket ⊔ appears and the CP1 waits for data. Only the cells contained in the
  transfer are overwritten, so you can e.g. load a subroutine library into cells 200-255.
- At the end the display shows `rdY`, or `⊓ Su Err` / `⊔ Su Err` on a checksum/format error.

Received partial ranges are saved as JSON with only these cells. `kosmos_send.py --schnell`
sends all cells of the file (they must be contiguous) or the range given by --von/--bis.
Press CAL on the CP1 first, then confirm on the Pi.

Sending re-runs itself with `sudo` to get real-time priority: on a Pi Zero, pulses
otherwise get up to 0.5 ms too long (measured), which breaks the 0.4/1.2 ms encoding.

Line protocol: idle high; one bit = low pulse, 0.4 ms = 1, 1.2 ms = 0, followed by at least
0.4 ms high (2 ms after each byte); LSB first. Frame: $C1, first cell, last cell, per cell
command + argument, CRC-8 (polynomial $07, init 0) over everything before.



Remote control: kosmos_remote.py
--------------------------------

```
kosmos_remote.py serve [--port 8049]     web page + API (keeps GPIO 26)
kosmos_remote.py anzeige                 print the display
kosmos_remote.py taste 0 0 0 pc run      press keys (name[:ms], e.g. cas:1500)
kosmos_remote.py laden file.json         press CAL and send
kosmos_remote.py speichern file.json [--von N --bis M]   press CAS and receive
```

Needs the "schnell" firmware 3.05 or later (4.01 for the flash). On the CP1, hold **RUN for 1 s**: the display shows
`rc on` (again: `rc oFF`). RUN pressed shortly still starts the program (on release). The
firmware shows its version (e.g. `4.01`) for one second at power-on.

Then the Pi can press keys and read the display, accumulator, PC and status at any time,
also while a program is running. The web page (http://bastelpi:8049/) shows the live display,
a keyboard like the CP1's (keys are held as long as you hold them, so CAS 1 s works), loads
assembler source or JSON (it presses CAL itself) and fetches memory (it presses CAS itself).
If a program drives terminal 8 of port 1 low permanently, the CP1 switches remote control off.

The timing is done by `kosmos_rc` (C, built with `gcc -O2 -o kosmos_rc kosmos_rc.c`), which
drives and samples the GPIO registers through /dev/gpiomem; Python on a Pi Zero is too slow for
the short reply pulses. It needs real-time priority: run the server as a systemd service with
`AmbientCapabilities=CAP_SYS_NICE` (user in group gpio). While the server runs, it owns
GPIO 26: use `kosmos_remote.py laden/speichern` or the web page instead of `--schnell`.

Protocol on the same line (P1.7, both sides only pull low):
- Pi knocks by pulling the line low. The CP1's timer interrupt (every 2.56 ms) only counts the
  ticks it sees low, it does not wait.
- 3.5 ms low (1-2 ticks) = status request: the CP1 sends internal RAM 0x20..0x3A (display, key
  buffer, accumulator, PC, status), one byte per interrupt, so the display keeps multiplexing.
- 8.5 ms low (3 ticks) = command: the CP1 blanks the display, waits for the release and reads
  4 bytes: bit = low pulse 150 µs = 1 / 750 µs = 0, 150 µs high, LSB first;
  byte 4 = b1 ^ b2 ^ b3 ^ $A5.
  - `01 zm dd` hold key: z = keyboard row (2..6), m = column mask, dd = frames of 15.36 ms
  - `02 aa nn` read nn bytes of internal RAM from aa
  - `03 aa ww` write internal RAM aa = ww (firmware 4.01; acknowledged like `01`)
- Reply, one byte per interrupt: data, then check byte (XOR ^ $A5); low pulse ~43 µs = 1 /
  ~125 µs = 0, ~43 µs high. `01` is acknowledged with the check byte only.
- Key codes of the firmware: digit d = d + 1, OUT 11, INP 12, CAL 13, STEP 14, STP 15, RUN 16,
  CAS 17, CLR 18, PC 19, ACC 20; row = (code + 7) / 4, bit = (code + 7) % 4.



SPI flash ("hard disk"): firmware 4.01
--------------------------------------

```
kosmos_remote.py flash                         directory (bank, start, name, autoboot)
kosmos_remote.py flash-speichern 12 "Rakete" [--start 20]   CP1 memory -> bank 12
kosmos_remote.py flash-laden 12                bank 12 -> memory, PC = start
kosmos_remote.py autoboot 12                   start bank 12 at power-on (0 = off)
```

The web page has the same functions in its "Flash" panel.

Hardware: an IS25LP016D (2 MB, 3.3 V) on port 1 terminals 1-4: P1.0 = CS#, P1.1 = SCK,
P1.2 = SI, P1.3 = SO. Supply from 5 V via 56 Ohm and a 3.3 V Zener diode (plus 10 µF and
100 nF); CS#, SCK and SI through 4.7 kOhm each (the flash's clamp diodes take the excess, the
Zener absorbs the current), SO through 1.5 kOhm to the 8049. WP# and HOLD# to 3.3 V.

The firmware no longer fits into 4 KB, so it uses both halves of the AT28C64B: **A12 is
driven by P1.4** (pin 31 of the 8049; on the adapter, cut the trace to terminal 5 and wire the
CPU side to the middle pin of JP3, jumper removed). Both halves contain the same lower 2 KB
(original code, interrupt, remote control); the upper 2 KB of half A (A12 = 1, EEPROM
0x1000-0x1FFF, selected after reset) hold the existing extensions, those of half B (EEPROM
0x0000-0x0FFF) the flash code. Switching happens in small stubs at the same address in both
halves (`ANL/ORL P1,#$10`). `OUT P1A` keeps P1.0-P1.4 and P1.7 at 1, so programs can only use
terminals 6 and 7 of port 1.

Storage: 256 banks of 256 cells (512 bytes). Each bank uses two 4 KB sectors alternately:
writing erases the free sector, copies the old contents over in 8-byte pieces, inserts the new
cells and finally marks the sector valid (generation counter), so a power failure never loses
the old version. Bank 0 is the directory: cell 0 = (00, autoboot bank), cell n = (00, start
of bank n). Name (16 ASCII characters) and generation are stored behind the cells. Writing
takes about 0.6 s, saving with directory entry about 1.3 s, reading 256 cells about 0.2 s.

On the CP1 (always 3 digits):
- `nnn CAS`: save memory to bank nnn, start = current PC (set it first with `xxx PC`).
  Display `5to nnn`, then `5to rdY`.
- `nnn CAL`: load bank nnn, PC = start (`LdA nnn`, then `P xxx`); RUN starts it.
- `nnn` + hold CAL for 1 s: autoboot bank nnn (`bot rdY`), `000` = off. At power-on the CP1
  shows `bot nnn` for 2 s (any key aborts), then loads and runs the bank.
- Errors: F-010 no flash answers, F-011 bank empty, F-003 bank 0 / invalid range, F-001 not
  3 digits.

New commands (firmware 4.01), parameters on the JSR/PSH stack:
- `36 PSK xxx` push the constant xxx
- `37 FRD xxx` pop count (0 = 256), first cell in the bank, bank; read these cells into memory from xxx
- `38 FWR xxx` the same in the other direction (bank 0 -> F-003)
- missing stack values -> F-009, no flash -> F-010
- `39 TSE 000` (firmware 4.02): accumulator = digit pressed since the last TSE, else 255; does not wait.
  VZG now remembers digit keys pressed while it waits, so a game loop with VZG + TSE never misses a key.

```
PSK 5      ; bank
PSK 123    ; first cell in the bank
PSK 10     ; 10 cells
FRD 80     ; -> memory 80..89
```

Remote jobs (used by the web page and the commands above): the Pi writes the parameters with
`03` (F_BANK 0x2C, F_SEKT 0x2D, F_OFH/F_OFL 0x2E/0x2F, name 0x60-0x6F), F_JOB (0x26) last, then
presses CAL; done when F_JOB is 0 again. Jobs: $01 read 16 raw bytes, $81 save memory with
name, $04 load, $08 autoboot, $10 find the next used bank from F_BANK. They only run while the
CP1 waits for keys (no program running).



kosmos_json_show.py filename.json
---------------------------------

Displays the contents of the JSON file in a decent way and shows the opcodes.



kosmos_disasm.php [-i] [-c] [-d] [-o] filename.json
---------------------------------------------------

Disassembles the JSON file and creates a KOA assembly language file.

Options:

```
       -c show code
       -d show description
       -i show inline numerics
       -o create filename.koa
```

By default kosmos_disasm displays only the assembly tokens and the labels it has
has recognized. Line numbers are omitted if possible:

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
With the option -c you may additionally view the decimal codes entered in the CP1 
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

With the -d option you can display the explanation for each command.
In the near future there may also be an English version for this:


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

The -o option writes the disassembled text to a KOA assembly language file.



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

This is the CP1 assembler. You can simply start with the CP1 mnemonics and use either numeric or symbolic parameters.
If you use symbolic parameters, you must declare them somewhere with a leading '>'.

You don't have to specify line numbers, if you do the assembler will try to assign them as you specified them.
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

As you can see, the assembler has beautified your code. You don't see any assembled code because you neither told the assembler
assembler neither to display it nor to write it to a file. 

With the -c option, you can see the code:

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

If you add the -d option, you will get a (German) explanation for each command:

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

Line numbers in parentheses are automatically assigned by the assembler.

If you like the beautified output, you can use the -r option to rewrite your source file with the beautified version.

Note: You can add comments by starting a line with '//'. These comments will be preserved by the assembler.
You can also add comments at the end of any line that starts with '//', but these will be retained in the
beautified output. It is recommended to use your own comment lines for this reason.

With the -o option you can instruct the assembler to write a JSON file for further use, e.g. for writing
to the CP1. If you use the option -s, the tool kosmos_send.py is called automatically and the transfer to the CP1 begins.


Installation and Prerequisites
------------------------------

The installation is pretty straightforward: just copy the files to any location in the file system of your Raspberry Pi
(recommended: /usr/local/bin) and set the execution flags (e.g. with chmod +x *.php *.py).
If you don't use /usr/local/bin, you should change the path at the end of the
of kosmos_asm.php:

```
if ($send) passthru("/usr/local/bin/kosmos_send.py $fo");
                     ^^^^^^^^^^^^^^^
```


The default Raspberry Pi operating system (formerly Raspbian, a Debian derivative) should include everything you need, perhaps with the exception of the php package
which has to be installed manually:

```
user@machine:# sudo apt update
user@machine:# sudo apt install php -y
```

