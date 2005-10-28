
import itertools
import time

from testbase import cur

for num in itertools.count():
    cur.execute("select * from foo")
    foovals = cur.fetchall()
    print num, 'I fetched', len(foovals), 'values.', time.ctime()
