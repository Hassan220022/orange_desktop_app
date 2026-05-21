# Issue tracker: Local markdown

PRDs and implementation issues for this repo live as markdown files under `.scratch/`.

## Conventions

- PRDs live under `.scratch/prds/`.
- Issues live under `.scratch/issues/<feature-slug>/`.
- Use dependency-ordered filenames like `001-title.md`, `002-title.md`.
- When a skill says "publish to the issue tracker", create or update local markdown files in those folders.
- When a skill says "apply a triage label", write the label in frontmatter or near the top of the issue body.

## Why local markdown

This repo has a GitHub remote, but agent planning should not silently create remote GitHub issues without an explicit user request.
