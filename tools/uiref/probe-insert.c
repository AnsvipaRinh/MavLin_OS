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

/* Linked from the guest's real libobjc.A.dylib (see build-probe-insert.sh). */
extern Class objc_getClass(const char *name);
extern SEL sel_registerName(const char *name);

extern long write(int fd, const void *buf, unsigned long count);
extern int getpid(void);
/* pthread_create from this constructor is already known to deadlock on 10.9;
   it is deliberately NOT exercised here any more, so that the Objective-C
   runtime calls below are actually reached. */

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
    /* Is the Objective-C runtime usable from an injected constructor at all?
       This is the one thing our inspector cannot work without. */
    Class nsobj = objc_getClass("NSObject");
    write(2, "probe-insert: objc_getClass(NSObject) = ", 38);
    write(2, nsobj ? "non-NULL" : "NULL", nsobj ? 8 : 4);
    write(2, "\n", 1);
    Class nsapp = objc_getClass("NSApplication");
    write(2, "probe-insert: objc_getClass(NSApplication) = ", 42);
    write(2, nsapp ? "non-NULL" : "NULL", nsapp ? 8 : 4);
    write(2, "\n", 1);
}
