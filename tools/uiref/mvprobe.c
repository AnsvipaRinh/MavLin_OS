/*
 * mvprobe.c - ground-truth probe for a running OS X 10.9 (Mavericks) system.
 *
 * Cross-compiled from Linux without an Apple SDK: every libc/AppKit symbol is
 * declared here and resolved at run time through dlsym() plus the Objective-C
 * runtime. Two flavours share this source:
 *
 *   mvprobe.dylib   DYLD_INSERT_LIBRARIES into an AppKit process; measures and
 *                   then ends that process (exit code carries the status).
 *   mvprobe-tool    standalone tool for the guest's Aqua session - preferred,
 *                   because it never kills an application.
 *
 * -DMVPROBE_SELFTEST builds the same document writer against a runtime that
 * resolves nothing, so tests/uiref/test_probe_json.py can prove on Linux that
 * the output is valid JSON and reports gaps instead of invented values.
 *
 *   skin     every +[NSColor ...Color] we can name -> hex + alpha + how it was
 *            converted; null and a gap record when AppKit refuses to convert
 *   window   a real NSWindow instance (standardWindowButton: is an instance
 *            method taking an NSWindowButton enum) plus
 *            contentRectForFrameRect:styleMask: for the masks in real use
 *   control  NSControlSize metrics for Regular(0)/Small(1)/Mini(2) - the real
 *            constants - and the numeric value of AppKit's private instance
 *            method -ns_widgetType when the cell class implements it
 *   text     system font roles with family, size, ascender/descender/leading
 *
 * The document is assembled in memory, written to a temp file, fsynced and
 * renamed, so a truncated file can never be mistaken for a good one.
 * Exit code: 0 complete, 2 partial (see summary.status), 3 runtime/output error.
 *
 * Build: tools/uiref/build-probe.sh
 */
/* casting objc_msgSend to the exact AppKit signature is the point of this file */
#pragma clang diagnostic ignored "-Wcast-function-type-mismatch"
#ifdef MVPROBE_SELFTEST
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#else
typedef struct _mv_FILE FILE;
#endif
typedef void *id;
typedef void *Class;
typedef void *SEL;
typedef signed char mv_bool;
typedef long mv_int;
typedef unsigned long mv_uint;
typedef double CGFloat;
typedef __builtin_va_list mv_va_list;
typedef unsigned long mv_size;
typedef struct { CGFloat x, y, w, h; } mv_rect;

extern void *dlopen(const char *path, int mode);
extern void *dlsym(void *handle, const char *sym);
extern char *getenv(const char *name);
extern FILE *fopen(const char *path, const char *mode);
extern int fclose(FILE *f);
extern int fprintf(FILE *f, const char *fmt, ...);
extern int snprintf(char *buf, unsigned long n, const char *fmt, ...);
extern int vsnprintf(char *buf, unsigned long n, const char *fmt, mv_va_list ap);
extern mv_size fwrite(const void *p, mv_size size, mv_size n, FILE *f);
extern int fflush(FILE *f);
extern int fsync(int fd);
extern int fileno(FILE *f);
extern int rename(const char *from, const char *to);
extern int unlink(const char *path);
extern void _exit(int code);

#define RTLD_DEFAULT ((void *)-2)
#define RTLD_LAZY 0x4

/* --- objective-C runtime --------------------------------------------------- */
static Class (*fn_objc_getClass)(const char *);
static SEL (*fn_sel_registerName)(const char *);
static void *(*fn_msgSend)(id, SEL);
static void *(*fn_class_getInstanceMethod)(Class, SEL);
static id (*fn_object_getClass)(id);
static void (*fn_free)(void *);

static SEL S(const char *n) { return fn_sel_registerName ? fn_sel_registerName(n) : 0; }

static const char *class_name_of(id obj) {
    if (!obj || !fn_object_getClass) return 0;
    Class c = fn_object_getClass(obj);
    return (const char *)c;
}

/* typed send helpers: the return type must match the AppKit selector exactly */
static id send_id(id o, const char *sel) {
    SEL s = S(sel);
    if (!o || !s || !fn_msgSend) return 0;
    id (*f)(id, SEL) = (id (*)(id, SEL))fn_msgSend;
    return f(o, s);
}

static id send_id_arg(id o, const char *sel, mv_int v) {
    SEL s = S(sel);
    if (!o || !s || !fn_msgSend) return 0;
    id (*f)(id, SEL, mv_int) = (id (*)(id, SEL, mv_int))fn_msgSend;
    return f(o, s, v);
}

static void send_void_arg(id o, const char *sel, mv_int v) {
    SEL s = S(sel);
    if (!o || !s || !fn_msgSend) return;
    void (*f)(id, SEL, mv_int) = (void (*)(id, SEL, mv_int))fn_msgSend;
    f(o, s, v);
}

static void send_void_str(id o, const char *sel, const char *v) {
    SEL s = S(sel);
    if (!o || !s || !fn_msgSend) return;
    void (*f)(id, SEL, const char *) = (void (*)(id, SEL, const char *))fn_msgSend;
    f(o, s, v);
}

static mv_bool send_bool(id o, const char *sel) {
    SEL s = S(sel);
    if (!o || !s || !fn_msgSend) return 0;
    mv_bool (*f)(id, SEL) = (mv_bool (*)(id, SEL))fn_msgSend;
    return f(o, s);
}

static mv_int send_int(id o, const char *sel) {
    SEL s = S(sel);
    if (!o || !s || !fn_msgSend) return 0;
    mv_int (*f)(id, SEL) = (mv_int (*)(id, SEL))fn_msgSend;
    return f(o, s);
}

static double send_dbl(id o, const char *sel) {
    SEL s = S(sel);
    if (!o || !s || !fn_msgSend) return 0.0;
    double (*f)(id, SEL) = (double (*)(id, SEL))fn_msgSend;
    return f(o, s);
}

static const char *send_str(id o, const char *sel) {
    SEL s = S(sel);
    if (!o || !s || !fn_msgSend) return 0;
    const char *(*f)(id, SEL) = (const char *(*)(id, SEL))fn_msgSend;
    return f(o, s);
}

static mv_rect send_rect(id o, const char *sel) {
    SEL s = S(sel);
    mv_rect r = {0, 0, -1, -1};
    if (!o || !s || !fn_msgSend) return r;
    mv_rect (*f)(id, SEL) = (mv_rect (*)(id, SEL))fn_msgSend;
    return f(o, s);
}

/* class methods live on the metaclass; instance methods on the class itself */
static Class meta_of(Class cls) {
    return cls && fn_object_getClass ? fn_object_getClass((id)cls) : 0;
}

static mv_bool has_instance_method(Class cls, const char *sel) {
    if (!cls || !fn_class_getInstanceMethod) return 0;
    return fn_class_getInstanceMethod(cls, S(sel)) != 0;
}

static mv_bool has_class_method(Class cls, const char *sel) {
    if (!cls || !fn_class_getInstanceMethod) return 0;
    return fn_class_getInstanceMethod(meta_of(cls), S(sel)) != 0;
}

static void release_obj(id o) {
    if (!o || !fn_msgSend) return;
    SEL s = S("release");
    if (!s) return;
    void (*f)(id, SEL) = (void (*)(id, SEL))fn_msgSend;
    f(o, s);
}

/* --- output buffer: the document is complete before anything is written ----- */
#define OUT_CAP (1 << 21)
static char out_buf[OUT_CAP];
static unsigned long out_len;
static int gap_count;
static int error_count;
static int item_count;

static void emit(const char *fmt, ...) {
    mv_va_list ap;
    if (out_len + 2048 >= OUT_CAP) return;
    __builtin_va_start(ap, fmt);
    out_len += (unsigned long)vsnprintf(out_buf + out_len, OUT_CAP - out_len, fmt, ap);
    __builtin_va_end(ap);
}

/* JSON string or null, without a helper table */
static const char *json_str(const char *v) {
    return v ? v : "null";
}

/* errors[] and gaps[] live in their own buffers: a gap raised while a section
   is still open must not land inside that section's array */
static char err_buf[OUT_CAP / 8];
static unsigned long err_len;
static char gap_buf[OUT_CAP / 4];
static unsigned long gap_len;

static void add_error(const char *section, const char *msg) {
    error_count++;
    if (err_len + 512 >= sizeof(err_buf)) return;
    err_len += (unsigned long)snprintf(err_buf + err_len, sizeof(err_buf) - err_len,
                                      "%s    {\"section\": \"%s\", \"message\": \"%s\"}",
                                      err_len ? ",\n" : "", section ? section : "?",
                                      msg ? msg : "unspecified");
}

static void add_gap(const char *section, const char *what, const char *reason) {
    gap_count++;
    if (gap_len + 512 >= sizeof(gap_buf)) return;
    gap_len += (unsigned long)snprintf(gap_buf + gap_len, sizeof(gap_buf) - gap_len,
                                      "%s    {\"section\": \"%s\", \"missing\": \"%s\", "
                                      "\"reason\": \"%s\", \"resolution\": "
                                      "\"re-run inside a full OS X 10.9 Aqua session\"}",
                                      gap_len ? ",\n" : "", section ? section : "?",
                                      what ? what : "?", reason ? reason : "unavailable");
}

static void flush_side(const char *key, const char *buf, unsigned long len) {
    if (!len) {
        emit("  \"%s\": [null],\n", key);
        return;
    }
    emit("  \"%s\": [\n    %.*s\n  ],\n", key, (int)len, buf);
}

/* --- colours --------------------------------------------------------------- */
static mv_bool color_to_hex(id c, char *hex, unsigned long n, double *alpha) {
    double r = -1, g = -1, b = -1, a = -1;
    if (!c) return 0;
    SEL srgb = S("getRed:green:blue:alpha:");
    if (fn_msgSend && srgb) {
        mv_bool (*f)(id, SEL, double *, double *, double *, double *) =
            (mv_bool (*)(id, SEL, double *, double *, double *, double *))fn_msgSend;
        if (f(c, srgb, &r, &g, &b, &a)) {
            *alpha = a;
            snprintf(hex, n, "#%02x%02x%02x", (int)(r * 255.0 + 0.5),
                     (int)(g * 255.0 + 0.5), (int)(b * 255.0 + 0.5));
            return 1;
        }
    }
    r = -1;
    SEL gray = S("getWhite:alpha:");
    if (fn_msgSend && gray) {
        mv_bool (*f)(id, SEL, double *, double *) =
            (mv_bool (*)(id, SEL, double *, double *))fn_msgSend;
        if (f(c, gray, &r, &a)) {
            *alpha = a;
            snprintf(hex, n, "#%02x%02x%02x", (int)(r * 255.0 + 0.5),
                     (int)(g * 255.0 + 0.5), (int)(b * 255.0 + 0.5));
            return 1;
        }
    }
    return 0;
}

static const char *COLOR_NAMES[] = {
    "windowBackgroundColor", "underPageBackgroundColor", "contentBackgroundColor",
    "controlBackgroundColor", "controlColor", "controlAccentColor",
    "selectedControlColor", "secondarySelectedControlColor", "alternateSelectedControlColor",
    "controlHighlightColor", "controlShadowColor", "controlEdgeColor",
    "textBackgroundColor", "textColor", "placeholderTextColor", "selectedTextColor",
    "selectedTextBackgroundColor", "selectedTextBackgroundAccentColor",
    "gridColor", "keyboardFocusIndicatorColor", "scrollbarTrackColor",
    "separatorColor", "linkColor", "activeCaptionColor", "inactiveCaptionColor",
    "windowFrameColor", "menuBackgroundColor", "menuItemHighlightColor",
    "toolTipBackgroundColor", "darkTextColor", "lightTextColor",
    "headerColor", "findHighlightColor", "systemBackgroundColor",
    "systemBlueColor", "systemGreenColor", "systemRedColor", "systemYellowColor",
    "systemOrangeColor", "systemPurpleColor", "systemTealColor", "systemGrayColor",
    "labelColor", "secondaryLabelColor", "tertiaryLabelColor",
    "gridBackgroundColor", "documentBackgroundColor",
};
#define COLOR_COUNT ((int)(sizeof(COLOR_NAMES) / sizeof(COLOR_NAMES[0])))

static int probe_colors(Class NSColor) {
    int found = 0, first = 1;
    emit("  \"colors\": {\n    \"status\": \"%s\",\n    \"requested\": %d,\n"
         "    \"items\": [\n", COLOR_COUNT ? "ok" : "failed", COLOR_COUNT);
    for (int i = 0; i < COLOR_COUNT; i++) {
        if (!NSColor || !has_class_method(NSColor, COLOR_NAMES[i])) {
            add_gap("colors", COLOR_NAMES[i], "no such class method on NSColor");
            continue;
        }
        id c = send_id(NSColor, COLOR_NAMES[i]);
        char hex[32];
        double alpha = -1.0;
        mv_bool ok = color_to_hex(c, hex, sizeof(hex), &alpha);
        char alpha_buf[32];
        if (ok && alpha >= 0.0 && alpha <= 1.0)
            snprintf(alpha_buf, sizeof(alpha_buf), "%.4f", alpha);
        else
            snprintf(alpha_buf, sizeof(alpha_buf), "null");
        emit("      %s{\"name\": \"%s\", \"hex\": %s%s%s, \"alpha\": %s, "
             "\"catalog\": %s, \"color_name\": %s, \"color_space\": %s}%s\n",
             first ? "" : ",\n", COLOR_NAMES[i],
             ok ? "\"" : "", ok ? hex : "null", ok ? "\"" : "",
             alpha_buf,
             json_str(send_str(c, "catalogName")),
             json_str(send_str(c, "colorName")),
             json_str(send_str(c, "colorSpaceName")),
             "");
        first = 0;
        found++;
        item_count++;
        if (!ok)
            add_gap("colors", COLOR_NAMES[i],
                    "AppKit refused getRed:/getWhite: (pattern or catalog colour)");
    }
    emit("    ]\n  },\n");
    if (!found) add_error("colors", "no colour could be read from NSColor");
    return found;
}

/* --- window ---------------------------------------------------------------- */
static const char *BUTTON_NAMES[3] = {"close", "miniaturize", "zoom"};
static const mv_int BUTTON_KINDS[3] = {0, 1, 2}; /* NSWindowClose/Miniaturize/ZoomButton */
static const mv_uint WINDOW_MASKS[8] = {1, 3, 7, 9, 15, 17, 129, 4111};

static int probe_window(Class NSWindow) {
    id win = 0;
    mv_rect content = {0, 0, 800, 600};
    mv_uint init_mask = 15UL; /* titled|closable|miniaturizable|resizable */

    if (NSWindow) {
        id alloc = send_id(NSWindow, "alloc");
        SEL initSel = S("initWithContentRect:styleMask:backing:defer:");
        if (alloc && initSel && fn_msgSend) {
            /* backing: NSBackingStoreBuffered = 2, defer: NO */
            id (*init)(id, SEL, mv_rect, mv_uint, mv_int, mv_bool) =
                (id (*)(id, SEL, mv_rect, mv_uint, mv_int, mv_bool))fn_msgSend;
            win = init(alloc, initSel, content, init_mask, 2, 0);
        }
        if (!win) add_error("window", "could not create an NSWindow instance");
    }

    emit("  \"window\": {\n    \"status\": \"%s\",\n    \"units\": \"pt\",\n"
         "    \"instance\": %s,\n", win ? "ok" : "failed", win ? "true" : "false");

    int buttons = 0, first = 1;
    emit("    \"standard_buttons\": [\n");
    for (int i = 0; i < 3 && win; i++) {
        id b = send_id_arg(win, "standardWindowButton:", BUTTON_KINDS[i]);
        if (!b) {
            add_gap("window", BUTTON_NAMES[i],
                    "standardWindowButton: returned nil for this button kind");
            continue;
        }
        mv_rect f = send_rect(b, "frame");
        if (f.w <= 0.0 || f.h <= 0.0)
            add_gap("window", BUTTON_NAMES[i], "button frame is empty (window not laid out)");
        const char *cell = class_name_of(send_id(b, "cell"));
        emit("      %s{\"name\": \"%s\", \"button_kind\": %ld, "
             "\"frame\": [%g, %g, %g, %g], \"cell\": %s, "
             "\"kind\": \"measured\", \"units\": \"pt\"}%s\n",
             first ? "" : ",\n", BUTTON_NAMES[i], (long)BUTTON_KINDS[i],
             f.x, f.y, f.w, f.h, json_str(cell),
             (i == 2) ? "\n" : "");
        first = 0;
        buttons++;
        item_count++;
    }
    emit("    ],\n");

    int math_ok = 0;
    first = 1;
    emit("    \"content_rect_math\": [\n");
    for (int i = 0; i < 8 && win && fn_msgSend; i++) {
        SEL sel = S("contentRectForFrameRect:styleMask:");
        if (!sel) break;
        mv_rect in = {100, 100, 800, 600};
        mv_rect (*f)(id, SEL, mv_rect, mv_uint) =
            (mv_rect (*)(id, SEL, mv_rect, mv_uint))fn_msgSend;
        mv_rect got = f(win, sel, in, WINDOW_MASKS[i]);
        if (got.w < 0.0) {
            add_gap("window", "contentRectForFrameRect",
                    "AppKit returned an invalid rectangle for this mask");
            continue;
        }
        emit("      %s{\"input_frame\": [%g, %g, %g, %g], \"style_mask\": %lu, "
             "\"content_rect\": [%g, %g, %g, %g], "
             "\"derived\": {\"kind\": \"derived\", \"deriv\": "
             "\"input_frame.height - content_rect.height\", "
             "\"titlebar_height\": %g, \"left_chrome\": %g, \"right_chrome\": %g}, "
             "\"units\": \"pt\", \"kind\": \"measured\"}%s\n",
             first ? "" : ",\n", in.x, in.y, in.w, in.h,
             (unsigned long)WINDOW_MASKS[i], got.x, got.y, got.w, got.h,
             in.h - got.h, got.x - in.x, (in.x + in.w) - (got.x + got.w),
             "");
        first = 0;
        math_ok++;
        item_count++;
    }
    emit("    ]\n  },\n");

    if (win) release_obj(win);
    if (win && !buttons) add_error("window", "no standard window button could be measured");
    if (win && !math_ok) add_error("window", "contentRectForFrameRect: produced no value");
    return buttons && math_ok;
}

/* --- controls -------------------------------------------------------------- */
/* NSControlSize: Regular = 0, Small = 1, Mini = 2. There is no "Large". */
static const mv_int CONTROL_SIZES[3] = {0, 1, 2};
static const char *CONTROL_SIZE_NAMES[3] = {"regular", "small", "mini"};
static const char *CELL_CLASSES[8] = {"NSButtonCell", "NSPopUpButtonCell", "NSSliderCell",
                                      "NSStepperCell", "NSProgressIndicatorCell",
                                      "NSSwitchCell", "NSSegmentedCell", "NSScroller"};

static int probe_controls(Class NSButton) {
    emit("  \"controls\": {\n    \"status\": \"%s\",\n    \"button_metrics\": [\n",
         NSButton ? "ok" : "failed");
    int metrics = 0;
    for (int i = 0; i < 3 && NSButton; i++) {
        id btn = send_id(NSButton, "alloc");
        SEL initSel = S("initWithFrame:");
        if (!btn || !initSel || !fn_msgSend) {
            add_gap("controls", CONTROL_SIZE_NAMES[i], "NSButton could not be allocated");
            continue;
        }
        mv_rect zero = {0, 0, 0, 0};
        id (*init)(id, SEL, mv_rect) = (id (*)(id, SEL, mv_rect))fn_msgSend;
        btn = init(btn, initSel, zero);
        if (!btn) {
            release_obj(btn);
            add_gap("controls", CONTROL_SIZE_NAMES[i],
                    "NSButton initWithFrame: returned nil");
            continue;
        }
        send_void_arg(btn, "setControlSize:", CONTROL_SIZES[i]);
        send_void_str(btn, "setTitle:", "Button");
        send_id(btn, "sizeToFit");
        mv_int readback = send_int(btn, "controlSize");
        mv_rect fsize = send_rect(btn, "frame");
        mv_rect fitting = send_rect(btn, "fittingSize");
        emit("      %s{\"control_size\": \"%s\", \"value\": %ld, \"read_back\": %ld, "
             "\"frame\": [%g, %g, %g, %g], \"fitting_size\": [%g, %g, %g, %g], "
             "\"units\": \"pt\", \"kind\": \"measured\"}",
             metrics ? ",\n" : "", CONTROL_SIZE_NAMES[i], (long)CONTROL_SIZES[i],
             (long)readback, fsize.x, fsize.y, fsize.w, fsize.h,
             fitting.x, fitting.y, fitting.w, fitting.h, "");
        metrics++;
        item_count++;
    }
    emit("    ],\n");

    int types = 0, first = 1;
    emit("    \"widget_types\": [\n");
    for (unsigned i = 0; i < sizeof(CELL_CLASSES) / sizeof(CELL_CLASSES[0]); i++) {
        Class cls = fn_objc_getClass ? fn_objc_getClass(CELL_CLASSES[i]) : 0;
        if (!cls) continue;
        mv_bool has = has_instance_method(cls, "ns_widgetType");
        mv_bool got = 0;
        mv_int value = 0;
        if (has) {
            id proto = send_id(cls, "init");
            if (proto) {
                value = send_int(proto, "ns_widgetType");
                got = 1;
                release_obj(proto);
            }
        }
        if (got)
            emit("      %s{\"cell\": \"%s\", \"has_instance_method\": true, "
                 "\"widget_type\": %ld, \"units\": \"raw AppKit enum\"}",
                 first ? "" : ",\n", CELL_CLASSES[i], (long)value);
        else
            emit("      %s{\"cell\": \"%s\", \"has_instance_method\": %s, "
                 "\"widget_type\": null}",
                 first ? "" : ",\n", CELL_CLASSES[i], has ? "true" : "false");
        first = 0;
        types++;
        item_count++;
        if (!got && has)
            add_gap("controls", CELL_CLASSES[i],
                    "ns_widgetType present but the prototype instance could not answer");
    }
    emit("    ]\n  },\n");
    if (NSButton && !metrics) add_error("controls", "no NSControlSize measurement succeeded");
    return metrics;
}

/* --- fonts ----------------------------------------------------------------- */
static const char *FONT_ROLES[9] = {
    "systemFontOfSize:", "menuFontOfSize:", "menuBarFontOfSize:",
    "smallSystemFontOfSize:", "labelFontOfSize:", "controlFontOfSize:",
    "statusFontOfSize:", "toolTipFontOfSize:", "windowTitleFontOfSize:",
};
static const double FONT_SIZES[9] = {13, 14, 13, 11, 13, 13, 12, 11, 13};

static int probe_fonts(Class NSFont) {
    int count = 0;
    emit("  \"text\": {\n    \"status\": \"%s\",\n    \"fonts\": [\n",
         NSFont ? "ok" : "failed");
    for (unsigned i = 0; i < sizeof(FONT_ROLES) / sizeof(FONT_ROLES[0]); i++) {
        if (!NSFont || !has_class_method(NSFont, FONT_ROLES[i])) {
            add_gap("text", FONT_ROLES[i], "role selector missing on NSFont");
            continue;
        }
        SEL s = S(FONT_ROLES[i]);
        id (*f)(id, SEL, double) = (id (*)(id, SEL, double))fn_msgSend;
        id font = f(NSFont, s, FONT_SIZES[i]);
        if (!font) {
            add_gap("text", FONT_ROLES[i], "NSFont returned nil for this role");
            continue;
        }
        emit("      %s{\"role\": \"%s\", \"requested_size\": %g, \"family\": %s, "
             "\"font_name\": %s, \"point_size\": %g, \"ascender\": %g, "
             "\"descender\": %g, \"leading\": %g, \"x_height\": %g, "
             "\"units\": \"pt\", \"kind\": \"measured\"}",
             count ? ",\n" : "", FONT_ROLES[i], FONT_SIZES[i],
             json_str(send_str(font, "familyName")),
             json_str(send_str(font, "fontName")),
             send_dbl(font, "pointSize"), send_dbl(font, "ascender"),
             send_dbl(font, "descender"), send_dbl(font, "leading"),
             send_dbl(font, "xHeight"));
        count++;
        item_count++;
    }
    emit("    ]\n  },\n");
    if (!count) add_error("text", "no font role could be measured");
    return count;
}

/* --- environment ----------------------------------------------------------- */
static void probe_environment(void) {
    Class NSProcessInfo = fn_objc_getClass ? fn_objc_getClass("NSProcessInfo") : 0;
    Class NSApp = fn_objc_getClass ? fn_objc_getClass("NSApplication") : 0;
    const char *os = 0;
    int have_session = 0;
    if (NSProcessInfo) {
        id info = send_id(NSProcessInfo, "processInfo");
        os = send_str(info, "operatingSystemVersionString");
    }
    if (NSApp) {
        id app = send_id(NSApp, "sharedApplication");
        have_session = app ? 1 : 0;
        if (app) {
            /* accessory policy: measure without stealing the user's focus */
            send_void_arg(app, "setActivationPolicy:", 1);
        }
    }
    emit("  \"environment\": {\n");
    emit("    \"os_version\": %s,\n", json_str(os));
    emit("    \"appkit\": \"/System/Library/Frameworks/AppKit.framework\",\n");
    emit("    \"aqua_session\": %s,\n", have_session ? "true" : "false");
    emit("    \"units\": {\"geometry\": \"pt\", "
         "\"note\": \"1 pt == 1 px at 1x scaling in this guest\"}\n");
    emit("  },\n");
}

/* --- document -------------------------------------------------------------- */
static int resolve_runtime(void) {
    fn_objc_getClass = (Class(*)(const char *))dlsym(RTLD_DEFAULT, "objc_getClass");
    fn_sel_registerName = (SEL(*)(const char *))dlsym(RTLD_DEFAULT, "sel_registerName");
    fn_msgSend = dlsym(RTLD_DEFAULT, "objc_msgSend");
    fn_class_getInstanceMethod =
        (void *(*)(Class, SEL))dlsym(RTLD_DEFAULT, "class_getInstanceMethod");
    fn_object_getClass = (id(*)(id))dlsym(RTLD_DEFAULT, "object_getClass");
    fn_free = (void(*)(void *))dlsym(RTLD_DEFAULT, "free");
    return fn_objc_getClass && fn_sel_registerName && fn_msgSend &&
           fn_class_getInstanceMethod && fn_object_getClass;
}

static int assemble_document(void) {
    Class NSColor = fn_objc_getClass("NSColor");
    Class NSWindow = fn_objc_getClass("NSWindow");
    Class NSButton = fn_objc_getClass("NSButton");
    Class NSFont = fn_objc_getClass("NSFont");

    int ok_colors = probe_colors(NSColor);
    int ok_window = probe_window(NSWindow);
    int ok_controls = probe_controls(NSButton);
    int ok_text = probe_fonts(NSFont);
    int complete = ok_colors && ok_window && ok_controls && ok_text;

    flush_side("errors", err_buf, err_len);
    flush_side("gaps", gap_buf, gap_len);
    emit("  \"summary\": {\"items\": %d, \"errors\": %d, \"gaps\": %d, "
         "\"status\": \"%s\"},\n", item_count, error_count, gap_count,
         complete ? "complete" : "partial");
    emit("  \"status\": \"%s\"\n", complete ? "complete" : "partial");
    emit("}\n");
    return complete;
}

static int write_document(const char *path) {
    char tmp[512];
    snprintf(tmp, sizeof(tmp), "%s.tmp", path);
    FILE *f = fopen(tmp, "w");
    if (!f) return 0;
    if (fwrite(out_buf, 1, out_len, f) != out_len) {
        fclose(f);
        unlink(tmp);
        return 0;
    }
    if (fflush(f) != 0) {
        fclose(f);
        unlink(tmp);
        return 0;
    }
    fsync(fileno(f));
    fclose(f);
    if (rename(tmp, path) != 0) {
        unlink(tmp);
        return 0;
    }
    return 1;
}

static int run_probe(const char *path) {
    if (!resolve_runtime()) {
        emit("{\n  \"schema\": \"mavlinos.uiprobe/2\",\n  \"status\": \"failed\",\n");
        emit("  \"errors\": [\n    {\"section\": \"runtime\", \"message\": "
             "\"Objective-C runtime unavailable (objc_msgSend / objc_getClass "
             "not resolvable in this process)\"}\n  ],\n");
        emit("  \"gaps\": [null],\n");
        emit("  \"summary\": {\"items\": 0, \"errors\": 1, \"gaps\": 0, "
             "\"status\": \"failed\"}\n}\n");
        if (!write_document(path)) return 3;
        return 3;
    }
    out_len = 0;
    emit("{\n");
    emit("  \"schema\": \"mavlinos.uiprobe/2\",\n");
    emit("  \"kind\": \"measured\",\n");
    emit("  \"extractor\": \"mvprobe.c\",\n");
    probe_environment();
    assemble_document();
    if (!write_document(path)) return 3;
    return error_count ? 2 : 0;
}

/* ======================= self test: fake runtime on Linux =================== */
#ifdef MVPROBE_SELFTEST
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static SEL stub_sel(const char *n) { (void)n; return (SEL)(size_t)1; }
static Class stub_class(const char *name) {
    static const char *known[] = {"NSColor", "NSWindow", "NSButton", "NSFont",
                                  "NSBundle", "NSApplication", "NSProcessInfo"};
    unsigned i;
    for (i = 0; i < sizeof(known) / sizeof(known[0]); i++)
        if (!strcmp(known[i], name)) return (Class)known[i];
    return 0;
}
static void *stub_instance_method(void) { return 0; }
static id stub_object_getClass(id o) { return o; }
/* a real function: every AppKit call resolves but answers nothing, which is
   exactly the degraded case the document writer has to survive */
static void *stub_msgSend(id o, SEL s) { (void)o; (void)s; return 0; }

/* The self test runs the real document writer with a runtime that resolves no
   AppKit behaviour at all: every value must come back as a documented gap and
   the file must still be valid JSON. */
int main(int argc, char **argv) {
    const char *out = argc > 1 ? argv[1] : "/tmp/mvprobe-selftest.json";
    fn_objc_getClass = stub_class;
    fn_sel_registerName = stub_sel;
    fn_msgSend = (void *)stub_msgSend; /* selectors resolve, no AppKit answers */
    fn_class_getInstanceMethod = (void *(*)(Class, SEL))stub_instance_method;
    fn_object_getClass = stub_object_getClass;
    emit("{\n  \"schema\": \"mavlinos.uiprobe/2\",\n");
    emit("  \"kind\": \"measured\",\n  \"extractor\": \"mvprobe.c\",\n");
    probe_environment();
    assemble_document();
    if (!write_document(out)) return 3;
    return error_count ? 2 : 0;
}
#else
static int mvprobe_run(void) {
    const char *path = getenv("MVPROBE_OUT");
    if (!path) path = "/tmp/mvprobe.json";
    return run_probe(path);
}
#ifndef MVPROBE_TOOL
__attribute__((constructor)) static void mvprobe_init(void) { _exit(mvprobe_run()); }
#else
int main(void) { return mvprobe_run(); }
#endif
#endif
