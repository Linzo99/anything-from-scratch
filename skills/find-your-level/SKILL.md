---
name: find-your-level
version: 2.0.0
description: >
  Interactive placement quiz for any course on the platform. Reads the course
  structure from data.json and generates questions from the actual lesson content
  to map the learner to the right starting phase.
  Trigger phrases: "where should I start", "find my level", "what do I know",
  "which phase", "assess my knowledge", "placement test", "skip ahead"
tags: [assessment, onboarding, placement]
---

# Find Your Level

You are administering a placement quiz to help the learner skip phases they already know and land at the right entry point in a course.

## Step 1: Choose a Course

Read `site/data.js` (or scan `site/courses/*/data.json`) to list all available courses.

If only one course exists, use it. If multiple exist and none was specified, ask the learner which course they want assessed.

## Step 2: Understand the Course Structure

Read `site/courses/<slug>/data.json`. Extract:
- The `phases` array (id, name, status, lessons)
- Total number of complete phases

Divide the complete phases into 5 evenly spaced knowledge bands (early → late). Each band will map to a round of questions. If the course has fewer than 5 complete phases, use one round per phase instead.

Example for a 10-phase course: bands at phases 0-1, 2-3, 4-5, 6-7, 8-9.

## Step 3: Sample Lesson Content

For each band, pick one representative phase. Read 1–2 `docs/en.md` files from that phase to understand what concepts are taught there.

File path pattern:
`site/courses/<slug>/phases/<phase-slug>/<lesson-slug>/docs/en.md`

(Split `lesson.path` on `/`: segment1=course-slug, segment2=phase-slug, segment3=lesson-slug.)

Use this content to write the questions — grounded in what the course actually teaches, not general knowledge.

## Step 4: Build the Quiz

Generate 10 questions — 2 per band, covering concepts introduced in that band's phase content.

**Round structure:**
- Round 1 → earliest phases (foundational concepts)
- Round 2 → early-mid phases
- Round 3 → mid phases
- Round 4 → mid-late phases
- Round 5 → advanced/final phases

Each question must:
- Have 3–4 answer options (A, B, C, optionally D)
- Have exactly one correct answer
- Be answerable by someone who completed that phase's lessons
- Use plausible wrong options — no joke answers

## Step 5: Administer the Quiz

Greet the learner briefly (one line), then start Round 1.

Use **AskUserQuestion** for every question. After each round (2 questions), show the round score before continuing. Keep commentary short.

Do not reveal correct answers until all 5 rounds are complete.

## Step 6: Score and Map to Entry Phase

After all 10 questions, show the breakdown:

```
[Band 1 name]:    X/2
[Band 2 name]:    X/2
[Band 3 name]:    X/2
[Band 4 name]:    X/2
[Band 5 name]:    X/2
----------------------------
Total:            X/10
```

Map the total score to an entry phase using this logic:
- Divide the complete phases into 5 equal buckets
- Score 0–1 → start at phase 0
- Score 2–3 → start at bucket 1 start
- Score 4–5 → start at bucket 2 start
- Score 6–7 → start at bucket 3 start
- Score 8–9 → start at bucket 4 start
- Score 10 → start at the final phase (or congratulate if already at the end)

If a learner scored 1/2 in a band they would otherwise skip, mark that phase range as "Review" instead of "Skip".

## Step 7: Personalized Learning Path

Generate a table of all complete phases:

```markdown
| Phase | Name | Status | 
|-------|------|--------|
| 0 | Foundations | Skip |
| 1 | [name] | Review |
| 2 | [name] | Do |
...
```

- **Skip**: learner demonstrated knowledge of this band
- **Review**: learner got 1/2 in this band — worth skimming
- **Do**: start here or beyond

End with one sentence: "Your entry point: Phase [N] — [name]. Start there and work forward."

Then add a brief note on their weakest area (lowest-scoring round) to address first.

## Rules

- Questions must come from actual lesson docs, not general subject knowledge.
- Never hardcode phases — always derive them from `data.json`.
- Keep all questions concise (1–2 sentences).
- Do not reveal answers mid-quiz.
