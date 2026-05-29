---
name: check-understanding
version: 2.0.0
description: Phase quiz for any course on the platform. Trigger with "quiz me", "test phase", "check my understanding", "do I know phase 3", or `/check-understanding [course] [phase]`.
---

# Check Understanding

Test your knowledge of a completed phase from any course on this platform.

## Activation

This skill activates when the user says things like:
- `/check-understanding` (no args — will guide them)
- `/check-understanding 3` or `/check-understanding deep-learning`
- `/check-understanding networking 2`
- "quiz me on phase 2"
- "test phase 1"
- "check my understanding of transformers"
- "do I know phase 3"
- "am I ready for the next phase"

## Input

Accepts an optional course slug and/or phase number/name as arguments. Examples:
- `/check-understanding` — ask which course, then which phase
- `/check-understanding 3` — ask which course, then use phase 3
- `/check-understanding networking 2` — use networking course, phase 2
- `/check-understanding ai-engineering nlp` — use ai-engineering course, resolve "nlp" to the matching phase

## Procedure

### Step 1: Discover Available Courses

Read `site/data.js` (or scan `site/courses/*/data.json`) to get the list of all available courses. Extract each course's `slug` and `title`.

If only one course exists, use it automatically. If multiple exist and no course was specified in the argument, ask the user which course they want to be quizzed on.

### Step 2: Load the Course

Read `site/courses/<slug>/data.json` for the selected course. Extract the `phases` array — each phase has:
- `id` (integer)
- `name` (string)
- `status` ("complete" | "in-progress" | "planned")
- `lessons` array (each has `path`, `name`, `status`)

Build the phase list dynamically from this data. Do NOT rely on any hardcoded phase map.

### Step 3: Resolve the Phase

Parse the phase argument (if any). Try to match it against:
1. An integer → match by `phase.id`
2. A string → match by checking if any phase `name` contains the keyword (case-insensitive), or if the slug of the phase directory contains the keyword

If no match is found, tell the user: "Unknown phase '[keyword]'. Pick from the list below:" and show all phases with their id and name.

If no phase argument was given, ask the user to pick from the full list.

Only quiz on phases with `status: "complete"`. If the user picks an `"in-progress"` or `"planned"` phase, tell them: "Phase [N] — [name] doesn't have complete content yet. Pick a completed phase."

### Step 4: Find Lesson Content

The path for each lesson is stored in `lesson.path` inside `data.json`, in the format:
`phases/<course-slug>/<phase-slug>/<lesson-slug>`

The actual file is at:
`site/courses/<course-slug>/<phase-slug>/<lesson-slug>/docs/en.md`

Wait — the path already includes the course slug as the second segment. So split on `/`:
- segment 0: `phases`
- segment 1: course slug
- segment 2: phase slug
- segment 3: lesson slug

The file path is: `site/courses/<segment1>/phases/<segment2>/<segment3>/docs/en.md`

Use Glob to find all `docs/en.md` files under the resolved phase directory. For each, read the file. These are the teaching materials you will generate questions from.

If a phase has many lessons (10+), read a representative spread: first 2, a middle sample, and last 2.

If no `en.md` files are found for the selected phase, tell the user: "Phase [N] — [name] doesn't have lesson content written yet. Pick another phase."

### Step 5: Generate 8 Questions

Create exactly 8 multiple-choice questions drawn from the lesson content you just read:

**Questions 1–4: Conceptual (What/Why)**
These test understanding of ideas, definitions, and reasoning. Examples:
- "What is the purpose of X?"
- "Why does Y happen when Z?"
- "Which statement best describes the relationship between A and B?"

**Questions 5–8: Practical (How/Build)**
These test applied knowledge and implementation awareness. Examples:
- "How would you implement X?"
- "Which approach correctly solves Y?"
- "What is the correct order of steps to build Z?"

Each question must have 3 or 4 answer options labeled A, B, C (and optionally D). Exactly one option is correct. Wrong options should be plausible but clearly incorrect to someone who studied the material.

Tag each question with the specific lesson it draws from (e.g., "Lesson 03: Variables & Types").

### Step 6: Present Questions One at a Time

Use the AskUserQuestion tool to present each question individually. Format:

```
Question 1/8 (Conceptual) — from Lesson 02: [lesson name]

[Question text]

A) ...
B) ...
C) ...
D) ...
```

Wait for the user's answer before moving to the next question. Do not reveal the correct answer until after the user responds.

### Step 7: Track and Score

Keep a running tally:
- Total correct out of 8
- For each wrong answer: the question number, user's answer, correct answer, lesson it came from

### Step 8: Show Results

After all 8 questions, display the score and grade:

**7–8 correct: Mastered**
"You have a strong grasp of Phase [N] — [name]. You are ready to move on to Phase [N+1]: [next phase name]."
If this was the final phase: "You have mastered the final phase. Congratulations on completing the entire course."

**5–6 correct: Almost**
"Solid foundation. Review these specific areas before moving on:"
List the lessons tied to the missed questions.

**3–4 correct: Developing**
"You are building understanding but need to revisit some lessons:"
List each missed question with the lesson to re-read.

**0–2 correct: Start Over**
"This phase needs more time. Work through the lessons again, focusing on:"
List all missed topics.

### Step 9: Wrong Answer Breakdown

For every question the user got wrong, show:

```
Question N: [question text, abbreviated]
Your answer: B
Correct answer: C — [the correct option text]
Why: [1–2 sentence explanation]
Review: Lesson [NN] — [lesson name]
```

### Step 10: What Next?

End by offering three choices:

1. **Retake this quiz** — generate a fresh set of 8 questions from the same phase
2. **Try another phase** — pick a different phase from the same course
3. **Switch course** — quiz on a phase from a different course

Wait for the user's choice and act accordingly. On retake, avoid repeating the same questions — rephrase or draw from different parts of the lesson docs.

## Rules

- Build the phase list from `data.json` every time. Never hardcode phases.
- Questions must be grounded in the actual lesson docs, not general knowledge about the subject.
- Do not show the correct answer until after the user responds.
- Keep question text concise — one or two sentences max.
- Wrong options must be plausible. No joke answers.
- On retakes, vary the questions. Once the pool is exhausted, rephrase rather than repeat verbatim.
