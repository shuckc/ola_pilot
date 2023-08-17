import pytest

from fx import perlin


def test_perlin():
    assert perlin(0, 0, 0) == 0
    assert perlin(0, 1, 0) == 0
    assert perlin(0, 0, 1) == 0
    assert perlin(0, 0, 2.1) == pytest.approx(-0.007704)
    assert perlin(0, 0, 2.2) == pytest.approx(-0.046336)
