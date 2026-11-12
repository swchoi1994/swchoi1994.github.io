#!/usr/bin/env python3
"""Rank a watchlist of AI names by how much they were discussed and covered this week.

Two public sources, neither needing a key:

- Hacker News: the points earned by stories from the past week whose titles mention the name.
  This measures what developers are discussing.
- Google News: about how many news articles a day mention the name. This measures coverage.

Writes content/trending.json, which the site build turns into the "Trending in AI" box on the
home page and the pages under /trending/. The deploy workflow runs this before each build.
Standard library only.

The names to rank are in content/trend-terms.json. Only those names and their numbers reach the
site: story and article titles are read to count them and are never published. If Hacker News
cannot be read the script exits with an error and leaves the existing file alone, so a build
still has the last good ranking (the build hides the box once that file is too old). If Google
News cannot be read, the ranking uses Hacker News alone and says so.
"""
import datetime
import json
import pathlib
import re
import sys
import time
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
TERMS = ROOT / 'content/trend-terms.json'
OUTPUT = ROOT / 'content/trending.json'
DAYS = 7            # how far back Hacker News stories count
FLOOR = 20          # ignore stories with fewer points than this
KEEP = 20           # how many ranked names to save; the home page shows the first ten
STORIES = 'https://hn.algolia.com/api/v1/search_by_date'
NEWS = 'https://news.google.com/rss/search'
# The news feed returns at most 100 articles. A name that fills it is counted over a shorter
# window and scaled up to a day: (search window, how many of them make a day).
WINDOWS = (('1d', 1), ('6h', 4), ('1h', 24))
# Google's public feed of trending searches, per country. It covers every subject, so an AI name
# appears there only on a big day; when one does, the site marks it.
SEARCHES = 'https://trends.google.com/trending/rss?geo={geo}'
GEOS = ('US', 'GB', 'IN', 'KR')
AGENT = {'User-Agent': 'journal-trends/1.0'}


def read(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=AGENT), timeout=40) as response:
        return response.read().decode('utf-8')


def fetch_stories(now):
    """Every story from the last DAYS days with at least FLOOR points, as {'title', 'points'}."""
    since = int((now - datetime.timedelta(days=DAYS)).timestamp())
    stories, page = [], 0
    while True:
        query = urllib.parse.urlencode({'tags': 'story', 'numericFilters': f'created_at_i>{since},points>={FLOOR}',
                                        'hitsPerPage': 1000, 'page': page})
        data = json.loads(read(f'{STORIES}?{query}'))
        stories += [{'title': hit.get('title') or '', 'points': hit.get('points') or 0} for hit in data['hits']]
        page += 1
        if page >= data['nbPages'] or not data['hits']:
            return stories


def news_query(entry, terms):
    """The news search for one name: its own `news` if given, else the name in quotes.

    A name that begins longer names on the list leaves those out, so "Claude" does not also
    collect every article about "Claude Code".
    """
    name = entry['term']
    longer = [other['term'] for other in terms if other['term'] != name and other['term'].lower().startswith(name.lower() + ' ')]
    return ' '.join([entry.get('news') or f'"{name}"'] + [f'-"{other}"' for other in longer])


def news_rate(query, fetch=read):
    """About how many news articles a day Google News lists for a search."""
    for window, per_day in WINDOWS:
        feed = fetch(f'{NEWS}?' + urllib.parse.urlencode({'q': f'{query} when:{window}', 'hl': 'en-US', 'gl': 'US', 'ceid': 'US:en'}))
        count = feed.count('<item>')
        if count < 100:
            break
    return count * per_day


def fetch_news(terms):
    """Articles a day for every name, or nothing at all if any search fails: half a source would skew the ranking."""
    rates = {}
    try:
        for entry in terms:
            rates[entry['term']] = news_rate(news_query(entry, terms))
            time.sleep(0.2)
    except OSError as problem:
        print(f'trends: Google News skipped ({entry["term"]}: {problem}); ranking by Hacker News alone', file=sys.stderr)
        return {}
    return rates


def fetch_searches():
    """Lower-cased search terms from Google's trending feeds. A feed that fails is skipped."""
    searches = set()
    for geo in GEOS:
        try:
            feed = read(SEARCHES.format(geo=geo))
        except OSError as problem:
            print(f'trends: Google trending searches for {geo} skipped: {problem}', file=sys.stderr)
            continue
        searches.update(title.strip().lower() for title in re.findall(r'<item>\s*<title>(.*?)</title>', feed, re.S))
    return searches


def pattern(entry):
    """The compiled rule for one watchlist entry: its own `match` if given, else the name itself."""
    return re.compile(rf'(?<![\w.-])(?:{entry.get("match") or re.escape(entry["term"])})(?![\w-])', re.I)


def rank(stories, terms, searches=()):
    """Watchlist names with at least one story, ordered by total points, most discussed first.

    A story counts for every name its title mentions, except a name whose match lies inside a
    longer one: "Claude Code ships X" counts for Claude Code, not also for Claude.
    """
    rules = [(entry['term'], pattern(entry)) for entry in terms]
    totals = {name: [0, 0] for name, _ in rules}
    for story in stories:
        found = [(name, match.span()) for name, rule in rules if (match := rule.search(story['title']))]
        for name, (start, end) in found:
            inside = any(other != name and s <= start and end <= e and (e - s) > (end - start) for other, (s, e) in found)
            if not inside:
                totals[name][0] += story['points']
                totals[name][1] += 1
    ranked = sorted(((name, points, count) for name, (points, count) in totals.items() if count),
                    key=lambda item: (-item[1], -item[2], item[0].lower()))
    rules = dict(rules)
    return [{'term': name, 'points': points, 'stories': count,
             'google': any(rules[name].fullmatch(search) for search in searches)}
            for name, points, count in ranked]


def blend(discussed, news):
    """One ranking from both sources.

    Each name gets its share of the week's Hacker News points and its share of the day's news
    articles, as percentages; the score is the average of the two. With no news figures the
    score is the Hacker News share alone. Names with a score of zero are left out.
    """
    rows = {row['term']: dict(row, news=None) for row in discussed}
    for name, rate in news.items():
        rows.setdefault(name, {'term': name, 'points': 0, 'stories': 0, 'google': False})['news'] = rate
    all_points = sum(row['points'] for row in rows.values()) or 1
    all_news = sum(news.values()) or 1
    for row in rows.values():
        shares = [100 * row['points'] / all_points] + ([100 * row['news'] / all_news] if news else [])
        row['score'] = round(sum(shares) / len(shares), 1)
    return sorted((row for row in rows.values() if row['score'] > 0), key=lambda row: (-row['score'], row['term'].lower()))


def main():
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    terms = json.loads(TERMS.read_text())
    try:
        stories = fetch_stories(now)
    except (OSError, ValueError, KeyError) as problem:
        sys.exit(f'trends: Hacker News could not be read, keeping the existing ranking: {problem}')
    discussed = rank(stories, terms, fetch_searches())
    if len(discussed) < 5:
        sys.exit(f'trends: only {len(discussed)} names matched {len(stories)} stories, keeping the existing ranking')
    news = fetch_news(terms)
    items = blend(discussed, news)[:KEEP]
    sources = ['Hacker News'] + (['Google News'] if news else [])
    OUTPUT.write_text(json.dumps({'updated': now.isoformat(), 'days': DAYS, 'sources': sources, 'items': items}, indent=2) + '\n')
    print(f'trends: ranked {len(items)} names from {len(stories)} stories and {"news for " + str(len(news)) + " names" if news else "no news figures"}; first is {items[0]["term"]}')


if __name__ == '__main__':
    main()
