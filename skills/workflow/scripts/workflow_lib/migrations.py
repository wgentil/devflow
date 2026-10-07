"""Grounded specification checks and ordered migration parity records."""
from __future__ import annotations
from copy import deepcopy

def review_specification(spec: dict, source_index: dict) -> dict:
    sources={(s.get('path'),s.get('commit')) for s in source_index.get('sources',[]) if isinstance(s,dict)}
    issues=[]; reqs=spec.get('requirements',[])
    seen=set()
    for req in reqs:
        rid=req.get('id')
        if not rid or rid in seen: issues.append({'requirement':rid,'reason':'missing or duplicate ID'})
        seen.add(rid)
        provenance=req.get('provenance',{}).get('sources',[])
        if not provenance or any((s.get('path'),s.get('commit')) not in sources or type(s.get('start_line')) is not int or type(s.get('end_line')) is not int or s['start_line']<1 or s['end_line']<s['start_line'] for s in provenance):
            issues.append({'requirement':rid,'reason':'source citation is unavailable or malformed'})
    return {'complete':not issues,'issues':issues,'requirement_ids':sorted(seen)}

def validate_increments(increments: dict, parity: list[dict]) -> dict:
    rows=increments.get('increments',[]) if isinstance(increments,dict) else []
    ids=[r.get('id') for r in rows if isinstance(r,dict)]; errors=[]
    if len(ids)!=len(rows) or len(set(ids))!=len(ids): errors.append('increment IDs must be unique')
    required={p.get('id') for p in parity}; covered=set()
    graph={r.get('id'):r.get('depends_on',[]) for r in rows if isinstance(r,dict)}
    for row in rows:
        criteria=row.get('criteria',[]); covered.update(criteria)
        if any(d not in graph for d in row.get('depends_on',[])): errors.append('unknown increment dependency')
    if covered!=required: errors.append('parity criteria coverage mismatch')
    visiting=set(); done=set()
    def visit(node):
        if node in visiting: errors.append('increment dependency cycle'); return
        if node in done:return
        visiting.add(node)
        for dep in graph.get(node,[]):
            if dep in graph: visit(dep)
        visiting.discard(node);done.add(node)
    for node in graph:visit(node)
    delivered=set(increments.get('delivered',[])) if isinstance(increments,dict) else set()
    ready={node:all(dep in delivered for dep in deps) for node,deps in graph.items()}
    return {'valid':not errors,'errors':errors,'ready':ready,'ids':ids}

def record_parity(state: dict, increment_id: str, verified: list[str], ruling: dict|None) -> dict:
    result=deepcopy(state); records=result.setdefault('parity',[])
    existing=next((r for r in records if r.get('increment_id')==increment_id),None)
    record={'increment_id':increment_id,'verified':sorted(set(verified)),'ruling':deepcopy(ruling)}
    if existing:
        if existing!=record: raise ValueError('parity record already exists with different evidence')
    else: records.append(record)
    return result
