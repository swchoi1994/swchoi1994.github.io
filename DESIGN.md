# Seongwoo Choi Portfolio Design System

## Design read

An editorial technical portfolio for an AI systems leader. The site should feel credible, warm, globally minded, and quietly ambitious. It should communicate research depth and product responsibility without looking like a startup template or a visual resume.

## Audience

- Senior technology leaders and founders
- AI research and engineering collaborators
- Investors and startup partners
- Selective recruiters for technical leadership roles

## Visual theme

- Warm paper-like canvas instead of pure white
- Ink-first typography with one terracotta accent
- Editorial hierarchy with large serif display type and precise sans-serif supporting text
- Asymmetric composition and generous whitespace
- Real professional evidence instead of decorative AI imagery

## Color roles

- Canvas: `#F6F4EF`
- Primary surface: `#FFFDF8`
- Muted surface: `#EBE7DE`
- Primary ink: `#1E1F23`
- Secondary ink: `#686862`
- Border: `#D8D4CB`
- Accent: `#A64B2A`
- Accent dark: `#7D321A`
- Accent soft: `#EAD8CE`

Use the accent for links, focus, data highlights, and primary actions. Do not introduce a second accent.

## Typography

- Display: Newsreader, 500 or 600 weight
- Body and interface: DM Sans, 400 through 700
- Headlines use tight tracking and short line lengths
- Body paragraphs stay near 55 to 65 characters per line
- Numbers that communicate metrics use tabular figures
- Sentence case for headings and controls

## Layout

- Maximum content width: 1180px
- Desktop sections use asymmetric 2-column grids
- Section spacing ranges from 88px to 144px
- Mobile side padding: 16px
- Desktop side padding: 24px minimum
- Use full-width tonal bands only for major narrative transitions
- Preserve a clear top-to-bottom reading order at every breakpoint

## Shape and depth

- Base radius: 12px
- Buttons and navigation controls: 8px
- Portrait frame: 18px
- Pills are permitted only for compact capability tags
- Use borders and tonal surfaces before shadows
- Reserve the large warm shadow for the portrait or a single priority element

## Components

### Navigation

- Sticky, translucent warm canvas
- Five primary anchors maximum
- Download CV is a secondary outlined action
- Mobile menu is a solid full-viewport sheet, not transparent over content

### Hero

- Name and role are immediately understandable
- Headline fits within two to three lines on desktop
- One primary and one secondary action
- Candid real portrait, rectangular crop
- No scroll cue, decorative status dot, or technology-logo cloud

### Proof metrics

- A dark ink band provides a confident change in pace
- Metrics are editorial cells, not floating cards
- Every number has specific context

### Selected work

- Each entry states context, responsibility, approach, and outcome
- Use typographic structure instead of screenshots when proprietary work is under NDA
- Avoid generic project-card grids

### Research

- Warm muted surface
- Sticky section introduction on desktop
- White reading panels with restrained spacing and no decorative icons

### Contact

- Email is visible as text and a direct link
- No form unless it connects to a real delivery service
- Professional profile links remain secondary

## Interaction

- Motion is limited to direct hover, press, and menu feedback
- Never hide primary content before a scroll event
- Respect `prefers-reduced-motion`
- Every interactive element has visible keyboard focus
- Touch targets are at least 44px

## Content rules

- Write in plain, specific language
- Prefer evidence and constraints over adjectives
- Do not expose confidential stealth-company details
- Do not publish placeholder projects, posts, or fake success messages
- Keep dates and current roles synchronized with the latest CV
- Use hyphens instead of em dashes

## Avoid

- Purple-blue AI gradients
- Equal icon-card feature rows
- Circular headshots with bright rings
- Fake terminals or dashboards
- Dead links and decorative controls
- Font Awesome or unnecessary UI dependencies
- Scroll-triggered opacity that can leave content blank
- Advertising or unrelated third-party scripts
