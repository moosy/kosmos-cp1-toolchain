# CP1 firmware 5.x and 6.x – sources

Sources of the extended CP1 firmware (currently 5.05). The original Kosmos ROM is copyrighted, so
**neither the original nor any built image is included**. The build patches the commented ROM
listing `cp1.asm` from Andreas Signer's emulator project (https://github.com/asig/kosmos-cp1);
put that file into this directory first.

```
firmware/
  cp1.asm            <- not included, copy it here from asig/kosmos-cp1
  asm48.py           own MCS-48 assembler (bit-exact with MAME cp1-2716 for the original)
  v5/                firmware 5.x (AT28C64B): sources, simulator, tests, review tools
  v6/                firmware 6.x (AT28C256): four block sources, build with stack check, simulator, tests,
                     routinen.py (routine list), pi/ = Pi software for 6.x (not yet deployed)
  history/schnell/   firmware 3.0x (fast cassette, remote control) - reference only
  history/flash4/    firmware 4.0x (SPI flash) - reference only, expects the old v4/ layout
```

Build 6.x (from this directory; German overview in ../docs/firmware6-de.md):

```
python3 v6/build6.py        # -> v6/cp1v6-eeprom.bin (32 KB for the AT28C256), cp1v6.sym; checks stack depth and space
sh v6/alle_tests.sh         # 19 test series in the simulator
python3 v6/routinen.py > ../docs/firmware6-routinen-de.md
```

SHA-256 of a correct 6.21 build starts with `e595c1d5` (6.20: `9bd7de80`).

Build 5.x (from this directory):

```
python3 v5/build5.py        # -> v5/cp1v5.bin (4 KB view), v5/cp1v5-eeprom.bin (8 KB for the AT28C64B), v5/cp1v5.sym
sh v5/alle_tests.sh         # all test series in the own 8049/8155/SPI flash simulator (slow on a Pi Zero)
```

The EEPROM image contains both 4 KB halves (A12 = P1.4, see INTERNALS.md). SHA-256 of a correct 5.05
build starts with `3e404bb0`.

Files in `v5/`:

| File | Content |
|---|---|
| `schnell5.asm` | half A, upper 2 KB: keys CAS/CAL/RUN, prompts, commands 25–39, browse, ASCII→segment, cold start |
| `flash5.asm` | half B, upper 2 KB: SPI flash, FNI, jobs |
| `rc_unten.asm`, `rc_seite1.asm`, `rc_seite3.asm`, `unten5.py` | changes in the lower 2 KB (NIE in the timer interrupt, reset, hooks into the original) |
| `stummel_a.asm`, `stummel_b.asm`, `gen_stummel.py` | switching stubs between the halves |
| `build5.py`, `packer.py` | build, gap filler (moves self-contained paragraphs into free page space) |
| `sim48.py`, `pi_fni.py` | simulator (8049, two 8155, keyboard, display, SPI flash) and a model of the Pi side |
| `test_*.py`, `alle_tests.sh` | tests; `test_remote5.py` runs `kosmos_remote.py` from the repository root against the simulator |
| `review/` | static checks: control flow, stack depth, call chains, cycle counts |
| `pruef4.py` | check that code crosses halves only through the stubs |

Comments and identifiers are German (the project language); the protocol is documented in English in
[../INTERNALS.md](../INTERNALS.md), the full German development history in [../docs/](../docs/).
