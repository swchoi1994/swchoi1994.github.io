#!/usr/bin/env python3
"""Trusted-base policy for automatic article PRs. Never execute PR code here."""
import argparse
import base64
import datetime as dt
import json
import os
import re
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
REPO = 'swchoi1994/swchoi1994.github.io'
OWNER = 'swchoi1994'
LABEL = 'auto-publish'
POST_PATH = re.compile(r'content/posts/[a-z0-9]+(?:-[a-z0-9]+)*\.html\Z')


def api(path):
    result = subprocess.run(['gh', 'api', f'repos/{REPO}/{path}'],
                            check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def report_status(sha, state, description):
    subprocess.run(['gh', 'api', '--method', 'POST', f'repos/{REPO}/statuses/{sha}',
                    '-f', 'context=Automatic article policy', '-f', f'state={state}',
                    '-f', f'description={description[:140]}', '-f',
                    'target_url=' + os.environ.get('GITHUB_SERVER_URL', 'https://github.com')
                    + '/' + REPO + '/actions/runs/' + os.environ['GITHUB_RUN_ID']],
                   check=True, capture_output=True, text=True, timeout=30)


def metadata(text):
    match = re.match(r'\s*<!--(.*?)-->\s*', text, re.S)
    if not match:
        raise ValueError('Article requires JSON metadata')
    return json.loads(match[1]), text[match.end():]


def timestamp(value):
    value = dt.datetime.fromisoformat(value)
    if value.tzinfo is None:
        raise ValueError('Use a timezone-aware publication timestamp')
    return value


def quota(root, now, maximum):
    if not isinstance(maximum, int) or maximum < 1:
        raise ValueError('Publication limit must be a positive integer')
    recent = []
    for path in (root / 'content/posts').glob('*.html'):
        info, _ = metadata(path.read_text())
        date = timestamp(info['date'])
        if date > now - dt.timedelta(days=7):
            recent.append(date)
    recent.sort()
    return {'used': len(recent), 'limit': maximum,
            'available': max(0, maximum - len(recent)),
            'next_slot_at': (recent[-maximum] + dt.timedelta(days=7)).isoformat()
            if len(recent) >= maximum else None}


class ArticleHTML(HTMLParser):
    """Automatic articles use prose, code samples and existing CSS motifs only."""
    tags = set('p h2 h3 h4 ul ol li pre code strong em b i blockquote table thead tbody tfoot tr td th a details summary div span figure figcaption br hr dl dt dd kbd samp'.split())
    attributes = {'id', 'class', 'title', 'href', 'aria-label', 'role', 'colspan', 'rowspan', 'scope', 'open'}

    def handle_starttag(self, tag, attrs):
        if tag not in self.tags:
            raise ValueError(f'Automatic articles cannot contain <{tag}>; use a manual PR')
        for name, value in attrs:
            if name not in self.attributes:
                raise ValueError(f'Automatic articles cannot set {name}')
            if name == 'href':
                value = value or ''
                parsed = urlsplit(value)
                if not ((parsed.scheme == 'https' and parsed.hostname and not parsed.username)
                        or (value.startswith('/') and not value.startswith('//') and '\\' not in value)
                        or value.startswith('#')):
                    raise ValueError('Article links must use HTTPS or local paths')

    handle_startendtag = handle_starttag


def validate(pr, files, tree, text, root=ROOT, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    if pr['state'] != 'open' or pr['draft'] or pr['user']['login'] != OWNER:
        raise ValueError('Only ready, owner-created PRs qualify')
    if pr['base']['ref'] != 'main' or pr['head']['repo']['full_name'] != REPO:
        raise ValueError('Only same-repository PRs targeting main qualify')
    if not pr['head']['ref'].startswith('auto-post/') or LABEL not in [x['name'] for x in pr['labels']]:
        raise ValueError('Automatic publishing requires auto-post/ and auto-publish')
    if len(files) != 1 or files[0]['status'] != 'added' or not POST_PATH.fullmatch(files[0]['filename']):
        raise ValueError('Automatic publishing allows exactly one NEW content/posts/*.html file')
    path = files[0]['filename']
    entry = next((x for x in tree if x['path'] == path), None)
    if not entry or entry['type'] != 'blob' or entry['mode'] != '100644':
        raise ValueError('Article must be an ordinary file, not a symlink or executable')
    if len(text.encode()) > 100_000:
        raise ValueError('Article exceeds 100 KB')
    info, body = metadata(text)
    if '<' in json.dumps(info) or '>' in json.dumps(info):
        raise ValueError('Metadata must be plain text, never HTML')
    if '{{video:' in body:
        raise ValueError('Embedded media needs a manual PR')
    published = timestamp(info['date'])
    if not now - dt.timedelta(hours=48) <= published <= now + dt.timedelta(minutes=5):
        raise ValueError('Refresh the honest publication date when the article is ready')
    settings = json.loads((root / 'tools/editorial-config.json').read_text())
    budget = quota(root, now, settings['posts_per_seven_days'])
    if not budget['available']:
        raise ValueError('Publication quota full; next slot: ' + budget['next_slot_at'])
    if not isinstance(info.get('sources'), list) or len(info['sources']) < 2:
        raise ValueError('At least two sources are required')
    for source in info['sources']:
        url = urlsplit(source['url'])
        if url.scheme != 'https' or not url.hostname or url.username:
            raise ValueError('Sources must be HTTPS URLs without credentials')
    parser = ArticleHTML(convert_charrefs=True)
    parser.feed(body)
    # Appended page markup must not complete a tag that feed() left buffered.
    if parser.rawdata:
        raise ValueError('Article ends with incomplete HTML')
    parser.close()
    return path


def inspect_pr(number, root=ROOT):
    pr = api(f'pulls/{number}')
    files = api(f'pulls/{number}/files?per_page=100')
    # A one-file PR cannot hide a later page; changed_files comes from GitHub.
    if pr['changed_files'] != len(files) or len(files) != 1:
        raise ValueError('Expected exactly one changed file')
    if not POST_PATH.fullmatch(files[0]['filename']):
        raise ValueError('Expected a native article path')
    tree_response = api(f'git/trees/{pr["head"]["sha"]}?recursive=1')
    if tree_response.get('truncated'):
        raise ValueError('Refusing an incomplete repository tree')
    entry = next((x for x in tree_response['tree'] if x['path'] == files[0]['filename']), None)
    if not entry or entry.get('type') != 'blob' or entry.get('mode') != '100644':
        raise ValueError('Expected a regular article file')
    blob = api(f'git/blobs/{entry["sha"]}')
    if blob.get('size', 100_001) > 100_000 or blob.get('encoding') != 'base64':
        raise ValueError('Unexpected article blob')
    text = base64.b64decode(blob['content']).decode('utf-8')
    path = validate(pr, files, tree_response['tree'], text, root)
    return {'pr': number, 'head_sha': pr['head']['sha'], 'path': path, 'text': text}


def trusted_automatic_peers(sha):
    # Use authoritative commit associations, not GitHub's eventually indexed
    # search. Read every page and apply the bound only to trusted owner peers.
    result = subprocess.run(['gh', 'api', '--paginate', '--slurp',
                             f'repos/{REPO}/commits/{sha}/pulls?per_page=100'],
                            check=True, capture_output=True, text=True, timeout=60)
    peers = [p for page in json.loads(result.stdout) for p in page
             if p['user']['login'] == OWNER and p['state'] == 'open'
             and (p['head'].get('repo') or {}).get('full_name') == REPO and p['head']['sha'] == sha]
    if len(peers) > 1000:
        raise ValueError('Owner PR inventory exceeds inspection limit')
    return [p['number'] for p in peers if p['head']['ref'].startswith('auto-post/')
            or LABEL in [x['name'] for x in p['labels']]]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--event', type=Path)
    parser.add_argument('--pr', type=int)
    parser.add_argument('--quota', action='store_true')
    parser.add_argument('--report-status', action='store_true')
    args = parser.parse_args()
    if args.quota:
        config = json.loads((ROOT / 'tools/editorial-config.json').read_text())
        print(json.dumps(quota(ROOT, dt.datetime.now(dt.timezone.utc), config['posts_per_seven_days'])))
        return
    if args.event:
        event = json.loads(args.event.read_text())
        pr = event['pull_request']
        number = pr['number']
        sha = pr['head']['sha']
        # Commit statuses are shared by SHA, including forks. An outsider must
        # never overwrite a trusted owner's result using a second PR at that SHA.
        # GitHub's immutable event identity lets us reject foreign events without
        # a network call, then invalidate prior approval before any live lookup.
        if pr['user']['login'] != OWNER or (pr['head'].get('repo') or {}).get('full_name') != REPO:
            print('Foreign PR: no shared commit status emitted. Use an owner branch for review.')
            return
        if args.report_status:
            report_status(sha, 'pending', 'Checking trusted article policy')
        try:
            current = api(f'pulls/{number}')
            if current['head']['sha'] != sha:
                raise ValueError('PR changed during validation; wait for the latest run')
            if LABEL not in [x['name'] for x in current['labels']] and not current['head']['ref'].startswith('auto-post/'):
                # Even an owner's second manual PR must not clear an automatic
                # PR's failure on the same commit (statuses are not PR-scoped).
                for peer_number in trusted_automatic_peers(sha):
                    if inspect_pr(peer_number)['head_sha'] != sha:
                        raise ValueError('Associated automatic PR changed during validation')
                print('Manual PR scope checked, including automatic PRs sharing this commit.')
            else:
                result = inspect_pr(number)
                if result['head_sha'] != sha:
                    raise ValueError('PR changed during validation')
                print(json.dumps({k: v for k, v in result.items() if k != 'text'}))
        except Exception:
            if args.report_status:
                report_status(sha, 'failure', 'Article policy failed; inspect workflow logs')
            raise
        if args.report_status:
            report_status(sha, 'success', 'Trusted article policy passed')
        return
    else:
        number = args.pr
    if not number:
        parser.error('--event, --pr or --quota required')
    result = inspect_pr(number)
    print(json.dumps({k: v for k, v in result.items() if k != 'text'}))


if __name__ == '__main__':
    main()
