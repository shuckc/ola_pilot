from array import array
import asyncio
import math
import time

from aio_ola import OlaClient
from rtmidi.midiutil import open_midiinput
from rtmidi.midiconstants import NOTE_ON, NOTE_OFF, PROGRAM_CHANGE, CONTROLLER_CHANGE
from functools import partial
from collections import defaultdict

DMX_UNIVERSE_SIZE = 512


# https://blog.saikoled.com/post/44677718712/how-to-convert-from-hsi-to-rgb-white
class RGBW:
    def __init__(self):
        self._data = array("B", [0] * 4)

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
        self._data = array("B", [0] * 4)
        self.pan_range = pan_range
        self.tilt_range = tilt_range

    def set_rpos_deg(self, pan, tilt):
        # arguments in degress relative to straight down
        pan = 0xFFFF * (0.5 + (pan / self.pan_range))
        tilt = 0xFFFF * (0.5 + (tilt / self.tilt_range))
        self.set_pos(pan, tilt)

    def set_pos(self, pan, tilt):
        pan = min(0xFFFF, max(0, int(pan)))
        tilt = min(0xFFFF, max(0, int(tilt)))
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
        self.pan = 0
        super().__init__()

    def tick(self, counter):
        ms = counter
        wave = math.sin(ms) * self.wave
        # print(f"wave: {wave} {self.pan}")
        self.set_rpos_deg(360 * ((self.pan / 127) - 0.5), wave)

    def set_pan(self, pan):
        self.pan = pan

    def set_wave_deg(self, wave):
        self.wave = wave


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
        for p in [
            self.pos,
            self.wash,
            self.spot,
            self.spot_colour,
            self.spot_gobo,
            self.light_belt,
        ]:
            p.tick(counter)
        universe[base + 0 : base + 4] = self.pos.as_dmx_PPTT()
        universe[base + 4] = 0  # pan/tilt speed
        universe[base + 5] = 255  # global dimmer
        universe[base + 6] = self.spot.as_dmx()
        universe[base + 7] = self.spot_colour.as_dmx()
        universe[base + 8] = self.spot_gobo.as_dmx()
        # RGBW
        universe[base + 9 : base + 13] = self.wash.as_dmx_RGBW()
        universe[base + 13] = 0  # strobe
        universe[base + 14] = 0  # wash effect
        universe[base + 15] = 0  # auto/sound
        universe[base + 16] = 0  # effect speed
        universe[base + 17] = 0  # PT control
        universe[base + 18] = self.light_belt.as_dmx()


class FixtureController:
    def __init__(self, client, update_interval=25):
        self._update_interval = update_interval
        self._client = client
        self.fixtures = []
        self.pollable = []
        self.init = time.time()
        self.frames = 0
        self.fps = 0
        self.target_fps = 1 / self._update_interval * 1000
        self.showtime = 0
        self.universes = {}
        self.blackout = False
        self._blackout_buffer = array("B", [0] * DMX_UNIVERSE_SIZE)

    async def run(self):
        await self._client.connect()

        while True:
            self.showtime = time.time() - self.init
            self.frames += 1
            self.fps = self.frames / self.showtime

            for pollable in self.pollable:
                pollable.tick(self.showtime)

            for universe, base, fixture in self.fixtures:
                fixture.write(self.universes[universe], base, self.showtime)

            # Send the DMX data
            for universe, data in self.universes.items():
                if self.blackout:
                    await self._client.set_dmx(universe, self._blackout_buffer)
                else:
                    await self._client.set_dmx(universe, data)
            await asyncio.sleep(self._update_interval / 1000.0)

    def add_fixture(self, universe: int, base: int, fixture: Fixture):
        self.fixtures.append((universe, base, fixture))
        if not universe in self.universes:
            self.universes[universe] = array("B", [0] * DMX_UNIVERSE_SIZE)

    def add_pollable(self, pollable):
        self.pollable.append(pollable)

    def __repr__(self):
        s = ""
        for fixture, base, universe in self.fixtures:
            s = s + f"{universe} {base} {fixture}\n"
        s = (
            s
            + f"time={time.time()} showtime={self.showtime} fps={self.fps} target={self.target_fps}"
        )
        return s


class MidiCC:
    def __init__(self, midi_in):
        self.midi_in = midi_in
        self.notes_on = {}
        self.cc_last = {}
        self.cc_pending = {}
        self.cc_listeners = defaultdict(list)

    def tick(self, counter):
        while True:
            msg = self.midi_in.get_message()
            if msg:
                message, timedelta = msg
                channel = message[0] & 0x0F
                if message[0] & 0xF0 == CONTROLLER_CHANGE:
                    print(f"CC: {channel} {message[1]} = {message[2]}")
                    self.cc_last[message[1]] = message[2]
                    self.cc_pending[message[1]] = message[2]
                elif message[0] & 0xF0 == NOTE_ON:
                    print(
                        f"Note On: ch{channel} note {message[1]} velocity {message[2]}"
                    )
                    self.notes_on[message[1]] = message[2]
                elif message[0] & 0xF0 == NOTE_OFF:
                    print(f"Note Off: ch{channel} note {message[1]}")
                    del self.notes_on[message[1]]
                else:
                    print(f"unknown midi event: {msg} {hex(msg[0][0])}")
            else:
                break

        for k, v in self.cc_pending.items():
            for listener in self.cc_listeners[k]:
                listener(v)

        self.cc_pending.clear()

    def __repr__(self):
        return f"CC: {self.cc_last}\nNotes: {self.notes_on}"

    # TODO: some sort of auto scaling, ie. bind to a 'pin' rather than a callback fn
    def bind_cc(self, channel, listener):
        self.cc_listeners[channel].append(listener)


def build_show():
    client = OlaClient()

    midiin, port_name = open_midiinput(port="MPK")
    banks = MidiCC(midiin)

    controller = FixtureController(client, update_interval=25)

    mini = IbizaMini()
    mini2 = IbizaMini()
    controller.add_fixture(1, 20, mini)
    controller.add_fixture(1, 40, mini2)
    controller.add_pollable(banks)

    # mini.wash.set_red(200)
    mini.wash.set_green(200)
    mini.pos.set_rpos_deg(0, 0)
    mini.pos = WavePTPos(wave=20)

    banks.bind_cc(70, mini.pos.set_pan)
    banks.bind_cc(71, mini.pos.set_wave_deg)
    banks.bind_cc(72, mini.spot.set)

    mini.spot.set(150)
    return controller


async def main():
    controller = build_show()
    print(controller)
    await controller.run()


if __name__ == "__main__":
    asyncio.run(main())
