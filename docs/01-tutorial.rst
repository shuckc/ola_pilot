Tutorial
========

This is a simple example controlling a single RGB LED par, set to address 50 with `ola_pilot` and `ola`.


Prequisites
-----------

.. code-block:: console

    $ pip install ola_pilot


Now lets write a showfile `demo.py`:

.. code-block:: python

    from ola_pilot import Controller, Fixture
    from ola_pilot.trait import RGB

    class ToyFixture(Fixture):
        wash = RGB()

    tf = ToyFixture()
    controller = Controller()
    controller.add_fixture(tf, univ=0, base=50)

We can launch this show file:

.. code-block:: console

    $ ola_pilot tui demo.py

You will see the terminal UI, with the fixtures and patching shown:

.. raw:: html
    :file: screen-basic.svg

Navigate in the terminal app using the cursor keys within a table (:kbd:`Up, Left, Right, Down`). Move to the 'wash' column for ToyFixture-0. Pressing :kbd:`Enter` edits a trait value, and :kbd:`Escape` dismisses the trait editor.

Within the Trait Editor, pressing and :kbd:`Tab` (and :kbd:`Shift-tab`) moves the focus between the three sliders. We can make adjustments rapidly with the cursor keys as follows:

* :kbd:`Up` and :kbd:`Down` move the value up or down by 0.1%.
* :kbd:`PageUp` and :kbd:`PageDown` move by +10% or -10%.
* :kbd:`F` jumps to the full value, :kbd:`Z` to zero and :kbd:`H` to halfway.

As we change the RGB sliders the DMX (universe 0) addresses for R (50), G (51) and B (52) change accordingly:

.. raw:: html
    :file: screen-basic-change.svg

The DMX universes are being calculated but not yet sent to any hardware. To do this setup some DMX hardware (ie. DMX adapters) using 'ola' and then connect our controller object to the ola instance, like this:

.. code-block:: python

    from ola_pilot import controller, Fixture, ola_client
    from ola_pilot.trait import RGB

    class ToyFixture(Fixture):
        wash = RGB()

    tf = ToyFixture()
    controller = Controller()
    controller.add_fixture(tf, univ=0, base=50)
    controller.add_output(ola_client(host='localhost:8000'))

This will connect to ola, fetch the list of universes, and any universes that intersect with what has been patched will be written to. For more advanced use cases, you can add a second `ola_client` handling other universes, and the ola instance can be running on the local machine or over a network.

Patching list
-------------
To create a patching list, do this:

.. code-block:: console

    $ ola_pilot patch demo.py
    fixture             univ  base  channels  mode
    ToyFixture-0        0     50    3         -

We can also get a per-channel view:

.. code-block:: console

    $ ola_pilot channels demo.py
    fixture             univ  addr  channel  mode
    ToyFixture-0        0     50    0        wash.red
    ToyFixture-0        0     51    1        wash.green
    ToyFixture-0        0     52    2        wash.blue

You might have some questions about the `ToyFixture` above.

* how did it know to take 3 channels, and in what order
* and what is the `RGB` object?

The default `Fixture` base class constructor iterates the dictionary-view of the `Class` looking for standard Traits (PTPos, RGB, Intensity, IndexedValue) and duplicates them as fields on the instance. It then iterates the traits in order, and queries their channels, asuming no gaps between then. Since an `RGB` Trait has three channels, they get allocated sequentially.

.. code-block:: console

    >>> tf = ToyFixture()
    >>> tf.get_channel_count()
    3
    >>> tf.get_traits()
    [wash]
    >>> tf.get_channels()
    [wash.red, wash.green, wash.blue]

Controlling a Moving Head
-------------------------

Another example `demo2.py`, using multiple Traits:

.. code-block:: python

    class ToyMovingHead(Fixture):
        pos = PTPos(order='PPTT')
        wash = RGBW(order='WRGB')
        intentity = Intensity()

    controller.add_fixture(0, 5, ToyMovingHead())

.. code-block:: console

    $ ola_pilot patch demo2.py
    fixture             univ  base  channels  mode
    ToyMovingHead-0     0     50    3         -

    $ ola_pilot channels demo2.py
    fixture             univ  addr  channel  mode
    ToyMovingHead-0     0     5     0        pos.pan
    ToyMovingHead-0     0     6     1        pos.pan_fine
    ToyMovingHead-0     0     7     2        pos.tilt
    ToyMovingHead-0     0     8     3        pos.tilt_fine
    ToyMovingHead-0     0     9     4        wash.white
    ToyMovingHead-0     0     10    5        wash.red
    ToyMovingHead-0     0     11    6        wash.green
    ToyMovingHead-0     0     12    7        wash.blue
    ToyMovingHead-0     0     13    8        intensity.value


Controlling Multiple Fixtures
-----------------------------

We now want to patch a second RGB LED, and drive a signal to it from a MIDI controller

.. code-block:: python

    controller.patch_fixture(0, 5, tf1 := ToyFixture())
    controller.patch_fixture(0, 10, tf2 := ToyFixture())
    controller.add_efx(h := HueToRGB())
    h.rgb.bind(tf1.wash)
    h.rgb.bind(tf2.wash)
    h.hue.set(0.5)
    h.intensity.set(0.5)

    >>> print(controller.get_universe(0))
    00 00 00 00 cc dd 00 00 00 00 00 00 00 00 00 00 00 00 ...

    >>> print(tf1.wash.drivers)
    [out(HueToRGB-0.rgb)]

    >>> print(h.rgb.targets)
    [in(ToyMovingHead-0.wash), in(ToyMovingHead-1.wash)]

    midi.search_device('MK3')
    midi.bind_cc(83, h.hue)
    midi.bind_cc(84, h.intensity)

Connectable objects (fixtures, fx) need to be registered with a controller before they bind to other ports, otherwise there will be no unique naming available for the connection.

.. code-block:: python

    >>> h = HueToRGB()
    >>> tf = ToyFixture()
    >>> h.rgb.bind(tf.wash)
    ValueError("source is not named, add to a controller")
    >>> controller.add_efx(h)
    >>> h.rgb.bind(tf.wash)
    ValueError("dest is not named, add to a controller")
    >>> controller.add_fixture(tf)
    >>> h.rgb.bind(tf.wash)
    >>> print(controller.bindings())
    ['HueToRGB-0.rgb->ToyFixture-0.wash']


Multiple drivers
----------------

If we connect two drivers to an input, we need to decide which value wins:

.. code-block:: python

    controller.patch_fixture(0, 5, tf1 := ToyFixture())
    controller.patch_efx(h := HueToRGB())
    controller.patch_efx(h2 := HueToRGB())
    h1.rgb.bind(tf1.wash)
    h2.rgb.bind(tf1.wash)
    h1.hue.set(0.5)
    h1.intensity.set(0.5)
    h2.hue.set(0.1)
    h2.intensity.set(0.3)

Here should the lights be a hue of 0.1 purple or 0.5 red? There are several common stratagies:

* HTP highest-takes-precidence
* LTP last-takes-precidence
* PTP priority-takes-precidence

Highest takes precidence is a historical hang-over, and it not well defined for RGB colour space (which is higher, #FF0000 or #00FF00 ?). How can a blinder FX cause a flashing effect if it cannot drive the lights dimmer than existing driver?

Last takes precidence is quite common on boards where a manual fader/slider has been moved, by setting the priority from a global counter that is increased when any dial is changed. This allows e.g. two faders for the same channel, and you can raise the level up with one fader, then when you move the second, it immediately snaps to the most recent value.

Explitic priority (PTP) requires each driver to the output to have a strength, for instance a flasher effect driven by midi
might have an output with priority 0 when the note is not played, and a priority of 200 when held, so that it can override
any other effect driving the fixture. I have taken this approach - every driver has a priority for it's outputs, the priority
is potentially dynamic or set within the scene/preset, and an input with multiple drivers is controlled exclusively by the highest priority.

All inputs including every trait of every fixture, can have a default value saved in the global preset.

.. code-block:: python

    controller.patch_fixture(0, 5, tf1 := ToyFixture())
    controller.patch_fixture(0, 10, tf2 := ToyFixture())
    controller.patch_efx(h := HueToRGB())
    controller.patch_efx(fl := Flasher())

    h.rgb.bind(tf1.wash)
    h.rgb.bind(tf2.wash)
    h.hue.set(0.5)
    h.intensity.set(0.5)

    fl.rgb.bind(tf1.wash)
    fl.rgb.bind(tf2.wash)

    midi = RTMIDI()
    midi.search_device('MK3')
    midi.bind_cc(83, h.hue)
    midi.bind_cc(84, h.intensity)
    midi.bind_cc(85, fl.speed)
    midi.bind_note(63, fl.trigger)


We can ask an output for the list of it's drivers:

.. code-block:: python

   >>> tf1.wash.drivers()
   [
     [ToyFixture-0  wash] <- [rgb  HueToRGB-0  hue] <- 0.5,
     [ToyFixture-0  wash] <- [rgb  HueToRGB-0  intensity] <- 0.5
     [ToyFixture-0  wash] <- [rgb  HueToRGB-0  hue] <- [cc83  RTMIDI]
     [ToyFixture-0  wash] <- [rgb  HueToRGB-0  intensity] <- [cc84  RTMIDI]
     [ToyFixture-0  wash] <- [rgb  Flasher-0  speed] <- [cc85  RTMIDI]
     [ToyFixture-0  wash] <- [rgb  Flasher-0  trigger] <- [note63  RTMIDI]
   ]

This tracing is possible because `Trait.bind(other)` records both sides of the binding, and *within* an EFX implementation, we use `Trait.drives(other)` to record the dependancy, even though it is calculated by code.


Webserver
---------

This will start up the basic http server for web browser control:

.. code-block:: console

    $ ola_pilot web demo.py
