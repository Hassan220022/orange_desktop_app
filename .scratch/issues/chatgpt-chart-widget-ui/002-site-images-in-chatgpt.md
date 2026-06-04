---
title: Site images in ChatGPT — extend chart widget to render BDT photos
label: ready-for-agent
type: AFK
priority: P1
blocked_by: None
parent: ../../prds/chatgpt-chart-widget-ui.md
---

# 002 — Site images in ChatGPT

## Problems addressed

The first end-to-end ChatGPT render confirmed that the data + render flow
works, but the model is still blind to site images. In this domain,
"site images" are BDT (Battery Discharge Test) photos stored as
`BlobAsset` rows on disk and indexed via `BDTPhoto → BDTTest`. They are
the only visual evidence a field engineer has of a site's condition.
The gap is in three places:

1. **No MCP path that ships image bytes to ChatGPT.** `read_photo_blob`
   already returns base64 bytes (guarded by traversal / size / MIME / SHA
   checks in `llm_tools/service.py:1397-1439`), but the MCP server
   (`llm_tools/mcp_server.py:101-114`) wraps every tool result as a
   single `{"type": "text"}` content block. The model never gets an
   `{"type": "image"}` content block, and the chart widget has no
   payload kind for images. Net result: the model can fetch a base64
   string but cannot show the photo.
2. **No widget branch for photos.** `mcp_app/chart_widget/src/chart_widget.ts`
   only renders chart kinds. There is no way for the Apps SDK to mount
   the existing widget for an image-bearing tool result. Extending the
   existing chart widget (per the user's chosen shape) keeps a single
   resource URI and a single host, with a new `payload_kind` discriminator
   inside the same `structuredContent`.
3. **Desktop `chat_panel.py` only renders photos from `get_photo_metadata`.**
   `_tool_result_widget` at `ui/panels/chat_panel.py:1657` dispatches
   photo rendering only for `get_photo_metadata` (line 1664). The richer
   tools — `get_bdt_detail` (line 1680), `get_site_dossier` (line 1934),
   `get_site_full_context` — already return photo metadata in their
   payload, but the panel does not visualize it.

## Decision summary

- **One widget, two payload kinds.** Extend
  `mcp_app/chart_widget/src/chart_widget.ts` to dispatch on a new
  top-level `payload_kind` field in `structuredContent`. Keep the same
  `CHART_WIDGET_URI` resource; the Apps SDK treats the same
  `openai/outputTemplate` URI as a host for any structured payload the
  same tool template declares. This avoids a second resource, a second
  build, and a second MIME registration.
- **New MCP tool: `render_photo_widget`.** Mirrors `render_chart_widget`
  in shape. Inputs are a list of `sha256` references (with optional
  site_code / bdt_test_id filtering). Output is a `structuredContent`
  with `payload_kind: "photos"` plus the inline base64 / MIME for each
  photo, attached to the existing `CHART_WIDGET_URI` via `_meta`.
  Bytes are read through the existing `read_photo_blob` path so all
  guards (traversal, `MAX_BLOB_BYTES = 5 * 1024 * 1024`, MIME prefix,
  SHA round-trip, `Image.verify()`) still apply.
- **Cap batch size.** 6 photos per call by default, matching the
  desktop `chat_panel.py:_photo_metadata_widget` cap of 12 thumbnails
  and the existing `_PHOTO_THUMBNAIL_LIMIT`. Hard cap is 12. Larger
  sets must paginate via repeated `render_photo_widget` calls.
- **Out of scope:** changing the read-only parity tools
  (`query_bdt_full`, `get_site_full_context`, `get_sites_context_report`)
  to inline bytes. The existing PRD's "Photo metadata does not include
  image bytes" rule still stands; bytes flow only through the new
  `render_photo_widget` tool.

## Acceptance criteria

- [ ] New MCP tool `render_photo_widget` is registered in
      `llm_tools/tools.py:TOOL_SCHEMAS`, with `tool_definitions_for_mcp`
      returning the existing `CHART_WIDGET_URI` in `_meta.openai/outputTemplate`
      and `_meta.ui.resourceUri`. `render_photo_widget` is added to
      `_OPENROUTER_EXCLUDED_TOOL_NAMES` (it is host-only).
- [ ] `LocalDataService.render_photo_widget` in `llm_tools/service.py`
      accepts `site_code | bdt_test_id | sha256s` and a `limit`
      (default 6, max 12). For each requested `sha256`, it pulls bytes
      via the existing `read_photo_blob` logic (so all the guards still
      run) and returns a `structuredContent` of the shape:
      `json
    {
      "payload_kind": "photos",
      "title": "Site <site_code> — BDT photos",
      "photos": [
        {"sha256": "...", "mime_type": "image/jpeg", "width": 1920, "height": 1080, "slot_category": "rectifier", "slot_index": 3, "test_date": "2026-05-12", "data_url": "data:image/jpeg;base64,..."}
      ],
      "warnings": [...],
      "truncated": false
    }
    `
- [ ] If the input resolves to zero photos, the response uses the
      existing `empty_state` shape (`{title, message}`) and the widget
      shows a centred "no photos" panel exactly like the chart empty
      state.
- [ ] If the request asks for a `sha256` that is not in the DB, the
      tool returns a structured warning and a partial payload (do not
      throw). Missing photos go into `warnings: ["sha256 <x> not found"]`.
- [ ] `_model_safe_tool_result` in `llm_tools/openrouter_agent.py:132`
      keeps the new `photos[].data_url` field for this tool only. The
      `local_path` field is still redacted everywhere.
- [ ] `mcp_app/chart_widget/src/chart_widget.ts` adds a top-level
      dispatcher: if `payload.payload_kind === "photos"`, call a new
      `renderPhotos(payload)` that renders a responsive image grid
      (3 cols, 12 cap, lazy-loaded `<img>` with `decoding="async"`).
      Clicking a thumb opens a full-size modal overlay with `Esc` /
      `←` / `→` / `Close` controls.
- [ ] The chart widget's existing `payload_kind === "chart"` (or
      absent, for backward compatibility) path is unchanged. The build
      artifact `mcp_app/chart_widget/dist/chart.html` is rebuilt and
      remains browser-valid.
- [ ] `mcp_app/chart_widget/src/chart_widget.ts` escapes all
      `slot_category` / `title` / warning text before injection. Image
      `data_url` is set as an `<img src=...>` attribute, not injected
      as raw HTML.
- [ ] `ui/panels/chat_panel.py:_tool_result_widget` adds a branch for
      `name == "render_photo_widget"` that calls a new
      `_photo_grid_widget(result)` helper. The existing
      `_photo_metadata_widget` is reused for `get_photo_metadata`; the
      new helper is for the new tool's payload shape.
- [ ] `tests/test_llm_tools.py` adds: - `test_render_photo_widget_returns_inline_data_urls` - `test_render_photo_widget_caps_batch_at_limit` - `test_render_photo_widget_emits_warning_for_missing_sha256` - `test_render_photo_widget_excluded_from_openrouter` - a new test that loads `mcp_app/chart_widget/dist/chart.html`
      and asserts it contains the new `payload_kind === "photos"`
      branch (string match is enough — no DOM assertions).
- [ ] `tests/test_e2e_backend.py` adds: - `test_mcp_render_photo_widget_returns_structured_data_and_ui_metadata`
      (parallel to `test_mcp_render_chart_widget_*`). - `test_mcp_render_photo_widget_unknown_sha256_returns_warning`.
- [ ] The existing `read_photo_blob` tests still pass unchanged; no
      change to its guards or return shape.

## Constraints

- Edit only:
  - `mcp_app/chart_widget/src/chart_widget.ts` and
    `mcp_app/chart_widget/dist/chart.html` (regenerated by `build.py`).
  - `llm_tools/tools.py` (add `render_photo_widget` to `TOOL_SCHEMAS`,
    `_WRITE_TOOL_NAMES`, `_OPENROUTER_EXCLUDED_TOOL_NAMES`).
  - `llm_tools/service.py` (add `LocalDataService.render_photo_widget`).
  - `llm_tools/mcp_server.py` (no change needed if `render_photo_widget`
    is wired through the generic tool dispatcher; only add a branch if
    the existing handler cannot route it).
  - `ui/panels/chat_panel.py` (add the new dispatcher branch + a small
    `_photo_grid_widget` helper reusing the existing
    `_ImagePreviewDialog`).
  - `tests/test_llm_tools.py` and `tests/test_e2e_backend.py`.
- Do not touch `db/`, `bdt/`, `data/`, `core/`, or any `_PATH_KEYS`
  redaction logic in `openrouter_agent.py`. The new
  `_model_safe_tool_result` carve-out is a per-tool allowlist, not a
  global change.
- Do not modify `mcp_app/chart_widget/build.py`. It stays a trivial
  embed-script wrapper.
- Do not introduce a new resource URI. Both payload kinds share
  `CHART_WIDGET_URI` (`text/html;profile=mcp-app`).
- The widget must remain self-contained browser-valid JavaScript with
  no external network calls. No CDN image-loading.
- Treat all `structuredContent` as untrusted: escape labels, titles,
  slot categories, and warnings before injecting as HTML. Set
  `data_url` only as an `<img src=...>` attribute.
- The architecture rule still holds: widget code lives under `mcp_app/`,
  separate from `ui/`, `web/`, and `core/`.
- Hard cap: 12 photos per `render_photo_widget` call. The widget does
  not need to defend against larger payloads because the server caps it.

## Context

Key files:

- `llm_tools/service.py:1397-1439` — `read_photo_blob` is the bytes
  back-end. The new `render_photo_widget` should call into the same
  guards and reuse `MAX_BLOB_BYTES`, `_PATH_KEYS`, and the SHA-256
  round-trip.
- `llm_tools/service.py:1844-1882` — `render_chart_widget` is the
  template for the new tool's return shape, including the `_meta`
  block and the `structuredContent` envelope.
- `llm_tools/tools.py:368-373` and `llm_tools/service.py:1878-1881` —
  how the chart tool attaches `CHART_WIDGET_URI` to its `_meta`. Mirror
  this for `render_photo_widget`.
- `llm_tools/tools.py:780-781` — `_OPENROUTER_EXCLUDED_TOOL_NAMES`. Add
  `"render_photo_widget"` so the OpenRouter chat surface does not
  advertise a tool it cannot meaningfully call.
- `llm_tools/openrouter_agent.py:132-146` — `_model_safe_tool_result`
  walks results and redacts `*_path` keys. The carve-out for
  `photos[].data_url` should be a per-tool check (e.g. a set
  `_PHOTO_BEARING_TOOLS = {"render_photo_widget"}`), not a key-name
  allowlist, so `base64` continues to be redacted everywhere else.
- `mcp_app/chart_widget/src/chart_widget.ts:110-143` — `render(payload)`
  builds the card and dispatches to `renderChart`. Refactor: read
  `payload.payload_kind`, dispatch to `renderPhotos` for `"photos"`,
  keep `renderChart` for `"chart"` or absent. Both branches share the
  title / pill / warning shell.
- `mcp_app/chart_widget/src/chart_widget.ts:147-157` — message handlers.
  No change needed; they pass `structuredContent` straight through.
- `ui/panels/chat_panel.py:1657-1682` — `_tool_result_widget` dispatch.
  Add a `name == "render_photo_widget"` branch.
- `ui/panels/chat_panel.py:526-570` — `_ImagePreviewDialog` is the
  full-screen zoomable preview. Reuse it for the photo grid's click
  handler so the desktop UX stays consistent with the existing
  `get_photo_metadata` flow.
- `tests/test_llm_tools.py:67-69` — `TINY_PNG_BYTES` fixture is the
  shared base for all photo-byte tests; reuse it for the new tests.

Screenshots and the prior review show the gap is in the host-side
renderer, not in the data: the desktop chat panel can already render
photos from `get_photo_metadata`. The new tool is the missing link
between "the bytes exist on disk" and "ChatGPT can show them in a
widget".

## Verification

After the change:

1. `python mcp_app/chart_widget/build.py` rebuilds the dist HTML
   without errors and the new `payload_kind === "photos"` branch is
   present in the artifact.
2. `python -m pytest tests/test_llm_tools.py -k "render_photo_widget or chart_widget_package_builds"` passes.
3. `python -m pytest tests/test_e2e_backend.py -k render_photo_widget` passes.
4. Open `mcp_app/chart_widget/dist/chart.html` in a browser, dispatch a
   synthetic `message` event with `method: "ui/notifications/tool-result"`
   and a `structuredContent` of `payload_kind: "photos"` containing 3
   data URLs; confirm the grid renders, the modal opens, and Esc
   closes it. Dispatch an empty `payload_kind: "photos"` payload; confirm
   the empty state appears.
5. In the desktop `alarm_app`, with `OPENROUTER_API_KEY` unset, ask
   the chat panel "show me photos for site <code>". The
   `render_photo_widget` branch should open the image grid locally
   (the panel uses the same payload shape because `_tool_result_widget`
   handles both surfaces).

## Stop condition

Done when all acceptance criteria pass, the targeted tests pass, the
dist HTML is regenerated, and the chart-widget path remains
backward-compatible (a payload with no `payload_kind` still renders as
a chart). Do not refactor widget helpers beyond the new dispatch and
the new `renderPhotos` function.

---

## GPT-5.5 Agent Prompt

```
## Outcome

Make site images (BDT photos) visible inside ChatGPT. Extend the
existing mcp_app/chart_widget to recognise a new payload_kind
"photos" and render an image grid with a full-size modal. Add a new
MCP tool render_photo_widget that returns inline base64 photos with
the existing CHART_WIDGET_URI attached as _meta.openai/outputTemplate.
Wire the desktop chat_panel.py to render the same payload. Rebuild the
widget artifact.

## Success criteria

1. A new MCP tool render_photo_widget is registered in
   llm_tools/tools.py:TOOL_SCHEMAS. It is added to
   _OPENROUTER_EXCLUDED_TOOL_NAMES (it is host-only) and to
   _WRITE_TOOL_NAMES.
2. LocalDataService.render_photo_widget in llm_tools/service.py accepts
   site_code | bdt_test_id | sha256s and a limit (default 6, max 12).
   It returns a structuredContent of:
     {payload_kind: "photos", title, photos: [{sha256, mime_type,
      width, height, slot_category, slot_index, test_date, data_url}],
      warnings, truncated}
   with the same _meta shape as render_chart_widget (CHART_WIDGET_URI
   on _meta.openai.outputTemplate and _meta.ui.resourceUri).
3. Bytes are read through the existing read_photo_blob logic so all
   guards (path traversal, MAX_BLOB_BYTES, MIME prefix, SHA round-trip,
   Image.verify) still apply. Missing sha256s emit a warning and the
   call still returns the rest of the batch. Empty batches return the
   empty_state shape.
4. _model_safe_tool_result in llm_tools/openrouter_agent.py keeps the
   new photos[].data_url field for render_photo_widget only, via a
   per-tool allowlist. local_path stays redacted everywhere.
5. mcp_app/chart_widget/src/chart_widget.ts dispatches on
   payload.payload_kind. "photos" calls a new renderPhotos(payload)
   that renders a 3-column responsive grid, lazy <img decoding=async>,
   click-to-open full-size modal with Esc / arrow / close controls. The
   existing chart path is unchanged and remains the default when
   payload_kind is absent.
6. The widget escapes all slot_category / title / warning text and
   sets data_url only as an <img src=...> attribute.
7. ui/panels/chat_panel.py:_tool_result_widget adds a branch for
   name == "render_photo_widget" that calls a new
   _photo_grid_widget(result) helper reusing _ImagePreviewDialog.
8. mcp_app/chart_widget/dist/chart.html is regenerated by
   `python mcp_app/chart_widget/build.py` and contains the new
   payload_kind === "photos" branch.
9. python -m pytest tests/test_llm_tools.py -k
   "render_photo_widget or chart_widget_package_builds" passes.
10. python -m pytest tests/test_e2e_backend.py -k render_photo_widget
    passes. The new tests cover: inline data URLs, batch cap,
    missing-sha256 warning, unknown-tool path, _meta presence.
11. The existing read_photo_blob tests still pass unchanged; the chart
    path is backward-compatible (no payload_kind still renders as a
    chart).

## Constraints

- Edit only: mcp_app/chart_widget/src/chart_widget.ts and
  mcp_app/chart_widget/dist/chart.html, llm_tools/tools.py,
  llm_tools/service.py, llm_tools/mcp_server.py (only if the generic
  tool dispatcher cannot route render_photo_widget),
  ui/panels/chat_panel.py, tests/test_llm_tools.py,
  tests/test_e2e_backend.py.
- Do not touch db/, bdt/, data/, core/, or the _PATH_KEYS redaction
  set in openrouter_agent.py. The new carve-out is a per-tool
  allowlist, not a global change.
- Do not modify mcp_app/chart_widget/build.py.
- Do not introduce a new resource URI; both payload kinds share
  CHART_WIDGET_URI.
- The widget stays self-contained browser-valid JavaScript with no
  external network calls. No CDN image-loading.
- Treat all structuredContent as untrusted: escape labels, titles,
  slot categories, and warnings before injecting as HTML. Set
  data_url only as an <img src=...> attribute.
- Architecture rule: widget code lives under mcp_app/, separate from
  ui/, web/, and core/.
- Hard cap: 12 photos per render_photo_widget call. The widget does
  not need to defend against larger payloads because the server caps
  it.

## Context

Files:
- llm_tools/service.py:1397-1439 — read_photo_blob is the bytes
  back-end; reuse its guards.
- llm_tools/service.py:1844-1882 — render_chart_widget is the
  template for the new tool's return shape.
- llm_tools/tools.py:368-373 and llm_tools/service.py:1878-1881 —
  CHART_WIDGET_URI is attached via _meta; mirror for
  render_photo_widget.
- llm_tools/tools.py:780-781 — add render_photo_widget to
  _OPENROUTER_EXCLUDED_TOOL_NAMES.
- llm_tools/openrouter_agent.py:132-146 — add a per-tool allowlist
  for render_photo_widget so photos[].data_url is preserved.
- mcp_app/chart_widget/src/chart_widget.ts:110-143 — refactor
  render(payload) to dispatch on payload_kind.
- ui/panels/chat_panel.py:1657-1682 — add the new branch.
- ui/panels/chat_panel.py:526-570 — reuse _ImagePreviewDialog.
- tests/test_llm_tools.py:67-69 — TINY_PNG_BYTES fixture.

## Verification

1. python mcp_app/chart_widget/build.py rebuilds the dist HTML and
   the new payload_kind === "photos" branch is present.
2. python -m pytest tests/test_llm_tools.py -k
   "render_photo_widget or chart_widget_package_builds" passes.
3. python -m pytest tests/test_e2e_backend.py -k render_photo_widget
   passes.
4. Open mcp_app/chart_widget/dist/chart.html, dispatch a synthetic
   message event with payload_kind: "photos" containing 3 data URLs
   and an empty batch; confirm the grid, modal, and empty state all
   render.
5. Ask the desktop chat panel "show me photos for site <code>". The
   image grid should open via _photo_grid_widget.

## Stop condition

Done when all success criteria pass and the targeted tests pass. Do
not refactor widget helpers beyond the new dispatch and renderPhotos
function. Do not change read_photo_blob's guards.
```
