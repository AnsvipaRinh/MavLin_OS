#!/bin/bash
# Main CI workflow - runs all test suites

set -e

echo "========================================"
echo "MavLinOS CI - Full Test Suite"
echo "========================================"
echo ""

# Mission Control tests
echo "🎯 Running Mission Control tests..."
./ci/test-mission-control.sh
echo ""

# F3 binding test
echo "🔗 Running F3 binding test..."
./ci/test-f3-binding.sh
echo ""

echo "========================================"
echo "✅ All CI tests passed!"
echo "========================================"
