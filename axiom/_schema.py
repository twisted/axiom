
# DELETE_OBJECT = 'DELETE FROM "axiom_objects" WHERE "oid" = ?'
CREATE_OBJECT = 'INSERT INTO "*DATABASE*"."axiom_objects" ("type_id") VALUES (?)'
CREATE_TYPE = 'INSERT INTO "*DATABASE*"."axiom_types" ("typename", "module", "version") VALUES (?, ?, ?)'

GET_TABLE_INFO = 'PRAGMA *DATABASE*.table_info(?)'



# The storeID for an object must be unique over the lifetime of the store.
# Since the storeID is allocated by inserting into axiom_objects, we use
# AUTOINCREMENT so that oids/rowids and thus storeIDs are never reused.

# The column is named "oid" instead of "storeID" for backwards compatibility
# with the implicit oid/rowid column in old Stores.
CREATE_OBJECTS = """
CREATE TABLE "*DATABASE*"."axiom_objects" (
    "oid" INTEGER PRIMARY KEY AUTOINCREMENT,
    "type_id" INTEGER NOT NULL
        CONSTRAINT "fk_type_id" REFERENCES "axiom_types"("oid")
)
"""

CREATE_OBJECTS_IDX = """
CREATE INDEX "*DATABASE*"."axiom_objects_type_idx"
    ON "axiom_objects"("type_id");
"""

CREATE_TYPES = """
CREATE TABLE "*DATABASE*"."axiom_types" (
    "oid" INTEGER PRIMARY KEY AUTOINCREMENT,
    "typename" VARCHAR,
    "module" VARCHAR,
    "version" INTEGER
)
"""


CREATE_ATTRIBUTES = """
CREATE TABLE "*DATABASE*"."axiom_attributes" (
    "type_id" INTEGER,
    "row_offset" INTEGER,
    "indexed" BOOLEAN,
    "sqltype" VARCHAR,
    "allow_none" BOOLEAN,
    "pythontype" VARCHAR,
    "attribute" VARCHAR,
    "docstring" TEXT
)
"""

BASE_SCHEMA = [
    CREATE_OBJECTS, CREATE_OBJECTS_IDX, CREATE_TYPES, CREATE_ATTRIBUTES]


TYPEOF_QUERY = """
SELECT "*DATABASE*"."axiom_types"."typename", "*DATABASE*"."axiom_types"."module", "*DATABASE*"."axiom_types"."version"
    FROM "*DATABASE*"."axiom_types", "*DATABASE*"."axiom_objects"
    WHERE "*DATABASE*"."axiom_objects"."oid" = ?
        AND "*DATABASE*"."axiom_types"."oid" = "*DATABASE*"."axiom_objects"."type_id"
"""

HAS_SCHEMA_FEATURE = ('SELECT COUNT("oid") FROM "*DATABASE*"."sqlite_master" '
                      'WHERE "type" = ? AND "name" = ?')

IDENTIFYING_SCHEMA = ('SELECT "indexed", "sqltype", "allow_none", "attribute" '
                      'FROM "*DATABASE*"."axiom_attributes" WHERE "type_id" = ? '
                      'ORDER BY "row_offset"')

ADD_SCHEMA_ATTRIBUTE = (
    'INSERT INTO "*DATABASE*"."axiom_attributes" '
    '("type_id", "row_offset", "indexed", "sqltype", "allow_none", "attribute", "docstring", "pythontype") '
    'VALUES (?, ?, ?, ?, ?, ?, ?, ?)')

ALL_TYPES = 'SELECT "oid", "module", "typename", "version" FROM "*DATABASE*"."axiom_types"'


LATEST_TYPES = 'SELECT "typename", MAX("version") FROM "*DATABASE*"."axiom_types" GROUP BY "typename"'

GET_GREATER_VERSIONS_OF_TYPE = ('SELECT "version" FROM "*DATABASE*"."axiom_types" '
                                'WHERE "typename" = ? AND "version" > ?')

PERSISTED_SCHEMA = """
SELECT "attribute", "type_id", "sqltype", "indexed", "pythontype", "docstring"
    FROM "*DATABASE*"."axiom_attributes"
"""

CHANGE_TYPE = 'UPDATE "*DATABASE*"."axiom_objects" SET "type_id" = ? WHERE "oid" = ?'

APP_VACUUM = 'DELETE FROM "*DATABASE*"."axiom_objects" WHERE ("type_id" == -1) AND ("oid" != (SELECT MAX("oid") from "*DATABASE*"."axiom_objects"))'

