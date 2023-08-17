from abc import ABC, abstractmethod
from typing import Any, Callable, List, MutableSequence, TypeAlias

from trait import Trait

UniverseType: TypeAlias = MutableSequence[int]


class Observable:
    def __init__(self):
        self._listeners: List[Callable[[Any], None]] = []
        super().__init__()

    def patch_listener(self, listener: Callable[[Trait], None]):
        self._listeners.append(listener)

    def _changed(self, change_from):
        for l in self._listeners:
            l(change_from)


class ChannelProp(Observable, ABC):
    def __init__(self, pos_min=0, pos_max=255, pos=0, units=""):
        super().__init__()
        self.pos_min = pos_min
        self.pos_max = pos_max
        self.pos = pos
        self.data = None
        self.base = 0

    def patch(self, data: UniverseType, base: int):
        self.data = data
        self.base = base
        self._write_dmx()

    @abstractmethod
    def set(self, value: int):
        pass

    @abstractmethod
    def _write_dmx(self):
        pass


class ByteChannelProp(ChannelProp):
    def set(self, value: int):
        self.pos = min(0xFF, max(0, int(value)))
        self._write_dmx()
        self._changed(self)

    def _write_dmx(self):
        if self.data:
            self.data[self.base] = self.pos


class FineChannelProp(ChannelProp):
    def set(self, value: int):
        self.pos = min(0xFFFF, max(0, int(value)))
        self._write_dmx()
        self._changed(self)

    def _write_dmx(self):
        if self.data:
            self.data[self.base] = self.pos >> 8
            self.data[self.base + 1] = self.pos & 0xFF
