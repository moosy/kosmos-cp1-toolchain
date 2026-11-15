import sys, runpy
sys.argv = ['fluss.py', sys.argv[1], sys.argv[2]]
import io, contextlib
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    g = runpy.run_path('../review/fluss.py')
sym, tiefe, v = g['sym'], g['tiefe'], g['v']
def t(name):
    a = sym[name]
    if a < 0x800: return tiefe(a, 'A', 0, False)
    if a < 0x1000: return tiefe(a, 'A', 1, False)
    return tiefe(a - 0x1000, 'B', 1, False)
for n in ['k_cal_vor', 'fni_pc', 'fni_cp', 'fni_fp', 'fni_pf', 'j_speichern', 'j_laden', 'j_autoboot', 'k_teil', 'sf_ok', 'f_boot', 's_cas', 's_cal_ui', 's_run', 's_fbef', 'step_handler', 'wait_key', 's_demo8', 's_demo9', 's_seg', 's_tse']:
    if n in sym: print(f'{n:14s} {t(n)}')
isr = max(tiefe(a, h, m, i) for a, h, m, i in g['wurzeln'] if i)
print('Interrupt: 1 +', isr)
