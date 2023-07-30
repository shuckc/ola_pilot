import asyncio

from textual.app import App, ComposeResult
from textual.widgets import Button, Footer, Header, Static, DataTable, Label, OptionList, Input, Switch, Checkbox, Select
from textual.containers import ScrollableContainer, Grid, Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.binding import Binding

from rich.text import Text
from typing import Optional

from desk import build_show, MidiCC, Fixture, fixture_class_list, EFX

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
        bodict = {True: "[BLACKOUT]", False: ""}
        self.update(
            f"Showtime {hours:02,.0f}:{minutes:02.0f}:{seconds:05.2f} fps {self.controller.fps:02.0f}/{self.controller.target_fps:02.0f}  {bodict[self.controller.blackout]}"
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


class FixturesTable(DataTable):
    def __init__(
        self,
        fixtures,
    ) -> None:
        super().__init__()
        self.fixtures = fixtures
        self.traits = []

    def on_mount(self) -> None:
        self.traits = ["wash", "pos", "spot", "spot_gobo", "spot_cw"]
        self.trait_conv = [self.fmt_wash, self.fmt_pos, self.fmt_ch, self.fmt_idx, self.fmt_idx]
        for c in ["univ", "base", "ch", "fixture"] + self.traits:
            self.add_column(c, key=c)
        for f in self.fixtures:
            rk = self.add_row(*self.prep(f))
            f[2]._fixture_RowKey = rk
        self.update_timer = self.set_interval(1 / 10, self.update_time)

    def prep(self, f: Fixture):
        basic = [f[0], f[1]+1, f[2].ch, type(f[2]).__name__]
        traits = [c(getattr(f[2], t)) if hasattr(f[2], t) else "" for t,c in zip(self.traits, self.trait_conv)]
        return basic + traits

    def update_time(self) -> None:
        for f in self.fixtures:
            for t,c in zip(self.traits, self.trait_conv):
                v = c(getattr(f[2], t)) if hasattr(f[2], t) else ""
                self.update_cell(f[2]._fixture_RowKey, t, v)


    def fmt_ch(self, channel):
        v = int(channel.value / 255 * 100)
        return f"{v:2}%"

    def fmt_pos(self, position):
        return f"{position.pan:5} {position.tilt:5}"

    def fmt_wash(self, wash):
        t = f"{wash.get_red():3} {wash.get_green():3} {wash.get_blue():3}"

        return Text(t, style=wash.get_hex(), justify="right")

    def fmt_idx(self, indexed):
        return "open"

    def on_data_table_cell_selected(self, event: DataTable.CellSelected) -> None:
        def handler(value):
            pass
        row_key = event.cell_key.row_key
        fixture = [f[2] for f in self.fixtures if f[2]._fixture_RowKey == row_key][0]
        trait = event.cell_key.column_key.value
        name = f"{type(fixture).__name__}.{trait}"
        value = getattr(fixture, trait)
        self.app.push_screen(EditTraitScreen(name, value),handler)


class EFXTable(DataTable):
    def __init__(
        self,
        efx,
    ) -> None:
        super().__init__()
        self.efx = efx
        self.traits = []

    def on_mount(self) -> None:
        self.traits = ["wave", "pan_midi", "tilt_midi"]
        self.trait_conv = [self.fmt_pos, self.fmt_ch, self.fmt_ch]
        for c in ["efx"] + self.traits:
            self.add_column(c, key=c)
        for e in self.efx:
            rk = self.add_row(*self.prep(e))
            e._efx_RowKey = rk
        self.update_timer = self.set_interval(1 / 10, self.update_time)

    def prep(self, e: EFX):
        basic = [type(e).__name__]
        traits = [c(getattr(e, t)) if hasattr(e, t) else "" for t,c in zip(self.traits, self.trait_conv)]
        return basic + traits

    def update_time(self) -> None:
        for e in self.efx:
            for t,c in zip(self.traits, self.trait_conv):
                v = c(getattr(e, t)) if hasattr(e, t) else ""
                self.update_cell(e._efx_RowKey, t, v)

    def fmt_ch(self, channel):
        return f"{channel:4}%"

    def fmt_pos(self, position):
        return f"{position:5}"


class FixturesTools(Static):
    def __init__(
        self,
        controller,
    ) -> None:
        super().__init__()
        self.controller = controller

    def compose(self) -> ComposeResult:
        yield Button("Add")


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
        g.border_title="Set value"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "quit":
            self.dismiss(None)
        else:
            self.dismiss(self.old_value)
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
             [(c.__name__,i) for i,c in enumerate(fixture_class_list)],
            id="fixturelist"),
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
        g.border_title="Add fixture"

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
        ("f", "add_fixture", "Add fixture"),
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
            # + [FixturesTools(self.controller)]
            + [
                MidiInfo(midi)
                for midi in self.controller.pollable
                if isinstance(midi, MidiCC)
            ]
            + [EFXTable(self.controller.efx)]
        )
        yield ShowtimeDisplay(self.controller)

        self.t = asyncio.create_task(controller.run())

    def action_toggle_dark(self) -> None:
        """An action to toggle dark mode."""
        self.dark = not self.dark

    def action_blackout(self) -> None:
        self.controller.blackout = not self.controller.blackout

    def action_request_quit(self) -> None:
        """Action to display the quit dialog."""
        self.push_screen(QuitScreen())

    def action_add_fixture(self) -> None:
        self.push_screen(AddFixtureScreen())


if __name__ == "__main__":
    controller = build_show()
    app = OlaPilot(controller)
    app.run()
