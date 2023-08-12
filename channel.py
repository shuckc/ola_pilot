from abc import ABC, abstractmethod
from typing import Optional, TypeAlias, List, MutableSequence


UniverseType: TypeAlias = MutableSequence[int]


class ChannelProp(ABC):
    def __init__(self, pos_min=0, pos_max=255, pos=0, units=""):
        self.pos_min = pos_min
        self.pos_max = pos_max
        self.pos = pos
        self.data = None
        self.base = 0

    def patch(self, data: UniverseType, base: int):
        self.data = data
        self.base = base
        self.set(self.pos)

    @abstractmethod
    def set(self, value: int):
        pass


class ByteChannelProp(ChannelProp):
    def set(self, value: int):
        self.pos = min(0xFF, max(0, int(value)))
        if self.data:
            self.data[self.base] = value


class FineChannelProp(ChannelProp):
    def __init__(self, pos_min=0, pos_max=0xFFFF, pos=0, units=""):
        super().__init__(pos_min=pos_min, pos_max=pos_max, pos=pos)

    def set(self, value: int):
        self.pos = min(0xFFFF, max(0, int(value)))
        if self.data:
            self.data[self.base] = self.pos >> 8
            self.data[self.base + 1] = self.pos & 0xFF
