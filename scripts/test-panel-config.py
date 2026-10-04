#!/usr/bin/env python3
"""Validate the shipped Xfce panel configuration invariants."""

from pathlib import Path
import xml.etree.ElementTree as ET

PATH = Path("archiso-profile/releng/airootfs/etc/skel/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-panel.xml")


def main() -> None:
    root = ET.parse(PATH).getroot()
    plugins = root.find("./property[@name='plugins']")
    panel = root.find("./property[@name='panels']/property[@name='panel-1']")
    assert plugins is not None, "missing plugins property"
    assert panel is not None, "missing panel-1"

    ids = [v.get("value") for v in panel.findall("./property[@name='plugin-ids']/value")]
    assert len(ids) == len(set(ids)), f"duplicate panel plugin IDs: {ids}"

    properties = {}
    for child in plugins:
        name = child.get("name")
        assert name and name.startswith("plugin-"), f"unexpected plugin property: {name!r}"
        assert name not in properties, f"duplicate plugin property: {name}"
        properties[name] = child

    assert set(ids) == {name.removeprefix("plugin-") for name in properties}, (
        "panel plugin-ids and plugin properties disagree"
    )

    hud = properties.get("plugin-7")
    assert hud is not None and hud.get("type") == "string" and hud.get("value") == "genmon", (
        "plugin-7 must be the genmon HUD"
    )
    assert hud.find("./property[@name='command']").get("value") == "mv-hud"
    assert hud.find("./property[@name='update-period']").get("value") == "5000"

    print(f"OK: {PATH}")


if __name__ == "__main__":
    main()
