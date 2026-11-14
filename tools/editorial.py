#!/usr/bin/env python3
"""Discover topic leads and submit reviewed, article-only PRs for GitHub auto-merge."""
import argparse
import datetime as dt
import fcntl
import hashlib
import html
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import urllib.request
from urllib.parse import urlencode
import xml.etree.ElementTree as ET

from article_policy import OWNER, REPO, ROOT, LABEL, POST_PATH, api, inspect_pr, metadata, quota, validate

STATE = Path(os.environ.get('JOURNAL_EDITORIAL_STATE', Path.home() / '.local/state/journal-editorial'))


def run(*args, cwd=None, timeout=900):
    try:
        return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True, timeout=timeout).stdout.strip()
    except subprocess.CalledProcessError as error:
        print((error.stderr or error.stdout or 'Command failed without diagnostic output')[-4000:], file=sys.stderr)
        raise


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def read(path, default):
    return json.loads(path.read_text()) if path.exists() else default


def receipt_path(branch):
    return STATE / 'requests' / (branch.split('/')[1] + '.json')


def remember(branch, pr):
    old = read(receipt_path(branch), {})
    old.update({'branch': branch, 'pr': pr['number'], 'url': pr['url'], 'status': pr['state'].lower()})
    if pr['state'] == 'OPEN' and pr.get('autoMergeRequest') is None:
        old['status'] = 'paused'
    save(receipt_path(branch), old)
    return old


def feed_entries(data):
    root = ET.fromstring(data)
    entries = []
    for item in list(root.findall('.//item')) + list(root.findall('{http://www.w3.org/2005/Atom}entry')):
        title = item.findtext('title') or item.findtext('{http://www.w3.org/2005/Atom}title') or ''
        link = item.findtext('link')
        if not link:
            node = item.find('{http://www.w3.org/2005/Atom}link')
            link = node.get('href') if node is not None else None
        if title.strip() and link and link.startswith('https://'):
            entries.append({'title': re.sub(r'\s+', ' ', title).strip(), 'url': link})
    return entries[:25]


def discover():
    config = json.loads((ROOT / 'tools/editorial-config.json').read_text())
    queue_path = STATE / 'topics.json'
    old = json.loads(queue_path.read_text()) if queue_path.exists() else {'topics': {}}
    topics = old['topics']
    failures, counts = [], {}
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    for feed in config['feeds']:
        try:
            request = urllib.request.Request(feed['url'], headers={
                'User-Agent': 'SeongwooJournal/1.0 (+https://swchoi1994.github.io/blog/)'})
            with urllib.request.urlopen(request, timeout=15) as response:
                data = response.read(2_000_001)
            if len(data) > 2_000_000:
                raise ValueError('Feed exceeds size limit')
            rows = feed_entries(data)
            counts[feed['name']] = len(rows)
            for row in rows:
                key = hashlib.sha256(row['url'].encode()).hexdigest()[:20]
                topics.setdefault(key, {**row, 'id': key, 'source': feed['name'], 'first_seen': now,
                                       'status': 'candidate', 'evidence_scope': 'Headline only; read primary sources before drafting'})
        except Exception as error:
            failures.append({'source': feed['name'], 'error': type(error).__name__,
                             'http_status': getattr(error, 'code', None)})
    # Keep recent discovery bounded; submitted/used topics are also tracked in PRs/receipts.
    topics = dict(sorted(topics.items(), key=lambda x: x[1]['first_seen'], reverse=True)[:500])
    report = {'checked_at': now, 'topics': topics, 'source_counts': counts, 'source_errors': failures}
    save(queue_path, report)
    print(json.dumps({'topic_count': len(topics), 'source_counts': counts, 'source_errors': failures}))


def request_branch(request_id):
    if not request_id.strip():
        raise ValueError('Use a stable request ID')
    return 'auto-post/' + hashlib.sha256(request_id.encode()).hexdigest()[:24]


def existing_pr(branch):
    def matches(pr):
        return (pr['user']['login'] == OWNER and pr['base']['ref'] == 'main'
                and (pr['head'].get('repo') or {}).get('full_name') == REPO and pr['head']['ref'] == branch)

    saved = read(receipt_path(branch), {})
    if saved.get('pr'):
        # The durable receipt outranks discovery. A failed exact lookup stops;
        # it must never turn a cancelled request into a replacement publication.
        pr = api(f'pulls/{int(saved["pr"])}')
        if not matches(pr):
            raise ValueError('Saved PR identity changed; inspect without creating a replacement')
        data = [pr]
    else:
        # Orphan recovery: qualify the source owner at the API and consume every
        # page, then verify identity. Do not use a capped cross-fork inventory.
        query = urlencode({'state': 'all', 'base': 'main', 'head': OWNER + ':' + branch, 'per_page': 100})
        pages = json.loads(run('gh', 'api', '--paginate', '--slurp', f'repos/{REPO}/pulls?{query}'))
        data = [p for page in pages for p in page if matches(p)]
    if len(data) > 1:
        raise ValueError('Multiple PRs for one request; inspect before doing anything')
    if not data:
        return None
    pr = data[0]
    return {'number': pr['number'], 'url': pr['html_url'], 'state': 'MERGED' if pr.get('merged_at') else pr['state'].upper(),
            'isDraft': pr['draft'], 'autoMergeRequest': pr.get('auto_merge'),
            'isCrossRepository': False, 'author': {'login': OWNER}}


def enqueue(number):
    # This gate is checked again by the required trusted-base GitHub workflow.
    candidate = inspect_pr(number)
    run('gh', 'pr', 'merge', str(number), '--repo', REPO, '--auto', '--squash',
        '--match-head-commit', candidate['head_sha'])
    return candidate


def submit(file, request_id, evidence):
    branch = request_branch(request_id)
    existing = existing_pr(branch)
    if existing:
        # An uncertain earlier attempt is reconciled; never create a second post.
        remember(branch, existing)
        # A retry must not reverse a later owner stop. Only the first submission
        # or an explicit resume-pr command may enable native auto-merge.
        print(json.dumps({'status': 'existing_request', 'pr': existing}))
        return
    text = file.read_text()
    info, _ = metadata(text)
    path = 'content/posts/' + file.name
    if not POST_PATH.fullmatch(path) or not evidence.is_file() or len(evidence.read_text().strip()) < 80:
        raise ValueError('Provide a native article and a substantive source/verification report')
    if request_id.startswith('wa:') and request_id in evidence.read_text():
        raise ValueError('Keep private WhatsApp request IDs out of the public evidence report')
    with tempfile.TemporaryDirectory(prefix='journal-post-') as temp:
        work = Path(temp) / 'site'
        run('git', 'clone', '--quiet', '--branch', 'main', '--single-branch',
            f'https://github.com/{REPO}.git', str(work))
        target = work / path
        if target.exists():
            raise ValueError('This slug is already published; automatic publishing does not edit existing posts')
        # Validate against current main, including the shared publication quota.
        synthetic = {'state': 'open', 'draft': False, 'user': {'login': 'swchoi1994'},
                     'base': {'ref': 'main'}, 'head': {'repo': {'full_name': REPO}, 'ref': branch},
                     'labels': [{'name': LABEL}]}
        validate(synthetic, [{'status': 'added', 'filename': path}],
                 [{'path': path, 'mode': '100644', 'type': 'blob'}], text, work)
        remote = run('git', 'ls-remote', '--heads', 'origin', 'refs/heads/' + branch, cwd=work)
        if remote:
            # Recover a push whose PR creation failed. Never replace its contents.
            run('git', 'fetch', 'origin', 'refs/heads/' + branch, cwd=work)
            run('git', 'switch', '-c', branch, 'FETCH_HEAD', cwd=work)
            changed = run('git', 'diff', '--name-status', 'origin/main...HEAD', cwd=work)
            if changed != 'A\t' + path or target.is_symlink() or target.read_text() != text:
                raise ValueError('Orphan branch differs from this request; inspect without force-pushing')
        else:
            run('git', 'switch', '-c', branch, cwd=work)
            target.write_text(text)
            run('git', 'add', '--', path, cwd=work)
        run('python3', 'tools/publish.py', cwd=work)
        run('python3', '-m', 'unittest', 'discover', '-s', 'tools', '-p', 'test_*.py', cwd=work)
        run('git', 'diff', '--cached', '--check', cwd=work)
        run('git', 'diff', '--check', 'origin/main...HEAD', cwd=work)
        run('node', 'tools/article-smoke.cjs', path, cwd=work)
        if not remote:
            run('git', '-c', 'user.name=Seongwoo Choi', '-c', 'user.email=15826122+swchoi1994@users.noreply.github.com',
                'commit', '-m', 'Publish article: ' + info['title'], cwd=work)
        head = run('git', 'rev-parse', 'HEAD', cwd=work)
        # A stable branch plus a lease-free push refuses concurrent, conflicting requests.
        run('git', '-c', 'credential.helper=!gh auth git-credential', 'push', 'origin', f'HEAD:refs/heads/{branch}', cwd=work)
        body = (f'Owner-authorized automatic article publication.\n\nArticle: `{path}`\n\n'
                'Source verification and original contribution:\n\n' + evidence.read_text().strip() + '\n')
        body_file = Path(temp) / 'pr-body.md'
        body_file.write_text(body)
        url = run('gh', 'pr', 'create', '--repo', REPO, '--base', 'main', '--head', branch,
                  '--title', 'Article: ' + info['title'], '--body-file', str(body_file), '--label', LABEL)
        number = int(url.rstrip('/').split('/')[-1])
        receipt = {'request_id_hash': branch.removeprefix('auto-post/'), 'branch': branch,
                   'pr': number, 'url': url, 'head_sha': head, 'status': 'created'}
        receipt['path'] = path
        save(receipt_path(branch), receipt)
        enqueue(number)
        receipt['status'] = 'auto_merge_requested'
        save(receipt_path(branch), receipt)
        print(json.dumps(receipt))


def reconcile():
    rows = json.loads(run('gh', 'pr', 'list', '--repo', REPO, '--label', LABEL, '--state', 'open',
                          '--json', 'number,headRefName,headRefOid,isDraft,isCrossRepository,author,autoMergeRequest', '--limit', '100'))
    results = []
    for row in rows:
        if row['isCrossRepository'] or row['author']['login'] != OWNER or not row['headRefName'].startswith('auto-post/'):
            continue
        try:
            remember(row['headRefName'], {'number': row['number'], 'url': f'https://github.com/{REPO}/pull/{row["number"]}', 'state': 'OPEN', 'autoMergeRequest': None if row['isDraft'] else row['autoMergeRequest']})
            if row['isDraft'] or row['autoMergeRequest'] is None:
                results.append({'pr': row['number'], 'status': 'paused', 'reason': 'Native auto-merge is disabled; an owner request is required to resume'})
                continue
            candidate = inspect_pr(row['number'])
            # GitHub itself decides whether an update is needed; all new checks rerun.
            pr = api(f'pulls/{row["number"]}')
            if pr['mergeable_state'] == 'behind':
                run('gh', 'api', '--method', 'PUT', f'repos/{REPO}/pulls/{row["number"]}/update-branch',
                    '-f', 'expected_head_sha=' + candidate['head_sha'])
            # Updating the branch reruns CI; GitHub retains or disables its own
            # auto-merge state. Never re-enable it during background maintenance.
            results.append({'pr': row['number'], 'status': 'auto_merge_enabled_at_check'})
        except (ValueError, subprocess.CalledProcessError) as error:
            results.append({'pr': row['number'], 'status': 'held',
                            'reason': str(error) if isinstance(error, ValueError) else 'GitHub operation failed; inspect PR checks'})
    save(STATE / 'reconcile.json', {'checked_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'results': results})
    print(json.dumps(results))


def resume_pr(number):
    """Explicit owner command, never called by the scheduled writer/reconciler."""
    candidate = enqueue(number)
    pr = api(f'pulls/{number}')
    receipt = {'branch': pr['head']['ref'], 'pr': number, 'url': pr['html_url'],
               'head_sha': candidate['head_sha'], 'path': candidate['path'], 'status': 'auto_merge_requested'}
    save(receipt_path(receipt['branch']), receipt)
    print(json.dumps(receipt))


def queue_request(topic, request_id):
    branch = request_branch(request_id)
    path = STATE / 'owner-queue.json'
    data = read(path, {})
    key = branch.split('/')[1]
    if key in data and data[key]['topic'] != topic:
        raise ValueError('Request ID already belongs to different content')
    data.setdefault(key, {'request_id': request_id, 'topic': topic,
                         'created_at': dt.datetime.now(dt.timezone.utc).isoformat()})
    save(path, data)
    print(json.dumps({'status': 'queued', 'request': data[key]}))


def next_topic():
    config = json.loads((ROOT / 'tools/editorial-config.json').read_text())
    budget = quota(ROOT, dt.datetime.now(dt.timezone.utc), config['posts_per_seven_days'])
    receipts = [read(p, {}) for p in (STATE / 'requests').glob('*.json')]
    pending = [r['pr'] for r in receipts if r.get('status') not in ('live', 'closed', 'merged', 'paused')]
    done = {r['branch'] for r in receipts}
    decisions = read(STATE / 'decisions.json', {})
    done.update(key for key, decision in decisions.items() if decision['status'] == 'held')
    owners = list(read(STATE / 'owner-queue.json', {}).values())
    candidates = list(read(STATE / 'topics.json', {'topics': {}})['topics'].values())
    topics = [{'request_id': x['id'], **x} for x in reversed(candidates)]
    selected = next((x for x in owners + topics if request_branch(x['request_id']) not in done), None)
    print(json.dumps({'quota': budget, 'pending_prs': pending,
                      'paused_prs': [r['pr'] for r in receipts if r.get('status') == 'paused'],
                      'can_submit': bool(budget['available'] and not pending), 'next': selected,
                      'held_requests': decisions}))


def decision(request_id, reason=None):
    path = STATE / 'decisions.json'
    data = read(path, {})
    key = request_branch(request_id)
    data[key] = {'status': 'held' if reason else 'ready', 'reason': reason,
                 'updated_at': dt.datetime.now(dt.timezone.utc).isoformat()}
    save(path, data)
    print(json.dumps(data[key]))


def published_matches(document, title, body):
    from publish import scrollable_tables
    # Apply the same presentation transform as the site generator. A 200 alone
    # or merely matching the title does not establish a published article.
    return '<h1' in document and html.escape(title, quote=True) in document and scrollable_tables(body).strip() in document


def receipts():
    results = []
    for path in (STATE / 'requests').glob('*.json'):
        receipt = read(path, {})
        if receipt.get('notified') or receipt.get('status') == 'closed':
            continue
        pr = api(f'pulls/{receipt["pr"]}')
        if not pr.get('merged_at'):
            # Also reconcile records whose label was removed, so an intentional
            # stop does not block unrelated future topics indefinitely.
            receipt['status'] = ('closed' if pr['state'] == 'closed' else
                                 'paused' if pr.get('draft') or pr.get('auto_merge') is None else 'open')
            save(path, receipt)
            continue
        receipt['status'] = 'merged'
        save(path, receipt)
        try:
            files = api(f'pulls/{receipt["pr"]}/files?per_page=100')
            if len(files) != 1 or not POST_PATH.fullmatch(files[0]['filename']):
                raise ValueError('Receipt is not an article-only PR')
            article_path = files[0]['filename']
            blob = api(f'contents/{article_path}?ref={pr["merge_commit_sha"]}')
            import base64
            article = base64.b64decode(blob['content']).decode()
            info, body = metadata(article)
            url = 'https://swchoi1994.github.io/blog/posts/' + Path(article_path).stem + '/'
            request = urllib.request.Request(url, headers={'Cache-Control': 'no-cache', 'User-Agent': 'SeongwooJournal/1.0'})
            with urllib.request.urlopen(request, timeout=30) as response:
                document = response.read(2_000_000).decode()
            if not published_matches(document, info['title'], body):
                raise ValueError('Public page has not yet served the merged article')
            receipt.update({'status': 'live', 'public_url': url, 'verified_at': dt.datetime.now(dt.timezone.utc).isoformat()})
            save(path, receipt)
            message = STATE / 'requests' / f'{path.stem}-published.txt'
            message.write_text(f'Published: {info["title"]}\n{url}\nPR: {receipt["url"]}\nArticle checks passed and the public page was verified.\n')
            run(str(Path.home() / '.local/bin/codex-openclaw'), 'notify', '--key',
                'journal-published-' + str(receipt['pr']), '--file', str(message), timeout=120)
            receipt['notified'] = True
            save(path, receipt)
            results.append({'pr': receipt['pr'], 'status': 'live', 'url': url})
        except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
            results.append({'pr': receipt['pr'], 'status': 'awaiting_verified_receipt', 'reason': type(error).__name__})
    print(json.dumps(results))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('discover')
    commands.add_parser('reconcile')
    commands.add_parser('receipts')
    commands.add_parser('next')
    queue_parser = commands.add_parser('queue')
    queue_parser.add_argument('--topic', required=True)
    queue_parser.add_argument('--request-id', required=True)
    hold_parser = commands.add_parser('hold')
    hold_parser.add_argument('--request-id', required=True)
    hold_parser.add_argument('--reason', required=True)
    resume_parser = commands.add_parser('resume')
    resume_parser.add_argument('--request-id', required=True)
    resume_pr_parser = commands.add_parser('resume-pr')
    resume_pr_parser.add_argument('--pr', type=int, required=True)
    submit_parser = commands.add_parser('submit')
    submit_parser.add_argument('--file', type=Path, required=True)
    submit_parser.add_argument('--request-id', required=True)
    submit_parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    STATE.mkdir(parents=True, exist_ok=True)
    local_command = args.command in ('queue', 'hold', 'resume')
    with (STATE / ('queue.lock' if local_command else 'editorial.lock')).open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.command == 'discover':
            discover()
        elif args.command == 'reconcile':
            reconcile()
        elif args.command == 'receipts':
            receipts()
        elif args.command == 'next':
            next_topic()
        elif args.command == 'queue':
            queue_request(args.topic, args.request_id)
        elif args.command in ('hold', 'resume'):
            decision(args.request_id, args.reason if args.command == 'hold' else None)
        elif args.command == 'resume-pr':
            resume_pr(args.pr)
        else:
            submit(args.file.resolve(), args.request_id, args.evidence.resolve())


if __name__ == '__main__':
    main()
