# Makefile for mavericks-apps — mv-hud + mv-apple panel plugin.
# Target CPU: Kaby Lake-Y (m3-7Y32). No -march=native (ISO builds on any host).
CC ?= cc
CFLAGS ?= -march=skylake -mtune=skylake -O2 -pipe -fno-plt -fPIC
LDFLAGS ?= -Wl,-O1,--sort-common,--as-needed -s
PREFIX ?= /usr
PANEL_CFLAGS := $(shell pkg-config --cflags libxfce4panel-2.0 gtk+-3.0 2>/dev/null)
PANEL_LIBS := $(shell pkg-config --libs libxfce4panel-2.0 gtk+-3.0 2>/dev/null)

all: mv-hud libmv-apple.so

mv-hud: bin/mv-hud.c
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

libmv-apple.so: panel/mv-apple.c
	@if [ -z "$(PANEL_CFLAGS)" ]; then \
	  echo "WARN: libxfce4panel-2.0 not found — building stub object skipped"; \
	  echo "/* stub */" > $@.c; $(CC) -shared -fPIC -o $@ $@.c; rm -f $@.c; \
	else \
	  $(CC) $(CFLAGS) $(PANEL_CFLAGS) -shared -o $@ $< $(PANEL_LIBS) $(LDFLAGS); \
	fi

clean:
	rm -f mv-hud libmv-apple.so

install: all
	install -Dm755 mv-hud "$(DESTDIR)$(PREFIX)/bin/mv-hud"
	install -Dm755 lib/mission_control.py "$(DESTDIR)$(PREFIX)/share/mavericks-apps/mission_control.py"
	install -Dm755 lib/mv_hotkeys_core.py "$(DESTDIR)$(PREFIX)/share/mavericks-apps/mv_hotkeys_core.py"
	install -Dm644 config/hotkeys/skills.json "$(DESTDIR)$(PREFIX)/share/mavericks-apps/hotkeys/skills.json"
	install -Dm755 lib/mission_control_thumbnail.py "$(DESTDIR)$(PREFIX)/share/mavericks-apps/mission_control_thumbnail.py"
	for f in bin/mv-settings bin/mv-about bin/mv-activity bin/mv-console \
	         bin/mv-control bin/mv-power-ui bin/mv-shot bin/mv-quicklook \
	         bin/mv-quicklook-thunar bin/mv-spotlight-preview \
	         bin/mv-notes bin/mv-reminders bin/mv-voice bin/mv-newfolder bin/mv-spotlight \
	         bin/mv-getinfo bin/mv-openwith bin/mv-rename bin/mv-eject bin/mv-launchpad bin/mv-mission-control bin/mv-textedit bin/mv-calculator bin/mv-calendar bin/mv-dictionary bin/mv-music bin/mv-photos bin/mv-mail bin/mv-preview \
	         bin/mv-mc-overview bin/mv-mc-gui bin/mv-mc-grid \
	         bin/mv-mc-thumbnail bin/mv-mc-window-spaces bin/mv-mc-activate-window \
	         bin/mv-workspace-count \
	         bin/mv-keychain bin/mv-fontbook bin/mv-colormeter bin/mv-stickies bin/mv-notify-send bin/mv-notification-center bin/mv-diskutil bin/mv-airdrop bin/mv-timemachine bin/mv-ytplayer \
	         bin/mv-finder-search bin/mv-finder-columns bin/mv-brightness \
	         bin/mv-quit-app bin/mv-minimize-window bin/mv-hide-app bin/mv-close-window bin/mv-trash \
	         bin/mv-force-quit bin/mv-recent-items bin/mv-hotkeys bin/mv-hotkeys-gui; do \
		install -Dm755 "$$f" "$(DESTDIR)$(PREFIX)/bin/$$(basename $$f)"; \
	done
	install -Dm755 bin/mv_launchpad_edit.py "$(DESTDIR)$(PREFIX)/bin/mv-launchpad-edit"
	install -Dm755 bin/mv_desktop_cache.py "$(DESTDIR)$(PREFIX)/bin/mv_desktop_cache.py"
	install -d "$(DESTDIR)$(PREFIX)/share/applications"
	install -m644 desktop/*.desktop "$(DESTDIR)$(PREFIX)/share/applications/"
	install -m644 config/mv-ytplayer-protocol.desktop "$(DESTDIR)$(PREFIX)/share/applications/"
	install -d "$(DESTDIR)$(PREFIX)/share/mavericks-apps"
	install -m644 config/rofi-mavericks.rasi "$(DESTDIR)$(PREFIX)/share/mavericks-apps/"
	install -m644 config/rofi-launchpad.rasi "$(DESTDIR)$(PREFIX)/share/mavericks-apps/"
	install -m644 config/rofi-mission-control.rasi "$(DESTDIR)$(PREFIX)/share/mavericks-apps/"
	install -m644 config/thunar-uca.xml "$(DESTDIR)$(PREFIX)/share/mavericks-apps/"
	install -m644 config/xfce4-keyboard-shortcuts.xml "$(DESTDIR)$(PREFIX)/share/mavericks-apps/"
	install -m644 config/mv-ytplayer-bookmarklet.html "$(DESTDIR)$(PREFIX)/share/mavericks-apps/"
	install -m644 lib/mavericks_appmenu.py "$(DESTDIR)$(PREFIX)/share/mavericks-apps/mavericks_appmenu.py"
	install -Dm644 ../../../../configs/mv-ytplayer/codec-policy.conf "$(DESTDIR)/etc/mv-ytplayer/codec-policy.conf"
	install -d "$(DESTDIR)$(PREFIX)/lib/xfce4/panel/plugins"
	install -Dm755 libmv-apple.so "$(DESTDIR)$(PREFIX)/lib/xfce4/panel/plugins/libmv-apple.so"
	install -d "$(DESTDIR)$(PREFIX)/share/xfce4/panel/plugins"
	install -m644 panel/mv-apple.desktop "$(DESTDIR)$(PREFIX)/share/xfce4/panel/plugins/mv-apple.desktop"
	install -d "$(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps"
	install -m644 icons/mv-apple.svg "$(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps/mv-apple.svg"
	install -Dm644 config/mv-reminders-check.timer \
		"$(DESTDIR)/usr/lib/systemd/user/mv-reminders-check.timer"
	install -Dm644 config/mv-reminders-check.service \
		"$(DESTDIR)/usr/lib/systemd/user/mv-reminders-check.service"
	install -Dm644 config/mv-calendar-check.timer \
		"$(DESTDIR)/usr/lib/systemd/user/mv-calendar-check.timer"
	install -Dm644 config/mv-calendar-check.service \
		"$(DESTDIR)/usr/lib/systemd/user/mv-calendar-check.service"
	install -Dm644 config/mv-timemachine-check.timer \
		"$(DESTDIR)/usr/lib/systemd/user/mv-timemachine-check.timer"
	install -Dm644 config/mv-timemachine-check.service \
		"$(DESTDIR)/usr/lib/systemd/user/mv-timemachine-check.service"

.PHONY: all clean install
