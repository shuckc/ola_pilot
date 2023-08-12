import pytest
from array import array
from desk import FixtureController
from registration import Fixture
from trait import RGB, RGBW, RGBA

class TestClient:
    async def set_dmx(self, universe, data):
        pass


def make_test_universe():
    return array("B", [0] * 512)


@pytest.mark.asyncio
async def test_fixture():
    client = TestClient()
    controller = FixtureController(client, update_interval=25)
    controller.set_dmx(1, 0, 128)
    assert 1 in controller.universes
    assert controller.blackout == False
    assert controller.frames == 0
    await controller._tick_once()

    assert controller.frames == 1
    # check our manually patched value
    assert controller.get_dmx(1, 0) == 128
    assert controller.get_dmx(1, 1) == 0

    controller.blackout = True
    assert controller.get_dmx(1, 0) == 0

    controller.blackout = False
    assert controller.get_dmx(1, 0) == 128


def test_trait():
    r = RGB()
    r.red.set(255)
    assert r.get_hex() == "#FF0000"
    r.green.set(127)
    assert r.get_hex() == "#FF7F00"

    u = make_test_universe()
    r.patch(u, 5)
    assert u[4] == 0
    assert u[5] == 255
    assert u[6] == 127
    assert u[7] == 0
    assert u[8] == 0

    # setters write through to the universe once patched
    r.red.set(1)
    assert u[5] == 1


def test_rgbw_downsample():
    r = RGBW()
    r.white.set(255)
    assert r.get_hex() == "#FFFFFF"

    r.red.set(0)
    r.green.set(0)
    r.blue.set(255)
    assert r.get_hex() == "#FFFFFF"

    r.white.set(128)
    assert r.get_hex() == "#8080FF"


def test_rgba_downsample():
    r = RGBA()
    r.amber.set(255)
    assert r.get_hex() == "#FFBF00"

    r.red.set(255)
    r.green.set(255)
    r.blue.set(255)
    assert r.get_hex() == "#FFBF00"

    r.red.set(255)
    r.green.set(191)
    r.blue.set(0)
    r.amber.set(0)
    assert r.get_hex() == "#FFBF00"


def test_fixture_unpatched():
    class TestRGBFixture(Fixture):
        def __init__(self):
            self.wash = RGB()

        def patch(self, universe, base, data):
            self.wash.patch(data, base)

    client = TestClient()
    controller = FixtureController(client, update_interval=25)
    f_unpatched = TestRGBFixture()

    controller.add_fixture(f_unpatched)
    controller.set_dmx(1, 2, 33)  # check this gets overriden during patching
    assert controller.get_dmx(1, 1) == 0
    assert controller.get_dmx(1, 2) == 33

    f_unpatched.wash.red.set(128)
    assert f_unpatched.wash.red.pos == 128

    controller.patch_fixture(f_unpatched, 1, 1)
    assert controller.get_dmx(1, 1) == 128
    assert controller.get_dmx(1, 2) == 0  # was overridden
