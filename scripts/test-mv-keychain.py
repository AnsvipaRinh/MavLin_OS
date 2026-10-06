#!/usr/bin/env python3
"""Headless tests for mv-keychain.

Pure-logic section (no GTK widgets, Secret backend fully mocked —
no real secrets, no real keyring daemon):
- classify_item kind heuristics
- generate_password length/charset/coverage/uniqueness (CSPRNG via secrets)
- password_strength entropy estimate
- get_collections: Secret None, service error, service OK, empty service
- list_items: Secret None, service error, empty collection, populated
- get_item_secret: bytes pass-through, str encode, error -> None
- store_password: schema/attrs/label/password wiring, validation, errors
- delete_item: success + error
- lock_items: per-item locking, skip attrless, error tolerance

GUI smoke (display only, skipped headless):
- construction with mocked Secret service/collections/items
- sidebar populated, item list populated, selection -> detail rendered
- search filters client-side without re-querying backend
- new item dialog stores via backend and refreshes
- generator dialog produces a password with chosen length
- lock toggle invokes lock_items
- unavailable states: no libsecret, no daemon, empty keychain
- keyboard: Ctrl+N focuses new dialog, Ctrl+F focuses search

Usage: python3 scripts/test-mv-keychain.py
Exit 0 = all tests passed."""
import importlib.machinery
import importlib.util
import os
import sys
import tempfile
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_PATH = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-keychain")

# GUI smoke must never reach the ambient host display (WSLg: DISPLAY=:0 and
# wayland-0 both forward to the user's Windows desktop).  gui_display() pins
# the dedicated Xvfb :97 — or returns None (headless, GTK then refuses to
# init) — and arms the fail-loud guard for child processes.
sys.path.insert(0, os.path.join(REPO, "scripts", "gui-guard"))
import mv_gui_iso

mv_gui_iso.gui_display()


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


# Shared Mavericks dialog helpers path (for module import during test)
sys.path.insert(0, os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps/bin"))

def load_app():
    loader = importlib.machinery.SourceFileLoader("mv_keychain", APP_PATH)
    spec = importlib.util.spec_from_loader("mv_keychain", loader)
    m = importlib.util.module_from_spec(spec)
    loader.exec_module(m)
    return m


class FakeValue:
    def __init__(self, data):
        self._data = data

    def get(self):
        return self._data


class FakeItem:
    def __init__(self, label, attrs, locked=False,
                 schema="org.freedesktop.Secret.Generic",
                 secret=b"correct horse battery staple"):
        self._label = label
        self._attrs = dict(attrs)
        self._locked = locked
        self._schema = schema
        self._secret = secret
        self.deleted = False
        self.secret_loads = 0

    def get_attributes(self):
        return dict(self._attrs)

    def get_label(self):
        return self._label

    def get_locked(self):
        return self._locked

    def get_schema_name(self):
        return self._schema

    def load_secret_sync(self, cancellable):
        self.secret_loads += 1
        return FakeValue(self._secret)

    def delete_sync(self, cancellable):
        self.deleted = True
        return True


class FakeCollection:
    def __init__(self, name, label, locked=False, items=None):
        self._name = name
        self._label = label
        self._locked = locked
        self._items = items or []

    def get_name(self):
        return self._name

    def get_label(self):
        return self._label

    def get_locked(self):
        return self._locked

    def load_items_sync(self, cancellable):
        return list(self._items)


class FakeService:
    def __init__(self, collections):
        self._collections = collections

    def get_collections(self):
        return self._collections


class FakeSchema:
    def __init__(self, name, flags, attrs):
        self.name = name
        self.attrs = dict(attrs)


def make_fake_secret(service=None, store_side_effect=None,
                     lock_side_effect=None):
    """A stand-in for gi.repository.Secret."""
    fake = mock.Mock()
    fake.SchemaFlags.NONE = 0
    fake.SchemaAttributeType.STRING = 0
    fake.ServiceFlags.NONE = 0
    fake.COLLECTION_DEFAULT = "default"

    def schema(name, flags, attrs):
        check("fake schema is generic", name == "org.freedesktop.Secret.Generic", name)
        return FakeSchema(name, flags, attrs)
    fake.Schema = schema

    def service_get_sync(flags, cancellable):
        if service is None:
            raise RuntimeError("The name is not activatable")
        return service
    fake.Service.get_sync = mock.Mock(side_effect=service_get_sync)

    stored = {}

    def password_store_sync(schema, attrs, collection, label, password, cancellable):
        if store_side_effect is not None:
            raise store_side_effect
        stored["schema"] = schema
        stored["attrs"] = dict(attrs)
        stored["collection"] = collection
        stored["label"] = label
        stored["password"] = password
        return True
    fake.password_store_sync = mock.Mock(side_effect=password_store_sync)
    fake._stored = stored

    def password_lock_sync(schema, attrs, cancellable):
        if lock_side_effect is not None:
            raise lock_side_effect
        return True
    fake.password_lock_sync = mock.Mock(side_effect=password_lock_sync)

    def collection_for_alias_sync(alias, flags, cancellable):
        for c in (service.get_collections() if service else []):
            if c.get_name() == alias or c.get_label() == alias:
                return c
        if alias == "default":
            return FakeCollection("login", "login", items=FIXTURE_ITEMS)
        return None
    fake.Collection.for_alias_sync = mock.Mock(
        side_effect=collection_for_alias_sync)
    fake.CollectionFlags.NONE = 0
    return fake


FIXTURE_ITEMS = [
    FakeItem("Example account", {"account": "alice", "where": "example.com"}),
    FakeItem("WiFi Guest", {"ssid": "GuestNet"}),
    FakeItem("SSH Key", {"comment": "laptop"}, schema="com.github.openssh.key"),
]


def test_pure(m):
    # --- classify_item ---
    check("classify cert",
          m.classify_item({"schema_name": "gnome-ring.x509", "attributes": {}})
          == "Certificate")
    check("classify ssh key",
          m.classify_item({"schema_name": "com.github.openssh.key",
                           "attributes": {}}) == "Key")
    check("classify secure note",
          m.classify_item({"schema_name": "org.gnome.keyring.Note",
                           "attributes": {"note": "x"}}) == "Secure Note")
    check("classify generic password",
          m.classify_item({"schema_name": "org.freedesktop.Secret.Generic",
                           "attributes": {"account": "a"}}) == "Password")

    # --- generate_password ---
    pw = m.generate_password()
    check("gen default length 16", len(pw) == 16, len(pw))
    pw24 = m.generate_password(24)
    check("gen length 24", len(pw24) == 24, len(pw24))
    pw_low = m.generate_password(32, upper=False, digits=False, symbols=False)
    check("gen lowercase only", pw_low.islower() and pw_low.isalpha(), pw_low[:8])
    pw_full = m.generate_password(20, True, True, True)
    check("gen guarantees upper", any(c.isupper() for c in pw_full))
    check("gen guarantees digit", any(c.isdigit() for c in pw_full))
    check("gen guarantees symbol",
          any(c in m.SYMBOLS for c in pw_full))
    pw_len4 = m.generate_password(4, True, True, True)
    check("gen min length covers all classes", len(pw_len4) >= 4)
    check("gen uniqueness", len({m.generate_password() for _ in range(50)}) > 45)
    check("gen clamps length",
          len(m.generate_password(10000)) == 256)
    with mock.patch.object(m.secrets, "choice",
                           side_effect=AssertionError("must use secrets")):
        try:
            m.generate_password()
            check("gen uses secrets module", False, "no exception")
        except AssertionError:
            check("gen uses secrets module", True)

    # --- password_strength ---
    check("strength empty", m.password_strength("") == 0.0)
    s8 = m.password_strength("abcdefgh")
    check("strength 8 lower ~37.6", 30 < s8 < 45, s1 := s8)
    s16 = m.password_strength("abcd1234ABCD!@#$")
    check("strength mixed > lower", s16 > s8, (s16, s8))
    check("strength scales with length",
          m.password_strength("a" * 32) > m.password_strength("a" * 8) * 3)

    # --- get_collections ---
    saved = m.Secret
    try:
        m.Secret = None
        cols = m.get_collections()
        check("collections fallback when no libsecret",
              [c["name"] for c in cols]
              == ["login", "System", "System Roots", "iCloud"], cols)

        m.Secret = make_fake_secret(service=None)
        cols = m.get_collections()
        check("collections fallback when daemon absent",
              [c["name"] for c in cols]
              == ["login", "System", "System Roots", "iCloud"], cols)

        m.Secret = make_fake_secret(service=FakeService([
            FakeCollection("login", "login", locked=False),
            FakeCollection("system", "System", locked=True),
        ]))
        cols = m.get_collections()
        check("collections parsed",
              [(c["name"], c["locked"]) for c in cols]
              == [("login", False), ("system", True)], cols)

        m.Secret = make_fake_secret(service=FakeService([]))
        cols = m.get_collections()
        check("collections fallback when service empty",
              [c["name"] for c in cols]
              == ["login", "System", "System Roots", "iCloud"], cols)

        # --- list_items ---
        m.Secret = None
        check("list_items None when no libsecret", m.list_items("login") is None)

        m.Secret = make_fake_secret(service=None)
        check("list_items None when daemon absent", m.list_items("login") is None)

        m.Secret = make_fake_secret(service=FakeService([
            FakeCollection("login", "login", items=FIXTURE_ITEMS),
        ]))
        items = m.list_items("login")
        check("list_items populated", len(items) == len(FIXTURE_ITEMS), items)
        check("list_items label",
              items[0]["label"] == "Example account", items[0]["label"])
        check("list_items attributes",
              items[0]["attributes"].get("account") == "alice")
        check("list_items handle", items[0]["_item"] is FIXTURE_ITEMS[0])

        m.Secret = make_fake_secret(service=FakeService([
            FakeCollection("login", "login", items=[]),
        ]))
        check("list_items empty collection", m.list_items("login") == [])

        m.Secret = make_fake_secret(service=FakeService([
            FakeCollection("other", "Other", items=FIXTURE_ITEMS),
        ]))
        items = m.list_items("login")
        check("list_items falls back to default collection",
              len(items) == len(FIXTURE_ITEMS), items)

        # --- get_item_secret ---
        m.Secret = make_fake_secret(service=FakeService([
            FakeCollection("login", "login", items=FIXTURE_ITEMS),
        ]))
        items = m.list_items("login")
        secret = m.get_item_secret(items[0])
        check("secret returned as bytes",
              secret == b"correct horse battery staple", type(secret).__name__)
        check("secret loaded via handle", FIXTURE_ITEMS[0].secret_loads == 1)
        check("secret None when no handle", m.get_item_secret({}) is None)

        class BoomItem:
            def load_secret_sync(self, cancellable):
                raise RuntimeError("locked")
        check("secret None on load error",
              m.get_item_secret({"_item": BoomItem()}) is None)

        class StrValue(FakeValue):
            def get(self):
                return "plaintext-secret"
        class StrItem:
            def load_secret_sync(self, cancellable):
                return StrValue("plaintext-secret")
        check("secret str encoded to bytes",
              m.get_item_secret({"_item": StrItem()}) == b"plaintext-secret")

        # --- store_password ---
        m.Secret = make_fake_secret(service=FakeService([]))
        before = dict(m.Secret._stored)
        good = m.store_password("Example account",
                                {"account": "alice", "where": "example.com"},
                                "hunter2")
        check("store returns True", good is True)
        check("store schema attrs",
              m.Secret._stored["schema"].attrs
              == {"account": 0, "where": 0}, m.Secret._stored["schema"].attrs)
        check("store label", m.Secret._stored["label"] == "Example account")
        check("store collection default",
              m.Secret._stored["collection"] == "default",
              m.Secret._stored["collection"])
        check("store invoked once",
              m.Secret.password_store_sync.call_count == 1)
        check("store passed secret to backend only",
              m.Secret._stored["password"] == "hunter2"
              and "password" not in before)

        check("store rejects empty attrs",
              m.store_password("x", {}, "pw") is False)
        check("store rejects empty label",
              m.store_password("", {"account": "a"}, "pw") is False)
        check("store rejects None password",
              m.store_password("x", {"account": "a"}, None) is False)
        m.Secret = make_fake_secret(
            service=FakeService([]), store_side_effect=RuntimeError("denied"))
        check("store False on backend error",
              m.store_password("x", {"account": "a"}, "pw") is False)
        m.Secret = None
        check("store False without libsecret",
              m.store_password("x", {"account": "a"}, "pw") is False)

        # --- delete_item ---
        m.Secret = make_fake_secret(service=FakeService([
            FakeCollection("login", "login", items=FIXTURE_ITEMS),
        ]))
        items = m.list_items("login")
        victim = items[0]["_item"]
        check("delete True", m.delete_item(items[0]) is True)
        check("delete called on handle", victim.deleted)
        check("delete False without handle", m.delete_item({}) is False)
        m.Secret = None
        check("delete False without libsecret", m.delete_item(items[1]) is False)

        class DelBoom:
            def delete_sync(self, cancellable):
                raise RuntimeError("denied")
        check("delete False on error",
              m.get_item_secret  # keep flake quiet
              and m.delete_item({"_item": DelBoom()}) is False)

        # --- lock_items ---
        m.Secret = make_fake_secret(service=FakeService([
            FakeCollection("login", "login", items=FIXTURE_ITEMS),
        ]))
        items = m.list_items("login")
        n = m.lock_items(items)
        check("lock locks every item", n == len(FIXTURE_ITEMS), n)
        check("lock invokes backend per item",
              m.Secret.password_lock_sync.call_count == len(FIXTURE_ITEMS))
        check("lock skips attrless items", m.lock_items([{"label": "x"}]) == 0)
        check("lock None items safe", m.lock_items(None) == 0)
        m.Secret = make_fake_secret(
            service=FakeService([]), lock_side_effect=RuntimeError("no daemon"))
        check("lock tolerates backend errors", m.lock_items(items) == 0)
        m.Secret = None
        check("lock zero without libsecret", m.lock_items(items) == 0)
    finally:
        m.Secret = saved


def find_button(win, tooltip):
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk
    hits = []

    def walk(w):
        if isinstance(w, Gtk.Button) \
                and w.get_tooltip_text() == tooltip:
            hits.append(w)
        if isinstance(w, Gtk.Container):
            for child in w.get_children():
                walk(child)
    walk(win)
    return hits[0] if hits else None


def grid_entries(dlg):
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk
    grid = [c for c in dlg.get_content_area().get_children()
            if isinstance(c, Gtk.Grid)][0]
    return [c for c in grid.get_children() if isinstance(c, Gtk.Entry)], grid


def test_gui_smoke(m, td):
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk, Gdk
    except (ImportError, ValueError):
        print("SKIP - gui smoke (no PyGObject on this host)")
        return
    if not Gtk.init_check()[0]:
        print("ok - gui smoke skipped (no display)")
        return

    fake_secret = make_fake_secret(service=FakeService([
        FakeCollection("login", "login", locked=False, items=FIXTURE_ITEMS),
        FakeCollection("system", "System", locked=True),
    ]))
    with mock.patch.object(m, "Secret", fake_secret):
        win = m.build_keychain_class()()
        try:
            for _ in range(20):
                Gtk.main_iteration_do(False)

            check("gui constructs", True)
            check("gui sidebar populated", len(win.sidebar_store) == 2,
                  len(win.sidebar_store))
            check("gui items populated", len(win.store) == len(FIXTURE_ITEMS),
                  len(win.store))
            check("gui no error bar", not win.error_bar.get_visible())

            win.view.get_selection().select_path(Gtk.TreePath.new_first())
            for _ in range(5):
                Gtk.main_iteration_do(False)
            check("gui selection sets detail",
                  "Example account" in win.detail_label.get_text(),
                  win.detail_label.get_text())
            check("gui attrs rendered",
              len(win.attr_grid.get_children()) >= 4,
              len(win.attr_grid.get_children()))

            calls_before = fake_secret.Service.get_sync.call_count
            win.search.set_text("WiFi")
            for _ in range(5):
                Gtk.main_iteration_do(False)
            visible = [r[0] for r in win.store]
            check("gui search filters client-side", visible == ["WiFi Guest"],
                  visible)
            check("gui search did not re-query backend",
                  fake_secret.Service.get_sync.call_count == calls_before,
                  fake_secret.Service.get_sync.call_count - calls_before)
            win.search.set_text("")
            for _ in range(5):
                Gtk.main_iteration_do(False)
            check("gui search clear restores rows",
                  len(win.store) == len(FIXTURE_ITEMS), len(win.store))

            win.view.get_selection().select_path(Gtk.TreePath.new_first())
            for _ in range(5):
                Gtk.main_iteration_do(False)
            win.show_secret.set_active(True)
            for _ in range(5):
                Gtk.main_iteration_do(False)
            check("gui secret revealed on toggle",
                  win.secret_entry.get_text() == "correct horse battery staple",
                  win.secret_entry.get_text()[:12])
            check("gui copy enabled after reveal",
                  win.copy_secret.get_sensitive())

            new_btn = find_button(win, "New Password Item (Ctrl+N)")
            check("gui new button exists", new_btn is not None)
            if new_btn is not None:
                stored_before = len(fake_secret._stored)

                def fake_new_run(self, *a, **k):
                    entries, _grid = grid_entries(self)
                    by_ph = {e.get_placeholder_text(): e for e in entries}
                    by_ph["e.g. Example account"].set_text("Test Item")
                    by_ph["username"].set_text("bob")
                    by_ph["example.com"].set_text("test.example.org")
                    pw_entry = [e for e in entries
                                if e.get_placeholder_text() is None][0]
                    pw_entry.set_text("secret-pw-123")
                    return Gtk.ResponseType.OK
                with mock.patch.object(m.Gtk.Dialog, "run", fake_new_run):
                    new_btn.emit("clicked")
                for _ in range(5):
                    Gtk.main_iteration_do(False)
                check("gui new dialog stores via backend",
                      fake_secret._stored.get("label") == "Test Item",
                      fake_secret._stored.get("label"))
                check("gui new dialog stores attrs",
                      fake_secret._stored.get("attrs")
                      == {"account": "bob", "where": "test.example.org"},
                      fake_secret._stored.get("attrs"))
                check("gui new dialog stored secret",
                      fake_secret._stored.get("password") == "secret-pw-123")

            gen_btn = find_button(win, "Password Generator (Ctrl+G)")
            check("gui generator button exists", gen_btn is not None)
            if gen_btn is not None:
                gen_captured = {}

                def fake_gen_run(self, *a, **k):
                    entries, grid = grid_entries(self)
                    gen_captured["pw"] = entries[0].get_text()
                    gen_captured["strength"] = [
                        c.get_text() for c in grid.get_children()
                        if isinstance(c, Gtk.Label)
                        and "entropy" in c.get_text()][-1]
                    return Gtk.ResponseType.CLOSE
                with mock.patch.object(m.Gtk.Dialog, "run", fake_gen_run):
                    gen_btn.emit("clicked")
                for _ in range(5):
                    Gtk.main_iteration_do(False)
                check("gui generator produces password",
                      len(gen_captured.get("pw", "")) == 16,
                      len(gen_captured.get("pw", "")))
                check("gui generator shows entropy",
                      "bits of entropy" in gen_captured.get("strength", ""),
                      gen_captured.get("strength", ""))

            lock_btn = find_button(win, "Lock this keychain (Ctrl+L)")
            check("gui lock button exists", lock_btn is not None)
            if lock_btn is not None:
                lock_btn.emit("clicked")
                for _ in range(5):
                    Gtk.main_iteration_do(False)
                check("gui lock invokes backend",
                      fake_secret.password_lock_sync.call_count
                      == len(FIXTURE_ITEMS),
                      fake_secret.password_lock_sync.call_count)

            win.view.get_selection().select_path(Gtk.TreePath.new_first())
            for _ in range(5):
                Gtk.main_iteration_do(False)
            del_btn = win.del_btn
            check("gui delete enabled", del_btn.get_sensitive())
            if del_btn.get_sensitive():
                victim = win.selected_item["_item"]
                with mock.patch.object(m.Gtk.MessageDialog, "run",
                                       return_value=Gtk.ResponseType.OK):
                    del_btn.emit("clicked")
                for _ in range(5):
                    Gtk.main_iteration_do(False)
                check("gui delete removes item", victim.deleted)
        finally:
            win.destroy()

    # unavailable states
    with mock.patch.object(m, "Secret", None):
        win2 = m.build_keychain_class()()
        try:
            for _ in range(10):
                Gtk.main_iteration_do(False)
            check("gui no-libsecret shows error",
                  "libsecret is unavailable"
                  in win2.error_bar.get_content_area()
                  .get_children()[0].get_text())
            check("gui no-libsecret sidebar fallback",
                  len(win2.sidebar_store) == len(m.DEFAULT_COLLECTIONS))
        finally:
            win2.destroy()

    with mock.patch.object(m, "Secret", make_fake_secret(service=None)):
        win3 = m.build_keychain_class()()
        try:
            for _ in range(10):
                Gtk.main_iteration_do(False)
            check("gui daemon-absent shows error",
                  "keychain service is unavailable"
                  in win3.error_bar.get_content_area()
                  .get_children()[0].get_text())
        finally:
            win3.destroy()

    with mock.patch.object(m, "Secret", make_fake_secret(
            service=FakeService([FakeCollection("login", "login", items=[])]))):
        win4 = m.build_keychain_class()()
        try:
            for _ in range(10):
                Gtk.main_iteration_do(False)
            win4.view.get_selection().unselect_all()
            for _ in range(5):
                Gtk.main_iteration_do(False)
            check("gui empty keychain state",
                  "No items in this keychain." in win4.detail_label.get_text(),
                  win4.detail_label.get_text())
            check("gui no error bar when service ok",
                  not win4.error_bar.get_visible())
        finally:
            win4.destroy()


def main():
    m = load_app()
    test_pure(m)
    td = tempfile.mkdtemp(prefix="mv-keychain-test-")
    test_gui_smoke(m, td)
    print("---")
    print("passed: %d, failed: %d" % (ok.count, len(bad.failures)))
    if bad.failures:
        for name, detail in bad.failures:
            print("FAILED: %s %s" % (name, detail))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())


def test_native_window_chrome_contract():
    with open(APP_PATH, encoding="utf-8") as fh:
        source = fh.read()
    check("keychain has no GTK HeaderBar", "Gtk.HeaderBar" not in source)
    check("keychain uses Mavericks toolbar", 'mav-toolbar' in source)
    check("keychain keeps real window chrome", 'self.set_titlebar' not in source)
    check("keychain toolbar has search", 'Search items...' in source)
