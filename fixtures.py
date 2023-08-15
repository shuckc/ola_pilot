from trait import PTPos, RGBW, RGBA, Channel, IndexedChannel, IntensityChannel
from channel import UniverseType
from registration import fixture, Fixture

# fixture is a set of traits, exposed via. __dict__
# trait is a grouping of channels, each of which exposes a ranged value and
# can be patched into a DMX universe


@fixture
class IbizaMini(Fixture):
    def __init__(self):
        super().__init__(ch=19)
        self.pos = PTPos()
        self.wash = RGBW()
        self.spot = IntensityChannel()
        self.spot_cw = IndexedChannel()
        self.spot_gobo = IndexedChannel()
        self.light_belt = Channel()
        self.pt_speed = Channel(value=0)
        self.global_dimmer = Channel(value=255)

    def patch(self, universe: int, base: int, data: UniverseType) -> None:
        super().patch(universe, base, data)
        self.pos.patch(data, base + 0)
        self.pt_speed.patch(data, base + 4)
        self.global_dimmer.patch(data, base + 5)
        self.spot.patch(data, base + 6)
        self.spot_cw.patch(data, base + 7)
        self.spot_gobo.patch(data, base + 8)
        self.wash.patch(data, base + 9)
        self.light_belt.patch(data, base + 18)


@fixture
class LedJ7Q5RGBA(Fixture):
    def __init__(self):
        super().__init__(ch=4)
        self.wash = RGBA()

    def patch(self, universe: int, base: int, data: UniverseType) -> None:
        super().patch(universe, base, data)
        self.wash.patch(data, base)
