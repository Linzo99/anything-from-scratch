# Contributing

This repo is a **template** — the intended use is to fork it and generate your own courses with the `/generate-course` skill. It is not a community-contributed curriculum.

Pull requests are accepted for **site bug fixes only**:

- Something renders wrong in the lesson viewer, sidebar, roadmap, catalog, or glossary
- A broken link or 404 in the site shell (not lesson content)
- A bug in `combine.js` or `course.js`

## To report a bug

Open an issue with the bug report template. Include the URL, what you expected, and what you saw.

## To fix a bug

1. Fork the repo
2. Fix it
3. Run `cd site && python3 -m http.server 4000` and verify the fix
4. Open a PR — one fix per PR, short description

## To add your own courses

Fork the repo and use the Claude Code skill:

```
/generate-course Generate a "Python from Scratch" course. Slug: python, repo: yourname/python-from-scratch
```

That is not something to PR back here — it belongs in your fork.
