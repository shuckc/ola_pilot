from fx import perlin


def test_perlin():
    assert perlin(0, 0, 0) == 0.5
    assert perlin(0, 1, 0) == 0.5
    assert perlin(0, 0, 1) == 0.5
    assert perlin(0, 0, 2.1) == 0.496148
    assert perlin(0, 0, 2.2) == 0.476832
