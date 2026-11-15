# Umschalt-Stummel für beide EEPROM-Hälften erzeugen (gleiche Bytes an gleicher Stelle, Ende 0xFFF)
NACH_B = ['k_cal_vor', 'sf_ok', 'f_boot', 'j_speichern', 'j_laden', 'j_autoboot', 'k_teil', 'bl_suche']
NACH_A = ['s_ende', 's_cal_ui', 'boot_warte', 'job_kopf', 'bl_zeige']
NACH_UNTEN = ['inc_pc', 'show_error', 'wait_key', 'run_weiter']        # über A, dann SEL MB0
groesse = 5 * (len(NACH_B) + len(NACH_A)) + 6 * len(NACH_UNTEN)
start = 0x1000 - groesse
def text(pre, org):
    z = [f'; Umschalt-Stummel (erzeugt von gen_stummel.py, {groesse} Byte)', f'                .org ${org:x}']
    for n in NACH_B:
        z += [f'{pre}zb_{n}: ANL  P1, #$ef      ; A12 = 0 -> Hälfte B', '                NOP', f'                JMP  {n}']
    for n in NACH_A:
        z += [f'{pre}za_{n}: ORL  P1, #$10      ; A12 = 1 -> Hälfte A', '                NOP', f'                JMP  {n}']
    for n in NACH_UNTEN:
        z += [f'{pre}za_{n}: ORL  P1, #$10', '                NOP', '                SEL  MB0', f'                JMP  {n}']
    return '\n'.join(z) + '\n'
open('stummel_a.asm', 'w').write(text('', start))
open('stummel_b.asm', 'w').write(text('b_', start + 0x1000))
print(f'Stummel ab {start:#x}, {groesse} Byte')
