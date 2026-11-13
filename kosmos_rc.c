/* kosmos_rc – Fernsteuerungs-Übertragung zum Kosmos CP1 direkt über die GPIO-Register (/dev/gpiomem).
 *
 * Läuft dauerhaft neben kosmos_remote.py (Pipe): je Zeile auf stdin ein Auftrag
 *     <rahmen-hex oder -> <bits>
 *   "-"      = nur anklopfen, 3,5 ms (Statusabfrage, der CP1 hält dafür nicht an)
 *   rahmen   = 8,5 ms anklopfen, dann 4 Byte senden (je Bit Low 150 µs = 1 / 750 µs = 0, danach 150 µs high)
 *   bits     = so viele Low-Pulse der Antwort messen
 * Antwort auf stdout:  OK <low_us> <low_us> ...   bzw.  TIMEOUT <low_us> ...
 *
 * Leitung: GPIO 26 (BCM2835, Pi Zero). Low = Ausgang mit 0, sonst Eingang (der CP1 und der
 * Pullup ziehen hoch) – beide Seiten ziehen nur nach low.
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

#define GPIO 26
#define KLOPF_US 3500          /* Statusabfrage: 1-2 Interrupt-Takte low */
#define KLOPF_BEFEHL_US 8500   /* Befehl: >= 3 Takte low, dann hört der CP1 zu */
#define NACH_KLOPF_US 300
#define EINS_US 150
#define NULL_US 750
#define LUECKE_US 150

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
static void ende(int sig) { los(); _exit(sig ? 128 + sig : 0); }   /* nie mit Leitung low aufhören */

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

    char zeile[256];
    static unsigned lows[4096];
    while (fgets(zeile, sizeof zeile, stdin)) {
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
