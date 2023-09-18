import argparse
import asyncio
import json
import math
import os
import time
from array import array
from collections import defaultdict
from typing import List, Optional, Dict, Any
import itertools

from rtmidi.midiconstants import (
    CHANNEL_AFTERTOUCH,
    CONTROLLER_CHANGE,
    NOTE_OFF,
    NOTE_ON,
    POLY_AFTERTOUCH,
    PROGRAM_CHANGE,
)
from rtmidi.midiutil import open_midiinput
from fixtures import IbizaMini, LedJ7Q5RGBA
from fx import ColourInterpolateEFX, PerlinNoiseEFX
from registration import (
    EFX,
    Fixture,
    efx_class_list,
    fixture_class_list,
    register_efx,
    ThingWithTraits,
)
from trait import Channel, PTPos

DMX_UNIVERSE_SIZE = 512


@register_efx
class WavePT_EFX(EFX):
    def __init__(self, wave=0):
        self.wave = Channel(wave)
        self.orientation = 0
        super().__init__()
        self.pan_midi = 0
        self.tilt_midi = 0
        self.offset = PTPos()
        self.o0 = PTPos()

    def tick(self, counter):
        ms = counter
        # wave_p = math.sin(ms) * self.wave
        # magnitude of oscilation
        wave = math.cos(ms) * self.wave.value.pos
        # map to pan and tilt by orientation
        wave_p = wave * math.cos(self.orientation)
        wave_t = wave * math.sin(self.orientation)

        self.o0.set_degrees_pos(
            360 * ((self.pan_midi / 127) - 0.5),
            360 * ((self.tilt_midi / 127) - 0.5) + wave,
        )

    def set_pan_midi(self, pan):
        self.pan_midi = pan

    def set_tilt_midi(self, tilt):
        self.tilt_midi = tilt

    def set_wave_deg(self, wave):
        self.wave = wave


class ControllerUniverseOutput:
    async def set_dmx(self, universe: int, buffer):
        pass

    async def connect():
        pass


class Controller:
    def __init__(self, update_interval=25):
        self._update_interval: int = update_interval
        self.outputs = []
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
        self.prefix_counter: Dict[str, itertools.count] = defaultdict(itertools.count)
        self.objects_by_name: Dict[str, ThingWithTraits] = {}
        self.presets = {}
        self.showfile_name: Optional[str] = None

    async def run(self):
        self._conn_task = [asyncio.create_task(o.connect()) for o in self.outputs]

        while True:
            before = time.time()
            await self._tick_once(before)
            next_tick = before + self._update_interval / 1000.0
            await asyncio.sleep(next_tick - time.time())

    async def _tick_once(self, showtime):
        self.showtime = showtime - self.init
        self.frames += 1
        self.fps = self.frames / self.showtime

        for pollable in self.pollable + self.efx:
            pollable.tick(self.showtime)

        # Send the DMX data
        for o in self.outputs:
            for universe, data in self.universes.items():
                if self.blackout:
                    await o.set_dmx(universe, self._blackout_buffer)
                else:
                    await o.set_dmx(universe, data)

    def _own_and_name(self, thing: ThingWithTraits) -> str:
        # take ownership and provide unique name
        uid = thing.name
        if uid is None:
            name = type(thing).__name__
            prefix_count = next(self.prefix_counter[name])
            uid = f"{name}-{prefix_count}"
            thing.set_owner_name(self, uid)
            self.objects_by_name[uid] = thing
        return uid

    def add_fixture(
        self,
        fixture: Fixture,
        universe: Optional[int] = None,
        base: Optional[int] = None,
    ) -> str:
        if fixture in self.fixtures:
            raise ValueError(f"Fixture already registered {fixture}")
        self.fixtures.append(fixture)

        uid = self._own_and_name(fixture)

        if universe is not None and base is not None:
            self.patch_fixture(fixture, universe, base)

        return uid

    def patch_fixture(self, fixture: Fixture, universe=None, base=None):
        if fixture not in self.fixtures:
            raise ValueError("Add fixture first")
        univ = self._get_universe(universe)
        fixture.patch(universe, base, data=univ)
        if fixture.base != base:
            raise ValueError("fixture.patch did not call superclass")

    def _get_universe(self, universe: int):
        if universe not in self.universes:
            self.universes[universe] = array("B", [0] * DMX_UNIVERSE_SIZE)
        return self.universes[universe]

    def add_efx(self, efx: EFX) -> str:
        uid = self._own_and_name(efx)
        self.efx.append(efx)
        return uid

    def add_output(self, output: ControllerUniverseOutput) -> None:
        self.outputs.append(output)

    def add_pollable(self, pollable):
        self.pollable.append(pollable)

    def set_dmx(self, universe: int, channel: int, value: int):
        univ = self._get_universe(universe)
        univ[channel] = value

    def get_dmx(self, universe, channel):
        if self.blackout:
            return 0
        return self.universes[universe][channel]

    def __repr__(self):
        return f"showtime={self.showtime} fps={self.fps} target={self.target_fps}"

    def get_state_as_dict(self) -> Dict[str, Any]:
        out = {}
        for name, t in self.objects_by_name.items():
            out[name] = t.get_state_as_dict()
        return out

    def get_global_as_dict(self) -> Dict[str, Any]:
        out = {}
        for name, t in self.objects_by_name.items():
            out[name] = t.get_global_as_dict()
        return out

    def set_state_from_dict(self, state) -> None:
        for name, t in state.items():
            obj = self.objects_by_name.get(name)
            if obj is not None:
                obj.set_state(t)

    def set_global_from_dict(self, state) -> None:
        for name, t in state.items():
            obj = self.objects_by_name.get(name)
            if obj is not None:
                obj.set_global(t)

    def save_preset(self, name: str) -> None:
        self.presets[name] = self.get_state_as_dict()

    def load_preset(self, name: str) -> None:
        self.set_state_from_dict(self.presets[name])

    def load_showfile(self, name: str):
        nm = os.path.expanduser(name)
        self.showfile_name = nm
        try:
            with open(nm) as f:
                d = json.loads(f.read())
            self.presets = d["presets"]
            self.set_global_from_dict(d.get("global", {}))
        except FileNotFoundError:
            pass

    def save_showfile(self):
        d = {}
        d["presets"] = self.presets
        d["global"] = self.get_global_as_dict()
        if self.showfile_name:
            with open(self.showfile_name, "w") as f:
                json.dump(d, f, indent=2)
                f.write("\n")


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
        if channel not in self.cc_last:
            self.cc_last[channel] = 0


def build_show():
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--midi-in", action="store_true")
    args = parser.parse_args()

    controller = Controller(update_interval=25)

    if args.midi_in:
        midiin, port_name = open_midiinput(port="MPK")
        banks = MidiCC(midiin)
        controller.add_pollable(banks)

    mini0 = IbizaMini()
    mini1 = IbizaMini()
    mini2 = IbizaMini()
    mini3 = IbizaMini()

    controller.add_fixture(mini0, 1, 00)
    controller.add_fixture(mini1, 1, 20)
    controller.add_fixture(mini2, 1, 40)
    controller.add_fixture(mini3, 1, 60)

    controller.add_fixture(par1 := LedJ7Q5RGBA(), 1, 85)
    controller.add_fixture(par2 := LedJ7Q5RGBA(), 1, 79)
    controller.add_fixture(par3 := LedJ7Q5RGBA(), 1, 85)
    controller.add_fixture(par4 := LedJ7Q5RGBA(), 1, 90)

    # this sets a raw channel value in the DMX universe, it will
    # be overridden by any patched fixture
    controller.set_dmx(1, 0, 128)

    # mini.wash.set_red(200)
    mini0.wash.set_green(200)
    mini0.pos.set_degrees_pos(0, 0)
    mini0.spot.set(150)

    efx = WavePT_EFX(wave=10)
    controller.add_efx(efx)

    par2.wash.set_green(200)

    if args.midi_in:
        banks.bind_cc(70, efx.set_pan_midi)
        banks.bind_cc(71, efx.set_tilt_midi)
        banks.bind_cc(72, mini0.spot.set)
        banks.bind_cc(73, efx.set_wave_deg)

    noise = PerlinNoiseEFX(count=10)
    controller.add_efx(noise)

    col = ColourInterpolateEFX(channels=8)
    controller.add_efx(col)
    noise.o0.bind(col.i0)
    noise.o1.bind(col.i1)
    noise.o2.bind(col.i2)
    col.o1.bind(mini3.wash)

    noise.enabled.set(1)

    return controller


async def main():
    controller = build_show()

    async def print_stats():
        while True:
            print(controller)
            await asyncio.sleep(1.0)

    task = asyncio.create_task(print_stats())
    await controller.run()


if __name__ == "__main__":
    asyncio.run(main())
