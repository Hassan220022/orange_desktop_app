# PRD: Chatbot UI Improvements

**Status:** ready-for-agent
**Date:** 2026-06-03
**Source:** Deep UI analysis of `ui/panels/chat_panel.py`

---

## Problem Statement

The `ChatPanel` (Copilot-style assistant embedded in the Alarm Viewer) has strong architectural bones — non-blocking threads, rich tool-result widgets, conversation summarisation — but suffers from 17 concrete UX and code quality issues that degrade the experience:

| #   | Category                                                                   | Severity |
| --- | -------------------------------------------------------------------------- | -------- |
| 1   | No thinking indicator inside chat history                                  | P1       |
| 2   | No Stop/Cancel button during generation                                    | P1       |
| 3   | Char-limit label (4000) is cosmetic — not enforced                         | P1       |
| 4   | Empty state: blank scroll area when chat has no messages                   | P1       |
| 5   | Error bubbles have no Retry action                                         | P2       |
| 6   | Timestamps stored in messages but lost on rehydration                      | P2       |
| 7   | "API key missing" status is 11px text; no in-chat CTA                      | P2       |
| 8   | `text-transform: uppercase` in QSS has no effect in Qt                     | P2       |
| 9   | Model selector row occupies full header line in narrow panel               | P3       |
| 10  | Markdown headings (##, ###) rendered as plain paragraphs                   | P3       |
| 11  | Table border colour `#2a4060` is hard-coded in Python, not themed          | P3       |
| 12  | Copy button shown on system/info messages (visual noise)                   | P3       |
| 13  | History dialog has no search filter                                        | P3       |
| 14  | `tool_section` labels rely on CSS uppercase — must be `.upper()` in Python | P3       |
| 15  | Tool card margin `2px 0px` too tight                                       | P3       |
| 16  | Composer and toolbar backgrounds visually merge                            | P3       |
| 17  | Bubble border-radius same on all corners — no "tail" visual distinction    | P4       |

---

## GPT-5.5 Prompting Policy (applies to all issues in this PRD)

These issues are implemented as independent GPT-5.5 subagent tasks. Each issue file contains a `## GPT-5.5 Agent Prompt` section ready to paste into a subagent call.

**Derived from OpenAI GPT-5.5 prompting guidance (2026):**

- Prompts are **outcome-first**: goal → success criteria → constraints → context → verification. No step-by-step instructions.
- `reasoning.effort = medium` for all tasks here (scoped, local edits).
- Each prompt includes an **explicit scope fence** to prevent task expansion — GPT-5.5 reads every guidance file and tends to over-expand without this.
- **Verification is scaled to blast radius**: single-file edits get a focused lint/import check, not a full suite.
- Absolute rules (`ALWAYS`, `NEVER`) are reserved for true invariants (architecture rule: `core/` and `data/` must never import from `ui/`).
- Preamble instruction included for tool-heavy tasks so the model acknowledges the first step before acting.

---

## Work Streams (parallel — no dependencies between streams)

| Issue | Stream          | File                                    |
| ----- | --------------- | --------------------------------------- |
| 001   | Chat State      | thinking-indicator-and-stop-button      |
| 002   | Input UX        | input-validation-empty-state-api-banner |
| 003   | Message Actions | error-retry-and-message-actions         |
| 004   | Rendering       | message-rendering-fixes                 |
| 005   | Model Selector  | compact-model-selector                  |
| 006   | History         | history-search-and-preview              |
| 007   | Style           | style-polish                            |

All streams operate exclusively in `ui/panels/chat_panel.py` and `styles.py`.
No changes to `core/`, `data/`, `db/`, or `bdt/`.
