import asyncio

from fixtures import IbizaMini, LedJ7Q5RGBA, IntimidatorSpotDuo
from desk import FixtureController, MidiCC, WavePT_EFX
from fx import (
    ColourInterpolateEFX,
    PerlinNoiseEFX,
    StaticColour,
    CosPulseEFX,
    StaticCopy,
    ChangeInBlack,
    PositionIndexer,
)
from trait import RGB
from pilot import OlaPilot
from aio_ola import OlaClient
from rtmidi.midiutil import open_midiinput
from registration import Fixture


def build_show():
    controller = FixtureController(None, update_interval=25)

    class ToyFixture(Fixture):
        def __init__(self):
            super().__init__(self)
            self.wash = RGB()

        def patch(self, uni, base, data):
            pass

    tf = ToyFixture()
    # controller.add_fixture(tf)
    controller.patch_fixture(tf, 0, 50)
    return controller


async def main():
    controller = build_show()
    app = OlaPilot(controller)
    async with app.run_test(
        size=(100, 60),
    ) as pilot:
        # await pilot.click("#Button.ok")
        # await pilot.press('f')
        app.save_screenshot(path="docs/", filename="screen-basic.svg")
        await pilot.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
