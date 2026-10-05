#!/bin/bash
# CI gate: verify F3 → mv-mc-gui Mission Control binding
# This ensures the binding is correctly configured and non-breaking

set -e

echo "=== Testing F3 Mission Control binding ==="

# Run Python test
python3 tests/test_f3_mission_control_binding.py

echo "=== F3 binding test passed ==="
