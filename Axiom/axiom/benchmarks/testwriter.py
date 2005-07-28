
import time
import itertools

from testbase import con, cur
BATCH = 500
for num in itertools.count():
    for x in range(BATCH):
        n = (num * BATCH) + x
        cur.execute("insert into foo values (?, ?)",
                    (n, "string-value-of-"+str(n)))
    con.commit()
    print num, 'write pass complete', time.ctime()
