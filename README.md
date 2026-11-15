# kosmos-cp1-toolchain
Toolchain for the 1980s Kosmos-CP1 learning computer.

This is a toolchain for owners of the brilliant Kosmos-CP1 learning computer.
See https://de.wikipedia.org/wiki/Kosmos_CP1 for details.
A comprehensive collection of documentation can be found at 
http://www.8bit-homecomputermuseum.at/computer/kosmos_computer_praxis_cp1.html.

Quick reference (German, 3 pages A4, firmware 5.07 with all extensions): [cp1-schnelluebersicht.pdf](cp1-schnelluebersicht.pdf)

Firmware internals, the terminal 7/8 protocol (K78P) with NIE and FNI, jobs and flash layout: [INTERNALS.md](INTERNALS.md)

Everything else of the project is here too:
- [firmware/](firmware/) - sources of the extended firmware 5.x, own assembler, simulator and tests
  (the original ROM is copyrighted and not included; the build patches asig's `cp1.asm`)
- [hardware/](hardware/) - the EA adapter board (KiCad generator, board, Gerber, schematic)
- [docs/](docs/) - German project documentation (`firmware-de.md`) and the raw lab notebook (`laborbuch-de.md`)
- [examples/](examples/) - Rakete, Lauftext, Asteroiden; [cheatsheet/](cheatsheet/) - sources of the quick reference
- `kosmos-remote.service` - systemd unit for the web page

This toolchain consists of the following tools:

Firmware 5.07 in short
----------------------

The CP1 runs an extended firmware (own code in the 8049's upper address range, two halves of
an AT28C64B switched by P1.4, see "SPI flash" below). At power-on it shows its version
(`5.07`) for one second. Since 5.00 the original cassette is gone: CAS and CAL operate the SPI
flash, and the Raspberry Pi talks to the CP1 over port 1 terminals 7 and 8 at any time.

Wiring to the Pi (both lines with the same protection; the Pi only ever pulls low):

```
GPIO: --------o-----[1 kOhm]------ Port 1/8   (Pin 37 = BCM 26: data / remote control)
              |                    Port 1/7   (Pin 35 = BCM 19: clock for fast transfers)
            -----,
              ^     Zener diode 3,3 V
             / \
            -----
              |
GND:  --------o-------------------- GND
```

Beware: The CP1 is a 5V device, therefore the voltage to the Raspberry Pi must be limited.

Two transfer modes:
- **NIE** (normal, interrupt enabled): small things in the background, unnoticed, also while a
  program runs: display and status, key presses, internal RAM, single memory cells.
- **FNI** (fast, no interrupt): whole banks or parts of them, from/to memory or flash. The CP1
  switches its interrupt off for about a second and shows the direction on the right three
  digits: `C-P` CP1 -> Pi, `P-C` Pi -> CP1, `F-P` flash -> Pi, `P-F` Pi -> flash, then `rdY`
  (or `Err`). FNI jobs only start while the CP1 waits for keys; otherwise they are refused.

Reset (firmware 5.02): hold **CLR and press STP** on the CP1, or `kosmos_remote.py reset` / the
"Reset" button on the web page (NIE command `09 00 00`). Works also while a program runs. Same as
switching off and on: all memory is cleared (8049 RAM and both 8155), then version, `P 000` and
autoboot if set.

Decimal point (hardware mod): the DP segments of all digits are connected and driven by PA7
of the 8155 (pin 28) through the former overvoltage BC238C. In normal operation the firmware
lights a separator dot after the third digit (`P  .000`); SEG programs can use it freely.



kosmos_send.py / kosmos_recv.py
-------------------------------

```
kosmos_send.py filename.json                   JSON -> CP1 memory (FNI, about 1 s)
kosmos_recv.py filename.json [--von N --bis M] CP1 memory -> JSON (without range: 000 to memory size)
```

No key press on the CP1 is needed. If the server `kosmos_remote.py serve` runs, both go
through it, otherwise they use the GPIOs directly. Same as `kosmos_remote.py laden/speichern`.

Older firmware:
- `--kassette`: the original slow cassette (original firmware up to 4.x; press CAS or CAL on
  the CP1). Uses GPIO 26 with gpiozero (1.x and 2.x). Receiving takes about 3.5 min (7 min
  with memory expansion); sending is faster (`time_base` 15 instead of the original 33).
- `--schnell`: the fast cassette of firmware 3.05-4.x (`kosmos_schnell.py`; bit = low pulse
  0.4 ms = 1 / 1.2 ms = 0, frame $C1, first cell, last cell, cells, CRC-8).



Remote control: kosmos_remote.py
--------------------------------

```
kosmos_remote.py serve [--port 8049]     web page + API (keeps GPIO 26 and 19)
kosmos_remote.py anzeige                 print the display
kosmos_remote.py taste 0 0 0 pc run      press keys (name[:ms], e.g. cas:1500)
kosmos_remote.py laden file.json         file -> memory (FNI)
kosmos_remote.py speichern file.json [--von N --bis M]   memory -> file (FNI)
kosmos_remote.py zelle N [B A]           read cell N, or set it to B.A (NIE, also while a program runs)
kosmos_remote.py reset                   cold start like power-on, all memory cleared (5.02)
```

Remote control is always on. The web page (http://bastelpi:8049/) shows the live display,
accumulator and PC, has a keyboard like the CP1's (keys are held as long as you hold them, so
"CAS 1 s" works), one program editor and a name table, shows and edits single cells (optionally
following them live while a program runs) and has a flash panel (directory, load, save, autoboot).

The editor holds one program: fetch it from the CP1 memory, from a flash bank ("In Editor" in the
directory) or from a .koa/.json file; change it; then "Assemblieren" (check, relabel), "In CP1
laden", "Editor speichern" (directly into a bank, memory untouched) or save it as .koa/.json.
The name table beside it ("035=display_loop") gives the disassembler speaking labels. When you
assemble, it is rebuilt from the labels in the source (plus your own entries for cells without a
label). With firmware 5.03 the table is stored in the flash bank together with the program and
comes back with "In Editor". In a .koa download it is appended as `// 035=name` comment lines,
which the editor reads back when opening the file. The draft stays in the browser.

The timing is done by `kosmos_rc` (C, built with `gcc -O2 -o kosmos_rc kosmos_rc.c`), which
drives and samples the GPIO registers through /dev/gpiomem; Python on a Pi Zero is too slow.
It needs real-time priority: run the server as a systemd service with
`AmbientCapabilities=CAP_SYS_NICE` (user in group gpio).

NIE protocol (terminal 8 = P1.7, handled in the CP1's timer interrupt every 2.56 ms):
- The Pi knocks by pulling the line low. 3.5 ms = status request: the CP1 sends internal RAM
  0x20..0x3A (display, key buffer, accumulator, PC, status), one byte per interrupt.
- 8.5 ms = command: 4 bytes follow, bit = low pulse 50 µs = 1 / 150 µs = 0, at least 50 µs
  high, LSB first; byte 4 = b1 ^ b2 ^ b3 ^ $A5. Replies: one byte per interrupt, low pulses
  ~50 / ~150 µs, then the check byte (XOR ^ $A5).
  - `01 zm dd` hold key: z = keyboard row (2..6), m = column mask, dd = frames of 15.36 ms
  - `02 aa nn` read nn bytes of internal RAM from aa; `03 aa ww` write internal RAM aa = ww
  - `04 jj 00` start job jj (attention). Reply = F_JOB: jj = accepted. For FNI jobs the
    acceptance is "terminal 7 goes low" instead.
  - `05 aa nn` / `06 aa nn` read nn bytes from byte address aa of the internal / CP3 8155,
    `07 aa ww` / `08 aa ww` write one byte (cell z = bytes 2z and 2z+1; CP3 = cells 128-255)
  - `09 00 00` reset like power-on (5.02, no reply)
- Key codes of the firmware: digit d = d + 1, OUT 11, INP 12, CAL 13, STEP 14, STP 15, RUN 16,
  CAS 17, CLR 18, PC 19, ACC 20; row = (code + 7) / 4, bit = (code + 7) % 4.

FNI protocol (interrupt off): terminal 7 = T (P1.6, clock), terminal 8 = D (P1.7, data).
- Per bit the Pi pulls T low (at least 80 µs); the CP1 holds T low as long as it is busy
  (erasing the flash may take a while). Then T is high for at least 100 µs. D low = 0, LSB first;
  the sender sets D, the CP1 polls T about every 22.5 µs (details in INTERNALS.md).
- Head [job, bank, first cell, count] + CRC-8, then blocks up to the next 4-cell boundary
  (2 bytes per cell) + CRC-8 (polynomial $07, init 0). After each block the receiver answers
  one bit: 1 = ok, 0 = repeat (3 tries on the CP1 side).
- Parameters, written with `03` before the `04`: F_BANK 0x2C, F_ANF 0x3C, F_ANZ 0x3D
  (0 = 256), F_START 0x3E (255 = no directory entry), name 0x60-0x6F. Result in F_JOB (0x26):
  0 = ok, $EE = error/refused.
- Jobs: $20 Pi -> memory, $21 memory -> Pi, $22 / $23 Pi -> flash (without / with name),
  $24 flash -> Pi, $25 whole bank -> Pi (256 cells, then 0x200-0x5FF of the sector: name,
  generation, valid, name table; 128 blocks of 8), $26 all names (per used bank a block
  [bank, 0, name 0-5], [name 6-13], [name 14-15]; end = block of 8 zeros), $29 Pi -> flash with
  name and name table (5.03: after the cell blocks 96 blocks of 8 for 0x300-0x5FF).
  The directory is read with $24 of bank 0 plus $26.
- Jobs with interrupt on: $04 load bank, $08 autoboot, $80/$81 memory -> bank (with name).
  ($01 raw read and $10 find bank were dropped in 5.03.)



SPI flash ("hard disk")
-----------------------

```
kosmos_remote.py flash                         directory (bank, start, name, autoboot)
kosmos_remote.py flash-speichern 12 "Rakete" [--start 20]   CP1 memory -> bank 12
kosmos_remote.py flash-laden 12                bank 12 -> memory, PC = start
kosmos_remote.py autoboot 12                   start bank 12 at power-on (0 = off)
kosmos_remote.py bank-sichern 12 file.json     bank 12 -> file directly (memory untouched; names -> file.json.namen)
kosmos_remote.py bank-einspielen 12 file.json ["Name"] [--start 20] [--namen file.namen]   file -> bank 12 directly
```

Hardware: an IS25LP016D (2 MB, 3.3 V) on port 1 terminals 1-4: P1.0 = CS#, P1.1 = SCK,
P1.2 = SI, P1.3 = SO. Supply from 5 V via 56 Ohm and a 3.3 V Zener diode (plus 10 µF and
100 nF); CS#, SCK and SI through 4.7 kOhm each (the flash's clamp diodes take the excess, the
Zener absorbs the current), SO through 1.5 kOhm to the 8049. WP# and HOLD# to 3.3 V.

The firmware no longer fits into 4 KB, so it uses both halves of the AT28C64B: **A12 is
driven by P1.4** (pin 31 of the 8049; on the adapter, cut the trace to terminal 5 and wire the
CPU side to the middle pin of JP3, jumper removed). Both halves contain the same lower 2 KB
(original code, interrupt, remote control); the upper 2 KB of half A (A12 = 1, EEPROM
0x1000-0x1FFF, selected after reset) hold the key handling and extensions, those of half B
(EEPROM 0x0000-0x0FFF) the flash and FNI code. Switching happens in small stubs at the same
address in both halves (`ANL/ORL P1,#$10`). `OUT P1A` keeps P1.0-P1.4 and P1.6/P1.7 at 1, so
programs can only use terminal 6 of port 1.

Storage: 256 banks of 256 cells (512 bytes). Each bank uses two 4 KB sectors alternately:
writing erases the free sector, copies the old contents over in 8-byte pieces, inserts the new
cells and finally marks the sector valid (generation counter), so a power failure never loses
the old version. Bank 0 is the directory: cell 0 = (00, autoboot bank), cell n = (00, start
of bank n). Name (16 ASCII characters) and generation are stored behind the cells.
Firmware 5.03: 0x300-0x5FF of the sector hold the name table (5.05: the last 8 bytes, 0x5F8-0x5FD, are the
bank's own 6-digit display for browsing) (per entry: length, cell, name in
ASCII; FF = end; 768 bytes, about 70 names of 8 characters). Byte 0x212 = 00 marks a bank with
names. Only then the copy runs up to 0x5FF (about 1.7 s longer), otherwise it stops at 0x217
as before.

On the CP1 (always 3 digits; CLR clears the input, STP aborts):
- CAS short: `bAn ___`, type nnn, CAS: memory -> bank nnn, start = current PC (set it first
  with `xxx PC`). Display `5to rdY`.
- CAS held 1 s: `Fr ___`, `to ___` (cells of memory), `bAn ___`, `d5t ___` (first cell in the
  bank), each confirmed with CAS. Only pressing CAS takes the default (whole memory, cell 0).
  The rest of the bank stays, the directory is not touched.
- CAL short (5.05): browse the used banks. Each shows `bAn nnn` for a moment, then its own 6-digit
  display (set on the web page, field "Anzeige") or the first letters of its name. CAL again = next
  bank (after the last one it starts again; that step takes ~1.6 s), hold CAL 1 s = load it (PC = start,
  `P xxx`; RUN starts it), digits = the usual `bAn ___` input, STP = cancel.
- CAL held 1 s: `bAn ___`, `Fr ___`, `to ___` (cells in the bank), `d5t ___` (cells of
  memory). PC stays, display `LdA rdY`.
- RUN held 1 s: `bot ___`, nnn RUN: autoboot bank nnn (`bot rdY`), `000` = off. At power-on
  the CP1 shows `bot nnn` for 2 s (any key aborts), then loads and runs the bank.
- Errors: F-010 no flash answers, F-011 bank empty, F-003 bank 0 / invalid range, F-001 not
  3 digits.

New commands (firmware 4.01), parameters on the JSR/PSH stack:
- `36 PSK xxx` push the constant xxx
- `37 FRD xxx` pop count (0 = 256), first cell in the bank, bank; read these cells into memory from xxx
- `38 FWR xxx` the same in the other direction
- bank 000 (firmware 5.07) = the program's own bank, i.e. the bank it was loaded from (no own bank: F-003)
- missing stack values -> F-009, no flash -> F-010
- `39 TSE 000` (firmware 4.02): accumulator = digit pressed since the last TSE, else 255; does not wait.
  VZG now remembers digit keys pressed while it waits, so a game loop with VZG + TSE never misses a key.

```
PSK 5      ; bank
PSK 123    ; first cell in the bank
PSK 10     ; 10 cells
FRD 80     ; -> memory 80..89
```

```
PSK 0      ; own bank (5.07)
PSK leben  ; first variable
PSK 16     ; 16 cells
FRD leben  ; -> all start values back, e.g. for a new game (4 cells instead of one AKO/ABS pair each)
```

Firmware 5.06: commands with a fixed value and pictures from flash
- `40`–`46`: `ADD #n`, `SUB #n`, `VGL #n`, `VGR #n`, `VKL #n`, `UND #n`, `ODR #n` – like the normal
  commands, but n is the value itself instead of a cell (no constant cells needed any more).
- `47 SEF xxx`: show 6 picture bytes from the program's own bank (stored in the flash sector, not in
  the 256 cells). Pictures are defined on the web page (field "Bilder", e.g. `titel=MInEn`,
  `lauf=  HALLO CP1  `, `#1,2,3` for raw segment values) and written with "Editor speichern"; in the
  program you write `SEF titel`, `SEF lauf+3` or `ADD #lauf` – the assembler fills in the numbers.
  `SEF 254` takes the position from the accumulator (scrolling text in a loop), `SEF 248` shows the
  bank's own browse display, `SEF 255` clears. About 12 ms per picture.
- The JSR/PSH stack has 23 levels since 5.06.

Example: `examples/minenflug.koa` – a little game with mines, shots, LED bars on ports 2 and 4 and
pictures (bank 8 on Michael's CP1). Details of all commands and data formats: [INTERNALS.md](INTERNALS.md).

Demos: `8 RUN` reaction test, `9 RUN` countdown.



kosmos_json_show.py filename.json
---------------------------------

Displays the contents of the JSON file in a decent way and shows the opcodes.



kosmos_disasm.php [-i] [-c] [-d] [-o] [-n names.txt] filename.json
-----------------------------------------------------------------

Disassembles the JSON file and creates a KOA assembly language file.

Options:

```
       -c show code
       -d show description
       -i show inline numerics
       -o create filename.koa
       -n name table: one "035=display_loop" per line; these names are used instead of
          label_N / wert_N, and every named cell gets a label (even if nothing refers to it)
```

Every label line shows the cell number it stands for (`>display_loop:          035`). It is
only for reading: the assembler ignores everything behind the label and writes the current
number again with `-r` (relabel), so moving code never causes a conflict.

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
The beautified output (and -r) puts the current cell number behind every label, so you see where things landed.
Several labels in a row all name the same cell.

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


For the remote control, build the timing helper and run the server as a service:

```
user@machine:# gcc -O2 -o kosmos_rc kosmos_rc.c
```

```
# /etc/systemd/system/kosmos-remote.service
[Unit]
Description=Kosmos CP1 remote control (web page port 8049)
After=network-online.target

[Service]
User=pi
SupplementaryGroups=gpio
WorkingDirectory=/home/pi/kosmos-cp1-toolchain
ExecStart=/usr/bin/python3 /home/pi/kosmos-cp1-toolchain/kosmos_remote.py serve
AmbientCapabilities=CAP_SYS_NICE
CapabilityBoundingSet=CAP_SYS_NICE
NoNewPrivileges=true
Restart=on-failure

[Install]
WantedBy=multi-user.target
```
