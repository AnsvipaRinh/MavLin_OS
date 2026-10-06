# MavLinOS Main Makefile
# Convenience targets for common tasks

.PHONY: help install-mission-control test-mission-control

help:
	@echo "MavLinOS Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  install-mission-control  - Install all Mission Control helpers"
	@echo "  test-mission-control     - Run Mission Control test suite"
	@echo "  help                     - Show this help message"
	@echo ""

install-mission-control:
	@echo "Installing Mission Control helpers..."
	@$(MAKE) -f packages/mavericks-apps/src/mavericks-apps/MISSION_CONTROL_Makefile install

test-mission-control:
	@echo "Running Mission Control test suite..."
	@./ci/test-mission-control.sh
