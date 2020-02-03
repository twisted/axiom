
import sys
import readline # Imported for its side-effects
import traceback
from pprint import pprint

from axiom._pysqlite2 import Connection

con = Connection.fromDatabaseName(sys.argv[1])
cur = con.cursor()

while True:
    try:
        cur.execute(raw_input("SQL> "))
        results = list(cur)
        if results:
            pprint(results)
    except:
        traceback.print_exc()
