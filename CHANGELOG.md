# Changelog

All notable changes to MavLinOS will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Full Mission Control implementation with GUI overlay ([#2](https://github.com/AnsvipaRinh/MavLin_OS/issues/2))
  - `mv-mc-gui` — GTK3 fullscreen overlay with thumbnails
  - `mv-mc-window-spaces` — JSON window listing by workspace
  - `mv-mc-thumbnail` — Window thumbnail generation
  - `mv-mc-grid` — Dynamic grid layout calculation
  - `mv-mc-activate-window` — Window activation by ID
  - `mv-mc-overview` — CLI integration
  - `mv-workspace-count` — Space count management (1-16)
- F3 keyboard shortcut for Mission Control (non-breaking)
- Comprehensive test suite (12 tests)
- CI gates for automated testing
- Makefile for easy installation (`make install-mission-control`)
- Documentation:
  - `docs/QUICKSTART.md` — First-time user guide
  - `docs/CONTRIBUTING.md` — Developer guide
  - `docs/MISSION_CONTROL.md` — Technical implementation guide
  - `docs/KEYBOARD.md` — Complete keyboard reference
  - `README.md` — Project overview with quick start

### Changed
- Updated README with QUICKSTART and CONTRIBUTING links
- Enhanced MISSION_CONTROL.md with installation instructions
- Added dependency checking to Makefile

### Fixed
- Quick Look native Mavericks window chrome
- Preview native Mavericks window chrome
- Finder native Mavericks window chrome and toolbar visibility
- Hotkeys restoration (AirDrop, empty-trash, GUI spotlight/launchpad)

## [0.1.0] - 2026-10-04

### Added
- Initial MavLinOS release
- Mavericks-style GTK theme
- Basic keyboard shortcuts
- Launchpad implementation
- Spotlight search
- Quick Look preview
- Xfce configuration

## Notes

- Mission Control implementation is complete and ready for use
- All tests pass via `make test-mission-control`
- CI gates ensure quality via `ci/run-all-tests.sh`
- Documentation is comprehensive and user-friendly

## Future

- [ ] Smooth zoom animations for Mission Control
- [ ] Window clustering by application
- [ ] Search/filter in Mission Control
- [ ] Touchpad gesture support (3-finger swipe up)
- [ ] Multi-monitor awareness
- [ ] Cached thumbnails for performance
- [ ] Native C implementation for performance-critical paths
