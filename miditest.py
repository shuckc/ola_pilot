import logging
import sys

from rtmidi.midiutil import open_midiinput

from desk import MidiCC

log = logging.getLogger("midiin_poll")
logging.basicConfig(level=logging.DEBUG)

port = sys.argv[1] if len(sys.argv) > 1 else None


try:
    midiin, port_name = open_midiinput(port)
except (EOFError, KeyboardInterrupt):
    sys.exit()

# import mido

# instrument = mido.get_input_names()
print(port_name)

banks = MidiCC(midiin)

while True:
    banks.tick(0)
