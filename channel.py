from abc import ABC, abstractmethod
from typing import Any, Callable, List, MutableSequence, TypeAlias, Optional, Dict, Any

UniverseType: TypeAlias = MutableSequence[int]


class ChannelProp(ABC):
    # Note that pos_max is a valid value of pos, ie. max is inclusive
    def __init__(self, pos_min: int = 0, pos_max: int = 255, pos: int = 0, units=""):
        super().__init__()
        self.pos_min = pos_min
        self.pos_max = pos_max
        self.pos = pos
        self.data: Optional[UniverseType] = None
        self.base = 0

    def patch(self, data: UniverseType, base: int) -> None:
        self.data = data
        self.base = base
        self._write_dmx()

    def set(self, value: int, source=None) -> bool:
        np = min(self.pos_max, max(self.pos_min, int(value)))
        changed = np != self.pos
        self.pos = np
        if changed:
            self._write_dmx()
        return changed

    @abstractmethod
    def _write_dmx(self):
        pass

    def add_state(self, key: str, d: Dict[str, Any]):
        d[key] = self.pos

    def add_global(self, key: str, d: Dict[str, Any]):
        d[key] = self.pos


class ByteChannelProp(ChannelProp):
    def _write_dmx(self):
        if self.data:
            self.data[self.base] = self.pos


class FineChannelProp(ChannelProp):
    def __init__(self):
        super().__init__(pos_max=0xFFFF)

    def _write_dmx(self):
        if self.data:
            self.data[self.base] = self.pos >> 8
            self.data[self.base + 1] = self.pos & 0xFF


class IndexedByteChannelProp(ByteChannelProp):
    def __init__(self, values: Dict[str, int]):
        super().__init__(pos_max=len(values) - 1)
        self.key_list: List[str] = list(values)
        self.values: Dict[str, int] = values
        self.keys_to_pos = dict([(k, i) for i, k in enumerate(self.key_list)])

    def _write_dmx(self):
        key: str = self.key_list[self.pos]
        v = self.values[key]
        if self.data:
            self.data[self.base] = v

    def set_key(self, key: str) -> bool:
        pos: int = self.keys_to_pos.get(key, 0)
        print(f" set by key {key} to pos {pos} using {self.keys_to_pos}")
        return super().set(pos)
