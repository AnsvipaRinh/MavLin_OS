# Makefile for mavericks-apps — only mv-hud needs compilation.
# Target CPU: Kaby Lake-Y (m3-7Y32). No -march=native (ISO builds on any host).
CC ?= cc
CFLAGS ?= -march=skylake -mtune=skylake -O2 -pipe -fno-plt
LDFLAGS ?= -Wl,-O1,--sort-common,--as-needed -s
PREFIX ?= /usr

all: mv-hud

mv-hud: bin/mv-hud.c
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

clean:
	rm -f mv-hud

install: all
	install -Dm755 mv-hud "$(DESTDIR)$(PREFIX)/bin/mv-hud"
	for f in bin/mv-settings bin/mv-about bin/mv-activity bin/mv-console \
	         bin/mv-control bin/mv-power-ui bin/mv-shot bin/mv-quicklook \
	         bin/mv-quicklook-thunar bin/mv-spotlight-preview \
	         bin/mv-notes bin/mv-reminders bin/mv-voice bin/mv-newfolder bin/mv-spotlight \
	         bin/mv-getinfo bin/mv-openwith bin/mv-rename bin/mv-eject bin/mv-launchpad bin/mv-mission-control bin/mv-textedit bin/mv-calculator bin/mv-calendar bin/mv-dictionary bin/mv-music bin/mv-photos bin/mv-mail bin/mv-preview \
	         bin/mv-keychain bin/mv-fontbook bin/mv-colormeter bin/mv-stickies bin/mv-notify-send bin/mv-notification-center bin/mv-diskutil bin/mv-airdrop bin/mv-timemachine bin/mv-ytplayer \
	         bin/mv-finder-search bin/mv-finder-columns; do \
		install -Dm755 "$$f" "$(DESTDIR)$(PREFIX)/bin/$$(basename $$f)"; \
	done
	install -Dm755 bin/mv_desktop_cache.py "$(DESTDIR)$(PREFIX)/bin/mv_desktop_cache.py"
	install -d "$(DESTDIR)$(PREFIX)/share/applications"
	install -m644 desktop/*.desktop "$(DESTDIR)$(PREFIX)/share/applications/"
	install -m644 config/mv-ytplayer-protocol.desktop "$(DESTDIR)$(PREFIX)/share/applications/"
	install -d "$(DESTDIR)$(PREFIX)/share/mavericks-apps"
	install -m644 lib/mavericks_appmenu.py "$(DESTDIR)$(PREFIX)/share/mavericks-apps/mavericks_appmenu.py"
	install -m644 config/rofi-mavericks.rasi "$(DESTDIR)$(PREFIX)/share/mavericks-apps/"
	install -m644 config/rofi-launchpad.rasi "$(DESTDIR)$(PREFIX)/share/mavericks-apps/"
	install -m644 config/rofi-mission-control.rasi "$(DESTDIR)$(PREFIX)/share/mavericks-apps/"
	install -m644 config/thunar-uca.xml "$(DESTDIR)$(PREFIX)/share/mavericks-apps/"
	install -m644 config/xfce4-keyboard-shortcuts.xml "$(DESTDIR)$(PREFIX)/share/mavericks-apps/"
	install -m644 config/mv-ytplayer-bookmarklet.html "$(DESTDIR)$(PREFIX)/share/mavericks-apps/"
	install -Dm644 ../../../../configs/mv-ytplayer/codec-policy.conf "$(DESTDIR)/etc/mv-ytplayer/codec-policy.conf"
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