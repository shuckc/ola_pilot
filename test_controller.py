import itertools
from array import array

import pytest

from desk import FixtureController
from registration import Fixture
from trait import RGB, RGBA, RGBW


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
    assert controller.blackout is False
    assert controller.frames == 0
    await controller._tick_once(0)

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
    r.set_red(255)

    assert r.get_hex() == "#FF0000"
    r.set_green(127)
    assert r.get_hex() == "#FF7F00"

    u = make_test_universe()
    r.patch(u, 5)
    assert u[4] == 0
    assert u[5] == 255
    assert u[6] == 127
    assert u[7] == 0
    assert u[8] == 0

    # setters write through to the universe once patched
    r.set_red(1)
    assert u[5] == 1


def test_changed_hook():
    c = itertools.count()

    def changed(thing):
        # traceback.print_stack(limit=5)
        next(c)

    r = RGB()
    assert len(r._listeners) == 0
    assert len(r.red._listeners) == 1  # trait listens to channel
    r._patch_listener(changed)
    assert len(r._listeners) == 1  # we are listening to trait
    r.set_red(255)
    r.set_green(127)
    assert next(c) == 2


def test_trait_bind():
    r = RGB()
    r2 = RGB()
    r.bind(r2)

    r.set_red(60)
    assert r2.red.pos == 60


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
            super().__init__()

        def patch(self, universe, base, data):
            self.wash.patch(data, base)

    client = TestClient()
    controller = FixtureController(client, update_interval=25)
    f_unpatched = TestRGBFixture()
    assert f_unpatched.name is None
    assert f_unpatched.owner is None

    uid = controller.add_fixture(f_unpatched)
    controller.set_dmx(1, 2, 33)  # check this gets overriden during patching
    assert controller.get_dmx(1, 1) == 0
    assert controller.get_dmx(1, 2) == 33
    assert uid == "TestRGBFixture-0"
    assert f_unpatched.owner == controller
    assert f_unpatched.name == uid

    f_unpatched.wash.red.set(128)
    assert f_unpatched.wash.red.pos == 128

    controller.patch_fixture(f_unpatched, 1, 1)
    assert controller.get_dmx(1, 1) == 128
    assert controller.get_dmx(1, 2) == 0  # was overridden

    uid2 = controller.add_fixture(TestRGBFixture())
    assert uid2 == "TestRGBFixture-1"


def test_controller_persist():
    class TestRGBFixture(Fixture):
        def __init__(self):
            self.wash = RGB()
            super().__init__()

        def patch(self, universe, base, data):
            self.wash.patch(data, base)

    client = TestClient()
    controller = FixtureController(client, update_interval=25)
    uid = controller.add_fixture(f := TestRGBFixture())
    f.wash.red.set(128)

    j = controller.get_state_as_dict()
    assert j == {"TestRGBFixture-0": {"wash": {"red": 128, "green": 0, "blue": 0}}}

    controller.set_state_from_dict({"TestRGBFixture-0": {"wash": {"red": 250, "green": 0, "blue": 0}}})
    assert f.wash.red.pos == 250

    controller.save_preset("red-on")
    f.wash.red.set(0)
    controller.load_preset("red-on")
    assert f.wash.red.pos == 250
