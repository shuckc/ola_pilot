from events import Observable, ObservableDict
from test_controller import ChangeCounter

def test_observable():

    class Obs(Observable["Obs"]):
        pass

    o = Obs()
    ref = ChangeCounter()
    def p(src):
        ref.changed()

    o.sub(p)
    o.notify(None)
    assert ref.changes == 1

    o.unsub(p)
    o.notify(None)
    assert ref.changes == 1

    o.sub(p)
    o.notify(None)
    assert ref.changes == 2

def test_observable_dict():
    ref = ChangeCounter()

    s = ObservableDict()
    s.added.sub(ref.changed)
    s.removed.sub(ref.changed)
    s.changed.sub(ref.changed)
    assert ref.changes == 0

    s['xyx'] = True
    assert ref.changes == 1

    assert len(s) == 1
    s['xyx'] = False
    assert ref.changes == 2

    del s['xyx']
    assert len(s) == 0
    assert ref.changes == 3

