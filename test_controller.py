
import pytest
from desk import FixtureController

class TestClient:
    async def set_dmx(self, universe, data):
        pass

@pytest.mark.asyncio
async def test_universe():

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

