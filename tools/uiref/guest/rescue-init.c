/*
 * rescue-init.c - PID 1 for a Linux initramfs that installs an OS X 10.9
 * payload from a read-only squashfs into an HFS+ volume, without a GUI and
 * without the Apple installer.
 *
 * It is a static binary on purpose: the early initramfs of the Arch ISO has no
 * shell, so the kernel runs this directly. Modules (squashfs, hfsplus) come
 * from the same initramfs, uncompressed, and are loaded with finit_module.
 *
 * Everything it does is printed to the serial console between MVSTEP markers,
 * and it ends with MV_INSTALL_DONE followed by a halt, so the host can wait
 * for an unambiguous completion marker.
 */
#define _GNU_SOURCE
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/reboot.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/sysmacros.h>
#include <sys/types.h>
#include <unistd.h>

#define COPY_BUF (4u << 20)

static unsigned long files_done;
static unsigned long dirs_done;
static unsigned long bytes_done;

static void step(const char *msg)
{
    printf("MVSTEP %s\n", msg);
    fflush(stdout);
}

static void fail(const char *msg)
{
    printf("MVFAIL %s\n", msg);
    fflush(stdout);
}

static char *slurp(const char *path, unsigned long *len_out)
{
    int fd = open(path, O_RDONLY);
    struct stat st;
    char *buf;
    if (fd < 0)
        return NULL;
    if (fstat(fd, &st) != 0 || st.st_size <= 0) {
        close(fd);
        return NULL;
    }
    buf = malloc((size_t)st.st_size);
    if (!buf) {
        close(fd);
        return NULL;
    }
    {
        ssize_t got = read(fd, buf, (size_t)st.st_size);
        close(fd);
        if (got <= 0) {
            free(buf);
            return NULL;
        }
        *len_out = (unsigned long)got;
    }
    return buf;
}

static void load_module(const char *path)
{
    unsigned long len = 0;
    char *buf;
    int fd, rc;
    buf = slurp(path, &len);
    if (!buf) {
        printf("MVWARN module missing: %s\n", path);
        return;
    }
    /* finit_module wants a real descriptor; -1 is invalid */
    fd = open(path, O_RDONLY);
    if (fd >= 0) {
        rc = (int)syscall(__NR_finit_module, fd, "", 0);
        close(fd);
    } else {
        rc = -1;
    }
    if (rc != 0) {
        /* fall back to init_module(2) with the image in memory */
        rc = (int)syscall(__NR_init_module, buf, len, "");
    }
    printf("MVSTEP module %s -> %d (%s)\n", path, rc, strerror(rc < 0 ? -rc : 0));
    free(buf);
}

static void dump_partitions(void)
{
    FILE *f = fopen("/proc/partitions", "r");
    char line[256];
    if (!f) {
        printf("MVSTEP no /proc/partitions\n");
        return;
    }
    while (fgets(line, sizeof(line), f))
        if (line[0] != 0 && strstr(line, "major") == NULL)
            printf("MVSTEP part %s", line);
    fclose(f);
}

static int copy_file(const char *src, const char *dst, const struct stat *st)
{
    int in = open(src, O_RDONLY);
    int out;
    char *buf;
    ssize_t n;
    struct timespec times[2];

    if (in < 0)
        return -1;
    buf = malloc(COPY_BUF);
    if (!buf) {
        close(in);
        return -1;
    }
    unlink(dst);
    out = open(dst, O_WRONLY | O_CREAT | O_TRUNC, st->st_mode & 07777);
    if (out < 0) {
        free(buf);
        close(in);
        return -1;
    }
    while ((n = read(in, buf, COPY_BUF)) > 0) {
        ssize_t off = 0;
        while (off < n) {
            ssize_t w = write(out, buf + off, (size_t)(n - off));
            if (w <= 0) {
                free(buf);
                close(in);
                close(out);
                return -1;
            }
            off += w;
        }
        bytes_done += (unsigned long)n;
    }
    free(buf);
    close(in);
    close(out);
    fchmodat(AT_FDCWD, dst, st->st_mode & 07777, 0);
    fchownat(AT_FDCWD, dst, st->st_uid, st->st_gid, 0);
    times[0] = st->st_atim;
    times[1] = st->st_mtim;
    utimensat(AT_FDCWD, dst, times, 0);
    files_done++;
    if (files_done % 20000 == 0) {
        printf("MVPROGRESS files=%lu dirs=%lu bytes=%lu\n",
               files_done, dirs_done, bytes_done);
        fflush(stdout);
    }
    return 0;
}

static int copy_tree(const char *src, const char *dst)
{
    DIR *d = opendir(src);
    struct dirent *e;
    struct stat st;
    char sp[4096], dp[4096];

    if (!d)
        return -1;
    if (lstat(src, &st) != 0) {
        closedir(d);
        return -1;
    }
    if (!S_ISDIR(st.st_mode)) {
        closedir(d);
        return 0;
    }
    mkdir(dst, st.st_mode & 07777);
    while ((e = readdir(d)) != NULL) {
        if (!strcmp(e->d_name, ".") || !strcmp(e->d_name, ".."))
            continue;
        snprintf(sp, sizeof(sp), "%s/%s", src, e->d_name);
        snprintf(dp, sizeof(dp), "%s/%s", dst, e->d_name);
        if (lstat(sp, &st) != 0)
            continue;
        if (S_ISDIR(st.st_mode)) {
            copy_tree(sp, dp);
            dirs_done++;
        } else if (S_ISLNK(st.st_mode)) {
            char target[4096];
            ssize_t n = readlink(sp, target, sizeof(target) - 1);
            if (n > 0) {
                target[n] = 0;
                unlink(dp);
                if (symlink(target, dp) != 0) {
                    printf("MVWARN symlink %s\n", dp);
                }
            }
        } else if (S_ISREG(st.st_mode)) {
            if (copy_file(sp, dp, &st) != 0)
                printf("MVWARN copy failed %s\n", sp);
        }
        /* device nodes and sockets do not occur in the InstallESD payload */
    }
    closedir(d);
    fchmodat(AT_FDCWD, dst, st.st_mode & 07777, 0);
    fchownat(AT_FDCWD, dst, st.st_uid, st.st_gid, 0);
    {
        struct timespec times[2];
        times[0] = st.st_atim;
        times[1] = st.st_mtim;
        utimensat(AT_FDCWD, dst, times, 0);
    }
    return 0;
}

static int write_file(const char *path, const char *body)
{
    FILE *f = fopen(path, "w");
    if (!f) {
        printf("MVWARN cannot write %s\n", path);
        return -1;
    }
    fputs(body, f);
    fclose(f);
    return 0;
}

static void halt(void)
{
    printf("MV_INSTALL_DONE\n");
    fflush(stdout);
    sync();
    sleep(2);
    reboot(RB_POWER_OFF);
    for (;;)
        pause();
}

int main(void)
{
    static const char *SSHD_CONFIG =
        "PermitRootLogin yes\n"
        "PasswordAuthentication yes\n"
        "PermitEmptyPasswords yes\n"
        "UsePAM no\n"
        "X11Forwarding no\n"
        "PrintMotd no\n"
        "AcceptEnv *\n"
        "Subsystem sftp /usr/lib/ssh/sftp-server\n";
    static const char *SSHD_PLIST =
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" "
        "\"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">\n"
        "<plist version=\"1.0\">\n<dict>\n"
        "  <key>Label</key><string>com.mavlinos.sshd</string>\n"
        "  <key>ProgramArguments</key>\n"
        "  <array><string>/usr/sbin/sshd</string><string>-D</string></array>\n"
        "  <key>RunAtLoad</key><true/>\n"
        "  <key>KeepAlive</key><true/>\n"
        "  <key>StandardOutPath</key><string>/tmp/mvsshd.log</string>\n"
        "  <key>StandardErrorPath</key><string>/tmp/mvsshd.err</string>\n"
        "</dict>\n</plist>\n";

    static const char *CANDIDATES[] = {"/dev/sda", "/dev/sda1", "/dev/sda2",
                                       "/dev/sdb", "/dev/sdb1", "/dev/sdc",
                                       "/dev/sdc1", "/dev/sr0", NULL};
    const char *src = NULL, *tgt = NULL;
    int i;
    struct stat st;

    step("rescue-init start");
    mkdir("/dev", 0755);
    mkdir("/proc", 0755);
    mkdir("/sys", 0755);
    mount("proc", "/proc", "proc", 0, NULL);
    mount("sysfs", "/sys", "sysfs", 0, NULL);
    if (mount("devtmpfs", "/dev", "devtmpfs", 0, NULL) != 0)
        printf("MVWARN devtmpfs mount failed: %s\n", strerror(errno));
    load_module("/usr/lib/modules/rescue/squashfs.ko");
    load_module("/usr/lib/modules/rescue/ata_piix.ko");
    load_module("/usr/lib/modules/rescue/nls_utf8.ko");
    load_module("/usr/lib/modules/rescue/cdrom.ko");
    load_module("/usr/lib/modules/rescue/hfsplus.ko");
    sleep(1);

    dump_partitions();
    {
        static const char *devs[] = {"/dev/sda", "/dev/sdb", "/dev/sdb1", NULL};
        long r;
        int k;
        for (k = 0; devs[k]; k++) {
            struct stat sb;
            int fd;
            if (stat(devs[k], &sb) != 0) {
                printf("MVSTEP node %s stat failed %s\n", devs[k], strerror(errno));
                continue;
            }
            fd = open(devs[k], O_RDONLY);
            printf("MVSTEP node %s mode=%o rdev=%lu:%lu open=%d size=%lld\n", devs[k],
                   (unsigned)sb.st_mode,
                   (unsigned long)major(sb.st_rdev), (unsigned long)minor(sb.st_rdev),
                   fd, (long long)sb.st_size);
            if (fd >= 0) close(fd);
        }
        {
            DIR *bd = opendir("/sys/block");
            struct dirent *e;
            while (bd && (e = readdir(bd)) != NULL) {
                char p[256], buf[64];
                FILE *f;
                if (e->d_name[0] == '.') continue;
                snprintf(p, sizeof(p), "/sys/block/%s/dev", e->d_name);
                f = fopen(p, "r");
                if (f) {
                    if (fgets(buf, sizeof(buf), f))
                        printf("MVSTEP sysblock %s dev=%s", e->d_name, buf);
                    fclose(f);
                }
            }
            if (bd) closedir(bd);
        }
        errno = 0;
        r = syscall(SYS_mount, "/dev/sda", "/mnt/src", "squashfs", MS_RDONLY, NULL);
        printf("MVSTEP mount syscall sda -> %ld (%s)\n", r, strerror(errno));
        errno = 0;
        r = syscall(SYS_mount, "/mnt/src", "/mnt/src", "squashfs", MS_BIND, NULL);
        printf("MVSTEP mount bind -> %ld (%s)\n", r, strerror(errno));
    }
    {
        FILE *ff = fopen("/proc/filesystems", "r");
        char ln[256];
        printf("MVSTEP filesystems:");
        while (ff && fgets(ln, sizeof(ln), ff)) {
            ln[strcspn(ln, "\n")] = 0;
            printf(" [%s]", ln);
        }
        {
            DIR *md = opendir("/sys/module");
            struct dirent *e;
            int n = 0;
            while (md && (e = readdir(md)) != NULL) {
                if (strstr(e->d_name, "squash") || strstr(e->d_name, "hfs") ||
                    strstr(e->d_name, "ata_piix") || strstr(e->d_name, "cdrom"))
                    printf(" MVSTEP loaded_module %s", e->d_name);
                n++;
            }
            printf("\nMVSTEP modules_in_sys=%d", n);
            if (md) closedir(md);
        }
        printf("\n");
        if (ff) fclose(ff);
    }
    {
        int fd = open("/dev/sdb1", O_RDONLY);
        printf("MVSTEP open /dev/sdb1 -> %d %s\n", fd, fd < 0 ? strerror(errno) : "ok");
        if (fd >= 0) close(fd);
    }
    mkdir("/mnt", 0755);
    mkdir("/mnt/src", 0755);
    mkdir("/mnt/tgt", 0755);
    for (i = 0; CANDIDATES[i]; i++) {
        if (stat(CANDIDATES[i], &st) != 0)
            continue;
        if (!src) {
            if (mount(CANDIDATES[i], "/mnt/src", "squashfs", MS_RDONLY, NULL) == 0)
                src = CANDIDATES[i];
            else
                printf("MVSTEP mount %s squashfs -> %s\n", CANDIDATES[i],
                       strerror(errno));
        }
    }
    printf("MVSTEP source=%s\n", src ? src : "(none)");
    for (i = 0; CANDIDATES[i]; i++) {
        if (stat(CANDIDATES[i], &st) != 0)
            continue;
        if (src && !strcmp(CANDIDATES[i], src))
            continue;
        if (tgt)
            continue;
        if (mount(CANDIDATES[i], "/mnt/tgt", "hfsplus", 0, NULL) == 0)
            tgt = CANDIDATES[i];
        else
            printf("MVSTEP mount %s hfsplus -> %s\n", CANDIDATES[i], strerror(errno));
    }
    printf("MVSTEP target=%s\n", tgt ? tgt : "(none)");
    if (!src || !tgt) {
        DIR *d = opendir("/sys/class");
        struct dirent *e;
        fail("could not mount the squashfs payload or the HFS+ target");
        printf("MVSTEP /dev entries:");
        {
            DIR *dv = opendir("/dev");
            while (dv && (e = readdir(dv)) != NULL)
                if (strncmp(e->d_name, "sd", 2) == 0 || strncmp(e->d_name, "hd", 2) == 0)
                    printf(" %s", e->d_name);
            printf("\n");
        }
        while (d && (e = readdir(d)) != NULL)
            printf("MVSTEP sysclass %s\n", e->d_name);
        halt();
    }

    dump_partitions();
    {
        static const char *devs[] = {"/dev/sda", "/dev/sdb", "/dev/sdb1", NULL};
        long r;
        int k;
        for (k = 0; devs[k]; k++) {
            struct stat sb;
            int fd;
            if (stat(devs[k], &sb) != 0) {
                printf("MVSTEP node %s stat failed %s\n", devs[k], strerror(errno));
                continue;
            }
            fd = open(devs[k], O_RDONLY);
            printf("MVSTEP node %s mode=%o rdev=%lu:%lu open=%d size=%lld\n", devs[k],
                   (unsigned)sb.st_mode,
                   (unsigned long)major(sb.st_rdev), (unsigned long)minor(sb.st_rdev),
                   fd, (long long)sb.st_size);
            if (fd >= 0) close(fd);
        }
        {
            DIR *bd = opendir("/sys/block");
            struct dirent *e;
            while (bd && (e = readdir(bd)) != NULL) {
                char p[256], buf[64];
                FILE *f;
                if (e->d_name[0] == '.') continue;
                snprintf(p, sizeof(p), "/sys/block/%s/dev", e->d_name);
                f = fopen(p, "r");
                if (f) {
                    if (fgets(buf, sizeof(buf), f))
                        printf("MVSTEP sysblock %s dev=%s", e->d_name, buf);
                    fclose(f);
                }
            }
            if (bd) closedir(bd);
        }
        errno = 0;
        r = syscall(SYS_mount, "/dev/sda", "/mnt/src", "squashfs", MS_RDONLY, NULL);
        printf("MVSTEP mount syscall sda -> %ld (%s)\n", r, strerror(errno));
        errno = 0;
        r = syscall(SYS_mount, "/mnt/src", "/mnt/src", "squashfs", MS_BIND, NULL);
        printf("MVSTEP mount bind -> %ld (%s)\n", r, strerror(errno));
    }
    {
        FILE *ff = fopen("/proc/filesystems", "r");
        char ln[256];
        printf("MVSTEP filesystems:");
        while (ff && fgets(ln, sizeof(ln), ff)) {
            ln[strcspn(ln, "\n")] = 0;
            printf(" [%s]", ln);
        }
        {
            DIR *md = opendir("/sys/module");
            struct dirent *e;
            int n = 0;
            while (md && (e = readdir(md)) != NULL) {
                if (strstr(e->d_name, "squash") || strstr(e->d_name, "hfs") ||
                    strstr(e->d_name, "ata_piix") || strstr(e->d_name, "cdrom"))
                    printf(" MVSTEP loaded_module %s", e->d_name);
                n++;
            }
            printf("\nMVSTEP modules_in_sys=%d", n);
            if (md) closedir(md);
        }
        printf("\n");
        if (ff) fclose(ff);
    }
    {
        int fd = open("/dev/sdb1", O_RDONLY);
        printf("MVSTEP open /dev/sdb1 -> %d %s\n", fd, fd < 0 ? strerror(errno) : "ok");
        if (fd >= 0) close(fd);
    }
    step("HFS+ write test");
    {
        int fd = open("/mnt/tgt/__mvtest.txt", O_WRONLY | O_CREAT | O_TRUNC, 0644);
        if (fd >= 0) {
            ssize_t w = write(fd, "mavlinos", 8);
            printf("MVSTEP hfsplus write -> %zd bytes\n", w);
            close(fd);
        } else {
            printf("MVWARN hfsplus create failed: %s\n", strerror(errno));
        }
        {
            char buf[32] = {0};
            int rd = open("/mnt/tgt/__mvtest.txt", O_RDONLY);
            if (rd >= 0) {
                ssize_t r = read(rd, buf, sizeof(buf) - 1);
                printf("MVSTEP hfsplus readback -> %zd bytes: %s\n", r, buf);
                close(rd);
            } else {
                printf("MVWARN hfsplus readback failed: %s\n", strerror(errno));
            }
        }
        unlink("/mnt/tgt/__mvtest.txt");
    }

    step("copying payload into the HFS+ volume");
    if (copy_tree("/mnt/src", "/mnt/tgt") != 0)
        printf("MVWARN copy_tree reported an error, continuing\n");
    printf("MVSTEP copied files=%lu dirs=%lu bytes=%lu\n",
           files_done, dirs_done, bytes_done);
    sync();

    step("writing first-boot configuration");
    mkdir("/mnt/tgt/etc/ssh", 0755);
    mkdir("/mnt/tgt/Library/LaunchDaemons", 0755);
    write_file("/mnt/tgt/etc/ssh/sshd_config", SSHD_CONFIG);
    write_file("/mnt/tgt/Library/LaunchDaemons/com.mavlinos.sshd.plist", SSHD_PLIST);
    sync();

    step("verifying the result");
    if (stat("/mnt/tgt/System/Library/CoreServices/boot.efi", &st) == 0)
        printf("MVSTEP boot.efi present (%lld bytes)\n", (long long)st.st_size);
    else
        printf("MVWARN boot.efi missing\n");
    if (stat("/mnt/tgt/System/Library/Frameworks/AppKit.framework", &st) == 0)
        printf("MVSTEP AppKit.framework present\n");
    else
        printf("MVWARN AppKit.framework missing\n");
    sync();
    halt();
    return 0;
}
