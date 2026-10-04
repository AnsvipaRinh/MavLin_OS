#!/usr/bin/env python3
"""Validate the shipped Xfce panel configuration invariants."""

from pathlib import Path
import sys
import xml.etree.ElementTree as ET

PATHS = [
    Path(
        "archiso-profile/releng/airootfs/etc/skel/.config/xfce4/"
        "xfconf/xfce-perchannel-xml/xfce4-panel.xml"
    ),
    Path("configs/desktop/xfce/xfce4-panel.xml"),
]


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return [f"missing {path}"]

    root = ET.parse(path).getroot()
    plugins = root.find("./property[@name='plugins']")
    panel = root.find("./property[@name='panels']/property[@name='panel-1']")
    if plugins is None:
        errors.append(f"{path}: missing plugins property")
        return errors
    if panel is None:
        errors.append(f"{path}: missing panel-1")
        return errors

    ids = [v.get("value") for v in panel.findall("./property[@name='plugin-ids']/value")]
    if len(ids) != len(set(ids)):
        errors.append(f"{path}: duplicate panel plugin IDs: {ids}")

    properties = {}
    for child in plugins:
        name = child.get("name")
        if not name or not name.startswith("plugin-"):
            errors.append(f"{path}: unexpected plugin property: {name!r}")
            continue
        if name in properties:
            errors.append(f"{path}: duplicate plugin property: {name}")
            continue
        properties[name] = child

    prop_ids = {name.removeprefix("plugin-") for name in properties}
    if set(ids) != prop_ids:
        errors.append(
            f"{path}: panel plugin-ids {ids} disagree with properties {sorted(prop_ids)}"
        )

    hud = properties.get("plugin-7")
    if hud is None or hud.get("type") != "string" or hud.get("value") != "genmon":
        errors.append(f"{path}: plugin-7 must be genmon (type=string value=genmon)")
    else:
        cmd = hud.find("./property[@name='command']")
        period = hud.find("./property[@name='update-period']")
        if cmd is None or cmd.get("value") != "mv-hud":
            errors.append(f"{path}: plugin-7 command must be mv-hud")
        if period is None or period.get("value") != "5000":
            errors.append(f"{path}: plugin-7 update-period must be 5000 (ms)")
        if hud.find("./property[@name='interval']") is not None:
            errors.append(f"{path}: legacy genmon 'interval' still present")

    return errors


def main() -> int:
    all_errors: list[str] = []
    for path in PATHS:
        errs = validate(path)
        if errs:
            all_errors.extend(errs)
        else:
            print(f"OK: {path}")

    # configs/ and airootfs must stay byte-identical (check-sync pair)
    if PATHS[0].is_file() and PATHS[1].is_file():
        if PATHS[0].read_bytes() != PATHS[1].read_bytes():
            all_errors.append(
                f"drift: {PATHS[1]} != {PATHS[0]} (check-sync pair must match)"
            )
        else:
            print("OK: configs/ ↔ airootfs panel XML identical")

    if all_errors:
        for e in all_errors:
            print(f"FAIL: {e}")
        return 1

    print("OK: unique plugin IDs and properties agree")
    print("OK: plugin-7 genmon HUD contract (mv-hud, update-period=5000)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
