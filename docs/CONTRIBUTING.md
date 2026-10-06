# Contributing to MavLinOS

Thank you for contributing to MavLinOS! This guide will help you get started.

## Quick Start for Developers

```bash
# Clone the repo
git clone https://github.com/AnsvipaRinh/MavLinOS.git
cd MavLinOS

# Install dependencies
sudo apt install python3-gi gir1.2-gtk-3.0 imagemagick wmctrl xdotool python3-ewmh python3-xlib

# Run tests
make test-mission-control
```

## Development Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
```

### 2. Make Your Changes

Follow the project structure:
- **CLI helpers**: `packages/mavericks-apps/src/mavericks-apps/bin/`
- **Tests**: `packages/mavericks-apps/src/mavericks-apps/tests/` or `tests/`
- **Docs**: `docs/`
- **Configs**: `configs/desktop/xfce/`

### 3. Write Tests

Every new feature needs tests:

```bash
# Example: new MC helper
python3 packages/mavericks-apps/src/mavericks-apps/tests/test_mission_control_your_feature.py
```

### 4. Run Tests

```bash
# Full test suite
make test-mission-control

# Or specific test
python3 packages/mavericks-apps/src/mavericks-apps/tests/test_mission_control_gui.py
```

### 5. Update Documentation

If you add a feature:
- Update `docs/KEYBOARD.md` for keyboard shortcuts
- Update `docs/MISSION_CONTROL.md` for MC features
- Update `docs/QUICKSTART.md` for user-facing changes
- Update `README.md` if needed

### 6. Commit Your Changes

```bash
git add .
git commit -m "feat: add your feature description

Claim: issue #X (optional)

- Detail 1
- Detail 2
- Detail 3"
```

### 7. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Then create a pull request on GitHub.

## Coding Standards

### Python Helpers

```python
#!/usr/bin/env python3
"""Helper name - short description.

Usage: helper-name <args>

Longer description if needed.
"""
import sys
import argparse

def main():
    parser = argparse.ArgumentParser(description="Helper description")
    parser.add_argument("--debug", action="store_true", help="Debug mode")
    args = parser.parse_args()
    
    # Your code here
    pass

if __name__ == "__main__":
    main()
```

### Tests

```python
"""Test helper name."""
import subprocess
import sys
import os


def test_something():
    """Test that something works."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/your-helper"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    result = subprocess.run(
        ["python3", script_path, "--arg"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0, f"Should succeed: {result.stderr}"
    print("PASS: your test description")


if __name__ == "__main__":
    test_something()
```

### Documentation

Use Markdown with:
- Clear headings (`##`, `###`)
- Code blocks with language (```bash, ```python)
- Tables for comparisons
- Links to related docs

## Testing Guidelines

### Unit Tests

Test individual helpers:
```bash
python3 packages/mavericks-apps/src/mavericks-apps/tests/test_mission_control_gui.py
```

### Integration Tests

Test helpers working together:
```bash
python3 packages/mavericks-apps/src/mavericks-apps/tests/test_mission_control_overview.py
```

### CI Tests

Run full CI suite:
```bash
./ci/run-all-tests.sh
```

## Common Tasks

### Add a New Helper

1. Create `bin/mv-your-helper`
2. Make it executable: `chmod +x bin/mv-your-helper`
3. Add to `MISSION_CONTROL_Makefile` HELPERS list
4. Write tests
5. Update docs

### Add a Keyboard Shortcut

1. Edit `configs/desktop/xfce/xfce4-panel.xml`
2. Update `docs/KEYBOARD.md`
3. Add test if needed

### Add Documentation

1. Create `docs/YOUR-DOC.md`
2. Link from README or relevant doc
3. Update table of contents if applicable

## Questions?

- **First time?** See [`docs/QUICKSTART.md`](QUICKSTART.md)
- **Keyboard shortcuts?** See [`docs/KEYBOARD.md`](KEYBOARD.md)
- **Mission Control?** See [`docs/MISSION_CONTROL.md`](MISSION_CONTROL.md)
- **Troubleshooting?** See [`docs/TROUBLESHOOTING.md`](TROUBLESHOOTING.md)

## Thank You!

Every contribution makes MavLinOS better. Thank you for your time and effort! 🎉
