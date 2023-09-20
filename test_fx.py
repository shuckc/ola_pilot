import pytest

from fx import perlin, ColourInterpolateEFX, CosPulseEFX, ChangeInBlack, PositionIndexer
from trait import IndexedChannel


def test_perlin():
    assert perlin(0, 0, 0) == 0
    assert perlin(0, 1, 0) == 0
    assert perlin(0, 0, 1) == 0
    assert perlin(0, 0, 2.1) == pytest.approx(-0.007704)
    assert perlin(0, 0, 2.2) == pytest.approx(-0.046336)


def test_colour_interpolate():
    c = ColourInterpolateEFX(channels=2, controlpts=4, steps=10)

    # since 4 control points all RGB=0, no steps to interpolate
    assert len(c._interp) == 1

    # set first control point to be white
    c.c0.set_rgb(255, 255, 255)
    assert len(c._interp) == 10
    assert c._interp[0].get_hex() == "#FFFFFF"
    assert c._interp[-1].get_hex() == "#000000"

    # set second control point to white, so we have wwbb
    c.c1.set_rgb(255, 255, 255)
    assert len(c._interp) == 10
    assert c._interp[0].get_hex() == "#FFFFFF"
    assert c._interp[-1].get_hex() == "#000000"

    # set control points wbwb
    c.c1.set_rgb(0, 0, 0)
    c.c2.set_rgb(255, 255, 255)
    assert len(c._interp) == 30
    assert c._interp[0].get_hex() == "#FFFFFF"
    assert c._interp[-1].get_hex() == "#000000"


def test_cos_pulse():
    c = CosPulseEFX(channels=4)
    c.enabled.set(1)
    c.tick(0)
    assert c.o0.value.pos == 255
    assert c.o1.value.pos == 0
    assert c.o2.value.pos == 0
    assert c.o3.value.pos == 0

    # speed is 0 (stationary) at 128, and unitary at 128+50=
    c.speed.set(178)
    # after one second, the peak should be lining up with channel 1
    c.tick(1.0)
    assert c.o0.value.pos == 0
    assert c.o1.value.pos == 255
    assert c.o2.value.pos == 0
    assert c.o3.value.pos == 0

    c.tick(1.5)
    assert c.o0.value.pos == 0
    assert c.o1.value.pos == 128
    assert c.o2.value.pos == 128
    assert c.o3.value.pos == 0

    c.tick(2.0)
    assert c.o0.value.pos == 0
    assert c.o1.value.pos == 0
    assert c.o2.value.pos == 255
    assert c.o3.value.pos == 0

    c.tick(3.0)
    assert c.o0.value.pos == 0
    assert c.o1.value.pos == 0
    assert c.o2.value.pos == 0
    assert c.o3.value.pos == 255

    c.tick(3.5)
    assert c.o0.value.pos == 128
    assert c.o1.value.pos == 0
    assert c.o2.value.pos == 0
    assert c.o3.value.pos == 128

    c.tick(4.0)
    assert c.o0.value.pos == 255
    assert c.o1.value.pos == 0
    assert c.o2.value.pos == 0
    assert c.o3.value.pos == 0


def test_change_in_black():
    colour_wheel = IndexedChannel(values={"red": 50, "black": 100})
    cib = ChangeInBlack(channels=1, changes=[[colour_wheel]], blackout=0.3)
    cib.i0.set(128)
    cib.tick(0)
    # at time zero, is blacked out
    assert cib.o0.value.pos == 0

    cib.tick(0.25)
    assert cib.o0.value.pos == 0

    cib.tick(0.35)
    assert cib.o0.value.pos == 128

    cib.tick(1.00)
    assert cib.o0.value.pos == 128

    colour_wheel.set("black")
    assert cib.o0.value.pos == 0

    cib.tick(1.25)
    assert cib.o0.value.pos == 0

    cib.tick(1.5)
    assert cib.o0.value.pos == 128

    # changing to existing value does not make a blackout
    colour_wheel.set("black")
    cib.tick(1.6)
    assert cib.o0.value.pos == 128


def test_position_index():
    pi = PositionIndexer(channels=1, presets=2)
    pi.preset.set(0)
    pi.c0.set_degrees_pos(0, 0)
    assert pi.get_global_as_dict() == {
        "data-0-0": {"pan": 32767, "tilt": 32767},
        "data-0-1": {"pan": 0, "tilt": 0},
    }
    assert pi.c0.get_degrees_str() == "  -0   -0"
    assert pi.o0.get_degrees_str() == "  -0   -0"

    print(id(pi.data[0][0]))
    print(id(pi.data[0][1]))

    assert pi.get_state_as_dict() == {
        "c0": {},
        "i0": {"value": 0},
        "o0": {"pan": 32767, "tilt": 32767},
        "preset": {"value": 0},
        "width": {"value": 0},
    }
    pi.preset.set(1)
    assert pi.get_global_as_dict() == {
        "data-0-0": {"pan": 32767, "tilt": 32767},
        "data-0-1": {"pan": 0, "tilt": 0},
    }
    # output has switched
    assert pi.get_state_as_dict() == {
        "c0": {},
        "i0": {"value": 0},
        "o0": {"pan": 0, "tilt": 0},
        "preset": {"value": 1},
        "width": {"value": 0},
    }
    # change preset 1 values by control input
    pi.c0.set_degrees_pos(15, -15)
    assert pi.c0.get_degrees_str() == " +15  -15"
    assert pi.o0.get_degrees_str() == " +15  -15"
    assert pi.get_global_as_dict() == {
        "data-0-0": {"pan": 32767, "tilt": 32767},
        "data-0-1": {"pan": 34587, "tilt": 27306},
    }
    # fails here
    pi.preset.set(0)
    pi.c0.get_degrees_str() == "  +0   +0"
    assert pi.get_state_as_dict() == {
        "c0": {},
        "i0": {"value": 0},
        "o0": {"pan": 32767, "tilt": 32767},
        "preset": {"value": 0},
        "width": {"value": 0},
    }
    assert pi.get_global_as_dict() == {
        "data-0-0": {"pan": 32767, "tilt": 32767},
        "data-0-1": {"pan": 34587, "tilt": 27306},
    }
