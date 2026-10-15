/*
 * mvax.c - cross-process UI extraction from a running Mavericks desktop via
 * the Accessibility API (AXUIElement, HIServices).
 *
 * This is the complement to nsinspect.c.  nsinspect can see real Objective-C
 * objects but only inside its own process; AXUIElement can see the windows and
 * controls of *other* applications without loading a single line of code into
 * them.  The two are not equivalent and must not be merged: AX exposes an
 * accessibility tree (roles, geometry, state, actions), not the NSView
 * hierarchy.  Both are recorded separately, see docs/UI_REFERENCE/runtime/.
 *
 * Everything is resolved through the CoreFoundation/AX runtime by name, so no
 * Apple SDK is required to build it from Linux.  Symbols are linked against
 * link-time stubs carrying the install names the guest really has.
 *
 * Build: tools/uiref/build-mvax.sh
 */
typedef void *CFTypeRef;
typedef CFTypeRef CFStringRef;
typedef CFTypeRef CFArrayRef;
typedef CFTypeRef CFNumberRef;
typedef CFTypeRef CFBooleanRef;
typedef CFTypeRef CFDictionaryRef;
typedef CFTypeRef CFAllocatorRef;
typedef long CFIndex;
typedef unsigned int CFStringEncoding;
typedef unsigned long CFTypeID;
typedef double CFTimeInterval;
typedef int pid_t;
typedef int Boolean;

typedef struct _ns_FILE FILE;

/* --- libc / CF / AX surface --------------------------------------------- */
extern void *dlopen(const char *path, int mode);
extern void *dlsym(void *handle, const char *sym);
extern char *getenv(const char *name);
extern FILE *fopen(const char *path, const char *mode);
extern int fclose(FILE *f);
extern int fprintf(FILE *f, const char *fmt, ...);
extern int snprintf(char *buf, unsigned long n, const char *fmt, ...);
extern int vsnprintf(char *buf, unsigned long n, const char *fmt, __builtin_va_list ap);
extern int atoi(const char *s);
extern int fflush(FILE *f);
extern int fsync(int fd);
extern int fileno(FILE *f);
extern int rename(const char *from, const char *to);
extern int unlink(const char *path);
extern int strcmp(const char *a, const char *b);
extern unsigned long fwrite(const void *p, unsigned long size, unsigned long n, FILE *f);
extern int getpid(void);
extern unsigned int sleep(unsigned int s);
extern long write(int fd, const void *buf, unsigned long count);

extern CFStringRef CFStringCreateWithCString(CFAllocatorRef, const char *, CFStringEncoding);
extern Boolean CFStringGetCString(CFStringRef, char *, CFIndex, CFStringEncoding);
extern CFTypeID CFGetTypeID(CFTypeRef);
extern CFTypeID CFStringGetTypeID(void);
extern CFTypeID CFArrayGetTypeID(void);
extern CFTypeID CFNumberGetTypeID(void);
extern CFTypeID CFBooleanGetTypeID(void);
extern CFIndex CFArrayGetCount(CFArrayRef);
extern const void *CFArrayGetValueAtIndex(CFArrayRef, CFIndex);
extern Boolean CFNumberGetValue(CFNumberRef, int type, void *value);
extern Boolean CFBooleanGetValue(CFBooleanRef);
extern void CFRelease(CFTypeRef);

extern CFTypeRef AXUIElementCreateApplication(pid_t);
extern CFTypeRef AXUIElementCreateSystemWide(void);
extern int AXUIElementCopyAttributeValue(CFTypeRef, CFStringRef, CFTypeRef *);
extern int AXUIElementCopyAttributeNames(CFTypeRef, CFArrayRef *);
extern int AXUIElementCopyActionNames(CFTypeRef, CFArrayRef *);
extern int AXUIElementPerformAction(CFTypeRef, CFStringRef);
extern Boolean AXIsProcessTrusted(void);
extern int AXUIElementSetMessagingTimeout(CFTypeRef, CFTimeInterval);

#define CF_STRING_ENCODING_ASCII 0x0600
#define CF_NUMBER_SINT32 3
#define CF_NUMBER_DOUBLE 13

#define RTLD_DEFAULT ((void *)-2)

/* --- tiny JSON emitter --------------------------------------------------- */
#define OUT_CAP (1 << 22)
static char out_buf[OUT_CAP];
static unsigned long out_len;

static void emit(const char *s) {
    unsigned long n = 0;
    while (s[n]) n++;
    if (out_len + n < OUT_CAP) {
        for (unsigned long i = 0; i < n; i++) out_buf[out_len + i] = s[i];
        out_len += n;
    }
}
static void emitf(const char *fmt, ...) {
    char tmp[4096];
    __builtin_va_list ap;
    __builtin_va_start(ap, fmt);
    int n = vsnprintf(tmp, sizeof tmp, fmt, ap);
    __builtin_va_end(ap);
    if (n > 0) {
        if (out_len + (unsigned long)n < OUT_CAP) {
            for (int i = 0; i < n; i++) out_buf[out_len + i] = tmp[i];
            out_len += (unsigned long)n;
        }
    }
}

/* --- helpers ------------------------------------------------------------- */
static CFStringRef S(const char *s) {
    return CFStringCreateWithCString(0, s, CF_STRING_ENCODING_ASCII);
}
static int is(CFTypeRef v, CFTypeID t) { return v && CFGetTypeID(v) == t; }

static void json_str(const char *s) {
    emit("\"");
    for (const unsigned char *p = (const unsigned char *)s; p && *p; p++) {
        if (*p == '"' || *p == '\\') { emit("\\"); emit((const char *)p); }
        else if (*p == '\n') emit("\\n");
        else if (*p < 0x20) { char b[8]; snprintf(b, sizeof b, "\\u%04x", *p); emit(b); }
        else { char b[2] = { (char)*p, 0 }; emit(b); }
    }
    emit("\"");
}
static void json_cfstr(CFTypeRef v) {
    if (!is(v, CFStringGetTypeID())) { emit("null"); return; }
    char buf[512];
    if (CFStringGetCString((CFStringRef)v, buf, (CFIndex)sizeof buf, CF_STRING_ENCODING_ASCII))
        json_str(buf);
    else
        emit("null");
}
static void json_cf(CFTypeRef v) {
    if (!v) { emit("null"); return; }
    if (is(v, CFStringGetTypeID())) { json_cfstr(v); return; }
    if (is(v, CFBooleanGetTypeID())) {
        emit(CFBooleanGetValue((CFBooleanRef)v) ? "true" : "false"); return;
    }
    if (is(v, CFNumberGetTypeID())) {
        double d = 0;
        if (CFNumberGetValue((CFNumberRef)v, CF_NUMBER_DOUBLE, &d)) emitf("%g", d);
        else emit("null");
        return;
    }
    if (is(v, CFArrayGetTypeID())) {
        emit("[");
        CFIndex n = CFArrayGetCount((CFArrayRef)v);
        for (CFIndex i = 0; i < n; i++) {
            if (i) emit(",");
            json_cf((CFTypeRef)CFArrayGetValueAtIndex((CFArrayRef)v, i));
        }
        emit("]");
        return;
    }
    emit("null");
}

static int attr(CFTypeRef e, const char *name, CFTypeRef *out) {
    CFStringRef n = S(name);
    int err = AXUIElementCopyAttributeValue(e, n, out);
    CFRelease(n);
    return err;
}
/* Emits the VALUE only. The caller owns the JSON key: the AX attribute name
   is not necessarily the name we want in the document, and emitting both once
   produced invalid JSON ("app_identifier": "AXIdentifier": null). */
static void emit_attr(CFTypeRef e, const char *name) {
    CFTypeRef v = 0;
    int err = attr(e, name, &v);
    if (err == 0) { json_cf(v); if (v) CFRelease(v); }
    else emit("null");
}
static int emit_attr_names(CFTypeRef e) {
    CFArrayRef names = 0;
    int err = AXUIElementCopyAttributeNames(e, &names);
    emitf("\"attribute_names_err\": %d, ", err);
    emit("\"attribute_names\": ");
    if (err == 0 && names) { json_cf(names); CFRelease(names); }
    else emit("[]");
    return err;
}
static int emit_actions(CFTypeRef e) {
    CFArrayRef acts = 0;
    int err = AXUIElementCopyActionNames(e, &acts);
    emitf("\"actions_err\": %d, ", err);
    emit("\"actions\": ");
    if (err == 0 && acts) { json_cf(acts); CFRelease(acts); }
    else emit("[]");
    return err;
}

/* Structural facts that distinguish an AX element from an NSView. */
static void emit_geometry(CFTypeRef e) {
    CFTypeRef v = 0;
    emit("\"position\": ");
    if (attr(e, "AXPosition", &v) == 0 && v) { json_cf(v); CFRelease(v); } else emit("null");
    v = 0;
    emit(", \"size\": ");
    if (attr(e, "AXSize", &v) == 0 && v) { json_cf(v); CFRelease(v); } else emit("null");
}
static void emit_state(CFTypeRef e) {
    static const char *names[] = { "AXEnabled", "AXFocused", "AXSelected", 0 };
    emit("");
    for (int i = 0; names[i]; i++) {
        CFTypeRef v = 0;
        emitf(", \"%s\": ", names[i]);
        if (attr(e, names[i], &v) == 0) { json_cf(v); if (v) CFRelease(v); } else emit("null");
    }
}

static int depth_limit = 24;
static int control_total;
static int node_total;

/* Recursive walk over AXChildren.  Depth is capped so a self-referential or
   cyclic tree cannot hang the extractor; the cap is reported in the output. */
static void walk(CFTypeRef e, int depth) {
    if (!e || depth > depth_limit) return;
    node_total++;
    emit("{\"depth\": ");
    emitf("%d", depth);
    emit(", \"role\": ");        emit_attr(e, "AXRole");
    emit(", \"role_description\": "); emit_attr(e, "AXRoleDescription");
    emit(", \"subrole\": ");    emit_attr(e, "AXSubrole");
    emit(", \"identifier\": "); emit_attr(e, "AXIdentifier");
    emit(", \"description\": ");emit_attr(e, "AXDescription");
    emit(", \"title\": ");      emit_attr(e, "AXTitle");
    emit(", \"label\": ");      emit_attr(e, "AXLabel");
    emit(", \"value\": ");      emit_attr(e, "AXValue");
    emit(", \"help\": ");       emit_attr(e, "AXHelp");
    emit(", \"min_value\": ");  emit_attr(e, "AXMinValue");
    emit(", \"max_value\": ");  emit_attr(e, "AXMaxValue");
    emit(", ");                emit_geometry(e);
    emit(", ");                emit_state(e);
    emit_attr_names(e);
    emit_actions(e);

    CFTypeRef kids = 0;
    if (attr(e, "AXChildren", &kids) == 0 && kids && is(kids, CFArrayGetTypeID())) {
        CFIndex n = CFArrayGetCount((CFArrayRef)kids);
        emit(", \"child_count\": "); emitf("%ld", (long)n);
        emit(", \"children\": [");
        for (CFIndex i = 0; i < n; i++) {
            if (i) emit(",");
            walk((CFTypeRef)CFArrayGetValueAtIndex((CFArrayRef)kids, i), depth + 1);
        }
        emit("]");
        if (kids) CFRelease(kids);
    } else {
        emit(", \"child_count\": null, \"children\": null");
    }
    emit("}");
}

static int walk_windows(CFTypeRef app, int with_children) {
    CFTypeRef wins = 0;
    int err = attr(app, "AXWindows", &wins);
    emitf("\"windows_err\": %d, ", err);
    emit("\"windows\": ");
    if (err != 0 || !wins || !is(wins, CFArrayGetTypeID())) { emit("[]"); return err; }
    CFIndex n = CFArrayGetCount((CFArrayRef)wins);
    emit("[");
    for (CFIndex i = 0; i < n; i++) {
        if (i) emit(",");
        CFTypeRef w = (CFTypeRef)CFArrayGetValueAtIndex((CFArrayRef)wins, i);
        emit("{\"title\": ");  emit_attr(w, "AXTitle");
        emit(", \"role\": "); emit_attr(w, "AXRole");
        emit(", \"subrole\": "); emit_attr(w, "AXSubrole");
        emit(", ");            emit_geometry(w);
        emit(", ");            emit_state(w);
        if (with_children) {
            emit(", ");          emit_attr_names(w);
            emit(", ");          emit_actions(w);
            CFTypeRef kids = 0;
            if (attr(w, "AXChildren", &kids) == 0 && kids && is(kids, CFArrayGetTypeID())) {
                CFIndex cn = CFArrayGetCount((CFArrayRef)kids);
                emit(", \"child_count\": "); emitf("%ld", (long)cn);
                emit(", \"children\": [");
                for (CFIndex k = 0; k < cn; k++) {
                    if (k) emit(",");
                    walk((CFTypeRef)CFArrayGetValueAtIndex((CFArrayRef)kids, k), 1);
                }
                emit("]");
                if (kids) CFRelease(kids);
            } else {
                emit(", \"child_count\": null, \"children\": null");
            }
        }
        emit("}");
    }
    emit("]");
    if (wins) CFRelease(wins);
    return err;
}

/* Discover the pid of a running application by walking the system-wide
   application element's "AXChildren" (one AXApplication per running app). */
static int discover_apps(void) {
    CFTypeRef sys = AXUIElementCreateSystemWide();
    int derr = -1;
    int first = 1;
    if (sys) {
        CFTypeRef kids = 0;
        derr = attr(sys, "AXChildren", &kids);
        if (derr == 0 && kids && is(kids, CFArrayGetTypeID())) {
            CFIndex n = CFArrayGetCount((CFArrayRef)kids);
            for (CFIndex i = 0; i < n; i++) {
                CFTypeRef a = (CFTypeRef)CFArrayGetValueAtIndex((CFArrayRef)kids, i);
                if (!is(a, CFStringGetTypeID()) && !a) continue;
                CFTypeRef pidv = 0;
                if (attr(a, "AXProcessIdentifier", &pidv) != 0 || !pidv) continue;
                int pid = 0;
                CFNumberGetValue((CFNumberRef)pidv, CF_NUMBER_SINT32, &pid);
                if (!pid) { CFRelease(pidv); continue; }
                CFRelease(pidv);
                if (!first) emit(",");
                first = 0;
                emit("{\"pid\": "); emitf("%d", pid);
                emit(", \"name\": ");       emit_attr(a, "AXTitle");
                emit(", \"bundle_id\": ");  emit_attr(a, "AXIdentifier");
                emit(", \"focused\": ");    emit_attr(a, "AXFocused");
                emit(", \"frontmost\": ");  emit_attr(a, "AXMain");
                emit("}");
            }
            if (kids) CFRelease(kids);
        }
        CFRelease(sys);
    }
    emit("]");
    return derr;
}

static void inspect_app(const char *name, int pid, int deep) {
    emit("{\"name\": "); json_str(name);
    emit(", \"pid\": "); emitf("%d", pid);

    CFTypeRef app = AXUIElementCreateApplication((pid_t)pid);
    if (!app) {
        emit(", \"error\": \"AXUIElementCreateApplication returned NULL\"}");
        return;
    }
    AXUIElementSetMessagingTimeout(app, 4.0);

    emit(", \"app_identifier\": ");  emit_attr(app, "AXIdentifier");
    emit(", \"app_title\": ");       emit_attr(app, "AXTitle");
    emit_attr_names(app);
    emit_actions(app);

    CFTypeRef focused = 0;
    emit(", \"focused_window\": ");
    if (attr(app, "AXFocusedWindow", &focused) == 0 && focused) {
        json_cf(focused);
        CFRelease(focused);
    } else emit("null");

    int werr = walk_windows(app, deep);

    emit(", \"ax_errors\": {");
    emitf("\"create_application\": %d, ", app ? 0 : -1);
    emitf("\"windows\": %d, ", werr);
    emitf("\"app_identifier\": %d, ", attr(app, "AXIdentifier", 0));
    emitf("\"children\": %d", attr(app, "AXChildren", 0));
    emit("}");
    emit(", \"nodes_visited\": "); emitf("%d", node_total);
    emit("}");
}

static int write_document(const char *path) {
    char tmp[512];
    snprintf(tmp, sizeof tmp, "%s.tmp", path);
    FILE *f = fopen(tmp, "w");
    if (!f) return 0;
    if (fwrite(out_buf, 1, out_len, f) != out_len) { fclose(f); unlink(tmp); return 0; }
    fflush(f);
    fsync(fileno(f));
    fclose(f);
    if (rename(tmp, path) != 0) { unlink(tmp); return 0; }
    return 1;
}

static int run(int argc, char **argv) {
    if (dlopen("/System/Library/Frameworks/ApplicationServices.framework/"
               "Versions/A/Frameworks/HIServices.framework/Versions/A/HIServices",
               0x4) == 0) {
        emit("{\n  \"schema\": \"mavlinos.axinspect/1\",\n  \"status\": \"failed\",\n");
        emit("  \"error\": \"HIServices framework could not be loaded\"\n}\n");
        return write_document(argv[1]) ? 1 : 1;
    }

    emit("{\n");
    emit("  \"schema\": \"mavlinos.axinspect/1\",\n");
    emit("  \"kind\": \"runtime-observed\",\n");
    emit("  \"method\": \"AXUIElement (HIServices)\",\n");
    emit("  \"extractor\": \"mvax.c\",\n");
    emit("  \"source\": \"cross-process accessibility tree\",\n");
    emit("  \"not_an_nsview_tree\": true,\n");
    emitf("  \"host_pid\": %d,\n", getpid());
    emitf("  \"ax_is_process_trusted\": %s,\n",
         AXIsProcessTrusted() ? "true" : "false");
    emitf("  \"depth_limit\": %d,\n", depth_limit);

    if (argc > 2) depth_limit = atoi(argv[2]);

    int derr = discover_apps();

    emitf(",\n  \"system_wide_children_err\": %d,", derr);

    /* argv[3..] are "name:pid" pairs. */
    emit("\n  \"targets\": [\n");
    int count = 0;
    for (int i = 3; i < argc; i++) {
        char buf[256];
        snprintf(buf, sizeof buf, "%s", argv[i]);
        char *colon = buf;
        while (*colon && *colon != ':') colon++;
        if (!*colon) continue;
        *colon = 0;
        int pid = atoi(colon + 1);
        if (!pid) continue;
        if (count) emit(",\n");
        inspect_app(buf, pid, 1);
        count++;
    }
    emit("\n  ],\n");
    emitf("  \"targets_inspected\": %d,\n", count);
    emit("  \"status\": \"ok\"\n}\n");
    return write_document(argv[1]) ? 0 : 3;
}

#ifdef MVAX_INJECT
/*
 * Injected flavour.
 *
 * A worker thread is NOT an option here: on Mavericks a DYLD_INSERT_LIBRARIES
 * image whose constructor calls pthread_create deadlocks - the new thread and
 * the constructor both block, and the host hangs (proved with
 * tools/uiref/probe-insert.c, whose thread starts and then never finishes).
 * A SIGALRM handler needs no thread and no run loop, and the AXUIElement API
 * is documented as safe to call from any thread, so this captures the host
 * process's own accessibility tree while it is fully up.
 */
#define SIGALRM_N 14
extern int signal(int sig, void (*handler)(int));
extern unsigned int alarm(unsigned int seconds);

static void mvax_on_alarm(int sig) {
    (void)sig;
    char out[512];
    char target[512];
    snprintf(out, sizeof out, "/tmp/mvax-host-%d.json", (int)getpid());
    snprintf(target, sizeof target, "Host:%d", (int)getpid());
    char *args[4];
    args[0] = "mvax"; args[1] = out; args[2] = "12"; args[3] = target;
    run(4, args);
}

__attribute__((constructor)) static void mvax_inject_init(void) {
    write(2, "mvax-inject: loaded\n", 20);
    signal(SIGALRM_N, mvax_on_alarm);
    alarm(9);
    write(2, "mvax-inject: SIGALRM armed for 9s\n", 34);
}
#else
int main(int argc, char **argv) {
    const char *out = argc > 1 ? argv[1] : getenv("MVAX_OUT");
    if (!out) out = "/tmp/mvax.json";
    return run(argc, argv);
}
#endif