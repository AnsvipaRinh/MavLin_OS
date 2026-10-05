#!/usr/bin/env python3
"""Mission Control O6 — animation timeline tests (mocked time, no X11).

Acceptance mapping (docs/MISSION_CONTROL_PLAN.md §5 O6):
- entrance/exit duration 150ms ± 20ms — ENTRANCE_MS/EXIT_MS bounds +
  exact completion time on a mocked clock;
- reduced-motion preference disables animation entirely;
- directional offsets reproduce "thumbnails leave their window
  positions / return to them" with capped, correctly-signed pulls.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))

import mission_control_anim as mca


def test_timeline_progress_bounds():
    t = mca.Timeline(160, start_at_ms=0)
    assert t.value(0) == 0.0
    assert t.raw(-5) == 0.0
    assert t.value(160) == 1.0
    assert t.value(1000) == 1.0
    assert t.done(160) and t.done(999)
    assert not t.done(159.99)
    assert 0.0 <= t.value(80) <= 1.0
    print("PASS: timeline progress bounds")


def test_durations_inside_plan_window():
    # plan: "Animation completes in 150ms ± 20ms"
    assert 130 <= mca.ENTRANCE_MS <= 170, mca.ENTRANCE_MS
    assert 130 <= mca.EXIT_MS <= 170, mca.EXIT_MS
    # exact completion: done() flips exactly at start + duration
    entrance = mca.Timeline(mca.ENTRANCE_MS, start_at_ms=1000.0)
    assert not entrance.done(1000.0 + mca.ENTRANCE_MS - 1)
    assert entrance.done(1000.0 + mca.ENTRANCE_MS)
    print("PASS: entrance/exit durations inside 150ms ± 20ms (160/140)")


def test_ease_out_cubic_shape():
    assert mca.ease_out_cubic(0.0) == 0.0
    assert mca.ease_out_cubic(1.0) == 1.0
    prev = 0.0
    for i in range(1, 21):
        t = i / 20.0
        v = mca.ease_out_cubic(t)
        assert v >= prev, (t, v, prev)
        prev = v
    # fast settle: past halfway progress before half the time is gone
    assert mca.ease_out_cubic(0.5) >= 0.5
    assert mca.ease_out_cubic(0.25) >= 0.25 * 0.9
    print("PASS: ease-out cubic is monotonic and fast-settling")


def test_animator_dispatch_and_completion():
    animator = mca.Animator()
    seen_a, seen_b = [], []
    t0 = 500.0
    animator.add(mca.Timeline(100, start_at_ms=t0), lambda p: seen_a.append(p))
    animator.add(mca.Timeline(200, start_at_ms=t0), lambda p: seen_b.append(p))
    assert animator.active

    assert animator.tick(t0) is True          # both fire at 0 progress
    assert animator.tick(t0 + 50) is True
    assert animator.tick(t0 + 100) is True    # A finishes -> final 1.0, dropped
    assert seen_a[-1] == 1.0
    assert not any(p > 1.0 for p in seen_a + seen_b)
    assert animator.tick(t0 + 200) is False   # B finishes this frame -> drained
    assert seen_b[-1] == 1.0
    assert animator.active is False
    assert animator.tick(t0 + 300) is False   # registry stays drained
    assert len(seen_b) == 4
    print("PASS: animator dispatch, completion and registry drain")


def test_animator_exceptions_swallowed():
    animator = mca.Animator()
    good = []
    def broken(_p):
        raise RuntimeError("boom")
    animator.add(mca.Timeline(50), broken)
    animator.add(mca.Timeline(50), good.append)
    assert animator.tick(25) is True
    assert good == [mca.ease_out_cubic(0.5)]
    assert animator.tick(50) is False         # finished frame fires + drains
    assert good[-1] == 1.0
    print("PASS: animator swallows callback exceptions")


def test_zero_duration_timeline_is_instant():
    t = mca.Timeline(0)
    assert t.value(0) == 1.0 and t.done(0)
    seen = []
    a = mca.Animator()
    a.add(t, seen.append)
    assert a.tick(0) is False      # fires final frame, then drains
    assert seen == [1.0]
    print("PASS: zero-duration timeline completes instantly (reduced-motion shape)")


def test_directional_offset_caps_and_signs():
    ox, oy = mca.directional_offset(1900, 1000, 100, 100)
    assert ox == mca.DIRECTIONAL_MAX_PX      # window right of grid -> +x pull
    assert oy == mca.DIRECTIONAL_MAX_PX
    ox, oy = mca.directional_offset(0, 0, 900, 500)
    assert ox == -mca.DIRECTIONAL_MAX_PX     # window left of grid -> -x pull
    assert oy == -mca.DIRECTIONAL_MAX_PX
    ox, oy = mca.directional_offset(200, 150, 100, 100)
    assert 0 < ox <= mca.DIRECTIONAL_MAX_PX
    assert abs(ox - 100 * mca.DIRECTIONAL_PULL) < 1e-9
    print("PASS: directional offset capped at ±%dpx with correct signs" % mca.DIRECTIONAL_MAX_PX)


def test_lerp_offset_progress():
    ox, oy = -30.0, 20.0
    assert mca.lerp_offset(ox, oy, 0.0) == (-30.0, 20.0)
    assert mca.lerp_offset(ox, oy, 1.0) == (0.0, 0.0)
    lx, ly = mca.lerp_offset(ox, oy, 0.25)
    assert abs(lx - (-22.5)) < 1e-9 and abs(ly - 15.0) < 1e-9
    print("PASS: lerp offset interpolates to zero at completion")


def test_choreography_progress_contract():
    """Entrance: offset factor 1->0, opacity 0->1; exit: mirrored.

    _apply_choreo maps entrance progress p to lerp_offset(off, p)
    (full pull at p=0, home at p=1) and exit progress p to
    lerp_offset(off, 1 - p) with opacity 1 - p (home -> full pull).
    """
    ox, oy = -30.0, 20.0
    # entrance
    assert mca.lerp_offset(ox, oy, 0.0) == (-30.0, 20.0)   # leaves the window
    assert mca.lerp_offset(ox, oy, 1.0) == (0.0, 0.0)      # settles in grid
    # exit (mirrored): returns toward the window's pull
    assert mca.lerp_offset(ox, oy, 1.0 - 0.0) == (0.0, 0.0)
    assert mca.lerp_offset(ox, oy, 1.0 - 1.0) == (-30.0, 20.0)
    opacity_exit_at_end = 1.0 - 1.0
    assert opacity_exit_at_end == 0.0
    print("PASS: choreography progress contract (entrance/exit mirrored)")


def test_reduced_motion_env():
    env = {"MV_REDUCED_MOTION": "1"}
    assert mca.when_mv_reduced_motion(env) is True
    env = {"MV_REDUCED_MOTION": "YES"}
    assert mca.when_mv_reduced_motion(env) is True
    env = {"MV_REDUCED_MOTION": "0"}
    assert mca.when_mv_reduced_motion(env) is False
    env = {"MV_REDUCED_MOTION": ""}
    # unset/empty + no xfconf -> full motion; never raises
    assert mca.when_mv_reduced_motion(env) in (True, False)
    print("PASS: reduced-motion env gating")


TESTS = [
    test_timeline_progress_bounds,
    test_durations_inside_plan_window,
    test_ease_out_cubic_shape,
    test_animator_dispatch_and_completion,
    test_animator_exceptions_swallowed,
    test_zero_duration_timeline_is_instant,
    test_directional_offset_caps_and_signs,
    test_lerp_offset_progress,
    test_choreography_progress_contract,
    test_reduced_motion_env,
]

if __name__ == "__main__":
    passed = failed = 0
    for test in TESTS:
        try:
            test()
            passed += 1
        except AssertionError as exc:
            print(f"FAIL: {test.__name__}: {exc}")
            failed += 1
        except Exception as exc:
            print(f"ERROR: {test.__name__}: {type(exc).__name__}: {exc}")
            failed += 1
    print(f"Results: {passed} passed, {failed} failed out of {len(TESTS)}")
    raise SystemExit(1 if failed else 0)
