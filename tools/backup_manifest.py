"""Generate a local SHA-256 inventory, excluding credentials and ignored data."""
import hashlib
import json
from pathlib import Path
import subprocess
from privacy_check import ROOT, project_files, classifications

entries = []
for name in project_files():
    if name == 'backup-manifest.json': continue
    path = ROOT / name
    if not path.is_file(): continue
    data = path.read_bytes()
    if classifications(name, data, []): raise SystemExit('Privacy check required before creating manifest')
    entries.append({'path':name, 'bytes':len(data), 'sha256':hashlib.sha256(data).hexdigest()})
manifest = {'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'files':entries}
output = ROOT / 'backup-manifest.json'
output.write_text(json.dumps(manifest,ensure_ascii=False,indent=2) + '\n')
print(json.dumps({'files':len(entries), 'total_bytes':sum(e['bytes'] for e in entries), 'manifest':output.name}))
