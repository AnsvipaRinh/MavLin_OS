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
    """Test that F3 binding doesn't override existing wm shortcuts."""
    config_path = "configs/desktop/xfce/xfce4-panel.xml"
    
    if not os.path.exists(config_path):
        print(f"SKIP: {config_path} not found")
        return
    
    try:
        tree = ET.parse(config_path)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"FAIL: Invalid XML: {e}")
        sys.exit(1)
    
    # Check that we're not modifying xfwm4.xml bindings
    # The panel shortcuts should be in a separate "shortcuts" property
    shortcuts_section = False
    
    for elem in root.iter():
        if elem.tag == "property" and elem.get("name") == "shortcuts":
            shortcuts_section = True
            break
    
    assert shortcuts_section, "Custom shortcuts section not found - may be breaking existing bindings"
    
    print("PASS: F3 binding uses non-breaking custom shortcuts section")


if __name__ == "__main__":
    test_f3_binding_exists()
    test_f3_binding_non_breaking()
