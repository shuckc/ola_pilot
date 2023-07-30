ola_pilot
---

A simple desk supporting fixtures using [ola](https://www.openlighting.org/ola/) to handle DMX hardware.
All output is via. TCP to ola's RPC port (localhost:9010) using protobufs and asyncio.

Whilst I like QLC+, I was motivated by finding it very difficult to achieve certain things - like map a MIDI CC to a hue, and drive this to fixtures of multiple types (RGB, RGBA, RGBW) together. With moving heads it was difficult to shape the parameters of animation on the fly.

Optional CLI using [textual](https://github.com/Textualize/textual).

Midi support uses [rtmidi](https://github.com/SpotlightKid/python-rtmidi).

Running
----

    $ olad -l 3

Use OLA admin http://localhost:9090/ola.html to attach a universe to a dongle or 'Dummy Device', then

    $ python -m venv venv
    $ . venv/bin/activate
    $ pip install -r requirements.txt
    $ python pilot.py


Further Information
-----

* OLA RPC System https://docs.openlighting.org/ola/doc/latest/rpc_system.html
* blocking python API https://www.openlighting.org/ola/developer-documentation/python-api/
* Open Fixture Library https://github.com/OpenLightingProject/open-fixture-library

TODO
---
* sound to light with https://github.com/aubio/aubio/blob/master/python/README.md
* colour conversion with https://blog.saikoled.com/post/44677718712/how-to-convert-from-hsi-to-rgb-white

