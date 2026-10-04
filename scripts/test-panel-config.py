#!/usr/bin/env python3
"""Validate the shipped Xfce panel configuration invariants."""

from pathlib import Path
import sys
import xml.etree.ElementTree as ET

PATH = Path(
    "archiso-profile/releng/airootfs/etc/skel/.config/xfce4/"
    "xfconf/xfce-perchannel-xml/xfce4-panel.xml"
)


def main() -> int:
    if not PATH.is_file():
        print(f"FAIL: missing {PATH}")
        return 1

    root = ET.parse(PATH).getroot()
    plugins = root.find("./property[@name='plugins']")
    panel = root.find("./property[@name='panels']/property[@name='panel-1']")
    if plugins is None:
        print("FAIL: missing plugins property")
        return 1
    if panel is None:
        print("FAIL: missing panel-1")
        return 1

    ids = [v.get("value") for v in panel.findall("./property[@name='plugin-ids']/value")]
    if len(ids) != len(set(ids)):
        print(f"FAIL: duplicate panel plugin IDs: {ids}")
        return 1

    properties = {}
    for child in plugins:
        name = child.get("name")
        if not name or not name.startswith("plugin-"):
            print(f"FAIL: unexpected plugin property: {name!r}")
            return 1
        if name in properties:
            print(f"FAIL: duplicate plugin property: {name}")
            return 1
        properties[name] = child

    prop_ids = {name.removeprefix("plugin-") for name in properties}
    if set(ids) != prop_ids:
        print(f"FAIL: panel plugin-ids {ids} disagree with properties {sorted(prop_ids)}")
        return 1

    hud = properties.get("plugin-7")
    if hud is None or hud.get("type") != "string" or hud.get("value") != "genmon":
        print("FAIL: plugin-7 must be the genmon HUD (type=string value=genmon)")
        return 1

    cmd = hud.find("./property[@name='command']")
    period = hud.find("./property[@name='update-period']")
    if cmd is None or cmd.get("value") != "mv-hud":
        print("FAIL: plugin-7 command must be mv-hud")
        return 1
    if period is None or period.get("value") != "5000":
        print("FAIL: plugin-7 update-period must be 5000 (ms)")
        return 1

    # Legacy wrong property must not remain
    if hud.find("./property[@name='interval']") is not None:
        print("FAIL: legacy genmon 'interval' property still present; use update-period")
        return 1

    print(f"OK: {PATH}")
    print("OK: unique plugin IDs and properties agree")
    print("OK: plugin-7 genmon HUD contract (mv-hud, update-period=5000)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
