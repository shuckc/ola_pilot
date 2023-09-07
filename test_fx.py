import pytest

from fx import perlin, ColourInterpolateEFX


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
