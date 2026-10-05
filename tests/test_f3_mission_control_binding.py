"""Test that F3 Mission Control binding is configured in xfce4-panel.xml."""
import xml.etree.ElementTree as ET
import os
import sys


def test_f3_binding_exists():
    """Test that F3 → mv-mc-gui binding exists in panel config."""
    config_path = "configs/desktop/xfce/xfce4-panel.xml"
    
    if not os.path.exists(config_path):
        print(f"SKIP: {config_path} not found")
        return
    
    try:
        tree = ET.parse(config_path)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"FAIL: Invalid XML in {config_path}: {e}")
        sys.exit(1)
    
    # Find all shortcut properties
    found_f3 = False
    found_mc_gui = False
    
    for elem in root.iter():
        if elem.tag == "property":
            name = elem.get("name", "")
            value = elem.get("value", "")
            
            # Check for F3 binding
            if "F3" in name and "mv-mc-gui" in value:
                found_f3 = True
                found_mc_gui = True
                print(f"Found F3 binding: {name} → {value}")
    
    assert found_f3, "F3 binding not found in xfce4-panel.xml"
    assert found_mc_gui, "mv-mc-gui command not bound to F3"
    
    print("PASS: F3 → mv-mc-gui binding configured correctly")


def test_f3_binding_non_breaking():
    """F3 binding must be a custom command shortcut, not a wm binding hack.

    Contract (f7602c4): the real binding lives in the
    xfce4-keyboard-shortcuts channel (package + archiso skel copies);
    xfce4-panel.xml only mirrors it inside a dedicated custom-shortcuts
    container — never inside a panel plugin definition.
    """
    shortcuts_copies = [
        "packages/mavericks-apps/src/mavericks-apps/config/xfce4-keyboard-shortcuts.xml",
        "archiso-profile/releng/airootfs/etc/skel/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-keyboard-shortcuts.xml",
    ]
    for path in shortcuts_copies:
        if not os.path.exists(path):
            print(f"SKIP: {path} not found")
            return
        tree = ET.parse(path)
        found = False
        for elem in tree.getroot().iter():
            if elem.tag == "property" and elem.get("name") == "<Super>F3":
                assert elem.get("value") == "mv-mc-gui", (path, elem.get("value"))
                found = True
        assert found, f"<Super>F3 command binding missing in {path}"

    panel_path = "configs/desktop/xfce/xfce4-panel.xml"
    if not os.path.exists(panel_path):
        print(f"SKIP: {panel_path} not found")
        return
    tree = ET.parse(panel_path)
    mirror = None
    for elem in tree.getroot().iter():
        if elem.tag == "property" and elem.get("name") == "custom-shortcuts":
            for child in elem:
                if child.tag == "property" and child.get("name") == "<Super>F3":
                    mirror = child
    assert mirror is not None, "panel F3 mirror missing under custom-shortcuts"
    assert mirror.get("value") == "mv-mc-gui"

    # The mirror must live outside every plugin-* definition.
    for elem in tree.getroot().iter():
        if elem.tag == "property" and elem.get("name", "").startswith("plugin-"):
            for child in elem.iter():
                if child is mirror:
                    assert False, "F3 mirror must not sit inside a panel plugin"

    print("PASS: F3 binding uses non-breaking custom shortcuts contract")


if __name__ == "__main__":
    test_f3_binding_exists()
    test_f3_binding_non_breaking()
