import asyncio

from textual.app import App, ComposeResult
from textual.widgets import Button, Footer, Header, Static, DataTable, Label
from textual.containers import ScrollableContainer, Grid
from textual.reactive import reactive
from textual.screen import ModalScreen

from desk import build_show, MidiCC


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

    def on_mount(self) -> None:
        self.add_columns("univ", "base", "fixture")
        self.add_rows(self.fixtures)


class MidiInfo(Static):
    def __init__(self, midi):
        super().__init__()
        self.midi = midi

    def on_mount(self) -> None:
        self.update_timer = self.set_interval(1 / 60, self.update_time)

    def update_time(self) -> None:
        self.update(f"Midi\n{self.midi}")


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


class OlaPilot(App):
    """A Textual app to manage stopwatches."""

    CSS_PATH = "stopwatch03.css"
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


if __name__ == "__main__":
    controller = build_show()
    app = OlaPilot(controller)
    app.run()
