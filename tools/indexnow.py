#!/usr/bin/env python3
"""Tell IndexNow search engines (Bing, Naver, Yandex and others) which pages changed.

Run after a deploy. It reads the live sitemap and submits the pages dated today or yesterday,
so each deploy announces new articles and the listing pages that now link to them. The key is
public by design: IndexNow checks it against the key file served at the site root.
"""
import datetime
import json
import sys
import urllib.request
import xml.etree.ElementTree as ET

SITE = 'https://swchoi1994.github.io'
KEY = '55dbbdd38ce93ce4e612a95a6450165f'
ENDPOINT = 'https://api.indexnow.org/indexnow'


def recent(sitemap, today, days=1):
    """URLs from sitemap XML whose lastmod falls within the last `days` days, in sitemap order."""
    earliest = (today - datetime.timedelta(days=days)).isoformat()
    urls = []
    for entry in ET.fromstring(sitemap).findall('{*}url'):
        location, modified = entry.findtext('{*}loc'), entry.findtext('{*}lastmod')
        if location and modified and modified[:10] >= earliest and location.startswith(SITE + '/'):
            urls.append(location)
    return urls


def main():
    with urllib.request.urlopen(SITE + '/sitemap.xml', timeout=30) as response:
        urls = recent(response.read(), datetime.datetime.now(datetime.timezone.utc).date())
    if not urls:
        print('IndexNow: nothing changed in the last day')
        return
    body = json.dumps({'host': SITE.split('//')[1], 'key': KEY, 'keyLocation': f'{SITE}/{KEY}.txt', 'urlList': urls[:10000]}).encode()
    request = urllib.request.Request(ENDPOINT, data=body, headers={'Content-Type': 'application/json; charset=utf-8'})
    with urllib.request.urlopen(request, timeout=30) as response:
        print(f'IndexNow: submitted {len(urls)} URLs, HTTP {response.status}')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:  # a search engine being unreachable must never fail a deploy
        print(f'IndexNow: skipped ({error})')
        sys.exit(0)
