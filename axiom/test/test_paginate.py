
from twisted.trial.unittest import TestCase


from axiom.store import Store
from axiom.item import Item
from axiom.attributes import integer

from axiom.test.util import QueryCounter

class B(Item):
    n = integer(indexed=True)




class CrossTransactionIteration(TestCase):

    def test_separateTransactions(self):
        """
        Verify that 'paginate' is iterable in separate transactions.
        """
        s = Store()
        b1 = B(store=s, n=1)
        b2 = B(store=s, n=2)
        b3 = B(store=s, n=3)
        itr = s.transact(lambda : iter(s.query(B).paginate()))
        self.assertIdentical(s.transact(itr.next), b1)
        self.assertEquals(s.transact(lambda : (itr.next(), itr.next())),
                          (b2, b3))
        self.assertRaises(StopIteration, itr.next)


    def test_moreItemsNotMoreWork(self):
        """
        Verify that each step of a paginate does not become more work as items
        are added.
        """
        s = Store()
        self._checkEfficiency(s.query(B))

    def test_moreItemsNotMoreWorkSorted(self):
        """
        Verify that each step of a paginate does not become more work as more
        items are added even if a sort is given.
        """
        s = Store()
        self._checkEfficiency(s.query(B, sort=B.n.ascending))

    def _checkEfficiency(self, qry):
        s = qry.store
        mnum = [0]
        def more():
            mnum[0]+=1
            B(store=s, n=mnum[0])
        more(); more(); more(); more(); more() # 5

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
        what = qc.measure(g.next)                # 1
        oneunit = qc.measure(g.next)                   # 2
        otherunit = qc.measure(g.next)
        self.assertEquals(otherunit, oneunit) # 3
        # Now, make some more data

        more(); more(); more()
        # and make sure that doesn't increase the amount of work
        self.assertEquals(qc.measure(g.next), oneunit) # 4
        self.assertEquals(qc.measure(g.next), oneunit) # 5
        self.assertEquals(qc.measure(g.next), oneunit) # 6

        # one more sanity check - we're at the end.
        self.assertEquals(g.next().n, 7)
        self.assertEquals(g.next().n, 8)
        self.assertEquals(list(g), [])


    def test_storeIDTiebreaker(self):
        """
        Verify that items whose sort column are identical are all returned and
        deterministically ordered.
        """

        # This is sensitive to page size, so let's test it at a few inflection
        # points:
        s = Store()
        x = [B(store=s, n=1234) for nothing in range(10)]
        first = B(store=s, n=1233)
        last = B(store=s, n=1235)
        for pagesize in [1, 2, 5, 6, 10, 12, 20, 1000]:
            # The ordering here in the asserts might look a little weird - that we
            # ascend by storeID in both cases regardless of the order of the sort,
            # but it's intentional.  The storeID is merely to be a tiebreaker to
            # provide a stable sort.  You could be sorting by any number of
            # compound columns, 'ascending' for your particular column might mean
            # something odd or contradictory to 'ascending' for storeID's
            # 'ascending'.  If you want guaranteed stability on storeID, do that.
            self.assertEqual(
                list(s.query(B, sort=B.n.descending).paginate(pagesize=pagesize)),
                [last] + x + [first])

            self.assertEqual(
                list(s.query(B, sort=B.n.ascending).paginate(pagesize=pagesize)),
                [first] + x + [last])


