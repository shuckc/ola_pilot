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
class IntimidatorSpotDuo(Fixture):
    def __init__(self, head=0):
        super().__init__(ch=20)
        if head not in [0, 1]:
            raise ValueError("bad head number")
        self.head = head
        self.pos = PTPos()
        self.spot = IntensityChannel()
        self.spot_cw = IndexedChannel(
            values={
                "white": 0,
                "orange": 16,
                "cyan": 32,
                "red": 48,
                "green": 64,
                "yellow": 96,
                "blue": 112,
            }
        )
        self.spot_gobo = IndexedChannel(
            values={
                "open": 0,
                "small": 10,
                "swirl": 16,
                "rose": 22,
                "bolt": 28,
                "triangle": 34,
                "hex": 40,
                "shock": 46,
                "swirl2": 52,
                "ice": 58,
            }
        )
        self.shutter = IndexedChannel(
            values={
                "off": 0,
                "on": 4,
                "shutter 0": 8,
                "shutter 1": 18,
                "shutter 2": 28,
                "shutter 3": 38,
                "shutter 4": 48,
                "shutter 5": 58,
                "shutter 6": 68,
                "pulse 0": 77,
                "strobe": 146,
            }
        )
        if head == 0:
            self.pt_speed = Channel(value=0)

    def patch(self, universe: int, base: int, data: UniverseType) -> None:
        super().patch(universe, base, data)
        if self.head == 0:
            self.pos.patch(data, base + 0)
            self.pt_speed.patch(data, base + 8)
            self.spot_cw.patch(data, base + 9)
            self.spot_gobo.patch(data, base + 11)
            self.spot.patch(data, base + 13)
            self.shutter.patch(data, base + 15)
        else:
            self.pos.patch(data, base + 4)
            self.spot_cw.patch(data, base + 10)
            self.spot_gobo.patch(data, base + 12)
            self.spot.patch(data, base + 14)
            self.shutter.patch(data, base + 16)


@fixture
class LedJ7Q5RGBA(Fixture):
    def __init__(self):
        super().__init__(ch=4)
        self.wash = RGBA()

    def patch(self, universe: int, base: int, data: UniverseType) -> None:
        super().patch(universe, base, data)
        self.wash.patch(data, base)
