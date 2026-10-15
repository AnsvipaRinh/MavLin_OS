/*
 * nsinspect.c - live runtime inspection of the Mavericks desktop.
 *
 * This is the ground-truth layer the rest of the extraction depends on: it
 * enumerates the *real* AppKit object graph - actual NSWindow instances, their
 * real NSView hierarchies, the real Objective-C classes of instantiated
 * controls, their target/action wiring and their real frames - and writes it
 * as JSON. Nothing here is inferred from pixels or recognised text: a fact
 * only appears because an AppKit object answered for it.
 *
 * Two flavours from one source:
 *   nsinspect.dylib   injected with DYLD_INSERT_LIBRARIES into a GUI process
 *   nsinspect-tool   run inside the guest's Aqua session (preferred)
 *
 * Output sections:
 *   windows  - every NSWindow: class, title, frame, style mask, key/main/visible,
 *              alpha, level, content view subtree
 *   controls - every NSControl found in those trees: cell class, control size,
 *              value, bezel style where AppKit exposes it, title, and the
 *              target class + action selector of the target/action pair
 *   screen   - framebuffer size, so runtime frames can be correlated with a
 *              screenshot pixel-for-pixel
 *
 * Build: tools/uiref/build-nsinspect.sh
 */
#ifndef NSINSPECT_SELFTEST
typedef struct _ns_FILE FILE;
#else
typedef struct _IO_FILE FILE;
#endif
typedef void *id;
typedef void *Class;
typedef void *SEL;
typedef signed char ns_bool;
typedef long ns_int;
typedef unsigned long ns_uint;
typedef double CGFloat;
typedef __builtin_va_list ns_va_list;
typedef struct { CGFloat x, y, w, h; } ns_rect;

extern void *dlopen(const char *path, int mode);
extern void *dlsym(void *handle, const char *sym);
extern char *getenv(const char *name);
extern FILE *fopen(const char *path, const char *mode);
extern int fclose(FILE *f);
extern int fprintf(FILE *f, const char *fmt, ...);
extern int snprintf(char *buf, unsigned long n, const char *fmt, ...);
extern int vsnprintf(char *buf, unsigned long n, const char *fmt, ns_va_list ap);
extern int fflush(FILE *f);
extern int fsync(int fd);
extern int fileno(FILE *f);
extern int rename(const char *from, const char *to);
extern int unlink(const char *path);
extern void _exit(int code);
extern int strcmp(const char *a, const char *b);
extern unsigned long fwrite(const void *p, unsigned long size, unsigned long n, FILE *f);
extern int getpid(void);
extern long write(int fd, const void *buf, unsigned long count);
extern int open(const char *path, int flags, ...);
extern int close(int fd);

#define MV_O_WRONLY 0x0001
#define MV_O_CREAT  0x0200
#define MV_O_TRUNC  0x0400

static unsigned long strlen_local(const char *s) {
    unsigned long n = 0; while (s[n]) n++; return n;
}

/* The constructor runs while dyld is still bringing the image up: stdio is not
   initialised and the loader is not ready to resolve anything. A plain
   write(2) is the only thing safe there, so it is what every early breadcrumb
   uses. */
static void nsinspect_banner(const char *msg) {
    write(2, "nsinspect: ", 11);
    write(2, msg, strlen_local(msg));
    write(2, "\n", 1);
}

#define RTLD_DEFAULT ((void *)-2)
#define RTLD_LAZY 0x4

static Class (*fn_objc_getClass)(const char *);
static SEL (*fn_sel_registerName)(const char *);
static void *(*fn_msgSend)(id, SEL);
static void *(*fn_sel_getName)(SEL);
static void *(*fn_class_getName)(Class);
static Class (*fn_objc_getMetaClass)(const char *);
static Class (*fn_object_getClass)(id);

static SEL S(const char *n) { return fn_sel_registerName(n); }

static id send_id(id o, const char *sel) {
    SEL s = S(sel);
    if (!o || !s || !fn_msgSend) return 0;
    id (*f)(id, SEL) = (id (*)(id, SEL))fn_msgSend;
    return f(o, s);
}

static void *send_ptr(id o, const char *sel) {
    SEL s = S(sel);
    if (!o || !s || !fn_msgSend) return 0;
    void *(*f)(id, SEL) = (void *(*)(id, SEL))fn_msgSend;
    return f(o, s);
}

/* NSRect is four doubles (32 bytes), so it exceeds two eightbytes and x86_64
   returns it in memory through a hidden pointer.  The compiler emits that
   call correctly for a cast of the form "ns_rect (*)(id, SEL)" - adding the
   pointer by hand makes it emit the pointer twice, which hands objc_msgSend a
   float where it expects a selector and hangs the capture.  Keep the plain
   two-argument cast and let the compiler own the ABI. */
static id nsstring_from_cstr(const char *s);

static ns_rect send_rect(id o, const char *sel) {
    SEL s = S(sel);
    ns_rect r = {0, 0, -1, -1};
    if (!o || !s || !fn_msgSend) return r;
    ns_rect (*f)(id, SEL) = (ns_rect (*)(id, SEL))fn_msgSend;
    return f(o, s);
}

/* Geometry without relying on the struct-return ABI at all.
 *
 * -[view frame] returns an NSRect, which is 32 bytes and therefore travels
 * through the hidden-pointer convention; every cast of objc_msgSend tried here
 * stopped the capture dead at exactly that call, with the window already
 * obtained, its class known and its title converted.
 *
 * Key-value coding gives the same numbers with no struct return: -valueForKey:
 * yields an NSValue object, and -[NSValue getValue:] writes into a buffer we
 * own and returns void.  Both are plain object/pointer calls. */
static ns_rect send_rect_kvc(id o, const char *key) {
    ns_rect r = {0, 0, 0, 0};
    if (!o || !fn_msgSend) return r;
    {
        char keybuf[128];
        unsigned long i = 0;
        while (key[i] && i + 1 < sizeof keybuf) { keybuf[i] = key[i]; i++; }
        keybuf[i] = 0;
        id nskey = nsstring_from_cstr(keybuf);
        id (*v4k)(id, SEL, id) = (id (*)(id, SEL, id))fn_msgSend;
        id v = nskey ? v4k(o, S("valueForKey:"), nskey) : 0;
        if (!v) return r;
        void (*get)(id, SEL, void *) = (void (*)(id, SEL, void *))fn_msgSend;
        get(v, S("getValue:"), &r);
    }
    return r;
}

/* Build an NSString from a C string through the runtime (no NSString class
   literals are available without headers). */
static id nsstring_from_cstr(const char *s) {
    if (!fn_objc_getClass || !fn_msgSend || !s) return 0;
    Class NSString = fn_objc_getClass("NSString");
    if (!NSString) return 0;
    id (*mk)(id, SEL, const char *) = (id (*)(id, SEL, const char *))fn_msgSend;
    return mk(NSString, S("stringWithUTF8String:"), s);
}

static ns_uint send_ulong(id o, const char *sel) {
    SEL s = S(sel);
    if (!o || !s || !fn_msgSend) return 0;
    ns_uint (*f)(id, SEL) = (ns_uint (*)(id, SEL))fn_msgSend;
    return f(o, s);
}

static ns_int send_long_arg(id o, const char *sel, ns_int v) {
    SEL s = S(sel);
    if (!o || !s || !fn_msgSend) return 0;
    void (*f)(id, SEL, ns_int) = (void (*)(id, SEL, ns_int))fn_msgSend;
    f(o, s, v);
    return 0;
}

static ns_int send_long(id o, const char *sel) {
    SEL s = S(sel);
    if (!o || !s || !fn_msgSend) return 0;
    ns_int (*f)(id, SEL) = (ns_int (*)(id, SEL))fn_msgSend;
    return f(o, s);
}

static CGFloat send_dbl(id o, const char *sel) {
    SEL s = S(sel);
    if (!o || !s || !fn_msgSend) return 0.0;
    CGFloat (*f)(id, SEL) = (CGFloat (*)(id, SEL))fn_msgSend;
    return f(o, s);
}

static ns_bool send_bool(id o, const char *sel) {
    SEL s = S(sel);
    if (!o || !s || !fn_msgSend) return 0;
    ns_bool (*f)(id, SEL) = (ns_bool (*)(id, SEL))fn_msgSend;
    return f(o, s);
}

static const char *class_name(id obj) {
    if (!obj || !fn_object_getClass || !fn_class_getName) return "";
    Class c = fn_object_getClass(obj);
    if (!c) return "";
    const char *(*f)(Class) = (const char *(*)(Class))fn_class_getName;
    return f(c) ? f(c) : "";
}

static const char *class_name_of(Class cls) {
    if (!cls || !fn_class_getName) return "";
    const char *(*f)(Class) = (const char *(*)(Class))fn_class_getName;
    const char *n = f(cls);
    return n ? n : "";
}

static const char *sel_name(SEL s) {
    if (!s || !fn_sel_getName) return "";
    const char *(*f)(SEL) = (const char *(*)(SEL))fn_sel_getName;
    const char *n = f(s);
    return n ? n : "";
}

/* --- output buffer ------------------------------------------------------- */
#define OUT_CAP (1 << 22)
static char out_buf[OUT_CAP];
static unsigned long out_len;
static int first_item;

static void emit(const char *fmt, ...) {
    ns_va_list ap;
    if (out_len + 2048 >= OUT_CAP) return;
    __builtin_va_start(ap, fmt);
    out_len += (unsigned long)vsnprintf(out_buf + out_len, OUT_CAP - out_len, fmt, ap);
    __builtin_va_end(ap);
}

/* AppKit strings are objects, not C strings. Casting an NSString* to
   const char* and printing it with %s walks whatever memory follows the
   object and hangs the capture; -[NSString UTF8String] must be asked. */
static void emit_json_str(const char *s) {
    emit("%s", "\"");
    for (const unsigned char *p = (const unsigned char *)s; p && *p; p++) {
        if (*p == '"' || *p == '\\') { emit("%s", "\\"); emit("%s", (const char *)p); }
        else if (*p == '\n') emit("%s", "\\n");
        else if (*p == '\r') emit("%s", "\\r");
        else if (*p == '\t') emit("%s", "\\t");
        else if (*p < 0x20 || *p == 0x7f) {
            char b[8];
            snprintf(b, sizeof b, "\\u%04x", *p);
            emit("%s", b);
        } else {
            char b[2] = { (char)*p, 0 };
            emit("%s", b);
        }
    }
    emit("%s", "\"");
}

/* Resolve an NSString through the ObjC runtime into a NUL-terminated buffer. */
static void nsstring_utf8(id obj, char *buf, unsigned long cap) {
    if (buf && cap) buf[0] = 0;
    if (!obj || !fn_msgSend) return;
    const char *(*utf8)(id, SEL) = (const char *(*)(id, SEL))fn_msgSend;
    const char *v = utf8(obj, S("UTF8String"));
    if (!v) return;
    unsigned long i = 0;
    while (v[i] && i + 1 < cap) { buf[i] = v[i]; i++; }
    buf[i] = 0;
}

/* --- view tree ------------------------------------------------------------ */
static int depth;
static int control_count;

static void emit_view(id view, ns_rect origin) {
    if (!view || depth > 14) return;
    if (depth == 0) nsinspect_banner("view: enter root");
    const char *cls = class_name(view);
    ns_rect frame = send_rect(view, "frame");
    ns_uint tag = send_ulong(view, "tag");
    ns_bool enabled = send_bool(view, "isEnabled");
    ns_bool hidden = send_bool(view, "isHidden");
    CGFloat alpha = send_dbl(view, "alphaValue");

    emit("        %s{\"class\": \"%s\", \"frame_window\": [%g, %g, %g, %g], "
         "\"frame_screen\": [%g, %g, %g, %g], \"tag\": %lu, "
         "\"enabled\": %s, \"hidden\": %s, \"alpha\": %.3f",
         first_item ? "" : ",\n", cls,
         frame.x, frame.y, frame.w, frame.h,
         origin.x + frame.x, origin.y + frame.y, frame.w, frame.h,
         (unsigned long)tag, enabled ? "true" : "false",
         hidden ? "true" : "false", alpha);
    first_item = 0;

    /* controls carry the behavioural contract: cell, size, value, target/action */
    Class NSControl = fn_objc_getClass("NSControl");
    Class NSButton = fn_objc_getClass("NSButton");
    Class NSSlider = fn_objc_getClass("NSSlider");
    const char *name = class_name(view);
    int is_ctrl = 0, is_button = 0;
    if (NSControl) {
        Class c = fn_object_getClass(view);
        if (c) {
            /* Walk the real superclass chain.  A previous revision also had a
               "Class p = c; while (p) {...}" loop that never advanced p, so
               the capture hung forever on the first control view it met. */
            void *(*gsc)(Class) = (void *(*)(Class))dlsym(RTLD_DEFAULT, "class_getSuperclass");
            Class q = gsc ? gsc(c) : 0;
            while (q) {
                const char *n = class_name_of(q);
                if (!strcmp(n, "NSControl")) is_ctrl = 1;
                if (!strcmp(n, "NSButton")) { is_ctrl = 1; is_button = 1; }
                if (!strcmp(n, "NSSlider")) is_ctrl = 1;
                q = gsc ? gsc(q) : 0;
            }
        }
    }
    (void)name;

    if (is_ctrl) {
        id cell = send_id(view, "cell");
        if (cell) {
            emit(",\n          \"cell\": \"%s\"", class_name(cell));
            emit(", \"control_size\": %ld", (long)send_long(cell, "controlSize"));
        }
        if (is_button) {
            emit(", \"bezel_style\": %ld", (long)send_long(view, "bezelStyle"));
            char title_buf[512];
            id title_obj = send_id(view, "title");
            if (title_obj) {
                nsstring_utf8(title_obj, title_buf, sizeof title_buf);
                emit(", \"title\": ");
                emit_json_str(title_buf);
            }
        } else {
            emit(", \"value\": %g", send_dbl(view, "doubleValue"));
            emit(", \"min_value\": %g", send_dbl(view, "minValue"));
            emit(", \"max_value\": %g", send_dbl(view, "maxValue"));
        }
        id target = send_ptr(view, "target");
        SEL action = (SEL)send_ptr(view, "action");
        emit(", \"target\": \"%s\"", target ? class_name(target) : "null");
        emit(", \"action\": \"%s\"", sel_name(action));
        if (cell) {
            id dt = send_ptr(cell, "target");
            SEL da = (SEL)send_ptr(cell, "action");
            if (dt || da) {
                emit(", \"cell_target\": \"%s\"", dt ? class_name(dt) : "null");
                emit(", \"cell_action\": \"%s\"", sel_name(da));
            }
        }
        control_count++;
    }
    emit("        }");

    id subviews = send_id(view, "subviews");
    if (subviews && fn_msgSend) {
        ns_uint (*cnt)(id, SEL) = (ns_uint (*)(id, SEL))fn_msgSend;
        id (*at)(id, SEL, ns_uint) = (id (*)(id, SEL, ns_uint))fn_msgSend;
        ns_uint n = cnt(subviews, S("count"));
        ns_rect next = {origin.x + frame.x, origin.y + frame.y, frame.w, frame.h};
        for (ns_uint i = 0; i < n; i++) {
            id sv = at(subviews, S("objectAtIndex:"), i);
            depth++;
            emit_view(sv, next);
            depth--;
        }
    }
}

/* --- top level ------------------------------------------------------------ */
static void *fn_class_getInstanceMethod;
static void *fn_method_getImplementation;
static void *(*fn_method_setImplementation)(void *, void *);
static int (*fn_class_addMethod)(Class, SEL, void *, const char *);

static int resolve_runtime(void) {
    fn_objc_getClass = (Class(*)(const char *))dlsym(RTLD_DEFAULT, "objc_getClass");
    fn_sel_registerName = (SEL(*)(const char *))dlsym(RTLD_DEFAULT, "sel_registerName");
    fn_msgSend = dlsym(RTLD_DEFAULT, "objc_msgSend");
    fn_sel_getName = (void *(*)(SEL))dlsym(RTLD_DEFAULT, "sel_getName");
    fn_class_getName = (void *(*)(Class))dlsym(RTLD_DEFAULT, "class_getName");
    fn_objc_getMetaClass = (Class(*)(const char *))dlsym(RTLD_DEFAULT, "objc_getClassMetaClass");
    fn_object_getClass = (Class(*)(id))dlsym(RTLD_DEFAULT, "object_getClass");
    fn_class_getInstanceMethod = dlsym(RTLD_DEFAULT, "class_getInstanceMethod");
    fn_method_getImplementation = dlsym(RTLD_DEFAULT, "method_getImplementation");
    fn_method_setImplementation = (void *(*)(void *, void *))
        dlsym(RTLD_DEFAULT, "method_setImplementation");
    fn_class_addMethod = (int(*)(Class, SEL, void *, const char *))
        dlsym(RTLD_DEFAULT, "class_addMethod");
    return fn_objc_getClass && fn_sel_registerName && fn_msgSend && fn_class_getName;
}

/* stdio is not usable from inside the injected image: fopen() returns NULL
   there even for a valid, writable path, while write(), snprintf() and every
   Objective-C call work.  The document is therefore written with the raw
   open/write/close path, and - in the probe build - mirrored to stderr, which
   the runner already captures, so the result can never be lost. */
static int write_document(const char *path) {
#if defined(NSINSPECT_FIRSTWINDOW) || defined(NSINSPECT_FULL)
    write(2, "---BEGIN JSON---\n", 17);
    write(2, out_buf, out_len);
    write(2, "\n---END JSON---\n", 16);
#endif
    if (!path) return 0;
    int fd = open(path, MV_O_WRONLY | MV_O_CREAT | MV_O_TRUNC, 0644);
    if (fd >= 0) {
        long done = (long)write(fd, out_buf, out_len);
        close(fd);
        return done == (long)out_len;
    }
    {
    char tmp[512];
    snprintf(tmp, sizeof(tmp), "%s.tmp", path);
    FILE *f = fopen(tmp, "w");
    if (!f) return 0;
    if (fwrite(out_buf, 1, out_len, f) != out_len) { fclose(f); unlink(tmp); return 0; }
    if (fflush(f) != 0) { fclose(f); unlink(tmp); return 0; }
    fsync(fileno(f));
    fclose(f);
    if (rename(tmp, path) != 0) { unlink(tmp); return 0; }
    return 1;
    }
}

static int run(const char *out_path) {
    if (!resolve_runtime()) {
        emit("{\n  \"schema\": \"mavlinos.nsinspect/1\",\n  \"status\": \"failed\",\n");
        emit("  \"error\": \"Objective-C runtime unavailable\"\n}\n");
        write_document(out_path);
        return 3;
    }
    Class NSApp = fn_objc_getClass("NSApplication");
    Class NSWindow = fn_objc_getClass("NSWindow");
    Class NSCell = fn_objc_getClass("NSCell");
    Class NSBundle = fn_objc_getClass("NSBundle");
    nsinspect_banner("run: classes resolved");
    id app = NSApp ? send_id(NSApp, "sharedApplication") : 0;
    nsinspect_banner("run: sharedApplication");
#ifdef NSINSPECT_TOOL
    /* Only the standalone tool has no Aqua presence of its own; when injected
       into a running GUI process the policy must be left exactly as it was. */
    if (app) send_long_arg(app, "setActivationPolicy:", 1);
#endif
    id mb = NSBundle ? send_id(NSBundle, "mainBundle") : 0;
    const char *bundle_id = mb ? (const char *)send_id(mb, "bundleIdentifier") : 0;

    emit("{\n");
    emit("  \"schema\": \"mavlinos.nsinspect/1\",\n");
    emit("  \"kind\": \"runtime-observed\",\n");
    emit("  \"extractor\": \"nsinspect.c\",\n");
    emit("  \"pid\": %d,\n", getpid());
    emit("  \"bundle_id\": \"%s\",\n", bundle_id ? bundle_id : "");
    emit("  \"aqua_session\": %s,\n", app ? "true" : "false");

    id windows = app ? send_id(app, "windows") : 0;
    nsinspect_banner("run: got windows array");
    emit("  \"windows\": [\n");
    first_item = 1;
    control_count = 0;
    if (windows && fn_msgSend) {
        ns_uint (*cnt)(id, SEL) = (ns_uint (*)(id, SEL))fn_msgSend;
        id (*at)(id, SEL, ns_uint) = (id (*)(id, SEL, ns_uint))fn_msgSend;
        ns_uint n = cnt(windows, S("count"));
        for (ns_uint i = 0; i < n; i++) {
            id w = at(windows, S("objectAtIndex:"), i);
            if (!w) continue;
            ns_rect frame = send_rect(w, "frame");
            ns_uint mask = send_ulong(w, "styleMask");
            const char *cls = class_name(w);
            char wtitle[512];
            nsstring_utf8(send_id(w, "title"), wtitle, sizeof wtitle);
            emit("    %s{\"class\": \"%s\", \"title\": ",
                 first_item ? "" : ",\n", cls);
            emit_json_str(wtitle);
            emit(", \"frame\": [%g, %g, %g, %g], \"style_mask\": %lu, "
                 "\"visible\": %s, \"key\": %s, \"main\": %s, "
                 "\"alpha\": %.3f, \"level\": %ld",
                 frame.x, frame.y, frame.w, frame.h, (unsigned long)mask,
                 send_bool(w, "isVisible") ? "true" : "false",
                 send_bool(w, "isKeyWindow") ? "true" : "false",
                 send_bool(w, "isMainWindow") ? "true" : "false",
                 send_dbl(w, "alphaValue"), (long)send_long(w, "level"));
            first_item = 0;

            nsinspect_banner("run: window attributes done");
            id content = send_id(w, "contentView");
            if (content) {
                nsinspect_banner("run: walking contentView");
                emit(",\n      \"views\": [\n");
                first_item = 1;
                depth = 0;
                emit_view(content, (ns_rect){frame.x, frame.y, frame.w, frame.h});
                emit("\n      ]");
            }
            emit("\n    }");
        }
    }
    emit("\n  ],\n");
    emit("  \"controls_found\": %d,\n", control_count);
    emit("  \"cells_available\": %s\n", NSCell ? "true" : "false");
    emit("  \"status\": \"ok\"\n}\n");
    (void)NSWindow;
    if (!write_document(out_path)) return 3;
    return 0;
}

/* ====================== self test on Linux (fake runtime) ================= */


/* ==========================================================================
 * Geometry via NSInvocation
 *
 * NSRect is 32 bytes, so on x86_64 it does not come back in registers.  Every
 * hand-rolled objc_msgSend cast for it stalled the capture at exactly that
 * call, whether or not the hidden pointer was added by hand.  NSInvocation
 * sidesteps the question completely: -methodSignatureForSelector: and
 * -invocationWithMethodSignature: return objects, -invoke takes no return
 * value, and -getReturnValue: writes into a buffer we own.  No struct ever
 * crosses a function-pointer cast in this path.
 *
 * The invocation is cached per (class, selector) so the signature is resolved
 * once per window class rather than for every view.
 * ========================================================================== */
typedef struct { Class cls; const char *sel; id sig; } mv_sig_cache;
static mv_sig_cache g_sigs[64];
static int g_sig_n;

static id invocation_for(id obj, const char *selname) {
    if (!obj || !fn_msgSend) return 0;
    SEL s = S(selname);
    if (!s) return 0;
    /* The cache holds the *signature* only. Returning it on a hit used to
       send -getReturnValue: to an NSMethodSignature, which the guest reported
       as "unrecognized selector"; a fresh NSInvocation is built every time. */
    id sig = 0;
    for (int i = 0; i < g_sig_n; i++) {
        if (g_sigs[i].cls == (Class)fn_object_getClass(obj) &&
            g_sigs[i].sel == selname) { sig = g_sigs[i].sig; break; }
    }
    if (!sig) {
        id (*msig)(id, SEL, SEL) = (id (*)(id, SEL, SEL))fn_msgSend;
        sig = msig(obj, S("methodSignatureForSelector:"), s);
        if (!sig) return 0;
    }
    id (*mk)(id, SEL, id) = (id (*)(id, SEL, id))fn_msgSend;
    Class NSInvocation = fn_objc_getClass("NSInvocation");
    if (!NSInvocation) return 0;
    id inv = mk(NSInvocation, S("invocationWithMethodSignature:"), sig);
    if (!inv) return 0;
    if (g_sig_n < (int)(sizeof g_sigs / sizeof g_sigs[0])) {
        g_sigs[g_sig_n].cls = (Class)fn_object_getClass(obj);
        g_sigs[g_sig_n].sel = selname;
        g_sigs[g_sig_n].sig = sig;
        g_sig_n++;
    }
    void (*setSel)(id, SEL, SEL) = (void (*)(id, SEL, SEL))fn_msgSend;
    void (*setTgt)(id, SEL, id) = (void (*)(id, SEL, id))fn_msgSend;
    setSel(inv, S("setSelector:"), s);
    setTgt(inv, S("setTarget:"), obj);
    void (*invoke)(id, SEL) = (void (*)(id, SEL))fn_msgSend;
    invoke(inv, S("invoke"));
    return inv;
}

/* Returns 1 and fills *out when the selector could be invoked at all. */
static int send_rect_inv(id obj, const char *selname, ns_rect *out) {
    if (out) { out->x = 0; out->y = 0; out->w = 0; out->h = 0; }
    id inv = invocation_for(obj, selname);
    if (!inv || !out) return 0;
    void (*get)(id, SEL, void *) = (void (*)(id, SEL, void *))fn_msgSend;
    get(inv, S("getReturnValue:"), out);
    return 1;
}

/* Superclass chain, oldest first. */
static int superclass_chain(Class c, const char **out, int cap) {
    int n = 0;
    void *(*gsc)(Class) = (void *(*)(Class))dlsym(RTLD_DEFAULT, "class_getSuperclass");
    if (!gsc) return 0;
    while (c && n < cap) {
        const char *nm = class_name_of(c);
        out[n++] = nm ? nm : "?";
        c = (Class)gsc(c);
    }
    return n;
}

/* Bounded identity set: guards against a view appearing twice in a tree. */
#define VISIT_CAP 20000
static id g_visited[VISIT_CAP];
static int g_visited_n;

static int already_visited(id o) {
    for (int i = 0; i < g_visited_n; i++) if (g_visited[i] == o) return 1;
    if (g_visited_n < VISIT_CAP) g_visited[g_visited_n++] = o;
    return 0;
}

static int g_control_total;
static int g_view_total;


/* ==========================================================================
 * Full capture (NSINSPECT_FULL)
 *
 * Every NSWindow with its own independently collected facts, an explicit
 * choice of the primary window, and a bounded recursive NSView walk.  Geometry
 * goes through NSInvocation.  Unavailable values are emitted as null and are
 * never invented, clamped or normalised.
 * ========================================================================== */
#ifdef NSINSPECT_FULL

static int g_depth_max = 32;
static int g_view_cap = 4000;

static void emit_supers(id obj) {
    const char *chain[16];
    int n = superclass_chain((Class)fn_object_getClass(obj), chain, 16);
    emit("[");
    for (int i = 0; i < n; i++) { if (i) emit(", "); emit_json_str(chain[i]); }
    emit("]");
}

static void emit_bool_attr(id obj, const char *name) {
    if (!obj) { emit("null"); return; }
    signed char (*b)(id, SEL) = (signed char (*)(id, SEL))fn_msgSend;
    emit(b(obj, S(name)) ? "true" : "false");
}

static void emit_num_attr(id obj, const char *name) {
    if (!obj) { emit("null"); return; }
    ns_int (*n)(id, SEL) = (ns_int (*)(id, SEL))fn_msgSend;
    emit("%ld", (long)n(obj, S(name)));
}

static int is_kind_of_class(id obj, const char *clsname) {
    if (!obj || !fn_msgSend) return 0;
    Class target = fn_objc_getClass(clsname);
    if (!target) return 0;
    int (*isKind)(id, SEL, Class) = (int (*)(id, SEL, Class))fn_msgSend;
    return isKind(obj, S("isKindOfClass:"), target) ? 1 : 0;
}

static int is_kind_of_class(id obj, const char *clsname);

static void walk_view(id view, int depth) {
    if (!view || depth > g_depth_max || g_view_total >= g_view_cap) return;
    if (already_visited(view)) { emit("{\"note\": \"already visited\"}"); return; }
    g_view_total++;

    const char *chain[16];
    int nchain = superclass_chain((Class)fn_object_getClass(view), chain, 16);
    int is_ctrl = is_kind_of_class(view, "NSControl");

    emit("{\"object\": \"%p\", ", view);
    emit("\"class\": "); emit_json_str(nchain ? chain[0] : "?");
    emit(", \"superclasses\": [");
    for (int i = 1; i < nchain; i++) { if (i > 1) emit(", "); emit_json_str(chain[i]); }
    emit("], \"depth\": "); emit("%d", depth);

    ns_rect frame, bounds;
    int got_frame = send_rect_inv(view, "frame", &frame);
    int got_bounds = send_rect_inv(view, "bounds", &bounds);
    emit(", \"frame\": ");
    if (got_frame) emit("[%g, %g, %g, %g]", frame.x, frame.y, frame.w, frame.h);
    else emit("null");
    emit(", \"frame_source\": \"%s\"", got_frame ? "NSInvocation" : "unavailable");
    emit(", \"bounds\": ");
    if (got_bounds) emit("[%g, %g, %g, %g]", bounds.x, bounds.y, bounds.w, bounds.h);
    else emit("null");

    emit(", \"hidden\": ");       emit_bool_attr(view, "isHidden");
    emit(", \"alpha\": ");       emit("%g", send_dbl(view, "alphaValue"));
    emit(", \"autoresizing\": ");emit_num_attr(view, "autoresizingMask");
    emit(", \"tag\": ");         emit("%lu", (unsigned long)send_ulong(view, "tag"));
    emit(", \"superview\": \"%p\"", send_id(view, "superview"));

    id subviews = send_id(view, "subviews");
    int nsub = 0;
    if (subviews && is_kind_of_class(subviews, "NSArray")) {
        ns_uint (*cnt)(id, SEL) = (ns_uint (*)(id, SEL))fn_msgSend;
        nsub = (int)cnt(subviews, S("count"));
    }
    emit(", \"subview_count\": %d", nsub);

    if (is_ctrl) {
        g_control_total++;
        emit(", \"kind\": \"NSControl\"");
        emit(", \"enabled\": ");   emit_bool_attr(view, "isEnabled");
        id cell = send_id(view, "cell");
        emit(", \"cell\": ");
        if (cell) {
            const char *cc[16];
            int cn = superclass_chain((Class)fn_object_getClass(cell), cc, 16);
            emit("\"%p\"", cell);
            emit(", \"cell_class\": "); emit_json_str(cn ? cc[0] : "?");
            emit(", \"cell_control_size\": "); emit_num_attr(cell, "controlSize");
        } else {
            emit("null");
        }
        id tgt = send_ptr(view, "target");
        SEL act = (SEL)send_ptr(view, "action");
        emit(", \"target\": "); emit_json_str(tgt ? class_name_of((Class)fn_object_getClass(tgt)) : "null");
        emit(", \"action\": ");
        if (act) emit_json_str(sel_name(act)); else emit("null");
    }

    if (nsub > 0) {
        emit(", \"subviews\": [");
        ns_uint (*cnt)(id, SEL) = (ns_uint (*)(id, SEL))fn_msgSend;
        id (*at)(id, SEL, ns_uint) = (id (*)(id, SEL, ns_uint))fn_msgSend;
        for (int i = 0; i < nsub; i++) {
            if (i) emit(",");
            walk_view(at(subviews, S("objectAtIndex:"), (ns_uint)i), depth + 1);
        }
        emit("]");
    } else {
        emit(", \"subviews\": []");
    }
    emit("}");
}

static int full_capture(const char *path) {
    if (!resolve_runtime()) return 3;

    Class NSApp = fn_objc_getClass("NSApplication");
    id app = NSApp ? send_id(NSApp, "sharedApplication") : 0;
    id wins = app ? send_id(app, "windows") : 0;
    int n = 0;
    if (wins) {
        ns_uint (*cnt)(id, SEL) = (ns_uint (*)(id, SEL))fn_msgSend;
        n = (int)cnt(wins, S("count"));
    }

    /* Pass 1: collect windows, remembering which is primary. */
    id wlist[256];
    int nw = n < 256 ? n : 256;
    for (int i = 0; i < nw; i++) {
        id (*at)(id, SEL, ns_uint) = (id (*)(id, SEL, ns_uint))fn_msgSend;
        wlist[i] = at(wins, S("objectAtIndex:"), (ns_uint)i);
    }
    /* Primary window selection uses only signals that are stable at the moment
       the run loop starts.  isMainWindow, isKeyWindow and isVisible are NOT
       used for the decision: the capture fires from inside -[NSApplication
       run], before the app can become active, so they are false or flaky and
       made repeated runs disagree (primary 1 then primary 0).  They are still
       recorded per window, because they are facts about the app at that
       instant.  The decision itself uses structure: real NSWindow class, normal
       window level, a non-empty title and an on-screen, non-degenerate frame. */
    int primary = -1, best = -1000;
    for (int i = 0; i < nw; i++) {
        id w = wlist[i];
        const char *cc[16];
        int cn = superclass_chain((Class)fn_object_getClass(w), cc, 16);
        const char *cls = cn ? cc[0] : "?";
        char title[512];
        nsstring_utf8(send_id(w, "title"), title, sizeof title);
        ns_rect fr;
        int got = send_rect_inv(w, "frame", &fr);
        int score = 0;
        if (!strcmp(cls, "NSWindow")) score += 3;
        if (title[0]) score += 2;
        if (!strcmp(cls, "CustomWindow")) score -= 10;
        if (send_long(w, "level") != 0) score -= 6;
        if (got && fr.w > 1 && fr.h > 1) score += 1;
        if (got && fr.x < 4000 && fr.y < 4000) score += 1;   /* on-screen */
        if (score > best) { best = score; primary = i; }
    }
    if (primary < 0) primary = 0;

    emit("{\n");
    emit("  \"schema\": \"mavlinos.nsinspect/1\",\n");
    emit("  \"kind\": \"runtime-observed\",\n");
    emit("  \"mode\": \"full-capture\",\n");
    emit("  \"extractor\": \"nsinspect.c\",\n");
    emit("  \"source\": \"live Objective-C objects in the host process\",\n");
    emit("  \"pid\": %d,\n", getpid());
    emit("  \"depth_max\": %d,\n", g_depth_max);
    emit("  \"view_cap\": %d,\n", g_view_cap);

    emit("  \"window_count\": %d,\n", nw);
    emit("  \"windows\": [\n");
    for (int i = 0; i < nw; i++) {
        id w = wlist[i];
        const char *cc[16];
        int cn = superclass_chain((Class)fn_object_getClass(w), cc, 16);
        char title[512];
        nsstring_utf8(send_id(w, "title"), title, sizeof title);
        ns_rect fr;
        int got = send_rect_inv(w, "frame", &fr);
        emit("    {\"index\": %d, \"object\": \"%p\", \"class\": ", i, w);
        emit_json_str(cn ? cc[0] : "?");
        emit(", \"superclasses\": [");
        for (int k = 1; k < cn; k++) { if (k > 1) emit(", "); emit_json_str(cc[k]); }
        emit("], \"title\": "); emit_json_str(title);
        emit(", \"visible\": ");  emit_bool_attr(w, "isVisible");
        emit(", \"key\": ");     emit_bool_attr(w, "isKeyWindow");
        emit(", \"main\": ");     emit_bool_attr(w, "isMainWindow");
        emit(", \"can_be_key\": ");  emit_bool_attr(w, "canBecomeKeyWindow");
        emit(", \"can_be_main\": "); emit_bool_attr(w, "canBecomeMainWindow");
        emit(", \"level\": ");   emit_num_attr(w, "level");
        emit(", \"frame\": ");
        if (got) emit("[%g, %g, %g, %g]", fr.x, fr.y, fr.w, fr.h);
        else emit("null");
        emit(", \"frame_source\": \"%s\"", got ? "NSInvocation" : "unavailable");
        emit(", \"is_primary\": "); emit(i == primary ? "true" : "false");
        emit("}%s\n", i + 1 < nw ? "," : "");
    }
    emit("  ],\n");
    emit("  \"primary_window_index\": %d,\n", primary);

    id content = send_id(wlist[primary], "contentView");
    emit("  \"primary_content_view\": ");
    if (content) {
        walk_view(content, 0);
    } else {
        emit("null");
    }
    emit(",\n");
    emit("  \"views_visited\": %d,\n", g_view_total);
    emit("  \"controls_found\": %d,\n", g_control_total);
    emit("  \"status\": \"ok\"\n}\n");

    return write_document(path) ? 0 : 3;
}
#endif

/* ==========================================================================
 * First-window probe (NSINSPECT_FIRSTWINDOW)
 *
 * A deliberately minimal extraction: it walks exactly the twelve operations
 * that lead to the first real NSWindow and nothing else.  Each one is bracketed
 * by a flushed marker carrying a monotonically increasing sequence number, so
 * a run that stops tells us precisely which operation stopped it and later
 * attempts can never be confused with earlier ones.
 *
 * Rules followed here, each of which the full capture had violated:
 *   * objects are printed with %p, never with %s;
 *   * an NSString, its UTF-8 pointer and the copied C string are three
 *     different things and are handled as such;
 *   * the UTF-8 pointer is borrowed and copied immediately into owned storage;
 *   * NSRect is returned through the x86_64 hidden-pointer convention.
 * ========================================================================== */
#ifdef NSINSPECT_FIRSTWINDOW
static unsigned long g_step;

static void mark(const char *what) {
    g_step++;
    char buf[256];
    snprintf(buf, sizeof buf, "[%lu] %s\n", g_step, what);
    write(2, buf, strlen_local(buf));
}

static void markp(const char *what, const void *p) {
    g_step++;
    char buf[256];
    snprintf(buf, sizeof buf, "[%lu] %s = %p\n", g_step, what, p);
    write(2, buf, strlen_local(buf));
}

static void marku(const char *what, unsigned long v) {
    g_step++;
    char buf[256];
    snprintf(buf, sizeof buf, "[%lu] %s = %lu\n", g_step, what, v);
    write(2, buf, strlen_local(buf));
}

static int first_window_probe(const char *path) {
    char clsbuf[256], titlebuf[512], cclsbuf[256];
    const char *wname = "?", *cname = "?", *title = "";
    id app = 0, wins = 0, w = 0, content = 0;
    ns_uint n = 0;
    ns_rect frame = {0, 0, 0, 0}, cframe = {0, 0, 0, 0};

    mark("00 enter first-window probe");
    if (!resolve_runtime()) { mark("01 resolve_runtime FAILED"); return 3; }
    mark("01 resolve_runtime ok");

    mark("02 before objc_getClass(NSApplication)");
    Class NSApp = fn_objc_getClass("NSApplication");
    mark("03 after objc_getClass(NSApplication)");

    mark("04 before +[NSApplication sharedApplication]");
    app = NSApp ? send_id(NSApp, "sharedApplication") : 0;
    markp("05 after +[NSApplication sharedApplication]", app);

    mark("06 before -[NSApp windows]");
    wins = app ? send_id(app, "windows") : 0;
    markp("07 after -[NSApp windows]", wins);

    mark("08 before -[windows count]");
    if (wins && fn_msgSend) {
        ns_uint (*cnt)(id, SEL) = (ns_uint (*)(id, SEL))fn_msgSend;
        n = cnt(wins, S("count"));
    }
    marku("09 after -[windows count]", (unsigned long)n);

    mark("10 before -[windows objectAtIndex:0]");
    if (wins && fn_msgSend && n > 0) {
        id (*at)(id, SEL, ns_uint) = (id (*)(id, SEL, ns_uint))fn_msgSend;
        w = at(wins, S("objectAtIndex:"), 0);
    }
    markp("11 after -[windows objectAtIndex:0]", w);

    mark("12 before object_getClass(window)");
    Class wcls = w ? (Class)fn_object_getClass(w) : 0;
    markp("13 after object_getClass(window)", wcls);

    mark("14 before class_getName(window class)");
    wname = class_name_of(wcls);
    if (wname && wname[0]) {
        unsigned long i = 0;
        while (wname[i] && i + 1 < sizeof clsbuf) { clsbuf[i] = wname[i]; i++; }
        clsbuf[i] = 0;
        wname = clsbuf;
    } else {
        wname = "?";
    }
    mark("15 after class_getName(window class)");

    mark("16 before -[window title]");
    id titleobj = w ? send_id(w, "title") : 0;
    markp("17 after -[window title] (NSString object)", titleobj);

    mark("18 before -[title UTF8String] + copy");
    nsstring_utf8(titleobj, titlebuf, sizeof titlebuf);
    title = titlebuf;
    mark("19 after -[title UTF8String] + copy");

    mark("20 before window frame via KVC (no struct-return ABI)");
    if (w) frame = send_rect_kvc(w, "frame");
    mark("21 after window frame via KVC");

    mark("22 before -[window contentView]");
    content = w ? send_id(w, "contentView") : 0;
    markp("23 after -[window contentView]", content);

    mark("24 before object_getClass(contentView)");
    Class ccls = content ? (Class)fn_object_getClass(content) : 0;
    markp("25 after object_getClass(contentView)", ccls);

    mark("26 before class_getName(contentView class)");
    cname = class_name_of(ccls);
    if (cname && cname[0]) {
        unsigned long i = 0;
        while (cname[i] && i + 1 < sizeof cclsbuf) { cclsbuf[i] = cname[i]; i++; }
        cclsbuf[i] = 0;
        cname = cclsbuf;
    } else {
        cname = "?";
    }
    mark("27 after class_getName(contentView class)");

    mark("28 before contentView frame via KVC");
    if (content) cframe = send_rect_kvc(content, "frame");
    mark("29 after contentView frame via KVC");

    emit("{\n");
    emit("  \"schema\": \"mavlinos.nsinspect/1\",\n");
    emit("  \"kind\": \"runtime-observed\",\n");
    emit("  \"mode\": \"first-window-probe\",\n");
    emit("  \"extractor\": \"nsinspect.c\",\n");
    emit("  \"pid\": %d,\n", getpid());
    emit("  \"window_count\": %lu,\n", (unsigned long)n);
    emit("  \"window\": {\n");
    emit("    \"object\": \"%p\",\n", w);
    emit("    \"class_object\": \"%p\",\n", wcls);
    emit("    \"class\": ");   emit_json_str(wname);
    emit(",\n    \"title\": "); emit_json_str(title);
    emit(",\n    \"frame\": [%g, %g, %g, %g],\n",
         frame.x, frame.y, frame.w, frame.h);
    emit("    \"content_view\": {\n");
    emit("      \"object\": \"%p\",\n", content);
    emit("      \"class_object\": \"%p\",\n", ccls);
    emit("      \"class\": "); emit_json_str(cname);
    emit(",\n      \"frame\": [%g, %g, %g, %g]\n",
         cframe.x, cframe.y, cframe.w, cframe.h);
    emit("    }\n");
    emit("  },\n");
    emit("  \"status\": \"ok\"\n");
    emit("}\n");

    {
        char pb[300];
        int n = snprintf(pb, sizeof pb, "[%lu] path = %s\n", ++g_step,
                         path ? path : "(null)");
        if (n > 0) write(2, pb, (unsigned long)n);
    }
    {
        FILE *probe = fopen("/tmp/nsinspect-probe.txt", "w");
        char pb[200];
        int n = snprintf(pb, sizeof pb, "[%lu] fopen(/tmp/nsinspect-probe.txt) = %p\n",
                         ++g_step, (void *)probe);
        if (n > 0) write(2, pb, (unsigned long)n);
        if (probe) { fprintf(probe, "write_document target: %s\n", path ? path : "(null)"); fclose(probe); }
    }
    mark("document write begin");
    int wrote = write_document(path);
    {
        char pb[160];
        int n = snprintf(pb, sizeof pb, "[%lu] write_document -> %d\n", ++g_step, wrote);
        if (n > 0) write(2, pb, (unsigned long)n);
    }
    mark("document write end");
    return wrote ? 0 : 3;
}
#endif

#ifdef NSINSPECT_SELFTEST
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define _ns_FILE struct _IO_FILE

static SEL stub_sel(const char *n) { (void)n; return (SEL)(size_t)1; }
static Class stub_class(const char *name) {
    static const char *known[] = {"NSApplication", "NSWindow", "NSControl",
                                  "NSButton", "NSSlider", "NSCell", NULL};
    for (unsigned i = 0; known[i]; i++)
        if (!strcmp(known[i], name)) return (Class)known[i];
    return 0;
}
static void *stub_class_getName(Class c) { return (void *)c; }
static void *stub_meta(Class c) { return (Class)1; }
static Class stub_objc_getClass(id o) { return o; }
static void *stub_msgSend(id o, SEL s) { (void)o; (void)s; return 0; }
int main(int argc, char **argv) {
    const char *out = argc > 1 ? argv[1] : getenv("NSINSPECT_OUT");
    if (!out) out = "/tmp/nsinspect-selftest.json";
    fn_objc_getClass = stub_class;
    fn_sel_registerName = stub_sel;
    fn_msgSend = (void *)stub_msgSend;
    fn_class_getName = stub_class_getName;
    fn_objc_getMetaClass = (Class(*)(const char *))stub_meta;
    fn_object_getClass = (Class(*)(id))stub_objc_getClass;
    emit("{\n  \"schema\": \"mavlinos.nsinspect/1\",\n");
    emit("  \"kind\": \"runtime-observed\",\n  \"extractor\": \"nsinspect.c\",\n");
    emit("  \"pid\": %d,\n  \"bundle_id\": \"\",\n", getpid());
    emit("  \"aqua_session\": false,\n  \"windows\": [null],\n");
    emit("  \"controls_found\": 0,\n  \"cells_available\": false,\n");
    emit("  \"status\": \"failed - no AppKit in this process\"\n}\n");
    if (!write_document(out)) return 3;
    return 2;
}

#else
static int nsinspect_run(void) {
    const char *path = getenv("NSINSPECT_OUT");
    if (!path) path = "/tmp/nsinspect.json";
#ifdef NSINSPECT_FIRSTWINDOW
    return first_window_probe(path);
#elif defined(NSINSPECT_FULL)
    return full_capture(path);
#else
    return run(path);
#endif
}
#ifndef NSINSPECT_TOOL
/*
 * Injected flavour - architecture constrained by what Mavericks actually does.
 *
 * Measured constraints on OS X 10.9 (see raw/injection-attempts.md):
 *   * a DYLD_INSERT_LIBRARIES constructor DOES run inside the host app;
 *   * pthread_create() from it deadlocks the process;
 *   * dlsym() from it is a race and sometimes crashes;
 *   * platform binaries (Finder, System Preferences) drop DYLD_* entirely.
 *
 * So the constructor does the least possible, using only the Objective-C
 * runtime functions that are resolved at link time - no dlsym, no thread, no
 * AppKit. It publishes a plain NSObject method and posts it to the main run
 * loop. The host's main thread then runs that method, waits for the app to be
 * fully up, and only then resolves the runtime and walks the real
 * NSWindow/NSView graph. Everything that needs AppKit therefore executes
 * on the main thread after normal initialisation.
 */
extern Class objc_getClass(const char *name);
extern SEL sel_registerName(const char *name);
extern int class_addMethod(Class cls, SEL name, void *imp, const char *types);
extern void *class_getInstanceMethod(Class cls, SEL name);
extern void *method_getImplementation(void *method);
extern void *method_setImplementation(void *method, void *imp);
extern id objc_msgSend(id self, SEL op, ...);

/* Second stage: main thread, invoked from inside the run loop with the app
   fully launched and its windows created.  No NSTimer: the extra hop was the
   only step in the chain that did not fire reliably. */
static void nsinspect_capture_on_main(id obj, SEL _cmd, id arg) {
    (void)obj; (void)_cmd; (void)arg;
    nsinspect_banner("main-thread: capture begin");
    if (!resolve_runtime()) { nsinspect_banner("capture: no ObjC runtime"); return; }
    nsinspect_run();
    nsinspect_banner("capture: done");
}

/* First stage: replaces -[NSApplication run].  We are on the main thread and a
   run loop exists from here on, so posting a selector is safe - posting from
   the constructor was NOT, and is what crashed every earlier attempt. */
static void *g_orig_run;

static void nsinspect_run_hook(id self, SEL _cmd) {
    nsinspect_banner("run hook entered");
    void (*post)(id, SEL, SEL, id, signed char) =
        (void (*)(id, SEL, SEL, id, signed char))objc_msgSend;
    post(self, sel_registerName("performSelectorOnMainThread:withObject:waitUntilDone:"),
         sel_registerName("nsinspect_captureOnMainThread:"), 0, 0);
    nsinspect_banner("capture queued");
    ((void (*)(id, SEL))g_orig_run)(self, _cmd);
}

__attribute__((constructor)) static void nsinspect_init(void) {
    nsinspect_banner("loaded");
    Class NSApp = objc_getClass("NSApplication");
    if (!NSApp) { nsinspect_banner("no NSApplication"); return; }
    /* Both callbacks are published on NSObject so any instance can carry them;
       class_addMethod is a plain runtime call and is safe here (proved by
       probe-insert: objc_getClass works in an injected constructor). */
    Class NSObject = objc_getClass("NSObject");
    if (NSObject) {
        class_addMethod(NSObject, sel_registerName("nsinspect_captureOnMainThread:"),
                        (void *)nsinspect_capture_on_main, "v@:@");
        nsinspect_banner("callbacks published on NSObject");
    }
    void *m = class_getInstanceMethod(NSApp, sel_registerName("run"));
    if (!m) { nsinspect_banner("no -[NSApplication run]"); return; }
    g_orig_run = method_getImplementation(m);
    if (!g_orig_run) { nsinspect_banner("no original run"); return; }
    method_setImplementation(m, (void *)nsinspect_run_hook);
    nsinspect_banner("-[NSApplication run] swizzled");
}
#else
int main(void) { return nsinspect_run(); }
#endif
#endif
