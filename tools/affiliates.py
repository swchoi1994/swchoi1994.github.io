"""Apply the owner's Amazon tracking ID to selected product links at build time."""
import html
from html.parser import HTMLParser
import json
import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

MARKETPLACES = {'amazon.com', 'amazon.co.uk', 'amazon.ca', 'amazon.com.au', 'amazon.ae', 'amazon.de', 'amazon.fr', 'amazon.it', 'amazon.es', 'amazon.co.jp', 'amazon.in'}
DISCLOSURE = '<aside class="affiliate-disclosure" aria-label="Affiliate disclosure"><strong>Affiliate disclosure.</strong> As an Amazon Associate I earn from qualifying purchases. This article contains affiliate links; I may receive a commission if you buy through them.</aside>'


def load_affiliates(path, article_ids):
    config = json.loads(path.read_text())
    marketplace, tag = config.get('marketplace'), config.get('tracking_id')
    if marketplace is None and tag is None and not config.get('placements'):
        return None
    if marketplace not in MARKETPLACES or not isinstance(tag, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{1,63}', tag):
        raise ValueError('Affiliate setup requires a supported Amazon marketplace and a valid owner tracking ID')
    for slug, products in config.get('placements', {}).items():
        if slug not in article_ids:
            raise ValueError(f'Affiliate placement points to an unpublished article: {slug}')
        if not isinstance(products, list):
            raise ValueError('Each article placement must be a product list')
        for product in products:
            if not re.fullmatch(r'[A-Z0-9]{10}', product.get('asin', '')):
                raise ValueError(f'Invalid Amazon ASIN in {slug}')
            if any(not isinstance(product.get(key), str) or not product[key].strip() for key in ('title', 'reason')):
                raise ValueError(f'Product title and a relevant editorial reason are required in {slug}')
    return config


class Anchor(HTMLParser):
    def handle_starttag(self, tag, attrs):
        self.attrs = dict(attrs)


def apply_affiliates(source, slug, config):
    if config is None:
        return source
    count = 0

    def tag_link(match):
        nonlocal count
        parser = Anchor()
        parser.feed(match[0])
        attrs = parser.attrs
        url = urlsplit(attrs.get('href', ''))
        if (url.scheme != 'https' or url.netloc not in {config['marketplace'], 'www.' + config['marketplace']}
                or not re.match(r'^/(?:[^/]+/)?(?:dp|gp/product)/[A-Z0-9]{10}(?:/|$)', url.path)):
            return match[0]
        query = [(k, v) for k, v in parse_qsl(url.query, keep_blank_values=True) if k.lower() != 'tag']
        query.append(('tag', config['tracking_id']))
        attrs['href'] = urlunsplit(url._replace(query=urlencode(query)))
        attrs['rel'] = ' '.join(sorted(set(attrs.get('rel', '').split()) | {'sponsored', 'nofollow', 'noopener'}))
        count += 1
        return '<a ' + ' '.join(k if v is None else f'{k}="{html.escape(v, quote=True)}"' for k, v in attrs.items()) + '>'

    products = config.get('placements', {}).get(slug, [])
    if products:
        items = ''.join(f'<li><a href="https://www.{config["marketplace"]}/dp/{p["asin"]}/">{html.escape(p["title"])} on Amazon</a><p>{html.escape(p["reason"])}</p></li>' for p in products)
        block = f'<section class="product-links"><h2>Products mentioned in this guide</h2><ul>{items}</ul><p>Check the listing for current specifications, compatibility, price, and availability.</p></section>'
        if '<section class="source-box">' not in source:
            raise ValueError(f'Cannot find source boundary for affiliate placement: {slug}')
        source = source.replace('<section class="source-box">', block + '<section class="source-box">', 1)
    source = re.sub(r'<a\b[^>]*>', tag_link, source, flags=re.I)
    if count:
        if '<header class="reading-header">' not in source:
            raise ValueError(f'Cannot place affiliate disclosure: {slug}')
        source = source.replace('<header class="reading-header">', '<header class="reading-header">' + DISCLOSURE, 1)
    return source
