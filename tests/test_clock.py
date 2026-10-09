import argparse
import subprocess
import sys
from datetime import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import clock  # noqa: E402


def lit(frame):
    """Map of led index -> RGB for LEDs that are not fully off."""
    return {i: c for i, c in enumerate(frame) if (c.r, c.g, c.b) != (0, 0, 0)}


# --- is_active ---------------------------------------------------------------

def test_is_active_normal_window():
    on, off = time(6, 0), time(22, 55)
    assert clock.is_active(time(12, 0), on, off)
    assert not clock.is_active(time(3, 0), on, off)
    assert not clock.is_active(time(23, 30), on, off)


def test_is_active_midnight_wrap():
    on, off = time(18, 0), time(2, 0)
    assert clock.is_active(time(19, 0), on, off)
    assert clock.is_active(time(23, 59), on, off)
    assert clock.is_active(time(0, 30), on, off)
    assert not clock.is_active(time(2, 30), on, off)
    assert not clock.is_active(time(12, 0), on, off)


def test_is_active_boundaries_on_inclusive_off_exclusive():
    for on, off in ((time(6, 0), time(22, 55)), (time(22, 55), time(6, 0))):
        assert clock.is_active(on, on, off)
        assert not clock.is_active(off, on, off)


def test_is_active_always_on_cases():
    assert clock.is_active(time(3, 0), None, None)
    assert clock.is_active(time(3, 0), None, time(2, 0))
    assert clock.is_active(time(3, 0), time(6, 0), None)
    assert clock.is_active(time(3, 0), time(6, 0), time(6, 0))


# --- calc_bin_vals -----------------------------------------------------------

def test_calc_bin_vals_integer_position():
    assert clock.calc_bin_vals(0) == [(0, 240)]
    assert clock.calc_bin_vals(5) == [(5, 240)]


def test_calc_bin_vals_half_position():
    assert clock.calc_bin_vals(2.5) == [(2, 120), (3, 120)]


def test_calc_bin_vals_wraps_11_to_0():
    assert clock.calc_bin_vals(11.5) == [(11, 120), (0, 120)]
    assert clock.calc_bin_vals(11) == [(11, 240)]


# --- get_clock ---------------------------------------------------------------

def test_get_clock_returns_twelve_leds():
    assert len(clock.get_clock(time(1, 2, 3))) == 12


def test_get_clock_noon():
    # all three hands point at LED 0
    assert lit(clock.get_clock(time(12, 0, 0))) == {0: clock.RGB(240, 240, 240)}


def test_get_clock_three_oclock():
    face = clock.get_clock(time(3, 0, 0))
    assert face[3].r == 240
    assert face[0].g == 240 and face[0].b == 240
    assert face[3].g == 0 and face[3].b == 0
    assert len(lit(face)) == 2


def test_get_clock_09_30_15():
    face = clock.get_clock(time(9, 30, 15))
    # hour hand: 9.5 -> LEDs 9 and 10 half each
    assert face[9].r == pytest.approx(120, abs=2) and face[10].r == pytest.approx(120, abs=2)
    # minute hand: (30 + 15/60) / 5 = 6.05 -> mostly LED 6
    assert face[6].g > face[7].g > 0
    # second hand: 15 s -> 3.0 -> LED 3 fully
    assert face[3].b == 240
    assert sum(c.r > 0 for c in face) == 2
    assert sum(c.b > 0 for c in face) == 1


def test_get_clock_hour_hand_uses_seconds_as_float():
    # 5s past: 3600s/hour so second term is tiny but not integer-divided away
    a = clock.get_clock(time(1, 0, 0))
    b = clock.get_clock(time(1, 59, 59))
    assert a[1].r == 240
    assert b[2].r > 230  # almost at 2 o'clock


def test_get_clock_inactive_is_all_zero():
    assert lit(clock.get_clock(time(9, 30, 15), active=False)) == {}


# --- interpolate -------------------------------------------------------------

def test_interpolate_curves():
    assert clock.interpolate(0.5, 0, 100) == 50
    assert clock.interpolate(1, 0, 100, clock.SINE) == pytest.approx(100)


def test_interpolate_invalid_curve_raises():
    with pytest.raises(ValueError):
        clock.interpolate(0.5, 0, 1, "cubic")


# --- frame conversion / CLI --------------------------------------------------

def test_to_frame_scales_blue_and_clamps():
    frame = clock.to_frame([clock.RGB(300, -5, 200)], 0.5)
    assert frame == [(255, 0, 100)]
    assert clock.to_frame([clock.RGB(0, 0, 240)], 2.0) == [(0, 0, 255)]


def test_parse_hhmm_accepts_valid():
    assert clock.parse_hhmm("06:00") == time(6, 0)
    assert clock.parse_hhmm("22:55") == time(22, 55)


@pytest.mark.parametrize("bad", ["25:00", "abc", "", "12:60"])
def test_parse_hhmm_rejects_invalid(bad):
    with pytest.raises(argparse.ArgumentTypeError):
        clock.parse_hhmm(bad)


def test_parser_defaults_and_driver_case_insensitive():
    args = clock.build_parser().parse_args(["--type", "WS2801"])
    assert args.driver_type == "ws2801"
    assert args.on == time(6, 0) and args.off == time(22, 55)
    assert args.refresh_hz == 10 and args.blue_scale == 0.7


def test_lpd8806_is_a_valid_driver():
    assert clock.DRIVERS["lpd8806"] == ("pigredients.ics.lpd8806", "LPD8806_Chain")


def test_import_is_lazy():
    code = "import sys, clock; sys.exit(1 if any(m.split('.')[0] == 'pigredients' for m in sys.modules) else 0)"
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT)
    assert result.returncode == 0
