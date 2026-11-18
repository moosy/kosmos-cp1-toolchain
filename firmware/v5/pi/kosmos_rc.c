/* kosmos_rc – Übertragung zum Kosmos CP1 direkt über die GPIO-Register (/dev/gpiomem). Firmware 5.00.
 *
 * Läuft dauerhaft neben kosmos_remote.py (Pipe): je Zeile auf stdin ein Auftrag
 *   NIE (Fernsteuerung im Interrupt des CP1):   <rahmen-hex oder -> <bits>
 *     "-"      = nur anklopfen, 3,5 ms (Statusabfrage, der CP1 hält dafür nicht an)
 *     rahmen   = 8,5 ms anklopfen, dann 4 Byte senden (je Bit Low 50 µs = 1 / 150 µs = 0, danach 50 µs high)
 *     bits     = so viele Low-Pulse der Antwort messen
 *     Antwort:  OK <low_us> <low_us> ...   bzw.  TIMEOUT <low_us> ...
 *   FNI (CP1 mit abgeschaltetem Interrupt, getaktet):   F <E|A|K|N> <anf> <anz> <kopf-hex> [<daten-hex>]
 *     E = Pi sendet (Pi -> 8155 / Flash), A = Pi empfängt; anf/anz = Zellen (anz 0 = 256), kopf = 4 Byte
 *     K = Bank komplett empfangen: 256 Zellen + Bankkopf 18 Byte (Blöcke 8/8/2)
 *     N = alle Namen: je Bank Blöcke 8/8/2 = Bank, 0, Name 16; Ende = 8-Byte-Block mit Bank 0
 *     Antwort:  OK [<daten-hex>]   bzw.  FEHLER <grund>
 *
 * Leitungen (Pi Zero, BCM-Nummern): D = GPIO 26 (Pin 37, Klemme 8 = P1.7), T = GPIO 19 (Pin 35, Klemme 7 = P1.6).
 * Low = Ausgang mit 0, sonst Eingang (CP1 und Pullup ziehen hoch) – beide Seiten ziehen nur nach low.
 * Echtzeit (SCHED_FIFO) braucht CAP_SYS_NICE (kommt vom systemd-Dienst).
 *
 * gcc -O2 -o kosmos_rc kosmos_rc.c
 */
#include <fcntl.h>
#include <sched.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <time.h>
#include <signal.h>
#include <unistd.h>

#define GPIO 26                /* D */
#define GPIO_T 19              /* T (FNI-Takt) */
#define KLOPF_US 3500          /* Statusabfrage: 1-2 Interrupt-Takte low */
#define KLOPF_BEFEHL_US 8500   /* Befehl: >= 3 Takte low, dann hört der CP1 zu */
#define NACH_KLOPF_US 300
#define EINS_US 50
#define NULL_US 150
#define LUECKE_US 50
/* FNI: Mindestzeiten; Verzögerungen des Pi verlängern nur (der CP1 fragt alle 15 µs ab) */
#define FNI_LOW_US 80             /* der CP1 (4 MHz, Abfrage alle 22,5 µs) hält T nach höchstens ~45 µs fest */
#define FNI_HIGH_US 100           /* T high, bevor der Pi wieder zieht: der CP1 muss das High sicher sehen */
#define FNI_ANNAHME_US 300000  /* so lange auf „T low“ (Auftrag übernommen) warten */
#define FNI_FRIST_US 5000000   /* so lange darf der CP1 T festhalten (Flash löschen/kopieren) */

static volatile uint32_t *g;

static inline uint64_t us(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC_RAW, &t);
    return (uint64_t)t.tv_sec * 1000000u + t.tv_nsec / 1000;
}
static inline void warte_bis(uint64_t t) { while (us() < t) ; }
static inline void low(void) {
    g[0x28 / 4] = 1u << GPIO;                                   /* GPCLR0 */
    g[0x08 / 4] = (g[0x08 / 4] & ~(7u << 18)) | (1u << 18);     /* GPFSEL2: Ausgang */
}
static inline void los(void) { g[0x08 / 4] &= ~(7u << 18); }    /* Eingang */
static inline int pegel(void) { return (g[0x34 / 4] >> GPIO) & 1; }
/* T = GPIO 19: GPFSEL1, Bits 27..29 */
static inline void t_low(void) {
    g[0x28 / 4] = 1u << GPIO_T;
    g[0x04 / 4] = (g[0x04 / 4] & ~(7u << 27)) | (1u << 27);
}
static inline void t_los(void) { g[0x04 / 4] &= ~(7u << 27); }
static inline int t_pegel(void) { return (g[0x34 / 4] >> GPIO_T) & 1; }
static void ende(int sig) { los(); t_los(); _exit(sig ? 128 + sig : 0); }   /* nie mit Leitung low aufhören */

/* ---------------- FNI ---------------- */
static int t_warten(int pegel_soll, uint64_t frist_us) {
    uint64_t ende_ = us() + frist_us;
    while (t_pegel() != pegel_soll) if (us() > ende_) return 0;
    return 1;
}
static int blocknr = 0;
static int bit_senden(int b) {
    if (!t_warten(1, FNI_FRIST_US)) return 0;
    warte_bis(us() + FNI_HIGH_US);
    if (b) los(); else low();
    uint64_t t = us(); t_low(); warte_bis(t + FNI_LOW_US); t_los();
    return 1;
}
static int bit_lesen(int *b) {
    if (!t_warten(1, FNI_FRIST_US)) return 0;
    warte_bis(us() + FNI_HIGH_US);
    los();
    uint64_t t = us(); t_low(); warte_bis(t + FNI_LOW_US); t_los();
    if (!t_warten(1, FNI_FRIST_US)) return 0;    /* der CP1 hat D gesetzt und lässt T los */
    *b = pegel();
    return 1;
}
static uint8_t crc8(const uint8_t *d, int n) {
    uint8_t c = 0;
    for (int i = 0; i < n; i++) { c ^= d[i]; for (int k = 0; k < 8; k++) c = (c & 0x80) ? (uint8_t)((c << 1) ^ 0x07) : (uint8_t)(c << 1); }
    return c;
}
static int byte_senden(uint8_t x) { for (int k = 0; k < 8; k++) if (!bit_senden(x >> k & 1)) return 0; return 1; }
static int byte_lesen(uint8_t *x) {
    *x = 0;
    for (int k = 0; k < 8; k++) { int b; if (!bit_lesen(&b)) return 0; *x |= (uint8_t)(b << k); }
    return 1;
}
/* 1 gut, 0 Zeit um, -1 nach Versuchen aufgegeben */
static int block_senden(const uint8_t *d, int n) {
    blocknr++;
    for (int v = 0; v < 3; v++) {          /* wie der CP1: 3 Versuche */
        for (int i = 0; i < n; i++) if (!byte_senden(d[i])) return 0;
        if (!byte_senden(crc8(d, n))) return 0;
        int q; if (!bit_lesen(&q)) return 0;
        if (q) return 1;
        fprintf(stderr, "FNI: Block %d (%d Byte) vom CP1 nicht angenommen, Versuch %d\n", blocknr, n, v + 1);
    }
    return -1;
}
static int block_lesen(uint8_t *d, int n) {
    uint8_t buf[9];
    blocknr++;
    for (int v = 0; v < 3; v++) {          /* wie der CP1: 3 Versuche */
        for (int i = 0; i <= n; i++) if (!byte_lesen(&buf[i])) return 0;
        int ok = crc8(buf, n) == buf[n];
        if (!bit_senden(ok)) return 0;
        if (ok) { memcpy(d, buf, n); return 1; }
        fprintf(stderr, "FNI: Block %d (%d Byte) mit falscher CRC empfangen, Versuch %d\n", blocknr, n, v + 1);
    }
    return -1;
}
static void fni(char *zeile) {
    char richtung; unsigned anf, anz; char kopfhex[16] = "", datenhex[2700] = "";
    static uint8_t daten[256 * 18 + 600];
    if (sscanf(zeile, "F %c %u %u %15s %2699s", &richtung, &anf, &anz, kopfhex, datenhex) < 4 || strlen(kopfhex) != 8) { printf("FEHLER Aufruf\n"); return; }
    uint8_t kopf[4]; for (int i = 0; i < 4; i++) { unsigned x; sscanf(kopfhex + 2 * i, "%2x", &x); kopf[i] = x; }
    int zellen = anz ? (int)anz : 256, laenge = 0;
    if (richtung == 'E') {
        laenge = (int)strlen(datenhex) / 2;      /* 5.03: hinter den Zellen ggf. der Namensbereich (Vielfaches von 8) */
        if (laenge < 2 * zellen || (laenge - 2 * zellen) % 8) { printf("FEHLER Datenlaenge\n"); return; }
        for (int i = 0; i < laenge; i++) { unsigned x; sscanf(datenhex + 2 * i, "%2x", &x); daten[i] = x; }
    }
    los(); t_los(); blocknr = 0;
    if (!t_warten(0, FNI_ANNAHME_US)) { printf("FEHLER nicht_angenommen\n"); return; }
    int r;
    if (richtung == 'N') {          /* alle Namen */
        uint8_t k[4]; r = block_lesen(k, 4);
        if (r != 1 || memcmp(k, kopf, 4)) { printf("FEHLER Kopf\n"); los(); t_los(); return; }
        for (;;) {
            if (laenge + 18 > (int)sizeof daten) { printf("FEHLER zu_viele\n"); los(); t_los(); return; }
            if (block_lesen(daten + laenge, 8) != 1) { printf("FEHLER Namen\n"); los(); t_los(); return; }
            if (daten[laenge] == 0) break;
            if (block_lesen(daten + laenge + 8, 8) != 1 || block_lesen(daten + laenge + 16, 2) != 1) { printf("FEHLER Namen\n"); los(); t_los(); return; }
            laenge += 18;
        }
        los();
        if (!t_warten(1, FNI_FRIST_US)) { printf("FEHLER Ende\n"); t_los(); return; }
        printf("OK ");
        for (int i = 0; i < laenge; i++) printf("%02x", daten[i]);
        printf("\n");
        return;
    }
    if (richtung == 'E') r = block_senden(kopf, 4);
    else { uint8_t k[4]; r = block_lesen(k, 4); if (r == 1 && memcmp(k, kopf, 4)) { printf("FEHLER Kopf\n"); los(); t_los(); return; } }
    if (r != 1) { printf("FEHLER Kopf_%s\n", r ? "aufgegeben" : "Zeit"); los(); t_los(); return; }
    int c = anf & 0xFF, rest = zellen, pos = 0;
    while (rest) {
        int k = 4 - (c & 3); if (k > rest) k = rest;
        r = richtung == 'E' ? block_senden(daten + pos, 2 * k) : block_lesen(daten + pos, 2 * k);   /* A und K */
        if (r != 1) { printf("FEHLER Block_%d_%s\n", pos / 2, r ? "aufgegeben" : "Zeit"); los(); t_los(); return; }
        pos += 2 * k; rest -= k; c = (c + k) & 0xFF;
    }
    if (richtung == 'E')            /* 5.03 ($29): Namensbereich in 8-Byte-Blöcken */
        for (; pos < laenge; pos += 8)
            if ((r = block_senden(daten + pos, 8)) != 1) { printf("FEHLER Namen_%s\n", r ? "aufgegeben" : "Zeit"); los(); t_los(); return; }
    if (richtung == 'K')            /* 5.03: 0x200..0x5FF (Name, Generation, gültig, Namensbereich), 128 Blöcke à 8 */
        for (int i = 0; i < 128; i++, pos += 8)
            if (block_lesen(daten + pos, 8) != 1) { printf("FEHLER Bankkopf\n"); los(); t_los(); return; }
    los();
    if (!t_warten(1, FNI_FRIST_US)) { printf("FEHLER Ende\n"); t_los(); return; }
    printf("OK");
    if (richtung != 'E') { printf(" "); for (int i = 0; i < pos; i++) printf("%02x", daten[i]); }
    printf("\n");
}

int main(void) {
    int fd = open("/dev/gpiomem", O_RDWR | O_SYNC);
    if (fd < 0) { perror("/dev/gpiomem"); return 1; }
    g = mmap(NULL, 4096, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (g == MAP_FAILED) { perror("mmap"); return 1; }
    mlockall(MCL_CURRENT | MCL_FUTURE);
    signal(SIGTERM, ende); signal(SIGINT, ende); signal(SIGHUP, ende); signal(SIGPIPE, ende);
    struct sched_param sp = { .sched_priority = 50 };
    int rt = sched_setscheduler(0, SCHED_FIFO, &sp) == 0;
    setvbuf(stdout, NULL, _IOLBF, 0);
    printf("BEREIT %s\n", rt ? "rt" : "ohne-rt");

    char zeile[3000];
    static unsigned lows[4096];
    while (fgets(zeile, sizeof zeile, stdin)) {
        if (zeile[0] == 'F') { fni(zeile); continue; }
        char rahmen[64]; int bits = 0;
        if (sscanf(zeile, "%63s %d", rahmen, &bits) != 2 || bits < 0 || bits > 4096) { printf("FEHLER\n"); continue; }
        uint8_t b[16]; int nb = 0;
        if (strcmp(rahmen, "-") != 0)
            for (; nb < 16 && rahmen[2 * nb] && rahmen[2 * nb + 1]; nb++) { unsigned x; sscanf(rahmen + 2 * nb, "%2x", &x); b[nb] = x; }

        /* Anklopfen */
        uint64_t t = us();
        low(); warte_bis(t + (nb ? KLOPF_BEFEHL_US : KLOPF_US)); los();
        if (nb) {
            t = us() + NACH_KLOPF_US;
            warte_bis(t);
            for (int i = 0; i < nb; i++)
                for (int k = 0; k < 8; k++) {
                    int lang = (b[i] >> k & 1) ? EINS_US : NULL_US;
                    t = us(); low(); warte_bis(t + lang); los();
                    warte_bis(us() + LUECKE_US);
                }
        }
        /* Antwort messen: Bytes kommen je Interrupt (2,56 ms), erstes nach ~2,6 ms */
        int n = 0, alt = 1; uint64_t t_low = 0, ende = us() + 12000 + (uint64_t)bits * 900, letzt = us();
        while (n < bits) {
            int v = pegel();
            uint64_t jetzt = us();
            if (v != alt) {
                if (!v) t_low = jetzt; else lows[n++] = (unsigned)(jetzt - t_low);
                alt = v; letzt = jetzt;
            }
            if (jetzt > ende || (n && jetzt - letzt > 8000)) break;
        }
        printf(n >= bits ? "OK" : "TIMEOUT");
        for (int i = 0; i < n; i++) printf(" %u", lows[i]);
        printf("\n");
    }
    ende(0);
    return 0;
}
