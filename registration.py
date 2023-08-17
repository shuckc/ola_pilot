from abc import ABC, abstractmethod
from typing import List, Optional

from channel import UniverseType
from trait import OnOffChannel, Trait


class Fixture(ABC):
    def __init__(self, ch=0):
        self.universe: Optional[int] = None
        self.base: Optional[int] = None
        self.ch: int = ch

    @abstractmethod
    def patch(self, universe: int, base: int, data: UniverseType) -> None:
        self.universe = universe
        self.base = base


class EFX:
    def __init__(self, target):
        self.enabled = OnOffChannel()
        self.target = target
        self.can_act_on = [Trait]

    def tick(self, counter):
        pass


fixture_class_list: List[type[Fixture]] = []
efx_class_list: List[type[EFX]] = []


def fixture(wrapped: type[Fixture]):
    fixture_class_list.append(wrapped)
    return wrapped


def register_efx(wrapped: type[EFX]):
    efx_class_list.append(wrapped)
    return wrapped
