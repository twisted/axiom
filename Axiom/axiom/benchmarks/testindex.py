
from testbase import con, cur

cur.execute('create index foo_bar_idx on foo(bar)')
cur.commit()
