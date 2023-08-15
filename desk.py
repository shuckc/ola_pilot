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

from fx import PerlinNoiseEFX
from registration import (
    register_efx,
    fixture,
    fixture_class_list,
    efx_class_list,
    Fixture,
    EFX,
)
from channel import ByteChannelProp, FineChannelProp, UniverseType
from trait import OnOffChannel, PTPos, RGBW, RGBA, RGB, Channel, Trait, IndexedChannel

from fixtures import IbizaMini, LedJ7Q5RGBA

DMX_UNIVERSE_SIZE = 512


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
        if fixture in self.fixtures:
            raise ValueError(f"Fixture already registered {fixture}")
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

    mini0 = IbizaMini()
    mini1 = IbizaMini()
    mini2 = IbizaMini()
    mini3 = IbizaMini()

    controller.add_fixture(mini0, 1, 00)
    controller.add_fixture(mini1, 1, 20)
    controller.add_fixture(mini2, 1, 40)
    controller.add_fixture(mini3, 1, 60)

    controller.add_pollable(banks)
    controller.add_fixture(par1 := LedJ7Q5RGBA(), 1, 85)
    controller.add_fixture(par2 := LedJ7Q5RGBA(), 1, 79)
    controller.add_fixture(par3 := LedJ7Q5RGBA(), 1, 85)
    controller.add_fixture(par4 := LedJ7Q5RGBA(), 1, 90)

    # this sets a raw channel value in the DMX universe, it will
    # be overridden by any patched fixture
    controller.set_dmx(1, 0, 128)

    # mini.wash.set_red(200)
    mini0.wash.set_green(200)
    mini0.pos.set_rpos_deg(0, 0)
    mini0.spot.set(150)

    efx = WavePT_EFX(wave=10, target=mini0.pos)
    controller.add_efx(efx)

    par2.wash.set_green(200)

    banks.bind_cc(70, efx.set_pan_midi)
    banks.bind_cc(71, efx.set_tilt_midi)
    banks.bind_cc(72, mini0.spot.set)
    banks.bind_cc(73, efx.set_wave_deg)

    noise = PerlinNoiseEFX(count=10)
    controller.add_efx(noise)

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
