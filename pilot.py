import asyncio
import functools
import collections
import time
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Tuple,
    TypeVar,
    Optional,
    Iterable,
)

from rich.text import Text
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Horizontal, ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    OptionList,
    Select,
    Static,
)
from textual.widgets._data_table import RowKey

from channel import ChannelProp
from desk import EFX, Fixture, MidiCC, build_show
from registration import fixture_class_list, ThingWithTraits
from trait import (
    RGB,
    RGBA,
    RGBW,
    Channel,
    IndexedChannel,
    IntChannel,
    IntensityChannel,
    OnOffTrait,
    PTPos,
    Trait,
    DegreesChannel,
)
from widgets import PositionBar

BLACKOUT_DICT = {True: "[BLACKOUT]", False: ""}
UPDATE_TIMER = 1 / 10


class ShowtimeDisplay(Static):
    """A widget to display show time, fps"""

    def __init__(
        self,
        controller,
    ) -> None:
        super().__init__()
        self.controller = controller

    def on_mount(self) -> None:
        self.update_timer = self.set_interval(UPDATE_TIMER, self.update_time)

    def update_time(self) -> None:
        st = self.controller.showtime
        minutes, seconds = divmod(st, 60)
        hours, minutes = divmod(minutes, 60)
        self.update(
            f"Showtime {hours:02,.0f}:{minutes:02.0f}:{seconds:05.2f} fps "
            + f"{self.controller.fps:02.0f}/{self.controller.target_fps:02.0f}  {BLACKOUT_DICT[self.controller.blackout]}"
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
        self.update_timer = self.set_interval(UPDATE_TIMER, self.update_time)
        self.update_time()

    def update_time(self) -> None:
        st = self.data
        s = bytes(st).hex()
        uhex = " ".join(s[i : i + 2] for i in range(0, len(s), 2))
        self.update(f"DMX {self.universe}\n{uhex}")


T = TypeVar("T", bound="ThingWithTraits")

EMPTY_TEXT = Text("")


class TraitTable(DataTable, Generic[T]):
    def __init__(self, fixtures: List[T], extra_columns: List[str] = ["name"]) -> None:
        super(TraitTable, self).__init__()
        self.fixtures: List[T] = fixtures
        self.traits: List[str] = []
        self.rk: Dict[T, RowKey] = {}
        self.rupd: Dict[T, int] = collections.defaultdict(int)
        self.extra_columns = extra_columns
        traits_keys = {}
        for f in self.fixtures:
            for k, v in f.__dict__.items():
                if isinstance(v, Trait):
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

        self.styles.scrollbar_gutter = "stable"

    def _get_basic(self, f: T) -> List[Text]:
        name = f.name
        if name is None:
            name = "None"
        return [Text(name)]

    def _get_row_data(self, f: T) -> List[Text]:
        rowdata = self._get_basic(f)
        for t in self.traits:
            try:
                a = getattr(f, t)
                if a is None:
                    rowdata.append(EMPTY_TEXT)
                else:
                    formatter = TRAIT_FORMATTER_DICT[type(a)]
                    a._patch_listener(
                        functools.partial(self.on_value_changed, f, t, a, formatter)
                    )
                    rowdata.append(formatter(a))
            except AttributeError:
                rowdata.append(EMPTY_TEXT)
        return rowdata

    def on_value_changed(
        self,
        fixture: T,
        trait_name: str,
        attr: Trait,
        formatter: Callable[[Trait], Text],
        cause: Any,
    ) -> None:
        k = (fixture, trait_name)
        last_change = self.rupd[k]
        t = time.time()
        if t - last_change < 0.5:
            return
        self.rupd[k] = t
        self.update_cell(self.rk[fixture], trait_name, formatter(attr))

    def on_data_table_cell_selected(self, event: DataTable.CellSelected) -> None:
        def handler(value):
            pass

        row_key = event.cell_key.row_key
        fixture: T = [f for f, rk in self.rk.items() if rk == row_key][0]
        trait_name = event.cell_key.column_key.value
        name = f"{fixture.name}.{trait_name}"
        if trait_name:
            try:
                trait = getattr(fixture, trait_name)
                self.app.push_screen(EditTraitScreen(name, trait), handler)
            except AttributeError:
                pass


class FixturesTable(TraitTable[Fixture]):
    BINDINGS = [
        ("f", "add_fixture", "Add fixture"),
    ]

    def __init__(self, fixtures):
        super().__init__(fixtures, ["universe", "base", "ch", "fixture"])

    def _get_basic(self, f: Fixture):
        return [
            "-" if f.universe is None else f.universe,
            "-" if f.base is None else f.base + 1,
            f.ch,
            f.name,
        ]

    def action_add_fixture(self) -> None:
        self.app.push_screen(AddFixtureScreen())


class EFXTable(TraitTable[EFX]):
    BINDINGS = [
        Binding("E", "add_efx", "Add EFX", show=True),
        Binding("Delete", "rm_efx", "Remove EFX", show=True),
    ]

    def __init__(self, efx):
        super().__init__(efx, ["name"])


def fmt_colour(rgb: RGB) -> Text:
    # t = f"⬤ {rgb.red.pos:3} {rgb.green.pos:3} {rgb.blue.pos:3}"
    return fmt_hexblob(rgb.get_hex())


@functools.lru_cache(maxsize=20000)
def fmt_hexblob(hexcolour: str) -> Text:
    t = f"⬤ "
    return Text(t, style=hexcolour)


def fmt_pos(pos: PTPos) -> Text:
    return fmt_str_inner(pos.get_degrees_str())


def fmt_ch(channel: Channel) -> Text:
    v = int(channel.value.pos / 255 * 100)
    return Text(f"{v:2}%")


def fmt_intensity(channel: IntensityChannel) -> Text:
    return fmt_intensity_inner(channel.value.pos)


@functools.lru_cache(maxsize=300)
def fmt_intensity_inner(v: int) -> Text:
    pc = int(v / 255 * 100)
    rgb = v
    text = "⬤ FL" if pc > 99 else f"⬤ {pc:2}"
    colourhex = f"#{rgb:02X}{rgb:02X}{rgb:02X}"
    return Text(text, style=colourhex)


def fmt_idxch(channel: IndexedChannel) -> Text:
    s = channel.get()
    return fmt_str_inner(s)


@functools.lru_cache(maxsize=500)
def fmt_str_inner(s: str) -> Text:
    return Text(s)


TEXT_ON_OFF = {0: Text("off"), 1: Text("on")}


def fmt_on_off(channel) -> Text:
    v = channel.value.pos
    return TEXT_ON_OFF[v]


def fmt_degrees(channel: DegreesChannel) -> Text:
    return fmt_str_inner(f"{channel.value.pos}°")


def fmt_int_ch(channel: IntChannel) -> Text:
    return fmt_str_inner(f"{channel.value.pos}")


TRAIT_FORMATTER_DICT: Dict[type[Trait], Callable[[Trait], Text]] = {
    PTPos: fmt_pos,
    RGB: fmt_colour,
    RGBA: fmt_colour,
    RGBW: fmt_colour,
    Channel: fmt_ch,
    IntensityChannel: fmt_intensity,
    IndexedChannel: fmt_idxch,
    OnOffTrait: fmt_on_off,
    DegreesChannel: fmt_degrees,
    IntChannel: fmt_int_ch,
}


class MidiInfo(Static):
    def __init__(self, midi):
        super().__init__()
        self.midi = midi

    def on_mount(self) -> None:
        self.update_timer = self.set_interval(UPDATE_TIMER, self.update_time)

    def update_time(self) -> None:
        self.update(f"Midi\n{self.midi}")


class EditTraitScreen(ModalScreen[None]):
    """Edit trait value or cancel editing"""

    DEFAULT_CSS = """
    EditTraitScreen > Vertical {
        width: 90;
        border: heavy yellow;
        background: $surface;
        padding: 0 0 0 0;
        height: auto;
    }
    EditTraitScreen > Vertical > Horizontal > Button {
        margin: 1;
    }
    EditTraitScreen > Vertical > Horizontal {
        height: auto;
    }
    EditTraitScreen > Vertical > Grid {
        margin: 0 1 0 1;
        grid-size: 2;
        grid-columns: 1fr 3fr;
        padding: 0 0 0 0;
        height: auto;
    }
    """

    BINDINGS = [
        Binding("escape", "app.pop_screen", "", show=False),
    ]

    def __init__(self, ref: str, trait: Trait):
        self.ref = ref
        self.trait = trait
        self.ch: Dict[str, ChannelProp] = dict(
            [
                (k, ch)
                for k, ch in self.trait.__dict__.items()
                if isinstance(ch, ChannelProp)
            ]
        )
        super(EditTraitScreen, self).__init__()
        self.pos_to_ch: Dict[PositionBar, ChannelProp] = {}

        self.controls: List[Widget] = []
        for k, ch in self.ch.items():
            self.controls.append(Label(k))
            self.controls.append(
                p := PositionBar(
                    position=ch.pos, position_max=ch.pos_max, position_min=ch.pos_min
                )
            )
            self.pos_to_ch[p] = ch

    def compose(self) -> ComposeResult:
        g = Grid(
            Label("Editing trait"),
            Label(self.ref),
            *self.controls,
        )
        v = Vertical(
            g,
            Horizontal(
                Button("Set", variant="primary", id="quit"),
                Button("Cancel", variant="default", id="cancel"),
            ),
        )
        yield v
        v.border_title = "Set value"

    @on(PositionBar.PositionChanged)
    def on_position_changed(self, event):
        self.trait.set_single(self.pos_to_ch[event.bar], event.position)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        # if event.button.id == "quit":
        #    self.dismiss(None)
        self.dismiss(None)


class QuitScreen(ModalScreen[bool]):
    """Screen with a dialog to quit."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield Grid(
            Label("Are you sure you want to quit?", id="question"),
            Button("Quit", variant="error", id="quit"),
            Button("Cancel", variant="primary", id="cancel"),
            id="dialog",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "quit":
            self.dismiss(True)
        else:
            self.dismiss(False)


class SavePresetScreen(ModalScreen[Optional[str]]):
    BINDINGS = [
        Binding("escape", "app.pop_screen", "", show=False),
    ]

    def __init__(self, last_preset: Optional[str]):
        self.last_preset = last_preset
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("Save preset", id="question"),
            Input(
                placeholder="Preset name",
                value=self.last_preset,
            ),
            Horizontal(
                Button("Save", variant="error", id="save"),
                Button("Cancel", variant="primary", id="cancel"),
            ),
            id="dialog",
        )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            self.dismiss(None)
        else:
            self.dismiss(None)


class LoadPresetScreen(ModalScreen[Optional[str]]):
    BINDINGS = [
        Binding("escape", "app.pop_screen", "", show=False),
    ]

    def __init__(self, choices: List[str], last_preset: Optional[str]):
        self.choices = choices
        self.last_preset = last_preset
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("Load Preset"),
            ol := OptionList(
                *self.choices,
            ),
            Button("Cancel", variant="primary", id="cancel"),
            id="dialog",
        )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(self.choices[event.option_index])

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            self.dismiss(None)
        else:
            self.dismiss(None)


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
    """A Textual app to manage DMX lighting."""

    CSS_PATH = "pilot.css"
    BINDINGS = [
        ("d", "toggle_dark", "Toggle dark mode"),
        ("b", "blackout", "Toggle blackout"),
        ("q", "request_quit", "Quit?"),
        ("s", "save_preset", "Save preset"),
        ("l", "load_preset", "Load preset"),
    ]

    def __init__(
        self, controller, show_dmx=True, show_efx=True, show_fixtures=True
    ) -> None:
        super().__init__()
        self.controller = controller
        self.last_preset: Optional[str] = None
        self.show_dmx = show_dmx
        self.show_efx = show_efx
        self.show_fixtures = show_fixtures

    def compose(self) -> ComposeResult:
        contents: List[Widget] = []
        if self.show_dmx:
            for univ, data in self.controller.universes.items():
                contents.append(UniverseDisplay(univ, data))

        if self.show_fixtures:
            contents.append(FixturesTable(self.controller.fixtures))

        for midi in self.controller.pollable:
            if isinstance(midi, MidiCC):
                contents.append(MidiInfo(midi))

        if self.show_efx:
            contents.append(EFXTable(self.controller.efx))

        """Create child widgets for the app."""
        yield Header()
        yield Footer()
        yield ScrollableContainer(*contents)
        yield ShowtimeDisplay(self.controller)

        self.t = asyncio.create_task(self.controller_run())

        self.update_title()

    async def controller_run(self):
        try:
            await self.controller.run()
        except Exception as e:
            self.log(e)

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

        def quit_cb(quit: bool):
            if quit:
                self.app.exit()

        self.push_screen(QuitScreen(), quit_cb)

    def action_save_preset(self) -> None:
        def save_preset_cb(name: Optional[str]):
            if name is not None:
                self.last_preset = name
                self.controller.save_preset(name)

        self.push_screen(SavePresetScreen(self.last_preset), save_preset_cb)

    def action_load_preset(self) -> None:
        def load_preset_cb(name: Optional[str]):
            if name is not None:
                self.last_preset = name
                self.controller.load_preset(name)

        self.push_screen(
            LoadPresetScreen(list(self.controller.presets.keys()), self.last_preset),
            load_preset_cb,
        )


if __name__ == "__main__":
    controller = build_show()
    app = OlaPilot(controller)
    app.run()
    print("finished")
    controller.save_showfile()
