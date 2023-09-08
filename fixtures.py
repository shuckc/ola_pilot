from channel import UniverseType
from registration import Fixture, fixture
from trait import RGBA, RGBW, Channel, IndexedChannel, IntensityChannel, PTPos

# fixture is a set of traits, exposed via. __dict__
# trait is a grouping of channels, each of which exposes a ranged value and
# can be patched into a DMX universe


@fixture
class IbizaMini(Fixture):
    def __init__(self):
        super().__init__(ch=19)

        lb_presets = {
            "off": 0,
            "sol red": 10,
            "sol green": 20,
            "sol blue": 35,
            "sol yellow": 50,
            "sol purple": 65,
            "sol cyan": 80,
            "sol white": 95,
            "sol cycle": 110,
            "spin red": 118,
            "spin green": 126,
            "spin blue": 134,
            "spin yellow": 142,
            "spin purple": 150,
            "spin cyan": 158,
            "spin white": 166,
            "sector red yellow": 174,
            "sector purple red": 182,
            "sector green yellow": 190,
            "sector blue purple": 198,
        }
        self.pos = PTPos()
        self.wash = RGBW()
        self.spot = IntensityChannel()
        self.spot_cw = IndexedChannel(
            values={
                "white": 0,
                "red": 20,
                "green": 40,
                "blue": 55,
                "yellow": 70,
                "magenta": 90,
                "amber": 100,
            }
        )
        self.spot_gobo = IndexedChannel(
            values={
                "open": 0,
                "arc seg": 20,
                "jazz sun": 40,
                "star blob": 55,
                "star rad": 70,
                "rings": 90,
                "swirl": 100,
                "donut": 120,
            }
        )
        self.light_belt = IndexedChannel(values=lb_presets)
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
