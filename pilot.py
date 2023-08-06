import asyncio

from textual.app import App, ComposeResult
from textual.widgets import (
    Button,
    Footer,
    Header,
    Static,
    DataTable,
    Label,
    OptionList,
    Input,
    Switch,
    Checkbox,
    Select,
)
from textual.containers import ScrollableContainer, Grid, Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.binding import Binding
from textual.widgets._data_table import RowKey

from rich.text import Text
from typing import Optional, List, Dict, Any, Tuple, Callable, TypeVar, Generic

from desk import (
    build_show,
    MidiCC,
    Fixture,
    fixture_class_list,
    EFX,
    PTPos,
    RGB,
    RGBA,
    RGBW,
    Channel,
    IndexedChannel,
    Trait,
    OnOffChannel,
)

BLACKOUT_DICT = {True: "[BLACKOUT]", False: ""}


class ShowtimeDisplay(Static):
    """A widget to display show time, fps"""

    def __init__(
        self,
        controller,
    ) -> None:
        super().__init__()
        self.controller = controller

    def on_mount(self) -> None:
        self.update_timer = self.set_interval(1 / 60, self.update_time)

    def update_time(self) -> None:
        st = self.controller.showtime
        minutes, seconds = divmod(st, 60)
        hours, minutes = divmod(minutes, 60)
        self.update(
            f"Showtime {hours:02,.0f}:{minutes:02.0f}:{seconds:05.2f} fps {self.controller.fps:02.0f}/{self.controller.target_fps:02.0f}  {BLACKOUT_DICT[self.controller.blackout]}"
        )


class UniverseDisplay(Static):
    def __init__(
        self,
        universe,
        data,
    ) -> None:
        super().__init__()
        self.universe = universe
        self.data = data

    def on_mount(self) -> None:
        self.update_timer = self.set_interval(1 / 60, self.update_time)

    def update_time(self) -> None:
        st = self.data
        s = bytes(st).hex()
        uhex = " ".join(s[i : i + 2] for i in range(0, len(s), 2))
        self.update(f"DMX {self.universe}\n{uhex}")


T = TypeVar("T")


class TraitTable(DataTable, Generic[T]):
    def __init__(self, fixtures: List[T], extra_columns: List[str] = ["name"]) -> None:
        super().__init__()
        self.fixtures: List[T] = fixtures
        self.traits: List[str] = []
        self.traits_fmt: Dict[Tuple[str, type], Callable[[int], str]] = {}
        self.rk: Dict[T, RowKey] = {}
        self.extra_columns = extra_columns
        traits_keys = {}
        for f in self.fixtures:
            for k, v in f.__dict__.items():
                if isinstance(v, Trait):
                    self.traits_fmt[(k, type(v))] = TRAIT_FORMATTER_DICT[type(v)]
                    traits_keys[k] = True

        self.traits.extend(list(traits_keys.keys()))

    def on_mount(self) -> None:
        # iterate fixtures for traits, build dicts
        # traits with same nuderlying type and name over multiple fixures go in same column

        for c in self.extra_columns + self.traits:
            self.add_column(c, key=c)
        for f in self.fixtures:
            p = self._get_row_data(f)
            rk = self.add_row(*p)
            self.rk[f] = rk

        self.update_timer = self.set_interval(1 / 10, self.update_time)

    def _get_basic(self, f: T):
        return [type(f).__name__]

    def _get_row_data(self, f: T):
        rowdata = self._get_basic(f)
        for t in self.traits:
            try:
                a = getattr(f, t)
                fmt = self.traits_fmt[(t, type(a))]
                rowdata.append(fmt(a))
            except AttributeError:
                rowdata.append("")
        return rowdata

    def update_time(self) -> None:
        for f in self.fixtures:
            for t in self.traits:
                try:
                    a = getattr(f, t)
                    fmt = self.traits_fmt[(t, type(a))]
                    self.update_cell(self.rk[f], t, fmt(a))
                except AttributeError:
                    pass

    def on_data_table_cell_selected(self, event: DataTable.CellSelected) -> None:
        def handler(value):
            pass

        row_key = event.cell_key.row_key
        fixture: T = [f for f, rk in self.rk.items() if rk == row_key][0]
        trait = event.cell_key.column_key.value
        name = f"{type(fixture).__name__}.{trait}"
        if trait:
            try:
                value = getattr(fixture, trait)
                self.app.push_screen(EditTraitScreen(name, value), handler)
            except AttributeError:
                pass


class FixturesTable(TraitTable[Fixture]):
    BINDINGS = [
        ("f", "add_fixture", "Add fixture"),
    ]

    def __init__(self, fixtures):
        super().__init__(fixtures, ["universe", "base", "ch", "fixture"])

    def _get_basic(self, f: T):
        return [f.universe, f.base + 1 if f.base else "-", f.ch, type(f).__name__]

    def action_add_fixture(self) -> None:
        self.push_screen(AddFixtureScreen())


class EFXTable(TraitTable[EFX]):
    BINDINGS = [
        Binding("E", "add_efx", "Add EFX", show=True),
        Binding("Delete", "rm_efx", "Remove EFX", show=True),
    ]

    def __init__(self, efx):
        super().__init__(efx, ["name"])


def fmt_colour(rgb):
    t = f"{rgb.red.pos:3} {rgb.green.pos:3} {rgb.blue.pos:3}"
    return Text(t, style=rgb.get_hex(), justify="right")


def fmt_pos(pos):
    return f"{pos.pan.pos:5} {pos.tilt.pos:5}"


def fmt_ch(channel):
    v = int(channel.value.pos / 255 * 100)
    return f"{v:2}%"


def fmt_idxch(indexed):
    return "open"


def fmt_on_off(channel):
    v = channel.value.pos
    return {0: "off", 1: "on"}[v]


TRAIT_FORMATTER_DICT = {
    PTPos: fmt_pos,
    RGB: fmt_colour,
    RGBA: fmt_colour,
    RGBW: fmt_colour,
    Channel: fmt_ch,
    IndexedChannel: fmt_idxch,
    OnOffChannel: fmt_on_off,
}


class MidiInfo(Static):
    def __init__(self, midi):
        super().__init__()
        self.midi = midi

    def on_mount(self) -> None:
        self.update_timer = self.set_interval(1 / 60, self.update_time)

    def update_time(self) -> None:
        self.update(f"Midi\n{self.midi}")


class EditTraitScreen(ModalScreen[Optional[int]]):
    """Edit trait value or cancel editing"""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "", show=False),
    ]

    def __init__(self, ref, old_value):
        self.ref = ref
        self.old_value = str(old_value)
        super().__init__()

    def compose(self) -> ComposeResult:
        g = Grid(
            Label("Fixture"),
            Label(self.ref),
            Label("Value"),
            Input(self.old_value),
            Button("Set", variant="primary", id="quit"),
            Button("Cancel", variant="default", id="cancel"),
            id="dialog3",
        )
        yield g
        g.border_title = "Set value"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "quit":
            self.dismiss(None)
        else:
            self.dismiss(int(self.old_value))
        # self.app.pop_screen()


class QuitScreen(ModalScreen):
    """Screen with a dialog to quit."""

    def compose(self) -> ComposeResult:
        yield Grid(
            Label("Are you sure you want to quit?", id="question"),
            Button("Quit", variant="error", id="quit"),
            Button("Cancel", variant="primary", id="cancel"),
            id="dialog",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "quit":
            self.app.exit()
        else:
            self.app.pop_screen()


class AddFixtureScreen(ModalScreen):
    """Browse fixture list and dynamic add."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "", show=False),
    ]

    def compose(self) -> ComposeResult:
        g = Grid(
            Label("Fixture"),
            Select(
                [(c.__name__, i) for i, c in enumerate(fixture_class_list)],
                id="fixturelist",
            ),
            Label("Quantity"),
            Input("1"),
            Label("Patch?"),
            Checkbox("Patch", id="patch"),
            Label("Universe"),
            Input("1"),
            Label("First address"),
            Input("1"),
            Label("Spacing"),
            Input("10"),
            Button("Add", variant="primary", id="quit"),
            Button("Cancel", variant="default", id="cancel"),
            id="dialog2",
        )
        yield g
        g.border_title = "Add fixture"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "quit":
            pass
        self.app.pop_screen()


class OlaPilot(App):
    """A Textual app to manage stopwatches."""

    CSS_PATH = "pilot.css"
    BINDINGS = [
        ("d", "toggle_dark", "Toggle dark mode"),
        ("b", "blackout", "Toggle blackout"),
        ("q", "request_quit", "Quit?"),
    ]

    def __init__(
        self,
        controller,
    ) -> None:
        super().__init__()
        self.controller = controller

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield Footer()
        yield ScrollableContainer(
            *[
                UniverseDisplay(univ, data)
                for univ, data in self.controller.universes.items()
            ]
            + [FixturesTable(self.controller.fixtures)]
            + [
                MidiInfo(midi)
                for midi in self.controller.pollable
                if isinstance(midi, MidiCC)
            ]
            + [EFXTable(self.controller.efx)]
        )
        yield ShowtimeDisplay(self.controller)

        self.t = asyncio.create_task(controller.run())
        self.update_title()

    def update_title(self):
        title = f"OLA Pilot {BLACKOUT_DICT[self.controller.blackout]}"
        self.console.set_window_title(title)

    def action_toggle_dark(self) -> None:
        """An action to toggle dark mode."""
        self.dark = not self.dark

    def action_blackout(self) -> None:
        self.controller.blackout = not self.controller.blackout

    def action_request_quit(self) -> None:
        """Action to display the quit dialog."""
        self.push_screen(QuitScreen())


if __name__ == "__main__":
    controller = build_show()
    app = OlaPilot(controller)
    app.run()
