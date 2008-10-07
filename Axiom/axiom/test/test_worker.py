# Copyright (c) 2008 Divmod.  See LICENSE for details.
"""
Tests for L{axiom.worker}.
"""

from twisted.trial import unittest
from twisted.internet.defer import Deferred

from axiom.item import Item
from axiom.store import Store
from axiom.attributes import integer, inmemory
from axiom.worker import Worker, QueuedEvent


class TestJob(Item):
    """
    Example item for scheduling.
    """
    timesRun = integer(default=0, doc="""
                                      Number of times this item's run method was
                                      called.
                                      """)

    callback = inmemory(doc="""
                            A callable to be run when this item is
                            executed.
                            """)
    def run(self):
        self.timesRun += 1
        self.callback(self)


class WorkerTest(unittest.TestCase):
    """

    """

    def test_queueJob(self):
        """
        Enqueueing an item in the site store creates a QueuedEvent describing
        its position in the queue.
        """
        s = Store()
        w = Worker(store=s)
        self.assertEqual(w.nowServing, 0)
        self.assertEqual(w.nextTicket, 0)
        t = TestJob(store=s, callback=None)
        w.enqueue(t)
        self.assertEqual(w.nextTicket, 1)
        q = s.findUnique(QueuedEvent)
        self.assertEqual(q.runnable, t)
        self.assertEqual(q.ticket, 0)


    def test_runQueuedJob(self):
        """
        Enqueueing an item results in its 'run' method being called.
        """
        d = Deferred()
        s = Store()
        w = Worker(store=s)
        t = TestJob(store=s, callback=d.callback)
        w.enqueue(t)
        self.assertEqual(t.timesRun, 0)
        w.start()
        return d
