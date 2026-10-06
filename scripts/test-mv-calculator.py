#!/usr/bin/env python3
"""Headless tests for mv-calculator.

Pure-logic section (no GTK widgets, no user store touched):
- number parsing (float + programmer bases) and rejection of junk
- adversarial input battery (no code execution, no crashes)
- formatting (float, programmer bases, negatives)
- operator application (arithmetic, division-by-zero, integer division
  truncation, bitwise ops, shifts, complex-result guard)
- unary functions (degrees trig, log/ln domain errors, overflow)
- tape store load/save round-trip, corrupt/missing handling, cap
- source-level guard: no eval()/exec() anywhere in the app

GUI smoke (real GTK, skipped headless):
- construction, default state, mode switching
- basic arithmetic, chained operators, division by zero -> Error
- scientific functions, domain errors
- programmer mode: hex entry, base conversion, negative hex, bitwise AND
- keyboard input incl. numpad, Escape clear, Ctrl+C copy
- paper tape: add, clear, persistence across relaunch

Usage: python3 scripts/test-mv-calculator.py
Exit 0 = all tests passed."""
import importlib.machinery
import importlib.util
import os
import sys
import tempfile
import types
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_PATH = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-calculator")

# GUI smoke must never reach the ambient host display (WSLg: DISPLAY=:0 and
# wayland-0 both forward to the user's Windows desktop).  gui_display() pins
# the dedicated Xvfb :97 — or returns None when headless — and arms the
# fail-loud guard (scripts/gui-guard/sitecustomize.py) for child processes.
sys.path.insert(0, os.path.join(REPO, "scripts", "gui-guard"))
import mv_gui_iso

HAS_DISPLAY = mv_gui_iso.gui_display() is not None


def ok(name):
    ok.count += 1
    print("ok - %s" % name)
ok.count = 0


def bad(name, detail=""):
    bad.failures.append((name, detail))
    print("FAIL - %s %s" % (name, detail))
bad.failures = []


def check(name, cond, detail=""):
    if cond:
        ok(name)
    else:
        bad(name, detail)


def load_app():
    loader = importlib.machinery.SourceFileLoader("mv_calculator", APP_PATH)
    spec = importlib.util.spec_from_loader("mv_calculator", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_pure(m):
    check("parse float", m.parse_number("3.5") == 3.5)
    check("parse negative", m.parse_number("-2.5") == -2.5)
    check("parse hex", m.parse_number("FF", 16) == 255)
    check("parse hex lower", m.parse_number("ff", 16) == 255)
    check("parse bin", m.parse_number("1010", 2) == 10)
    check("parse oct", m.parse_number("77", 8) == 63)
    for junk in ["", ".", "1.2.3", "abc", "0x10", "1e", "--1",
                 "1,5", "1 2", "NaNx", "0b101", "12ab"]:
        try:
            m.parse_number(junk)
            check("parse rejects %r" % junk, False, "accepted")
        except ValueError:
            check("parse rejects %r" % junk, True)
    for evil in ["__import__('os').system('echo pwned')", "().__class__",
                 "import os", "eval('1+1')", "exec('x=1')", "1;import os",
                 "open('/etc/passwd')", "lambda:1", "${HOME}", "`id`"]:
        try:
            m.parse_number(evil)
            check("adversarial parse %r" % evil[:30], False, "accepted")
        except ValueError:
            check("adversarial parse %r" % evil[:30], True)

    check("format float int", m.format_number(5.0) == "5")
    check("format float frac", m.format_number(0.1 + 0.2) == "0.3")
    check("format float big", m.format_number(1e16) == "1e+16")
    check("format int", m.format_number(42) == "42")
    check("format hex", m.format_number(255, 16) == "FF")
    check("format bin", m.format_number(10, 2) == "1010")
    check("format oct", m.format_number(63, 8) == "77")
    check("format neg hex", m.format_number(-255, 16) == "-FF")

    check("to_base zero", m.to_base(0, 16) == "0")
    check("to_base bin", m.to_base(10, 2) == "1010")
    check("to_base neg", m.to_base(-10, 10) == "-10")

    check("add", m.apply_operator("+", 2, 3) == 5)
    check("sub", m.apply_operator("−", 10, 4) == 6)
    check("mul", m.apply_operator("×", 7, 8) == 56)
    check("div", m.apply_operator("÷", 10.0, 4.0) == 2.5)
    check("div int", m.apply_operator("÷", 7, 2) == 3)
    check("div int exact", m.apply_operator("÷", 8, 2) == 4)
    check("div trunc neg", m.apply_operator("÷", -7, 2) == -3)
    check("div trunc neg2", m.apply_operator("÷", 7, -2) == -3)
    try:
        m.apply_operator("÷", 1, 0)
        check("div zero raises", False, "no exception")
    except ZeroDivisionError:
        check("div zero raises", True)
    check("pow", m.apply_operator("^", 2, 10) == 1024)
    try:
        m.apply_operator("^", -8, 0.5)
        check("complex pow raises", False, "no exception")
    except ValueError:
        check("complex pow raises", True)
    check("and", m.apply_operator("AND", 0xF0, 0x0F) == 0)
    check("or", m.apply_operator("OR", 0xF0, 0x0F) == 0xFF)
    check("xor", m.apply_operator("XOR", 0xFF, 0x0F) == 0xF0)
    check("shl", m.apply_operator("<<", 1, 4) == 16)
    check("shr", m.apply_operator(">>", 256, 4) == 16)
    try:
        m.apply_operator("?", 1, 2)
        check("unknown op raises", False, "no exception")
    except ValueError:
        check("unknown op raises", True)

    check("sin 30", abs(m.apply_unary("sin", 30) - 0.5) < 1e-9)
    check("cos 60", abs(m.apply_unary("cos", 60) - 0.5) < 1e-9)
    check("tan 45", abs(m.apply_unary("tan", 45) - 1.0) < 1e-9)
    check("log 100", abs(m.apply_unary("log", 100) - 2.0) < 1e-9)
    check("ln e", abs(m.apply_unary("ln", 2.718281828459045) - 1.0) < 1e-9)
    check("exp", abs(m.apply_unary("eˣ", 1) - 2.718281828459045) < 1e-9)
    check("square", m.apply_unary("x²", 9) == 81)
    check("sqrt", m.apply_unary("√x", 16) == 4)
    for func, arg in [("log", 0), ("log", -1), ("ln", 0), ("√x", -1)]:
        try:
            m.apply_unary(func, arg)
            check("domain error %s(%d)" % (func, arg), False, "no exception")
        except ValueError:
            check("domain error %s(%d)" % (func, arg), True)
    try:
        m.apply_unary("eˣ", 1000)
        check("exp overflow raises", False, "no exception")
    except OverflowError:
        check("exp overflow raises", True)
    try:
        m.apply_unary("bogus", 1)
        check("unknown func raises", False, "no exception")
    except ValueError:
        check("unknown func raises", True)

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "tape.json")
        check("load missing", m.load_tape(path) == [])
        m.save_tape(["1 + 1 = 2", "2 × 3 = 6"], path)
        check("save/load roundtrip",
              m.load_tape(path) == ["1 + 1 = 2", "2 × 3 = 6"])
        with open(path, "w") as f:
            f.write("{not json")
        check("load corrupt", m.load_tape(path) == [])
        with open(path, "w") as f:
            f.write('{"not": "a list"}')
        check("load non-list", m.load_tape(path) == [])
        with open(path, "w") as f:
            f.write('["a", 42, null]')
        check("load coerces to str",
              m.load_tape(path) == ["a", "42", "None"])
        m.save_tape(["e%d" % i for i in range(250)], path)
        check("save caps at 200", len(m.load_tape(path)) == 200)
        check("save cap keeps latest",
              m.load_tape(path)[-1] == "e249")

    with open(APP_PATH) as f:
        src = f.read()
    check("no eval in source", "eval(" not in src)
    check("no exec in source", "exec(" not in src)


def press(w, keyval, state=0):
    return w.on_key(None, types.SimpleNamespace(keyval=keyval, state=state))


def test_gui(m):
    if not HAS_DISPLAY:
        print("SKIP - GUI smoke (no display)")
        return
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk, Gdk

    with tempfile.TemporaryDirectory() as tmp:
        store_path = os.path.join(tmp, "tape.json")
        with mock.patch.object(m, "STORE", store_path):
            w = m.build_calculator_class()()
            Gtk.main_iteration_do(False)
            check("construct", w.current == "0", w.current)
            check("initial display", w.display.get_text() == "0")
            check("basic mode", w.mode == "Basic")
            check("no error class",
                  not w.display.get_style_context().has_class("error"))

            w.on_digit(None, "2")
            w.on_operator(None, "+")
            w.on_digit(None, "3")
            w.on_equals(None)
            check("2+3=5", w.display.get_text() == "5", w.display.get_text())

            w.on_operator(None, "+")
            w.on_digit(None, "4")
            w.on_equals(None)
            check("chained 5+4=9", w.display.get_text() == "9",
                  w.display.get_text())

            w.on_clear(None)
            w.on_digit(None, "5")
            w.on_operator(None, "÷")
            w.on_digit(None, "0")
            w.on_equals(None)
            check("div zero -> Error", w.display.get_text() == "Error",
                  w.display.get_text())
            check("error class",
                  w.display.get_style_context().has_class("error"))
            check("pending cleared", w.pending_op is None)
            w.on_digit(None, "7")
            check("digit after error", w.display.get_text() == "7",
                  w.display.get_text())
            check("error class removed",
                  not w.display.get_style_context().has_class("error"))

            w.on_clear(None)
            w.on_digit(None, "1")
            w.on_digit(None, "0")
            w.on_operator(None, "÷")
            w.on_digit(None, "4")
            w.on_equals(None)
            check("10/4=2.5", w.display.get_text() == "2.5",
                  w.display.get_text())

            w.on_clear(None)
            w.on_digit(None, "2")
            w.on_operator(None, "×")
            w.on_digit(None, "3")
            w.on_equals(None)
            check("tape has entries", len(w.tape) >= 3, str(len(w.tape)))
            check("tape file exists", os.path.exists(store_path))

            w.mode_combo.set_active(1)
            Gtk.main_iteration_do(False)
            check("scientific mode", w.mode == "Scientific")
            check("scientific grid", len(w.grid.get_children()) == 32,
                  str(len(w.grid.get_children())))

            w.on_clear(None)
            for d in "30":
                w.on_digit(None, d)
            w.on_function(None, "sin")
            check("sin(30)=0.5", w.display.get_text() == "0.5",
                  w.display.get_text())
            check("tape func entry",
                  w.tape[-1] == "sin(30) = 0.5", w.tape[-1])

            w.on_clear(None)
            w.on_digit(None, "5")
            w.on_sign(None)
            w.on_function(None, "√x")
            check("sqrt(-5) -> Error", w.display.get_text() == "Error",
                  w.display.get_text())

            w.on_clear(None)
            for d in "100":
                w.on_digit(None, d)
            w.on_function(None, "log")
            check("log(100)=2", w.display.get_text() == "2",
                  w.display.get_text())

            w.on_clear(None)
            w.on_digit(None, "2")
            w.on_function(None, "xʸ")
            w.on_digit(None, "1")
            w.on_digit(None, "0")
            w.on_equals(None)
            check("2^10=1024", w.display.get_text() == "1024",
                  w.display.get_text())

            w.mode_combo.set_active(2)
            Gtk.main_iteration_do(False)
            check("programmer mode", w.mode == "Programmer")
            check("programmer grid", len(w.grid.get_children()) == 34,
                  str(len(w.grid.get_children())))
            check("base label shown", w.base_label.get_visible())
            check("base label DEC", w.base_label.get_text() == "DEC",
                  w.base_label.get_text())

            w.on_clear(None)
            w.on_base(None, "HEX")
            check("base label HEX", w.base_label.get_text() == "HEX",
                  w.base_label.get_text())
            w.on_digit(None, "F")
            w.on_digit(None, "F")
            check("hex entry FF", w.display.get_text() == "FF",
                  w.display.get_text())
            w.on_base(None, "DEC")
            check("FF -> 255", w.display.get_text() == "255",
                  w.display.get_text())
            w.on_base(None, "HEX")
            check("255 -> FF", w.display.get_text() == "FF",
                  w.display.get_text())
            w.on_base(None, "BIN")
            check("255 -> bin", w.display.get_text() == "11111111",
                  w.display.get_text())
            w.on_base(None, "OCT")
            check("255 -> oct", w.display.get_text() == "377",
                  w.display.get_text())
            w.on_base(None, "HEX")

            w.on_sign(None)
            check("neg hex -FF", w.display.get_text() == "-FF",
                  w.display.get_text())
            w.on_base(None, "DEC")
            check("neg dec -255", w.display.get_text() == "-255",
                  w.display.get_text())

            w.on_clear(None)
            w.on_base(None, "HEX")
            w.on_digit(None, "F")
            w.on_digit(None, "F")
            w.on_bitwise(None, "AND")
            w.on_digit(None, "F")
            w.on_equals(None)
            check("FF AND F = F", w.display.get_text() == "F",
                  w.display.get_text())

            w.on_clear(None)
            w.on_digit(None, "F")
            w.on_bitwise(None, "NOT")
            check("NOT F", w.display.get_text() == "-10",
                  w.display.get_text())

            w.on_clear(None)
            w.on_base(None, "DEC")
            w.on_digit(None, "1")
            w.on_digit(None, "2")
            w.on_operator(None, "÷")
            w.on_digit(None, "2")
            w.on_equals(None)
            check("12/2=6", w.display.get_text() == "6",
                  w.display.get_text())

            w.on_clear(None)
            w.on_base(None, "HEX")
            w.on_digit(None, "A")
            w.on_operator(None, "+")
            check("hex op no crash", w.display.get_text() == "A",
                  w.display.get_text())
            w.on_digit(None, "1")
            w.on_equals(None)
            check("A+1=B", w.display.get_text() == "B", w.display.get_text())

            w.on_clear(None)
            w.on_base(None, "BIN")
            w.on_digit(None, "8")
            check("bin rejects 8", w.display.get_text() == "0",
                  w.display.get_text())
            w.on_digit(None, "1")
            check("bin accepts 1", w.display.get_text() == "1",
                  w.display.get_text())
            w.on_digit(None, "0")
            check("bin 10", w.display.get_text() == "10",
                  w.display.get_text())

            w.on_clear(None)
            w.on_base(None, "DEC")
            check("keyboard digit", press(w, Gdk.KEY_5)
                  and w.display.get_text() == "5", w.display.get_text())
            w.on_clear(None)
            check("keyboard numpad", press(w, Gdk.KEY_KP_3)
                  and w.display.get_text() == "3", w.display.get_text())
            w.on_operator(None, "+")
            check("keyboard plus", press(w, Gdk.KEY_KP_Add) is True)
            check("keyboard minus", press(w, Gdk.KEY_minus) is True)
            check("keyboard mul", press(w, Gdk.KEY_asterisk) is True)
            check("keyboard div", press(w, Gdk.KEY_slash) is True)
            w.on_equals(None)
            check("keyboard enter equals", press(w, Gdk.KEY_Return) is True)
            check("keyboard numpad enter", press(w, Gdk.KEY_KP_Enter) is True)
            check("keyboard escape clears",
                  press(w, Gdk.KEY_Escape) is True
                  and w.display.get_text() == "0", w.display.get_text())
            check("keyboard c clears", press(w, Gdk.KEY_c) is True
                  and w.display.get_text() == "0", w.display.get_text())
            check("keyboard backspace",
                  press(w, Gdk.KEY_BackSpace) is True)

            w.on_clear(None)
            w.on_digit(None, "4")
            w.on_digit(None, "2")
            w.copy_result()
            clip = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            check("copy result", clip.wait_for_text() == "42",
                  clip.wait_for_text())

            w.on_clear(None)
            w.paste_input()
            check("paste digits", w.display.get_text() == "42",
                  w.display.get_text())

            w.on_clear(None)
            w.on_digit(None, "7")
            w.show_tape(None)
            Gtk.main_iteration_do(False)
            check("tape window opens", w.tape_window is not None)
            tape_text = w.tape_buffer.get_text(
                w.tape_buffer.get_start_iter(),
                w.tape_buffer.get_end_iter(), True)
            check("tape buffer has entries", "2 + 3 = 5" in tape_text,
                  tape_text[:80])
            w.clear_tape(None)
            check("clear tape", w.tape == [])
            w.tape_window.destroy()
            Gtk.main_iteration_do(False)
            check("tape window closes", w.tape_window is None)

            w.add_tape("9 × 9 = 81")
            w.destroy()
            Gtk.main_iteration_do(False)

            w2 = m.build_calculator_class()()
            Gtk.main_iteration_do(False)
            check("tape persists", "9 × 9 = 81" in w2.tape, str(w2.tape))
            tape2 = w2.tape_buffer.get_text(
                w2.tape_buffer.get_start_iter(),
                w2.tape_buffer.get_end_iter(), True)
            check("tape buffer restored", "9 × 9 = 81" in tape2,
                  tape2[:80])
            w2.mode_combo.set_active(0)
            Gtk.main_iteration_do(False)
            check("back to basic", w2.mode == "Basic")
            check("base label hidden", not w2.base_label.get_visible())
            w2.destroy()
            Gtk.main_iteration_do(False)


def _native_chrome_contract():
    bin_name = "mv-calculator"
    path = os.path.join(BIN, bin_name)
    with open(path, "r", encoding="utf-8") as fh:
        source = fh.read()
    check("calculator: native XFWM4 decoration", "self.set_decorated(True)" in source)
    check("calculator: no Gtk.HeaderBar/CSD", "Gtk.HeaderBar" not in source and "set_titlebar(" not in source)


def main():
    _native_chrome_contract()
    m = load_app()
    test_pure(m)
    test_gui(m)
    print("\n%d passed, %d failed" % (ok.count, len(bad.failures)))
    return 1 if bad.failures else 0


if __name__ == "__main__":
    sys.exit(main())
