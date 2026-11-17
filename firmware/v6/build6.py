# Firmware 6.x für den AT28C256: Original + Haken (wie 5.x), obere Blöcke aus BLOECKE, gemeinsame Sprungtabelle
import os
AUS=os.environ.get('AUS','v6/cp1v6')
RC_UNTEN=os.environ.get('RC_UNTEN','v6/rc_unten.asm')
RC_SEITE3=os.environ.get('RC_SEITE3','v6/rc_seite3.asm')
# baut cp1schnell.asm aus cp1.asm + schnell.asm, assembliert, vergleicht mit dem Original
import sys, re, subprocess, hashlib
src=open('cp1.asm',encoding='latin-1').read()
def rep(a,b):
    global src
    assert src.count(a)==1, a
    src=src.replace(a,b)
rep("cas_handler:    CALL clear_display\n                CALL clear_access_ram_extension_status_bit\n",
    "cas_handler:    SEL  MB1            ; -> schnelle Kassette (0x800)\n                JMP  s_cas\n                NOP\n")
rep("cal_handler:    CALL clear_display\n                CALL clear_access_ram_extension_status_bit\n",
    "cal_handler:    SEL  MB1            ; -> schnelle Kassette (0x800)\n                JMP  s_cal\n                NOP\n")
# je genau so viele Bytes wie im Original ersetzen (sonst verschiebt sich alles dahinter)
rep("opcode_UND:     MOV  R0, #ACCU      ; Load Accu's MSB...\n                MOV  A, @R0         ; ... into A\n",
    "opcode_UND:     SEL  MB1            ; -> UND bitweise (Block 1101 über die Tabelle)\n                JMP  zu_s_und\n")
rep(".db  <opcode_ANZ             ; opcode 02: ANZ", ".db  <anz_neu               ; opcode 02: ANZ -> 0xD00 (ANZ 001 mit Vorzeichen)")
# 4.03: Punkt-Leitung an PA7 (Michael: Überspannungs-Treiber an 8155 Pin 28, alle DP verbunden, Trennung nicht mehr fest).
# Der Trennpunkt ist nicht mehr fest verdrahtet: wait_key (Leerlauf, Normalbetrieb) setzt Bit 7 bei Ziffer 3.
# SEG/ANZ/laufende Programme laufen nicht durch wait_key -> dort nur Punkte, die das Programm selbst setzt.
DP_ISR = """dp_warte:       MOV  R0, #$22       ; Ziffer 3: Trennpunkt (Bit 7 -> PA7) im Normalbetrieb
                MOV  A, @R0
                ORL  A, #$80
                MOV  @R0, A
                MOV  R0, #$1e       ; wie bisher: R6' (Taste)
                RET
"""
# alter NEG-Rumpf (23 Byte) ist tot, seit NEG nach 0xD00 springt: dort anz_neu, Rest NOP
i0 = src.index("opcode_NEG:"); i1 = src.index("error_f005:     MOV  R4, #$05")
src = src[:i0] + "opcode_NEG:     SEL  MB1            ; -> NEG mit Maske (Block 1101 über die Tabelle)\n                JMP  zu_s_neg\nanz_neu:        SEL  MB1            ; -> ANZ (Block 1101 über die Tabelle)\n                JMP  zu_s_anz\nneg_was_zero:\nneg_done:\n" + DP_ISR + "                NOP\n" * 8 + "\n" + src[i1:]
rep("error_f006:     MOV  R4, #$06\n                JMP  show_error     ; F-006\n",
    "error_f006:     SEL  MB1            ; -> OVF-Schalter (Block 1101 über die Tabelle)\n                JMP  zu_s_f006\n                NOP\n")
rep("ADD  A, #$e7        ; add (256 - 25) to check for max opcode",
    "ADD  A, #$ce        ; (256 - 50): 6.21: INP nimmt Befehle bis 49 an (48 JOV, 49 ZUF; 5.06: bis 47)")
# 5.06: Marken hinter den Zellenprüfungen von ADD/VGL/VGR/VKL für die Befehle mit festem Wert (nur Marken, Bytes gleich)
rep("                JF1  execute_sub_trampoline ; if F1 is set, it's a SUB\n",
    "add_imm:        JF1  execute_sub_trampoline ; if F1 is set, it's a SUB\n")
rep("                MOVX A, @R1         ; Load operand cell content LSB\n                XRL  A, @R0         ; Compare to Accu LSB\n",
    "vgl_imm:        MOVX A, @R1         ; Load operand cell content LSB\n                XRL  A, @R0         ; Compare to Accu LSB\n")
rep("                MOVX A, @R1         ; Load operand cell content LSB\n                JZ   vgl_end        ; if zero, no need to compare\n",
    "vkl_imm:        MOVX A, @R1         ; Load operand cell content LSB\n                JZ   vgl_end        ; if zero, no need to compare\n")
rep("                MOV  A, @R0         ; Load Accu LSB\n                JZ   vgl_end        ; If zero, it can't be greater than anything\n",
    "vgr_imm:        MOV  A, @R0         ; Load Accu LSB\n                JZ   vgl_end        ; If zero, it can't be greater than anything\n")
rep("                MOV  @R0, A         ; store entered number in PC\n                MOV  R6, #$00       ; reset # of entered digits\n                JMP  wait_key\n",
    "                MOV  @R0, A         ; store entered number in PC\n                SEL  MB1            ; -> PC gesetzt: JSR-Stapel leeren (Block 1101 über die Tabelle)\n                JMP  zu_s_pcset\n                NOP\n")
rep("opcode_inv:     MOV  R4, #$02       ; F-002\n                JMP  show_error\n",
    "opcode_inv:     SEL  MB1            ; -> Befehl 25 ODR oder F-002 (Block 1101 über die Tabelle)\n                JMP  zu_s_inv\n                NOP\n")
rep("wait_key:       MOV  R0, #$1e       ; Wait for key press: 0x1e is R6', used in interrupt\n",
    "wait_key:       CALL dp_warte       ; 4.03: Trennpunkt setzen, R0 = 0x1e (2 Byte gegen 2 Byte)\n")
# Fernsteuerung: Hook im Timer-Interrupt (2 Byte gegen 2 Byte)
rep("                MOVD A, P4          ; ????? write to lower nibble of port 2, then read from it? why not just read from it?\n                CLR  C\n",
    "                CALL rc_tast        ; Fernsteuerung: P1.7 abfragen, Ferntaste dazumischen (liest MOVD A, P4; CLR C)\n")
# toter Rest der alten CAL-Routine (0x712..0x7E0) -> Fernsteuerung im Interrupt
i0 = src.index("                MOV  R0, #VRAM      ; Set left-most digit...\n                MOV  @R0, #$1c")
i1 = src.index("; Clear result of last comparison in status byte")
src = src[:i0] + open(RC_UNTEN,encoding='utf-8').read() + "\n                .org $7e1\n" + src[i1:]
# toter Rest der alten CAS-Routine (0x1C8..0x1FE) -> Fernsteuerung Teil 2
i0 = src.index("                MOV  R0, #VRAM      ; Set left-most digit...\n                MOV  @R0, #$23")
i1 = src.index("out_handler:\n")
src = src[:i0] + open('v6/rc_seite1.asm',encoding='utf-8').read() + "\n                .org $1ff\n" + src[i1:]
rep("                JMP  save_done\n\ncas_handler:", "                JMP  wait_key       ; (tot)\n\ncas_handler:")
# VZG: in Hälfte A warten und dabei Zifferntasten für TSE merken (3 Byte gegen 3 Byte)
rep("opcode_VZG:     MOVX A, @R1         ; load operand into A\n                JZ   end_VZG        ; if zero, no delay necessary\n",
    "opcode_VZG:     SEL  MB1            ; -> VZG mit Tastengedächtnis (Block 1101 über die Tabelle)\n                JMP  zu_s_vzg\n")
# OUT P1A: interne Leitungen schützen (3 Byte gegen 3 Byte)
rep("write_to_p1:    OUTL P1, A          ; write byte to 8049 port 1\n                JMP  inc_pc\n",
    "write_to_p1:    SEL  MB1            ; -> P1.0-P1.4, P1.7 bleiben 1 (Block 1101 über die Tabelle)\n                JMP  zu_s_p1aus\n")
# Start: Firmware-Version 1 s zeigen (4 Byte gegen 4 Byte)
rep("                CALL clear_ram\n                EN   TCNTI          ; enable Timer/Counter interrupts\n                STRT T              ; and start the timer\n",
    "                SEL  MB1            ; -> Version zeigen, dann wie bisher (Block 1101 über die Tabelle)\n                JMP  s_boot\n                NOP\n")
# tote alte CAS-Sende-Routine (0x3BD..0x3F2) -> Fernsteuerung Teil 3
i0 = src.index("save_memory:\n                MOV  R1, #$00")
i1 = src.index("clear_access_ram_extension_status_bit:\n")
src = src[:i0] + open(RC_SEITE3,encoding='utf-8').read() + "\n                .org $3f3\n\n" + src[i1:]
# RUN: 1 s halten schaltet die Fernsteuerung (3 Byte gegen 3 Byte)
rep("run_handler:    MOV  A, R6          ; Load # of entered digits\n                XRL  A, #$01        ; is it 1?\n                JNZ  not_one        ; jump if not.\n",
    "run_handler:    SEL  MB1            ; -> RUN halten = Fernsteuerung an/aus (Block 1101 über die Tabelle)\n                JMP  s_run\nrun_weiter:     JNZ  not_one        ; jump if not.\n")
import importlib.util as _iu, sys as _s
_s.path.insert(0,'v6'); import unten5
src = unten5.anwenden(src, rep)
# =====================================================================
# 6.x: obere Blöcke. Ein Block = 2 KB, benannt nach A11 A12 A13 A14 (LSB zuerst).
#   A11 = MB0/MB1, A12 = P1.4, A13 = P1.5, A14 = P1.1 (SCK; im Betrieb immer 1, SPI Mode 3).
#   Assembler-Adresse = EEPROM-Adresse: Block 1 a b c liegt bei 0x800 + a*0x1000 + b*0x2000 + c*0x4000.
#   0xxx: unten, in allen acht Kopien gleich (Original, Interrupt).
# Sprungtabelle: oben in jedem Block 1xxx Byte für Byte gleich. Nur dort wird der Block gewechselt.
#   zu_X  (X in einem oberen Block):  ORL P1,#$30 (-> 1111)  [ANL P1,#maske (-> Ziel)]  JMP X
#   zu_X  (X unten):                  ORL P1,#$30 (-> 1111)  SEL MB0  JMP X
#   fa_X  (Fernaufruf, CALL aus Block Q nach X in Block Z):  [ORL]/[ANL] (-> Z)  CALL X  [ORL]/[ANL] (-> Q)  RET
#         Der Eintrag liegt in Q und Z an derselben Stelle: der Befehl nach dem Umschalten kommt schon aus dem
#         anderen Block. Kostet eine Stapelebene mehr; nur aus dem einen Block Q aufrufbar.
# Regel: ins Original (unten) geht es per JMP nur aus 1111 (die Haken des Originals springen direkt nach 1111);
#   aus anderen Blöcken nur über zu_X. CALL nach unten ist überall erlaubt (RET kommt in denselben Block zurück).
# =====================================================================
BLOECKE = [  # (Name, Datei, Basis)
    ('1111', 'v6/bedienung.asm', 0x7000),   # Bedienung (Start nach Reset: P1 = FF)
    ('1011', 'v6/treiber.asm',  0x6000),   # Flash-Treiber und FNI-Übertragung
    ('1101', 'v6/befehle.asm',  0x5000),   # Befehle
    ('1001', 'v6/auftraege.asm', 0x4000),  # Aufträge (Tasten, SEF, PSK/FRD/FWR, Autoboot), ruft den Treiber per fa_X
]
KNAPP = 0x6000          # 1011 trägt nur den Teil der Tabelle, der ihn betrifft (Ziel oder Absprung in 1011)
SPIEGEL = {0x2000: 0x6000}                 # 1010 = Kopie von 1011 (SCK-Fenster in spi)
LABEL_RE = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*):', re.M)
texte = [(n, open(d, encoding='utf-8').read(), b) for n, d, b in BLOECKE]
heimat = {}
for n, t, b in texte:
    for l in LABEL_RE.findall(t): heimat[l] = b
def ohne_kommentar(t): return '\n'.join(x.split(';')[0] for x in t.split('\n'))
def refs(t, art='zu'): return set(re.findall(rf'\b{art}_([A-Za-z0-9_]+)', ohne_kommentar(t)))
alle_texte = ohne_kommentar(src) + '\n' + '\n'.join(t for _, t, _ in texte)
ziele = sorted(refs(alle_texte))
knapp_t = next(t for _, t, b in texte if b == KNAPP)
fuer_knapp = {z for z in ziele if heimat.get(z) == KNAPP} | refs(knapp_t)
fern = {}                                           # X -> (Block Q des Aufrufers, Block Z von X)
for n, t, b in texte:
    for x in refs(t, 'fa'):
        if x in fern and fern[x][0] != b: raise SystemExit(f'fa_{x}: aus mehreren Blöcken aufgerufen')
        if heimat.get(x) in (None, b): raise SystemExit(f'fa_{x}: Ziel unten oder im eigenen Block (CALL genügt)')
        fern[x] = (b, heimat[x])
def umschalten(von, nach):                          # Befehle, die P1 von Block von auf Block nach bringen
    a = [(0x10, 0x1000), (0x20, 0x2000)]
    setz = sum(bit for bit, adr in a if nach & adr and not von & adr)
    loesch = sum(bit for bit, adr in a if von & adr and not nach & adr)
    r = []
    if setz: r.append(f'ORL  P1, #${setz:02x}')
    if loesch: r.append(f'ANL  P1, #${0xff & ~loesch:02x}')
    return r
def fern_eintrag(x):
    q, z = fern[x]; hin, her = umschalten(q, z), umschalten(z, q)
    zeilen = hin + [f'CALL {x}'] + her + ['RET']
    t = [f'fa_{x}:'.ljust(15) + ' ' + zeilen[0]] + ['                ' + l for l in zeilen[1:]]
    return t, 2 * len(hin) + 2 + 2 * len(her) + 1
def eintrag(z):
    b = heimat.get(z)
    if b is None:                                   # unten
        return [f'zu_{z}:'.ljust(16) + 'ORL  P1, #$30', '                SEL  MB0', f'                JMP  {z}'], 5
    if b == 0x7000:
        return [f'zu_{z}:'.ljust(16) + 'ORL  P1, #$30', f'                JMP  {z}'], 4
    maske = 0xFF & ~(0 if b & 0x1000 else 0x10) & ~(0 if b & 0x2000 else 0x20)
    return [f'zu_{z}:'.ljust(16) + 'ORL  P1, #$30', f'                ANL  P1, #${maske:02x}', f'                JMP  {z}'], 6
# Reihenfolge: erst die übrigen Einträge, ganz oben die für 1011 (so endet 1011s Teil am Blockende)
TAB_Z, TAB_N, TAB_K = [], 0, 0
for z in [z for z in ziele if z not in fuer_knapp] + [z for z in ziele if z in fuer_knapp]:
    t, n = eintrag(z); TAB_Z += t; TAB_N += n
    if z in fuer_knapp: TAB_K += n
for x in sorted(fern):                              # Fernaufrufe ganz oben (alle betreffen bisher 1011)
    t, n = fern_eintrag(x); TAB_Z += t; TAB_N += n
    if KNAPP in fern[x]: TAB_K += n
    else: raise SystemExit(f'fa_{x}: Fernaufruf ohne 1011 – Tabellenaufteilung erweitern')
TAB = 0x1000 - TAB_N                                # Offset im Block: ganze Tabelle
TAB_B = 0x1000 - TAB_K                              # Offset: Teil für 1011
tabelle = (f'; Sprungtabelle (erzeugt von build6.py, {TAB_N} Byte, davon {TAB_K} oben auch in 1011)\n'
           f'                .org ${0x7000 + TAB:x}\n' + '\n'.join(TAB_Z) + '\n')
def tab_ab(b): return TAB_B if b == KNAPP else TAB
for n, t, b in texte:
    assert re.search(rf'^\s*\.org \${b + 0x800:x}\s*(;|$)', t, re.M), f'{n}: .org ${b + 0x800:x} fehlt'
src += '\n' + ''.join(t + '\n' for _, t, _ in texte) + tabelle
open(AUS+'.asm','w',encoding='latin-1',errors='replace').write(src)
sys.path.insert(0,'.'); import asm48
start_b1 = src.count('\n', 0, src.index(texte[0][1][:200])) + 1
import re as _re

def block(a): return None if a < 0x800 else a & 0x7000

def _fit(text, groesse):
    """bedingter Sprung über eine Seitengrenze -> Absatz (bis zur Leerzeile davor) auf die nächste Seite"""
    for runde in range(120):
        open(AUS+'.asm','w',encoding='latin-1',errors='replace').write(text)
        try:
            r, s = asm48.assembliere(AUS+'.asm',0xff,groesse); return text, r, s
        except SystemExit as e:
            m=_re.match(r'Zeile (\d+): .*Sprungziel', str(e))
            if not m: raise
            z=text.split('\n'); n=int(m.group(1))-1
            assert n>=start_b1, e
            while n>start_b1 and z[n-1].strip(): n-=1
            if z[n].strip()=='.seite': raise SystemExit(f'Absatz passt in keine Seite: {e}')
            z.insert(n,'                .seite'); text='\n'.join(z)
    raise SystemExit('kein Ende')

src, rom, sym = _fit(src, 0x8000)
# Platz: Code jedes Blocks muss unter der Tabelle enden
frei = {}
for n, _, b in BLOECKE:
    rest = [i for i in range(b + tab_ab(b), b + 0x1000) if rom[i] != 0xff] if b != 0x7000 else []
    if rest: raise SystemExit(f'Block {n} zu voll: Code reicht bis {max(rest):#x}, Tabelle ab {b + tab_ab(b):#x}')
    frei[n] = sum(1 for i in range(b + 0x800, b + tab_ab(b)) if rom[i] == 0xff)
# Sicherung: vor jeder eingefügten .seite muss der Code unbedingt enden (sonst liefe er in die FF-Lücke)
_z = open(AUS+'.asm',encoding='latin-1').read().split('\n')
for _n, _l in enumerate(_z):
    if _l.strip().lower() == '.seite' and _n >= start_b1:
        _k = _n - 1
        while _k > 0 and (not _z[_k].split(';')[0].strip() or _z[_k].split(';')[0].strip().endswith(':')): _k -= 1
        _code = _z[_k].split(';')[0].strip()
        _mn = _code.split(':')[-1].split()[0].upper() if _code.split(':')[-1].split() else ''
        if _mn not in ('JMP', 'RET', 'RETR', 'JMPP', '.DB', '.SEITE', '.ORG'):
            raise SystemExit(f'.seite nach durchlaufendem Code (Zeile {_k+1}: {_z[_k].strip()})')
# Sprungprüfung (JMP/CALL kodieren nur 11 Bit: ein Ziel in einem anderen Block landete still im falschen)
tab_von = 0x7000 + TAB
fehler = []
pc = 0
for nr, lab, m, ops in asm48.zeilen(AUS+'.asm'):
    if m is None: continue
    if m == '.EQU': continue
    if m == '.ORG': pc = asm48.zahl(ops[0], sym); continue
    if m == '.SEITE': pc = (pc + 0xff) & ~0xff; continue
    laenge = len(ops) if m == '.DB' else len(asm48.befehl(m, ops, pc, sym))
    if pc >= 0x800 and not (tab_von <= pc < 0x8000) and m in ('OUTL', 'ANL', 'ORL') and ops and ops[0].upper() == 'P1':
        # P1-Prüfung: P1.4 = A12, P1.5 = A13, P1.1 = A14 (SCK). Außerhalb der Tabelle darf oben nichts den Block wechseln.
        w = None if m == 'OUTL' else asm48.zahl(ops[1][1:], sym) & 0xFF
        if m == 'OUTL': fehler.append(f'Zeile {nr}: OUTL P1 ({pc:#06x}): schreibt A12–A14 mit (Blockwechsel)')
        elif m == 'ANL' and w & 0x30 != 0x30: fehler.append(f'Zeile {nr}: ANL P1,#${w:02x} ({pc:#06x}): löscht A12/A13 (Blockwechsel)')
        elif m == 'ANL' and not w & 0x02 and pc != sym.get('sp_k'): fehler.append(f'Zeile {nr}: ANL P1,#${w:02x} ({pc:#06x}): A14/SCK low nur im Fenster sp_k')
        elif m == 'ORL' and w & 0x30 and block(pc) != 0x7000: fehler.append(f'Zeile {nr}: ORL P1,#${w:02x} ({pc:#06x}): setzt A12/A13 außerhalb von 1111 (Blockwechsel)')
    if m in ('JMP', 'CALL') and not (tab_von <= pc < 0x8000):
        t = asm48.zahl(ops[0], sym); hier = block(pc)
        fa = next((x for x in fern if sym.get('fa_' + x) == (t & 0xFFF | 0x7000)), None) if t >= 0x800 else None
        if fa is not None:
            ok = hier == fern[fa][0] and (t & 0xFFF) >= tab_ab(hier)
            warum = f'fa_{fa} gilt nur aus Block {fern[fa][0]:#x}'
        elif hier is None:
            ok = t < 0x800 or block(t) == 0x7000
            warum = 'aus dem Original nur nach 1111'
        elif t < 0x800:
            ok = m == 'CALL' or hier == 0x7000
            warum = 'nach unten per JMP nur aus 1111 (sonst zu_…)'
        elif t >= tab_von or (t & 0xFFF) >= tab_ab(hier) and block(t) == hier:
            ok = m == 'JMP' and (t & 0xFFF) >= tab_ab(hier)
            warum = 'in die Tabelle nur per JMP' if m != 'JMP' else 'Eintrag fehlt im Tabellenteil von 1011'
        else:
            ok = block(t) == hier; warum = 'Ziel in einem anderen Block (zu_… benutzen)'
        if not ok: fehler.append(f'Zeile {nr}: {m} {ops[0]} ({pc:#06x} -> {t:#06x}): {warum}')
    pc += laenge
if fehler: raise SystemExit('Sprung- und P1-Prüfung:\n  ' + '\n  '.join(fehler))

# MBF-Prüfung: JMP/CALL kodieren A11 nicht, er kommt aus dem Merker MBF (SEL MB0/MB1). Für jeden Befehl in den
# oberen Blöcken wird verfolgt, mit welchem MBF er erreicht werden kann (auch über bedingte Sprünge und
# Unterprogramme). Ein Sprung nach oben (eigener Block, Tabelle) braucht MBF = 1, nach unten MBF = 0.
class _pk:                                          # bedingte Sprünge (8048)
    BEDINGT = {'JB0', 'JB1', 'JB2', 'JB3', 'JB4', 'JB5', 'JB6', 'JB7', 'JC', 'JNC', 'JZ', 'JNZ', 'JF0', 'JF1',
               'JT0', 'JNT0', 'JT1', 'JNT1', 'JTF', 'JNI', 'DJNZ'}
befehle_o, zeile_o = {}, {}
fa_start = min((sym['fa_' + x] for x in fern), default=0x8000)   # Fernaufrufe stehen ganz oben in der Tabelle
pc = 0
for nr, lab, m, ops in asm48.zeilen(AUS+'.asm'):
    if m is None or m == '.EQU': continue
    if m == '.ORG': pc = asm48.zahl(ops[0], sym); continue
    if m == '.SEITE': pc = (pc + 0xff) & ~0xff; continue
    n = len(ops) if m == '.DB' else len(asm48.befehl(m, ops, pc, sym))
    if pc >= 0x800 and not (tab_von <= pc < fa_start): befehle_o[pc] = (nr, m, ops, n)   # Fernaufrufe mitprüfen
    pc += n
fa_adr = {sym['fa_' + x] & 0xFFF: sym[x] for x in fern}     # Offset des Eintrags -> Ziel X
def ist_tab(t): return t >= tab_von or (block(t) is not None and (t & 0xFFF) >= tab_ab(block(t)))
def fa_von(t): return 0x7000 | t & 0xFFF if t >= 0x800 and (t & 0xFFF) in fa_adr else None
def folgbar(pc, t):                                  # Ziel im selben Block oder Fernaufruf-Eintrag bzw. dessen CALL
    if fa_von(t) is not None: return True
    if pc >= fa_start: return t in fa_adr.values()  # CALL X im Eintrag (Ziel in einem anderen Block)
    return not ist_tab(t) and block(t) == block(pc)
start = set()
for z in ziele:
    if heimat.get(z) is not None: start.add(sym[z])
for a_, (nr, m, ops, n) in []: pass
pc = 0
for nr, lab, m, ops in asm48.zeilen(AUS+'.asm'):                 # Haken: Sprünge aus dem Original nach oben
    if m is None or m == '.EQU': continue
    if m == '.ORG': pc = asm48.zahl(ops[0], sym); continue
    if m == '.SEITE': pc = (pc + 0xff) & ~0xff; continue
    n = len(ops) if m == '.DB' else len(asm48.befehl(m, ops, pc, sym))
    if pc < 0x800 and m in ('JMP', 'CALL'):
        t = asm48.zahl(ops[0], sym)
        if t >= 0x800 and not ist_tab(t): start.add(t)
    pc += n
zustand = {}                       # pc -> {(mbf, routine)}
rueck, aufrufe = {}, {}            # routine -> {mbf bei RET}; routine -> {(pc nach CALL, aufrufende Routine)}
arbeit = [(t, 1, 'oben') for t in start]
mbf_fehler = set()
def melde(pc, text):
    mbf_fehler.add(f'Zeile {befehle_o[pc][0]} ({pc:#06x}): {text}' if pc in befehle_o else f'{pc:#06x}: {text}')
def weiter(pc, mbf, r):
    if pc not in befehle_o: melde(pc, 'Code läuft ins Leere (kein Befehl an dieser Adresse)'); return
    if (mbf, r) not in zustand.setdefault(pc, set()):
        zustand[pc].add((mbf, r)); arbeit.append((pc, mbf, r))
while arbeit:
    pc, mbf, r = arbeit.pop()
    if pc not in befehle_o: melde(pc, 'Einsprung ohne Befehl'); continue
    zustand.setdefault(pc, set()).add((mbf, r))
    nr, m, ops, n = befehle_o[pc]; nach = pc + n
    if m == '.DB': melde(pc, 'Code läuft in Daten (.db)'); continue
    if m == 'SEL' and ops[0].upper() in ('MB0', 'MB1'): weiter(nach, int(ops[0][2]), r); continue
    if m in ('RET', 'RETR'):
        if mbf not in rueck.setdefault(r, set()):
            rueck[r].add(mbf)
            for (p2, r2) in aufrufe.get(r, ()): weiter(p2, mbf, r2)
        continue
    if m in _pk.BEDINGT:
        weiter(asm48.zahl(ops[-1], sym), mbf, r); weiter(nach, mbf, r); continue
    if m == 'JMPP':
        for k, v in sym.items():
            if v >> 8 == pc >> 8 and v in befehle_o: weiter(v, mbf, r)
        continue
    if m in ('JMP', 'CALL'):
        t = asm48.zahl(ops[0], sym); soll = 0 if t < 0x800 else 1
        if mbf != soll: melde(pc, f'{m} {ops[0]} mit MBF = {mbf} (nötig: {soll}) – landet in {"oben" if mbf else "unten"}')
        if t >= 0x800 and fa_von(t) is not None: t = fa_von(t)          # Eintrag in der Tabelle (bei 0x7xxx assembliert)
        if m == 'JMP':
            if t >= 0x800 and folgbar(pc, t): weiter(t, mbf, r)
            continue
        if t < 0x800: weiter(nach, mbf, r); continue       # Original-Routine: lässt MBF in Ruhe
        if folgbar(pc, t):
            aufrufe.setdefault(t, set()).add((nach, r))
            weiter(t, 1, t)
            for mb in rueck.get(t, ()): weiter(nach, mb, r)
        continue
    weiter(nach, mbf, r)
if mbf_fehler: raise SystemExit('MBF-Prüfung:\n  ' + '\n  '.join(sorted(mbf_fehler)))
print(f'MBF-Prüfung: {len(zustand)} Befehle von {len(start)} Einsprüngen aus erreicht, alle Sprünge mit passendem MBF')
# Stapelprüfung (statisch): wie viele Ebenen belegt ein Einsprung höchstens? Jeder CALL zählt eine Ebene (ein
# Fernaufruf also zwei: Eintrag + CALL X); wo der Timer-Interrupt kommen kann, zählt er mit seiner eigenen Tiefe
# (vom Build aus dem Handler ermittelt). Routinen mit „[ohne Interrupt]“ im Kommentar der Label-Zeile laufen nur
# bei abgeschaltetem Interrupt (FNI) – dort und darunter zählt er nicht; der Simulator prüft das bei jedem Befehl
# (cp1v6.ohneint). JMP ins Original (zu_…, unten) verlässt den Auftrag.
# Grenze: 7 von 8 Ebenen – eine Reserve (wie der Simulator).
STAPEL_MAX = 7
alle_bef = {}
_roh = open(AUS+'.asm', encoding='latin-1').read().split('\n')
ohne_int_start = set()
pc = 0
for nr, lab, m, ops in asm48.zeilen(AUS+'.asm'):
    if lab and '[ohne Interrupt]' in _roh[nr-1]: ohne_int_start.add(sym[lab])
    if m is None or m == '.EQU': continue
    if m == '.ORG': pc = asm48.zahl(ops[0], sym); continue
    if m == '.SEITE': pc = (pc + 0xff) & ~0xff; continue
    n = len(ops) if m == '.DB' else len(asm48.befehl(m, ops, pc, sym))
    alle_bef[pc] = (nr, m, ops, n); pc += n
namen_r = {}
for k, v in sym.items(): namen_r.setdefault(v, k)
def ziel_von(t): return fa_von(t) if t >= 0x800 and fa_von(t) is not None else t
_tiefe, _in_arbeit, ohne_int_adr = {}, set(), set()
ISR_TIEFE = 0
def bedarf(start, int_an):
    """(Ebenen, die start höchstens belegt – mit Interrupt, wo er kommen kann; Kette)"""
    if start in ohne_int_start: int_an = False
    key = (start, int_an)
    if key in _tiefe: return _tiefe[key]
    if key in _in_arbeit: raise SystemExit(f'Stapelprüfung: Rekursion über {namen_r.get(start, hex(start))}')
    _in_arbeit.add(key)
    best, gesehen, offen = ((ISR_TIEFE, ['Interrupt']) if int_an else (0, [])), set(), [start]
    while offen:
        pc = offen.pop()
        if pc in gesehen: continue
        gesehen.add(pc)
        if pc not in alle_bef: continue
        if not int_an: ohne_int_adr.add(pc)
        nr, m, ops, n = alle_bef[pc]; nach = pc + n
        if m in ('RET', 'RETR', '.DB'): continue
        if m in _pk.BEDINGT: offen += [asm48.zahl(ops[-1], sym), nach]; continue
        if m == 'JMPP':
            offen += [v for v in sym.values() if v >> 8 == pc >> 8 and v in alle_bef]; continue
        if m in ('JMP', 'CALL'):
            roh_t = asm48.zahl(ops[0], sym); t = ziel_von(roh_t)
            if m == 'JMP':
                if (roh_t & 0xFFF) >= TAB and roh_t >= 0x800 and fa_von(roh_t) is None:   # zu_X: weiter in X, wenn oben
                    x = next((z for z in ziele if sym.get('zu_' + z) == (roh_t & 0xFFF | 0x7000)), None)
                    if x and heimat.get(x) is not None: offen.append(sym[x])
                    continue
                if pc >= 0x800 and t < 0x800: continue      # (nur 1111) ins Original: Auftrag verlassen
                offen.append(t); continue
            d, k = bedarf(t, int_an)
            if d + 1 > best[0]: best = (d + 1, [namen_r.get(t, hex(t))] + k)
            offen.append(nach); continue
        offen.append(nach)
    _in_arbeit.discard(key); _tiefe[key] = best
    return best
_isr_d, _isr_k = bedarf(0x007, False)               # Timer-Interrupt: Einsprung (1) + was der Handler aufruft
ISR_TIEFE = _isr_d + 1; _tiefe.clear(); ohne_int_adr.clear()
einspruenge = sorted({sym[z] for z in ziele if heimat.get(z) is not None})
tief = sorted(((bedarf(e, True), e) for e in einspruenge), key=lambda x: -x[0][0])
stapel_fehler = [f'{namen_r[e]}: {d} Ebenen > {STAPEL_MAX} ({" > ".join(k)})' for (d, k), e in tief if d > STAPEL_MAX]
if os.environ.get('STAPEL_ZEIGEN'):
    for (d, k), e in tief[:12]: print(f'  {d}  {namen_r[e]}: {" > ".join(k)}')
if stapel_fehler: raise SystemExit('Stapelprüfung:\n  ' + '\n  '.join(stapel_fehler))
(d0, k0), e0 = tief[0]
print(f'Stapelprüfung: Interrupt {ISR_TIEFE} Ebenen ({" > ".join(_isr_k)}); tiefster Einsprung {namen_r[e0]}: '
      f'{d0} von 8 ({" > ".join(k0)}); {len(ohne_int_adr)} Befehle [ohne Interrupt]')
open(AUS+'.ohneint', 'w').write('\n'.join(f'{a:04x}' for a in sorted(ohne_int_adr)) + '\n')
orig,_=asm48.assembliere('cp1.asm',0x00,0x800)
d=[i for i in range(0x800) if rom[i]!=orig[i]]
print(f'Original-Bereich: {len(d)} Byte geändert (Haken, Fernsteuerung)')
print(f'Sprungtabelle {len(ziele)} Einträge, {TAB_N} Byte ab Offset {TAB:#05x} (1011: {TAB_K} Byte ab {TAB_B:#05x}); frei: ' +
      ', '.join(f'{n} {f} Byte' for n, f in frei.items()))
# EEPROM-Abbild (32 KB): unten überall gleich, oben je Block; Tabelle in allen Blöcken 1xxx
tab = bytes(rom[0x7000 + TAB:0x8000])
bild = bytearray([0xFF]) * 0x8000
for b in range(0, 0x8000, 0x1000):
    bild[b:b + 0x800] = rom[0:0x800]
    quelle = SPIEGEL.get(b, b)
    bild[b + 0x800:b + 0x1000] = rom[quelle + 0x800:quelle + 0x1000]
    t0 = tab_ab(quelle)
    bild[b + t0:b + 0x1000] = tab[t0 - TAB:]
for n, _, b in BLOECKE: assert bild[b + 0x800:b + tab_ab(b)] == rom[b + 0x800:b + tab_ab(b)]
assert bild[0x7800:0x8000] == rom[0x7800:0x8000]
open(AUS+'-eeprom.bin','wb').write(bild)
sym['TABELLE'], sym['TABELLE_1011'] = 0x7000 + TAB, 0x7000 + TAB_B
open(AUS+'.sym','w').write('\n'.join(f'{v:04x} {k}' for k,v in sorted(sym.items(),key=lambda x:x[1])))
if os.environ.get('MBF_ZEIGEN'):
    tot = sorted(a for a in befehle_o if a not in zustand and befehle_o[a][1] != '.DB')
    namen = {v: k for k, v in sym.items()}
    print('nicht erreicht:', len(tot), [f'{a:#06x} {namen.get(a, "")} Z{befehle_o[a][0]}' for a in tot if a in namen][:40])
