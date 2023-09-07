import functools
from abc import ABC, abstractmethod
from typing import Any, List, Iterator, Tuple, Dict

from channel import (
    ByteChannelProp,
    FineChannelProp,
    Observable,
    UniverseType,
    ChannelProp,
)


class Trait(Observable, ABC):
    @abstractmethod
    def patch(self, data: UniverseType, base: int) -> None:
        pass

    @abstractmethod
    def bind(self, other: "Trait") -> None:
        pass

    @abstractmethod
    def interpolate_to(self, other: "Trait", steps: int) -> List["Trait"]:
        pass

    def get_state_as_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {}
        for k, t in self.channel_items():
            t.add_state(k, d)
        return d

    def set_state(self, data: Dict[str, Any]):
        d = dict(list(self.channel_items()))
        for k, t in data.items():
            tr = d.get(k)
            if tr is not None:
                tr.set(t)

    def channel_items(self) -> Iterator[Tuple[str, ChannelProp]]:
        for k, v in self.__dict__.items():
            if isinstance(v, ChannelProp):
                yield k, v


# https://blog.saikoled.com/post/44677718712/how-to-convert-from-hsi-to-rgb-white
class RGB(Trait):
    def __init__(self):
        super().__init__()
        self.red = ByteChannelProp()
        self.green = ByteChannelProp()
        self.blue = ByteChannelProp()

        self.red._patch_listener(self._changed)
        self.green._patch_listener(self._changed)
        self.blue._patch_listener(self._changed)

    def set_red(self, red):
        # TODO value from HSV or HSI
        self.red.set(red)

    def set_green(self, green):
        self.green.set(green)

    def set_blue(self, blue):
        self.blue.set(blue)

    def set_rgb(self, red, green, blue):
        self.red.set(red)
        self.green.set(green)
        self.blue.set(blue)

    def set_hex(self, hexstr):
        if hexstr.startswith("#"):
            hexstr = hexstr[1:]
        if len(hexstr) != 6:
            raise ValueError("not 6-digit hex string")
        r, g, b = int(hexstr[0:2], 16), int(hexstr[2:4], 16), int(hexstr[4:6], 16)
        self.set_rgb(r, g, b)

    def get_approx_rgb(self):
        return self.red.pos, self.green.pos, self.blue.pos

    def get_hex(self):
        r, g, b = self.get_approx_rgb()
        return f"#{r:02X}{g:02X}{b:02X}"

    def patch(self, data: UniverseType, base: int) -> None:
        self.red.patch(data, base + 0)
        self.green.patch(data, base + 1)
        self.blue.patch(data, base + 2)

    def _copy_to(self, other: "RGB", src: Any):
        other.red.set(self.red.pos)
        other.green.set(self.green.pos)
        other.blue.set(self.blue.pos)

    def bind(self, other: Trait):
        if not isinstance(other, RGB):
            raise ValueError()
        super().bind(other)
        self._patch_listener(functools.partial(self._copy_to, other))

    def interpolate_to(self, other: Trait, steps: int):
        if not isinstance(other, RGB):
            raise ValueError()
        r1, g1, b1 = self.get_approx_rgb()
        r2, g2, b2 = other.get_approx_rgb()
        result = []
        for i in range(steps):
            r = ((r2 - r1) / steps * i) + r1
            g = ((g2 - g1) / steps * i) + g1
            b = ((b2 - b1) / steps * i) + b1
            oc = RGB()
            oc.set_rgb(r, g, b)
            result.append(oc)
        return result


class RGBW(RGB):
    def __init__(self):
        super().__init__()
        self.white = ByteChannelProp()
        self.white._patch_listener(self._changed)

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
        self.amber._patch_listener(self._changed)

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
        super().__init__()
        self._pan_range = pan_range
        self._tilt_range = tilt_range
        self.pan = FineChannelProp()
        self.tilt = FineChannelProp()
        self.pan._patch_listener(self._changed)
        self.tilt._patch_listener(self._changed)

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

    def _copy_to(self, other: "PTPos", src: Any):
        other.pan.set(self.pan.pos)
        other.tilt.set(self.tilt.pos)

    def bind(self, other: Trait):
        if not isinstance(other, PTPos):
            raise ValueError()
        self._patch_listener(functools.partial(self._copy_to, other))

    def interpolate_to(self, other: Trait, steps: int):
        raise ValueError()


class Channel(Trait):
    def __init__(self, value=0):
        self.value = ByteChannelProp(pos=value)
        self.value._patch_listener(self._changed)
        super().__init__()

    def set(self, value):
        self.value.set(value)

    def patch(self, data: UniverseType, base: int) -> None:
        self.value.patch(data, base)

    def _copy_to(self, other: "Channel", src: Any):
        other.value.set(self.value.pos)

    def bind(self, other: Trait):
        if not isinstance(other, Channel):
            raise ValueError()
        self._patch_listener(functools.partial(self._copy_to, other))

    def interpolate_to(self, other: Trait, steps: int):
        raise ValueError()


class IntensityChannel(Channel):
    def __init__(self, value=0):
        super().__init__()


class IndexedChannel(Channel):
    pass


class OnOffChannel(Trait):
    def __init__(self, value=0):
        self.value = ByteChannelProp(pos=value, pos_max=1)
        self.value._patch_listener(self._changed)
        super().__init__()

    def set(self, value):
        self.value.set(value)

    def patch(self, data: UniverseType, base: int) -> None:
        self.value.patch(data, base)

    def _copy_to(self, other: "OnOffChannel", src: Any):
        other.value.set(self.value.pos)

    def bind(self, other: Trait):
        if not isinstance(other, OnOffChannel):
            raise ValueError()
        self._patch_listener(functools.partial(self._copy_to, other))

    def interpolate_to(self, other: Trait, steps: int):
        raise ValueError()
