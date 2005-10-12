# -*- test-case-name: axiom.test.test_queryutil -*-

from axiom.attributes import AND, OR

def overlapping(startAttribute, # X
                endAttribute,   # Y
                startValue,     # A
                endValue,       # B
                ):
    """
    Return an L{axiom.iaxiom.IComparison} (an object that can be passed as the
    'comparison' argument to Store.query/.sum/.count) which will constrain a
    query against 2 attributes for ranges with overlap with the given
    arguments.

    For a database with Items of class O which represent values in this
    configuration:

            X                   Y
           (a)                 (b)
            |-------------------|
      (c)      (d)
       |--------|          (e)      (f)
                            |--------|

   (g) (h)
    |---|                            (i)    (j)
                                      |------|

   (k)                                   (l)
    |-------------------------------------|

           (a)                           (l)
            |-----------------------------|
      (c)                      (b)
       |------------------------|

      (c)  (a)
       |----|
                               (b)       (l)
                                |---------|

    The query:
        myStore.query(
            O,
            findOverlapping(O.X, O.Y,
                            a, b))

    Will return a generator of Items of class O which represent segments a-b,
    c-d, e-f, k-l, a-l, c-b, c-a and b-l, but NOT segments g-h or i-j.

    (NOTE: If you want to pass attributes of different classes for
    startAttribute and endAttribute, read the implementation of this method to
    discover the additional join clauses required.  This may be eliminated some
    day so for now, consider this method undefined over multiple classes.)

    In the database where this query is run, for an item N, all values of
    N.startAttribute must be less than N.endAttribute.

    startValue must be less than endValue.

    """
    assert startValue <= endValue

    return OR(
        AND(startAttribute >= startValue,
            startAttribute <= endValue),
        AND(endAttribute >= startValue,
            endAttribute <= endValue),
        AND(startAttribute <= startValue,
            endAttribute >= endValue)
        )
