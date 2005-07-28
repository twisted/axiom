
from testbase import con, cur

cur.execute("create table foo (bar int, baz varchar)")

for x in range(500):
    cur.execute("insert into foo values (?, ?)",
                (x, "string-value-of-"+str(x)))

con.commit()
