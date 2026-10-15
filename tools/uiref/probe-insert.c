/*
 * probe-insert.c - the smallest possible DYLD_INSERT_LIBRARIES probe.
 *
 * Its only job is to answer one question with no ambiguity: can an injected
 * dylib run its constructor inside a Mavericks application at all?  It calls
 * exactly one libSystem function (write(2)) and touches no Objective-C API,
 * so any failure here cannot be blamed on AppKit or on our inspector logic.
 *
 * Build: tools/uiref/build-probe-insert.sh
 */
typedef void *id;
typedef void *Class;
typedef void *SEL;

extern long write(int fd, const void *buf, unsigned long count);
extern int getpid(void);
extern int pthread_create(void *th, const void *attr,
                          void *(*start)(void *), void *arg);
extern unsigned int sleep(unsigned int s);

static void *probe_thread(void *arg) {
    (void)arg;
    write(2, "probe-insert: thread started\n", 29);
    sleep(3);
    write(2, "probe-insert: thread slept ok\n", 30);
    return 0;
}

__attribute__((constructor)) static void probe_insert_init(void) {
    write(2, "probe-insert: constructor ran, pid=", 34);
    char buf[16];
    int n = 0, v = getpid();
    if (v <= 0) { write(2, "?\n", 2); return; }
    char tmp[16];
    while (v > 0 && n < 15) { tmp[n++] = (char)('0' + v % 10); v /= 10; }
    for (int i = n - 1; i >= 0; i--) buf[i] = tmp[n - 1 - i];
    write(2, buf, (unsigned long)n);
    write(2, "\n", 1);
    pthread_create(0, 0, probe_thread, 0);
    write(2, "probe-insert: pthread_create returned\n", 36);
}
