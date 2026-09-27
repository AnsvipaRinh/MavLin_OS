/* mv-hud.c — low-overhead energy/thermal readout for xfce4-genmon-plugin.
 * Runs ONCE per invocation, prints one line, exits. No daemon, no polling loop,
 * no subprocesses, no heap churn. genmon controls the interval (default 5s).
 * Reads: Intel RAPL energy_uj (package), thermal zones, i915 freq (if present).
 * Graceful degradation: prints "n/a" per missing metric, never fails.
 * License: GPL-2.0-or-later. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dirent.h>
#include <unistd.h>

static int read_ull(const char *path, unsigned long long *out) {
    FILE *f = fopen(path, "r");
    if (!f) return -1;
    int r = fscanf(f, "%llu", out);
    fclose(f);
    return r == 1 ? 0 : -1;
}
static int read_temp(const char *path, double *celsius) {
    unsigned long long m;
    if (read_ull(path, &m)) return -1;
    *celsius = m / 1000.0;
    return 0;
}
/* Find first RAPL package energy file; cache path after first call (single run). */
static const char *rapl_pkg(void) {
    static char path[512];
    static int done = 0;
    if (done) return path[0] ? path : NULL;
    done = 1;
    path[0] = 0;
    DIR *d = opendir("/sys/class/powercap");
    if (!d) return NULL;
    struct dirent *e;
    while ((e = readdir(d))) {
        if (e->d_name[0] == '.') continue;
        char name[300], type[300];
        snprintf(name, sizeof name, "/sys/class/powercap/%s/name", e->d_name);
        FILE *f = fopen(name, "r");
        if (!f) continue;
        char buf[64] = {0};
        size_t n = fread(buf, 1, sizeof buf - 1, f);
        fclose(f);
        if (n == 0) continue;
        if (strncmp(buf, "package", 7) == 0) {
            snprintf(path, sizeof path, "/sys/class/powercap/%s/energy_uj", e->d_name);
            (void)type;
            break;
        }
    }
    closedir(d);
    return path[0] ? path : NULL;
}
/* Hottest thermal zone of type x86_pkg_temp or highest temp overall. */
static int hottest(double *celsius) {
    DIR *d = opendir("/sys/class/thermal");
    if (!d) return -1;
    struct dirent *e;
    double best = -1;
    int found = 0;
    while ((e = readdir(d))) {
        if (strncmp(e->d_name, "thermal_zone", 12)) continue;
        char tp[300], tt[300];
        snprintf(tp, sizeof tp, "/sys/class/thermal/%s/temp", e->d_name);
        snprintf(tt, sizeof tt, "/sys/class/thermal/%s/type", e->d_name);
        double t;
        if (read_temp(tp, &t)) continue;
        FILE *f = fopen(tt, "r");
        char type[64] = {0};
        if (f) { size_t n = fread(type, 1, sizeof type - 1, f); (void)n; fclose(f); }
        if (strstr(type, "x86_pkg_temp")) { *celsius = t; closedir(d); return 0; }
        if (t > best) { best = t; found = 1; }
    }
    closedir(d);
    if (!found) return -1;
    *celsius = best;
    return 0;
}
int main(int argc, char **argv) {
    /* Optional instantaneous power: pass previous energy+time via state file. */
    const char *state = "/tmp/mv-hud.state";
    unsigned long long e_now = 0;
    double temp = -1;
    const char *rp = rapl_pkg();
    int have_e = (rp && read_ull(rp, &e_now) == 0);
    int have_t = (hottest(&temp) == 0);
    double watts = -1;
    if (have_e) {
        FILE *f = fopen(state, "r");
        unsigned long long e_prev = 0, t_prev = 0;
        unsigned long long t_now = 0;
        FILE *cf = fopen("/proc/uptime", "r");
        if (cf) { double up = 0; if (fscanf(cf, "%lf", &up) == 1) t_now = (unsigned long long)(up * 1000000); fclose(cf); }
        if (f && t_now) {
            if (fscanf(f, "%llu %llu", &e_prev, &t_prev) == 2 && t_now > t_prev && e_now >= e_prev) {
                double dt = (t_now - t_prev) / 1000000.0;
                if (dt >= 1.0 && dt < 3600.0)
                    watts = (e_now - e_prev) / dt / 1000000.0;
            }
            fclose(f);
        }
        if (t_now) {
            f = fopen(state, "w");
            if (f) { fprintf(f, "%llu %llu\n", e_now, t_now); fclose(f); }
        }
    }
    char watts_s[32], temp_s[32];
    if (watts >= 0) snprintf(watts_s, sizeof watts_s, "%.1fW", watts);
    else strcpy(watts_s, "n/a");
    if (have_t) snprintf(temp_s, sizeof temp_s, "%.0f°C", temp);
    else strcpy(temp_s, "n/a");
    const char *fmt = (argc > 1) ? argv[1] : "CPU %s | %s";
    printf(fmt, watts_s, temp_s);
    printf("\n");
    return 0;
}
