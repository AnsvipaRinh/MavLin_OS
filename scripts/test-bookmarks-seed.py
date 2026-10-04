#!/usr/bin/env python3
"""Validate GTK bookmarks template + firstboot seed_bookmarks contract."""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_PATHS = [
    os.path.join(REPO, "configs/desktop/thunar/bookmarks"),
    os.path.join(
        REPO, "archiso-profile/releng/airootfs/etc/skel/.gtk-bookmarks.template"
    ),
]
FIRSTBOOT_PATHS = [
    os.path.join(REPO, "scripts/install/mavericks-firstboot.sh"),
    os.path.join(
        REPO,
        "archiso-profile/releng/airootfs/usr/local/bin/mavericks/mavericks-firstboot.sh",
    ),
]

errors = []
texts = []
for path in TEMPLATE_PATHS:
    if not os.path.isfile(path):
        errors.append("missing %s" % path)
        continue
    text = open(path, encoding="utf-8").read()
    texts.append(text)
    if "USER_PLACEHOLDER" in text:
        errors.append("%s still has USER_PLACEHOLDER" % path)
    if "Desktop/Desktop" in text:
        errors.append("%s has doubled Desktop/Desktop path" % path)
    if "@HOME@" not in text:
        errors.append("%s must use @HOME@ placeholder" % path)
    for place in ("Desktop", "Documents", "Downloads", "Music", "Pictures", "Movies"):
        if place not in text:
            errors.append("%s missing place %s" % (path, place))
    if "file:///tmp" in text or "file:///Computer" in text:
        errors.append("%s should not bookmark /tmp or /Computer" % path)

if len(texts) == 2 and texts[0] != texts[1]:
    errors.append("bookmarks template mirrors differ")

fb_texts = []
for path in FIRSTBOOT_PATHS:
    if not os.path.isfile(path):
        errors.append("missing %s" % path)
        continue
    text = open(path, encoding="utf-8").read()
    fb_texts.append(text)
    if "seed_bookmarks" not in text:
        errors.append("%s missing seed_bookmarks" % path)
    if ".gtk-bookmarks" not in text:
        errors.append("%s does not write .gtk-bookmarks" % path)

if len(fb_texts) == 2 and fb_texts[0] != fb_texts[1]:
    errors.append("firstboot mirrors differ")

if errors:
    for e in errors:
        print("FAIL - %s" % e)
    sys.exit(1)

print("ok - bookmarks template uses @HOME@ places")
print("ok - firstboot seed_bookmarks wired (both mirrors)")
