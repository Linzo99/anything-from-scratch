# AFS — Anything from Scratch

A static, self-hostable learning platform for building "from scratch" courses on any subject. Each course has full lesson content, per-lesson quizzes, a progress tracker, an interactive roadmap, and a glossary — all running with zero backend.

Fork it, generate a course with one command, and have a fully working learning site in minutes.

Built on top of the original **[AI Engineering from Scratch](https://github.com/rohitg00/ai-engineering-from-scratch)** curriculum by [@rohitg00](https://github.com/rohitg00), which this repo forks and extends into a multi-course platform.

---

## What's included

| Course | Phases | Lessons |
|---|---|---|
| AI Engineering from Scratch | 20 | 468 |
| Networking Basics from Scratch | 9 | 47 |
| System Design from Scratch | 9 | 44 |

More courses can be added in minutes with the `/generate-course` skill (see below).

---

## How it works

All content lives under `site/courses/<slug>/`:

```
site/
  courses/
    ai-engineering/
      data.json              ← course metadata, phases, lessons, glossary
      phases/
        00-setup-and-tooling/
          01-dev-environment/
            docs/en.md       ← lesson content (markdown)
            quiz.json        ← pre + post quiz questions
    networking/
      data.json
      phases/
        ...
  combine.js                 ← build step: merges all data.json → data.js
  data.js                    ← generated; loaded by every page
  course.js                  ← runtime course resolver (?course=<slug>)
  lesson.html                ← single-page lesson viewer
  prereqs.html               ← per-course dependency roadmap (SVG)
  catalog.html               ← lesson browser across all courses
  glossary.html              ← searchable glossary
  style.css
```

The only build step is:

```bash
node site/combine.js
```

This reads every `courses/<slug>/data.json` and writes `site/data.js`, which all HTML pages load as a `<script>`. No bundler, no framework, no server required.

### Serving locally

```bash
cd site && python3 -m http.server 4000
```

### Course switching

The active course is resolved from `?course=<slug>` in the URL. The first course alphabetically is the default (no param needed). A `<select>` is injected into the navbar automatically when more than one course exists.

---

## Adding a new course

The repo includes a Claude Code skill that generates a complete course — `data.json`, every `docs/en.md`, every `quiz.json`, `prereqs`, `tierOrder` — in one shot.

Invoke it from Claude Code:

```
/generate-course Generate a "Python from Scratch" course. Slug: python, repo: user/python-from-scratch
```

The skill will:
1. Write `site/courses/python/data.json` with the full phase + lesson structure
2. Write a `docs/en.md` and `quiz.json` for every lesson
3. Run `node site/combine.js` to register the course

The course appears in the navbar selector immediately.

### Manual course structure

If you prefer to write the course yourself, create `site/courses/<slug>/data.json` following this shape:

```jsonc
{
  "slug": "python",
  "title": "Python from Scratch",
  "tagline": "47 lessons. 9 phases.",
  "description": "Learn Python by writing real programs from day one.",
  "githubRepo": "user/python-from-scratch",
  "githubBranch": "main",
  "contentHost": "local",       // "local" = serve from /courses/<slug>/phases/
  "phases": [...],
  "glossary": [...],
  "artifacts": [],
  "prereqs": { "0": [], "1": [0], ... },   // drives the /roadmap dependency graph
  "tierOrder": [[0], [1], [2], ...]        // controls roadmap row layout
}
```

Then run `node site/combine.js`.

---

## Features

- **Lesson pages** — markdown rendered client-side, syntax-highlighted code blocks, mermaid diagrams, TOC, scroll progress
- **Per-lesson quizzes** — pre/post questions with explanations, progress persisted in localStorage
- **Sidebar navigation** — phase + lesson list, active lesson highlighted, prev/next buttons
- **Roadmap** (`/prereqs.html`) — SVG dependency graph generated from `prereqs`/`tierOrder` in each course's `data.json`
- **Catalog** (`/catalog.html`) — filterable lesson browser across phases and types
- **Glossary** (`/glossary.html`) — searchable "what people say / what it means" definitions
- **Dark mode** — system preference + manual toggle, persisted
- **Command palette** — `⌘K` search across lessons and glossary terms
- **Zero backend** — everything runs from flat files; deploy to Vercel, Netlify, GitHub Pages, or any static host

---

## Deploying

The repo includes a `vercel.json`. Push to Vercel and it builds automatically:

```json
{
  "buildCommand": "node site/combine.js",
  "outputDirectory": "site"
}
```

For other hosts, run `node site/combine.js` as your build command and serve the `site/` directory.

---

## Contributing

This repo is a template. Fork it, generate your own courses, host your own site. Pull requests are accepted for **site bug fixes only** — if something in the lesson viewer, sidebar, roadmap, or catalog is broken. See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Credits

The AI Engineering from Scratch course content and site foundation are from the original repo by **[@rohitg00](https://github.com/rohitg00)**:

> **[github.com/rohitg00/ai-engineering-from-scratch](https://github.com/rohitg00/ai-engineering-from-scratch)**

This fork extends that work into a multi-course platform. All original content remains MIT licensed.

---

## License

MIT
