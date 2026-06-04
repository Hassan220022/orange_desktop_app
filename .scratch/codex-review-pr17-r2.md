2026-06-04T15:17:28.567256Z ERROR codex_core::session::session: failed to load skill /Users/mikawi/.codex/plugins/cache/claude-plugins-official/convex-backend/1.0.0/skills/design/SKILL.md: invalid description: exceeds maximum length of 1024 characters
OpenAI Codex v0.136.0
--------
workdir: /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
model: gpt-5.5
provider: openai
approval: never
sandbox: workspace-write [workdir, /tmp, $TMPDIR]
reasoning effort: medium
reasoning summaries: none
session id: 019e9335-f7a8-7ef0-a309-07182f64aa4c
--------
user
changes against 'HEAD~1'
2026-06-04T15:17:31.244294Z ERROR codex_core::session::session: failed to load skill /Users/mikawi/.codex/plugins/cache/claude-plugins-official/convex-backend/1.0.0/skills/design/SKILL.md: invalid description: exceeds maximum length of 1024 characters
exec
/bin/zsh -lc 'cat /Users/mikawi/.codex/skills/review/SKILL.md && (test -d .gitnexus && gitnexus status || true) && git diff 9f2c094ebbf8cc88a39f0c6dd514dff331adb852 --stat && git diff 9f2c094ebbf8cc88a39f0c6dd514dff331adb852' in /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
 succeeded in 420ms:
Repository: /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
Indexed: 6/4/2026, 3:29:24 PM
Indexed commit: c2528ad
Current commit: 22292d8
Status: ⚠️ stale (re-run gitnexus analyze)
 .scratch/prds/chatgpt-chart-widget-ui.md | 37 +++++++++++--------
 AGENTS.md                                | 62 ++++++++++++++++----------------
 CLAUDE.md                                | 60 +++++++++++++++----------------
 llm_tools/service.py                     | 15 +++++++-
 tests/test_llm_tools.py                  | 57 +++++++++++++++++++++++++++--
 5 files changed, 151 insertions(+), 80 deletions(-)
diff --git a/.scratch/prds/chatgpt-chart-widget-ui.md b/.scratch/prds/chatgpt-chart-widget-ui.md
index b152e21..8c1a4b3 100644
--- a/.scratch/prds/chatgpt-chart-widget-ui.md
+++ b/.scratch/prds/chatgpt-chart-widget-ui.md
@@ -14,13 +14,14 @@ tool surface is no longer leaking server-side PNG generation. However, the
 first real ChatGPT render exposed clear visual and UX problems in the widget
 renderer at `mcp_app/chart_widget/src/chart_widget.ts`:
 
-| #   | Category                 | Severity | Issue                                                                                                                                      |
-| --- | ------------------------ | -------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
-| 1   | Donut/pie readability    | P1       | Sub-1% slices collapse into indistinguishable slivers; small values like `CS: 5` and `5G: 53,364` are visually equivalent.                 |
-| 2   | Legend association       | P1       | Legend is a stacked text block; no color swatches, no alignment with the ring, so users cannot map wedge → label without reading numbers.  |
-| 3   | Empty-state affordance   | P1       | When `data_quality` is all zeros, the card shows `0 shown / 0 points` pills plus the empty-state panel simultaneously, which looks broken. |
-| 4   | Rendering fallback       | P2       | Unsupported `chart_kind` shows a plain text table; should be a styled fallback inside the same card.                                       |
-| 5   | Color contrast / theming | P3       | Wedge palette is hand-picked and not theme-aware; only six colors repeat across all donut charts.                                          |
+| #   | Category                 | Severity | Issue                                                                                                                                                                                                                                                                                                                                                                  |
+| --- | ------------------------ | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
+| 1   | Donut/pie readability    | P1       | Sub-1% slices collapse into indistinguishable slivers; small values like `CS: 5` and `5G: 53,364` are visually equivalent.                                                                                                                                                                                                                                             |
+| 2   | Legend association       | P1       | Legend is a stacked text block; no color swatches, no alignment with the ring, so users cannot map wedge → label without reading numbers.                                                                                                                                                                                                                              |
+| 3   | Empty-state affordance   | P1       | When `data_quality` is all zeros, the card shows `0 shown / 0 points` pills plus the empty-state panel simultaneously, which looks broken.                                                                                                                                                                                                                             |
+| 4   | Rendering fallback       | P2       | Unsupported `chart_kind` shows a plain text table; should be a styled fallback inside the same card.                                                                                                                                                                                                                                                                   |
+| 5   | Color contrast / theming | P3       | Wedge palette is hand-picked and not theme-aware; only six colors repeat across all donut charts.                                                                                                                                                                                                                                                                      |
+| 6   | Site images unreachable  | P1       | BDT / site photos are available as `BlobAsset` blobs but the model cannot see them in ChatGPT. The widget has no image payload kind, and the MCP tool surface only ships base64 inside a `text` content block. The desktop `chat_panel.py` also only renders photos for `get_photo_metadata`, not for `get_bdt_detail` / `get_site_dossier` / `get_site_full_context`. |
 
 ---
 
@@ -43,10 +44,18 @@ Derived from the existing `chatbot-ui-improvements` PRD:
 
 ## Work Streams
 
-| Issue | Stream                          | File                                       |
-| ----- | ------------------------------- | ------------------------------------------ |
-| 001   | Donut/legend/empty-state polish | `mcp_app/chart_widget/src/chart_widget.ts` |
-
-All work operates only inside `mcp_app/chart_widget/`. The widget
-`build.py` and the tool contracts in `llm_tools/` are not in scope for
-this PRD.
+| Issue | Stream                          | File                                                                                                                                                                         |
+| ----- | ------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
+| 001   | Donut/legend/empty-state polish | `mcp_app/chart_widget/src/chart_widget.ts`                                                                                                                                   |
+| 002   | Site images in ChatGPT          | `mcp_app/chart_widget/src/chart_widget.ts` + `llm_tools/{tools,service,mcp_server}.py` + `ui/panels/chat_panel.py` + `tests/test_llm_tools.py` + `tests/test_e2e_backend.py` |
+
+The chart widget is the home of both payload kinds. Issue 002 extends it
+to recognise a new `payload_kind: "photos"` (or equivalent discriminator)
+and adds a sibling MCP tool plus the desktop `chat_panel.py` branches
+that exercise the same payload.
+
+**Out of scope for this PRD:** any change to the `db/` blob layout, the
+`read_photo_blob` traversal/size/MIME guards, the `_PATH_KEYS` redaction
+set in `openrouter_agent.py`, or the read-only parity PRD's "no image
+bytes in tool results" rule. The new flow goes through a new, explicitly
+photo-bearing tool, not by changing the existing read-only tools.
diff --git a/AGENTS.md b/AGENTS.md
index 27308c1..a39edcc 100644
--- a/AGENTS.md
+++ b/AGENTS.md
@@ -1,45 +1,43 @@
 <!-- gitnexus:start -->
-# GitNexus — Code Intelligence (CLI Only)
+# GitNexus — Code Intelligence
 
-This project is indexed by GitNexus as **orange_desktop_app** (8191 symbols, 14693 relationships, 298 execution flows).
+This project is indexed by GitNexus as **orange_desktop_app** (10466 symbols, 18718 relationships, 300 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.
 
-**IMPORTANT: ALWAYS use the `gitnexus` CLI via shell commands. NEVER use GitNexus MCP or code-review-graph MCP tools in this repository.** The local CLI is installed at `/opt/homebrew/bin/gitnexus`, and all GitNexus operations must go through CLI commands.
-
-Because multiple repositories are indexed globally, every graph command for this repo must include `-r orange_desktop_app`.
-
-> If the index is stale, run `gitnexus analyze` in terminal first, then rerun the GitNexus command.
+> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.
 
 ## Always Do
 
-- **MUST run `gitnexus status` at the start of code work** to confirm the index is available and current.
-- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus impact -r orange_desktop_app -d upstream <symbol>` and report the blast radius to the user.
-- **MUST run `gitnexus detect-changes -r orange_desktop_app --scope all` before committing** to verify your changes only affect expected symbols and execution flows.
+- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
+- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
 - **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
-- When exploring unfamiliar code, run `gitnexus query -r orange_desktop_app "<concept>"` before Grep/Glob/Read.
-- When you need full context on a specific symbol, run `gitnexus context -r orange_desktop_app <symbolName>`.
+- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
+- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.
 
 ## Never Do
 
-- NEVER use GitNexus MCP tools, code-review-graph MCP tools, or `gitnexus://...` MCP resources for this repo.
-- NEVER edit a function, class, or method without first running `gitnexus impact` on it.
+- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
 - NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
-- NEVER commit changes without running `gitnexus detect-changes` to check affected scope.
-
-## CLI Commands
-
-All commands require `-r orange_desktop_app` because multiple repos are indexed.
-
-| Command | Use when |
-|---------|---------|
-| `gitnexus analyze` | Index or re-index the repository |
-| `gitnexus status` | Check if index is up-to-date |
-| `gitnexus list` | List all indexed repositories |
-| `gitnexus query -r orange_desktop_app "<concept>"` | Find execution flows by concept |
-| `gitnexus context -r orange_desktop_app <symbol>` | 360-degree view of a symbol |
-| `gitnexus impact -r orange_desktop_app -d upstream\|downstream <symbol>` | Blast radius analysis |
-| `gitnexus detect-changes -r orange_desktop_app --scope all` | Analyze uncommitted git changes |
-| `gitnexus wiki` | Generate repository wiki |
-| `gitnexus clean` | Delete index for current repo |
-| `gitnexus doctor` | Check runtime capabilities |
+- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
+- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.
+
+## Resources
+
+| Resource | Use for |
+|----------|---------|
+| `gitnexus://repo/orange_desktop_app/context` | Codebase overview, check index freshness |
+| `gitnexus://repo/orange_desktop_app/clusters` | All functional areas |
+| `gitnexus://repo/orange_desktop_app/processes` | All execution flows |
+| `gitnexus://repo/orange_desktop_app/process/{name}` | Step-by-step execution trace |
+
+## CLI
+
+| Task | Read this skill file |
+|------|---------------------|
+| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
+| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
+| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
+| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
+| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
+| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |
 
 <!-- gitnexus:end -->
diff --git a/CLAUDE.md b/CLAUDE.md
index a9ee843..e1d437f 100644
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ -135,45 +135,45 @@ Use the default five-role triage label vocabulary. See `docs/agents/triage-label
 This is a single-context repo with root `CONTEXT.md` and ADRs under `docs/adr/`. See `docs/agents/domain.md`.
 
 <!-- gitnexus:start -->
-# GitNexus — Code Intelligence (CLI Only)
+# GitNexus — Code Intelligence
 
-This project is indexed by GitNexus as **orange_desktop_app** (8191 symbols, 14693 relationships, 298 execution flows).
+This project is indexed by GitNexus as **orange_desktop_app** (10466 symbols, 18718 relationships, 300 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.
 
-**IMPORTANT: ALWAYS use the `gitnexus` CLI via shell commands. NEVER use GitNexus MCP or code-review-graph MCP tools in this repository.** The local CLI is installed at `/opt/homebrew/bin/gitnexus`, and all GitNexus operations must go through CLI commands.
-
-Because multiple repositories are indexed globally, every graph command for this repo must include `-r orange_desktop_app`.
-
-> If the index is stale, run `gitnexus analyze` in terminal first, then rerun the GitNexus command.
+> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.
 
 ## Always Do
 
-- **MUST run `gitnexus status` at the start of code work** to confirm the index is available and current.
-- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus impact -r orange_desktop_app -d upstream <symbol>` and report the blast radius to the user.
-- **MUST run `gitnexus detect-changes -r orange_desktop_app --scope all` before committing** to verify your changes only affect expected symbols and execution flows.
+- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
+- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
 - **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
-- When exploring unfamiliar code, run `gitnexus query -r orange_desktop_app "<concept>"` before Grep/Glob/Read.
-- When you need full context on a specific symbol, run `gitnexus context -r orange_desktop_app <symbolName>`.
+- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
+- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.
 
 ## Never Do
 
-- NEVER use GitNexus MCP tools, code-review-graph MCP tools, or `gitnexus://...` MCP resources for this repo.
+- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
 - NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
-- NEVER edit a function, class, or method without first running `gitnexus impact` on it.
-- NEVER commit changes without running `gitnexus detect-changes` to check affected scope.
-
-## CLI Commands
-
-| Command | Use when |
-|---------|---------|
-| `gitnexus analyze` | Index or re-index the repository |
-| `gitnexus status` | Check if index is up-to-date |
-| `gitnexus list` | List all indexed repositories |
-| `gitnexus query -r orange_desktop_app "<concept>"` | Find execution flows by concept |
-| `gitnexus context -r orange_desktop_app <symbol>` | 360-degree view of a symbol |
-| `gitnexus impact -r orange_desktop_app -d upstream\|downstream <symbol>` | Blast radius analysis |
-| `gitnexus detect-changes -r orange_desktop_app --scope all` | Analyze uncommitted git changes |
-| `gitnexus wiki` | Generate repository wiki |
-| `gitnexus clean` | Delete index for current repo |
-| `gitnexus doctor` | Check runtime capabilities |
+- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
+- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.
+
+## Resources
+
+| Resource | Use for |
+|----------|---------|
+| `gitnexus://repo/orange_desktop_app/context` | Codebase overview, check index freshness |
+| `gitnexus://repo/orange_desktop_app/clusters` | All functional areas |
+| `gitnexus://repo/orange_desktop_app/processes` | All execution flows |
+| `gitnexus://repo/orange_desktop_app/process/{name}` | Step-by-step execution trace |
+
+## CLI
+
+| Task | Read this skill file |
+|------|---------------------|
+| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
+| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
+| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
+| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
+| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
+| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |
 
 <!-- gitnexus:end -->
diff --git a/llm_tools/service.py b/llm_tools/service.py
index ca92f24..ff9600f 100644
--- a/llm_tools/service.py
+++ b/llm_tools/service.py
@@ -1489,7 +1489,20 @@ class LocalDataService:
         date_from = _date_value(kwargs.get("date_from"))
         date_to = _date_value(kwargs.get("date_to"))
         if site_code and kwargs.get("_prefer_site_slice"):
-            return self._alarm_rows_for_sites({site_code}, date_from=date_from, date_to=date_to)
+            q = alarm_store.AlarmQuery(
+                site_text="",
+                site_scope_keys={normalize_site_key(site_code)},
+                category=str(kwargs.get("category") or "All"),
+                vendor=str(kwargs.get("vendor") or "All"),
+                network_type=str(kwargs.get("network_type") or "All"),
+                date_from=date_from,
+                date_to=date_to,
+                sort_by="occurred_on",
+                sort_desc=False,
+                limit=None,
+                offset=0,
+            )
+            return self._with_alarm_source(lambda: alarm_store.query_alarms(q))
         q = alarm_store.AlarmQuery(
             site_text=str(kwargs.get("site_text") or "") if not site_code else "",
             site_scope_keys={normalize_site_key(site_code)} if site_code else None,
diff --git a/tests/test_llm_tools.py b/tests/test_llm_tools.py
index c3823df..53710b6 100644
--- a/tests/test_llm_tools.py
+++ b/tests/test_llm_tools.py
@@ -3025,7 +3025,7 @@ def test_get_chart_data_returns_deterministic_structured_payload(tmp_path, monke
         {"site_id": "AAA001", "alarm_category": "Down", "occurred_on": "2026-04-02"},
         {"site_id": "AAA001", "alarm_category": "Power", "occurred_on": "2026-04-03"},
     ])
-    monkeypatch.setattr(service, "_alarm_rows_for_sites", lambda site_keys, date_from=None, date_to=None, **kwargs: alarm_df)
+    monkeypatch.setattr(service, "_with_alarm_source", lambda fn: alarm_df)
 
     result = service.get_chart_data(
         chart_id="alarm_category_counts",
@@ -3049,6 +3049,57 @@ def test_get_chart_data_returns_deterministic_structured_payload(tmp_path, monke
     assert "path" not in result
 
 
+def test_get_chart_data_forwards_alarm_filters_in_prefer_site_slice_path(tmp_path, monkeypatch):
+    """Regression: site-scoped chart path must honor category / vendor / network_type filters."""
+    service = LocalDataService(export_dir=tmp_path / "exports")
+    alarm_df = pd.DataFrame([
+        {"site_id": "AAA001", "alarm_category": "Power", "vendor": "Huawei", "network_type": "4G"},
+        {"site_id": "AAA001", "alarm_category": "Down", "vendor": "Nokia", "network_type": "3G"},
+    ])
+    captured: list = []
+
+    def fake_alarm_source(fn):
+        # Run the closure (which builds an AlarmQuery and calls query_alarms),
+        # capturing the query kwargs the lambda handed to query_alarms.
+        from llm_tools import service as service_module
+        original_query = service_module.alarm_store.query_alarms
+
+        def recording_query_alarms(q):
+            captured.append({
+                "site_scope_keys": q.site_scope_keys,
+                "category": q.category,
+                "vendor": q.vendor,
+                "network_type": q.network_type,
+            })
+            return alarm_df
+
+        service_module.alarm_store.query_alarms = recording_query_alarms
+        try:
+            return fn()
+        finally:
+            service_module.alarm_store.query_alarms = original_query
+
+    monkeypatch.setattr(service, "_with_alarm_source", fake_alarm_source)
+
+    result = service.get_chart_data(
+        chart_id="alarm_category_counts",
+        filters={"site_code": "AAA001", "category": "Power", "vendor": "Huawei", "network_type": "4G"},
+    )
+
+    assert captured, "expected at least one AlarmQuery to be built"
+    query_kwargs = captured[-1]
+    assert query_kwargs["site_scope_keys"] == {"AAA001"}
+    assert query_kwargs["category"] == "Power"
+    assert query_kwargs["vendor"] == "Huawei"
+    assert query_kwargs["network_type"] == "4G"
+    assert result["query_context"]["filters"] == {
+        "site_code": "AAA001",
+        "category": "Power",
+        "vendor": "Huawei",
+        "network_type": "4G",
+    }
+
+
 def test_get_chart_data_clamps_max_points_and_reports_empty_state(tmp_path, monkeypatch):
     service = LocalDataService(export_dir=tmp_path / "exports")
     monkeypatch.setattr(service, "_alarm_rows_for_sites", lambda site_keys, date_from=None, date_to=None, **kwargs: pd.DataFrame())
@@ -3204,7 +3255,7 @@ def test_generate_graph_writes_png_from_alarm_data(tmp_path, monkeypatch):
         {"site_id": "AAA001", "alarm_category": "Down", "occurred_on": "2026-04-02"},
         {"site_id": "AAA001", "alarm_category": "Power", "occurred_on": "2026-04-03"},
     ])
-    monkeypatch.setattr(service, "_alarm_rows_for_sites", lambda site_keys, date_from=None, date_to=None, **kwargs: alarm_df)
+    monkeypatch.setattr(service, "_with_alarm_source", lambda fn: alarm_df)
 
     result = service.generate_graph(graph_type="alarm_category_counts", site_code="AAA001")
 
@@ -3226,7 +3277,7 @@ def test_generate_graph_supports_non_bar_chart_kinds(tmp_path, monkeypatch):
         {"site_id": "AAA001", "alarm_category": "Down", "occurred_on": "2026-04-01 04:00:00"},
         {"site_id": "AAA001", "alarm_category": "Power", "occurred_on": "2026-04-02 04:00:00"},
     ])
-    monkeypatch.setattr(service, "_alarm_rows_for_sites", lambda site_keys, date_from=None, date_to=None, **kwargs: alarm_df)
+    monkeypatch.setattr(service, "_with_alarm_source", lambda fn: alarm_df)
 
     pie = service.generate_graph(graph_type="alarm_category_share", site_code="AAA001")
     heatmap = service.generate_graph(graph_type="alarm_heatmap_day_hour", site_code="AAA001")

exec
/bin/zsh -lc "git log --oneline 9f2c094ebbf8cc88a39f0c6dd514dff331adb852..HEAD && sed -n '1420,1545p' llm_tools/service.py && sed -n '1545,1635p' llm_tools/service.py && grep -R \"def _alarm_rows_for_sites\\|_prefer_site_slice\\|get_chart_data\" -n llm_tools tests | head -80" in /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
 succeeded in 369ms:
llm_tools/service.py:1491:        if site_code and kwargs.get("_prefer_site_slice"):
llm_tools/service.py:1788:    def get_chart_data(self, **kwargs) -> dict[str, Any]:
llm_tools/service.py:1815:        series_kwargs["_prefer_site_slice"] = True
llm_tools/service.py:1906:        series_kwargs["_prefer_site_slice"] = True
llm_tools/service.py:2427:    def _alarm_rows_for_sites(
llm_tools/tools.py:284:        "description": "List supported chart types. For ChatGPT charts, call list_chart_types, then get_chart_data, then render_chart_widget.",
llm_tools/tools.py:296:    "get_chart_data": {
llm_tools/tools.py:299:            "Preferred ChatGPT chart flow: list_chart_types -> get_chart_data -> render_chart_widget."
llm_tools/tools.py:335:            "Render the Apps SDK chart widget from a validated get_chart_data payload. "
llm_tools/tools.py:336:            "Call get_chart_data first, then pass its structured payload here."
Binary file llm_tools/__pycache__/service.cpython-313.pyc matches
Binary file llm_tools/__pycache__/openrouter_agent.cpython-313.pyc matches
Binary file llm_tools/__pycache__/service.cpython-314.pyc matches
Binary file llm_tools/__pycache__/tools.cpython-314.pyc matches
Binary file llm_tools/__pycache__/tools.cpython-313.pyc matches
llm_tools/openrouter_agent.py:54:8. Use list_chart_types and get_chart_data when the user asks for chart-ready data; server-side PNG chart generation is not exposed as a chat tool.
tests/test_e2e_backend.py:283:        assert "get_chart_data" in tools
Binary file tests/__pycache__/test_e2e_backend.cpython-314-pytest-9.0.3.pyc matches
Binary file tests/__pycache__/test_llm_tools.cpython-314.pyc matches
Binary file tests/__pycache__/test_llm_tools.cpython-314-pytest-9.0.3.pyc matches
Binary file tests/__pycache__/test_llm_tools.cpython-313-pytest-9.0.3.pyc matches
Binary file tests/__pycache__/test_e2e_backend.cpython-314.pyc matches
Binary file tests/__pycache__/test_e2e_backend.cpython-313-pytest-9.0.3.pyc matches
tests/test_llm_tools.py:740:    assert "get_chart_data" in mcp_names
tests/test_llm_tools.py:741:    assert "get_chart_data" in openrouter_names
tests/test_llm_tools.py:796:    schema_ids = TOOL_SCHEMAS["get_chart_data"]["inputSchema"]["properties"]["chart_id"]["enum"]
tests/test_llm_tools.py:3021:def test_get_chart_data_returns_deterministic_structured_payload(tmp_path, monkeypatch):
tests/test_llm_tools.py:3030:    result = service.get_chart_data(
tests/test_llm_tools.py:3052:def test_get_chart_data_forwards_alarm_filters_in_prefer_site_slice_path(tmp_path, monkeypatch):
tests/test_llm_tools.py:3084:    result = service.get_chart_data(
tests/test_llm_tools.py:3103:def test_get_chart_data_clamps_max_points_and_reports_empty_state(tmp_path, monkeypatch):
tests/test_llm_tools.py:3107:    result = service.get_chart_data(

exec
/bin/zsh -lc "sed -n '1760,1935p' llm_tools/service.py && sed -n '2400,2475p' llm_tools/service.py && python - <<'PY'
import inspect
from llm_tools import alarm_store
print(alarm_store.AlarmQuery)
print(inspect.signature(alarm_store.query_alarms))
print(inspect.getsource(alarm_store.query_alarms)[:4000])
PY" in /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
 exited 127 in 0ms:

    def _chart_series_for_spec(self, graph_type: str, kwargs: dict[str, Any]) -> tuple[list[str], list[float], list[dict[str, Any]]]:
        spec = CHART_SPECS.get(graph_type)
        if spec is None:
            return [], [], []
        site_code = normalize_site_key(kwargs.get("site_code") or kwargs.get("site_text") or "")
        if spec.family == "alarm":
            alarm_df = self._chart_alarm_df(site_code=site_code, kwargs=kwargs)
            if graph_type in {"alarm_category_counts", "alarm_daily_counts", "alarm_duration_by_category"}:
                labels, values = self._alarm_graph_series(alarm_df, graph_type)
                series = [{"label": str(label), "value": float(value)} for label, value in zip(labels, values, strict=False)]
                return labels, values, series
            return self._alarm_chart_series(alarm_df, graph_type)
        if spec.family == "backup":
            return self._backup_chart_series(graph_type, kwargs)
        if spec.family == "bdt":
            return self._bdt_chart_series(graph_type, kwargs)
        # PM, HT, metadata, and advanced flow charts are catalogued now and can
        # be rendered as empty placeholders until their source-specific
        # aggregators are expanded.
        return [], [], []

    @staticmethod
    def _chart_axis_labels(chart_kind: str) -> tuple[str, str]:
        if chart_kind in {"line", "histogram", "heatmap", "scatter", "calendar_heatmap", "timeline"}:
            return "X", "Value"
        return "Category", "Count"

    def get_chart_data(self, **kwargs) -> dict[str, Any]:
        chart_id = str(kwargs.get("chart_id") or kwargs.get("graph_type") or "").strip()
        spec = CHART_SPECS.get(chart_id)
        if spec is None or not spec.renderable:
            return {"error": f"unsupported chart_id: {chart_id}"}

        raw_filters = kwargs.get("filters")
        filters = dict(raw_filters) if isinstance(raw_filters, dict) else {}
        for key in ("site_code", "site_text", "date_from", "date_to", "category", "vendor", "network_type", "min_minutes"):
            if key in kwargs and kwargs.get(key) not in (None, ""):
                filters[key] = kwargs.get(key)

        raw_max_points = kwargs.get("max_points")
        try:
            max_points = int(raw_max_points) if raw_max_points is not None else CHART_DATA_MAX_POINTS
        except (TypeError, ValueError):
            max_points = CHART_DATA_MAX_POINTS
        warnings: list[str] = []
        if max_points < 0:
            warnings.append(f"max_points raised from {max_points} to 0.")
            max_points = 0
        if max_points > CHART_DATA_MAX_POINTS:
            warnings.append(f"max_points clamped from {max_points} to {CHART_DATA_MAX_POINTS}.")
            max_points = CHART_DATA_MAX_POINTS

        title = str(kwargs.get("title") or spec.label)
        series_kwargs = dict(filters)
        series_kwargs["_prefer_site_slice"] = True
        labels, values, series = self._chart_series_for_spec(chart_id, series_kwargs)
        if not series:
            series = [{"label": str(label), "value": _chart_number(value) or 0.0} for label, value in zip(labels, values, strict=False)]
        series = [_normalize_chart_point(point) for point in series]
        total_points = len(series)
        returned_series = series[:max_points] if max_points > 0 else []
        if total_points > len(returned_series):
            warnings.append(f"Series truncated from {total_points} to {len(returned_series)} points.")

        labels = [str(point.get("label") or "") for point in returned_series]
        values = [_chart_number(point.get("value")) or 0.0 for point in returned_series]
        x_label, y_label = self._chart_axis_labels(spec.chart_kind)
        empty_state = None
        if total_points == 0:
            empty_state = {
                "title": "No chart data",
                "message": "No rows matched the selected chart and filters.",
            }

        return {
            "chart_id": chart_id,
            "chart_kind": spec.chart_kind,
            "title": title,
            "labels": labels,
            "values": values,
            "series": returned_series,
            "x_axis": {"label": x_label},
            "y_axis": {"label": y_label},
            "warnings": warnings,
            "data_quality": {
                "total_points": total_points,
                "returned_points": len(returned_series),
                "truncated": total_points > len(returned_series),
            },
            "query_context": {
                "filters": _sanitize_mcp_value(filters),
                "max_points": max_points,
            },
            "empty_state": empty_state,
        }

    def render_chart_widget(self, **kwargs) -> dict[str, Any]:
        chart_id = str(kwargs.get("chart_id") or "").strip()
        if not chart_id:
            return {"error": "chart_id is required"}
        chart_kind = str(kwargs.get("chart_kind") or "bar").strip() or "bar"
        title = str(kwargs.get("title") or chart_id)
        labels = kwargs.get("labels") if isinstance(kwargs.get("labels"), list) else []
        values = kwargs.get("values") if isinstance(kwargs.get("values"), list) else []
        series = kwargs.get("series") if isinstance(kwargs.get("series"), list) else []
        series = [_normalize_chart_point(point) for point in series]
        if not series:
            series = [
                {"label": str(label), "value": _chart_number(values[index] if index < len(values) else None) or 0.0}
                for index, label in enumerate(labels)
            ]
        labels = [str(point.get("label") or "") for point in series]
        values = [_chart_number(point.get("value")) or 0.0 for point in series]
        warnings = kwargs.get("warnings") if isinstance(kwargs.get("warnings"), list) else []
        data_quality = kwargs.get("data_quality") if isinstance(kwargs.get("data_quality"), dict) else {}
        query_context = kwargs.get("query_context") if isinstance(kwargs.get("query_context"), dict) else {}
        empty_state = kwargs.get("empty_state") if isinstance(kwargs.get("empty_state"), dict) else None
        return {
            "chart_id": chart_id,
            "chart_kind": chart_kind,
            "title": title,
            "labels": _sanitize_mcp_value(labels),
            "values": _sanitize_mcp_value(values),
            "series": _sanitize_mcp_value(series),
            "x_axis": _sanitize_mcp_value(kwargs.get("x_axis") if isinstance(kwargs.get("x_axis"), dict) else {}),
            "y_axis": _sanitize_mcp_value(kwargs.get("y_axis") if isinstance(kwargs.get("y_axis"), dict) else {}),
            "warnings": _sanitize_mcp_value(warnings),
            "data_quality": _sanitize_mcp_value(data_quality),
            "query_context": _sanitize_mcp_value(query_context),
            "empty_state": _sanitize_mcp_value(empty_state),
            "_meta": {
                "openai/outputTemplate": CHART_WIDGET_URI,
                "ui": {"resourceUri": CHART_WIDGET_URI},
            },
        }

    def generate_graph(self, **kwargs) -> dict[str, Any]:
        graph_type = str(kwargs.get("graph_type") or "alarm_category_counts").strip()
        spec = CHART_SPECS.get(graph_type)
        if spec is None or not spec.renderable:
            return {"error": f"unsupported graph_type: {graph_type}"}

        site_code = normalize_site_key(kwargs.get("site_code") or kwargs.get("site_text") or "")
        title = str(kwargs.get("title") or spec.label)
        series_kwargs = dict(kwargs)
        series_kwargs["_prefer_site_slice"] = True
        labels, values, series = self._chart_series_for_spec(graph_type, series_kwargs)
        if not series:
            series = [{"label": str(label), "value": float(value)} for label, value in zip(labels, values, strict=False)]

        path = _safe_export_path(self.export_dir / "charts", f"{title}_{site_code or 'all'}", "png")
        self._draw_chart(path, title, labels, values, chart_kind=spec.chart_kind, series=series)
        image_bytes = path.read_bytes()
        width, height = Image.open(BytesIO(image_bytes)).size
        return {
            "path": str(path),
            "graph_type": graph_type,
            "chart_kind": spec.chart_kind,
            "site_code": site_code,
            "points": len(series) if series else len(values),
            "labels": labels,
            "values": values,
            "series": _sanitize_mcp_value(series),
            "mime_type": "image/png",
            "image_base64": base64.b64encode(image_bytes).decode("ascii"),
            "width": int(width),
            "height": int(height),
        }

    def get_computed_report(self, **kwargs) -> dict[str, Any]:
        report_type = str(kwargs.get("report_type") or "").strip().lower()
        if report_type.startswith("chart:"):
            report_type = report_type[len("chart:"):].strip()

        include_raw_json = bool(kwargs.get("include_raw_json", False))
        best: tuple[pd.DataFrame, str, str, int] | None = None
        try:
            for sheet_name in book.sheet_names:
                df = pd.read_excel(book, sheet_name=sheet_name, dtype=object)
                site_col = infer_site_id_column(df, reference_df)
                if not site_col:
                    continue
                keys = {normalize_site_key(v) for v in df[site_col].dropna().tolist() if normalize_site_key(v)}
                score = len(keys)
                if best is None or score > best[3]:
                    best = (df, sheet_name, site_col, score)
        finally:
            try:
                book.close()
            except Exception:
                pass
        if best is None:
            raise ValueError("Could not identify a site ID column in the uploaded workbook.")
        return best[0], best[1], best[2]

    def _alarm_reference_df(self) -> pd.DataFrame:
        try:
            values = self._with_alarm_source(lambda: alarm_store.distinct_values("site_id")) or []
        except Exception:
            values = []
        return pd.DataFrame({"site_id": values})

    def _alarm_rows_for_sites(
        self,
        site_keys: set[str],
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> pd.DataFrame:
        if not site_keys:
            return pd.DataFrame()
        query = alarm_store.AlarmQuery(
            site_scope_keys=site_keys,
            date_from=date_from,
            date_to=date_to,
            sort_by="occurred_on",
            limit=None,
            offset=0,
        )
        return self._with_alarm_source(lambda: alarm_store.query_alarms(query))

    def _alarm_rows_for_pm_sheet(self, pm_df: pd.DataFrame, site_col: str, date_col: str) -> pd.DataFrame:
        site_keys = collect_site_sheet_keys(pm_df, site_col)
        dates = pd.to_datetime(pm_df[date_col], errors="coerce", format="mixed")
        valid_dates = [pd.Timestamp(v).date() for v in dates.dropna().tolist()]
        date_from = min(valid_dates) - timedelta(days=1) if valid_dates else None
        date_to = max(valid_dates) + timedelta(days=1) if valid_dates else None
        return self._alarm_rows_for_sites(site_keys, date_from=date_from, date_to=date_to)

    def _export_site_dossier_workbook(
        self,
        *,
        site_code: str,
        alarm_df: pd.DataFrame,
        bdt_rows: list[dict[str, Any]],
        bdt_details: list[dict[str, Any]],
    ) -> Path:
        path = _safe_export_path(self.export_dir, f"site_dossier_{site_code}", "xlsx")
        rules: list[dict[str, Any]] = []
        photos: list[dict[str, Any]] = []
        discharge_rows: list[dict[str, Any]] = []
        for detail in bdt_details:
            bdt = detail.get("bdt") if isinstance(detail.get("bdt"), dict) else {}
            run_id = detail.get("validation_run_id")
            for rule in detail.get("rules", []) if isinstance(detail.get("rules"), list) else []:
                if isinstance(rule, dict):
                    rules.append({"validation_run_id": run_id, **rule})
            for photo in detail.get("photos", []) if isinstance(detail.get("photos"), list) else []:
                if isinstance(photo, dict):
                    photos.append({"validation_run_id": run_id, **photo})
            for reading in bdt.get("discharge_readings", []) if isinstance(bdt, dict) else []:
zsh:1: command not found: python

exec
/bin/zsh -lc "grep -n \"def _with_alarm_source\\|class AlarmQuery\\|def query_alarms\" -n llm_tools/service.py llm_tools/alarm_store.py && sed -n '230,340p' llm_tools/alarm_store.py && sed -n '340,460p' llm_tools/alarm_store.py && sed -n '520,610p' llm_tools/service.py" in /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
 exited 2 in 0ms:
grep: llm_tools/alarm_store.py: No such file or directory
llm_tools/service.py:952:    def _with_alarm_source(self, fn):
llm_tools/service.py:985:    def query_alarms(self, **kwargs) -> dict[str, Any]:

exec
/bin/zsh -lc "grep -R \"class AlarmQuery\\|def query_alarms\" -n . | head -20 && sed -n '920,1010p' llm_tools/service.py" in /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
2026-06-04T15:18:36.300547Z ERROR codex_core::tools::router: error=write_stdin failed: stdin is closed for this session; rerun exec_command with tty=true to keep stdin open
 succeeded in 17185ms:
Binary file ./.gitnexus/lbug matches
./web/routers/alarms.py:36:def query_alarms(db: Session = Depends(get_db),
./llm_tools/service.py:985:    def query_alarms(self, **kwargs) -> dict[str, Any]:
./tests/test_llm_tools.py:1472:        def query_alarms(self, **kwargs):
./tests/test_llm_tools.py:1496:        def query_alarms(self, **kwargs):
./tests/test_llm_tools.py:1506:        def query_alarms(self, **kwargs):
./tests/test_llm_tools.py:1516:        def query_alarms(self, **kwargs):
./tests/test_llm_tools.py:1526:        def query_alarms(self, **kwargs):
./tests/test_llm_tools.py:1563:        def query_alarms(self, **kwargs):
./tests/test_llm_tools.py:1575:        def query_alarms(self, **kwargs):
./tests/test_llm_tools.py:2309:        def query_alarms(self, **kwargs):
./tests/test_llm_tools.py:2319:        def query_alarms(self, **kwargs):
./tests/test_llm_tools.py:2329:        def query_alarms(self, **kwargs):
./tests/test_llm_tools.py:3726:        def query_alarms(self, **kwargs):
./docs/plans/2026-04-22-alarm-db-driven-migration-plan.md:66:class AlarmQuery:
./docs/plans/2026-04-22-alarm-db-driven-migration-plan.md:86:def query_alarms(q: AlarmQuery) -> pd.DataFrame
./.scratch/codex-review-pr17-r2.md:658:/bin/zsh -lc "grep -n \"def _with_alarm_source\\|class AlarmQuery\\|def query_alarms\" -n llm_tools/service.py llm_tools/alarm_store.py && sed -n '230,340p' llm_tools/alarm_store.py && sed -n '340,460p' llm_tools/alarm_store.py && sed -n '520,610p' llm_tools/service.py" in /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
./.scratch/codex-review-pr17-r2.md:662:llm_tools/service.py:985:    def query_alarms(self, **kwargs) -> dict[str, Any]:
./.scratch/codex-review-pr17-r2.md:665:/bin/zsh -lc "grep -R \"class AlarmQuery\\|def query_alarms\" -n . | head -20 && sed -n '920,1010p' llm_tools/service.py" in /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
./data/alarm_store.py:75:class AlarmQuery:
        validation_error = federated_site.validate_admin_sql(sql)
        if validation_error is not None:
            return {
                "rows": [],
                "returned": 0,
                "limit": limit,
                "offset": offset,
                "has_more": False,
                "total": 0,
                "error": _sanitize_mcp_value(validation_error),
            }
        frames = self._admin_sql_view_frames()
        payload = federated_site.run_admin_sql(
            sql,
            frames,
            limit=limit,
            offset=offset,
        )
        run_warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
        source_warnings = getattr(self, "_admin_sql_source_warnings", [])
        if source_warnings:
            payload["source_warnings"] = list(source_warnings)
            run_warnings = [*run_warnings, *payload["source_warnings"]]

        if run_warnings:
            payload["warnings"] = run_warnings
        if isinstance(payload.get("rows"), list):
            payload["rows"] = _sanitize_mcp_records(payload["rows"])
        if payload.get("error") is not None:
            payload["error"] = _sanitize_mcp_value(payload["error"])
        return _jsonable(payload)

    def _with_alarm_source(self, fn):
        previous = alarm_store.ALARM_DB_FILE
        last_result = None
        last_error: Exception | None = None
        for path in (state.ALARM_DB_FILE, state.ALARM_DB_FALLBACK_FILE):
            if not Path(path).exists():
                continue
            try:
                alarm_store.set_alarm_db_file(path)
                result = fn()
                last_result = result
                if isinstance(result, pd.DataFrame):
                    if not result.empty:
                        return result
                elif isinstance(result, dict):
                    if int(result.get("total") or result.get("row_count") or 0) > 0:
                        return result
                elif result:
                    return result
            except Exception as exc:
                last_error = exc
                continue
            finally:
                alarm_store.set_alarm_db_file(previous)
        if last_result is not None:
            return last_result
        try:
            return fn()
        except Exception:
            if last_error is not None:
                raise last_error from None
            raise

    def query_alarms(self, **kwargs) -> dict[str, Any]:
        q = alarm_store.AlarmQuery(
            site_text=str(kwargs.get("site_text") or kwargs.get("site_id") or ""),
            category=str(kwargs.get("category") or "All"),
            vendor=str(kwargs.get("vendor") or "All"),
            network_type=str(kwargs.get("network_type") or "All"),
            date_from=_date_value(kwargs.get("date_from")),
            date_to=_date_value(kwargs.get("date_to")),
            sort_by=str(kwargs.get("sort_by") or "occurred_on"),
            sort_desc=bool(kwargs.get("sort_desc", False)),
            limit=_limit(kwargs.get("limit"), default=100),
            offset=max(int(kwargs.get("offset") or 0), 0),
        )
        df = self._with_alarm_source(lambda: alarm_store.query_alarms(q))
        return {"rows": _df_records(df), "row_count": len(df)}

    def query_alarm_events(self, **kwargs) -> dict[str, Any]:
        sort_direction = str(kwargs.get("sort_direction") or "").strip().lower()
        sort_by = str(kwargs.get("sort_by") or "occurred_on").strip() or "occurred_on"
        sort_desc = bool(kwargs.get("sort_desc", False))
        if sort_direction in {"asc", "desc"}:
            sort_desc = sort_direction == "desc"

        site_raw = (
            str(kwargs.get("site_code") or "")
            if str(kwargs.get("site_code") or "")

exec
/bin/zsh -lc "sed -n '1,180p' data/alarm_store.py && sed -n '180,360p' data/alarm_store.py && sed -n '360,520p' data/alarm_store.py" in /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
 succeeded in 0ms:
"""DuckDB-backed alarm access and query layer."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from alarm_app.core.classify import classify_by_alarm_id, compute_site_down_flag
    from alarm_app.core.duration import duration_to_secs, secs_to_hhmmss
except ImportError:
    from core.classify import classify_by_alarm_id, compute_site_down_flag
    from core.duration import duration_to_secs, secs_to_hhmmss

STATE_DIR = Path.home() / ".alarm_viewer"
ALARM_DB_FILE = STATE_DIR / "alarms.duckdb"
ALARM_TABLE = "alarm_records"
_log = logging.getLogger(__name__)
_LOCK_WARNING_EMITTED = False

_COLUMN_WHITELIST = {
    "site_id",
    "alarm_name",
    "alarm_id",
    "network_type",
    "vendor",
    "occurred_on",
    "cleared_on",
    "duration",
    "_duration_secs",
    "clearance_status",
    "alarm_source",
    "site_down_flag",
    "alarm_category",
    "file_source",
}
_SORTABLE_COLUMNS = {
    "site_id",
    "alarm_name",
    "alarm_id",
    "network_type",
    "vendor",
    "occurred_on",
    "cleared_on",
    "duration",
    "_duration_secs",
    "clearance_status",
    "alarm_source",
    "site_down_flag",
    "alarm_category",
    "file_source",
}
_TEXT_COLUMN_FILTERS = {
    "site_id",
    "alarm_name",
    "alarm_id",
    "network_type",
    "vendor",
    "duration",
    "clearance_status",
    "alarm_source",
    "site_down_flag",
    "alarm_category",
    "file_source",
}


@dataclass(slots=True)
class AlarmQuery:
    site_text: str = ""
    category: str = "All"
    vendor: str = "All"
    network_type: str = "All"
    min_duration_secs: float | None = None
    date_from: date | datetime | None = None
    date_to: date | datetime | None = None
    manual_days: Iterable[date | datetime | pd.Timestamp | str] | None = None
    both_pd: bool = False
    sort_by: str | None = None
    sort_desc: bool = False
    limit: int | None = None
    offset: int = 0
    site_scope_keys: Iterable[str] | None = None
    allowed_values: dict[str, Iterable[Any] | None] = field(default_factory=dict)
    column_filters: dict[str, Iterable[Any] | None] = field(default_factory=dict)
    col_filters: dict[str, Iterable[Any] | None] = field(default_factory=dict)


def set_alarm_db_file(path: Path) -> None:
    global ALARM_DB_FILE
    ALARM_DB_FILE = Path(path)


def _connect(*, read_only: bool = False):
    import duckdb

    if not read_only:
        ALARM_DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(ALARM_DB_FILE), read_only=read_only)


def _safe_connect(*, read_only: bool = False):
    global _LOCK_WARNING_EMITTED
    try:
        con = _connect(read_only=read_only)
        _LOCK_WARNING_EMITTED = False
        return con
    except Exception as exc:
        mode = "read-only" if read_only else "read-write"
        if not _LOCK_WARNING_EMITTED:
            _log.warning(
                "Alarm store connection failed (%s): %s (%s)",
                mode,
                ALARM_DB_FILE,
                exc,
            )
            _LOCK_WARNING_EMITTED = True
        return None


def _table_exists(con) -> bool:
    count = con.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema = 'main' AND table_name = ?
        """,
        [ALARM_TABLE],
    ).fetchone()[0]
    return bool(count)


def _table_columns(con) -> set[str]:
    if not _table_exists(con):
        return set()
    rows = con.execute(f"PRAGMA table_info('{ALARM_TABLE}')").fetchall()
    return {str(row[1]) for row in rows}


def _normalize_site_key(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().upper()
    if not text:
        return ""
    return "".join(ch for ch in text if ch.isalnum())


def _normalize_manual_days(values: Iterable[date | datetime | pd.Timestamp | str] | None) -> list[date]:
    out: list[date] = []
    seen: set[date] = set()
    for value in values or []:
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            continue
        day = pd.Timestamp(parsed).date()
        if day not in seen:
            out.append(day)
            seen.add(day)
    return out


def _range_start(value: date | datetime | None) -> datetime | None:
    if value is None:
        return None
    ts = pd.Timestamp(value)
    if pd.isna(ts):
        return None
    return ts.to_pydatetime()


def _range_end_exclusive(value: date | datetime | None) -> datetime | None:
    if value is None:
        return None
        return None
    ts = pd.Timestamp(value)
    if pd.isna(ts):
        return None
    return (ts.normalize() + pd.Timedelta(days=1)).to_pydatetime()


def _load_alarm_ids() -> dict[str, list[str]]:
    try:
        try:
            from alarm_app.data import state as _state
        except ImportError:
            from data import state as _state
    except ImportError:
        _state = None
    if _state is None:
        return {"power": [], "down": [], "door": []}
    try:
        data = _state.load_alarm_ids()
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    return {
        "power": [str(v).strip() for v in data.get("power", [])],
        "down": [str(v).strip() for v in data.get("down", [])],
        "door": [str(v).strip() for v in data.get("door", [])],
    }


def _ensure_derived_fields(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if out.empty:
        for col in ("alarm_category", "site_down_flag", "duration", "_duration_secs"):
            if col not in out.columns:
                out[col] = pd.Series(dtype="object")
        return out

    for col in ("occurred_on", "cleared_on"):
        if col in out.columns:
            out[col] = pd.to_datetime(out[col], errors="coerce", format="mixed")

    if "duration" not in out.columns:
        out["duration"] = ""

    if {"occurred_on", "cleared_on", "duration"}.issubset(out.columns):
        missing_duration = out["duration"].fillna("").astype(str).str.strip().eq("")
        has_times = missing_duration & out["occurred_on"].notna() & out["cleared_on"].notna()
        if has_times.any():
            delta_secs = (out.loc[has_times, "cleared_on"] - out.loc[has_times, "occurred_on"]).dt.total_seconds()
            out.loc[has_times, "duration"] = delta_secs.apply(secs_to_hhmmss)

    out["_duration_secs"] = out["duration"].apply(duration_to_secs).astype(float)
    out["duration"] = out["_duration_secs"].apply(secs_to_hhmmss)

    if "alarm_category" not in out.columns:
        out["alarm_category"] = ""
    out = classify_by_alarm_id(out, _load_alarm_ids())
    out["alarm_category"] = out["alarm_category"].fillna("").astype(str)
    out = compute_site_down_flag(out)
    if "site_down_flag" not in out.columns:
        out["site_down_flag"] = "No"
    out["site_down_flag"] = out["site_down_flag"].fillna("No").astype(str)
    return out


def replace_alarm_table(df: pd.DataFrame) -> None:
    prepared = _ensure_derived_fields(df if df is not None else pd.DataFrame())
    con = _connect(read_only=False)
    try:
        con.execute(f"DROP TABLE IF EXISTS {ALARM_TABLE}")
        con.register("prepared_df", prepared)
        con.execute(f"CREATE TABLE {ALARM_TABLE} AS SELECT * FROM prepared_df")
        con.unregister("prepared_df")
    finally:
        con.close()


def _build_where_clause(q: AlarmQuery, table_cols: set[str]) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []

    if q.site_scope_keys and "site_id" in table_cols:
        keys = [_normalize_site_key(v) for v in q.site_scope_keys]
        keys = [v for v in keys if v]
        if keys:
            placeholders = ", ".join(["?"] * len(keys))
            clauses.append(
                "regexp_replace(upper(COALESCE(CAST(site_id AS VARCHAR), '')), '[^A-Z0-9]', '', 'g') "
                f"IN ({placeholders})"
            )
            params.extend(keys)

    if q.site_text:
        terms = [t.strip().upper() for t in str(q.site_text).split(",") if t.strip()]
        if terms:
            term_clauses: list[str] = []
            for term in terms:
                like = f"%{term}%"
                if "site_id" in table_cols:
                    term_clauses.append("upper(COALESCE(CAST(site_id AS VARCHAR), '')) LIKE ?")
                    params.append(like)
                if "alarm_source" in table_cols:
                    term_clauses.append("upper(COALESCE(CAST(alarm_source AS VARCHAR), '')) LIKE ?")
                    params.append(like)
            if term_clauses:
                clauses.append("(" + " OR ".join(term_clauses) + ")")

    if "occurred_on" in table_cols:
        range_parts: list[str] = []
        range_start = _range_start(q.date_from)
        range_end = _range_end_exclusive(q.date_to)
        if range_start is not None:
            range_parts.append("occurred_on >= ?")
            params.append(range_start)
        if range_end is not None:
            range_parts.append("occurred_on < ?")
            params.append(range_end)
        range_clause = "(" + " AND ".join(range_parts) + ")" if range_parts else ""

        days = _normalize_manual_days(q.manual_days)
        day_clause = ""
        if days:
            placeholders = ", ".join(["?"] * len(days))
            day_clause = f"CAST(occurred_on AS DATE) IN ({placeholders})"
            params.extend(days)

        if range_clause and day_clause:
            clauses.append(f"({range_clause} OR {day_clause})")
        elif range_clause:
            clauses.append(range_clause)
        elif day_clause:
            clauses.append(day_clause)

    if q.category and q.category != "All" and "alarm_category" in table_cols:
        clauses.append("COALESCE(CAST(alarm_category AS VARCHAR), '') = ?")
        params.append(str(q.category))

    if q.network_type and q.network_type != "All" and "network_type" in table_cols:
        clauses.append("COALESCE(CAST(network_type AS VARCHAR), '') = ?")
        params.append(str(q.network_type))

    if q.vendor and q.vendor != "All" and "vendor" in table_cols:
        clauses.append("upper(COALESCE(CAST(vendor AS VARCHAR), '')) = ?")
        params.append(str(q.vendor).upper())

    if q.min_duration_secs is not None and "_duration_secs" in table_cols:
        clauses.append("COALESCE(_duration_secs, 0) >= ?")
        params.append(float(q.min_duration_secs))

    merged_column_filters: dict[str, Iterable[Any] | None] = {}
    merged_column_filters.update(q.allowed_values or {})
    merged_column_filters.update(q.column_filters or {})
    merged_column_filters.update(q.col_filters or {})

    for col, raw_allowed in merged_column_filters.items():
        if raw_allowed is None:
            continue
        if col not in _TEXT_COLUMN_FILTERS or col not in table_cols:
            continue
        allowed = [str(v) for v in raw_allowed]
        if not allowed:
            clauses.append("1 = 0")
            continue
        placeholders = ", ".join(["?"] * len(allowed))
        clauses.append(f"COALESCE(CAST({col} AS VARCHAR), '') IN ({placeholders})")
        params.extend(allowed)

    if q.both_pd and {"site_id", "alarm_category"}.issubset(table_cols):
        clauses.append(
            f"""
            site_id IN (
                SELECT site_id
                FROM {ALARM_TABLE}
                WHERE site_id IS NOT NULL
                GROUP BY site_id
                HAVING
                    SUM(CASE WHEN alarm_category = 'Power' THEN 1 ELSE 0 END) > 0
                    AND
                    SUM(CASE WHEN alarm_category = 'Down' THEN 1 ELSE 0 END) > 0
            )
            )
            """
        )

    if not clauses:
        return "", params
    return " WHERE " + " AND ".join(clauses), params


def query_alarms(q: AlarmQuery) -> pd.DataFrame:
    if not ALARM_DB_FILE.exists():
        return pd.DataFrame()
    con = _safe_connect(read_only=True)
    if con is None:
        return pd.DataFrame()
    try:
        table_cols = _table_columns(con)
        if not table_cols:
            return pd.DataFrame()
        where_sql, params = _build_where_clause(q, table_cols)
        sql = f"SELECT * FROM {ALARM_TABLE}{where_sql}"

        sort_by = q.sort_by if q.sort_by in _SORTABLE_COLUMNS and q.sort_by in table_cols else None
        if sort_by:
            direction = "DESC" if q.sort_desc else "ASC"
            sql += f" ORDER BY {sort_by} {direction} NULLS LAST"

        if q.limit is not None:
            limit = max(int(q.limit), 0)
            sql += " LIMIT ?"
            params.append(limit)
        if q.offset:
            offset = max(int(q.offset), 0)
            sql += " OFFSET ?"
            params.append(offset)

        return con.execute(sql, params).fetchdf()
    finally:
        con.close()


def count_alarms(q: AlarmQuery) -> int:
    if not ALARM_DB_FILE.exists():
        return 0
    con = _safe_connect(read_only=True)
    if con is None:
        return 0
    try:
        table_cols = _table_columns(con)
        if not table_cols:
            return 0
        where_sql, params = _build_where_clause(q, table_cols)
        row = con.execute(f"SELECT COUNT(*) FROM {ALARM_TABLE}{where_sql}", params).fetchone()
        return int(row[0] if row else 0)
    finally:
        con.close()


def distinct_values(column: str, q: AlarmQuery | None = None) -> list[str]:
    if column not in _COLUMN_WHITELIST:
        raise ValueError(f"Unsupported column: {column}")
    if not ALARM_DB_FILE.exists():
        return []
    con = _safe_connect(read_only=True)
    if con is None:
        return []
    try:
        table_cols = _table_columns(con)
        if column not in table_cols:
            return []
        normalized_q = replace(q, sort_by=None, limit=None, offset=0) if q else AlarmQuery()
        where_sql, params = _build_where_clause(normalized_q, table_cols)
        sql = (
            f"SELECT DISTINCT COALESCE(CAST({column} AS VARCHAR), '') AS value "
            f"FROM {ALARM_TABLE}{where_sql} ORDER BY value ASC"
        )
        rows = con.execute(sql, params).fetchall()
        return [str(row[0]) for row in rows]
    finally:
        con.close()


def stats(q: AlarmQuery | None = None) -> dict[str, int | float]:
    empty_stats = {
        "total": 0,
        "power": 0,
        "down": 0,
        "door": 0,
        "temp": 0,
        "sites": 0,
        "avg_duration_secs": 0.0,
    }
    if not ALARM_DB_FILE.exists():
        return empty_stats
    con = _safe_connect(read_only=True)
    if con is None:
        return empty_stats
    try:
        table_cols = _table_columns(con)
        if not table_cols:
            return empty_stats
        normalized_q = replace(q, sort_by=None, limit=None, offset=0) if q else AlarmQuery()
        where_sql, params = _build_where_clause(normalized_q, table_cols)
        row = con.execute(
            f"""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN alarm_category = 'Power' THEN 1 ELSE 0 END) AS power,
                SUM(CASE WHEN alarm_category = 'Down' THEN 1 ELSE 0 END) AS down,
                SUM(CASE WHEN alarm_category = 'Door' THEN 1 ELSE 0 END) AS door,
                SUM(CASE WHEN alarm_category = 'Temp' THEN 1 ELSE 0 END) AS temp,
                COUNT(DISTINCT site_id) AS sites,
                COALESCE(AVG(_duration_secs), 0) AS avg_duration_secs
            FROM {ALARM_TABLE}{where_sql}
            """,
            params,
        ).fetchone()
        return {
            "total": int(row[0] or 0),
            "power": int(row[1] or 0),
            "down": int(row[2] or 0),
            "door": int(row[3] or 0),
            "temp": int(row[4] or 0),
            "sites": int(row[5] or 0),
            "avg_duration_secs": float(row[6] or 0.0),
        }
    finally:
        con.close()


def load_alarm_slice_for_bdt(
    site_codes: list[str],
    date_from: datetime | None,
    date_to: datetime | None,
) -> pd.DataFrame:
    query = AlarmQuery(
        site_scope_keys=site_codes or None,
        date_from=date_from,
        date_to=date_to,
        sort_by="occurred_on",
        sort_desc=False,
    )
    return query_alarms(query)


def load_all_alarms() -> pd.DataFrame:
    if not ALARM_DB_FILE.exists():
        return pd.DataFrame()
    con = _safe_connect(read_only=True)
    if con is None:
        return pd.DataFrame()
    try:
        if not _table_exists(con):
            return pd.DataFrame()
        return con.execute(f"SELECT * FROM {ALARM_TABLE}").fetchdf()
    finally:
        con.close()


def occurred_on_bounds() -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    if not ALARM_DB_FILE.exists():

exec
/bin/zsh -lc "python3 -m pytest tests/test_llm_tools.py -k 'chart_data or generate_graph' -q" in /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
 exited 2 in 1497ms:

==================================== ERRORS ====================================
___________________ ERROR collecting tests/test_llm_tools.py ___________________
ImportError while importing test module '/Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604/tests/test_llm_tools.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/opt/homebrew/Cellar/python@3.14/3.14.0/Frameworks/Python.framework/Versions/3.14/lib/python3.14/importlib/__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/test_llm_tools.py:13: in <module>
    import pandas as pd
E   ModuleNotFoundError: No module named 'pandas'
=========================== short test summary info ============================
ERROR tests/test_llm_tools.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.86s

exec
/bin/zsh -lc "nl -ba AGENTS.md | sed -n '1,45p'; nl -ba CLAUDE.md | sed -n '135,178p'; nl -ba llm_tools/service.py | sed -n '1487,1505p'" in /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
 succeeded in 102ms:
exec
/bin/zsh -lc "git show 9f2c094ebbf8cc88a39f0c6dd514dff331adb852:llm_tools/service.py | sed -n '1488,1518p'; grep -R \"min_minutes\\|min_duration\" -n llm_tools tests | head -60" in /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
 succeeded in 286ms:
llm_tools/service.py:1060:        min_minutes = float(kwargs.get("min_minutes") or 0)
llm_tools/service.py:1087:                    "min_minutes": min_minutes,
llm_tools/service.py:1088:                    "threshold_minutes": min_minutes,
llm_tools/service.py:1094:            if min_minutes > 0:
llm_tools/service.py:1095:                working = working[working["_backup_td"] > pd.Timedelta(minutes=min_minutes)].copy()
llm_tools/service.py:1103:                    "min_minutes": min_minutes,
llm_tools/service.py:1104:                    "threshold_minutes": min_minutes,
llm_tools/service.py:1134:                "min_minutes": min_minutes,
llm_tools/service.py:1135:                "threshold_minutes": min_minutes,
llm_tools/service.py:1701:            min_minutes=kwargs.get("min_minutes"),
llm_tools/service.py:1796:        for key in ("site_code", "site_text", "date_from", "date_to", "category", "vendor", "network_type", "min_minutes"):
llm_tools/service.py:1989:                min_minutes=kwargs.get("min_minutes"),
llm_tools/service.py:2011:                "min_minutes": payload.get("min_minutes") if isinstance(payload, dict) else None,
llm_tools/tools.py:118:            "min_minutes": {"type": "number", "minimum": 0},
llm_tools/tools.py:128:            "min_minutes": {"type": "number"},
llm_tools/tools.py:309:                "description": "Optional safe chart filters such as site_code, site_text, date_from, date_to, category, vendor, network_type, and min_minutes.",
llm_tools/tools.py:395:            "min_minutes": {"type": "number", "minimum": 0},
llm_tools/tools.py:410:            "min_minutes": {"type": "number"},
Binary file llm_tools/__pycache__/service.cpython-313.pyc matches
Binary file llm_tools/__pycache__/service.cpython-314.pyc matches
Binary file llm_tools/__pycache__/tools.cpython-314.pyc matches
Binary file llm_tools/__pycache__/tools.cpython-313.pyc matches
tests/test_e2e_gui_viewer.py:274:            min_duration_secs=900,
tests/test_e2e_gui_viewer.py:282:        assert source_query.min_duration_secs == 900
tests/test_alarm_store.py:191:        min_duration_secs=1800,
Binary file tests/__pycache__/test_e2e_gui_viewer.cpython-313-pytest-9.0.3.pyc matches
Binary file tests/__pycache__/test_alarm_store.cpython-313-pytest-9.0.3.pyc matches
Binary file tests/__pycache__/test_temp_alarm.cpython-314-pytest-9.0.3.pyc matches
Binary file tests/__pycache__/test_llm_tools.cpython-314.pyc matches
Binary file tests/__pycache__/test_llm_tools.cpython-314-pytest-9.0.3.pyc matches
Binary file tests/__pycache__/test_alarm_cache_ui.cpython-314-pytest-9.0.3.pyc matches
Binary file tests/__pycache__/test_llm_tools.cpython-313-pytest-9.0.3.pyc matches
Binary file tests/__pycache__/test_alarm_cache_ui.cpython-313-pytest-9.0.3.pyc matches
Binary file tests/__pycache__/test_temp_alarm.cpython-313-pytest-9.0.3.pyc matches
Binary file tests/__pycache__/test_alarm_store.cpython-314-pytest-9.0.3.pyc matches
Binary file tests/__pycache__/test_e2e_gui_viewer.cpython-314-pytest-9.0.3.pyc matches
tests/test_alarm_cache_ui.py:248:    assert query.min_duration_secs == 900
tests/test_llm_tools.py:1051:    assert tools["query_backup_times"]["inputSchema"]["properties"]["min_minutes"]["minimum"] == 0
tests/test_llm_tools.py:1107:    result = service.query_backup_times(min_minutes=50, limit=100)
tests/test_llm_tools.py:1598:                "min_minutes": 5,
tests/test_llm_tools.py:1625:        "min_minutes": 5,
tests/test_llm_tools.py:1643:                "min_minutes": 0,
tests/test_llm_tools.py:2292:    result = dispatch_tool(_Service(), "query_backup_times", {"min_minutes": float("nan")})
tests/test_llm_tools.py:2294:    assert result == {"error": "invalid arguments for query_backup_times: min_minutes must be finite"}
tests/test_llm_tools.py:2302:    result = dispatch_tool(_Service(), "query_backup_times", {"min_minutes": float("inf")})
tests/test_llm_tools.py:2304:    assert result == {"error": "invalid arguments for query_backup_times: min_minutes must be finite"}
tests/test_temp_alarm.py:913:        min_duration_secs=900,
tests/test_temp_alarm.py:936:    assert calls[1].min_duration_secs == 900

exec
/bin/zsh -lc "ls -d .venv venv 2>/dev/null || true && (test -x .venv/bin/python && .venv/bin/python -m pytest tests/test_llm_tools.py -k 'chart_data or generate_graph' -q || true)" in /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
 succeeded in 2949ms:
......                                                                   [100%]
6 passed, 319 deselected in 1.64s

codex
The service change is covered by targeted tests, but the patch corrupts the repo's GitNexus operating instructions by switching them to unavailable MCP tooling. That will break future required repository workflows.

Review comment:

- [P2] Keep GitNexus instructions on the CLI surface — /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604/AGENTS.md:4-14
  In this repo, GitNexus is configured as CLI-only, but these updated instructions now tell future agents to use MCP functions/resources such as `gitnexus_impact`, `gitnexus_query`, and `gitnexus://...`; those tools are unavailable/prohibited here, so agents following AGENTS.md/CLAUDE.md will fail the required impact/change-detection workflow before code work. Please keep this block on the documented CLI commands for this repo.
The service change is covered by targeted tests, but the patch corrupts the repo's GitNexus operating instructions by switching them to unavailable MCP tooling. That will break future required repository workflows.

Review comment:

- [P2] Keep GitNexus instructions on the CLI surface — /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604/AGENTS.md:4-14
  In this repo, GitNexus is configured as CLI-only, but these updated instructions now tell future agents to use MCP functions/resources such as `gitnexus_impact`, `gitnexus_query`, and `gitnexus://...`; those tools are unavailable/prohibited here, so agents following AGENTS.md/CLAUDE.md will fail the required impact/change-detection workflow before code work. Please keep this block on the documented CLI commands for this repo.
