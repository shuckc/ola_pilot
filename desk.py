from array import array
import asyncio
import math
import time
from abc import ABC, abstractmethod

from aio_ola import OlaClient
from rtmidi.midiutil import open_midiinput
from rtmidi.midiconstants import (
    NOTE_ON,
    NOTE_OFF,
    PROGRAM_CHANGE,
    CONTROLLER_CHANGE,
    POLY_AFTERTOUCH,
    CHANNEL_AFTERTOUCH,
)
from functools import partial
from collections import defaultdict
from typing import Optional, TypeAlias, List, MutableSequence

DMX_UNIVERSE_SIZE = 512

UniverseType: TypeAlias = MutableSequence[int]


fixture_class_list = []


def fixture(wrapped):
    fixture_class_list.append(wrapped)
    return wrapped


efx_class_list = []


def register_efx(wrapped):
    efx_class_list.append(wrapped)
    return wrapped


class Trait(ABC):
    @abstractmethod
    def patch(self, data: UniverseType, base: int) -> None:
        pass


# https://blog.saikoled.com/post/44677718712/how-to-convert-from-hsi-to-rgb-white
class RGB(Trait):
    def __init__(self):
        self.red = ByteChannelProp()
        self.green = ByteChannelProp()
        self.blue = ByteChannelProp()

    def set_red(self, red):
        # TODO ?
        # from HSV?
        self.red.set(red)

    def set_green(self, green):
        self.green.set(green)

    def set_blue(self, blue):
        self.blue.set(blue)

    def get_approx_rgb(self):
        return self.red.pos, self.green.pos, self.blue.pos

    def get_hex(self):
        r,g,b = self.get_approx_rgb()
        return f"#{r:02X}{g:02X}{b:02X}"

    def patch(self, data: UniverseType, base: int) -> None:
        self.red.patch(data, base + 0)
        self.green.patch(data, base + 1)
        self.blue.patch(data, base + 2)


class RGBW(RGB):
    def __init__(self):
        super().__init__()
        self.white = ByteChannelProp()

    def patch(self, data: UniverseType, base: int) -> None:
        super().patch(data, base)
        self.white.patch(data, base + 3)

    def set_white(self, white):
        self.white.set(white)

    def get_approx_rgb(self):
        r,g,b = super().get_approx_rgb()
        w = self.white.pos
        # scale down rgb components by w intensity, and add w to all channels equally
        return int(r * (255 - w) / 255 + w), int(g * (255 - w)/255 + w), int(b * (255 - w)/255 + w)


class RGBA(RGB):
    def __init__(self):
        super().__init__()
        self.amber = ByteChannelProp()

    def set_amber(self, amber):
        self.amber.set(amber)

    def patch(self, data: UniverseType, base: int) -> None:
        super().patch(data, base)
        self.amber.patch(data, base + 3)

    def get_approx_rgb(self):
        r,g,b = super().get_approx_rgb()
        a = self.amber.pos
        # scale down rgb components by amber intensity, and add a weighted by 255,191,0 (#FFBF00) to channels
        return int(r * (255 - a)/255 + a), int(g * (255 - a)/255 + a*(191/255)), int(b * (255 - a)/255)


class PTPos(Trait):
    def __init__(self, pan_range=540, tilt_range=180):
        # self._data = array("B", [0] * 4)
        self._pan_range = pan_range
        self._tilt_range = tilt_range
        self.pan = FineChannelProp()
        self.tilt = FineChannelProp()

    def set_rpos_deg(self, pan, tilt):
        # arguments in degress relative to straight down
        pan = 0xFFFF * (0.5 + (pan / self._pan_range))
        tilt = 0xFFFF * (0.5 + (tilt / self._tilt_range))
        self.set_pos(pan, tilt)

    def set_pos(self, pan, tilt):
        self.pan.set(pan)
        self.tilt.set(tilt)

    def patch(self, data: UniverseType, base: int) -> None:
        self.pan.patch(data, base + 0)
        self.tilt.patch(data, base + 2)


class EFX:
    def __init__(self, target):
        self.enabled = OnOffChannel()
        self.target = target
        self.can_act_on = [Trait]

    def tick(self, counter):
        pass


@register_efx
class WavePT_EFX(EFX):
    def __init__(self, target, wave=0):
        self.wave = Channel(wave)
        self.orientation = 0
        super().__init__(target)
        self.can_act_on = [PTPos]
        self.pan_midi = 0
        self.tilt_midi = 0
        self.offset = PTPos()

    def tick(self, counter):
        ms = counter
        # wave_p = math.sin(ms) * self.wave
        # magnitude of oscilation
        wave = math.cos(ms) * self.wave.value.pos
        # map to pan and tilt by orientation
        wave_p = wave * math.cos(self.orientation)
        wave_t = wave * math.sin(self.orientation)

        self.target.set_rpos_deg(
            360 * ((self.pan_midi / 127) - 0.5),
            360 * ((self.tilt_midi / 127) - 0.5) + wave,
        )

    def set_pan_midi(self, pan):
        self.pan_midi = pan

    def set_tilt_midi(self, tilt):
        self.tilt_midi = tilt

    def set_wave_deg(self, wave):
        self.wave = wave


# fixture is a set of traits, exposed via. __dict__
# trait is a grouping of channels, each of which exposes a ranged value and
# can be patched into a DMX universe


class Fixture(ABC):
    def __init__(self, ch=0):
        self.universe: Optional[int] = None
        self.base: Optional[int] = None
        self.ch: int = ch

    @abstractmethod
    def patch(self, universe: int, base: int, data: UniverseType) -> None:
        self.universe = universe
        self.base = base


class ChannelProp(ABC):
    def __init__(self, pos_min=0, pos_max=255, pos=0, units=""):
        self.pos_min = pos_min
        self.pos_max = pos_max
        self.pos = pos
        self.data = None
        self.base = 0

    def patch(self, data: UniverseType, base: int):
        self.data = data
        self.base = base
        self.set(self.pos)

    @abstractmethod
    def set(self, value: int):
        pass


class ByteChannelProp(ChannelProp):
    def set(self, value: int):
        self.pos = min(0xFF, max(0, int(value)))
        if self.data:
            self.data[self.base] = value


class FineChannelProp(ChannelProp):
    def __init__(self, pos_min=0, pos_max=0xFFFF, pos=0, units=""):
        super().__init__(pos_min=pos_min, pos_max=pos_max, pos=pos)

    def set(self, value: int):
        self.pos = min(0xFFFF, max(0, int(value)))
        if self.data:
            self.data[self.base] = self.pos >> 8
            self.data[self.base + 1] = self.pos & 0xFF


class Channel(Trait):
    def __init__(self, value=0):
        self.value = ByteChannelProp(pos=value)

    def set(self, value):
        self.value.set(value)

    def patch(self, data: UniverseType, base: int) -> None:
        self.value.patch(data, base)


class IndexedChannel(Channel):
    pass


class OnOffChannel(Trait):
    def __init__(self, value=0):
        self.value = ByteChannelProp(pos=value, pos_max=1)

    def set(self, value):
        self.value.set(value)

    def patch(self, data: UniverseType, base: int) -> None:
        self.value.patch(data, base)


@fixture
class IbizaMini(Fixture):
    def __init__(self):
        super().__init__(ch=19)
        self.pos = PTPos()
        self.wash = RGBW()
        self.spot = Channel()
        self.spot_cw = IndexedChannel()
        self.spot_gobo = IndexedChannel()
        self.light_belt = Channel()
        self.pt_speed = Channel(value=0)
        self.global_dimmer = Channel(value=255)

    def patch(self, universe: int, base: int, data: UniverseType) -> None:
        super().patch(universe, base, data)
        self.pos.patch(data, base + 0)
        self.pt_speed.patch(data, base + 4)
        self.global_dimmer.patch(data, base + 5)
        self.spot.patch(data, base + 6)
        self.spot_cw.patch(data, base + 7)
        self.spot_gobo.patch(data, base + 8)
        self.wash.patch(data, base + 9)
        self.light_belt.patch(data, base + 18)


@fixture
class LedJ7Q5RGBA(Fixture):
    def __init__(self):
        super().__init__(ch=4)
        self.wash = RGBA()

    def patch(self, universe: int, base: int, data: UniverseType) -> None:
        super().patch(universe, base, data)
        self.wash.patch(data, base)


class FixtureController:
    def __init__(self, client, update_interval=25):
        self._update_interval: int = update_interval
        self._client = client
        self.fixtures: List[Fixture] = []
        self.pollable = []
        self.efx = []
        self.init = time.time()
        self.frames = 0
        self.fps: float = 0
        self.target_fps = 1 / self._update_interval * 1000
        self.showtime: float = 0
        self.universes = {}
        self.blackout = False
        self._blackout_buffer = array("B", [0] * DMX_UNIVERSE_SIZE)

    async def run(self):
        self._conn_task = asyncio.create_task(self._client.connect())

        while True:
            await self._tick_once()
            await asyncio.sleep(self._update_interval / 1000.0)

    async def _tick_once(self):
        self.showtime = time.time() - self.init
        self.frames += 1
        self.fps = self.frames / self.showtime

        for pollable in self.pollable + self.efx:
            pollable.tick(self.showtime)

        # Send the DMX data
        for universe, data in self.universes.items():
            if self.blackout:
                await self._client.set_dmx(universe, self._blackout_buffer)
            else:
                await self._client.set_dmx(universe, data)

    def add_fixture(
        self,
        fixture: Fixture,
        universe: Optional[int] = None,
        base: Optional[int] = None,
    ) -> None:
        self.fixtures.append(fixture)
        if universe is not None and base is not None:
            self.patch_fixture(fixture, universe, base)

    def patch_fixture(self, fixture: Fixture, universe=None, base=None):
        univ = self._get_universe(universe)
        fixture.patch(universe, base, data=univ)

    def _get_universe(self, universe: int):
        if not universe in self.universes:
            self.universes[universe] = array("B", [0] * DMX_UNIVERSE_SIZE)
        return self.universes[universe]

    def add_efx(self, efx: EFX):
        self.efx.append(efx)

    def add_pollable(self, pollable):
        self.pollable.append(pollable)

    def set_dmx(self, universe: int, channel: int, value: int):
        univ = self._get_universe(universe)
        univ[channel] = value

    def get_dmx(self, universe, channel):
        if self.blackout:
            return 0
        else:
            return self.universes[universe][channel]

    def __repr__(self):
        s = ""
        for fixture in self.fixtures:
            s = s + f"{fixture.universe} {fixture.base} {fixture}\n"
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
                elif message[0] & 0xF0 == CHANNEL_AFTERTOUCH:
                    pass
                    # print(f"Note touch: ch{channel} note {message[1]}")
                    # self.notes_on[message[1]] = message[2]
                elif message[0] & 0xF0 == POLY_AFTERTOUCH:
                    print(
                        f"Note touch: ch{channel} note {message[1]} velocity {message[2]}"
                    )
                    self.notes_on[message[1]] = message[2]
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
        if not channel in self.cc_last:
            self.cc_last[channel] = 0


def build_show():
    client = OlaClient()

    midiin, port_name = open_midiinput(port="MPK")
    banks = MidiCC(midiin)

    controller = FixtureController(client, update_interval=25)

    mini = IbizaMini()
    mini2 = IbizaMini()
    controller.add_fixture(mini, 1, 20)
    controller.add_fixture(mini2, 1, 40)
    controller.add_pollable(banks)
    controller.add_fixture(par1 := LedJ7Q5RGBA(), 1, 85)
    controller.add_fixture(par2 := LedJ7Q5RGBA(), 1, 79)

    # this sets a raw channel value in the DMX universe, it will
    # be overridden by any patched fixture
    controller.set_dmx(1, 0, 128)

    # mini.wash.set_red(200)
    mini.wash.set_green(200)
    mini.pos.set_rpos_deg(0, 0)
    mini.spot.set(150)

    efx = WavePT_EFX(wave=10, target=mini.pos)
    controller.add_efx(efx)

    par2.wash.set_green(200)

    banks.bind_cc(70, efx.set_pan_midi)
    banks.bind_cc(71, efx.set_tilt_midi)
    banks.bind_cc(72, mini.spot.set)
    banks.bind_cc(73, efx.set_wave_deg)

    # a bus is a subset of traits and fixtures, like a fixture group
    # busses also have an 'enabled' trait.
    # the simplest bus fans out it's trait to all registered fixtures
    # Another time-delays the propagation of values along the fixtures
    # another might export the trait twice as 'start' and 'end' traits and linearly
    # interpolate the difference
    # bus1 = ReplicateBus(['wash'], [mini1, mini2, par1, par2])
    # bus1.wash.set_red(200)
    return controller


async def main():
    print(f"fixtures: {fixture_class_list}")
    print(f"efx: {efx_class_list}")

    controller = build_show()
    print(controller)
    await controller.run()


if __name__ == "__main__":
    asyncio.run(main())
