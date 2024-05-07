from abc import ABC, abstractmethod
from typing import List, Optional, Any, Iterator, Tuple, Dict

from channel import UniverseType
from trait import OnOffTrait, Trait


class Pollable:
    def tick(self, showtime: float) -> None:
        pass


class ThingWithTraits:
    def __init__(self) -> None:
        self.owner: Optional[Any] = None
        self.name: Optional[str] = None

    def set_owner_name(self, owner: Any, name: str) -> None:
        self.owner = owner
        self.name = name

    def get_state_as_dict(self):
        d = {}
        for k, t in self.trait_items():
            if not t.is_bound:
                d[k] = t.get_state_as_dict()
        return d

    def get_global_as_dict(self):
        d = {}
        for k, t in self.trait_items():
            if not t.is_bound:
                d[k] = t.get_global_as_dict()
        return d

    def set_state(self, state: Dict[str, Any]) -> None:
        d = dict(list(self.trait_items()))
        for k, t in state.items():
            tr = d.get(k)
            if tr is not None:
                tr.set_state(t)

    def set_global(self, state: Dict[str, Any]) -> None:
        d = dict(list(self.trait_items()))
        for k, t in state.items():
            tr = d.get(k)
            if tr is not None:
                tr.set_global(t)

    def trait_items(self) -> Iterator[Tuple[str, Trait]]:
        for k, v in self.__dict__.items():
            if isinstance(v, Trait):
                yield k, v


class Fixture(ThingWithTraits, ABC):
    def __init__(self, ch: int = 0):
        self.universe: Optional[int] = None
        self.base: Optional[int] = None
        self.ch: int = ch
        super().__init__()

    @abstractmethod
    def patch(self, universe: int, base: int, data: UniverseType) -> None:
        self.universe = universe
        self.base = base


class EFX(ThingWithTraits, Pollable):
    def __init__(self):
        super().__init__()


class EnabledEFX:
    def __init__(self):
        super().__init__()
        self.enabled = OnOffTrait()


fixture_class_list: List[type[Fixture]] = []
efx_class_list: List[type[EFX]] = []


def fixture(wrapped: type[Fixture]):
    fixture_class_list.append(wrapped)
    return wrapped


def register_efx(wrapped: type[EFX]):
    efx_class_list.append(wrapped)
    return wrapped
