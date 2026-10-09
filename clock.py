#!/usr/bin/env python3
"""RGB LED Clock: hours in red, minutes in green, seconds in blue on a 12-LED ring."""
from __future__ import annotations

import argparse
import datetime
import importlib
import logging
import signal
import sys
import threading
import time as time_module
from dataclasses import dataclass
from math import pi, sin
from typing import Any, List, Optional, Sequence, Tuple

NUM_LEDS = 12
MAX_BRIGHTNESS = 240

SINE = "sine"
LINEAR = "linear"

# Supported LED drivers: name -> (module path, class name). Imported lazily.
DRIVERS = {
    "ws2801": ("pigredients.ics.ws2801", "WS2801_Chain"),
    "lpd6803": ("pigredients.ics.lpd6803", "LPD6803_Chain"),
    "lpd8806": ("pigredients.ics.lpd8806", "LPD8806_Chain"),
}

log = logging.getLogger("clock")


@dataclass
class RGB:
    """3-part colour value for one LED."""
    r: int = 0
    g: int = 0
    b: int = 0


def interpolate(val: float, op0: float, op1: float, curve: str = LINEAR) -> float:
    """Interpolate an input (0-1) between two output values, linear or sine curve."""
    diff = op1 - op0
    if curve == LINEAR:
        return op0 + diff * val
    if curve == SINE:
        return op0 + diff * sin(val * pi * 0.5)
    raise ValueError("can't interpolate with a curve of type [%s]" % curve)


def calc_bin_vals(pos: float) -> List[Tuple[int, int]]:
    """Return (led index, brightness) pairs for a position 0-12 on the clock face."""
    offset = pos % 1
    rtn = []

    bin1 = int(pos) % NUM_LEDS
    val1 = round(interpolate(offset, MAX_BRIGHTNESS, 0))
    if val1 > 0:
        rtn.append((bin1, val1))

    bin2 = int(pos + 1) % NUM_LEDS
    val2 = round(interpolate(offset, 0, MAX_BRIGHTNESS))
    if val2 > 0:
        rtn.append((bin2, val2))
    return rtn


def is_active(now: datetime.time, on: Optional[datetime.time], off: Optional[datetime.time]) -> bool:
    """Whether the clock should be lit at `now`. Handles windows that cross midnight.

    The window is [on, off). None for either end, or on == off, means always on.
    """
    if on is None or off is None or on == off:
        return True
    if on < off:
        return on <= now < off
    return now >= on or now < off


def get_clock(now: datetime.time, active: bool = True) -> List[RGB]:
    """Build the clock face for the given time. All LEDs are zero when not active."""
    clock = [RGB() for _ in range(NUM_LEDS)]
    if not active:
        return clock

    # positions of hands on the clock face 0-11
    hpos = (now.hour % 12) + now.minute / 60.0 + now.second / 3600.0
    mpos = (now.minute + now.second / 60.0) / 5
    spos = (now.second + now.microsecond / 1000000.0) / 5

    for i, v in calc_bin_vals(hpos):
        clock[i].r = v
    for i, v in calc_bin_vals(mpos):
        clock[i].g = v
    for i, v in calc_bin_vals(spos):
        clock[i].b = v
    return clock


def clamp(value: float) -> int:
    return max(0, min(255, int(value)))


def to_frame(clock: Sequence[RGB], blue_scale: float) -> List[Tuple[int, int, int]]:
    """Convert a clock face to driver channel values (clamped 0-255 ints)."""
    return [(clamp(c.r), clamp(c.g), clamp(c.b * blue_scale)) for c in clock]


class ConsoleChain:
    """Stand-in for a pigredients chain that prints frames to stdout (--dry-run)."""

    def __init__(self, ics_in_chain: int = NUM_LEDS) -> None:
        self.leds = [[0, 0, 0] for _ in range(ics_in_chain)]

    def set_ic(self, i: int, rgb: Sequence[int]) -> None:
        self.leds[i] = list(rgb)

    def set(self) -> None:
        stamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(stamp, " ".join("%3d,%3d,%3d" % tuple(led) for led in self.leds), flush=True)


def load_chain(driver: str) -> Any:
    """Lazily import the pigredients driver and build an LED chain."""
    module_path, class_name = DRIVERS[driver]
    cls = getattr(importlib.import_module(module_path), class_name)
    return cls(ics_in_chain=NUM_LEDS)


def write_frame(chain: Any, frame: Sequence[Tuple[int, int, int]]) -> None:
    for i, (r, g, b) in enumerate(frame):
        chain.set_ic(i, [r, g, b])
    chain.set()


def parse_hhmm(text: str) -> datetime.time:
    """argparse type: HH:MM -> datetime.time."""
    try:
        return datetime.datetime.strptime(text, "%H:%M").time()
    except ValueError:
        raise argparse.ArgumentTypeError("invalid time %r, expected HH:MM (00:00-23:59)" % text)


def positive_float(text: str) -> float:
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError("invalid number %r" % text)
    if not value > 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return value


def non_negative_float(text: str) -> float:
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError("invalid number %r" % text)
    if not value >= 0:
        raise argparse.ArgumentTypeError("must be 0 or greater")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RGB LED Clock.")
    parser.add_argument("--type", dest="driver_type", type=str.lower, choices=sorted(DRIVERS),
                        default="lpd6803", help="LED driver chip (default: %(default)s)")
    parser.add_argument("--on", type=parse_hhmm, default=datetime.time(6, 0),
                        help="time of day to switch on, HH:MM (default: 06:00)")
    parser.add_argument("--off", type=parse_hhmm, default=datetime.time(22, 55),
                        help="time of day to switch off, HH:MM (default: 22:55)")
    parser.add_argument("--always-on", action="store_true", help="ignore --on/--off")
    parser.add_argument("--refresh-hz", type=positive_float, default=10.0,
                        help="display refresh rate in Hz (default: %(default)s)")
    parser.add_argument("--blue-scale", type=non_negative_float, default=0.7,
                        help="scale applied to the blue channel (default: %(default)s)")
    parser.add_argument("--dry-run", action="store_true",
                        help="don't touch hardware; print each changed frame to stdout")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    return parser


def run(chain: Any, args: argparse.Namespace, stop: threading.Event) -> None:
    """Redraw at refresh rate until `stop` is set; always blank the LEDs on exit."""
    on = None if args.always_on else args.on
    off = None if args.always_on else args.off
    period = 1.0 / args.refresh_hz
    last_frame = None
    try:
        next_tick = time_module.monotonic()
        while not stop.is_set():
            now = datetime.datetime.now().time()
            frame = to_frame(get_clock(now, is_active(now, on, off)), args.blue_scale)
            if frame != last_frame:
                log.debug("frame at %s: %s", now.strftime("%H:%M:%S.%f"), frame)
                write_frame(chain, frame)
                last_frame = frame
            # sleep until the next tick boundary (no drift); resync if we fell behind
            next_tick = max(next_tick + period, time_module.monotonic())
            stop.wait(max(0.0, next_tick - time_module.monotonic()))
    finally:
        log.info("shutting down, blanking LEDs")
        write_frame(chain, [(0, 0, 0)] * NUM_LEDS)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    window = "always on" if args.always_on else "%s-%s" % (args.on.strftime("%H:%M"), args.off.strftime("%H:%M"))
    log.info("starting: driver=%s window=%s refresh=%.1fHz%s", args.driver_type, window,
             args.refresh_hz, " (dry run)" if args.dry_run else "")

    chain = ConsoleChain() if args.dry_run else load_chain(args.driver_type)

    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda signum, frame: stop.set())

    run(chain, args, stop)
    return 0


if __name__ == "__main__":
    sys.exit(main())
