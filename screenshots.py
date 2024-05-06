import asyncio

from desk import Controller
from trait import RGB
from pilot import OlaPilot
from registration import Fixture


def build_show():
    controller = Controller(update_interval=25)

    class ToyFixture(Fixture):
        def __init__(self):
            super().__init__(3)
            self.wash = RGB()

        def patch(self, uni, base, data):
            self.wash.patch(data, base)
            super().patch(uni, base, data)

    tf = ToyFixture()
    controller.add_fixture(tf, universe=1, base=50)
    return controller


async def main():
    controller = build_show()
    # await controller.run()

    app = OlaPilot(controller)
    async with app.run_test(
        size=(120, 40),
    ) as pilot:
        # await pilot.click("#Button.ok")
        # await pilot.press('f')
        await pilot.wait_for_scheduled_animations()
        app.save_screenshot(path="docs/", filename="screen-basic.svg")
        await pilot.press(*["right"] * 4)
        await pilot.press("enter", "tab", "h")
        await pilot.wait_for_scheduled_animations()

        app.save_screenshot(path="docs/", filename="screen-basic-change.svg")

        await pilot.exit(0)


if __name__ == "__main__":
    # controller = build_show()
    # app = OlaPilot(controller)
    # app.run()

    asyncio.run(main())
