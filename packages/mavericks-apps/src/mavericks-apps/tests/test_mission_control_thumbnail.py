#!/usr/bin/env python3
"""Headless unit tests for Mission Control thumbnail capture."""
import os
import sys
from unittest.mock import patch
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
import mission_control_thumbnail as mc

def test_mask_shift():
    assert mc._mask_shift(0x00FF0000) == (16, 8)
    assert mc._mask_shift(0x0000FF00) == (8, 8)
    assert mc._mask_shift(0x000000FF) == (0, 8)
    assert mc._mask_shift(0) == (0, 0)

def test_scale_channel():
    assert mc._scale_channel(255, 8) == 255
    assert mc._scale_channel(31, 5) == 255
    assert mc._scale_channel(0, 5) == 0

def test_image_to_rgb_32bit():
    image = mc._XImage()
    image.width, image.height = 1, 1
    image.bits_per_pixel, image.bytes_per_line, image.byte_order = 32, 4, 0
    image.red_mask, image.green_mask, image.blue_mask = 0x00FF0000, 0x0000FF00, 0x000000FF
    pixel = (0x12 << 16) | (0x34 << 8) | 0x56
    image.data = (mc.ctypes.c_ubyte * 4).from_buffer_copy(pixel.to_bytes(4, "little"))
    assert bytes(mc._image_to_rgb(image)) == b"\x12\x34\x56"

def test_image_to_rgb_16bit():
    image = mc._XImage()
    image.width, image.height = 1, 1
    image.bits_per_pixel, image.bytes_per_line, image.byte_order = 16, 2, 0
    image.red_mask, image.green_mask, image.blue_mask = 0xF800, 0x07E0, 0x001F
    image.data = (mc.ctypes.c_ubyte * 2).from_buffer_copy((0xF800).to_bytes(2, "little"))
    assert bytes(mc._image_to_rgb(image)) == b"\xFF\x00\x00"

def test_capture_failure_without_x11():
    with patch.object(mc, "_load_x11", side_effect=RuntimeError("no X11")):
        assert mc.capture_window(1) is None

TESTS = [test_mask_shift, test_scale_channel, test_image_to_rgb_32bit,
         test_image_to_rgb_16bit, test_capture_failure_without_x11]

if __name__ == "__main__":
    for test in TESTS:
        test()
    print(f"PASS: {len(TESTS)} Mission Control thumbnail tests")
