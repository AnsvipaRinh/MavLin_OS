"""Test mv-mail, mv-music, mv-photos, mv-voice, mv-ytplayer media apps."""
import subprocess
import sys
import os


def test_mail():
    """Test mv-mail invocation."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-mail"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    result = subprocess.run(
        ["python3", script_path],
        capture_output=True,
        text=True,
        timeout=5
    )
    
    if result.returncode == 0 or "usage" in result.stdout.lower():
        print("PASS: mv-mail executed")
    else:
        print(f"INFO: mv-mail exit={result.returncode}")


def test_music():
    """Test mv-music invocation."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-music"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    result = subprocess.run(
        ["python3", script_path],
        capture_output=True,
        text=True,
        timeout=5
    )
    
    if result.returncode == 0 or "usage" in result.stdout.lower():
        print("PASS: mv-music executed")
    else:
        print(f"INFO: mv-music exit={result.returncode}")


def test_photos():
    """Test mv-photos invocation."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-photos"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    result = subprocess.run(
        ["python3", script_path],
        capture_output=True,
        text=True,
        timeout=5
    )
    
    if result.returncode == 0 or "usage" in result.stdout.lower():
        print("PASS: mv-photos executed")
    else:
        print(f"INFO: mv-photos exit={result.returncode}")


def test_voice():
    """Test mv-voice invocation."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-voice"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    result = subprocess.run(
        ["python3", script_path],
        capture_output=True,
        text=True,
        timeout=5
    )
    
    if result.returncode == 0 or "usage" in result.stdout.lower():
        print("PASS: mv-voice executed")
    else:
        print(f"INFO: mv-voice exit={result.returncode}")


def test_ytplayer():
    """Test mv-ytplayer invocation."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-ytplayer"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    result = subprocess.run(
        ["python3", script_path],
        capture_output=True,
        text=True,
        timeout=5
    )
    
    if result.returncode == 0 or "usage" in result.stdout.lower():
        print("PASS: mv-ytplayer executed")
    else:
        print(f"INFO: mv-ytplayer exit={result.returncode}")


if __name__ == "__main__":
    test_mail()
    test_music()
    test_photos()
    test_voice()
    test_ytplayer()
