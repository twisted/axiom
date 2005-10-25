
__metaclass__ = type

from twisted.python import log
from twisted.internet import reactor

from twisted.application.service import Service

class UpgradeService(Service):

    delay = 0.02

    def __init__(self):
        # Service.__init__(self)
        self.tasks = []
        self.currentTask = 0
        self.delayed = None

    def addTask(self, task):
        """add a task to be performed

        @param task: 0-arg callable that returns True if it wants to be called
        again, False otherwise.
        """
        if not self.tasks:
            self.reschedule()
        self.tasks.append(task)

    def work(self):
        """Do some work.

        Run one task.  Reschedule if there are more tasks to perform.
        """
        self.delayed = None
        task = self.tasks[self.currentTask]
        try:
            keepGoing = task()
        except:
            log.err()
            keepGoing = False

        if keepGoing:
            self.currentTask += 1
        else:
            self.tasks.pop(self.currentTask)
        if self.tasks:
            self.currentTask %= len(self.tasks)
            self.reschedule()
        else:
            self.currentTask = 0

    def stopService(self):
        Service.stopService(self)
        if self.delayed is not None:
            self.delayed.cancel()
            self.delayed = None

    def startService(self):
        Service.startService(self)
        if self.pending:
            self.pending = False
            self.reschedule()

    def reschedule(self):
        """
        Activate a callLater.
        """
        if self.running:
            assert self.delayed is None
            self.delayed = reactor.callLater(self.delay, self.work)
        else:
            self.pending = True

    def privilegedStartService(self):
        pass

    pending = False


