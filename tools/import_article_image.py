#!/usr/bin/env python3
"""Import a generated cover as responsive WebP assets; Pillow is needed only for import."""
import argparse
import json
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('slug')
parser.add_argument('source', type=Path)
parser.add_argument('prompt')
parser.add_argument('alt')
args = parser.parse_args()
if not (ROOT / 'blog/posts' / args.slug / 'index.html').is_file() or '/' in args.slug:
    parser.error('Expected an existing article ID')
folder = ROOT / 'assets/img/articles'
folder.mkdir(exist_ok=True, parents=True)
manifest_path = ROOT / 'content/article-images.json'
manifest = json.loads(manifest_path.read_text())
with Image.open(args.source) as original:
    for width in (640, 1200):
        image = original.convert('RGB')
        image.thumbnail((width, width))
        image.save(folder / f'{args.slug}-{width}.webp', 'WEBP', quality=82, method=6)
    manifest[args.slug] = {
        'src': f'/assets/img/articles/{args.slug}-1200.webp',
        'small': f'/assets/img/articles/{args.slug}-640.webp',
        'width': image.width, 'height': image.height, 'alt': args.alt,
        'credit': 'AI-generated editorial illustration; not a product screenshot.',
        'prompt': args.prompt,
    }
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
print(f'Imported cover for {args.slug}')
