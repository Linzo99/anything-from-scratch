---
description: Generate a complete course for the multi-course site. Given a subject and description, produces courses/<slug>/data.json, all lesson content files (docs/en.md + quiz.json), and rebuilds data.js.
---

# generate-course

You are generating a self-contained course entry for a multi-course learning site. **Always write lesson content files** — a course with no `docs/en.md` files is incomplete.

## What you must produce

A directory: `site/courses/<slug>/` containing:

| File | Required | Description |
|---|---|---|
| `data.json` | ✅ | Course metadata, phases, lessons, glossary |
| `phases/<phase-slug>/<lesson-slug>/docs/en.md` | ✅ | Full lesson content for every lesson |
| `phases/<phase-slug>/<lesson-slug>/quiz.json` | ✅ | Quiz questions for every lesson |

After writing all files, run:
```bash
node site/combine.js
```

### Reference structure

```
site/courses/
  ai-engineering/          ← reference course
    data.json
    phases/
      00-setup-and-tooling/
        01-dev-environment/
          docs/en.md        ← full lesson content
          quiz.json         ← pre/post quiz questions
          code/             ← optional starter code
  <new-slug>/
    data.json
    phases/
      00-foundations/
        01-first-lesson/
          docs/en.md
          quiz.json
```

## Input you need from the user

| Field | Required | Example |
|---|---|---|
| Subject / title | ✅ | "Python from Scratch" |
| Slug (URL-safe) | ✅ | `python` |
| GitHub repo | ✅ | `user/python-from-scratch` |
| GitHub branch | optional | `main` (default) |
| Tagline | optional | auto-generate from subject |
| Description | optional | auto-generate |

## data.json schema

Follow this schema exactly. Use `site/courses/ai-engineering/data.json` as the canonical reference.

```jsonc
{
  "slug": "python",
  "title": "Python from Scratch",
  "tagline": "N lessons. N phases. ...",          // one sentence, include counts
  "description": "...",                           // 1-2 sentences, no buzzwords
  "githubRepo": "user/repo",
  "githubBranch": "main",
  "contentHost": "local",                         // ALWAYS "local" — you are writing the files
  "phases": [ /* see Phase schema below */ ],
  "glossary": [ /* see Glossary schema below */ ],
  "artifacts": [],
  "prereqs": {                                    // ✅ REQUIRED — drives the /roadmap graph
    "0": [],
    "1": [0],
    "2": [1]
    // one entry per phase id; value is array of phase ids this phase depends on
  },
  "tierOrder": [                                  // ✅ REQUIRED — controls roadmap row layout
    [0],
    [1],
    [2]
    // each sub-array is one horizontal row; phases in a row are shown side-by-side
    // phases not listed here auto-append to the bottom row
  ]
}
```

**Always use `"contentHost": "local"`** — you are writing the lesson files. Never use `"github"`.

### prereqs rules
- Every phase id must have an entry (even if `[]`)
- Keys are **strings** (`"0"`, `"1"`…), values are arrays of **integer** phase ids
- Phase 0 always has `[]` (nothing comes before foundations)
- Think about actual knowledge dependencies: does this phase require understanding from another?

### tierOrder rules
- Each sub-array is one horizontal row in the roadmap SVG
- Phases with no prerequisites go in tier 0; phases that depend on them go in the next tier
- Parallel tracks (e.g. DNS and HTTP both depend on Transport) go in the same tier
- The final capstone phase always gets its own last tier

### Phase schema

```jsonc
{
  "id": 0,
  "name": "Foundations",
  "status": "complete",             // "complete" | "in-progress" | "planned"
  "desc": "One sentence about what this phase builds.",
  "lessons": [ /* see Lesson schema */ ]
}
```

### Lesson schema

```jsonc
{
  "name": "Variables & Types",
  "status": "complete",
  "type": "Build",                  // "Build" | "Learn" | "Capstone" | "Project"
  "lang": "Python",
  "url": "https://github.com/<repo>/tree/<branch>/phases/<phase-slug>/<lesson-slug>/",
  "path": "phases/<slug>/<phase-slug>/<lesson-slug>",  // ALWAYS include this
  "summary": "One sentence describing what the student builds or learns.",
  "keywords": "keyword1 · keyword2 · keyword3"
}
```

**Critical path rules:**
- `url` format: `https://github.com/{repo}/tree/{branch}/phases/{phase-slug}/{lesson-slug}/`
- `path` format: `phases/{course-slug}/{phase-slug}/{lesson-slug}`
- Phase slugs: `{id:02d}-{kebab-name}` e.g. `00-foundations`
- Lesson slugs: `{index:02d}-{kebab-name}` e.g. `01-variables-and-types`
- All lessons must have `url` and `path` — no omissions for planned lessons

### Glossary schema

```jsonc
{
  "term": "Decorator",
  "says": "What people call it casually",
  "means": "What it actually is — precise definition, 1-2 sentences."
}
```

---

## docs/en.md schema

Every lesson must have a `docs/en.md`. Use this structure:

```markdown
# <Lesson Name>

> <One-line hook — a concrete claim or question that motivates the lesson.>

**Type:** Build | Learn | Capstone
**Languages:** Python, Bash, etc.
**Prerequisites:** Phase N, Lesson NN — <lesson name>
**Time:** ~XX minutes

## Learning Objectives

- Bullet list of 3-5 concrete, measurable outcomes
- Each starts with an action verb: Implement, Write, Explain, Build, Trace, Measure

## The Problem

2-4 paragraphs explaining WHY this matters and what goes wrong without this knowledge.
Use a concrete scenario. No buzzwords. No vague promises.

## The Concept

Thorough explanation of the underlying concept. Include:
- ASCII diagrams or tables where helpful
- The mental model a student needs
- Common misconceptions called out explicitly

Code blocks to illustrate concepts (not yet the exercise):

```language
# Annotated example showing the idea
```

## Build It

Step-by-step instructions. Each step has:
1. What to do (imperative)
2. The code or command
3. What to observe / verify

Full, runnable code blocks — no ellipsis, no placeholders.
"From scratch" courses must explain every line; never assume prior knowledge.

## Exercises

3-5 numbered exercises ranging from verification (run this, see that) to extension (modify it to do X).

## Key Terms

| Term | What people say | What it actually means |
|------|----------------|------------------------|
| ... | ... | ... |
```

**Quality bar for docs/en.md:**
- No lesson under 400 words
- Every code block is complete and runnable
- "From scratch" = explain every concept as if the reader has never seen it
- Diagrams (ASCII) for anything spatial: packet layouts, state machines, topologies
- No buzzwords: "powerful", "robust", "seamless", "revolutionary"

---

## quiz.json schema

Every lesson must have a `quiz.json`. Use this structure:

```jsonc
{
  "questions": [
    {
      "stage": "pre",          // "pre" = asked before reading, tests prior knowledge
      "question": "...",
      "options": ["A", "B", "C", "D"],
      "correct": 1,            // 0-indexed
      "explanation": "..."     // shown after answering — explain WHY, not just what
    },
    {
      "stage": "pre",
      "question": "...",
      ...
    },
    {
      "stage": "post",         // "post" = asked after reading, tests comprehension
      "question": "...",
      "options": ["A", "B", "C", "D"],
      "correct": 2,
      "explanation": "..."
    },
    ...
  ]
}
```

**Rules:**
- 2 `pre` questions + 3 `post` questions per lesson (5 total)
- `pre` questions test baseline assumptions — wrong answers are common misconceptions
- `post` questions test specific things taught in the lesson
- Every `explanation` teaches, not just confirms: "Correct. TCP uses X because Y."
- Distractors (wrong options) should be plausible — avoid obviously silly options

---

## Content generation guidelines

### Structure
- **8–20 phases** — start with 8 for a new subject, expand later
- **4–8 lessons per phase**
- **Phase 0** is always "Foundations" — tooling, environment, first program
- Final phase is always a Capstone with 3–5 real projects
- Status progression: early phases `complete`, middle `in-progress`, later `planned`
- **Write content for ALL lessons** regardless of status

### Quality bar
- Every lesson name is action-oriented: "Build a ...", "Implement ...", "Write ..."
- Every `summary` is a single concrete sentence
- Every `desc` on a phase is one sentence about the outcome
- Glossary: 20–50 terms
- No marketing language

### Subject-specific guidance
- **Systems/networking**: include packet diagrams, ASCII topology diagrams, explain every header field
- **Systems languages (Rust, C, Zig)**: emphasize memory safety, ownership, low-level concepts
- **ML/AI**: emphasize math-first, implement-before-framework, artifacts
- **Web/full-stack**: emphasize progressive disclosure, real deployable projects
- **Scripting/glue (Python, bash)**: emphasize practical tasks over CS theory

---

## Steps to execute

1. **Clarify** missing inputs (slug, repo at minimum)
2. **Write `data.json`** — full course structure including `prereqs` and `tierOrder`
3. **Write every `docs/en.md`** — thorough lesson content, no placeholders
4. **Write every `quiz.json`** — 2 pre + 3 post questions each
5. **Run** `node site/combine.js`
6. **Verify** console shows correct counts
7. **Report** slug, phase count, lesson count

**Do not skip steps 3 and 4.** A course without content files is broken.
**Do not omit `prereqs` and `tierOrder`.** Without them the `/roadmap` page breaks for this course.

## Example invocation

> Generate a course for "TypeScript from Scratch". Use slug `typescript`, repo `user/typescript-from-scratch`.

You would generate:
- `site/courses/typescript/data.json`
- `site/courses/typescript/phases/00-foundations/01-tooling/docs/en.md`
- `site/courses/typescript/phases/00-foundations/01-tooling/quiz.json`
- ... (one docs/en.md + quiz.json per lesson)
- Run `node site/combine.js`
