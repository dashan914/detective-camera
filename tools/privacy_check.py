"""Fail closed on common private data; report classifications, never contents."""
import argparse
import gzip
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    'private_key': rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
    'api_key': rb'\bsk-[A-Za-z0-9_-]{20,}',
    'github_token': rb'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})',
    'personal_path': rb'/' + rb'Users/[^\s\x00"\']+',
    'personal_email': rb'\b[A-Za-z0-9._%+-]+@(?:gmail|qq|163|126|outlook)\.com\b',
    'private_deployment_ip': rb'(?:150\.109\.' + rb'230\.42|49\.235\.' + rb'175\.57)',
}
PRIVATE_NAMES = {'.env', 'director_state.json', 'latest_photo.jpg', 'latest_preview.jpg',
                 'new_photo_review.jpg', 'story_review.json', 'id_rsa', 'id_ed25519'}
PRIVATE_SUFFIXES = {'.pem', '.key', '.p12', '.pfx', '.bin'}
PRIVATE_FOLDERS = {'case_audio', 'audio-source-backup', 'node_modules', '__pycache__'}


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def project_files():
    return sorted(set(git('ls-files', '-z', '--cached', '--others', '--exclude-standard').decode().split('\0')) - {''})


def classifications(name, data, secrets):
    path = Path(name)
    content = gzip.decompress(data) if path.suffix == '.blend' and data.startswith(b'\x1f\x8b') else data
    found = [label for label, pattern in PATTERNS.items() if re.search(pattern, content)]
    if path.name in PRIVATE_NAMES or path.suffix in PRIVATE_SUFFIXES or PRIVATE_FOLDERS.intersection(path.parts):
        found.append('private_file')
    if any(secret in content for secret in secrets): found.append('known_secret')
    if len(data) >= 100 * 1024 * 1024: found.append('github_file_limit')
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--history', action='store_true')
    parser.add_argument('--secret-env', type=Path, action='append', default=[])
    args = parser.parse_args()
    secrets = []
    for env in args.secret_env:
        for line in env.read_text().splitlines():
            if '=' not in line or line.lstrip().startswith('#'): continue
            key, value = line.split('=', 1)
            value = value.strip().strip('"').strip("'")
            if len(value) >= 12 and any(term in key.upper() for term in ('KEY', 'TOKEN', 'PASSWORD', 'REFERENCE_ID')):
                secrets.append(value.encode())
    findings = []
    files = project_files()
    for name in files:
        path = ROOT / name
        if not path.is_file(): continue
        kinds = classifications(name, path.read_bytes(), secrets)
        if kinds: findings.append({'scope': 'files', 'file': name, 'types': kinds})
    blobs = 0
    if args.history:
        for item in git('rev-list', '--objects', '--all').decode().splitlines():
            oid, _, name = item.partition(' ')
            if not name or git('cat-file', '-t', oid).strip() != b'blob': continue
            blobs += 1
            kinds = classifications(name, git('cat-file', 'blob', oid), secrets)
            if kinds: findings.append({'scope': 'history', 'file': name, 'types': kinds})
        # Git author identities are also metadata. Noreply addresses are allowed.
        identities = git('log', '--all', '--format=%ae%n%ce').decode().splitlines()
        if any(email and 'noreply' not in email for email in identities):
            findings.append({'scope':'history', 'file':'commit metadata', 'types':['non_noreply_email']})
    print(json.dumps({'ok': not findings, 'files_checked':len(files), 'history_blobs_checked':blobs,
                      'findings':findings}, ensure_ascii=False, indent=2))
    return 1 if findings else 0


if __name__ == '__main__': raise SystemExit(main())
