# Domain Docs

How engineering skills should consume this repo's domain documentation.

## Before exploring, read these

- `CONTEXT.md` at the repo root.
- `docs/adr/` for decisions touching the area being changed.

## Layout

This is a single-context repo:

```
/
├── CONTEXT.md
├── docs/adr/
└── alarm_app source modules
```

## Use the glossary vocabulary

When output names a domain concept in a PRD, issue, test, or implementation plan, use the term as defined in `CONTEXT.md`.

## Flag ADR conflicts

If output contradicts an existing ADR, surface it explicitly rather than silently overriding it.
