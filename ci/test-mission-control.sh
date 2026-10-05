#!/bin/bash
# CI gate: comprehensive Mission Control test suite
# Tests all MC components: CLI helpers, GUI, bindings, integration

set -e

echo "========================================"
echo "MavLinOS Mission Control Test Suite"
echo "========================================"
echo ""

TESTS_PASSED=0
TESTS_FAILED=0

run_test() {
    local test_name="$1"
    local test_cmd="$2"
    
    echo -n "Testing $test_name... "
    
    if eval "$test_cmd" > /dev/null 2>&1; then
        echo "✅ PASS"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo "❌ FAIL"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        echo "  Command: $test_cmd"
    fi
}

# GUI isolation (project rule: no test may touch the host display).
# The dev host is WSLg; every helper here opens X11 connections.
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "$REPO_DIR/scripts/gui-isolation.sh"
mv_gui_isolate
mv_gui_pin_display

echo "--- CLI Helper Tests ---"
run_test "window-spaces" "python3 packages/mavericks-apps/src/mavericks-apps/tests/test_mission_control_windows.py"
run_test "thumbnail helper" "python3 packages/mavericks-apps/src/mavericks-apps/tests/test_mission_control_thumbnail_helper.py"
run_test "grid helper" "python3 packages/mavericks-apps/src/mavericks-apps/tests/test_mission_control_grid.py"
run_test "activate helper" "python3 packages/mavericks-apps/src/mavericks-apps/tests/test_mission_control_activation.py"
run_test "overview integration" "python3 packages/mavericks-apps/src/mavericks-apps/tests/test_mission_control_overview.py"
run_test "GUI overlay" "python3 packages/mavericks-apps/src/mavericks-apps/tests/test_mission_control_gui.py"
run_test "workspace count" "python3 packages/mavericks-apps/src/mavericks-apps/tests/test_workspace_count_helper.py"
run_test "packaging manifest (issue #80)" "python3 packages/mavericks-apps/src/mavericks-apps/tests/test_mission_control_packaging.py"

echo ""
echo "--- Binding Tests ---"
run_test "F3 binding" "python3 tests/test_f3_mission_control_binding.py"

echo ""
echo "--- Integration Tests ---"
run_test "MC helpers exist" "test -f packages/mavericks-apps/src/mavericks-apps/bin/mv-mc-window-spaces && test -f packages/mavericks-apps/src/mavericks-apps/bin/mv-mc-thumbnail && test -f packages/mavericks-apps/src/mavericks-apps/bin/mv-mc-grid && test -f packages/mavericks-apps/src/mavericks-apps/bin/mv-mc-activate-window"
run_test "MC GUI exists" "test -f packages/mavericks-apps/src/mavericks-apps/bin/mv-mc-gui"
run_test "MC overview exists" "test -f packages/mavericks-apps/src/mavericks-apps/bin/mv-mc-overview"
run_test "Workspace helper exists" "test -f packages/mavericks-apps/src/mavericks-apps/bin/mv-workspace-count"

echo ""
echo "--- Documentation Tests ---"
run_test "KEYBOARD.md exists" "test -f docs/KEYBOARD.md"
run_test "MISSION_CONTROL.md exists" "test -f docs/MISSION_CONTROL.md"
run_test "MC docs mention F3" "grep -q 'F3' docs/KEYBOARD.md && grep -q 'mv-mc-gui' docs/KEYBOARD.md"

echo ""
echo "========================================"
echo "Test Summary"
echo "========================================"
echo "Passed: $TESTS_PASSED"
echo "Failed: $TESTS_FAILED"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo "✅ All Mission Control tests passed!"
    exit 0
else
    echo "❌ Some tests failed. Review output above."
    exit 1
fi
