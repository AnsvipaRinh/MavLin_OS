#!/usr/bin/env python3
"""Headless tests for mv-archive-utility (canonical #16 Archive Utility).

The canonical surface used to be a bare alias:

    mv-archive-utility.desktop:  Exec=xarchiver %U
                                 X-Mavericks-Alias-For=xarchiver

so these tests start from what was measurably missing rather than from
what exists:

  * no expansion path at all — thunar-uca.xml had "Compress" and nothing
    for the other direction, and the desktop file carried no MimeType;
  * no macOS "Expand" semantics — macOS 10.9 expands 'demo.tar.gz' into a
    folder 'demo' (the whole chain of extensions is stripped, not just the
    last) and opens it;
  * no failure surface — macOS shows "The archive couldn't be expanded
    because …" with Try Again / Cancel.

Everything runs in a temp dir. bsdtar(1) does the real work; when it is
absent the backend-dependent checks skip rather than lie.

Usage: python3 scripts/test-mv-archive-utility.py
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
TOOL = os.path.join(BIN, "mv-archive-utility")
DESKTOP = os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps/desktop/mv-archive-utility.desktop")
MAKEFILE = os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps/Makefile")
UCA = os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps/config/thunar-uca.xml")
UCA_SKEL = os.path.join(REPO, "archiso-profile/releng/airootfs/etc/skel/.config/Thunar/uca.xml")
PKGS = os.path.join(REPO, "archiso-profile/releng/packages.x86_64")
DESKTOP_DIR = os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps/desktop")

FAILURES = []
PASSED = 0
HAVE_BSDTAR = bool(shutil.which("bsdtar"))


def ok(name):
    global PASSED
    PASSED += 1
    print("ok - %s" % name)


def bad(name, detail=""):
    FAILURES.append((name, detail))
    print("FAIL - %s %s" % (name, detail))


def check(name, cond, detail=""):
    ok(name) if cond else bad(name, detail)


def skip(name):
    print("skip - %s (no bsdtar)" % name)


def load():
    spec = importlib.util.spec_from_loader("mv_archive", loader=None)
    mod = importlib.util.module_from_spec(spec)
    with open(TOOL, encoding="utf-8") as fh:
        src = fh.read().replace('if __name__ == "__main__":\n    sys.exit(main())', "")
    exec(compile(src, TOOL, "exec"), mod.__dict__)
    return mod


def make_archives(d):
    """Real archives of several formats, via bsdtar when available."""
    src = os.path.join(d, "src")
    os.makedirs(os.path.join(src, "sub"), exist_ok=True)
    with open(os.path.join(src, "a.txt"), "w") as fh:
        fh.write("one")
    with open(os.path.join(src, "sub", "b.txt"), "w") as fh:
        fh.write("two")
    made = {}
    if HAVE_BSDTAR:
        for name, fmt in (("demo.zip", "zip"), ("demo.tar.gz", "tar+zst" if False else "tar")):
            pass
        # zip
        subprocess.run(["bsdtar", "-a", "-cf", os.path.join(d, "demo.zip"), "a.txt",
                        "sub"], cwd=src, check=True)
        made["demo.zip"] = ["a.txt", "sub/b.txt"]
        # .tar.gz
        subprocess.run(["bsdtar", "-czf", os.path.join(d, "demo.tar.gz"), "a.txt",
                        "sub"], cwd=src, check=True)
        made["demo.tar.gz"] = ["a.txt", "sub/b.txt"]
        # .7z when the tool is there
        if shutil.which("7z"):
            subprocess.run(["7z", "a", os.path.join(d, "demo.7z"), "a.txt", "sub"],
                           cwd=src, check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            made["demo.7z"] = ["a.txt", "sub/b.txt"]
        # a folder to compress
        subprocess.run(["bsdtar", "-a", "-cf", os.path.join(d, "bundle.zip"), "src"],
                       cwd=d, check=True)
        made["bundle.zip"] = ["src/a.txt", "src/sub/b.txt"]
    return made


def test_naming(m):
    # The first version kept '.zip' in the folder name, so the computed
    # destination collided with the archive file and every plain .zip
    # failed with "demo.zip already exists".
    check("naming: demo.zip -> demo", m.expand_target_name("demo.zip") == "demo",
          m.expand_target_name("demo.zip"))
    check("naming: demo.tar.gz -> demo",
          m.expand_target_name("demo.tar.gz") == "demo",
          m.expand_target_name("demo.tar.gz"))
    check("naming: demo.tar.xz -> demo",
          m.expand_target_name("demo.tar.xz") == "demo")
    check("naming: Screenshot 2026-10-06.zip -> Screenshot 2026-10-06",
          m.expand_target_name("Screenshot 2026-10-06.zip")
          == "Screenshot 2026-10-06")
    check("naming: unknown suffix still drops one extension",
          m.expand_target_name("weird.qqq") == "weird")
    check("naming: a bare name survives",
          m.expand_target_name("plainfile") == "plainfile")
    check("naming: full path is reduced to a basename",
          m.expand_target_name("/a/b/demo.tar.gz") == "demo")


def test_kinds(m):
    for suffix in (".zip", ".tar.gz", ".tgz", ".tar.xz", ".7z", ".rar", ".cbr",
                   ".cpio", ".lha", ".iso"):
        check("kind: %s recognised" % suffix,
              m.archive_kind("x" + suffix) == suffix,
              m.archive_kind("x" + suffix))
    check("kind: long suffixes beat short ones",
          m.archive_kind("x.tar.gz") == ".tar.gz")
    check("kind: uppercase tolerated", m.archive_kind("X.ZIP") == ".zip")
    check("kind: a non-archive is not classified",
          m.archive_kind("notes.txt") == "")


def test_folder_collision(m):
    d = tempfile.mkdtemp(prefix="mvarch-collide-")
    try:
        target = m.folder_name_for(os.path.join(d, "demo.zip"), d)
        check("collision: first expansion uses the bare name",
              os.path.basename(target) == "demo", target)
        os.makedirs(os.path.join(d, "demo"))
        target2 = m.folder_name_for(os.path.join(d, "demo.zip"), d)
        check("collision: second becomes 'demo 2'",
              os.path.basename(target2) == "demo 2", target2)
        os.makedirs(os.path.join(d, "demo 2"))
        target3 = m.folder_name_for(os.path.join(d, "demo.zip"), d)
        check("collision: third becomes 'demo 3'",
              os.path.basename(target3) == "demo 3", target3)
        # A .tar.gz whose folder name collides with an existing 'demo' must
        # land on 'demo 2' too, not on a name derived from the archive.
        target4 = m.folder_name_for(os.path.join(d, "demo.tar.gz"), d)
        check("collision: the name comes from the archive, not the folder",
              os.path.basename(target4) == "demo 3", target4)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_backend(m):
    if not HAVE_BSDTAR:
        skip("backend: bsdtar discovery")
        return
    check("backend: bsdtar found", bool(m.find_bsdtar()))
    original = m.find_bsdtar
    m.find_bsdtar = lambda: (_ for _ in ()).throw(
        m.ArchiveError("bsdtar (libarchive) is not installed"))
    try:
        m.expand("/w/x.zip", "/w/x")
        bad("backend: missing bsdtar is a clean ArchiveError")
    except m.ArchiveError as exc:
        check("backend: missing bsdtar is a clean ArchiveError",
              "libarchive" in str(exc))
    m.find_bsdtar = original


def test_reason(m):
    check("reason: stderr's last line is used",
          m.reason_from(stderr="x\nError: bad archive\n") == "Error: bad archive")
    check("reason: stdout used when stderr is empty",
          m.reason_from(stderr="", stderr_alt="stdout problem") == "stdout problem")
    check("reason: never returns empty",
          m.reason_from(stderr="", stderr_alt=None) == "the archive could not be read")


def test_expand_roundtrip(m, made, srcdir):
    if not made:
        skip("expand: round trips (no bsdtar)")
        return
    for archive, expected in made.items():
        d = tempfile.mkdtemp(prefix="mvarch-")
        try:
            src = os.path.join(d, archive)
            shutil.copy(os.path.join(srcdir, archive), src)
            dest = m.folder_name_for(src, d)
            m.expand(src, dest)
            got = sorted(
                os.path.relpath(os.path.join(root, f), dest)
                for root, _dirs, files in os.walk(dest) for f in files)
            check("expand: %s -> folder %s" % (archive, os.path.basename(dest)),
                  got == sorted(expected), str(got))
        except m.ArchiveError as exc:
            bad("expand: %s" % archive, str(exc))
        finally:
            shutil.rmtree(d, ignore_errors=True)


def test_expand_failures(m):
    d = tempfile.mkdtemp(prefix="mvarch-")
    try:
        bad_archive = os.path.join(d, "bad.zip")
        with open(bad_archive, "w") as fh:
            fh.write("this is definitely not an archive")
        dest = os.path.join(d, "bad")
        try:
            m.expand(bad_archive, dest)
            bad("failure: corrupt archive raises")
        except m.ArchiveError as exc:
            check("failure: corrupt archive raises with a reason",
                  "could not" in str(exc) or "Error" in str(exc), str(exc))
        check("failure: no half-extracted folder is left behind",
              not os.path.exists(dest))
        try:
            m.expand(os.path.join(d, "absent.zip"), os.path.join(d, "absent"))
            bad("failure: missing archive raises")
        except m.ArchiveError as exc:
            check("failure: missing archive says so",
                  "no longer exists" in str(exc), str(exc))
        try:
            m.expand(d, os.path.join(d, "adir"))
            bad("failure: a directory is not an archive")
        except m.ArchiveError as exc:
            check("failure: a directory is refused", "not a file" in str(exc))
        # existing destination
        existing = os.path.join(d, "taken")
        os.makedirs(existing)
        if HAVE_BSDTAR:
            src = os.path.join(d, "ok.zip")
            subprocess.run(["bsdtar", "-a", "-cf", src, "bad.zip"], cwd=d, check=True)
            try:
                m.expand(src, existing)
                bad("failure: existing destination is refused")
            except m.ArchiveError as exc:
                check("failure: existing destination is refused",
                      "already exists" in str(exc), str(exc))
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_expand_here(m):
    if not HAVE_BSDTAR:
        skip("here: Extract Here merges into the current folder")
        return
    d = tempfile.mkdtemp(prefix="mvarch-")
    try:
        src = os.path.join(d, "payload")
        os.makedirs(src)
        with open(os.path.join(src, "keep.txt"), "w") as fh:
            fh.write("keep")
        subprocess.run(["bsdtar", "-a", "-cf", os.path.join(d, "here.zip"), "keep.txt"],
                       cwd=src, check=True)
        m.expand(os.path.join(d, "here.zip"), src, create=False)
        check("here: Extract Here writes into the existing folder",
              os.path.isfile(os.path.join(src, "keep.txt")))
    except m.ArchiveError as exc:
        bad("here: Extract Here", str(exc))
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_compress(m, made):
    if not made:
        skip("compress: --new")
        return
    d = tempfile.mkdtemp(prefix="mvarch-")
    cwd = os.getcwd()
    try:
        src = os.path.join(d, "src")
        os.makedirs(src)
        with open(os.path.join(src, "z.txt"), "w") as fh:
            fh.write("z")
        # compress() resolves relative sources against the process CWD, which
        # is what the CLI contract promises; run from the temp dir.
        os.chdir(d)
        out = os.path.join(d, "fresh.zip")
        m.compress(out, ["src"])
        listing = subprocess.run([shutil.which("bsdtar"), "-tf", out],
                                 capture_output=True, text=True, check=True).stdout
        check("compress: the top-level name is kept like Finder's",
              "src/z.txt" in listing, listing)
        try:
            m.compress(os.path.join(d, "x.tar"), ["src"])
            bad("compress: non-zip target is refused")
        except m.ArchiveError as exc:
            check("compress: non-zip target is refused", "zip" in str(exc))
        try:
            m.compress(os.path.join(d, "nodir", "y.zip"), ["src"])
            bad("compress: missing output directory is refused")
        except m.ArchiveError as exc:
            check("compress: missing output directory is refused",
                  "does not exist" in str(exc))
    except m.ArchiveError as exc:
        bad("compress", str(exc))
    finally:
        os.chdir(cwd)
        shutil.rmtree(d, ignore_errors=True)


def test_cli(m, made, srcdir):
    d = tempfile.mkdtemp(prefix="mvarch-")
    try:
        for archive in made:
            if archive == "bundle.zip":
                continue
            shutil.copy(os.path.join(srcdir, archive), os.path.join(d, archive))
        env = dict(os.environ, MV_ARCHIVE_QUIET="1")
        if HAVE_BSDTAR:
            r = subprocess.run([sys.executable, TOOL, "--quiet", "--no-open",
                                os.path.join(d, "demo.zip")],
                               capture_output=True, text=True, timeout=120, env=env,
                               stdin=subprocess.DEVNULL)
            check("cli: expansion succeeds", r.returncode == 0, r.stderr)
            check("cli: folder named 'demo' appears",
                  os.path.isfile(os.path.join(d, "demo", "a.txt")))
            r = subprocess.run([sys.executable, TOOL, "--quiet", "--no-open",
                                "--here", os.path.join(d, "demo.tar.gz")],
                               capture_output=True, text=True, timeout=120, env=env,
                               stdin=subprocess.DEVNULL)
            check("cli: --here merges in place",
                  r.returncode == 0 and os.path.isfile(os.path.join(d, "a.txt")),
                  r.stderr)
        r = subprocess.run([sys.executable, TOOL, "--list",
                            os.path.join(d, "demo.tar.gz")],
                           capture_output=True, text=True, timeout=120, env=env,
                           stdin=subprocess.DEVNULL)
        if HAVE_BSDTAR:
            check("cli: --list prints the archive contents",
                  "a.txt" in r.stdout and "sub/b.txt" in r.stdout, r.stdout)
        r = subprocess.run([sys.executable, TOOL, "--quiet", "--no-open",
                            os.path.join(d, "missing.zip")],
                           capture_output=True, text=True, timeout=120, env=env,
                           stdin=subprocess.DEVNULL)
        check("cli: missing archive exits 1 with a reason",
              r.returncode == 1 and "no longer exists" in r.stderr, r.stderr)
        r = subprocess.run([sys.executable, TOOL, "--list"],
                           capture_output=True, text=True, timeout=120, env=env,
                           stdin=subprocess.DEVNULL)
        check("cli: --list without an argument is a usage error",
              r.returncode == 1, r.stdout)
        r = subprocess.run([sys.executable, TOOL, "--new"],
                           capture_output=True, text=True, timeout=120, env=env,
                           stdin=subprocess.DEVNULL)
        check("cli: --new without files is a usage error",
              r.returncode != 0, "rc=%d" % r.returncode)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_notification_bounded():
    src = open(TOOL, encoding="utf-8").read()
    check("notification: notify-send is given a timeout",
          "timeout=2" in src, "notify-send can block ~5s with no daemon")
    check("notification: notify-send gets DEVNULL stdin",
          "stdin=subprocess.DEVNULL" in src)


def test_desktop_and_wiring(m):
    text = open(DESKTOP, encoding="utf-8").read()
    check("desktop: still a launchable .desktop", text.startswith("[Desktop Entry]"))
    check("desktop: carries the Mavericks name",
          "\nName=Archive Utility\n" in text)
    check("desktop: Exec goes through mv-archive-utility",
          "Exec=mv-archive-utility %U" in text)
    check("desktop: has a MimeType list (was missing entirely)",
          "\nMimeType=" in text)
    for mime in ("application/zip", "application/x-tar",
                 "application/x-compressed-tar", "application/gzip",
                 "application/x-bzip2", "application/x-xz", "application/x-7z-compressed",
                 "application/x-rar", "application/epub+zip"):
        check("desktop: advertises %s" % mime, mime in text)
    # The desktop file and the tool's own constant must not drift apart.
    line = [l for l in text.splitlines() if l.startswith("MimeType=")][0]
    declared = tuple(x for x in line.split("=", 1)[1].split(";") if x)
    check("desktop: MimeType matches mv-archive-utility's own list exactly",
          declared == m.DESKTOP_MIME_TYPES,
          "desktop has %d types, tool declares %d"
          % (len(declared), len(m.DESKTOP_MIME_TYPES)))
    check("desktop: still records the xarchiver alias honestly",
          "X-Mavericks-Alias-For=xarchiver" in text)
    check("desktop: desktop-file validation passes",
          subprocess.run(["desktop-file-validate", DESKTOP],
                         capture_output=True, text=True).returncode == 0)

    uca = open(UCA, encoding="utf-8").read()
    check("wiring: Extract Here action exists",
          "<name>Extract Here</name>" in uca)
    check("wiring: Extract Here calls mv-archive-utility --here",
          'mv-archive-utility --here --no-open "%f"' in uca)
    check("wiring: Expand action exists", "<name>Expand</name>" in uca)
    check("wiring: Expand calls mv-archive-utility",
          '<command>mv-archive-utility "%f"</command>' in uca)
    check("wiring: Compress no longer opens xarchiver's dialog",
          "xarchiver -a" not in uca)
    check("wiring: Compress uses the Mavericks helper",
          'mv-archive-utility --new "%d/%n.zip"' in uca)
    check("wiring: xarchiver is still only the browsing editor",
          uca.count("xarchiver") == 0)
    for action_id in ("mv-extract-here", "mv-expand-archive"):
        block = uca.split("<unique-id>%s</unique-id>" % action_id)[1].split("</action>")[0]
        check("wiring: %s only shows for archive patterns" % action_id,
              "<patterns>*.zip;" in block and ".7z" in block
              and not block.rstrip().endswith("<patterns>*</patterns>"))
    check("wiring: uca mirrors are identical",
          open(UCA, "rb").read() == open(UCA_SKEL, "rb").read())
    mk = open(MAKEFILE, encoding="utf-8").read()
    check("packaging: Makefile installs mv-archive-utility",
          "bin/mv-archive-utility" in mk)
    pkgs = open(PKGS, encoding="utf-8").read()
    check("packaging: libarchive (bsdtar) is an explicit ISO dependency",
          "\nlibarchive\n" in "\n" + pkgs + "\n")
    check("packaging: xarchiver stays, as the browsing editor",
          "\nxarchiver\n" in "\n" + pkgs + "\n")
    installed = subprocess.run(
        ["make", "-n", "install", "DESTDIR=" + tempfile.mkdtemp(prefix="mvdest-"),
         "PREFIX=/usr"],
        cwd=os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps"),
        capture_output=True, text=True)
    check("packaging: Makefile install line mentions the new binary",
          "mv-archive-utility" in installed.stdout, installed.stderr)


def main():
    print("=== mv-archive-utility ===")
    m = load()
    if not HAVE_BSDTAR:
        print("skip - bsdtar(1) not installed on this host: backend checks skipped")
    test_naming(m)
    test_kinds(m)
    test_folder_collision(m)
    test_backend(m)
    test_reason(m)
    workdir = tempfile.mkdtemp(prefix="mvarch-src-")
    made = make_archives(workdir)
    test_expand_roundtrip(m, made, workdir)
    test_expand_failures(m)
    test_expand_here(m)
    test_compress(m, made)
    test_cli(m, made, workdir)
    test_notification_bounded()
    test_desktop_and_wiring(m)
    shutil.rmtree(workdir, ignore_errors=True)
    print("\n%d passed, %d failed" % (PASSED, len(FAILURES)))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())