
import sys
import readline # Imported for its side-effects
import traceback

from pysqlite2.dbapi2 import connect
from pprint import pprint

con = connect(sys.argv[1])
cur = con.cursor()

while True:
    try:
        cur.execute(raw_input("SQL> "))
        results = cur.fetchall()
        if results:
            pprint(results)
    except:
        traceback.print_exc()
