# EA adapter (hardware)

Adapter board that lets the CP1's 8049 run its code from an external EEPROM (EA high): the original
8049 stays in its socket on the adapter, the AT28C64B holds the (extended) firmware.

| File | Content |
|---|---|
| `adapter/cp1adapter.py` | generates the KiCad board (placement, netlist, own grid router, GND fills) – run with KiCad's Python |
| `adapter/cp1schaltplan.py` | generates the schematic (`schaltplan.svg` / `.pdf`) |
| `adapter/cp1-adapter.kicad_pcb` | the board (v1, produced at NextPCB) |
| `adapter/cp1-adapter-gerber.zip` | Gerber files as ordered |
| `adapter/top.png` | rendering of the top side |
| `cp1-stecker-dioden.png` | fix on the plug board: 4 × BAT42 in P20–P23 (keyboard columns must not pull A8–A11 high) |

Changes made after v1 (see `../docs/firmware-de.md` for details and photos of the reasoning):
- **remove C1** (22 pF at XTAL1) – the NMOS MCS-48 oscillator does not tolerate it;
- 4 × BAT42 in the keyboard column lines (picture above);
- jumper JP2 replaced by a wire A11 → P23 (4 KB address space);
- trace from pin 31 (P1.4) to terminal 5 cut, P1.4 drives A12 of the EEPROM (two 4 KB halves);
- SPI flash IS25LP016D on terminals 1–4, Pi on terminals 7/8 (see `../INTERNALS.md`).
