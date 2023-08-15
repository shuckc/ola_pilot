import math
import time
from abc import ABC, abstractmethod

from typing import Optional, TypeAlias, List, MutableSequence

from channel import ByteChannelProp, FineChannelProp, UniverseType


class Trait(ABC):
    @abstractmethod
    def patch(self, data: UniverseType, base: int) -> None:
        pass


# https://blog.saikoled.com/post/44677718712/how-to-convert-from-hsi-to-rgb-white
class RGB(Trait):
    def __init__(self):
        self.red = ByteChannelProp()
        self.green = ByteChannelProp()
        self.blue = ByteChannelProp()

    def set_red(self, red):
        # TODO ?
        # from HSV?
        self.red.set(red)

    def set_green(self, green):
        self.green.set(green)

    def set_blue(self, blue):
        self.blue.set(blue)

    def get_approx_rgb(self):
        return self.red.pos, self.green.pos, self.blue.pos

    def get_hex(self):
        r, g, b = self.get_approx_rgb()
        return f"#{r:02X}{g:02X}{b:02X}"

    def patch(self, data: UniverseType, base: int) -> None:
        self.red.patch(data, base + 0)
        self.green.patch(data, base + 1)
        self.blue.patch(data, base + 2)


class RGBW(RGB):
    def __init__(self):
        super().__init__()
        self.white = ByteChannelProp()

    def patch(self, data: UniverseType, base: int) -> None:
        super().patch(data, base)
        self.white.patch(data, base + 3)

    def set_white(self, white):
        self.white.set(white)

    def get_approx_rgb(self):
        r, g, b = super().get_approx_rgb()
        w = self.white.pos
        # scale down rgb components by w intensity, and add w to all channels equally
        return (
            int(r * (255 - w) / 255 + w),
            int(g * (255 - w) / 255 + w),
            int(b * (255 - w) / 255 + w),
        )


class RGBA(RGB):
    def __init__(self):
        super().__init__()
        self.amber = ByteChannelProp()

    def set_amber(self, amber):
        self.amber.set(amber)

    def patch(self, data: UniverseType, base: int) -> None:
        super().patch(data, base)
        self.amber.patch(data, base + 3)

    def get_approx_rgb(self):
        r, g, b = super().get_approx_rgb()
        a = self.amber.pos
        # scale down rgb components by amber intensity, and add a weighted by 255,191,0 (#FFBF00) to channels
        return (
            int(r * (255 - a) / 255 + a),
            int(g * (255 - a) / 255 + a * (191 / 255)),
            int(b * (255 - a) / 255),
        )


class PTPos(Trait):
    def __init__(self, pan_range=540, tilt_range=180):
        # self._data = array("B", [0] * 4)
        self._pan_range = pan_range
        self._tilt_range = tilt_range
        self.pan = FineChannelProp()
        self.tilt = FineChannelProp()

    def set_rpos_deg(self, pan, tilt):
        # arguments in degress relative to straight down
        pan = 0xFFFF * (0.5 + (pan / self._pan_range))
        tilt = 0xFFFF * (0.5 + (tilt / self._tilt_range))
        self.set_pos(pan, tilt)

    def set_pos(self, pan, tilt):
        self.pan.set(pan)
        self.tilt.set(tilt)

    def patch(self, data: UniverseType, base: int) -> None:
        self.pan.patch(data, base + 0)
        self.tilt.patch(data, base + 2)


class Channel(Trait):
    def __init__(self, value=0):
        self.value = ByteChannelProp(pos=value)

    def set(self, value):
        self.value.set(value)

    def patch(self, data: UniverseType, base: int) -> None:
        self.value.patch(data, base)


class IntensityChannel(Channel):
    def __init__(self, value=0):
        self.value = ByteChannelProp(pos=value)

    def set(self, value):
        self.value.set(value)

    def patch(self, data: UniverseType, base: int) -> None:
        self.value.patch(data, base)



class IndexedChannel(Channel):
    pass


class OnOffChannel(Trait):
    def __init__(self, value=0):
        self.value = ByteChannelProp(pos=value, pos_max=1)

    def set(self, value):
        self.value.set(value)

    def patch(self, data: UniverseType, base: int) -> None:
        self.value.patch(data, base)
