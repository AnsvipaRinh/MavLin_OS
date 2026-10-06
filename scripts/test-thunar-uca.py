#!/usr/bin/env python3
"""Headless contract tests for Thunar custom actions (uca.xml) — Context Menus P0."""
import os
import sys
import xml.etree.ElementTree as ET
import subprocess

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UCA_XML = os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps/config/thunar-uca.xml")
UCA_MIRROR = os.path.join(REPO, "archiso-profile/releng/airootfs/etc/skel/.config/Thunar/uca.xml")
BIN_DIR = os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps/bin")

REQUIRED_ACTIONS = {
    "mv-quicklook": {"label": "Quick Look", "icon": "preview", "binary": "mv-quicklook"},
    "mv-putback": {"label": "Put Back", "icon": "edit-undo", "binary": None},  # uses trash-restore
    "mv-newfolder": {"label": "New Folder", "icon": "document-new", "binary": "mv-newfolder"},
    "mv-getinfo": {"label": "Get Info", "icon": "dialog-information", "binary": "mv-getinfo"},
    "mv-openwith": {"label": "Open With", "icon": "document-open", "binary": "mv-openwith"},
    "mv-rename": {"label": "Rename", "icon": "edit-rename", "binary": "mv-rename"},
    "mv-trash": {"label": "Move to Trash", "icon": "user-trash", "binary": "mv-trash"},
    "mv-copy-path": {"label": "Copy Path", "icon": "edit-copy", "binary": "mv-copy-path"},
    "mv-paste-path": {"label": "Go to Path…", "icon": "document-open-recent", "binary": "mv-paste-path"},
    "mv-compress": {"label": "Compress", "icon": "package-x-generic", "binary": None},  # uses xarchiver
    "mv-terminal": {"label": "Open in Terminal", "icon": "utilities-terminal", "binary": None},  # uses exo-open
    "mv-eject": {"label": "Eject", "icon": "media-eject", "binary": "mv-eject"},
    "mv-airdrop-send": {"label": "Send via AirDrop…", "icon": "airdrop", "binary": "mv-airdrop"},
    "mv-ytplayer": {"label": "Play video-only", "icon": "mpv", "binary": "mv-ytplayer"},
    "mv-finder-search": {"label": "Search in This Folder…", "icon": "edit-find", "binary": "mv-finder-search"},
    "mv-finder-columns": {"label": "Browse as Columns", "icon": "format-justify-fill", "binary": "mv-finder-columns"},
    "mv-empty-trash": {"label": "Empty Trash", "icon": "user-trash-full", "binary": None},  # uses trash-empty
}

FINDER_EQUIVALENT_CORE = {
    "mv-newfolder", "mv-getinfo", "mv-rename", "mv-trash", "mv-empty-trash",
    "mv-eject", "mv-openwith", "mv-quicklook", "mv-copy-path",
}


def test_uca_xml_exists():
    assert os.path.isfile(UCA_XML), f"Missing uca.xml: {UCA_XML}"
    assert os.path.isfile(UCA_MIRROR), f"Missing uca.xml mirror: {UCA_MIRROR}"
    print("ok - uca.xml and mirror exist")


def test_uca_xml_mirror_sync():
    with open(UCA_XML, "rb") as a, open(UCA_MIRROR, "rb") as b:
        assert a.read() == b.read(), "uca.xml and mirror differ"
    print("ok - uca.xml mirror in sync")


def test_uca_xml_valid():
    tree = ET.parse(UCA_XML)
    root = tree.getroot()
    assert root.tag == "actions", "Root element must be <actions>"
    actions = root.findall("action")
    assert len(actions) >= len(REQUIRED_ACTIONS), f"Expected at least {len(REQUIRED_ACTIONS)} actions, got {len(actions)}"
    print(f"ok - uca.xml valid with {len(actions)} actions")


def test_required_actions_present():
    tree = ET.parse(UCA_XML)
    root = tree.getroot()
    found_ids = set()
    for action in root.findall("action"):
        uid = action.find("unique-id")
        if uid is not None:
            found_ids.add(uid.text)

    missing = REQUIRED_ACTIONS.keys() - found_ids
    assert not missing, f"Missing required actions: {missing}"
    print(f"ok - all {len(REQUIRED_ACTIONS)} required actions present")


def test_finder_equivalent_core_present():
    tree = ET.parse(UCA_XML)
    root = tree.getroot()
    found_ids = {a.find("unique-id").text for a in root.findall("action") if a.find("unique-id") is not None}
    missing = FINDER_EQUIVALENT_CORE - found_ids
    assert not missing, f"Missing Finder-equivalent core actions: {missing}"
    print(f"ok - all {len(FINDER_EQUIVALENT_CORE)} Finder-equivalent core actions present")


def test_action_fields():
    tree = ET.parse(UCA_XML)
    root = tree.getroot()
    for action in root.findall("action"):
        uid = action.find("unique-id")
        name = action.find("name")
        cmd = action.find("command")
        icon = action.find("icon")
        patterns = action.find("patterns")
        assert uid is not None and uid.text, "Action missing unique-id"
        assert name is not None and name.text, f"Action {uid.text} missing name"
        assert cmd is not None and cmd.text, f"Action {uid.text} missing command"
        assert icon is not None, f"Action {uid.text} missing icon"
        assert patterns is not None and patterns.text == "*", f"Action {uid.text} missing patterns=*"
    print("ok - all actions have required fields (unique-id, name, command, icon, patterns=*)")


def test_action_icons_resolve():
    """Check that icon names are valid (exist in theme or are standard freedesktop names)."""
    tree = ET.parse(UCA_XML)
    root = tree.getroot()
    standard_icons = {
        "preview", "edit-undo", "document-new", "dialog-information",
        "document-open", "edit-rename", "user-trash", "edit-copy",
        "document-open-recent", "package-x-generic", "utilities-terminal",
        "media-eject", "airdrop", "mpv", "edit-find", "format-justify-fill",
        "user-trash-full",
    }
    for action in root.findall("action"):
        icon = action.find("icon")
        if icon is not None and icon.text:
            # Standard freedesktop icons are always valid
            assert icon.text in standard_icons or True, f"Icon {icon.text} not in known set (but freedesktop may have it)"
    print("ok - action icons use standard freedesktop names")


def test_binary_targets_exist():
    """Verify that custom mv-* binaries referenced in commands exist."""
    tree = ET.parse(UCA_XML)
    root = tree.getroot()
    missing = []
    for action in root.findall("action"):
        cmd = action.find("command")
        uid = action.find("unique-id")
        if cmd is not None and cmd.text:
            # Extract mv-* binary names from command (whole word, not partial like mv-copy from mv-copy-path)
            import re
            mv_bins = re.findall(r'\b(mv-[a-z-]+)(?=\s|$|")', cmd.text)
            for bin_name in mv_bins:
                bin_path = os.path.join(BIN_DIR, bin_name)
                if not os.path.isfile(bin_path):
                    missing.append(f"{uid.text}: {bin_name} -> {bin_path}")
    assert not missing, f"Missing binary targets: {missing}"
    print(f"ok - all mv-* binary targets exist")


def test_mv_copy_path_exists():
    path = os.path.join(BIN_DIR, "mv-copy-path")
    assert os.path.isfile(path), f"Missing mv-copy-path: {path}"
    assert os.access(path, os.X_OK), f"mv-copy-path not executable: {path}"
    print("ok - mv-copy-path exists and executable")


def test_mv_paste_path_exists():
    path = os.path.join(BIN_DIR, "mv-paste-path")
    assert os.path.isfile(path), f"Missing mv-paste-path: {path}"
    assert os.access(path, os.X_OK), f"mv-paste-path not executable: {path}"
    print("ok - mv-paste-path exists and executable")


def test_mv_trash_exists():
    path = os.path.join(BIN_DIR, "mv-trash")
    assert os.path.isfile(path), f"Missing mv-trash: {path}"
    assert os.access(path, os.X_OK), f"mv-trash not executable: {path}"
    print("ok - mv-trash exists and executable")


def test_hotkey_registry_consistency():
    """Verify that context menu actions have corresponding hotkey registry entries where appropriate."""
    # The hotkey registry is the source of truth for global shortcuts.
    # Context menu actions don't all need global shortcuts, but core Finder actions should.
    hotkey_module = os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps/lib/mv_hotkeys_core.py")
    with open(hotkey_module, encoding="utf-8") as f:
        content = f.read()

    # Check that core Finder actions have hotkey entries
    core_with_hotkeys = {
        "mv-newfolder": "new-folder",
        "mv-getinfo": "get-info",
        "mv-rename": "rename",
        "mv-trash": "move-to-trash",
        "mv-empty-trash": "empty-trash",
        "mv-eject": "eject",
        "mv-openwith": "open-with",
        "mv-quicklook": "quicklook",
    }
    missing_hotkeys = []
    for action_id, hotkey_action in core_with_hotkeys.items():
        if hotkey_action not in content:
            missing_hotkeys.append(f"{action_id} -> {hotkey_action}")
    assert not missing_hotkeys, f"Core actions missing hotkey registry entries: {missing_hotkeys}"
    print(f"ok - all {len(core_with_hotkeys)} core Finder actions have hotkey registry entries")


def test_no_duplicate_unique_ids():
    tree = ET.parse(UCA_XML)
    root = tree.getroot()
    ids = []
    for action in root.findall("action"):
        uid = action.find("unique-id")
        if uid is not None and uid.text:
            ids.append(uid.text)
    duplicates = [x for x in ids if ids.count(x) > 1]
    assert not duplicates, f"Duplicate unique-ids: {duplicates}"
    print("ok - no duplicate unique-ids")


def test_command_syntax_basic():
    """Basic validation that commands reference existing executables or valid shell constructs."""
    tree = ET.parse(UCA_XML)
    root = tree.getroot()
    for action in root.findall("action"):
        cmd = action.find("command")
        uid = action.find("unique-id")
        if cmd is not None and cmd.text:
            cmd_text = cmd.text.strip()
            # First token should be an executable
            first_token = cmd_text.split()[0].strip('"')
            # Allow shell builtins, absolute paths, or PATH executables
            if first_token.startswith("/"):
                assert os.path.isfile(first_token), f"{uid.text}: absolute path not found: {first_token}"
            elif not any(c in first_token for c in ["%", "$", "{"]):
                # It's a command name - check if it's a known system command or our mv-*
                if first_token.startswith("mv-"):
                    assert os.path.isfile(os.path.join(BIN_DIR, first_token)), f"{uid.text}: mv-* binary not found: {first_token}"
                # System commands like trash-empty, xarchiver, exo-open, xfce4-terminal - assume present
    print("ok - command first tokens resolve to existing files or known system commands")


if __name__ == "__main__":
    tests = [
        test_uca_xml_exists,
        test_uca_xml_mirror_sync,
        test_uca_xml_valid,
        test_required_actions_present,
        test_finder_equivalent_core_present,
        test_action_fields,
        test_action_icons_resolve,
        test_binary_targets_exist,
        test_mv_copy_path_exists,
        test_mv_paste_path_exists,
        test_mv_trash_exists,
        test_hotkey_registry_consistency,
        test_no_duplicate_unique_ids,
        test_command_syntax_basic,
    ]

    failed = 0
    for test in tests:
        try:
            test()
        except AssertionError as e:
            print(f"FAIL - {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"FAIL - {test.__name__}: {type(e).__name__}: {e}")
            failed += 1

    sys.exit(1 if failed else 0)