# Seongwoo Choi / Journal design system

## Design read

A quiet utility layout for a personal technology journal: a neutral canvas, white bordered cards, a sidebar for navigation, and text that does the work. It should read as one engineer's notebook, not a content farm and not a startup landing page. The portfolio at `/portfolio/` keeps its own earlier editorial style and stylesheet.

## What keeps it from looking generated

- Pictures explain or identify; they do not decorate. A card carries the article's illustration, labelled as AI-generated inside the article, or a drawn motif when there is none. Articles written here use diagrams built from real figures and terminal blocks that show real output. Both `card_covers` and `article_cover` in `content/site.json` can switch the illustrations off.
- Dates, read times and counts are set in a monospace face, in ISO form, like a log.
- Every article shows a real byline, its sources by name, and the Korean original.
- Personal details (mood, music, comments) appear only when the owner has actually entered or enabled them. Nothing personal is ever generated.
- No gradients, emoji, icon-card rows, decorative status dots or placeholder content.
- Colour carries meaning: blue is something to click, green is a label. Nothing is coloured for decoration.

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
| Link and action `--link` | `#0B57D0` | `#8AB4F8` |
| Text on a filled button `--on-link` | `#FFFFFF` | `#0B1B33` |
| Selected item `--tint` | `#E8F0FE` | `#1F2A3D` |
| Label `--accent` | `#137333` | `#81C995` |
| Warning `--warn` on `--warn-tint` | `#8A5300` on `#FDF2D8` | `#F2C26B` on `#33290F` |

Two colours, used the way a search result uses them. Blue is for anything you can click: article titles, links in text, primary buttons, the selected item in the sidebar (blue text on the tint). Green is for labels: the topic above a title, page eyebrows, "At a glance", the series part line and the second half of the brand mark. Body text, cards and code stay neutral. All four colours keep at least 4.5:1 against every surface they sit on, in both themes; a true cyan was tested and rejected because it reaches only 2.3:1 on white. Dark mode is deliberately not pure black and body text is not pure white.

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
- **Card picture**: 16:9 at the top of a card, hidden in the list view. Illustrations load lazily; motifs are inline drawings in the theme's colours, so they change with dark mode.
- **Callout**: a tinted box with a coloured left edge and a small label. Blue for a tip, amber for a warning, green for a rule of thumb. Amber appears nowhere else.
- **Diagram**: boxes, arrows and proportional bars built from HTML, on the soft panel colour, always with a caption. Bars that claim to be to scale are to scale.
- **Terminal**: a dark window, in both themes, for output copied from a real run.
- **Series**: an article in a series carries a collapsed box under its summary (part N of M, every part listed, the current one marked) and previous/next links where it ends. The home page shows each series as one wide card: what it is on the left, the parts in order on the right.
- **Project facts**: two lines under the summary, "You need" and "You end up with", repeated on the projects page.
- **Ads**: fixed slots sit at the edges only: the right rail, after the article ends, between home sections and above the footer. Never above the title, inside a paragraph or list, or between a heading and its text. A slot renders only when its ad unit ID is set.
- **Ad blocker wall**: the owner's choice (`adblock_wall`). When ads are blocked, the page is blurred behind one centred card that explains why, gives three steps, and has a reload button and a contact link. With the setting off, a dismissible notice is shown instead. Pages without ads never show either.
- **Share and follow**: one row of plain link buttons after each article. No third-party share scripts.

## Interaction

- Motion is limited to hover, focus and the search field's shadow. `prefers-reduced-motion` is respected.
- Every control is a real `button`, `a` or `input` with a visible focus ring.
- YouTube players and comments load only when the reader asks for them.

## Avoid

- A colour without a job, gradients, glass effects, drop shadows on cards. Do not borrow another company's multi-colour logo treatment.
- Stock imagery, and pictures that are only decoration. Invented terminal output or charts.
- Fake metrics, fake comments, placeholder posts, dead links.
- Third-party scripts beyond the owner-authorised analytics, AdSense and, when enabled, giscus.
