"""Independent, point-verifiable entity discovery witnesses (not authentication)."""
from .store import WorkflowError

SCHEMA='''
CREATE TABLE entity_catalog(space TEXT, key TEXT,
    position INTEGER NOT NULL, value_hash TEXT NOT NULL, run_id TEXT, status TEXT,
    host TEXT, session_id TEXT, package_hash TEXT, record_id TEXT, PRIMARY KEY(space,key));
CREATE INDEX catalog_run ON entity_catalog(space,run_id);
CREATE INDEX catalog_status ON entity_catalog(space,status);
CREATE INDEX catalog_session ON entity_catalog(space,host,session_id,status);
CREATE INDEX catalog_identity ON entity_catalog(space,record_id);
CREATE TABLE space_catalog(path TEXT PRIMARY KEY,parent TEXT,name TEXT NOT NULL,shape TEXT NOT NULL,position INTEGER NOT NULL);
CREATE TABLE operation_catalog(operation_id TEXT PRIMARY KEY, sequence INTEGER UNIQUE NOT NULL,
    kind TEXT NOT NULL, event_hash TEXT NOT NULL);
CREATE TABLE document_file_catalog(space TEXT, proposal_id TEXT, repo_id TEXT, path TEXT, record_hash TEXT,
    PRIMARY KEY(proposal_id,path));
CREATE INDEX document_catalog_lookup ON document_file_catalog(repo_id,path,record_hash);
'''
FIELDS='position,value_hash,run_id,status,host,session_id,package_hash,record_id'


def headers(path,value):
    meta=value if isinstance(value,dict) else {}
    binding=meta.get('binding') if isinstance(meta.get('binding'),dict) else {}
    run_id=meta.get('run_id') or (binding.get('run_id') if path==('usage','events') else meta.get('id') if path==('runs',) else None)
    # Query headers are auxiliary strings; opaque legacy business values retain
    # their original types in the checksum-bound body, including unknown shapes.
    def text(value):
        if isinstance(value,str) or value is None:return value
        if isinstance(value,bool):return str(int(value))
        if isinstance(value,(int,float)):return str(value)
        return None
    return tuple(text(value) for value in (run_id,meta.get('status'),meta.get('host'),meta.get('session_id'),meta.get('package_hash'),meta.get('id')))


def sync(conn,fields):
    values=fields[:3]+(fields[5],)+fields[6:]
    conn.execute('''INSERT INTO entity_catalog VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(space,key) DO UPDATE SET
        position=excluded.position,value_hash=excluded.value_hash,run_id=excluded.run_id,status=excluded.status,
        host=excluded.host,session_id=excluded.session_id,package_hash=excluded.package_hash,record_id=excluded.record_id''',values)


def check(conn,space,key,*,path=None,value=None):
    actual=conn.execute('SELECT '+FIELDS+' FROM entities WHERE space=? AND key=?',(space,key)).fetchone()
    witness=conn.execute('SELECT '+FIELDS+' FROM entity_catalog WHERE space=? AND key=?',(space,key)).fetchone()
    if actual!=witness or path is not None and actual is not None and actual[2:]!=headers(path,value):
        raise WorkflowError('CORRUPT_STORAGE','Entity catalog/header differs from its authoritative record; preserve the root and run full verification.')
    return actual


def rows(conn,space,filters=(),*,keys=None,by_key=False,stream=False):
    require_space(conn,space)
    allowed={'run_id','status','host','session_id','package_hash','record_id','key'}
    if any(field not in allowed for field,_ in filters):
        raise WorkflowError('UNDECLARED_STORAGE_SCOPE','An unindexed query is not an operational scope.')
    where=''.join(' AND '+field+'=?' for field,_ in filters)
    if keys is not None:
        keys=tuple(keys)
        if not keys:return iter(()) if stream else []
        where+=' AND key IN ('+','.join('?' for _ in keys)+')'
    selected='SELECT key FROM entity_catalog WHERE space=?'+where+' UNION SELECT key FROM entities WHERE space=?'+where
    values=(space,*(value for _,value in filters),*(keys or ()))
    cursor=conn.execute('SELECT chosen.key,e.codec,e.payload,e.value_hash FROM ('+selected+''' ) chosen
        LEFT JOIN entities e ON e.space=? AND e.key=chosen.key ORDER BY '''+('chosen.key' if by_key else 'e.position'),
        (*values,*values,space))
    return cursor if stream else cursor.fetchall()


def delete_space(conn,space):
    # Witnesses deliberately do not cascade from authority: a damaged namespace
    # must leave evidence. Intended removals update both copies in one transaction.
    conn.execute('''WITH RECURSIVE selected(path) AS (
        SELECT ? UNION SELECT s.path FROM spaces s JOIN selected p ON s.parent=p.path)
        DELETE FROM entity_catalog WHERE space IN (SELECT path FROM selected)''',(space,))
    conn.execute('''WITH RECURSIVE selected(path) AS (
        SELECT ? UNION SELECT s.path FROM spaces s JOIN selected p ON s.parent=p.path)
        DELETE FROM document_file_catalog WHERE space IN (SELECT path FROM selected)''',(space,))
    conn.execute('''WITH RECURSIVE selected(path) AS (
        SELECT ? UNION SELECT s.path FROM spaces s JOIN selected p ON s.parent=p.path)
        DELETE FROM space_catalog WHERE path IN (SELECT path FROM selected)''',(space,))
    conn.execute('DELETE FROM spaces WHERE path=?',(space,))



def verify(conn):
    verify_operations(conn)
    if conn.execute('SELECT * FROM spaces EXCEPT SELECT * FROM space_catalog').fetchone() or conn.execute('SELECT * FROM space_catalog EXCEPT SELECT * FROM spaces').fetchone():
        raise WorkflowError('CORRUPT_STORAGE','Complete namespace catalog differs from independent witnesses.')
    if conn.execute('SELECT * FROM document_files EXCEPT SELECT * FROM document_file_catalog').fetchone() or conn.execute('SELECT * FROM document_file_catalog EXCEPT SELECT * FROM document_files').fetchone():
        raise WorkflowError('CORRUPT_STORAGE','Complete document lookup differs from independent witnesses.')
    if conn.execute('SELECT 1 FROM entity_catalog c LEFT JOIN spaces s ON s.path=c.space WHERE s.path IS NULL LIMIT 1').fetchone():
        raise WorkflowError('CORRUPT_STORAGE','Entity namespace is missing while its independent catalog witness remains.')
    columns='space,key,'+FIELDS
    # Explicit full audit may enumerate both catalogs. Operational reads never do.
    if conn.execute('SELECT '+columns+' FROM entities EXCEPT SELECT '+columns+' FROM entity_catalog').fetchone() or conn.execute('SELECT '+columns+' FROM entity_catalog EXCEPT SELECT '+columns+' FROM entities').fetchone():
        raise WorkflowError('CORRUPT_STORAGE','Complete entity catalog differs from current records; no history was restored.')


def check_operation(conn,operation_id):
    actual=conn.execute('SELECT sequence,kind,event_hash FROM events WHERE operation_id=?',(operation_id,)).fetchone()
    witness=conn.execute('SELECT sequence,kind,event_hash FROM operation_catalog WHERE operation_id=?',(operation_id,)).fetchone()
    if actual!=witness:
        raise WorkflowError('CORRUPT_STORAGE','Operation locator differs from its independent witness; preserve and verify the root before retrying.')
    return actual


def record_operation(conn,event):
    # No FK/cascade: loss of a retained event locator must leave its ID reserved.
    conn.execute('INSERT INTO operation_catalog VALUES(?,?,?,?)',
        (event[1],event[0],event[2],event[5]))


def document_rows(conn,repo_id,path,record_hash):
    selected=conn.execute('''SELECT proposal_id,path FROM document_file_catalog WHERE repo_id=? AND path=? AND record_hash=?
        UNION SELECT proposal_id,path FROM document_files WHERE repo_id=? AND path=? AND record_hash=?''',
        (repo_id,path,record_hash,repo_id,path,record_hash)).fetchall()
    result=[]
    for proposal_id,file in selected:
        actual=conn.execute('SELECT * FROM document_files WHERE proposal_id=? AND path=?',(proposal_id,file)).fetchone()
        witness=conn.execute('SELECT * FROM document_file_catalog WHERE proposal_id=? AND path=?',(proposal_id,file)).fetchone()
        if actual!=witness:
            raise WorkflowError('CORRUPT_STORAGE','Document lookup differs from its independent witness; preserve and verify the root.')
        result.append(proposal_id)
    return result


def verify_operations(conn):
    columns='operation_id,sequence,kind,event_hash'
    if conn.execute('SELECT '+columns+' FROM events EXCEPT SELECT '+columns+' FROM operation_catalog').fetchone() or conn.execute('SELECT '+columns+' FROM operation_catalog EXCEPT SELECT '+columns+' FROM events').fetchone():
        raise WorkflowError('CORRUPT_STORAGE','Complete operation catalog differs from retained event locators; no ID can be reused.')


def check_space(conn,space):
    first=None;seen=set();required=False
    while True:
        if space in seen or len(seen)>=64:
            raise WorkflowError('CORRUPT_STORAGE','Namespace ancestry is cyclic or unsupported; preserve the root.')
        seen.add(space)
        actual=conn.execute('SELECT * FROM spaces WHERE path=?',(space,)).fetchone()
        witness=conn.execute('SELECT * FROM space_catalog WHERE path=?',(space,)).fetchone()
        if actual!=witness or required and actual is None:
            raise WorkflowError('CORRUPT_STORAGE','Namespace shape/identity differs from its independent witness; preserve and verify the root.')
        if not required:first=actual
        if actual is None or actual[1] is None:return first
        space=actual[1];required=True


def require_space(conn,space):
    record=check_space(conn,space)
    if record is None and has_rows(conn,space):
        raise WorkflowError('CORRUPT_STORAGE','Required entity namespace is missing while indexed records remain.')
    return record


def has_rows(conn,space):
    return conn.execute('SELECT 1 FROM entity_catalog WHERE space=? UNION ALL SELECT 1 FROM entities WHERE space=? LIMIT 1',(space,space)).fetchone() is not None
