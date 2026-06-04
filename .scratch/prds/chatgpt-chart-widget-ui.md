# PRD: ChatGPT Chart Widget UI

**Status:** ready-for-agent
**Date:** 2026-06-04
**Source:** First end-to-end render of the new Apps SDK chart widget in ChatGPT.

---

## Problem Statement

The MCP chart-widget data flow now works end-to-end in ChatGPT
(`list_chart_types` → `get_chart_data` → `render_chart_widget`), and the
tool surface is no longer leaking server-side PNG generation. However, the
first real ChatGPT render exposed clear visual and UX problems in the widget
renderer at `mcp_app/chart_widget/src/chart_widget.ts`:

| #   | Category                 | Severity | Issue                                                                                                                                      |
| --- | ------------------------ | -------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| 1   | Donut/pie readability    | P1       | Sub-1% slices collapse into indistinguishable slivers; small values like `CS: 5` and `5G: 53,364` are visually equivalent.                 |
| 2   | Legend association       | P1       | Legend is a stacked text block; no color swatches, no alignment with the ring, so users cannot map wedge → label without reading numbers.  |
| 3   | Empty-state affordance   | P1       | When `data_quality` is all zeros, the card shows `0 shown / 0 points` pills plus the empty-state panel simultaneously, which looks broken. |
| 4   | Rendering fallback       | P2       | Unsupported `chart_kind` shows a plain text table; should be a styled fallback inside the same card.                                       |
| 5   | Color contrast / theming | P3       | Wedge palette is hand-picked and not theme-aware; only six colors repeat across all donut charts.                                          |

---

## GPT-5.5 Prompting Policy (applies to all issues in this PRD)

Each issue file in `.scratch/issues/chatgpt-chart-widget-ui/` contains a
`## GPT-5.5 Agent Prompt` section ready to paste into a subagent call.

Derived from the existing `chatbot-ui-improvements` PRD:

- Prompts are outcome-first: goal → success criteria → constraints → context → verification.
- `reasoning.effort = medium` for all tasks here (scoped, local edits).
- Each prompt includes an explicit scope fence.
- Verification is scaled to blast radius: single-file widget edits get a focused
  build + targeted test, not a full suite.
- Absolute rules are reserved for true invariants (no external network calls
  inside the widget; widget never imports from `ui/`, `web/`, or `core/`).

---

## Work Streams

| Issue | Stream                          | File                                       |
| ----- | ------------------------------- | ------------------------------------------ |
| 001   | Donut/legend/empty-state polish | `mcp_app/chart_widget/src/chart_widget.ts` |

All work operates only inside `mcp_app/chart_widget/`. The widget
`build.py` and the tool contracts in `llm_tools/` are not in scope for
this PRD.
