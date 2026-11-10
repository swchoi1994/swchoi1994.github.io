# Seongwoo Choi / Journal design system

## Design read

A quiet utility layout for a personal technology journal: a neutral canvas, white bordered cards, a sidebar for navigation, and text that does the work. It should read as one engineer's notebook, not a content farm and not a startup landing page. The portfolio at `/portfolio/` keeps its own earlier editorial style and stylesheet.

## What keeps it from looking generated

- Lists and cards are text-first. AI cover illustrations are not shown in cards or, by default, in articles; they are kept for social previews only (`article_cover` in `content/site.json` turns the in-article cover back on).
- Dates, read times and counts are set in a monospace face, in ISO form, like a log.
- Every article shows a real byline, its sources by name, and the Korean original.
- Personal details (mood, music, comments) appear only when the owner has actually entered or enabled them. Nothing personal is ever generated.
- No gradients, emoji, icon-card rows, decorative status dots or placeholder content.

## Color roles

Defined once as custom properties in `assets/css/journal.css`, for light and dark.

| Role | Light | Dark |
| --- | --- | --- |
| Canvas `--bg` | `#F4F5F7` | `#15171B` |
| Surface `--surface` | `#FFFFFF` | `#1C1F25` |
| Soft panel `--soft` | `#F6F7F9` | `#22262D` |
| Inset / selected `--inset` | `#EEF0F4` | `#272B33` |
| Border `--border` | `#E3E5EA` | `#2E333D` |
| Hairline `--line` | `#ECEEF2` | `#272B33` |
| Headings `--ink` | `#16181D` | `#ECEEF2` |
| Body `--text` | `#2B2F38` | `#D0D4DC` |
| Secondary `--sub` | `#4A505C` | `#B4BAC5` |
| Muted `--muted` | `#5C6370` | `#9AA2AF` |
| Accent `--accent` | `#A64B2A` | `#E0916F` |

One accent only (terracotta), used for links, the brand mark, the summary label and primary buttons. Muted text keeps at least 4.5:1 on every surface it sits on. Dark mode is deliberately not pure black and body text is not pure white.

Dark mode follows the reader's system setting until they use the toggle; the choice is stored in `localStorage` and applied by an inline script before first paint.

## Typography

- Interface and reading: Inter, 400 to 700.
- Metadata (dates, read time, counts, labels): JetBrains Mono, 400 to 500.
- Page title 28px/1.2, article title up to 30px/1.25, section heading 17px, card title 16px, article body 17px/1.7 with a measure near 70 characters.
- Sentence case everywhere. Hyphens, not em dashes, in interface copy.

## Layout

- Desktop (1024px and up): a 248px sticky sidebar (brand, author, Read, Topics with counts, Elsewhere) and a content column up to 1040px. Articles use a 720px column with a 300px rail for the contents list and the author.
- 1500px and up: listing pages may show an ad rail in the otherwise empty right margin.
- Below 1024px: a 56px top bar with the theme and menu buttons, a scrolling row of topic tabs on listing pages, and the sidebar as a full-height sheet. The article becomes full-bleed.
- 16px side gutters on phones. No horizontal page scroll at any width; wide tables scroll inside their own box.
- Touch targets are at least 44px.

## Components

- **Post**: label, title, description, date and read time. The same markup is a card in the grid and a row in the list; the Cards/List toggle is remembered.
- **Search**: one rounded field with a magnifier, no button. It lifts on hover and focus.
- **Article**: title, byline, optional mood and music line, an "At a glance" summary, the body, named sources, then "Keep reading".
- **Ads**: fixed slots sit at the edges only: the right rail, after the article ends, between home sections and above the footer. Never above the title, inside a paragraph or list, or between a heading and its text. A slot renders only when its ad unit ID is set.
- **Ad blocker notice**: a dismissible request. It never blocks reading and stays away for a week once dismissed.

## Interaction

- Motion is limited to hover, focus and the search field's shadow. `prefers-reduced-motion` is respected.
- Every control is a real `button`, `a` or `input` with a visible focus ring.
- YouTube players and comments load only when the reader asks for them.

## Avoid

- A second accent colour, gradients, glass effects, drop shadows on cards.
- Cover images in lists; stock or generated imagery as decoration.
- Fake metrics, fake comments, placeholder posts, dead links.
- Third-party scripts beyond the owner-authorised analytics, AdSense and, when enabled, giscus.
