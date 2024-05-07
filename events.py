from typing import Callable, TypeVar, Generic
from collections import UserDict


T = TypeVar("T")


class Observable(Generic[T]):
    def __init__(self) -> None:
        self._listeners: dict[Callable[[T], None], None] = {}
        super().__init__()

    def _patch_listener(self, listener: Callable[[T], None]) -> None:
        self._listeners[listener] = None

    def sub(self, listener: Callable[[T], None]) -> None:
        self._listeners[listener] = None

    def unsub(self, callback: Callable[[T], None]) -> None:
        del self._listeners[callback]

    def notify(self, context: T) -> None:
        self._changed(context)

    def _changed(self, context: T) -> None:
        for listener in self._listeners.keys():
            listener(context)


OK = TypeVar("OK")
OV = TypeVar("OV")


class ObservableDict(UserDict, Generic[OK, OV]):
    def __init__(self) -> None:
        self.added: Observable[OK] = Observable()
        self.changed: Observable[OK] = Observable()
        self.removed: Observable[OK] = Observable()
        super().__init__()

    def __setitem__(self, key: OK, value: OV):
        existing = key in self.data
        super().__setitem__(key, value)
        if existing:
            self.changed.notify(key)
        else:
            self.added.notify(key)

    def __delitem__(self, key: OK):
        del self.data[key]
        self.removed.notify(key)
