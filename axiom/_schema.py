
DELETE_OBJECT = 'DELETE FROM atop_objects WHERE oid = ?'
CREATE_OBJECT = 'INSERT INTO atop_objects (type_id) VALUES (?)'
CREATE_TYPE = 'INSERT INTO atop_types (typename, version) VALUES (?, ?)'


BASE_SCHEMA = ["""
CREATE TABLE atop_objects (
    type_id INTEGER NOT NULL
        CONSTRAINT fk_type_id REFERENCES atop_types(oid)
)
""",

"""
CREATE TABLE atop_types (
    typename VARCHAR(256),
    version INTEGER
)
""",

"""
CREATE TABLE atop_attributes (
    type_id INTEGER,
    row_offset INTEGER,
    indexed BOOLEAN,
    sqltype VARCHAR,
    pythontype VARCHAR,
    attribute VARCHAR,
    docstring TEXT
)
"""]

TYPEOF_QUERY = """
SELECT atop_types.typename, atop_types.version
    FROM atop_types, atop_objects
    WHERE atop_objects.oid = ?
        AND atop_types.oid = atop_objects.type_id
"""

HAS_SCHEMA_FEATURE = ("SELECT COUNT(oid) FROM sqlite_master "
                      "WHERE type = ? AND name = ?")

IDENTIFYING_SCHEMA = ('SELECT indexed, sqltype, attribute '
                      'FROM atop_attributes WHERE type_id = ? '
                      'ORDER BY row_offset')

ADD_SCHEMA_ATTRIBUTE = (
    'INSERT INTO atop_attributes '
    '(type_id, row_offset, indexed, sqltype, attribute, docstring, pythontype) '
    'VALUES (?, ?, ?, ?, ?, ?, ?)')

ALL_TYPES = 'SELECT oid, typename, version FROM atop_types'

GET_TYPE_OF_VERSION = ('SELECT version FROM atop_types '
                       'WHERE typename = ? AND version > ? -- get type of version')

SCHEMA_FOR_TYPE = ('SELECT indexed, pythontype, attribute, docstring '
                   'FROM atop_attributes '
                   'WHERE type_id = ?')

CHANGE_TYPE = 'UPDATE atop_objects SET type_id = ? WHERE oid = ?'

