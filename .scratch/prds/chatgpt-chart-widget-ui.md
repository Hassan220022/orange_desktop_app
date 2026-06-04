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

| #   | Category                 | Severity | Issue                                                                                                                                                                                                                                                                                                                                                                  |
| --- | ------------------------ | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Donut/pie readability    | P1       | Sub-1% slices collapse into indistinguishable slivers; small values like `CS: 5` and `5G: 53,364` are visually equivalent.                                                                                                                                                                                                                                             |
| 2   | Legend association       | P1       | Legend is a stacked text block; no color swatches, no alignment with the ring, so users cannot map wedge → label without reading numbers.                                                                                                                                                                                                                              |
| 3   | Empty-state affordance   | P1       | When `data_quality` is all zeros, the card shows `0 shown / 0 points` pills plus the empty-state panel simultaneously, which looks broken.                                                                                                                                                                                                                             |
| 4   | Rendering fallback       | P2       | Unsupported `chart_kind` shows a plain text table; should be a styled fallback inside the same card.                                                                                                                                                                                                                                                                   |
| 5   | Color contrast / theming | P3       | Wedge palette is hand-picked and not theme-aware; only six colors repeat across all donut charts.                                                                                                                                                                                                                                                                      |
| 6   | Site images unreachable  | P1       | BDT / site photos are available as `BlobAsset` blobs but the model cannot see them in ChatGPT. The widget has no image payload kind, and the MCP tool surface only ships base64 inside a `text` content block. The desktop `chat_panel.py` also only renders photos for `get_photo_metadata`, not for `get_bdt_detail` / `get_site_dossier` / `get_site_full_context`. |

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

| Issue | Stream                          | File                                                                                                                                                                         |
| ----- | ------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 001   | Donut/legend/empty-state polish | `mcp_app/chart_widget/src/chart_widget.ts`                                                                                                                                   |
| 002   | Site images in ChatGPT          | `mcp_app/chart_widget/src/chart_widget.ts` + `llm_tools/{tools,service,mcp_server}.py` + `ui/panels/chat_panel.py` + `tests/test_llm_tools.py` + `tests/test_e2e_backend.py` |

The chart widget is the home of both payload kinds. Issue 002 extends it
to recognise a new `payload_kind: "photos"` (or equivalent discriminator)
and adds a sibling MCP tool plus the desktop `chat_panel.py` branches
that exercise the same payload.

**Out of scope for this PRD:** any change to the `db/` blob layout, the
`read_photo_blob` traversal/size/MIME guards, the `_PATH_KEYS` redaction
set in `openrouter_agent.py`, or the read-only parity PRD's "no image
bytes in tool results" rule. The new flow goes through a new, explicitly
photo-bearing tool, not by changing the existing read-only tools.
