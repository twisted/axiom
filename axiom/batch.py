# -*- test-case-name: axiom.test.test_batch -*-

"""
Utilities for performing repetitive tasks over potentially large sets
of data over an extended period of time.
"""

import weakref, datetime

from twisted.python import reflect, failure, log

from epsilon import extime

from axiom import item, attributes

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

    def _forwardWork(self, workUnitType):
        return self.store.query(
            workUnitType,
            workUnitType.storeID > self.forwardMark,
            sort=workUnitType.storeID.ascending,
            limit=2)

    def _backwardWork(self, workUnitType):
        return self.store.query(
            workUnitType,
            workUnitType.storeID < self.backwardMark,
            sort=workUnitType.storeID.descending,
            limit=2)


    def _doOneWork(self, workUnit):
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
        return False



class _BatchProcessorMixin:
    def step(self):
        now = extime.Time()
        first = True

        for listener in self.store.query(_ReliableListener,
                                         _ReliableListener.processor == self,
                                         ): # sort=_ReliableListener.lastRun.ascending):
            if not first:
                return True
            listener.lastRun = now
            try:
                if listener.step():
                    return True
            except _NoWorkUnits:
                pass
            else:
                first = False
        return False


    def run(self):
        now = extime.Time()
        if self.step():
            return now + datetime.timedelta(milliseconds=self.busyInterval)
        return now + datetime.timedelta(milliseconds=self.idleInterval)


    def addReliableListener(self, listener):
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
                          backwardMark=backwardMark)


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
        attrs = {
            '__name__': 'Batch_' + forType.__name__,

            '__module__': forType.__module__,

            '__repr__': lambda self: '<Batch %r %d>' % (reflect.qual(self.workUnitType), self.storeID),

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
