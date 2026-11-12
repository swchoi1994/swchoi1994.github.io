# Writing guide

For whoever writes a post for this journal: the owner, OpenClaw, or any other writer. It covers how a draft gets onto the site, what the build refuses, and how to keep a post from reading as machine-made.

## 1. How a post gets onto the site

1. Write one file, `content/posts/<slug>.html`. The file name becomes the address: `/blog/posts/<slug>/`.
2. Run the checks in section 5.
3. Open a pull request into `main`. One post per pull request. Never merge it yourself; the owner publishes by merging.

The file is a block of settings followed by the body as plain HTML. The full reference, with the pictures, diagrams and terminal figures you can use, is in `README.md` under "Articles written in this repository". The shortest valid file:

```html
<!--
{
  "title": "At most 60 characters",
  "description": "At most 160 characters, shown under the title and in search results",
  "date": "2026-11-12T09:00:00+00:00",
  "topic": "ai-automation",
  "checked": {"level": "read", "line": "Written from the vendor's documentation. Nothing was run."},
  "note": "The longer account of what was checked and what was not.",
  "sources": [
    {"title": "Name of the page", "url": "https://..."},
    {"title": "Name of a second page", "url": "https://..."}
  ]
}
-->
<p>The opening paragraph.</p>
<h2 id="first">A heading</h2>
<p>…</p>
```

Do not put drafts under `blog/`. That folder is filled by the sync from the Korean blog and is overwritten.

## 2. What the build refuses

The build stops, and the pull request cannot go ahead, when a post has:

- a title over 60 characters or a description over 160;
- fewer than two `https` sources, or fewer than three `<h2 id="…">` sections;
- no `note`, or no `checked` line;
- a `topic` that is not one of the journal's five;
- for a product release, no source on the company's own website.

## 3. Say what was tested

`checked` is one sentence shown directly under the summary, with a label.

| `level` | Label shown | Use it when |
| --- | --- | --- |
| `tested` | Tested | Everything shown was run, by you or by the owner |
| `partly` | Partly tested | Some of it was run; the line says which part |
| `read` | Not tested | It was written from documents; nothing was run |

Never round up. A post that says "Not tested" and is accurate is worth more to the journal than one that implies a test that did not happen.

The same goes for everything else on the page:

- Every number and every factual claim comes from a source you read and listed. A page that points to an announcement is not the source; the announcement is.
- A company's results for its own product are its claims. Write "Qualcomm says", not "is".
- Terminal output, error messages, quotations and screenshots are real or they are left out. A worked example with made-up inputs says the inputs are made up.
- If you could not read a source, do not use what you believe it says.

## 4. Writing that reads like a person wrote it

The journal has a problem to fix: many of its posts look alike. Titles follow one formula, every post has the same skeleton, and nothing in them could only have come from the owner. These rules are the repair.

**Start from material, not from a topic.** The best input is something the owner did or saw: output from his own servers, a mistake that cost him an afternoon, a number he measured, an opinion he holds. If the brief contains none of that, ask for it before writing. A post built only from public documents will read like every other page built from the same documents.

**Use the first person only for what the owner did.** "I ran this on two A100s and the first load took four minutes" is good when it is true. Do not invent experience.

**Let the subject decide the shape.** A comparison wants a table. A story wants paragraphs in order. A procedure wants numbered steps. Do not give every post the same numbered sections, the same closing table and the same summary.

**Habits to avoid.** These mark text as generated, whichever model wrote it:

- A title in the form "Topic: what to check first", or any single template used across posts.
- Opening with a definition of the subject, or with a sentence about how fast the field moves.
- Lists of exactly three by reflex, and paragraphs that end on a short quotable line.
- Setting up a point with a colon or a question and then answering it.
- "Not X, but Y" when nobody suggested X.
- Words that sell instead of say: powerful, seamless, robust, game-changing, unlock, dive in.
- Hedges stacked on every claim, and a closing section that repeats the post.
- Bold scattered through paragraphs.

**Prefer** the specific word, the real number with its unit, a full sentence over a fragment, and the detail a reader could not have guessed.

**Pictures.** No generated illustrations. Use a diagram that explains something, real terminal output, or a photograph or screenshot the owner supplied.

## 5. Checks before the pull request

```bash
python3 tools/publish.py
python3 -m unittest discover -s tools -p 'test_*.py'
```

Then add the new address to the list in `tools/browser-smoke.cjs`, serve `_site` on port 8791 (`python3 -m http.server 8791 --bind 127.0.0.1 --directory _site`) and run `node tools/browser-smoke.cjs`. Open every address in `sources` once and fix any that does not show the page. Refresh the checked-in preview with `cp _site/index.html index.html`.

In the pull request, say what the post claims, which sources you read, and what you did not verify.

## 6. How often

At most three new posts in any seven days. A day with thirty new posts tells every visitor how they were made. If a post has nothing in it that a reader could not get from the original announcement, it does not need to exist.
