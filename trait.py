import functools
from abc import ABC, abstractmethod
from typing import Any, List, Iterator, Tuple, Dict

from channel import (
    ByteChannelProp,
    FineChannelProp,
    Observable,
    UniverseType,
    ChannelProp,
    IndexedByteChannelProp,
)


class Trait(Observable, ABC):
    def __init__(self, is_global=False):
        super().__init__()
        self.is_bound = False
        self.is_global = is_global

    @abstractmethod
    def patch(self, data: UniverseType, base: int) -> None:
        pass

    @abstractmethod
    def bind(self, other: "Trait") -> None:
        other.is_bound = True

    @abstractmethod
    def interpolate_to(self, other: "Trait", steps: int) -> List["Trait"]:
        pass

    def get_state_as_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {}
        for k, t in self.channel_items():
            t.add_state(k, d)
        return d

    def get_global_as_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {}
        if self.is_global:
            for k, t in self.channel_items():
                t.add_global(k, d)
        return d

    def set_state(self, data: Dict[str, Any]):
        d = dict(list(self.channel_items()))
        for k, t in data.items():
            tr = d.get(k)
            if tr is not None:
                tr.set(t)

    def set_global(self, data: Dict[str, Any]):
        d = dict(list(self.channel_items()))
        for k, t in data.items():
            tr = d.get(k)
            if tr is not None:
                tr.set(t)

    def channel_items(self) -> Iterator[Tuple[str, ChannelProp]]:
        for k, v in self.__dict__.items():
            if isinstance(v, ChannelProp):
                yield k, v

    @abstractmethod
    def duplicate(self) -> "Trait":
        pass


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
        # because we listen to red, green, blue, set ourselves as the source
        # so that we drop rather than propagate the change 3 times
        self.red.set(red, source=self)
        self.green.set(green, source=self)
        self.blue.set(blue, source=self)
        self._changed(None)

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
        other.set_rgb(*self.get_approx_rgb())

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
            r = ((r2 - r1) / (steps - 1) * i) + r1
            g = ((g2 - g1) / (steps - 1) * i) + g1
            b = ((b2 - b1) / (steps - 1) * i) + b1
            oc = RGB()
            oc.set_rgb(r, g, b)
            result.append(oc)
        return result

    def duplicate(self):
        return RGB()


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
    def __init__(self, pan_range=540, tilt_range=180, is_global=False):
        super().__init__(is_global=is_global)
        self.pan_range = pan_range
        self.tilt_range = tilt_range
        self.pan = FineChannelProp()
        self.tilt = FineChannelProp()
        self.pan._patch_listener(self._changed)
        self.tilt._patch_listener(self._changed)

    def set_degrees_pos(self, pan, tilt):
        # arguments in degress relative to straight down
        pan = self.pan.pos_max * (0.5 + (pan / self.pan_range))
        tilt = self.tilt.pos_max * (0.5 + (tilt / self.tilt_range))
        self.set_pos(pan, tilt)

    def get_degrees_mid(self) -> Tuple[float, float]:
        pan = (self.pan.pos / self.pan.pos_max) - 0.5
        tilt = (self.tilt.pos / self.tilt.pos_max) - 0.5
        pan = pan * self.pan_range
        tilt = tilt * self.tilt_range
        return pan, tilt

    def get_degrees_str(self) -> str:
        p, t = self.get_degrees_mid()
        return f"{p:.0f} {t:.0f}"

    def set_pos(self, pan, tilt):
        self.pan.set(pan)
        self.tilt.set(tilt)

    def patch(self, data: UniverseType, base: int) -> None:
        self.pan.patch(data, base + 0)
        self.tilt.patch(data, base + 2)

    def _copy_to(self, other: "PTPos", src: Any):
        other.pan.set(self.pan.pos)
        other.tilt.set(self.tilt.pos)

    def set_degrees_relative_to(self, other: "PTPos", pan: float, tilt: float):
        # relative part
        rp, rt = other.get_degrees_mid()
        self.set_degrees_pos(rp + pan, rt + tilt)

    def bind(self, other: Trait):
        if not isinstance(other, PTPos):
            raise ValueError()
        super().bind(other)
        self._patch_listener(functools.partial(self._copy_to, other))

    def interpolate_to(self, other: Trait, steps: int):
        raise ValueError()

    def duplicate(self):
        return PTPos(pan_range=self.pan_range, tilt_range=self.tilt_range)


class Channel(Trait):
    def __init__(self, value=0, pos_max=255):
        super().__init__()
        self.value = ByteChannelProp(pos=value, pos_max=pos_max)
        self.value._patch_listener(self._changed)
        self.pos_max = pos_max

    def set(self, value):
        self.value.set(value)

    def patch(self, data: UniverseType, base: int) -> None:
        self.value.patch(data, base)

    def _copy_to(self, other: "Channel", src: Any):
        other.value.set(self.value.pos)

    def bind(self, other: Trait):
        if not isinstance(other, Channel):
            raise ValueError()
        super().bind(other)
        self._patch_listener(functools.partial(self._copy_to, other))

    def interpolate_to(self, other: Trait, steps: int):
        raise ValueError()

    def duplicate(self):
        return Channel(pos_max=self.pos_max)

    def as_fraction(self) -> float:
        return self.value.pos / self.value.pos_max


class IntensityChannel(Channel):
    # same as channel except scaled by grandmaster when written as DMX
    def __init__(self, value=0):
        super().__init__()

    def duplicate(self):
        return IntensityChannel()


class DegreesChannel(Channel):
    def __init__(self, value=0, pos_max=180):
        super().__init__(pos_max=pos_max)


class IntChannel(Channel):
    def __init__(self, value=0, pos_max=10):
        super().__init__(pos_max=pos_max)


class IndexedChannel(Trait):
    def __init__(self, values: Dict[str, int] = {}):
        super().__init__()
        self.value = IndexedByteChannelProp(values)
        self.values = values
        self.value._patch_listener(self._changed)

    def set(self, value: str):
        self.value.set_key(value)

    def patch(self, data: UniverseType, base: int) -> None:
        self.value.patch(data, base)

    def _copy_to(self, other: "Channel", src: Any):
        other.value.set(self.value.pos)

    def bind(self, other: Trait):
        if not isinstance(other, IndexedChannel):
            raise ValueError()
        if not other.values == self.values:
            raise ValueError(
                "Cannot bind IndexedChannel to one with different value dictionary"
            )
        super().bind(other)
        self._patch_listener(functools.partial(self._copy_to, other))

    def get(self) -> str:
        return self.value.key_list[self.value.pos]

    def interpolate_to(self, other: Trait, steps: int):
        raise ValueError()

    def duplicate(self):
        return IndexedChannel(values=self.values)


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
        super().bind(other)
        self._patch_listener(functools.partial(self._copy_to, other))

    def interpolate_to(self, other: Trait, steps: int):
        raise ValueError()

    def duplicate(self):
        return OnOffChannel()
