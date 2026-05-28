# Skills

Claude Code skills for working with this repo. Invoke them with `/skill-name` inside a Claude Code session.

## Available skills

### `/generate-course`
Generates a complete course from scratch — `data.json`, every `docs/en.md`, every `quiz.json`, `prereqs`, and `tierOrder` — then rebuilds `site/data.js`.

```
/generate-course Generate a "Python from Scratch" course. Slug: python, repo: yourname/python-from-scratch
```

### `/find-your-level`
Interactive quiz that helps a learner identify where they should start in a course based on their existing knowledge.

### `/check-understanding`
Checks a learner's understanding of the current lesson by asking targeted questions and giving feedback.

---

## Installing skills

Skills live in `.claude/skills/` where Claude Code can find them. Copy any skill you want to use:

```bash
cp -r skills/<skill-name> .claude/skills/
```

Or copy all of them at once:

```bash
cp -r skills/. .claude/skills/
```
