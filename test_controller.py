import itertools
from array import array
from typing import Any
import pytest

from desk import Controller
from registration import Fixture
from trait import RGB, RGBA, RGBW, IndexedChannel, PTPos, IntensityChannel


class TestClient:
    async def set_dmx(self, universe, data):
        pass


def make_test_universe():
    return array("B", [0] * 512)


@pytest.mark.asyncio
async def test_fixture():
    controller = Controller(update_interval=25)
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


def test_indexed_channel():
    spot_cw = IndexedChannel(values={"white": 0, "red": 20, "green": 40, "blue": 55})
    spot_cw.set("white")
    u = make_test_universe()
    spot_cw.patch(u, 5)
    assert u[5] == 0

    spot_cw.set("red")
    assert u[5] == 20
    assert spot_cw.get() == "red"

    # setting invalid gives first entry
    spot_cw.set("beige")
    assert u[5] == 0
    assert spot_cw.get() == "white"

    # channel should have min=0 max=3 pos=0
    assert spot_cw.value.pos_min == 0
    assert spot_cw.value.pos_max == 3
    assert spot_cw.value.pos == 0

    spot_cw.set("green")
    assert spot_cw.value.pos == 2
    assert u[5] == 40


class change_counter:
    def __init__(self):
        self.changes = 0

    def changed(self, source: Any):
        self.changes += 1


def test_changed_hook():
    cc = change_counter()
    assert cc.changes == 0

    r = RGB()
    assert len(r._listeners) == 0
    r._patch_listener(cc.changed)
    assert len(r._listeners) == 1  # we are listening to trait
    r.set_red(255)
    r.set_green(127)
    assert cc.changes == 2

    g = RGB()
    g.set_rgb(0, 255, 0)
    g._copy_to(r, None)
    assert cc.changes == 3


def test_trait_bind():
    r = RGB()
    r2 = RGB()
    cc = change_counter()

    assert not r2.is_bound

    # binding sets the bound flag on the trait
    r.bind(r2)
    assert r2.is_bound

    r.set_red(60)
    assert r2.red.pos == 60

    # should this raise CannotChangeBoundValue ?
    # r2.set_red(30)

    # it is OK to bind a trait to mulitple others
    r3 = RGB()
    r.bind(r3)

    # a change counter on r3 should be invoked by changes to r
    assert r3.is_bound
    r3._patch_listener(cc.changed)

    r.set_red(30)
    assert r2.red.pos == 30
    assert r3.red.pos == 30
    assert cc.changes == 1


def test_intensity_bind():
    r1 = IntensityChannel()
    r2 = IntensityChannel()
    cc = change_counter()
    r2._patch_listener(cc.changed)
    r1.bind(r2)
    r1.set(40)
    assert cc.changes == 1


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


class MockRGBFixture(Fixture):
    def __init__(self):
        self.wash = RGB()
        super().__init__()

    def patch(self, universe, base, data):
        self.wash.patch(data, base)
        super().patch(universe, base, data)


def test_fixture_unpatched():
    controller = Controller(update_interval=25)
    f_unpatched = MockRGBFixture()
    assert f_unpatched.name is None
    assert f_unpatched.owner is None

    uid = controller.add_fixture(f_unpatched)
    controller.set_dmx(1, 2, 33)  # check this gets overriden during patching
    assert controller.get_dmx(1, 1) == 0
    assert controller.get_dmx(1, 2) == 33
    assert uid == "MockRGBFixture-0"
    assert f_unpatched.owner == controller
    assert f_unpatched.name == uid

    f_unpatched.wash.red.set(128)
    assert f_unpatched.wash.red.pos == 128

    controller.patch_fixture(f_unpatched, 1, 1)
    assert controller.get_dmx(1, 1) == 128
    assert controller.get_dmx(1, 2) == 0  # was overridden

    uid2 = controller.add_fixture(MockRGBFixture())
    assert uid2 == "MockRGBFixture-1"


def test_fixture_add_and_patch():
    controller = Controller(update_interval=25)
    f = MockRGBFixture()
    uid = controller.add_fixture(f, universe=2, base=30)

    assert f.universe == 2
    assert f.base == 30

    f.wash.red.set(128)
    assert controller.get_dmx(2, 30) == 128


def test_controller_persist():
    controller = Controller(update_interval=25)
    uid = controller.add_fixture(f := MockRGBFixture())
    f.wash.red.set(128)

    j = controller.get_state_as_dict()
    assert j == {"MockRGBFixture-0": {"wash": {"red": 128, "green": 0, "blue": 0}}}

    controller.set_state_from_dict(
        {"MockRGBFixture-0": {"wash": {"red": 250, "green": 0, "blue": 0}}}
    )
    assert f.wash.red.pos == 250

    controller.save_preset("red-on")
    f.wash.red.set(0)
    controller.load_preset("red-on")
    assert f.wash.red.pos == 250


def test_controller_persist_skip_bound():
    # traits bound to the value of another should not be saved in presets
    controller = Controller(update_interval=25)
    controller.add_fixture(f1 := MockRGBFixture())
    controller.add_fixture(f2 := MockRGBFixture())
    f2.wash.bind(f1.wash)  # writes to f2 are copied to f1

    assert controller.get_state_as_dict() == {
        "MockRGBFixture-0": {},
        "MockRGBFixture-1": {"wash": {"red": 0, "green": 0, "blue": 0}},
    }


def test_ptpos():
    # default position is 0,0
    pt = PTPos(pan_range=540, tilt_range=180)
    assert pt.pan.pos == 0
    assert pt.tilt.pos == 0

    p, t = pt.get_degrees_mid()
    assert p == -270
    assert t == -90

    assert pt.get_degrees_str() == "-270  -90"

    pt.set_degrees_pos(0, 0)
    assert pt.pan.pos == 0x7FFF
    assert pt.tilt.pos == 0x7FFF
    # wierd?
    assert pt.get_degrees_str() == "  -0   -0"
    assert pt.get_state_as_dict() == {"pan": 32767, "tilt": 32767}

    p2 = pt.duplicate()
    p2.set_degrees_relative_to(pt, 5, 3)
    assert p2.get_degrees_str() == "  +5   +3"

    p3 = pt.duplicate()
    p3.set_degrees_relative_to(p2, 10, -20)
    assert p3.get_degrees_str() == " +15  -17"

    pt.set_degrees_pos(45, -45)
    p4 = pt.duplicate()
    assert p4.get_state_as_dict() == {"pan": 0, "tilt": 0}
    p4.set_state(pt.get_state_as_dict())
    assert p4.get_state_as_dict() == {"pan": 38228, "tilt": 16383}
    assert p4.get_degrees_str() == " +45  -45"
