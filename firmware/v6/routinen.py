"""Routinenliste der Firmware 6.x je Block als Markdown (für docs/firmware6-bloecke-de.md).
Aufruf nach dem Bauen (braucht v6/cp1v6.sym):  python3 v6/routinen.py > ../docs/firmware6-routinen-de.md
Als Routine gilt eine Marke, die per CALL, über die Sprungtabelle (zu_X, fa_X) oder aus den Haken im
Original (build6.py) erreicht wird, oder über der ein Kommentar mit ihrem Namen steht. Reine Sprungmarken
innerhalb einer Routine fehlen. Zweck = erste Kommentarzeile darüber, sonst der Kommentar in der Zeile."""
import os, re, sys
D = os.path.dirname(os.path.abspath(__file__))
BLOECKE = [('1111', 'bedienung.asm', 'Bedienung: Tasten CAS/CAL/RUN, Start, Version, Anzeige der Eingaben'),
           ('1101', 'befehle.asm', 'Befehle: alle neuen und geänderten CP1-Befehle'),
           ('1001', 'auftraege.asm', 'Aufträge: was mit dem Flash geschehen soll (Projekte, SEF, PSK/FRD/FWR/JOV, Autoboot)'),
           ('1011', 'treiber.asm', 'Treiber: wie der Flash gelesen und geschrieben wird, FNI zum Pi')]
UNTEN = [('rc_unten.asm', '0x712–0x7E0 (tote alte CAL-Routine)'), ('rc_seite1.asm', '0x1C8–0x1FE (tote alte CAS-Routine)'),
         ('rc_seite3.asm', '0x3BD–0x3F2 (tote alte Kassetten-Senderoutine)')]

sym = {}
for z in open(os.path.join(D, 'cp1v6.sym')):
    a, n = z.split()
    sym[n] = int(a, 16)

def code(t): return '\n'.join(x.split(';')[0] for x in t.split('\n'))
alle = ''.join(open(os.path.join(D, f), encoding='utf-8').read() for _, f, _ in BLOECKE)
alle += ''.join(open(os.path.join(D, f), encoding='utf-8').read() for f, _ in UNTEN)
haken = open(os.path.join(D, 'build6.py'), encoding='utf-8').read()
gerufen = set(re.findall(r'\bCALL\s+(?:fa_|zu_)?([A-Za-z0-9_]+)', code(alle)))
gerufen |= set(re.findall(r'\b(?:zu|fa)_([A-Za-z0-9_]+)', code(alle)))
gerufen |= set(re.findall(r'JMP\s+(?:zu_)?([a-z][A-Za-z0-9_]+)', haken)) | set(re.findall(r'CALL\s+([a-z][A-Za-z0-9_]+)', haken))

def kurz(t, n=120):
    t = re.sub(r'\s+', ' ', t).strip()
    return t if len(t) <= n else t[:n - 1].rsplit(' ', 1)[0] + ' …'

def routinen(datei):
    zeilen = open(os.path.join(D, datei), encoding='utf-8').read().split('\n')
    aus = []
    for i, z in enumerate(zeilen):
        m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*):', z)
        if not m: continue
        n = m.group(1)
        kom = []
        j = i - 1
        while j >= 0 and zeilen[j].startswith(';') and not zeilen[j].startswith('; ==='):
            if not zeilen[j].startswith('; ---'): kom.insert(0, zeilen[j][1:].strip())
            j -= 1
        benannt = any(re.match(rf'(\d\.\d\d\s+)?{re.escape(n)}\b', k) for k in kom)
        absatz = j < 0 or zeilen[j].strip() == '' or zeilen[j].startswith('; ===')
        befehl = bool(re.search(r';\s*(\d\.\d\d:\s*)?\d\d [A-Z]{3}\b', z))   # z. B. „; 6.10: 48 JOV“          # Marke beginnt einen Absatz
        if n not in gerufen and not benannt and not absatz and not befehl: continue
        zweck = ''
        if kom:
            for k in kom:
                k2 = re.sub(rf'^(\d\.\d\d\s+)?{re.escape(n)}\s*(\([^)]*\))?\s*:?\s*', '', k)
                if k2 and not re.match(r'(Firmware|Fernsteuerung, Teil)', k2): zweck = k2; break
        if not zweck and ';' in z: zweck = z.split(';', 1)[1].strip()
        aus.append((sym.get(n), n, kurz(zweck)))
    return aus

def tabelle(r):
    o = ['| Adresse | Routine | Zweck |', '|---|---|---|']
    for a, n, t in r:
        o.append(f'| {a:04X} | `{n}` | {t.replace("|", "/")} |' if a is not None else f'| | `{n}` | {t} |')
    return '\n'.join(o)

print('# Firmware 6.x – Routinen je Block\n')
print('Erzeugt von `firmware/v6/routinen.py` aus den Quelltexten und der Symboltabelle des Builds. '
      'Adressen sind EEPROM-Adressen (28C256, A14 = 1 im Betrieb). Nur Routinen, keine Sprungmarken innerhalb einer Routine. '
      'Überblick und Regeln stehen in `docs/firmware6-de.md`.\n')
for nr, datei, titel in BLOECKE:
    r = routinen(datei)
    print(f'## Block {nr} – {titel}\n\nQuelle `firmware/v6/{datei}`, {len(r)} Routinen.\n')
    print(tabelle(r) + '\n')
print('## Block 0xxx – Original mit Haken, Fernsteuerung im Interrupt\n')
print('Die unteren acht 2-KB-Blöcke sind gleich: das Kosmos-Original (nicht im Repo) mit Haken, die per '
      '`SEL MB1` / `JMP` in die oberen Blöcke springen, und der Fernsteuerung (NIE) in toten Resten alter Routinen.\n')
for datei, wo in UNTEN:
    r = routinen(datei)
    print(f'### `{datei}` → {wo}\n')
    print(tabelle(r) + '\n')
tab = sorted((a, n) for n, a in sym.items() if re.match(r'(zu|fa)_', n) and a >= 0x7000)
nzu = sum(1 for a, n in tab if n.startswith('zu_'))
print(f'## Sprungtabelle ({len(tab)} Einträge: {nzu} Sprünge zu_X, {len(tab) - nzu} Fernaufrufe fa_X; in jedem oberen Block an derselben Stelle)\n')
print('`zu_X` wechselt in den Block von X und springt (JMP). `fa_X` ist ein Fernaufruf von 1001 nach 1011: '
      '`ORL P1,#$20` / `CALL X` / `ANL P1,#$df` / `RET`, kostet eine Stapelebene.\n')
print(', '.join(f'`{n}`' for a, n in tab) + '\n')
