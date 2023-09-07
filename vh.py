import argparse

from fixtures import IbizaMini, LedJ7Q5RGBA
from desk import FixtureController, MidiCC, WavePT_EFX
from fx import ColourInterpolateEFX, PerlinNoiseEFX, StaticColour
from trait import IntensityChannel
from pilot import OlaPilot
from aio_ola import OlaClient
from rtmidi.midiutil import open_midiinput


def build_show(args):

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

    mini0.pos.set_rpos_deg(0, 0)

    efx = WavePT_EFX(wave=10)
    controller.add_efx(efx)

    # par2.wash.set_green(200)

    if args.midi_in:
        banks.bind_cc(70, efx.set_pan_midi)
        banks.bind_cc(71, efx.set_tilt_midi)
        banks.bind_cc(72, mini0.spot.set)
        banks.bind_cc(73, efx.set_wave_deg)

    noise = PerlinNoiseEFX(count=8)
    controller.add_efx(noise)

    col = ColourInterpolateEFX(channels=8)
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

    noise = PerlinNoiseEFX(count=4)
    controller.add_efx(noise)
    noise.o0.bind(mini0.spot)
    noise.o1.bind(mini1.spot)
    noise.o2.bind(mini2.spot)
    noise.o3.bind(mini3.spot)

    static = StaticColour()
    for f in [mini0, par0, mini1, par1, mini2, par2, mini3, par3]:
        static.c0.bind(f.wash)
    controller.add_efx(static)

    static = StaticColour(trait_type=IntensityChannel)
    for f in [mini0, mini1, mini2, mini3]:
        static.c0.bind(f.spot)
    controller.add_efx(static)

    return controller


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--midi-in", action="store_true")
    parser.add_argument("--hide-dmx", action="store_false")
    parser.add_argument("--hide-fixtures", action="store_false")
    parser.add_argument("--hide-efx", action="store_false")

    args = parser.parse_args()

    controller = build_show(args)
    controller.load_showfile("showfile.json")
    app = OlaPilot(controller, args.hide_efx, args.hide_dmx, args.hide_fixtures)
    app.run()
    controller.save_showfile()
