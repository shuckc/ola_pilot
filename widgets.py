from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from rich.style import Style
from textual import on
from textual.app import App, ComposeResult, RenderResult
from textual.binding import Binding
from textual.containers import Center, Horizontal, Middle
from textual.geometry import clamp
from textual.message import Message
from textual.reactive import reactive
from textual.renderables.bar import Bar as BarRenderable
from textual.timer import Timer
from textual.widget import Widget
from textual.widgets import Button, Footer, Label


class Bar(Widget, can_focus=True):
    """The bar portion of the progress bar."""

    COMPONENT_CLASSES = {"bar--bar", "bar--complete"}
    """
    The bar sub-widget provides the component classes that follow.

    These component classes let you modify the foreground and background color of the
    bar in its different states.

    | Class | Description |
    | :- | :- |
    | `bar--bar` | Style of the bar (may be used to change the color). |
    | `bar--complete` | Style of the bar when it's complete. |
    | `bar--focus` | Style of the bar when it has focus. |
    """

    DEFAULT_CSS = """
    Bar {
        width: 32;
        height: 1;
    }
    Bar > .bar--bar {
        color: $warning;
        background: $foreground 10%;
    }
    Bar:focus > .bar--bar {
        color: $error;
        background: $foreground 30%;
    }
    Bar > .bar--complete {
        color: $success;
        background: $foreground 10%;
    }
    Bar:focus > .bar--complete {
        color: $error;
        background: $foreground 30%;
    }
    """

    BINDINGS = [
        Binding("up", "increase", "Increase value (fine)", show=True),
        Binding("down", "decrease", "Decrease value (fine)", show=True),
        Binding("pageup", "page_up", "Increase value (course)", show=True),
        Binding("pagedown", "page_down", "Decrease value (course)", show=True),
    ]

    _percentage: reactive[float] = reactive[float](0.0)
    """The percentage of progress that has been completed."""

    class PositionDelta(Message):
        """Posted when the value of the slider changes.
        This message can be handled using an `on_slider_changed` method.
        """

        def __init__(self, bar: Bar, change: int) -> None:
            super().__init__()
            self.change: int = change
            self.bar: Bar = bar

        @property
        def control(self) -> Bar:
            return self.bar

    def __init__(
        self,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ):
        """Create a bar for a [`ProgressBar`][textual.widgets.ProgressBar]."""
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self._percentage = 0.0

    def watch__percentage(self, percentage: float) -> None:
        pass

    def render(self) -> RenderResult:
        """Render the bar with the correct portion filled."""
        bar_style = (
            self.get_component_rich_style("bar--bar")
            if self._percentage < 1
            else self.get_component_rich_style("bar--complete")
        )
        return BarRenderable(
            highlight_range=(0, self.size.width * self._percentage),
            highlight_style=Style.from_color(bar_style.color),
            background_style=Style.from_color(bar_style.bgcolor),
        )

    def action_page_up(self) -> None:
        """Move the cursor one page up."""
        self.post_message(self.PositionDelta(self, +10))

    def action_page_down(self) -> None:
        self.post_message(self.PositionDelta(self, -10))

    def action_increase(self) -> None:
        self.post_message(self.PositionDelta(self, +1))

    def action_decrease(self) -> None:
        self.post_message(self.PositionDelta(self, -1))


class PercentageStatus(Label):
    """A label to display the percentage status of the progress bar."""

    DEFAULT_CSS = """
    PercentageStatus {
        width: 4;
        content-align-horizontal: right;
    }
    """

    _label_text: reactive[str] = reactive("", repaint=False)
    """This is used as an auxiliary reactive to only refresh the label when needed."""
    _percentage: reactive[float | None] = reactive[Optional[float]](None)
    """The percentage of progress that has been completed."""

    def __init__(
        self,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ):
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self._percentage = None
        self._label_text = "--%"

    def watch__percentage(self, percentage: float | None) -> None:
        """Manage the text that shows the percentage of progress."""
        if percentage is None:
            self._label_text = "---%"
        else:
            self._label_text = f"{int(100 * percentage)}%"

    def watch__label_text(self, label_text: str) -> None:
        """If the label text changed, update the renderable (which also refreshes)."""
        self.update(label_text)


class FormattedValueLabel(Label):
    """A label to display the estimated time until completion of the progress bar."""

    DEFAULT_CSS = """
    FormattedValueLabel {
        width: 7;
        content-align-horizontal: right;
    }
    """

    _label_text: reactive[str] = reactive("", repaint=False)
    """This is used as an auxiliary reactive to only refresh the label when needed."""
    _value: reactive[int] = reactive[int](1)

    def __init__(
        self,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
        formatter: Callable[[int], str] = str,
    ):
        self.formatter = formatter
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self._value = 0
        self._label_text = f"{self.formatter(self._value)}"

    def watch__value(self, position: int | None) -> None:
        self._label_text = f"{self.formatter(self._value)}"

    def watch__label_text(self, label_text: str) -> None:
        """If the ETA label changed, update the renderable (which also refreshes)."""
        self.update(label_text)


class PositionBar(Widget, can_focus=False):
    """A progress bar widget."""

    DEFAULT_CSS = """
    PositionBar > Horizontal {
        width: auto;
        height: auto;
    }
    PositionBar {
        width: auto;
        height: 1;
    }
    PositionBar > Horizontal > #label_dash {
        color: grey;
    }
    PositionBar > Horizontal > #label_min {
        content-align-horizontal: right;
        color: grey;
        margin-right: 1;
    }

    PositionBar > Horizontal > #label_max {
        content-align-horizontal: left;
        color: grey;
        margin-left: 1;
    }

    """

    @dataclass
    class PositionChanged(Message):
        """Posted when the value of the slider changes.
        This message can be handled using an `on_slider_changed` method.
        """

        bar: PositionBar
        position_min: int
        position: int
        position_max: int

    """The progress so far, in number of steps."""
    position: reactive[int] = reactive(0)
    position_min: reactive[int] = reactive(0)
    position_max: reactive[int] = reactive(100)

    percentage: reactive[float | None] = reactive[Optional[float]](None)
    """The percentage of progress that has been completed.

    The percentage is a value between 0 and 1

    Example:
        ```py
        position_bar = PositionBar(0,0,100)
        print(position_bar.percentage)  # 0
        position_bar.update(total=100)
        position_bar.adjust(50)
        print(position_bar.percentage)  # 0.5
        ```
    """

    def __init__(
        self,
        position_min: int,
        position: int,
        position_max: int,
        formatter: Callable[[int], str] = str,
        *,
        show_bar: bool = True,
        show_percentage: bool = True,
        show_value: bool = True,
        show_range: bool = True,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ):
        """Create a Position Bar widget.

        The progress bar uses "steps" as the measurement unit.

        Example:
            ```py
            class MyApp(App):
                def compose(self):
                    yield ProgressBar(position_min=0, position_max=100, position=5)

                def key_space(self):
                    self.query_one(ProgressBar).adjust(5)
            ```

        Args:
            show_bar: Whether to show the bar portion of the progress bar.
            show_percentage: Whether to show the percentage status of the bar.
            show_value: Whether to show the min/value/max.
            name: The name of the widget.
            id: The ID of the widget in the DOM.
            classes: The CSS classes for the widget.
            disabled: Whether the widget is disabled or not.
        """
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self.formatter = formatter
        self.show_bar = show_bar
        self.show_percentage = show_percentage
        self.show_value = show_value
        self.show_range = show_range

        self.position_max = position_max
        self.position_min = position_min
        self.position = position

    def compose(self) -> ComposeResult:
        # We create a closure so that we can determine what are the sub-widgets
        # that are present and, therefore, will need to be notified about changes
        # to the percentage.
        def update_widget_value(
            widget: Widget, attrib: str
        ) -> Callable[[float | None], None]:
            """Closure to allow updating the percentage of a given widget."""

            def updater(percentage: float | None) -> None:
                """Update the percentage reactive of the enclosed widget."""
                setattr(widget, attrib, percentage)

            return updater

        with Horizontal():
            if self.show_range:
                min_label = FormattedValueLabel(
                    id="label_min", formatter=self.formatter
                )
                self.watch(
                    self, "position_min", update_widget_value(min_label, "_value")
                )
                yield min_label
            if self.show_bar:
                bar = Bar(id="bar")
                self.watch(self, "percentage", update_widget_value(bar, "_percentage"))
                yield bar
            elif self.show_range:
                yield Label("-", id="label_dash")
            if self.show_range:
                max_label = FormattedValueLabel(
                    id="label_max", formatter=self.formatter
                )
                self.watch(
                    self, "position_max", update_widget_value(max_label, "_value")
                )
                yield max_label

            if self.show_percentage:
                percentage_status = PercentageStatus(id="percentage")
                self.watch(
                    self,
                    "percentage",
                    update_widget_value(percentage_status, "_percentage"),
                )
                yield percentage_status
            if self.show_value:
                value_label = FormattedValueLabel(id="value", formatter=self.formatter)
                self.watch(self, "position", update_widget_value(value_label, "_value"))
                yield value_label

    def validate_position(self, position: float) -> float:
        """Clamp the position between minimum and the maximum."""
        return clamp(position, self.position_min, self.position_max)

    def compute_percentage(self) -> float | None:
        """Keep the percentage of progress updated automatically.

        This will report a percentage of `1` if the total is zero.
        """
        if self.position_min == self.position_max:
            return 0.0
        return (self.position - self.position_min) / (
            self.position_max - self.position_min
        )

    def adjust(self, adjust: int = 1) -> None:
        """Adjust the value of the position bar by the given amount.

        Example:
            ```py
            progress_bar.adjust(-10)  # Back 10 steps.
            ```
        Args:
            adjust: Number of steps to adjust position by.
        """
        self.position += adjust

    def update(
        self,
        *,
        position_min: int | None = None,
        position_max: int | None = None,
        position: int | None = None,
        adjust: int | None = None,
    ) -> None:
        """Update the progress bar with the given options.

        Options only affect the progress bar if they are not `None`.

        Example:
            ```py
            progress_bar.update(
                position=50,
                position_max=150,
            )
            ```

        Args:
            position_max: New maximum value (if not `None`)
            position_min: New minimum value (if not `None`)
            position: Set the progress to the given number of steps (if not `None`).
            adjust: Adjust position by this number of steps (if not `None`).
        """
        if position_min is not None:
            self.position_min = position_min
        if position_max is not None:
            self.position_max = position_max
        if position is not None:
            self.position = position
        if adjust is not None:
            self.position += adjust

    @on(Bar.PositionDelta)
    def _update_position(self, event) -> None:
        old_position = self.position
        self.position = self.position + event.change
        if self.position != old_position:
            self.post_message(
                self.PositionChanged(
                    self, self.position_min, self.position, self.position_max
                )
            )


class DemoPositionBar(App[None]):
    BINDINGS = [("r", "reset", "Reset")]

    progress_timer: Timer

    def compose(self) -> ComposeResult:
        def degrees(n):
            return f"{(n/10)}°"

        def pounds(n):
            return f"£{(n/100):.2f}"

        def ppmco2(n):
            return f"{(n/100):.2f}ppm CO²"

        with Center():
            with Middle():
                yield Label("PositionBar Demo")
                yield Label("\nFully featured")
                yield PositionBar(0, 1, 1, id="hi1f")
                yield PositionBar(0, 100, 300, id="hi1")
                yield Label("\nWith unit formatter")
                yield PositionBar(-200, 300, 400, id="hi2", formatter=degrees)
                yield PositionBar(200, 300, 400, id="hi3", formatter=pounds)
                yield PositionBar(0, 56, 255, id="hi4", formatter=hex)
                yield PositionBar(0, 0, 0, id="hi4z")
                yield Label("\nWithout range")
                yield PositionBar(
                    -200, 300, 400, id="hi5", formatter=degrees, show_range=False
                )
                yield Label("\nWithout range, percentage")
                yield PositionBar(
                    200,
                    300,
                    400,
                    id="hi6",
                    formatter=pounds,
                    show_range=False,
                    show_percentage=False,
                )
                yield Label("\nWithout range, percentage, value")
                yield PositionBar(
                    20,
                    30,
                    40,
                    id="hi7",
                    show_range=False,
                    show_percentage=False,
                    show_value=False,
                )

                yield Label("\nWithout bar")
                yield PositionBar(
                    20,
                    30,
                    40,
                    id="hi8",
                    show_range=True,
                    show_percentage=False,
                    show_bar=False,
                )
                yield PositionBar(
                    20,
                    30,
                    40,
                    id="hi9",
                    show_range=False,
                    show_percentage=False,
                    show_bar=False,
                    formatter=ppmco2,
                )
                yield Label("Last value: N/A", id="last_value")

                yield Button("Quit")

        yield Footer()

    def on_mount(self) -> None:
        """Set up a timer to simulate progess happening."""
        self.progress_timer = self.set_interval(1 / 10, self.make_progress)

    def make_progress(self) -> None:
        """Called automatically to adjust the progress bar."""
        self.query_one("#hi1", PositionBar).adjust(1)
        self.query_one("#hi2", PositionBar).adjust(1)

    def action_reset(self) -> None:
        self.query_one("#hi2", PositionBar).update(position=175)
        self.query_one("#hi3", PositionBar).update(
            position_max=200, position=175, position_min=50
        )

    def on_button_pressed(self, button):
        exit()

    @on(PositionBar.PositionChanged)
    def on_position_changed(self, event):
        self.query_one("#last_value", Label).update(f"Last value: {event}")


if __name__ == "__main__":
    DemoPositionBar().run()
