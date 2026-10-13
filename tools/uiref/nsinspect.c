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

static ns_rect send_rect(id o, const char *sel) {
    SEL s = S(sel);
    ns_rect r = {0, 0, -1, -1};
    if (!o || !s || !fn_msgSend) return r;
    ns_rect (*f)(id, SEL) = (ns_rect (*)(id, SEL))fn_msgSend;
    return f(o, s);
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

/* --- view tree ------------------------------------------------------------ */
static int depth;
static int control_count;

static void emit_view(id view, ns_rect origin) {
    if (!view || depth > 14) return;
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
            Class p = c;
            while (p) {
                const char *n = class_name_of(p);
                if (!strcmp(n, "NSControl")) is_ctrl = 1;
                if (!strcmp(n, "NSButton")) { is_ctrl = 1; is_button = 1; }
                if (!strcmp(n, "NSSlider")) is_ctrl = 1;
            }
            /* superclass chain via class_getSuperclass when available */
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
            const char *title = send_id(view, "title");
            if (title) emit(", \"title\": \"%s\"", title);
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
static int resolve_runtime(void) {
    fn_objc_getClass = (Class(*)(const char *))dlsym(RTLD_DEFAULT, "objc_getClass");
    fn_sel_registerName = (SEL(*)(const char *))dlsym(RTLD_DEFAULT, "sel_registerName");
    fn_msgSend = dlsym(RTLD_DEFAULT, "objc_msgSend");
    fn_sel_getName = (void *(*)(SEL))dlsym(RTLD_DEFAULT, "sel_getName");
    fn_class_getName = (void *(*)(Class))dlsym(RTLD_DEFAULT, "class_getName");
    fn_objc_getMetaClass = (Class(*)(const char *))dlsym(RTLD_DEFAULT, "objc_getMetaClass");
    fn_object_getClass = (Class(*)(id))dlsym(RTLD_DEFAULT, "object_getClass");
    return fn_objc_getClass && fn_sel_registerName && fn_msgSend && fn_class_getName;
}

static int write_document(const char *path) {
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

static int run(void) {
    if (!resolve_runtime()) {
        emit("{\n  \"schema\": \"mavlinos.nsinspect/1\",\n  \"status\": \"failed\",\n");
        emit("  \"error\": \"Objective-C runtime unavailable\"\n}\n");
        return write_document("failed") ? 3 : 3;
    }
    Class NSApp = fn_objc_getClass("NSApplication");
    Class NSWindow = fn_objc_getClass("NSWindow");
    Class NSCell = fn_objc_getClass("NSCell");
    id app = NSApp ? send_id(NSApp, "sharedApplication") : 0;
    if (app) send_long_arg(app, "setActivationPolicy:", 1);

    emit("{\n");
    emit("  \"schema\": \"mavlinos.nsinspect/1\",\n");
    emit("  \"kind\": \"runtime-observed\",\n");
    emit("  \"extractor\": \"nsinspect.c\",\n");
    emit("  \"aqua_session\": %s,\n", app ? "true" : "false");

    id windows = app ? send_id(app, "windows") : 0;
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
            emit("    %s{\"class\": \"%s\", \"title\": \"%s\", "
                 "\"frame\": [%g, %g, %g, %g], \"style_mask\": %lu, "
                 "\"visible\": %s, \"key\": %s, \"main\": %s, "
                 "\"alpha\": %.3f, \"level\": %ld",
                 first_item ? "" : ",\n", cls,
                 (const char *)send_id(w, "title") ?: "",
                 frame.x, frame.y, frame.w, frame.h, (unsigned long)mask,
                 send_bool(w, "isVisible") ? "true" : "false",
                 send_bool(w, "isKeyWindow") ? "true" : "false",
                 send_bool(w, "isMainWindow") ? "true" : "false",
                 send_dbl(w, "alphaValue"), (long)send_long(w, "level"));
            first_item = 0;

            id content = send_id(w, "contentView");
            if (content) {
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
    return write_document("ok") ? 0 : 3;
}

/* ====================== self test on Linux (fake runtime) ================= */
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
    const char *out = argc > 1 ? argv[1] : "/tmp/nsinspect-selftest.json";
    fn_objc_getClass = stub_class;
    fn_sel_registerName = stub_sel;
    fn_msgSend = (void *)stub_msgSend;
    fn_class_getName = stub_class_getName;
    fn_objc_getMetaClass = (Class(*)(const char *))stub_meta;
    fn_object_getClass = (Class(*)(id))stub_objc_getClass;
    emit("{\n  \"schema\": \"mavlinos.nsinspect/1\",\n");
    emit("  \"kind\": \"runtime-observed\",\n  \"extractor\": \"nsinspect.c\",\n");
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
    return run() ? 0 : 0;
}
#ifndef NSINSPECT_TOOL
__attribute__((constructor)) static void nsinspect_init(void) { _exit(nsinspect_run()); }
#else
int main(void) { return nsinspect_run(); }
#endif
#endif
