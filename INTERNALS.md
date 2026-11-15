# Kosmos CP1 – firmware 5.x internals

This document describes how the extended CP1 firmware (5.00–5.07) talks to the outside world,
mainly the **K78P** – the *terminal 7 and 8 protocol* between the CP1 and a Raspberry Pi – and the
data structures behind it. It is meant for people who want to write their own tools, or just want
to understand what happens on the two wires.

The firmware itself is not published here (it is a patched version of the original Kosmos ROM, which
is copyrighted). Everything below can be implemented on the Pi side without it; the reference
implementation is `kosmos_rc.c` (timing) and `kosmos_remote.py` (commands, jobs, data formats).

Contents:
1. Hardware overview
2. Memory map (EEPROM halves, internal RAM)
3. K78P physical layer
4. NIE – normal, interrupt enabled (terminal 8 only)
5. FNI – fast, no interrupt (terminals 7 + 8)
6. Jobs (F_JOB)
7. SPI flash layout (banks, directory, names, pictures, display)
8. Keys, display, segment codes
8a. Commands added in 5.x (immediate values, SEF, own bank)
9. Reset
10. Lessons learned


## 1. Hardware overview

| Part | Function |
|---|---|
| M5L8049 / 8049 (4 MHz, 15 clocks per cycle = 3.75 µs) | CPU, runs from external EEPROM (EA high) |
| 8155 internal | 128 cells of CP1 memory (2 bytes each), keyboard, display |
| 8155 on the CP3 memory expansion (optional) | cells 128–255 |
| AT28C64B (8 KB) | firmware, two 4 KB halves selected by A12 = **P1.4** |
| IS25LP016D (2 MB SPI, 3.3 V) | "hard disk": 256 banks of 256 cells |
| Port 1 terminals 1–4 | P1.0 CS#, P1.1 SCK, P1.2 SI, P1.3 SO (flash) |
| Port 1 terminal 5 | P1.4 = A12 of the EEPROM (trace cut, wired to JP3 middle) |
| Port 1 terminal 6 | P1.5, the only terminal left for user programs (`P1A`) |
| Port 1 terminal 7 | P1.6 = **T** (K78P clock) – Pi pin 35 = BCM 19 |
| Port 1 terminal 8 | P1.7 = **D** (K78P data) – Pi pin 37 = BCM 26 |
| 8155 PA7 (pin 28) | decimal points of all digits (former overvoltage LED transistor) |

Both K78P lines are open-drain style: **nobody ever drives them high.** The 8049's quasi-bidirectional
port pins have weak pull-ups; the Pi side switches its GPIO between "output low" and "input".
Each line: GPIO node with a 3.3 V Zener diode to GND and 1 kΩ to the terminal.

`OUT P1A` (command 17) keeps P1.0–P1.4, P1.6 and P1.7 at 1, so a user program can neither select
the flash, switch EEPROM halves nor jam the K78P lines.


## 2. Memory map

### EEPROM

```
EEPROM 0x0000-0x07FF  half B, lower 2 KB  \  identical: original code, timer interrupt,
EEPROM 0x1000-0x17FF  half A, lower 2 KB  /  NIE receiver, reset handler
EEPROM 0x0800-0x0FFF  half B, upper 2 KB     flash and FNI code
EEPROM 0x1800-0x1FFF  half A, upper 2 KB     key handling (CAS/CAL/RUN), new commands 25-39,
                                             browse, ASCII->segment table, cold start
```

After reset P1.4 = 1, so half A is active. The 8049 only sees 4 KB (A11 = P23 is wired as the highest
address line); the halves are switched by `ANL/ORL P1,#$10` in small *stubs* near 0xFA7 that contain
the same bytes in both halves (`ANL/ORL`, `NOP`, `JMP target`). Only `JMP` through a stub may cross
halves, never `CALL`/`RET`. Because the interrupt and the original routines live in the lower 2 KB of
both halves, an interrupt can come at any time.

### Internal RAM of the 8049 (128 bytes)

| Address | Use |
|---|---|
| 0x00–0x07 | register bank 0 |
| 0x08–0x15 | 8049 hardware stack (only 7 of 8 levels are ever used) |
| 0x16 | LEER: 1 = firmware waits for keys (idle). Set by `wait_key`, cleared by all prompts |
| 0x17 | AUFTRAG: key code handed over from the interrupt (NIE `04`) |
| 0x18–0x1F | register bank 1 (interrupt); R6' = 0x1E = last new key (~15 ms) |
| 0x20–0x25 | display, 6 bytes of segment patterns (digit 1..6), bit 7 = decimal point |
| 0x26 | F_JOB: job number / result (0 = done, $EE = error or refused) |
| 0x27–0x2A | key buffer (KBUF) |
| 0x2C | F_BANK |
| 0x2D–0x2F | F_SEKT, F_OFH, F_OFL (flash address while working) |
| 0x30–0x35 | key state per keyboard row (interrupt) |
| 0x36–0x37 | accumulator (command, argument) |
| 0x38 | PC |
| 0x3A | status flags |
| 0x3B | MEM_SIZE (127 or 255) |
| 0x3C | F_ANF: first cell |
| 0x3D | F_ANZ: number of cells (0 = 256) |
| 0x3E | F_START: start address for the directory (255 = leave the directory alone) |
| 0x45 | stack pointer of the CP1 stack (JSR/RET/PSH/POP/PSK) |
| 0x46 | RC_FLAG (NIE state) |
| 0x47 | OVF switch |
| 0x48–0x5E | CP1 stack, 23 levels (24 before 5.06) |
| 0x5F | S_PBANK (5.06): bank the running program was loaded from, 0 = none (typed in) |
| 0x60–0x6F | F_NAME: bank name, 16 ASCII characters |
| 0x70–0x77 | F_PUF: flash buffer |
| 0x78–0x7F | NIE buffers / FNI block buffer |

The firmware clears 0x16/0x17 and 0x48–0x7F at power-on (5.04; before that random RAM could be
taken for a key code).


## 3. K78P physical layer

Two lines, both idle high, both only ever pulled low:

- **D** = terminal 8 = P1.7 = Pi pin 37 / BCM 26 – data, used alone by NIE
- **T** = terminal 7 = P1.6 = Pi pin 35 / BCM 19 – clock, only used by FNI

**NIE** runs inside the CP1's timer interrupt (every 2.56 ms, the display multiplex): pulse-length
coding on D, one reply byte per interrupt. Programs keep running, the display keeps working.

**FNI** switches the interrupt off and clocks bits with T in an I²C-like handshake (the CP1 stretches
the clock while it is busy). About 10 times faster, but the CP1 is deaf to keys during the transfer and
shows only the direction on the display.

An FNI transfer is always started by NIE: parameters are written with `03`, then `04 jj` hands the
job to the CP1, which switches to FNI by pulling T low.


## 4. NIE – normal, interrupt enabled

### Knocking

The Pi pulls D low. The interrupt counts the interrupt periods in which D is low and **does not wait**:

| Low time (Pi) | Meaning |
|---|---|
| 3.5 ms (1–2 periods) | status request: the CP1 answers with internal RAM 0x20..0x3A (27 bytes) |
| 8.5 ms (3 periods) | command: the interrupt now waits for D to go high and reads 4 bytes |

The status request does not disturb the display at all, so the web page polls it continuously.

### Command frame (Pi → CP1)

After the long knock and ~300 µs high: 4 bytes, LSB first, each bit a low pulse
**50 µs = 1, 150 µs = 0** (threshold 100 µs, measured in steps of 20 µs), followed by ≥ 50 µs high.

```
byte 1   command
byte 2   a
byte 3   b
byte 4   byte1 ^ byte2 ^ byte3 ^ $A5      (wrong check byte: command ignored)
```

### Reply (CP1 → Pi)

After ~2.6 ms, **one byte per interrupt** (the display keeps running in between): same coding
(low ~50 µs = 1, ~150 µs = 0, ~50 µs high), LSB first. After the data comes a check byte
(XOR of all data bytes ^ $A5). Commands without data reply with just $A5.

### Commands

| Cmd | a | b | Action | Reply |
|---|---|---|---|---|
| `01` | zm: row z (2..6) << 4 \| column bit m | dd | hold the key for dd frames of 15.36 ms | $A5 |
| `02` | address aa | count nn | read internal RAM aa..aa+nn-1 | nn bytes |
| `03` | address aa | value ww | internal RAM aa = ww | $A5 |
| `04` | job jj | 00 | hand job jj to the main loop (only when idle, LEER = 1) | F_JOB (= jj: accepted) |
| `05` | byte address | count | read bytes of the internal 8155 | nn bytes |
| `06` | byte address | count | read bytes of the CP3 8155 (cells 128–255) | nn bytes |
| `07` | byte address | value | write one byte of the internal 8155 | $A5 |
| `08` | byte address | value | write one byte of the CP3 8155 | $A5 |
| `09` | 00 | 00 | cold start like power-on (5.02) | none |

Key `01`: row = (code + 7) / 4, column bit = 1 << ((code + 7) % 4), see section 8 and `taste_zm()` in
`kosmos_remote.py`. Example: RUN (code 16) = row 5, bit 3 → `01 58 07` holds RUN for ~100 ms.

Cell z of the CP1 memory is bytes 2z (command) and 2z+1 (argument) of its 8155; the CP3 8155 holds
cells 128–255 at byte addresses 2(z-128).

`04` is only accepted while the firmware waits for keys (LEER = 1, idle). The interrupt then puts
the CAL key code into AUFTRAG (0x17), and `wait_key` returns it like a real key press; the CAL
handler finds F_JOB ≠ 0 and runs the job. While a program runs, or during any prompt, the job is
refused (reply ≠ jj) – a running program is never interrupted by a transfer.

If D stays low for far too long (e.g. something on terminal 8 pulls it down), the receiver switches
itself off (emergency stop in RC_FLAG) until the next reset.

### Status block (reply to the short knock)

27 bytes = internal RAM 0x20..0x3A; offset = address − 0x20:

| Offset | Content |
|---|---|
| 0x00–0x05 | display segments, digit 1..6 |
| 0x06 | F_JOB |
| 0x10–0x15 | key state per row |
| 0x16–0x17 | accumulator (command, argument) |
| 0x18 | PC |
| 0x1A | status |


## 5. FNI – fast, no interrupt

### Start

1. Pi writes the parameters with NIE `03` (F_BANK, F_ANF, F_ANZ, F_START, F_NAME …) and finally
   sets F_JOB = 0.
2. Pi sends `04 jj 00` and immediately releases both lines and watches T.
3. **Acceptance = T goes low** (within ~300 ms). The `04` reply may be lost because the CP1 switches
   its interrupt off at that moment – it is not needed.
4. The CP1 shows `Q-Z` on the right three digits (C = CP1 memory, P = Pi, F = flash, e.g. `P-F`)
   and runs its own display loop (~66 Hz) between blocks.

### Bits

```
          Pi pulls T low           CP1 holds T low while busy, then releases
T  ‾‾‾‾‾‾\_________________________/‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾\______ ...
         |<-- >= 80 µs (Pi) ------>|<-- >= 100 µs -->|
D  ===X====== stable ===========X====
```

- The CP1 releases T, waits for T high, then for T low (the Pi's clock pulse), and grabs T itself.
- **CP1 receives:** the Pi sets D (low = 0, released = 1) *before* pulling T low; the CP1 samples D
  after it has grabbed T.
- **CP1 sends:** the CP1 sets D while it holds T and then releases T; the Pi reads D *after* T has
  gone high again.
- Bytes are LSB first.
- The CP1 polls T in a loop of 22.5 µs and may need up to ~45 µs to grab it, so the Pi uses
  **T low ≥ 80 µs and T high ≥ 100 µs** (5.04; 40/40 µs failed on long transfers). Longer is always
  fine – the protocol is not time critical on either side, the CP1 gives up after ~200 ms per bit.
- While the CP1 holds T (erasing a 4 KB flash sector, copying), the Pi must simply wait (up to
  several seconds).

### Frames

```
head:   [job, bank, first cell, count] CRC-8      -> ack bit
block:  [2 bytes per cell ...] CRC-8               -> ack bit
...
```

- CRC-8: polynomial $07, initial value 0, over the bytes of the block.
- Blocks end at 4-cell boundaries (≤ 8 bytes): the first block runs from the first cell to the next
  multiple of 4, the last one may be shorter.
- After each block (and after the head) the **receiver** sends one ack bit: 1 = ok, 0 = send again.
  Both sides try **3 times**, then give up (the Pi must not try more often than the CP1, otherwise
  it keeps clocking into a CP1 that has already left FNI).
- The head is always sent in transfer direction; when the CP1 sends, the Pi compares the received
  head with its own parameters.
- At the end the CP1 releases both lines, switches the interrupt back on and shows `rdY` or `Err`.
  F_JOB = 0 (ok) or $EE (error). The Pi waits until T is high, then polls F_JOB via NIE.

### Extra data after the cells

| Job | After the cell blocks |
|---|---|
| `$25` | bank header and name area 0x200..0x5FF of the sector: 128 blocks of 8 bytes |
| `$29` | name area 0x300..0x5FF (incl. display at 0x5F8): 96 blocks of 8 bytes, Pi → CP1 |
| `$26` | no cells: per used bank 3 blocks `[bank, 0, name 0..5]` `[name 6..13]` `[name 14..15]`, end = block of 8 zeros |


## 6. Jobs (F_JOB)

Parameters are written with NIE `03`, the job is started with `04 jj 00`.

**FNI (interrupt off):**

| Job | Direction | Parameters | Display |
|---|---|---|---|
| `$20` | Pi → CP1 memory | F_ANF, F_ANZ | `P-C` |
| `$21` | CP1 memory → Pi | F_ANF, F_ANZ | `C-P` |
| `$22` | Pi → flash bank (keep name) | F_BANK, F_ANF, F_ANZ, F_START | `P-F` |
| `$23` | Pi → flash bank with name | + F_NAME | `P-F` |
| `$24` | flash bank → Pi | F_BANK, F_ANF, F_ANZ | `F-P` |
| `$25` | whole bank → Pi (cells + 0x200..0x5FF) | F_BANK | `F-P` |
| `$26` | all bank names → Pi | – | `F-P` |
| `$29` | Pi → flash with name and name area (5.03) | like `$23` | `P-F` |

The directory is read in one go as `$24` of bank 0 plus `$26`.

**With interrupt (normal operation, shows the header on the display like the keys do):**

| Job | Action |
|---|---|
| `$04` | load bank F_BANK into memory, PC = start (`LdA nnn`) |
| `$08` | autoboot bank = F_BANK, 0 = off (`bot nnn`) |
| `$80` | memory → bank F_BANK, start = PC (`5to nnn`) |
| `$81` | the same with name F_NAME |

Bit 3 of the job number marks "with name area" (`$29`), so `ANL A,#$09` handles it without extra code.
(`$01` raw read and `$10` find bank existed in 4.x/5.0x and were dropped in 5.03.)

Errors: F_JOB = $EE. On the device a refused or failed job shows `Err` (FNI) or the usual
`F 0nn` codes (F 003 bank 0 / invalid range, F 010 no flash, F 011 bank empty).


## 7. SPI flash layout

- Bank b (0..255) owns two 4 KB sectors starting at b × 8 KB. Only one of them is valid.
- Writing: erase the free sector, copy the old contents over in 8-byte pieces while inserting the new
  bytes, finally write the *valid* byte. A power failure therefore never loses the old version.
- Bank 0 is the directory: cell 0 = (00, autoboot bank), cell n = (00, start address of bank n).

Sector layout:

| Offset | Content |
|---|---|
| 0x000–0x1FF | 256 cells × 2 bytes (command, argument) |
| 0x200–0x20F | name, 16 ASCII characters (FF = none) |
| 0x210 | generation (+1 per write; the newer sector wins) |
| 0x211 | 00 = valid |
| 0x212 | 00 = bank has a name area (set by `$29`); the copy then runs to 0x5FF, otherwise it stops at 0x217 |
| 0x300–0x5F7 | name area: entries `[length, cell, ASCII name]`, FF = end (~70 names of 8 characters); pictures from the top |
| 0x500–0x5F7 | pictures for SEF (5.06), packed directly below 0x5F8, growing down into the name area |
| 0x5F8–0x5FD | own 6-digit display for browsing (5.05): segment patterns, FF = none |

The name area is the "name table" of the editor (`035=display_loop`): cell numbers with labels for
the disassembler. The firmware itself never interprets it, it only keeps it when the bank is
rewritten from the keyboard.

Pictures (5.06): the firmware only knows "SEF xxx reads the 6 bytes at sector offset 0x500 + xxx". The
Pi side packs the pictures without gaps directly below the own display (0x5F8), so names (from 0x300
upwards) and pictures (from 0x5F7 downwards) share the space. Each picture also gets an entry in the
name list, `[length, SEF position, "@" + name]`, so that the editor gets the picture names back;
older readers skip these entries. Pictures shorter than 6 bytes are padded with 0 (dark).


## 8. Keys, display, segment codes

Key codes (as returned by `wait_key`): digit d = d + 1, OUT 11, INP 12, CAL 13, STEP 14, STP 15,
RUN 16, CAS 17, CLR 18, PC 19, ACC 20. Keyboard row = (code + 7) / 4, bit = (code + 7) % 4.
The interrupt remembers one key per row only – two keys in the same row cannot be combined.

Segment bits: a = 1, b = 2, c = 4, d = 8, e = 16, f = 32, g = 64, decimal point = 128.

5.05 contains an ASCII → segment table (since 5.06 only 0x2C..0x5F – `, - . /`, digits, `: ; < = > ? @`,
letters, `[ \ ] ^ _`; lower case mapped to upper case, everything else dark) used when browsing banks without an own display. The same table is used by
`anzeige_aus_text(..., wie_firmware=True)` in `kosmos_remote.py` for the preview.

Display headers of the firmware: `bAn ___` bank, `Fr ___` / `to ___` range, `d5t ___` destination,
`5to nnn` storing, `LdA nnn` loading, `bot nnn` autoboot, `Q-Z` FNI direction, `rdY`, `Err`.


## 8a. Commands added in 5.x

| Code | Mnemonic | Since | Meaning |
|---|---|---|---|
| 25 | ODR xxx | 3.0 | accumulator OR cell xxx |
| 26 | OVF x | 3.0 | x = 0: ADD/SUB wrap around (no F 006), else overflow error on |
| 27 | SEG xxx | 3.0 | cells xxx..xxx+5 as segment patterns on the display, SEG 255 clears |
| 28–30 | AS1/AS2/AS3 xxx | 3.0 | hundreds/tens/ones of the accumulator as segment pattern into cell xxx |
| 31 | TST | 3.0 | wait for a digit key |
| 32/33 | JSR xxx / RET | 3.0 | subroutine |
| 34/35 | PSH / POP | 3.0 | accumulator to/from the stack |
| 36 | PSK xxx | 4.0 | push constant |
| 37/38 | FRD xxx / FWR xxx | 4.0 | stack: bank, first cell, count; read/write flash ↔ memory from cell xxx |
| 39 | TSE | 4.02 | digit pressed since the last TSE, else 255 (does not wait) |
| 40–46 | ADD# SUB# VGL# VGR# VKL# UND# ODR# | 5.06 | like 07/08/10/12/13/15/25, but xxx is the value itself (assembler: `ADD #1`) |
| 47 | SEF xxx | 5.06 | 6 picture bytes from position xxx of the program's own bank onto the display |

Details:
- **40–46** jump into the original ADD/SUB/VGL/VGR/VKL routines right behind their operand-cell check;
  `MOVX A,@R1` there then reads the argument of the instruction itself. OVF, the comparison result and
  F 005 (accumulator not data) behave exactly as with the cell variants; ADD # leaves the comparison
  result alone, as ADD does.
- **SEF xxx**: reads from the bank the program was loaded from (S_PBANK, set by every successful bank
  load: CAL, autoboot, Pi job $04; the web page sets it via NIE `03 5F bb` when it loads the editor
  program). No own bank (typed in) → dark, no error. `SEF 248` = the bank's own browse display,
  `SEF 254` = position taken from the accumulator (scrolling text / animation in a loop),
  `SEF 255` clears the display. About 12 ms per picture (flash sector search + 6 bytes).
- **FRD/FWR with bank 000** (5.07) = the program's own bank (S_PBANK); without own bank F 003 (before
  5.07: FRD read the directory, FWR gave F 003). Typical uses: reload all start values with
  `PSK 0 / PSK first / PSK n / FRD first` (4 cells instead of one AKO/ABS pair per variable), or keep a
  high score in the program's own bank. FWR rewrites the whole sector including names and pictures
  (a few seconds), so use it at the end of a game, not in the loop.
- The CP1 stack has 23 levels since 5.06 (the 24th byte holds S_PBANK).


## 9. Reset

Firmware 5.02 has a cold start that is identical to power-on (all 8049 RAM and both 8155 cleared,
version, autoboot):

- On the CP1: **hold CLR and press STP.** The STP entry of the original jump table points to three
  free bytes after the `RETR` at 0x003, which jump to half A; there the key state of the
  CAS/CLR/PC/ACC row is checked (CLR = code 18).
- From the Pi: NIE `09 00 00` (no reply), also while a program runs. Inside the interrupt the firmware
  executes `CALL $003` so that the `RETR` there ends the interrupt state cleanly – otherwise no
  further interrupt would ever come – then restores port 1, selects half A and jumps to the cold start.

A hardware reset line would not clear the 8155 RAM; the original `init` does that.


## 10. Lessons learned

- **Never trust the simulator's power-on state.** The 8049's RAM is random at power-on; 5.00–5.03
  sometimes took garbage in 0x17 for a key press (`F 004`). The test suite now starts from random RAM.
- **Understand the timing before adding checks.** An extra "is the CP1 holding T?" check on the Pi
  broke every transfer, because in the byte loops the CP1 legitimately releases T before the Pi does.
- **Retry counts must match on both sides.** With 4 Pi tries against 3 on the CP1, the Pi kept
  clocking after the CP1 had given up – the resulting bit storm on D tripped the NIE emergency stop.
- **Reset F_JOB before every attempt.** Otherwise the $EE of a failed attempt is read as "refused".
- On the 8049 a conditional jump uses the page of its *operand byte* (pc + 1) – matters at page ends.
- **Check every boundary of the image, not just the one you expect.** While building 5.06 the code of
  half A ran past 0xFFF into a region the build never looked at; the image would simply have lacked
  that code. The build now checks the whole range.
