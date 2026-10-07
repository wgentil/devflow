"""Deterministic report rollups and portable exports."""
from __future__ import annotations
import csv,io,json
from datetime import datetime,timezone

def rollup(reports: list[dict], scope: dict) -> dict:
    eligible, excluded, reasons = [], [], {}
    seen_runs = set()
    for record in sorted(reports, key=lambda r: r.get('as_of', r.get('date', '')), reverse=True):
        date = record.get('as_of', record.get('date', ''))
        month = None
        if date:
            try:
                parsed = datetime.fromisoformat(date.replace('Z', '+00:00'))
                if parsed.tzinfo is not None:
                    month = parsed.astimezone(timezone.utc).strftime('%Y-%m')
            except ValueError:
                pass
        numerator = record.get('numerator', record.get('cost'))
        denominator = record.get('denominator', record.get('accepted_requirements'))
        matches = ((scope.get('project') is None or record.get('project') == scope['project'])
                   and (scope.get('version') is None or record.get('version') == scope['version'])
                   and (scope.get('month') is None or month == scope['month']))
        numeric = type(numerator) in (int, float) and type(denominator) in (int, float) and denominator > 0
        overlap = bool(set(record.get('run_ids', [])) & seen_runs)
        if matches and numeric and not overlap:
            eligible.append((record, numerator, denominator))
            seen_runs.update(record.get('run_ids', []))
        else:
            excluded.append(record)
            reasons[record.get('id', '')] = ('outside scope' if not matches else
                'overlapping earlier report snapshot' if overlap else 'cost or denominator unavailable')
    numerator = sum(n for _, n, _ in eligible)
    denominator = sum(d for _, _, d in eligible)
    ratio = numerator / denominator if denominator else None
    return {'eligible_run_ids': [r.get('id') for r, _, _ in eligible],
            'excluded_run_ids': [r.get('id') for r in excluded],
            'exclusion_reasons': reasons, 'numerator': numerator, 'denominator': denominator,
            'ratio': ratio, 'scope': scope, 'status': 'available' if ratio is not None else 'unavailable',
            'price_versions': sorted({r['price_version'] for r, _, _ in eligible if r.get('price_version')}),
            'formula_versions': sorted({r['formula_version'] for r, _, _ in eligible if r.get('formula_version')}),
            'provisional': any(r.get('defect_window_status') == 'provisional' for r, _, _ in eligible)}

def export_report(report:dict,format:str)->str:
 if format=='json':return json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+'\n'
 if format=='markdown':return '# Report\n\n'+ '\n'.join(f'- **{k}**: {v}' for k,v in sorted(report.items()))+'\n'
 if format=='csv':
  output=io.StringIO(); w=csv.writer(output); w.writerow(['field','value'])
  for k,v in sorted(report.items()):
   text=str(v)
   if text.lstrip().startswith(('=','+','-','@')):text="'"+text
   w.writerow([k,text])
  return output.getvalue()
 raise ValueError('unsupported export format')
