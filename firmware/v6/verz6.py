"""6.00: Projektverzeichnis im simulierten Flash (SPIFlash.m) anlegen und lesen – für die Tests.
Aufbau wie in treiber.asm: Bank b = 8 KB ab b * 0x2000, zwei 4-KB-Sektoren; gültig: 0x211 = 00, Generation 0x210.
Bank 0 = Verzeichnis: 0x000 „CP1V“, 0x004 Version 1; Bank 1 = Einstellungen: 0x000 Autoboot-Projekt (00/FF = aus).
Eintrag n (1..99) im Verzeichnis ab 0x300 + 32 (n - 1):
0..15 Name, 16 erste Bank, 17 reserviert, 18 Flags (FE belegt), 19..24 Kurzanzeige. Projektbank: 0x213 Start-PC."""
BELEGT = 0xFE


def sektor_leer():
    s = bytearray([0xFF]) * 0x1000
    s[0:0x200] = bytes(0x200)                    # Zellen 00 (wie eine neu beschriebene Bank)
    s[0x210] = 0; s[0x211] = 0
    return s


def setzen(fl, bank, sektor, welcher=0):
    """Sektor als gültigen Inhalt der Bank eintragen (der andere Sektor bleibt leer = FF)"""
    a = bank * 0x2000
    fl.m[a:a + 0x2000] = bytes([0xFF]) * 0x2000
    fl.m[a + welcher * 0x1000:a + welcher * 0x1000 + 0x1000] = bytes(sektor)


def gueltig(fl, bank):
    """-> Inhalt des gültigen Sektors (wie f_zustand) oder None"""
    a = bank * 0x2000
    s0, s1 = fl.m[a:a + 0x1000], fl.m[a + 0x1000:a + 0x2000]
    g0, g1 = s0[0x211] == 0, s1[0x211] == 0
    if g0 and g1: return bytes(s1) if (s0[0x210] + 1) & 0xFF == s1[0x210] else bytes(s0)
    if g1: return bytes(s1)
    if g0: return bytes(s0)
    return None


def projektbank(zellen=b'', name=None, start=None, meta=None):
    """Sektor einer Projektbank: zellen (Bytes ab Zelle 0), name, start (0x213), meta = 0x300..0x5FF (setzt 0x212 = 00)"""
    s = sektor_leer()
    s[0:len(zellen)] = zellen
    if name is not None: s[0x200:0x210] = name.encode('latin-1').ljust(16)[:16]
    if start is not None: s[0x213] = start
    if meta is not None:
        s[0x212] = 0; s[0x300:0x300 + len(meta)] = meta
    return s


def verzeichnis(projekte):
    """projekte = {n: {'bank', 'res', 'name', 'anzeige'}} -> Sektor für Bank 0"""
    s = bytearray([0xFF]) * 0x1000
    s[0:0x200] = bytes(0x200)
    s[0:6] = b'CP1V' + bytes([1, 0])
    s[0x210] = 0; s[0x211] = 0
    for n, p in projekte.items():
        e = 0x300 + 32 * (n - 1)
        if p.get('name'): s[e:e + 16] = p['name'].encode('latin-1').ljust(16)[:16]
        s[e + 16] = p['bank']; s[e + 17] = p.get('res', 4); s[e + 18] = BELEGT
        if p.get('anzeige') is not None: s[e + 19:e + 25] = bytes(p['anzeige'])
    return s


def lesen(fl):
    """-> {'autoboot', 'projekte': {n: {'bank', 'res', 'name', 'anzeige'}}} oder None (kein Verzeichnis)"""
    s = gueltig(fl, 0)
    if s is None or s[0:4] != b'CP1V': return None
    pr = {}
    for n in range(1, 100):
        e = 0x300 + 32 * (n - 1)
        if s[e + 18] != BELEGT: continue
        roh = s[e:e + 16]
        pr[n] = {'bank': s[e + 16], 'res': s[e + 17],
                 'name': None if roh[0] == 0xFF else roh.decode('latin-1').rstrip(),
                 'anzeige': None if s[e + 19] == 0xFF else list(s[e + 19:e + 25])}
    e = gueltig(fl, 1)
    ab = e[0] if e is not None and e[0] != 0xFF else 0
    return {'version': s[4], 'autoboot': ab, 'projekte': pr}


def anlegen(fl, projekte, autoboot=0):
    """Verzeichnis + Projektbänke auf einmal: projekte = {n: {'bank', 'res', 'name', 'anzeige', 'zellen', 'start',
    'meta'}}"""
    setzen(fl, 0, verzeichnis(projekte))
    if autoboot:
        e = sektor_leer(); e[0] = autoboot; setzen(fl, 1, e)
    for n, p in projekte.items():
        setzen(fl, p['bank'], projektbank(p.get('zellen', b''), p.get('name'), p.get('start'), p.get('meta')))
