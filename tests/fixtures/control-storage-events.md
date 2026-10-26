# Frozen control-state replay fixtures

`control-storage-events.json.gz` contains synthetic logical events captured from
owned temporary roots in the existing journal, host, review, PR, migration,
issue, repair, ingest and reporting tests. Compression keeps repeated fixture
packages small; decompress with a standard gzip reader to inspect the JSON.
Temporary application/plugin paths are inert fixture data. They are not real
project roots, and replay must not consult them. Preserve original package,
receipt and proof hashes when editing a case.

`storage_event_cases.py` adds explicit missing core/domain transitions and derives
the registered domain/host branch inventory from the reducers. The SQLite tests
require valid coverage of every core and registered domain/host event branch,
compare complete logical data and original receipts with the pure legacy
reducer, and compare malformed variant failures. Live repository approval guards
are tested separately from pure historical replay. The fixture is frozen rather
than regenerated from the new storage implementation, keeping the legacy oracle
independent of future physical layout changes.
