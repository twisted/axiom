# -*- test-case-name: axiom.test.test_batch -*-

"""
Utilities for performing repetitive tasks over potentially large sets
of data over an extended period of time.
"""

import weakref, datetime, os, sys

from zope.interface import implements

from twisted.python import reflect, failure, log, procutils, util
from twisted.application import service
from twisted.internet import task, defer, reactor, error, protocol

from epsilon import extime, process, cooperator, modal

from vertex import juice

from axiom import iaxiom, item, attributes

VERBOSE = False

_processors = weakref.WeakValueDictionary()


class _NoWorkUnits(Exception):
    """
    Raised by a _ReliableListener's step() method to indicate it
    didn't do anything.
    """


class _ProcessingFailure(Exception):
    """
    Raised when processItem raises any exception.
    """
    def __init__(self, reliableListener, workUnit, failure):
        Exception.__init__(self)
        self.reliableListener = reliableListener
        self.workUnit = workUnit
        self.failure = failure



class _ForwardProcessingFailure(_ProcessingFailure):
    pass



class _BackwardProcessingFailure(_ProcessingFailure):
    pass



class BatchProcessingError(item.Item):
    processor = attributes.reference(doc="""
    The batch processor which owns this failure.
    """)

    listener = attributes.reference(doc="""
    The listener which caused this error.
    """)

    item = attributes.reference(doc="""
    The item which actually failed to be processed.
    """)

    error = attributes.bytes(doc="""
    The error message which was associated with this failure.
    """)



class _ReliableListener(item.Item):
    processor = attributes.reference(doc="""
    The batch processor which owns this listener.
    """)

    listener = attributes.reference(doc="""
    The item which is actually the listener.
    """)

    backwardMark = attributes.integer(doc="""
    Store ID of the first Item after the next Item to be processed in
    the backwards direction.  Usually, the Store ID of the Item
    previously processed in the backwards direction.
    """)

    forwardMark = attributes.integer(doc="""
    Store ID of the first Item before the next Item to be processed in
    the forwards direction.  Usually, the Store ID of the Item
    previously processed in the forwards direction.
    """)

    lastRun = attributes.timestamp(doc="""
    Time indicating the last chance given to this listener to do some
    work.
    """)

    style = attributes.integer(doc="""
    Either L{iaxiom.LOCAL} or L{iaxiom.REMOTE}. Indicates where the
    batch processing should occur, in the main process or a
    subprocess.
    """)

    def __repr__(self):
        return '<ReliableListener %s %r #%r>' % ({iaxiom.REMOTE: 'remote',
                                                  iaxiom.LOCAL: 'local'}[self.style],
                                                 self.listener,
                                                 self.storeID)


    def _forwardWork(self, workUnitType):
        if VERBOSE:
            log.msg("%r looking forward from %r" % (self, self.forwardMark,))
        return self.store.query(
            workUnitType,
            workUnitType.storeID > self.forwardMark,
            sort=workUnitType.storeID.ascending,
            limit=2)


    def _backwardWork(self, workUnitType):
        if VERBOSE:
            log.msg("%r looking backward from %r" % (self, self.backwardMark,))
        if self.backwardMark == 0:
            return []
        return self.store.query(
            workUnitType,
            workUnitType.storeID < self.backwardMark,
            sort=workUnitType.storeID.descending,
            limit=2)


    def _doOneWork(self, workUnit, failureType):
        if VERBOSE:
            log.msg("Processing a unit of work: %r" % (workUnit,))
        try:
            self.listener.processItem(workUnit)
        except:
            f = failure.Failure()
            if VERBOSE:
                log.msg("Processing failed: %s" % (f.getErrorMessage(),))
            raise failureType(self, workUnit, f)


    def step(self):
        first = True
        for workUnit in self._forwardWork(self.processor.workUnitType):
            if first:
                first = False
            else:
                return True
            self.forwardMark = workUnit.storeID
            self._doOneWork(workUnit, _ForwardProcessingFailure)
        for workUnit in self._backwardWork(self.processor.workUnitType):
            if first:
                first = False
            else:
                return True
            self.backwardMark = workUnit.storeID
            self._doOneWork(workUnit, _BackwardProcessingFailure)
        if first:
            raise _NoWorkUnits()
        if VERBOSE:
            log.msg("%r.step() returning False" % (self,))
        return False



class _BatchProcessorMixin:
    def step(self, style=iaxiom.LOCAL, skip=()):
        now = extime.Time()
        first = True

        for listener in self.store.query(_ReliableListener,
                                         attributes.AND(_ReliableListener.processor == self,
                                                        _ReliableListener.style == style,
                                                        _ReliableListener.listener.notOneOf(skip)),
                                         sort=_ReliableListener.lastRun.ascending):
            if not first:
                if VERBOSE:
                    log.msg("Found more work to do, returning True from %r.step()" % (self,))
                return True
            listener.lastRun = now
            try:
                if listener.step():
                    if VERBOSE:
                        log.msg("%r.step() reported more work to do, returning True from %r.step()" % (listener, self))
                    return True
            except _NoWorkUnits:
                if VERBOSE:
                    log.msg("%r.step() reported no work units" % (listener,))
            else:
                first = False
        if VERBOSE:
            log.msg("No listeners left with work, returning False from %r.step()" % (self,))
        return False


    def run(self):
        now = extime.Time()
        if self.step():
            return now + datetime.timedelta(milliseconds=self.busyInterval)
        return now + datetime.timedelta(milliseconds=self.idleInterval)


    def timedEventErrorHandler(self, timedEvent, failureObj):
        failureObj.trap(_ProcessingFailure)
        workUnit = failureObj.value.workUnit
        listener = failureObj.value.reliableListener
        processingFailure = failureObj.value.failure

        log.msg("Batch processing failure")
        log.err(processingFailure)
        BatchProcessingError(
            store=self.store,
            processor=listener.processor,
            listener=listener.listener,
            item=workUnit,
            error=processingFailure.getErrorMessage())

        if failureObj.check(_ForwardProcessingFailure):
            listener.forwardMark = workUnit.storeID
        elif failureObj.check(_BackwardProcessingFailure):
            listener.backwardMark = workUnit.storeID

        return extime.Time() + datetime.timedelta(milliseconds=self.busyInterval)


    def addReliableListener(self, listener, style=iaxiom.LOCAL):
        """
        Add the given Item to the set which will be notified of Items
        available for processing.

        Note: Each Item is processed synchronously.  Adding too many
        listeners to a single batch processor will cause the L{step}
        method to block while it sends notification to each listener.

        @param listener: An Item instance which provides a
        C{processItem} method.
        """
        if self.store.findUnique(_ReliableListener,
                                 attributes.AND(_ReliableListener.processor == self,
                                                _ReliableListener.listener == listener),
                                 default=None) is not None:
            return

        for work in self.store.query(self.workUnitType,
                                     sort=self.workUnitType.storeID.descending,
                                     limit=1):
            forwardMark = work.storeID
            backwardMark = work.storeID + 1
            break
        else:
            forwardMark = 0
            backwardMark = 0

        _ReliableListener(store=self.store,
                          processor=self,
                          listener=listener,
                          forwardMark=forwardMark,
                          backwardMark=backwardMark,
                          style=style)


    def removeReliableListener(self, listener):
        """
        Remove a previously added listener.
        """
        self.store.query(_ReliableListener,
                         attributes.AND(_ReliableListener.processor == self,
                                        _ReliableListener.listener == listener)).deleteFromStore()
        self.store.query(BatchProcessingError,
                         attributes.AND(BatchProcessingError.processor == self,
                                        BatchProcessingError.listener == listener)).deleteFromStore()


    def getReliableListeners(self):
        """
        Return an iterable of the listeners which have been added to
        this batch processor.
        """
        for rellist in self.store.query(_ReliableListener, _ReliableListener.processor == self):
            yield rellist.listener


    def getFailedItems(self):
        """
        Return an iterable of two-tuples of listeners which raised an
        exception from C{processItem} and the item which was passed as
        the argument to that method.
        """
        for failed in self.store.query(BatchProcessingError, BatchProcessingError.processor == self):
            yield (failed.listener, failed.item)



def processor(forType):
    """
    Create an Axiom Item type which is suitable to use as a batch
    processor for the given Axiom Item type.

    @type forType: L{item.MetaItem}
    @param forType: The Axiom Item type for which to create a batch
    processor type.

    @rtype: L{item.MetaItem}
    @return: An Axiom Item type suitable for use as a batch processor.
    If such a type previously existed, it will be returned.
    Otherwise, a new type is created.
    """
    MILLI = 1000
    if forType not in _processors:
        def __init__(self, *a, **kw):
            item.Item.__init__(self, *a, **kw)
            self.store.powerUp(self, iaxiom.IBatchProcessor)

        attrs = {
            '__name__': 'Batch_' + forType.__name__,

            '__module__': forType.__module__,

            '__init__': __init__,

            '__repr__': lambda self: '<Batch of %s #%d>' % (reflect.qual(self.workUnitType), self.storeID),

            'workUnitType': forType,

            # MAGIC NUMBERS AREN'T THEY WONDERFUL?
            'rate': attributes.integer(doc="", default=10),
            'idleInterval': attributes.integer(doc="", default=60 * MILLI),
            'busyInterval': attributes.integer(doc="", default=MILLI / 10),
            }
        _processors[forType] = item.MetaItem(
            attrs['__name__'],
            (item.Item, _BatchProcessorMixin),
            attrs)
    return _processors[forType]



class ProcessUnavailable(Exception):
    """Indicates the process is not available to perform tasks.

    This is a transient error.  Calling code should handle it by
    arranging to do the work they planned on doing at a later time.
    """



class Shutdown(juice.Command):
    """
    Abandon, belay, cancel, cease, close, conclude, cut it out, desist,
    determine, discontinue, drop it, end, finish, finish up, give over, go
    amiss, go astray, go wrong, halt, have done with, hold, knock it off, lay
    off, leave off, miscarry, perorate, quit, refrain, relinquish, renounce,
    resolve, scrap, scratch, scrub, stay, stop, terminate, wind up.
    """
    commandName = "Shutdown"
    responseType = juice.QuitBox


def _childProcTerminated(self, err):
    self.mode = 'stopped'
    err = ProcessUnavailable(err)
    for d in self.waitingForProcess:
        d.errback(err)
    del self.waitingForProcess


class ProcessController(object):
    """Stateful class which tracks a Juice connection to a child process.

    Communication occurs over stdin and stdout of the child process.  The
    process is launched and restarted as necessary.  Failures due to the child
    process terminating, either unilaterally of by request, are represented as
    a transient exception class,

    Mode is one of
      'stopped'       (no process running or starting)
      'starting'      (process begun but not ready for requests)
      'ready'         (process ready for requests)
      'stopping'      (process being torn down)
      'waiting_ready' (process beginning but will be shut down
                          as soon as it starts up)

    Transitions are as follows

       getProcess:
           stopped -> starting:
               launch process
               create/save in waitingForStartup/return Deferred
           starting -> starting:
               create/save/return Deferred
           ready -> ready:
                return saved process
           stopping:
                return failing Deferred indicating transient failure
           waiting_ready:
                return failing Deferred indicating transient failure

       stopProcess:
           stopped -> stopped:
               return succeeding Deferred
           starting -> waiting_ready:
               create Deferred, add transient failure errback handler, return
           ready -> stopping:
               call shutdown on process
               return Deferred which fires when shutdown is done

       childProcessCreated:
           starting -> ready:
               callback saved Deferreds
               clear saved Deferreds
           waiting_ready:
               errback saved Deferred indicating transient failure
               return _shutdownIndexerProcess()

       childProcessTerminated:
           starting -> stopped:
               errback saved Deferreds indicating transient failure
           waiting_ready -> stopped:
               errback saved Deferreds indicating transient failure
           ready -> stopped:
               drop reference to process object
           stopping -> stopped:
               Callback saved shutdown deferred

    @ivar process: A reference to the process object.  Set in every non-stopped
    mode.

    @ivar juice: A reference to the juice protocol.  Set in all modes.

    @ivar connector: A reference to the process protocol.  Set in every
    non-stopped mode.

    @ivar onProcessStartup: None or a no-argument callable which will
    be invoked whenever the connection is first established to a newly
    spawned child process.

    @ivar onProcessTermination: None or a no-argument callable which
    will be invoked whenever a Juice connection is lost, except in the
    case where process shutdown was explicitly requested via
    stopProcess().
    """

    __metaclass__ = modal.ModalType

    initialMode = 'stopped'
    modeAttribute = 'mode'

    # A reference to the Twisted process object which corresponds to
    # the child process we have spawned.  Set to a non-None value in
    # every state except stopped.
    process = None

    # A reference to the process protocol object via which we
    # communicate with the process's stdin and stdout.  Set to a
    # non-None value in every state except stopped.
    connector = None

    def __init__(self, name, juice, tacPath, onProcessStartup=None, onProcessTermination=None):
        self.name = name
        self.juice = juice
        self.tacPath = tacPath
        self.onProcessStartup = onProcessStartup
        self.onProcessTermination = onProcessTermination

    def _startProcess(self):
        executable = sys.executable
        env = os.environ
        env['PYTHONPATH'] = os.pathsep.join(sys.path)

        twistdBinaries = procutils.which("twistd2.4") + procutils.which("twistd")
        if not twistdBinaries:
            return defer.fail(RuntimeError("Couldn't find twistd to start subprocess"))
        twistd = twistdBinaries[0]

        setsid = procutils.which("setsid")

        self.connector = JuiceConnector(self.juice, self)

        args = (
            sys.executable,
            twistd,
            '--logfile=%s.log' % (self.name,),
            '--pidfile=%s.pid' % (self.name,),
            '-noy',
            self.tacPath)

        if setsid:
            args = ('setsid',) + args
            executable = setsid[0]

        self.process = process.spawnProcess(
            self.connector, executable, args, env=env)

    class stopped(modal.mode):
        def getProcess(self):
            self.mode = 'starting'
            self.waitingForProcess = []

            self._startProcess()

            # Mode has changed, this will call some other
            # implementation of getProcess.
            return self.getProcess()

        def stopProcess(self):
            return defer.succeed(None)

    class starting(modal.mode):
        def getProcess(self):
            d = defer.Deferred()
            self.waitingForProcess.append(d)
            return d

        def stopProcess(self):
            def eb(err):
                err.trap(ProcessUnavailable)

            d = defer.Deferred().addErrback(eb)
            self.waitingForProcess.append(d)

            self.mode = 'waiting_ready'
            return d

        def childProcessCreated(self):
            self.mode = 'ready'

            if self.onProcessStartup is not None:
                self.onProcessStartup()

            for d in self.waitingForProcess:
                d.callback(self.juice)
            del self.waitingForProcess

        def childProcessTerminated(self, reason):
            _childProcTerminated(self, reason)
            if self.onProcessTermination is not None:
                self.onProcessTermination()


    class ready(modal.mode):
        def getProcess(self):
            return defer.succeed(self.juice)

        def stopProcess(self):
            self.mode = 'stopping'
            self.onShutdown = defer.Deferred()
            Shutdown().do(self.juice)
            return self.onShutdown

        def childProcessTerminated(self, reason):
            self.mode = 'stopped'
            self.process = self.connector = None


    class stopping(modal.mode):
        def getProcess(self):
            return defer.fail(ProcessUnavailable("Shutting down"))

        def stopProcess(self):
            return self.onShutdown

        def childProcessTerminated(self, reason):
            self.mode = 'stopped'
            self.process = self.connector = None
            self.onShutdown.callback(None)


    class waiting_ready(modal.mode):
        def getProcess(self):
            return defer.fail(ProcessUnavailable("Shutting down"))

        def childProcessCreated(self):
            # This will put us into the stopped state - no big deal,
            # we are going into the ready state as soon as it returns.
            _childProcTerminated(self, RuntimeError("Shutting down"))

            # Dip into the ready mode for ever so brief an instant so
            # that we can shut ourselves down.
            self.mode = 'ready'
            return self.stopProcess()

        childProcessTerminated = _childProcTerminated



class JuiceConnector(protocol.ProcessProtocol):

    def __init__(self, proto, controller):
        self.juice = proto
        self.controller = controller

    def connectionMade(self):
        log.msg("Subprocess started.")
        self.juice.makeConnection(self)
        self.controller.childProcessCreated()

    # Transport
    disconnecting = False

    def write(self, data):
        self.transport.write(data)

    def writeSequence(self, data):
        self.transport.writeSequence(data)

    def loseConnection(self):
        self.transport.loseConnection()

    def getPeer(self):
        return ('omfg what are you talking about',)

    def getHost(self):
        return ('seriously it is a process this makes no sense',)

    def inConnectionLost(self):
        log.msg("Standard in closed")
        protocol.ProcessProtocol.inConnectionLost(self)

    def outConnectionLost(self):
        log.msg("Standard out closed")
        protocol.ProcessProtocol.outConnectionLost(self)

    def errConnectionLost(self):
        log.msg("Standard err closed")
        protocol.ProcessProtocol.errConnectionLost(self)

    def outReceived(self, data):
        self.juice.dataReceived(data)

    def errReceived(self, data):
        log.msg("Received stderr from subprocess: " + repr(data))

    def processEnded(self, status):
        log.msg("Process ended")
        self.juice.connectionLost(status)
        self.controller.childProcessTerminated(status)



class JuiceChild(juice.Juice):
    """
    Protocol class which runs in the child process

    This just defines one behavior on top of a regular juice protocol: the
    shutdown command, which drops the connection and stops the reactor.
    """
    shutdown = False

    def connectionLost(self, reason):
        juice.Juice.connectionLost(self, reason)
        if self.shutdown:
            reactor.stop()

    def command_SHUTDOWN(self):
        log.msg("Shutdown message received, goodbye.")
        self.shutdown = True
        return {}
    command_SHUTDOWN.command = Shutdown



class SetStore(juice.Command):
    """
    Specify the location of the site store.
    """
    commandName = 'Set-Store'
    arguments = [('storepath', juice.Path())]



class SuspendProcessor(juice.Command):
    """
    Prevent a particular reliable listener from receiving any notifications
    until a L{ResumeProcessor} command is sent or the batch process is
    restarted.
    """
    commandName = 'Suspend-Processor'
    arguments = [('storepath', juice.Path()),
                 ('storeid', juice.Integer())]



class ResumeProcessor(juice.Command):
    """
    Cause a particular reliable listener to begin receiving notifications
    again.
    """
    commandName = 'Resume-Processor'
    arguments = [('storepath', juice.Path()),
                 ('storeid', juice.Integer())]



class BatchProcessingControllerService(service.Service):
    """
    Controls starting, stopping, and passing messages to the system process in
    charge of remote batch processing.
    """

    def __init__(self, store):
        self.store = store
        self.setName("Batch Processing Controller")


    def startService(self):
        service.Service.startService(self)
        tacPath = util.sibpath(__file__, "batch.tac")
        proto = BatchProcessingProtocol()
        self.batchController = ProcessController(
            "batch", proto, tacPath,
            self._setStore, self._restartProcess)
        return self.batchController.getProcess()


    def _setStore(self):
        return SetStore(storepath=self.store.dbdir).do(self.batchController.juice)


    def _restartProcess(self):
        self.batchController.getProcess()


    def stopService(self):
        service.Service.stopService(self)
        d = self.batchController.stopProcess()
        d.addErrback(lambda err: err.trap(error.ProcessDone))
        return d


    def suspend(self, storepath, storeID):
        return self.batchController.getProcess().addCallback(
            SuspendProcessor(storepath=storepath, storeid=storeID).do)


    def resume(self, storepath, storeID):
        return self.batchController.getProcess().addCallback(
            ResumeProcessor(storepath=storepath, storeid=storeID).do)



class _SubStoreBatchChannel(object):
    """
    SubStore adapter for passing messages to the batch processing system
    process.

    SubStores are adaptable to L{iaxiom.IBatchService} via this adapter.
    """
    implements(iaxiom.IBatchService)

    def __init__(self, substore):
        self.storepath = substore.dbdir
        self.service = iaxiom.IBatchService(substore.parent)


    def suspend(self, storeID):
        return self.service.suspend(self.storepath, storeID)


    def resume(self, storeID):
        return self.service.resume(self.storepath, storeID)



def storeBatchServiceSpecialCase(st, pups):
    if st.parent is not None:
        return _SubStoreBatchChannel(st)
    return service.IService(st).getServiceNamed("Batch Processing Controller")



class BatchProcessingProtocol(JuiceChild):
    siteStore = None

    def __init__(self, service=None):
        juice.Juice.__init__(self, False)
        self.storepaths = []
        self.service = service
        if service is not None:
            self.service.cooperator = cooperator.Cooperator()


    def command_SET_STORE(self, storepath):
        from axiom import store

        assert self.siteStore is None

        self.siteStore = store.Store(storepath, debug=False)
        self.subStores = {}
        self.pollCall = task.LoopingCall(self._pollSubStores)
        self.pollCall.start(10.0)
        return {}
    command_SET_STORE.command = SetStore


    def command_SUSPEND_PROCESSOR(self, storepath, storeid):
        return self.subStores[storepath.path].suspend(storeid).addCallback(lambda ign: {})
    command_SUSPEND_PROCESSOR.command = SuspendProcessor


    def command_RESUME_PROCESSOR(self, storepath, storeid):
        return self.subStores[storepath.path].resume(storeid).addCallback(lambda ign: {})
    command_RESUME_PROCESSOR.command = ResumeProcessor


    def _pollSubStores(self):
        from axiom import store, substore
        paths = set([p.path for p in self.siteStore.query(substore.SubStore).getColumn("storepath")])
        for removed in set(self.subStores) - paths:
            self.subStores[removed].disownServiceParent()
            del self.subStores[removed]
            if VERBOSE:
                log.msg("Removed SubStore " + removed)
        for added in paths - set(self.subStores):
            self.subStores[added] = BatchProcessingService(store.Store(added, debug=False), style=iaxiom.REMOTE)
            self.subStores[added].setServiceParent(self.service)
            if VERBOSE:
                log.msg("Added SubStore " + added)



class BatchProcessingService(service.Service):
    """
    Steps over the L{iaxiom.IBatchProcessor} powerups for a single L{axiom.store.Store}.
    """
    def __init__(self, store, style=iaxiom.LOCAL):
        self.store = store
        self.style = style
        self.suspended = []


    def suspend(self, storeID):
        item = self.store.getItemByID(storeID)
        self.suspended.append(item)
        return item.suspend()


    def resume(self, storeID):
        item = self.store.getItemByID(storeID)
        self.suspended.remove(item)
        return item.resume()


    def deferLater(self, n):
        d = defer.Deferred()
        reactor.callLater(n, d.callback, None)
        return d


    def items(self):
        return self.store.powerupsFor(iaxiom.IBatchProcessor)


    def step(self):
        while self.running:
            items = list(self.items())

            if VERBOSE:
                log.msg("Found %d processors for %s" % (len(items), self.store))

            more = False
            while items and self.running:
                item = items.pop()
                if VERBOSE:
                    log.msg("Stepping processor %r (suspended is %r)" % (item, self.suspended))
                more = more or item.store.transact(item.step, style=self.style, skip=self.suspended)
                yield None
            yield self.deferLater([10.0, 0.1][more])


    def ensafen(self, iterator, onError):
        """
        Create an iterator which yields the same elements C{iterator} would
        have produced, but catch any exceptions it raises (except for
        C{StopIteration}) and invoke C{onError} to handle them.
        """
        while True:
            try:
                yield iterator.next()
            except StopIteration:
                break
            except:
                f = failure.Failure()
                onError(f)


    def _desist(self, err):
        log.msg("Batch processor for %r encountered an error" % (self.store,))
        log.err(err)
        self.disownServiceParent()
        raise StopIteration


    def startService(self):
        service.Service.startService(self)
        self.parent.cooperator.coiterate(self.ensafen(self.step(), self._desist))


    def stopService(self):
        service.Service.stopService(self)
        self.store.close()
