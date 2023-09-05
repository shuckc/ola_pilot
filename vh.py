import argparse

from fixtures import IbizaMini, LedJ7Q5RGBA
from desk import FixtureController, MidiCC, WavePT_EFX
from fx import ColourInterpolateEFX, PerlinNoiseEFX
from pilot import OlaPilot
from aio_ola import OlaClient
from rtmidi.midiutil import open_midiinput


def build_show():
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--midi-in", action="store_true")
    args = parser.parse_args()

    client = OlaClient()
    controller = FixtureController(client, update_interval=25)

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

    controller.add_fixture(par0 := LedJ7Q5RGBA(), 1, 79)
    controller.add_fixture(par1 := LedJ7Q5RGBA(), 1, 84)
    controller.add_fixture(par2 := LedJ7Q5RGBA(), 1, 89)
    controller.add_fixture(par3 := LedJ7Q5RGBA(), 1, 94)

    # this sets a raw channel value in the DMX universe, it will
    # be overridden by any patched fixture
    controller.set_dmx(1, 0, 128)

    # mini.wash.set_red(200)
    mini0.wash.set_green(200)
    mini0.pos.set_rpos_deg(0, 0)
    mini0.spot.set(150)

    efx = WavePT_EFX(wave=10)
    controller.add_efx(efx)

    # par2.wash.set_green(200)

    if args.midi_in:
        banks.bind_cc(70, efx.set_pan_midi)
        banks.bind_cc(71, efx.set_tilt_midi)
        banks.bind_cc(72, mini0.spot.set)
        banks.bind_cc(73, efx.set_wave_deg)

    noise = PerlinNoiseEFX(count=10)
    controller.add_efx(noise)

    col = ColourInterpolateEFX(count=8)
    controller.add_efx(col)
    noise.o0.bind(col.i0)
    noise.o1.bind(col.i1)
    noise.o2.bind(col.i2)
    noise.o3.bind(col.i3)
    noise.o4.bind(col.i4)
    noise.o5.bind(col.i5)
    noise.o6.bind(col.i6)
    noise.o7.bind(col.i7)

    col.o0.bind(mini0.wash)
    col.o1.bind(par0.wash)
    col.o2.bind(mini1.wash)
    col.o3.bind(par1.wash)
    col.o4.bind(mini2.wash)
    col.o5.bind(par2.wash)
    col.o6.bind(mini3.wash)
    col.o7.bind(par3.wash)

    noise.enabled.set(1)

    return controller


if __name__ == "__main__":
    controller = build_show()
    controller.load_showfile("showfile.json")
    app = OlaPilot(controller)
    app.run()
    controller.save_showfile()
