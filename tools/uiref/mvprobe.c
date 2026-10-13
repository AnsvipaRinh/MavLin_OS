/*
 * mvprobe.c - ground-truth probe for a running OS X 10.9 system.
 *
 * Cross-compiled from Linux (no SDK): every libc/AppKit symbol is declared
 * here and resolved at runtime through dlsym + the Objective-C runtime.
 * Loaded with DYLD_INSERT_LIBRARIES into any AppKit process; writes exact UI
 * constants as JSON to $MVPROBE_OUT (default /tmp/mvprobe.json).
 *
 *   skin    every +[NSColor ...Color] we can name -> sRGB hex + alpha
 *   window  contentRect math, standard button frames, window animation defaults
 *   control widget-type mapping (AppKit's private ns_widgetType) + metrics
 *   text    system font roles: family, size, ascender/descender/leading
 *
 * Build:
 *   clang -target x86_64-apple-macos10.9 -dynamiclib -fPIC -O1 -nostdinc \
 *         -fuse-ld=lld -Wl,-undefined,dynamic_lookup -o mvprobe.dylib mvprobe.c
 */
typedef struct _mv_FILE FILE;
typedef void *id;
typedef void *SEL;
typedef struct { double x, y, w, h; } rect_t;

extern void *dlopen(const char *path, int mode);
extern void *dlsym(void *handle, const char *sym);
extern char *getenv(const char *name);
extern FILE *fopen(const char *path, const char *mode);
extern int fclose(FILE *f);
extern int fprintf(FILE *f, const char *fmt, ...);
extern int snprintf(char *buf, unsigned long n, const char *fmt, ...);
extern void _exit(int code);

#define RTLD_DEFAULT ((void *)-2)
#define RTLD_LAZY 0x4

static id (*fn_objc_getClass)(const char *);
static SEL (*fn_sel_registerName)(const char *);
static void *(*fn_msgSend)(id, SEL);
static void *(*fn_class_getClassMethod)(id, SEL);
static FILE *out;

static SEL S(const char *n) { return fn_sel_registerName(n); }

static id send_id(id o, const char *sel) {
    SEL s = S(sel);
    id (*f)(id, SEL) = (id (*)(id, SEL))fn_msgSend;
    return f ? f(o, s) : 0;
}

static double send_dbl(id o, const char *sel) {
    SEL s = S(sel);
    double (*f)(id, SEL) = (double (*)(id, SEL))fn_msgSend;
    return f ? f(o, s) : 0.0;
}

static const char *send_str(id o, const char *sel) {
    SEL s = S(sel);
    const char *(*f)(id, SEL) = (const char *(*)(id, SEL))fn_msgSend;
    return f ? f(o, s) : "";
}

static int has_class_method(id cls, const char *sel) {
    return cls && fn_class_getClassMethod(cls, S(sel)) != 0;
}

static rect_t send_rect(id o, const char *sel) {
    SEL s = S(sel);
    rect_t (*f)(id, SEL) = (rect_t (*)(id, SEL))fn_msgSend;
    rect_t r = {-1, -1, -1, -1};
    if (f) r = f(o, s);
    return r;
}

/* --- colours ------------------------------------------------------------- */

static void color_hex(id c, char *buf, unsigned long n) {
    double r = -1, g = -1, b = -1, a = -1;
    if (c) {
        signed char (*f)(id, SEL, double *, double *, double *, double *) =
            (signed char (*)(id, SEL, double *, double *, double *, double *))
                fn_msgSend;
        SEL s = S("getRed:green:blue:alpha:");
        if (f(c, s, &r, &g, &b, &a)) {
            /* ok */
        } else {
            signed char (*w)(id, SEL, double *, double *) =
                (signed char (*)(id, SEL, double *, double *))fn_msgSend;
            SEL sw = S("getWhite:alpha:");
            if (w(c, sw, &r, &a)) g = b = r;
        }
    }
    if (r < 0) {
        snprintf(buf, n, "null");
        return;
    }
    int R = (int)(r * 255.0 + 0.5), G = (int)(g * 255.0 + 0.5), B = (int)(b * 255.0 + 0.5);
    snprintf(buf, n, "#%02x%02x%02x a=%.3f", R, G, B, a);
}

static const char *COLOR_NAMES[] = {
    "windowBackgroundColor", "underPageBackgroundColor", "contentBackgroundColor",
    "controlBackgroundColor", "controlColor", "controlAccentColor",
    "selectedControlColor", "secondaryControlColor", "alternateSelectedControlColor",
    "controlHighlightColor", "controlShadowColor", "controlEdgeColor",
    "textBackgroundColor", "textColor", "placeholderTextColor", "selectedTextColor",
    "selectedTextBackgroundColor", "selectedTextBackgroundAccentColor",
    "alternatingContentBackgroundColors", "unemphasizedSelectedContentBackgroundColor",
    "gridColor", "keyboardFocusIndicatorColor", "scrollbarTrackColor",
    "separatorColor", "linkColor", "activeCaptionColor", "inactiveCaptionColor",
    "windowFrameColor", "menuBackgroundColor", "menuItemHighlightColor",
    "toolTipBackgroundColor", "darkTextColor", "lightTextColor",
    "headerColor", "alternatingRowBackgroundColors", "findHighlightColor",
    "systemBackgroundColor", "systemBlueColor", "systemGreenColor", "systemRedColor",
    "systemYellowColor", "systemOrangeColor", "systemPurpleColor", "systemTealColor",
    "systemGrayColor", "labelColor", "secondaryLabelColor", "tertiaryLabelColor",
    "gridBackgroundColor", "documentBackgroundColor", "underPageBackgroundColor",
};

/* --- window -------------------------------------------------------------- */

static void probe_window(id NSWindow) {
    fprintf(out, "  \"window\": {\n    \"contentRectMath\": [\n");
    double cases[3][4] = {{800, 600, 800, 572}, {1440, 900, 1440, 872}, {1280, 720, 1280, 692}};
    for (int i = 0; i < 3; i++) {
        rect_t in = {0, 0, cases[i][2], cases[i][3]};
        rect_t (*f)(id, SEL, rect_t, unsigned long) =
            (rect_t (*)(id, SEL, rect_t, unsigned long))fn_msgSend;
        rect_t got = {-1, -1, -1, -1};
        SEL s = S("contentRectForFrameRect:styleMask:");
        if (f) got = f(NSWindow, s, in, 7UL); /* titled|closable|miniaturizable|resizable */
        fprintf(out,
                "      {\"frame\": [%g, %g], \"content\": [%g, %g], \"derived\": [%g, %g, %g, %g]}%s\n",
                cases[i][0], cases[i][1], cases[i][2], cases[i][3],
                got.x, got.y, got.w, got.h, i == 2 ? "" : ",");
    }
    fprintf(out, "    ],\n    \"standardButtons\": {\n");

    id (*swb)(id, SEL, SEL) = (id (*)(id, SEL, SEL))fn_msgSend;
    SEL sel_btn = S("standardWindowButton:");
    const char *labels[3] = {"close", "miniaturize", "zoom"};
    const char *names[3] = {"closeButton", "miniaturizeButton", "zoomButton"};
    for (int i = 0; i < 3; i++) {
        id b = swb ? swb(NSWindow, sel_btn, S(labels[i])) : 0;
        if (!b) continue;
        rect_t r = send_rect(b, "frame");
        fprintf(out, "      \"%s\": [%g, %g, %g, %g]%s\n", names[i], r.x, r.y, r.w, r.h,
                i == 2 ? "" : ",");
    }
    fprintf(out, "    }\n  },\n");
}

/* --- controls ------------------------------------------------------------ */

static void probe_controls(id NSButton, id NSCell) {
    fprintf(out, "  \"controls\": {\n");
    if (NSCell) {
        id (*wt)(id, SEL) = (id (*)(id, SEL))fn_msgSend;
        SEL s = S("ns_widgetType");
        if (wt && NSCell) {
            /* widget types are an enum; sample the numeric value per cell class
             * by asking each known cell class for a prototype instance */
            const char *cells[] = {"NSButtonCell", "NSPopUpButtonCell", "NSSwitchCell",
                                   "NSSliderCell", "NSStepperCell", "NSProgressIndicatorCell",
                                   "NSScroller", "NSSegmentedCell"};
            fprintf(out, "    \"widgetTypeProbe\": [\n");
            for (unsigned i = 0; i < sizeof(cells) / sizeof(cells[0]); i++) {
                id cls = fn_objc_getClass(cells[i]);
                fprintf(out, "      {\"cell\": \"%s\", \"hasWidgetType\": %s}%s\n", cells[i],
                        has_class_method(cls, "ns_widgetType") ? "true" : "false",
                        i == sizeof(cells) / sizeof(cells[0]) - 1 ? "" : ",");
            }
            fprintf(out, "    ],\n");
            (void)wt;
        }
    }
    if (NSButton) {
        const char *sels[] = {"setBezelStyle:", "bezelStyle", "controlSize", "setTitle:"};
        fprintf(out, "    \"buttonMetrics\": [\n");
        double sizes[4] = {11, 12, 13, 10};
        const char *sizeNames[4] = {"regular", "small", "mini", "large"};
        for (int i = 0; i < 4; i++) {
            id proto = send_id(NSButton, "alloc");
            if (!proto) continue;
            void (*cs)(id, SEL, long) = (void (*)(id, SEL, long))fn_msgSend;
            SEL s = S("setControlSize:");
            if (cs) cs(proto, s, sizes[i]);
            void (*set)(id, SEL, const char *) = (void (*)(id, SEL, const char *))fn_msgSend;
            if (set) set(proto, S("setTitle:"), "Button");
            void (*lay)(id, SEL) = (void (*)(id, SEL))fn_msgSend;
            if (lay) lay(proto, S("layout"));
            rect_t f1 = send_rect(proto, "frame");
            rect_t f2 = send_rect(proto, "fittingSize");
            fprintf(out,
                    "      {\"size\": \"%s\", \"frame\": [%g, %g, %g, %g], \"fitting\": [%g, %g, %g, %g]}%s\n",
                    sizeNames[i], f1.x, f1.y, f1.w, f1.h, f2.x, f2.y, f2.w, f2.h,
                    i == 3 ? "" : ",");
        }
        fprintf(out, "    ]\n");
        (void)sels;
    }
    fprintf(out, "  },\n");
}

/* --- fonts --------------------------------------------------------------- */

static void probe_fonts(id NSFont) {
    fprintf(out, "  \"text\": {\n    \"fonts\": [\n");
    const char *roles[] = {"systemFontOfSize:", "menuFontOfSize:", "menuBarFontOfSize:",
                           "smallSystemFontOfSize:", "labelFontOfSize:",
                           "controlFontOfSize:", "statusFontOfSize:",
                           "toolTipFontOfSize:", "windowTitleFontOfSize:"};
    double sizes[9] = {13, 14, 13, 11, 13, 13, 12, 11, 13};
    int first = 1;
    for (unsigned i = 0; i < sizeof(roles) / sizeof(roles[0]); i++) {
        id (*f)(id, SEL, double) = (id (*)(id, SEL, double))fn_msgSend;
        id font = f ? f(NSFont, S(roles[i]), sizes[i]) : 0;
        if (!font) continue;
        fprintf(out,
                "      %s{\"role\": \"%s\", \"family\": \"%s\", \"pointSize\": %g, "
                "\"ascender\": %g, \"descender\": %g, \"leading\": %g, \"xHeight\": %g}",
                first ? "" : ",\n", roles[i], send_str(font, "familyName"),
                send_dbl(font, "pointSize"), send_dbl(font, "ascender"),
                send_dbl(font, "descender"), send_dbl(font, "leading"),
                send_dbl(font, "xHeight"));
        first = 0;
    }
    fprintf(out, "\n    ]\n  }\n");
}

__attribute__((constructor)) static void mvprobe_init(void) {
    const char *path = getenv("MVPROBE_OUT");
    if (!path) path = "/tmp/mvprobe.json";
    out = fopen(path, "w");
    if (!out) _exit(0);

    fn_objc_getClass = (id (*)(const char *))dlsym(RTLD_DEFAULT, "objc_getClass");
    fn_sel_registerName = (SEL (*)(const char *))dlsym(RTLD_DEFAULT, "sel_registerName");
    fn_msgSend = dlsym(RTLD_DEFAULT, "objc_msgSend");
    fn_class_getClassMethod = (void *(*)(id, SEL))dlsym(RTLD_DEFAULT, "class_getClassMethod");
    if (!fn_objc_getClass || !fn_sel_registerName || !fn_msgSend) {
        fprintf(out, "{\"error\": \"objc runtime unavailable\"}");
        fclose(out);
        _exit(0);
    }
    dlopen("/System/Library/Frameworks/Foundation.framework/Foundation", RTLD_LAZY);
    void *appkit = dlopen("/System/Library/Frameworks/AppKit.framework/AppKit", RTLD_LAZY);

    id NSColor = fn_objc_getClass("NSColor");
    id NSFont = fn_objc_getClass("NSFont");
    id NSWindow = fn_objc_getClass("NSWindow");
    id NSButton = fn_objc_getClass("NSButton");
    id NSCell = fn_objc_getClass("NSCell");

    fprintf(out, "{\n  \"schema\": \"mavlinos.uiprobe/1\",\n");
    fprintf(out, "  \"appkit\": \"%s\",\n", appkit ? "loaded" : "missing");
    fprintf(out, "  \"colors\": [\n");
    int first = 1;
    for (unsigned i = 0; i < sizeof(COLOR_NAMES) / sizeof(COLOR_NAMES[0]); i++) {
        if (!has_class_method(NSColor, COLOR_NAMES[i])) continue;
        char hex[64];
        color_hex(send_id(NSColor, COLOR_NAMES[i]), hex, sizeof(hex));
        fprintf(out, "    %s{\"name\": \"%s\", \"value\": \"%s\"}", first ? "" : ",\n",
                COLOR_NAMES[i], COLOR_NAMES[i], hex);
        first = 0;
    }
    fprintf(out, "\n  ],\n");
    probe_window(NSWindow);
    probe_controls(NSButton, NSCell);
    probe_fonts(NSFont);
    fprintf(out, "}\n");
    fclose(out);
    _exit(0);
}