"""Read-only public-release preflight. Never exports files or publishes a repo."""
from fnmatch import fnmatchcase
import json
from pathlib import PurePosixPath
from privacy_check import ROOT, project_files, classifications


def excluded(name, policy):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or '.git' in path.parts:
        return True
    if path.suffix.lower() in ('.mp3', '.pem', '.key', '.bin'):
        return True
    return any(fnmatchcase(name, pattern) for pattern in policy['exclude'])


def pending_reviews(policy):
    return [item for item in policy['reviews'] if item.get('complete') is not True]


def main():
    policy = json.loads((ROOT / 'tools/release_policy.json').read_text())
    included, omitted, privacy = [], [], []
    for name in project_files():
        path = ROOT / name
        if not path.is_file(): continue
        if excluded(name, policy):
            omitted.append(name)
            continue
        kinds = classifications(name, path.read_bytes(), [])
        if kinds: privacy.append({'file':name,'types':kinds})
        included.append(name)
    pending = pending_reviews(policy)
    ready = not pending and not privacy
    print(json.dumps({'mode':policy['mode'], 'ready_for_public_package':ready,
                      'publish_authorized':policy.get('publish_authorized') is True,
                      'candidate_files':len(included), 'excluded_files':omitted,
                      'privacy_findings':privacy, 'pending_reviews':pending,
                      'action':'read_only_no_export_no_publish'}, ensure_ascii=False, indent=2))
    return 0 if ready else 2


if __name__ == '__main__': raise SystemExit(main())
