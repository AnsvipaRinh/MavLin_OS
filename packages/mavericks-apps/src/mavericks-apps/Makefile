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
	         bin/mv-notes bin/mv-reminders bin/mv-voice bin/mv-newfolder bin/mv-spotlight \
	         bin/mv-getinfo bin/mv-openwith bin/mv-rename bin/mv-eject bin/mv-launchpad; do \
		install -Dm755 "$$f" "$(DESTDIR)$(PREFIX)/bin/$$(basename $$f)"; \
	done
	install -d "$(DESTDIR)$(PREFIX)/share/applications"
	install -m644 desktop/*.desktop "$(DESTDIR)$(PREFIX)/share/applications/"
	install -d "$(DESTDIR)$(PREFIX)/share/mavericks-apps"
	install -m644 config/rofi-mavericks.rasi "$(DESTDIR)$(PREFIX)/share/mavericks-apps/"
	install -m644 config/rofi-launchpad.rasi "$(DESTDIR)$(PREFIX)/share/mavericks-apps/"
	install -m644 config/thunar-uca.xml "$(DESTDIR)$(PREFIX)/share/mavericks-apps/"
	install -m644 config/xfce4-keyboard-shortcuts.xml "$(DESTDIR)$(PREFIX)/share/mavericks-apps/"
	install -Dm644 config/mv-reminders-check.timer \
		"$(DESTDIR)/usr/lib/systemd/user/mv-reminders-check.timer"
	install -Dm644 config/mv-reminders-check.service \
		"$(DESTDIR)/usr/lib/systemd/user/mv-reminders-check.service"

.PHONY: all clean install
