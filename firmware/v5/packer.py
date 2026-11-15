"""Seiten-Einpasser mit Lückenfüller (5.00).

einpassen(src, start, assembliere) setzt wie bisher .seite vor Absätze, deren bedingter Sprung über eine
Seitengrenze ginge. Danach füllt er Lücken: einen späteren, kleinen, *verschiebbaren* Absatz holt er vor die
Lücke. Verschiebbar heißt:
  - beginnt mit einer Marke, endet unbedingt (JMP/RET/RETR), der Absatz davor endet ebenfalls unbedingt
    (niemand läuft hinein, und nach dem Entfernen läuft niemand in den nächsten),
  - keine Direktiven (.org/.seite/.db/.equ),
  - seine bedingten Sprünge zielen nur auf eigene Marken, und kein bedingter Sprung von außen zielt hinein.
"""
import re

BEDINGT = {'JB0', 'JB1', 'JB2', 'JB3', 'JB4', 'JB5', 'JB6', 'JB7', 'JC', 'JNC', 'JZ', 'JNZ', 'JF0', 'JF1',
           'JT0', 'JNT0', 'JT1', 'JNT1', 'JTF', 'JNI', 'DJNZ'}
UNBEDINGT = {'JMP', 'RET', 'RETR', 'JMPP'}


def _code(zeile):
    return zeile.split(';')[0].rstrip()


def _zerlege(zeile):
    """-> (marke | None, mnemonik | None, operanden)"""
    c = _code(zeile)
    m = re.match(r'^(\w+):\s*(.*)$', c)
    lab, rest = (m.group(1), m.group(2)) if m else (None, c.strip())
    if not rest: return lab, None, []
    teile = rest.split(None, 1)
    ops = [o.strip() for o in teile[1].split(',')] if len(teile) > 1 else []
    return lab, teile[0].upper(), ops


def absaetze(zeilen, von, bis):
    """Absätze (Zeilenbereiche) zwischen Leerzeilen im Bereich [von, bis)"""
    out, i = [], von
    while i < bis:
        while i < bis and not zeilen[i].strip(): i += 1
        j = i
        while j < bis and zeilen[j].strip(): j += 1
        if j > i: out.append((i, j))
        i = j
    return out


def _info(zeilen, a, b, asm48):
    marken, bed_ziele, mnems, direktive = [], [], [], False
    erste_code_marke = None
    for z in zeilen[a:b]:
        lab, mn, ops = _zerlege(z)
        if lab: marken.append(lab)
        if mn is None: continue
        if erste_code_marke is None: erste_code_marke = bool(marken)
        if mn.startswith('.'): direktive = True
        mnems.append(mn)
        if mn in BEDINGT: bed_ziele.append(ops[-1])
    groesse = 0
    for z in zeilen[a:b]:
        lab, mn, ops = _zerlege(z)
        if mn and not mn.startswith('.'):
            groesse += len(asm48.befehl(mn, ops, 0, _Alle()))
    return {'marken': set(marken), 'bed': bed_ziele, 'letzte': mnems[-1] if mnems else None,
            'start_marke': bool(erste_code_marke), 'direktive': direktive, 'groesse': groesse}


class _Alle(dict):
    """Symboltabelle, die jede Marke kennt (nur für Befehlslängen)"""
    def __contains__(self, k): return True
    def __getitem__(self, k): return 0
    def get(self, k, d=None): return 0


def verschiebbare(zeilen, von, bis, asm48):
    ps = absaetze(zeilen, von, bis)
    infos = [_info(zeilen, a, b, asm48) for a, b in ps]
    alle_bed = {}
    for k, inf in enumerate(infos):
        for z in inf['bed']: alle_bed.setdefault(z, set()).add(k)
    out = []
    for k, ((a, b), inf) in enumerate(zip(ps, infos)):
        if k == 0 or inf['direktive'] or not inf['start_marke']: continue
        if inf['letzte'] not in UNBEDINGT: continue
        if infos[k - 1]['letzte'] not in UNBEDINGT: continue
        if any(z not in inf['marken'] for z in inf['bed']): continue
        if any(q != k for m_ in inf['marken'] for q in alle_bed.get(m_, ())): continue
        out.append((a, b, inf['groesse']))
    return out
