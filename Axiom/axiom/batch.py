# -*- test-case-name: axiom.test.test_batch -*-

"""
Utilities for performing repetitive tasks over potentially large sets
of data over an extended period of time.
"""

import weakref, datetime

from zope.interface import implements

from twisted.python import reflect, failure, log, util
from twisted.application import service
from twisted.internet import task, defer, reactor, error

from epsilon import extime, process, cooperator

from vertex import juice

from axiom import iaxiom, item, attributes

VERBOSE = True

_processors = weakref.WeakValueDictionary()


class _NoWorkUnits(Exception):
    """
    Raised by a _ReliableListener's step() method to indicate it
    didn't do anything.
    """


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
        return self.store.query(
            workUnitType,
            workUnitType.storeID < self.backwardMark,
            sort=workUnitType.storeID.descending,
            limit=2)


    def _doOneWork(self, workUnit):
        if VERBOSE:
            log.msg("Processing a unit of work: %r" % (workUnit,))
        try:
            self.store.transact(self.listener.processItem, workUnit)
        except:
            f = failure.Failure()
            log.msg("Batch processing failure")
            log.err(f)
            BatchProcessingError(
                store=self.store,
                processor=self.processor,
                listener=self.listener,
                item=workUnit,
                error=f.getErrorMessage())


    def step(self):
        first = True
        for workUnit in self._forwardWork(self.processor.workUnitType):
            if first:
                first = False
            else:
                return True
            self.forwardMark = workUnit.storeID
            self._doOneWork(workUnit)
        for workUnit in self._backwardWork(self.processor.workUnitType):
            if first:
                first = False
            else:
                return True
            self.backwardMark = workUnit.storeID
            self._doOneWork(workUnit)
        if first:
            raise _NoWorkUnits()
        if VERBOSE:
            log.msg("%r.step() returning False" % (self,))
        return False



class _BatchProcessorMixin:
    def step(self, style=iaxiom.LOCAL):
        now = extime.Time()
        first = True

        for listener in self.store.query(_ReliableListener,
                                         attributes.AND(_ReliableListener.processor == self,
                                                        _ReliableListener.style == style),
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
        self.batchController = process.ProcessController(
            "batch", proto, tacPath)
        return self.batchController.getProcess().addCallback(self._addStore)


    def _addStore(self, proto):
        return SetStore(storepath=self.store.dbdir).do(proto)


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



class BatchProcessingProtocol(process.JuiceChild):
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

        self.siteStore = store.Store(storepath)
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
        try:
            paths = set([p.path for p in self.siteStore.query(substore.SubStore).getColumn("storepath")])
        except:
            # See #658
            log.err()
        else:
            for removed in set(self.subStores) - paths:
                self.subStores[removed].disownServiceParent()
                del self.subStores[removed]
                if VERBOSE:
                    log.msg("Removed SubStore " + removed)
            for added in paths - set(self.subStores):
                self.subStores[added] = BatchProcessingService(store.Store(added), style=iaxiom.REMOTE)
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
        while True:
            try:
                items = list(self.items())
            except:
                # See #658
                log.err()
                yield self.deferLater(1.0)
                continue

            if VERBOSE:
                log.msg("Found %d processors for %s" % (len(items), self.store))
            while items and self.running:
                item = items.pop()
                if item not in self.suspended:
                    if VERBOSE:
                        log.msg("Stepping processor %r" % (item,))
                    try:
                        item.step(style=self.style)
                    except:
                        # See #658
                        log.err()
                else:
                    if VERBOSE:
                        log.msg("Skipping suspended processor %r" % (item,))
                yield None
            yield self.deferLater(1.0)


    def startService(self):
        service.Service.startService(self)
        self.parent.cooperator.coiterate(self.step())
