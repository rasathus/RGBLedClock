import datetime
import argparse

from time import sleep
from math import sin, pi

stop_time = datetime.time(hour=22, minute=55, second=00)
start_time = datetime.time(hour=06, minute=00, second=00)


class rgb:
    """ rgb class for storing 3-part rgb colour values """
    def __init__(self, r=0, g=0, b=0):
        self.r = r
        self.g = g
        self.b = b

    def __str__(self):
        return "rgb(%d,%d,%d)" % (self.r, self.g, self.b)

SINE = "sine"
LINEAR = "linear"
# Currently supported led drivers
valid_led_drivers = ['ws2801', 'lpd6803', 'lpd8806']


def interpolate(val, op0, op1, curve=LINEAR):
    # interpolate an input between two given output values. supports linear and sine curves
    diff = op1-op0
    if curve == LINEAR:
        rtn = op0+(diff*val)
    elif curve == SINE:
        rtn = op0+(diff*sin(val*pi*.5))
    else:
        raise Exception("can't interpolate with a curve of type [%s]" % curve)
    return rtn


def calcBinVals(pos):
    # helper function to return the bins and bin values for a given position on the clock face
    offset = pos % 1
    rtn = []

    bin1 = int(pos) % 12
    val1 = round(interpolate(offset, 240, 0))
    if val1 > 0:
        rtn.append((bin1, val1))

    bin2 = int(pos + 1) % 12
    val2 = round(interpolate(offset, 0, 240))
    if val2 > 0:
        rtn.append((bin2, val2))
    return rtn


def getclock(when):
    # build clock face for the given time
    clock = [rgb() for i in xrange(12)]

    # positions of hands on the clock face 0-11
    hpos = (when.hour % 12) + when.minute / 60.0 + when.second / 3600
    mpos = (when.minute + when.second / 60.0) / 5
    spos = (when.second + when.microsecond / 1000000.0) / 5

    # write the rgb values onto the clock face
    # If the user has set a stop_time, evaluate our stop and start window.
    if stop_time is not None:
        if start_time < when < stop_time:
            reduction_multiplier = 1
        else:
            # if we're outside our run times, set to zero.
            reduction_multiplier = 0
    else:
        # if not stop_time is set just run all the time.
        reduction_multiplier = 1

    for b in calcBinVals(hpos):
        clock[b[0]].r = b[1]*reduction_multiplier

    for b in calcBinVals(mpos):
        clock[b[0]].g = b[1]*reduction_multiplier

    for b in calcBinVals(spos):
        clock[b[0]].b = b[1]*reduction_multiplier

    return clock

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='RGB LED Clock.')

    parser.add_argument('--type', action="store", dest="driver_type", required=False, help='The model number of the LED driver, eg. ws2801 or lpd6803. defaults to configuration file.')

    args = parser.parse_args()

    if args.driver_type is not None:
        if args.driver_type.lower() in valid_led_drivers:
            driver_type = args.driver_type.lower()
        else:
            raise Exception("Invalid LED Driver %s specified, implemented types are : %s" % (args.driver_type, valid_led_drivers))
    else:
        # default to lpd6803 for compatibility with argumentless syntax.
        driver_type = 'lpd6803'

    if driver_type == 'ws2801':
        from pigredients.ics import ws2801 as ws2801
        led_chain = ws2801.WS2801_Chain(ics_in_chain=12)
    elif driver_type == 'lpd6803':
        from pigredients.ics import lpd6803 as lpd6803
        led_chain = lpd6803.LPD6803_Chain(ics_in_chain=12)
    # elif driver_type == 'lpd8806':
    #    from pigredients.ics import lpd8806 as lpd8806
    #    led_chain = lpd8806.LPD8806_Chain(ics_in_chain=12)
    last = datetime.datetime.now()
    while True:
        now = datetime.datetime.now().time()
        if now.second != last.second:
            last = now
            clock = getclock(now)
            # print "time %02d:%02d:%02d.%6d" % (now.hour, now.minute, now.second, now.microsecond)
            for i in range(len(clock)):
                # print "Setting led %d, to : %s" % (i, [int(clock[i].r), int(clock[i].g), int(clock[i].b)])
                led_chain.set_ic(i, [int(clock[i].r), int(clock[i].g), int(clock[i].b * 0.7)])
            led_chain.set()
            # print [str(c) for c in clock]
        sleep(0.1)
