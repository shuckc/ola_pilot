ola_pilot
---

A simple desk supporting fixtures using ola to handle DMX hardware.
Communicated by TCP to ola's RPC port (localhost:9010) using asyncio.


Running
----

    $ olad -l 3

Use OLA admin http://localhost:9090/ola.html to attach a universe to a dongle or 'Dummy Device', then

    $ python -m venv venv
    $ . venv/bin/activate
    $ pip install -r requirements.txt
    $ python desk.py


Further Information
-----

* OLA RPC System https://docs.openlighting.org/ola/doc/latest/rpc_system.html
* blocking python API https://www.openlighting.org/ola/developer-documentation/python-api/
* Open Fixture Library https://github.com/OpenLightingProject/open-fixture-library

