"""Deterministic documentation generated from catalog definitions."""
def generate_docs(catalog:dict,profiles:dict)->dict:
 lines=['# Workflow stages','']
 for stage in sorted(catalog.get('stages',[]),key=lambda x:x['id']):
  lines.append(f"- **{stage['id']}**; prerequisites: {', '.join(sorted(stage.get('prerequisites',[]))) or 'none'}")
 lines += ['', '# Source profiles','']
 values=profiles.get('profiles',{})
 for name in sorted(values): lines.append(f"- **{name}**: {', '.join(sorted(values[name].get('extensions',[])))}")
 return {'markdown':'\n'.join(lines)+'\n','content_hash':__import__('hashlib').sha256(('\n'.join(lines)+'\n').encode()).hexdigest()}
