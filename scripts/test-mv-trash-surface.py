#!/usr/bin/env python3
"""Headless tests for the Trash surface (canonical #15): mv-empty-trash and
mv-trash-putback.

The audit found two behaviours that the previous gates were happy with:

  * Empty Trash was wired straight to `trash-empty` from three entry points
    (Super+Shift+Delete, Super+Shift+E, the Finder context action) with no
    confirmation at all, and `trash-empty` is immediate, silent and
    irreversible. Finder always asks. These tests pin the exact wording,
    the Cancel-is-default property, and the hard rule that the only way to
    erase without asking is the explicit --yes.
  * Put Back was `xfce4-terminal --hold -e trash-restore`, which opens a
    Linux terminal from a file-manager menu and then asks the user to pick
    a number. trash-restore has no non-interactive form — verified: even
    `trash-restore <path>` prints a numbered menu and blocks on stdin —
    and %f inside the Trash folder is a trash:// URI it cannot consume.

Everything below runs against a throwaway XDG_DATA_HOME under a temp dir.
No real Trash is read or erased.

Usage: python3 scripts/test-mv-trash-surface.py
Exit 0 = all tests passed."""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts", "gui-guard"))
import mv_gui_iso

mv_gui_iso.arm_guard()

BIN = os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps/bin")
EMPTY = os.path.join(BIN, "mv-empty-trash")
PUTBACK = os.path.join(BIN, "mv-trash-putback")
TRASH = os.path.join(BIN, "mv-trash")
MAKEFILE = os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps/Makefile")
UCA = os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps/config/thunar-uca.xml")
UCA_SKEL = os.path.join(REPO, "archiso-profile/releng/airootfs/etc/skel/.config/Thunar/uca.xml")
KB = os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps/config/xfce4-keyboard-shortcuts.xml")
KB_SKEL = os.path.join(REPO, "archiso-profile/releng/airootfs/etc/skel/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-keyboard-shortcuts.xml")
KEYBOARD_DOC = os.path.join(REPO, "docs/KEYBOARD.md")

FAILURES = []
PASSED = 0


def ok(name):
    global PASSED
    PASSED += 1
    print("ok - %s" % name)


def bad(name, detail=""):
    FAILURES.append((name, detail))
    print("FAIL - %s %s" % (name, detail))


def check(name, cond, detail=""):
    ok(name) if cond else bad(name, detail)


def load(path, name):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)
    with open(path, encoding="utf-8") as fh:
        src = fh.read().replace('if __name__ == "__main__":\n    sys.exit(main())', "")
    exec(compile(src, path, "exec"), mod.__dict__)
    return mod


def make_trash(root, files):
    """Build a freedesktop trash store by hand (no trash-cli needed)."""
    files_dir = os.path.join(root, "files")
    info_dir = os.path.join(root, "info")
    os.makedirs(files_dir, exist_ok=True)
    os.makedirs(info_dir, exist_ok=True)
    made = []
    for name, (orig, payload) in files.items():
        target = os.path.join(files_dir, name)
        if payload is None:
            os.makedirs(target, exist_ok=True)
            with open(os.path.join(target, "inner.txt"), "w") as fh:
                fh.write("inner")
        else:
            with open(target, "w") as fh:
                fh.write(payload)
        with open(os.path.join(info_dir, name + ".trashinfo"), "w") as fh:
            fh.write("[Trash Info]\n")
            fh.write("Path=%s\n" % orig)
            fh.write("DeletionDate=2026-10-06T08:00:00\n")
        made.append(name)
    return made


# ---------------------------------------------------------------------------
# mv-empty-trash
# ---------------------------------------------------------------------------

def test_empty_discovery(m):
    root = tempfile.mkdtemp(prefix="mvtrash-")
    home = os.path.join(root, "home")
    data = os.path.join(root, "data")
    os.makedirs(home)
    os.makedirs(data)
    env = {"HOME": home, "XDG_DATA_HOME": data}
    store = os.path.join(data, "Trash")
    make_trash(store, {
        "one.txt": ("/orig/one.txt", "hello"),
        "two.txt": ("/orig/two.txt", "world!"),
        "adir": ("/orig/adir", None),
    })
    items = m.list_trash_items(home=home, environ=env)
    check("empty: finds every entry", len(items) == 3, str(len(items)))
    by_name = {i["name"]: i for i in items}
    check("empty: reads Path= back", by_name["one.txt"]["original_path"] == "/orig/one.txt")
    check("empty: reads DeletionDate", by_name["one.txt"]["deletion_date"]
          == "2026-10-06T08:00:00")
    check("empty: directories are flagged", by_name["adir"]["is_dir"] is True)
    check("empty: file size counted",
          by_name["two.txt"]["size"] == len("world!"),
          str(by_name["two.txt"]["size"]))
    check("empty: directory size is recursive",
          by_name["adir"]["size"] == len("inner") + os.lstat(
              os.path.join(by_name["adir"]["trash_path"])).st_size)
    count_text, _ = m.summarize(items)
    check("empty: summary is plural and sized",
          count_text.startswith("3 items, ") and "bytes" in count_text, count_text)
    check("empty: XDG_DATA_HOME wins over the HOME fallback",
          m.trash_dirs(home=home, environ=env)[0] == store)
    check("empty: HOME fallback still offered",
          os.path.join(home, ".local", "share", "Trash") in
          m.trash_dirs(home=home, environ=env))
    shutil.rmtree(root, ignore_errors=True)


def test_empty_sizes(m):
    check("size: bytes", m.format_size(512) == "512 bytes", m.format_size(512))
    check("size: kilobytes", m.format_size(2048) == "2.0 KB", m.format_size(2048))
    check("size: megabytes", m.format_size(5 * 1024 * 1024) == "5.0 MB")
    check("size: gigabytes", m.format_size(3 * 1024 ** 3) == "3.0 GB")
    check("size: singular item wording",
          m.summarize([{"name": "x", "size": 1}] * 1)[0].startswith("1 item,"))


def test_empty_confirm_contract(m):
    check("confirm: asks in Finder's words",
          m.CANCEL_MESSAGE == ("Are you sure you want to permanently erase "
                               "the items in the Trash?"), m.CANCEL_MESSAGE)
    check("confirm: warns it cannot be undone",
          m.CANCEL_SECONDARY == "You can't undo this action.", m.CANCEL_SECONDARY)
    check("confirm: destructive button says Empty Trash",
          m.EMPTY_LABEL == "Empty Trash")
    check("confirm: --yes is the only non-interactive consent",
          m.confirm("1 item", assume_yes=True) is True)
    check("confirm: --no refuses without a prompt",
          m.confirm("1 item", assume_no=True) is False)
    # Without a display there must be no stdin prompt at all: a keystroke
    # must never leave the user waiting on an invisible terminal.
    saved = {k: os.environ.get(k) for k in ("DISPLAY", "WAYLAND_DISPLAY")}
    for k in saved:
        os.environ.pop(k, None)
    old_argv = sys.argv
    sys.argv = [EMPTY]
    try:
        rc = m.confirm("1 item, 5 bytes")
    finally:
        sys.argv = old_argv
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    check("confirm: no usable display means refuse, never prompt",
          rc is False, "returned %r" % (rc,))
    src = open(EMPTY, encoding="utf-8").read()
    check("confirm: no input() anywhere in the source", "input(" not in src)
    check("confirm: no stdin read in executable code", "sys.stdin" not in src)


def test_empty_erase(m):
    root = tempfile.mkdtemp(prefix="mvtrash-")
    home = os.path.join(root, "home")
    data = os.path.join(root, "data")
    os.makedirs(home)
    store = os.path.join(data, "Trash")
    env = {"HOME": home, "XDG_DATA_HOME": data}
    make_trash(store, {"a.txt": ("/orig/a.txt", "aaa"),
                       "b.txt": ("/orig/b.txt", "bbb")})
    old = {k: os.environ.get(k) for k in ("HOME", "XDG_DATA_HOME")}
    os.environ.update(env)
    try:
        rc, message = m.erase(m.list_trash_items())
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    check("erase: falls back to direct unlink when trash-cli cannot see the store",
          rc == 0, message)
    check("erase: files/ is empty afterwards",
          os.listdir(os.path.join(store, "files")) == [])
    check("erase: info/ is cleaned up too",
          os.listdir(os.path.join(store, "info")) == [])
    shutil.rmtree(root, ignore_errors=True)


def test_empty_cli():
    root = tempfile.mkdtemp(prefix="mvtrash-")
    home = os.path.join(root, "home")
    data = os.path.join(root, "data")
    os.makedirs(home)
    store = os.path.join(data, "Trash")
    env = dict(os.environ, HOME=home, XDG_DATA_HOME=data, MV_TRASH_QUIET="1")
    make_trash(store, {"a.txt": ("/orig/a.txt", "aaa"),
                       "b.txt": ("/orig/b.txt", "bbbb")})

    def run(args, **extra):
        return subprocess.run([sys.executable, EMPTY] + args,
                              capture_output=True, text=True, timeout=60,
                              env=dict(env, **extra), stdin=subprocess.DEVNULL)

    r = run(["--status"])
    check("cli: --status reports 2 items", r.stdout.startswith("2 items,"), r.stdout)
    r = run(["--list"])
    check("cli: --list shows original paths",
          "a.txt  <-  /orig/a.txt" in r.stdout, r.stdout)
    r = run(["--no"])
    check("cli: --no prints the alert without erasing",
          "permanently erase" in r.stdout and "can't undo" in r.stdout, r.stdout)
    check("cli: --no left the Trash intact",
          len(os.listdir(os.path.join(store, "files"))) == 2)

# No display: must refuse fast and keep everything. DISPLAY is stripped
    # from the child env explicitly — check-sync exports DISPLAY=:97, and
    # inheriting it opened a real modal that blocked for the full timeout.
    child_env = dict(env)
    child_env.pop("DISPLAY", None)
    child_env.pop("WAYLAND_DISPLAY", None)
    import time
    t0 = time.time()
    r = subprocess.run([sys.executable, EMPTY], capture_output=True, text=True,
                       timeout=30, env=child_env, stdin=subprocess.DEVNULL,
                       cwd=root)
    elapsed = time.time() - t0
    check("cli: refuses without a display", r.returncode == 0
          and "nothing was erased" in (r.stdout + r.stderr),
          r.stdout + r.stderr)
    check("cli: refuses quickly instead of hanging", elapsed < 10,
          "%.1fs" % elapsed)
    check("cli: Trash survived the refusal",
          len(os.listdir(os.path.join(store, "files"))) == 2)

    r = run(["--yes"])
    check("cli: --yes erases", r.returncode == 0, r.stdout + r.stderr)
    check("cli: Trash is empty after --yes",
          os.listdir(os.path.join(store, "files")) == [])

    r = run(["--yes"])
    check("cli: idempotent on an empty Trash", r.returncode == 0,
          r.stdout + r.stderr)
    shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------------------
# mv-trash-putback
# ---------------------------------------------------------------------------

def test_putback_uris(m):
    check("uri: trash:///files/report.pdf",
          m.item_name_from_argument("trash:///files/report.pdf") == "report.pdf")
    check("uri: trash:///info/report.pdf.trashinfo",
          m.item_name_from_argument("trash:///info/report.pdf.trashinfo")
          == "report.pdf")
    check("uri: with a location query",
          m.item_name_from_argument("trash:///files/x.tar.gz?location=home")
          == "x.tar.gz")
    check("path: trash files/ path",
          m.item_name_from_argument("/h/.local/share/Trash/files/x.txt") == "x.txt")
    check("path: trashinfo path",
          m.item_name_from_argument("/h/.local/share/Trash/info/x.txt.trashinfo")
          == "x.txt")


def test_putback_plan(m):
    root = tempfile.mkdtemp(prefix="mvpb-")
    home = os.path.join(root, "home")
    data = os.path.join(root, "data")
    os.makedirs(home)
    store = os.path.join(data, "Trash")
    make_trash(store, {"report.pdf": ("/work/deep/report.pdf", "%PDF-1.4")})
    env = {"HOME": home, "XDG_DATA_HOME": data}

    for spelling in ("trash:///files/report.pdf",
                     os.path.join(store, "files", "report.pdf"),
                     os.path.join(store, "info", "report.pdf.trashinfo"),
                     "/work/deep/report.pdf"):
        okp, payload = m.plan_putback(spelling, home=home, environ=env)
        check("putback: resolves %s" % spelling.split("/")[-1],
              okp and payload["target_path"] == "/work/deep/report.pdf",
              str(payload))

    okp, payload = m.plan_putback("trash:///files/absent.pdf", home=home, environ=env)
    check("putback: unknown item is an honest error",
          not okp and "no trashed item" in payload, str(payload))
    shutil.rmtree(root, ignore_errors=True)


def test_putback_restore(m):
    root = tempfile.mkdtemp(prefix="mvpb-")
    home = os.path.join(root, "home")
    data = os.path.join(root, "data")
    work = os.path.join(root, "work")
    os.makedirs(home)
    os.makedirs(work)
    store = os.path.join(data, "Trash")
    # Trash an item, then delete the folders it lived in: Finder's Put Back
    # recreates the path, so mv-trash-putback must too.
    deep_dir = os.path.join(work, "deep", "er")
    os.makedirs(deep_dir)
    original = os.path.join(deep_dir, "note.txt")
    with open(original, "w") as fh:
        fh.write("payload")
    make_trash(store, {"note.txt": (original, "payload")})
    shutil.rmtree(os.path.join(work, "deep"))
    okp, _ = m.plan_putback("trash:///files/note.txt", home=home,
                            environ={"HOME": home, "XDG_DATA_HOME": data})
    check("putback: plans a restore into a directory that no longer exists", okp)
    rc, message = m.putback("trash:///files/note.txt", home=home,
                            environ={"HOME": home, "XDG_DATA_HOME": data})
    check("putback: recreates the missing parent and restores", rc == 0, message)
    check("putback: file is back where it came from",
          os.path.isfile(original) and open(original).read() == "payload")
    check("putback: trash payload is gone",
          os.listdir(os.path.join(store, "files")) == [])
    shutil.rmtree(root, ignore_errors=True)


def test_putback_collision(m):
    check("putback: free path is used as-is",
          m.unique_target("/w/a.txt") == "/w/a.txt")
    d = tempfile.mkdtemp(prefix="mvpb-collide-")
    try:
        first = os.path.join(d, "a.txt")
        with open(first, "w") as fh:
            fh.write("x")
        second = m.unique_target(first)
        check("putback: first collision becomes '<stem> copy<ext>'",
              second.endswith("a copy.txt"), second)
        with open(second, "w") as fh:
            fh.write("y")
        third = m.unique_target(first)
        check("putback: second collision is numbered", third.endswith("a copy 2.txt"),
              third)
        with open(third, "w") as fh:
            fh.write("z")
        fourth = m.unique_target(first)
        check("putback: third collision is numbered again",
              fourth.endswith("a copy 3.txt"), fourth)
        check("putback: every copy is distinct",
              len({first, second, third, fourth}) == 4)
        check("putback: the originals are all still on disk",
              all(os.path.isfile(p) for p in (first, second, third)))
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_putback_cli():
    root = tempfile.mkdtemp(prefix="mvpb-")
    home = os.path.join(root, "home")
    data = os.path.join(root, "data")
    work = os.path.join(root, "work")
    os.makedirs(home)
    os.makedirs(work)
    store = os.path.join(data, "Trash")
    orig = os.path.join(work, "notes.txt")
    with open(orig, "w") as fh:
        fh.write("original")
    make_trash(store, {"notes.txt": (orig, "original")})
    env = dict(os.environ, HOME=home, XDG_DATA_HOME=data, MV_TRASH_QUIET="1")

    def run(args):
        return subprocess.run([sys.executable, PUTBACK] + args,
                              capture_output=True, text=True, timeout=60,
                              env=env, stdin=subprocess.DEVNULL)

    r = run(["--list"])
    check("cli: --list shows the original path",
          "notes.txt  <-  %s" % orig in r.stdout, r.stdout)
    r = run(["--status", "trash:///files/notes.txt"])
    check("cli: --status from a trash:// URI", "->  %s" % orig in r.stdout, r.stdout)
    r = run(["trash:///files/notes.txt"])
    check("cli: restores", r.returncode == 0 and "Put back notes.txt" in r.stdout,
          r.stdout + r.stderr)
    check("cli: file is back at its original path",
          os.path.isfile(orig) and open(orig).read() == "original")
    check("cli: info/ entry removed",
          os.listdir(os.path.join(store, "info")) == [])
    r = run(["trash:///files/gone.txt"])
    check("cli: unknown item exits 1 with a reason",
          r.returncode == 1 and "no trashed item" in r.stderr, r.stderr)
    shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------

def test_packaging():
    mk = open(MAKEFILE, encoding="utf-8").read()
    check("packaging: Makefile installs mv-empty-trash", "bin/mv-empty-trash" in mk)
    check("packaging: Makefile installs mv-trash-putback",
          "bin/mv-trash-putback" in mk)
    uca = open(UCA, encoding="utf-8").read()
    check("wiring: Put Back uses mv-trash-putback",
          '<command>mv-trash-putback "%f"</command>' in uca)
    check("wiring: Put Back no longer opens a terminal",
          "xfce4-terminal" not in uca.split("<unique-id>mv-putback</unique-id>")[1]
          .split("</action>")[0])
    check("wiring: Put Back carries Finder's name",
          "<name>Put Back</name>" in uca)
    check("wiring: Empty Trash uses mv-empty-trash",
          "<command>mv-empty-trash</command>" in uca)
    check("wiring: Empty Trash signals it asks",
          "<name>Empty Trash…</name>" in uca)
    check("wiring: raw trash-empty is no longer reachable from the menu",
          "<command>trash-empty</command>" not in uca)
    check("wiring: no raw trash-restore anywhere in the menu",
          "trash-restore" not in uca)
    check("wiring: Move to Trash still uses mv-trash",
          "<command>mv-trash %F</command>" in uca)
    check("wiring: uca mirrors are identical",
          open(UCA, "rb").read() == open(UCA_SKEL, "rb").read())
    for path, label in ((KB, "package"), (KB_SKEL, "airootfs skel")):
        text = open(path, encoding="utf-8").read()
        check("wiring: Super+Shift+Delete → mv-empty-trash (%s)" % label,
              'name="&lt;Super&gt;&lt;Shift&gt;Delete" type="string" '
              'value="mv-empty-trash"' in text)
        check("wiring: Super+Shift+E → mv-empty-trash (%s)" % label,
              'name="&lt;Super&gt;&lt;Shift&gt;e" type="string" '
              'value="mv-empty-trash"' in text)
        check("wiring: raw trash-empty not bound any more (%s)" % label,
              'value="trash-empty"' not in text)
        check("wiring: Super+Delete still moves to Trash (%s)" % label,
              'name="&lt;Super&gt;Delete" type="string" value="mv-trash"' in text)
    doc = open(KEYBOARD_DOC, encoding="utf-8").read()
    check("docs: KEYBOARD.md names mv-empty-trash", "mv-empty-trash" in doc)
    check("docs: KEYBOARD.md says it asks first", "asks first" in doc)
    check("scripts: mv-trash itself is unchanged and still trash-put based",
          "trash-put" in open(TRASH, encoding="utf-8").read())
    check("scripts: trash-cli stays an ISO dependency for Move to Trash",
          "trash-put" in open(TRASH, encoding="utf-8").read())


def main():
    print("=== mv-empty-trash / mv-trash-putback ===")
    empty = load(EMPTY, "mv_empty_trash")
    putback = load(PUTBACK, "mv_trash_putback")
    test_empty_discovery(empty)
    test_empty_sizes(empty)
    test_empty_confirm_contract(empty)
    test_empty_erase(empty)
    test_empty_cli()
    test_putback_uris(putback)
    test_putback_plan(putback)
    test_putback_restore(putback)
    test_putback_collision(putback)
    test_putback_cli()
    test_packaging()
    print("\n%d passed, %d failed" % (PASSED, len(FAILURES)))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())