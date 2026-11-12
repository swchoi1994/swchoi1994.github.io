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
- On phones: page title 24px, article title 25px, card title 16px, article body 17px/1.7. On desktop these scale with the window; at 1540px the article body is about 20px/1.75. Headings inside an article are sized in `em`, so they scale with the body text.
- Sentence case everywhere. Hyphens, not em dashes, in interface copy.

## Layout

Widths are shares of the screen, not fixed pixels, so the layout fills any window.

- Desktop (1024px and up): the sidebar takes 16% of the width (never less than 210px, so its labels fit) and the content takes the rest, with 2.6% side padding. On article pages the right rail takes 24% of the content area. Card grids use a fixed number of equal columns: three, or four from 1800px.
- Text grows with the window as well. Sizes mix `rem` and `vw` inside `clamp()`, which keeps a line of article text between about 60 and 90 characters at any width and still follows the reader's own font-size setting. Paragraphs are capped at 88 characters as a safety net.
- The footer is one quiet row under both columns, pinned to the bottom of the window on short pages. The sidebar column is painted on the page canvas so it always reaches the bottom, including under an anchor ad.
- Below 1100px the article rail moves under the article. Below 1024px: a 56px top bar with the theme and menu buttons, a scrolling row of topic tabs on listing pages, and the sidebar as a full-height sheet. The article becomes full-bleed.
- 16px side gutters on phones. No horizontal page scroll at any width; tables scroll inside their own box.
- Touch targets are at least 44px.

## Components

- **Post**: label, title, description, date and read time. The same markup is a card in the grid and a row in the list; the Cards/List toggle is remembered.
- **Search**: one rounded field with a magnifier, no button. It lifts on hover and focus.
- **Article**: title, byline, optional mood and music line, an "At a glance" summary, the body, named sources, then "Keep reading".
- **Ads**: fixed slots sit at the edges only: the right rail, after the article ends, between home sections and above the footer. Never above the title, inside a paragraph or list, or between a heading and its text. A slot renders only when its ad unit ID is set.
- **Ad blocker wall**: the owner's choice (`adblock_wall`). When ads are blocked, the page is blurred behind one centred card that explains why, gives three steps, and has a reload button and a contact link. With the setting off, a dismissible notice is shown instead. Pages without ads never show either.
- **Share and follow**: one row of plain link buttons after each article. No third-party share scripts.

## Interaction

- Motion is limited to hover, focus and the search field's shadow. `prefers-reduced-motion` is respected.
- Every control is a real `button`, `a` or `input` with a visible focus ring.
- YouTube players and comments load only when the reader asks for them.

## Avoid

- A second accent colour, gradients, glass effects, drop shadows on cards.
- Cover images in lists; stock or generated imagery as decoration.
- Fake metrics, fake comments, placeholder posts, dead links.
- Third-party scripts beyond the owner-authorised analytics, AdSense and, when enabled, giscus.
