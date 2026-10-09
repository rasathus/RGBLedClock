RGBLedClock
===========

The RGB clock project can be used to drive 12 LEDs, which when positioned in a circle can be used as a clock.  More details about the project can be found here ... http://rasathus.blogspot.co.uk/2013/03/a-raspberry-pi-rgb-led-clock.html

## Requirements

- Raspberry Pi running Raspberry Pi OS (or similar) with Python 3.9+
- SPI enabled: `sudo raspi-config` -> Interface Options -> SPI
- 12 RGB LEDs with an LPD6803 (default), WS2801 or LPD8806 driver, wired to SPI
- [`spidev`](https://pypi.org/project/spidev/) and the author's
  [`pigredients`](https://github.com/rasathus/pigredients) library (not on PyPI)

Known prerequisite: `pigredients` needs its Python 3 port
([rasathus/pigredients#7](https://github.com/rasathus/pigredients/pull/7)).
Until that is merged, install it from that branch:
`pip install git+https://github.com/rasathus/pigredients.git@claude/dreamy-babbage-61tlx8`.
`--dry-run` does not need it.

## Install

```sh
sudo git clone https://github.com/rasathus/RGBLedClock.git /opt/rgbclock
sudo pip3 install -r /opt/rgbclock/requirements.txt   # add --break-system-packages, or use a venv, on newer Pi OS

# dedicated user with access to /dev/spidev*
sudo useradd --system --no-create-home --shell /usr/sbin/nologin -G spi rgbclock

# systemd (recommended)
sudo cp /opt/rgbclock/rgbclock.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now rgbclock
```

If you use a venv, point `ExecStart` in the unit at that venv's python.
To change options, edit `ExecStart` in the unit.

Legacy SysV init alternative:

```sh
sudo cp /opt/rgbclock/rgbclock.init /etc/init.d/rgbclock
sudo chmod +x /etc/init.d/rgbclock
sudo update-rc.d rgbclock defaults
sudo /etc/init.d/rgbclock start    # start|stop|restart|status
```

## Usage

```sh
python3 clock.py [options]
```

| Option | Description |
| --- | --- |
| `--type {ws2801,lpd6803,lpd8806}` | LED driver, default `lpd6803` |
| `--on HH:MM` | time LEDs turn on, default `06:00` |
| `--off HH:MM` | time LEDs turn off, default `22:55` (window may cross midnight) |
| `--always-on` | ignore `--on`/`--off` |
| `--refresh-hz FLOAT` | redraw rate, default `10` |
| `--blue-scale FLOAT` | blue channel scale (seconds hand), default `0.7` |
| `--dry-run` | print frames to stdout, no hardware/pigredients needed |
| `-v`, `--verbose` | debug logging |

Try it without any hardware:

```sh
python3 clock.py --dry-run --always-on
```

On SIGTERM the clock blanks the LEDs before exiting.

## The face

- red = hour hand
- green = minute hand
- blue = seconds hand

Each hand cross-fades between the two nearest LEDs, so it glides around the
ring rather than jumping.

## Tests

```sh
python3 -m pytest
```
