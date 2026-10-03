"""Generate only the approved demo inference via the project's existing API.

Run on the deployment host; secrets are read in memory, never printed/copied.
Does not import server.py, queue jobs, restart services, or change .env.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path

TEXT = '衣架穿了它太久，这件衣服早就记住了衣架的样子。\n衣服真正的主人是衣架。\n而你，极有可能是个小偷。'

parser = argparse.ArgumentParser()
parser.add_argument('--backend-dir', required=True, type=Path)
parser.add_argument('--output', required=True, type=Path)
parser.add_argument('--inspect', action='store_true')
parser.add_argument('--text', default=TEXT)
args = parser.parse_args()
if args.text not in [TEXT, *TEXT.splitlines()]:
    raise SystemExit('Only the approved case text or one approved sentence is allowed')

values = {}
for line in (args.backend_dir / '.env').read_text().splitlines():
    if '=' in line and not line.lstrip().startswith('#'):
        key, value = line.split('=', 1)
        if key.strip() in ('FISH_API_KEY', 'FISH_REFERENCE_ID', 'FISH_VOICE_ENABLED'):
            values[key.strip()] = value.strip().strip('\"').strip("'")
configured = bool(values.get('FISH_API_KEY')) and bool(values.get('FISH_REFERENCE_ID'))
if args.inspect:
    print(json.dumps({'configured': configured, 'helper_present': (args.backend_dir / 'case_voice.py').is_file()}))
    raise SystemExit(0)
if not configured:
    raise SystemExit('Existing project narration credential/voice is missing')
for key, value in values.items():
    os.environ[key] = value

spec = importlib.util.spec_from_file_location('project_case_voice', args.backend_dir / 'case_voice.py')
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
# One request, no retries or fallback; same configured voice and API as device.
try:
    audio, timing = helper._synthesize_text(args.text)
except Exception:
    raise SystemExit('Existing project narration API did not return valid audio') from None
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_bytes(audio)
print(json.dumps({'status': 'ok', 'bytes': len(audio), 'characters': len(args.text),
                  'complete_ms': timing.get('complete_ms'), 'filename': args.output.name}))
