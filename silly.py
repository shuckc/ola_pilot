from array import array
from ola.ClientWrapper import ClientWrapper
from ola.DMXConstants import (DMX_MAX_SLOT_VALUE, DMX_MIN_SLOT_VALUE, DMX_UNIVERSE_SIZE)
import math
import time

def onDmxSent(state):
    if not state.Succeeded():
        wrapper.Stop()
    # print(state)

class RGBW:
    def __init__(self):
        self._data = array('B', [DMX_MIN_SLOT_VALUE]*4)

    def set_red(self, red):
        # TODO ?
        # from HSV?
        self._data[0] = red
    def set_green(self, green):
        self._data[1] = green
    def tick(self, counter):
        pass


    def as_dmx_RGBW(self):
        return self._data

class PTPos:
    def __init__(self, pan_range=540, tilt_range=180):
        self._data = array('B', [DMX_MIN_SLOT_VALUE]*4)
        self.pan_range = pan_range
        self.tilt_range = tilt_range
    def set_rpos_deg(self, pan, tilt):
        # arguments in degress relative to straight down
        pan = 0xFFFF * (0.5 + (pan/self.pan_range))
        tilt = 0xFFFF * (0.5 + (tilt/self.tilt_range))
        self.set_pos(pan, tilt)

    def set_pos(self, pan, tilt):
        pan = int(pan)
        tilt = int(tilt)
        self._data[0] = pan >> 8
        self._data[1] = pan & 0xFF
        self._data[2] = tilt >> 8
        self._data[3] = tilt & 0xFF

    def tick(self, counter):
        pass

    def as_dmx_PPTT(self):
        return self._data


class WavePTPos(PTPos):
    def __init__(self, wave=10):
        self.wave = wave
        super().__init__()

    def tick(self, counter):
        ms = counter/1000
        wave = math.sin(ms) * self.wave
        self.set_rpos_deg(0, wave)


class Fixture:
    def __init__(self):
        pass
    def write(universe, base, counter):
        pass

class Channel:
    def __init__(self):
        self.value = 0
    def set(self, value):
        self.value = value
    def as_dmx(self):
        return self.value
    def tick(self, counter):
        pass

class IndexedChannel(Channel):
    pass

class IbizaMini(Fixture):
    def __init__(self):
        self.pos = PTPos()
        self.wash = RGBW()
        self.spot = Channel()
        self.spot_colour = IndexedChannel()
        self.spot_gobo = IndexedChannel()
        self.light_belt = Channel()

    def write(self, universe, base, counter):
        self.pos.tick(counter)
        self.wash.tick(counter)
        self.spot_colour.tick(counter)
        self.spot_gobo.tick(counter)
        self.light_belt.tick(counter)
        universe[base+0:base+4] = self.pos.as_dmx_PPTT()
        universe[base+4] = 5 # pan/tilt speed
        universe[base+5] = 255 # global dimmer
        universe[base+6] = self.spot.as_dmx()
        universe[base+7] = self.spot_colour.as_dmx()
        universe[base+8] = self.spot_gobo.as_dmx()
        # RGBW
        universe[base+9:base+13] = self.wash.as_dmx_RGBW()
        universe[base+13] = 0 # strobe
        universe[base+14] = 0 # wash effect
        universe[base+15] = 0 # auto/sound
        universe[base+16] = 0 # effect speed
        universe[base+17] = 0 # PT control
        universe[base+18] = self.light_belt.as_dmx()


class FixtureController:
    def __init__(self, client_wrapper, universe=1, update_interval=25):
        self._universe = universe
        self._update_interval = update_interval
        self._data = array('B', [DMX_MIN_SLOT_VALUE] * DMX_UNIVERSE_SIZE)
        self._wrapper = client_wrapper
        self._client = client_wrapper.Client()
        self._wrapper.AddEvent(self._update_interval, self.update_dmx)
        self._counter = 0
        self.fixtures = []
        self.init = time.time()

    def update_dmx(self):
        """
        This function gets called periodically based on UPDATE_INTERVAL
        """
        # reschedule our event
        self._wrapper.AddEvent(self._update_interval, self.update_dmx)

        for fixture, base in self.fixtures:
            fixture.write(self._data, base, self._counter)
        self._counter = self._counter + self._update_interval

        # Send the DMX data
        self._client.SendDmx(self._universe, self._data)

        print(f"time={time.time()} elapsed={time.time() - self.init} counter={self._counter/1000} slip={time.time()-self.init - self._counter/1000}")


    def add_fixture(self, fixture: Fixture, base: int):
        self.fixtures.append((fixture, base))

    def __repr__(self):
        for fixture, base in self.fixtures:
            print(f"{base} {fixture}")
        return ""

if __name__ == '__main__':
    wrapper = ClientWrapper()
    controller = FixtureController(wrapper, universe=1, update_interval=30)
    # wrapper.AddEvent(SHUTDOWN_INTERVAL, wrapper.Stop)

    mini = IbizaMini()
    controller.add_fixture(mini, 20)

    # mini.wash.set_red(200)
    mini.wash.set_green(200)
    mini.pos.set_rpos_deg(0,0)
    mini.pos = WavePTPos(wave=20)
    mini.spot.set(150)

    print(mini)
    print(controller)

    wrapper.Run()
