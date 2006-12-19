# Copyright 2006 Divmod, Inc.  See LICENSE file for details

"""
This module contains tests for the L{axiom.store.ItemQuery.paginate} method.
"""

from twisted.trial.unittest import TestCase


from axiom.store import Store
from axiom.item import Item
from axiom.attributes import integer, compoundIndex

from axiom.test.util import QueryCounter

class SingleColumnSortHelper(Item):
    mainColumn = integer(indexed=True)
    other = integer()
    compoundIndex(mainColumn, other)

class MultiColumnSortHelper(Item):
    columnOne = integer()
    columnTwo = integer()
    compoundIndex(columnOne, columnTwo)


class CrossTransactionIteration(TestCase):

    def test_separateTransactions(self):
        """
        Verify that 'paginate' is iterable in separate transactions.
        """
        s = Store()
        b1 = SingleColumnSortHelper(store=s, mainColumn=1)
        b2 = SingleColumnSortHelper(store=s, mainColumn=2)
        b3 = SingleColumnSortHelper(store=s, mainColumn=3)
        itr = s.transact(lambda : iter(s.query(SingleColumnSortHelper).paginate()))
        self.assertIdentical(s.transact(itr.next), b1)
        self.assertEquals(s.transact(lambda : (itr.next(), itr.next())),
                          (b2, b3))
        self.assertRaises(StopIteration, lambda : s.transact(itr.next))


    def test_moreItemsNotMoreWork(self):
        """
        Verify that each step of a paginate does not become more work as items
        are added.
        """
        s = Store()
        self._checkEfficiency(s.query(SingleColumnSortHelper))

    def test_moreItemsNotMoreWorkSorted(self):
        """
        Verify that each step of a paginate does not become more work as more
        items are added even if a sort is given.
        """
        s = Store()
        self._checkEfficiency(s.query(SingleColumnSortHelper,
                                      sort=SingleColumnSortHelper.mainColumn.ascending))


    def test_moreItemsNotMoreWorkRestricted(self):
        s = Store()
        self._checkEfficiency(s.query(SingleColumnSortHelper,
                                      SingleColumnSortHelper.other == 6,
                                      sort=SingleColumnSortHelper.mainColumn.ascending))


    def _checkEfficiency(self, qry):
        s = qry.store
        mnum = [0]
        def more():
            mnum[0] += 1
            SingleColumnSortHelper(store=s, mainColumn=mnum[0], other=6)
        for i in range(5):
            more()

        qc = QueryCounter(s)
        # Sanity check: calling paginate() shouldn't do _any_ DB work.
        L = []
        m = qc.measure(
            # Let's also keep the page-size to 1, forcing the implementation to
            # get exactly 1 item each time.  (Otherwise the first N items will
            # take a fixed amount of work, the next 10, and so on, but each
            # subsequent item will take 0, breaking our attempt to measure
            # below)
            lambda : L.append(qry.paginate(pagesize=1)))
        self.assertEquals(m, 0)
        y = L.pop()
        g = iter(y)
        # startup costs a little more, so ignore that
        # s.debug = True
        what = qc.measure(g.next)                # 1
        oneunit = qc.measure(g.next)                   # 2
        otherunit = qc.measure(g.next)
        self.assertEquals(otherunit, oneunit) # 3
        # Now, make some more data

        for i in range(3):
            more()
        # and make sure that doesn't increase the amount of work
        self.assertEquals(qc.measure(g.next), oneunit) # 4
        self.assertEquals(qc.measure(g.next), oneunit) # 5
        self.assertEquals(qc.measure(g.next), oneunit) # 6

        # one more sanity check - we're at the end.
        self.assertEquals(g.next().mainColumn, 7)
        self.assertEquals(g.next().mainColumn, 8)
        self.assertEquals(list(g), [])


    def test_storeIDTiebreaker(self):
        """
        Verify that items whose sort column are identical are all returned and
        deterministically ordered.
        """
        s = Store()
        x = [SingleColumnSortHelper(store=s, mainColumn=1234) for nothing in range(10)]
        first = SingleColumnSortHelper(store=s, mainColumn=1233)
        last = SingleColumnSortHelper(store=s, mainColumn=1235)
        # This is sensitive to page size, so let's test it at lots of places
        # where edge-cases are likely to develop in the implementation.
        for pagesize in range(1, 30) + [1000]:
            # The ordering here in the asserts might look a little weird - that we
            # ascend by storeID in both cases regardless of the order of the sort,
            # but it's intentional.  The storeID is merely to be a tiebreaker to
            # provide a stable sort.  You could be sorting by any number of
            # compound columns, 'ascending' for your particular column might mean
            # something odd or contradictory to 'ascending' for storeID's
            # 'ascending'.  If you want guaranteed stability on storeID, do that.
            self.assertEqual(
                list(s.query(
                        SingleColumnSortHelper,
                        sort=SingleColumnSortHelper.mainColumn.descending
                        ).paginate(pagesize=pagesize)),
                [last] + x + [first])

            self.assertEqual(
                list(s.query(
                        SingleColumnSortHelper,
                        sort=SingleColumnSortHelper.mainColumn.ascending
                        ).paginate(pagesize=pagesize)),
                [first] + x + [last])


    def test_moreThanOneColumnSort(self):
        """
        Verify that paginate works with queries that have complex sort expressions.

        Note: it doesn't.
        """
        s = Store()

        x = MultiColumnSortHelper(store=s, columnOne=1, columnTwo=9)
        y1 = MultiColumnSortHelper(store=s, columnOne=2, columnTwo=1)
        y2 = MultiColumnSortHelper(store=s, columnOne=2, columnTwo=2)
        y3 = MultiColumnSortHelper(store=s, columnOne=2, columnTwo=3)
        y4 = MultiColumnSortHelper(store=s, columnOne=2, columnTwo=4)
        z = MultiColumnSortHelper(store=s, columnOne=3, columnTwo=5)
        self.assertEquals(list(
                s.query(MultiColumnSortHelper,
                        sort=[MultiColumnSortHelper.columnOne.ascending,
                              MultiColumnSortHelper.columnTwo.ascending]
                        ).paginate(pagesize=1)),
                          [x, y1, y2, y3, y4, z])

    test_moreThanOneColumnSort.todo = (
        "There's no use-case for this yet, but it would be a consistent "
        "extension of the API.")


