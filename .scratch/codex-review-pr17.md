2026-06-04T15:04:39.036042Z ERROR codex_core::session::session: failed to load skill /Users/mikawi/.codex/plugins/cache/claude-plugins-official/convex-backend/1.0.0/skills/design/SKILL.md: invalid description: exceeds maximum length of 1024 characters
OpenAI Codex v0.136.0
--------
workdir: /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
model: gpt-5.5
provider: openai
approval: never
sandbox: workspace-write [workdir, /tmp, $TMPDIR]
reasoning effort: medium
reasoning summaries: none
session id: 019e932a-3911-7c41-9f27-913c5f1b62dd
--------
user
changes against 'main'
2026-06-04T15:04:40.100531Z ERROR codex_core::session::session: failed to load skill /Users/mikawi/.codex/plugins/cache/claude-plugins-official/convex-backend/1.0.0/skills/design/SKILL.md: invalid description: exceeds maximum length of 1024 characters
exec
/bin/zsh -lc "sed -n '1,220p' /Users/mikawi/.codex/skills/review/SKILL.md" in /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
 succeeded in 0ms:
---
name: review
description: Review the changes since a fixed point (commit, branch, tag, or merge-base) along two axes — Standards (does the code follow this repo's documented coding standards?) and Spec (does the code match what the originating issue/PRD asked for?). Runs both reviews in parallel sub-agents and reports them side by side. Use when the user wants to review a branch, a PR, work-in-progress changes, or asks to "review since X".
---

# Review

Two-axis review of the diff between `HEAD` and a fixed point the user supplies:

- **Standards** — does the code conform to this repo's documented coding standards?
- **Spec** — does the code faithfully implement the originating issue / PRD / spec?

Both axes run as **parallel sub-agents** so they don't pollute each other's context, then this skill aggregates their findings.

The issue tracker should have been provided to you — run `/setup-matt-pocock-skills` if `docs/agents/issue-tracker.md` is missing.

## Process

### 1. Pin the fixed point

Whatever the user said is the fixed point — a commit SHA, branch name, tag, `main`, `HEAD~5`, etc. Don't be opinionated; pass it through. If they didn't specify one, ask: "Review against what — a branch, a commit, or `main`?" Don't proceed until you have it.

Capture the diff command once: `git diff <fixed-point>...HEAD` (three-dot, so the comparison is against the merge-base). Also note the list of commits via `git log <fixed-point>..HEAD --oneline`.

### 2. Identify the spec source

Look for the originating spec, in this order:

1. Issue references in the commit messages (`#123`, `Closes #45`, GitLab `!67`, etc.) — fetch via the workflow in `docs/agents/issue-tracker.md`.
2. A path the user passed as an argument.
3. A PRD/spec file under `docs/`, `specs/`, or `.scratch/` matching the branch name or feature.
4. If nothing is found, ask the user where the spec is. If they say there isn't one, the **Spec** sub-agent will skip and report "no spec available".

### 3. Identify the standards sources

Anything in the repo that documents how code should be written. Common locations:

- `CLAUDE.md`, `AGENTS.md`
- `CONTRIBUTING.md`
- `CONTEXT.md`, `CONTEXT-MAP.md`, per-context `CONTEXT.md` files
- `docs/adr/` (architectural decisions are standards)
- `.editorconfig`, `eslint.config.*`, `biome.json`, `prettier.config.*`, `tsconfig.json` (machine-enforced standards — note them but don't re-check what tooling already checks)
- Any `STYLE.md`, `STANDARDS.md`, `STYLEGUIDE.md`, or similar at the repo root or under `docs/`

Collect the list of files. The **Standards** sub-agent will read them.

### 4. Spawn both sub-agents in parallel

Send a single message with two `Agent` tool calls. Use the `general-purpose` subagent for both.

**Standards sub-agent prompt** — include:

- The full diff command and commit list.
- The list of standards-source files you found in step 3.
- The brief: "Read the standards docs. Then read the diff. Report — per file/hunk where relevant — every place the diff violates a documented standard. Cite the standard (file + the rule). Distinguish hard violations from judgement calls. Skip anything tooling enforces. Under 400 words."

**Spec sub-agent prompt** — include:

- The diff command and commit list.
- The path or fetched contents of the spec.
- The brief: "Read the spec. Then read the diff. Report: (a) requirements the spec asked for that are missing or partial; (b) behaviour in the diff that wasn't asked for (scope creep); (c) requirements that look implemented but where the implementation looks wrong. Quote the spec line for each finding. Under 400 words."

If the spec is missing, skip the Spec sub-agent and note this in the final report.

### 5. Aggregate

Present the two reports under `## Standards` and `## Spec` headings, verbatim or lightly cleaned. Do **not** merge or rerank findings — the two axes are deliberately separate so the user can see them independently.

End with a one-line summary: total findings per axis, and the worst single issue (if any) flagged.

## Why two axes

A change can pass one axis and fail the other:

- Code that follows every standard but implements the wrong thing → **Standards pass, Spec fail.**
- Code that does exactly what the issue asked but breaks the project's conventions → **Spec pass, Standards fail.**

Reporting them separately stops one axis from masking the other.

exec
/bin/zsh -lc "grep -n \"alarm_app\\|BDT\\|ChatPanel\\|fetch_free_tool_models\" /Users/mikawi/.codex/memories/MEMORY.md | head -20" in /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
 succeeded in 0ms:
1:# Task Group: /Users/mikawi/Developer/orange/alarm_app BDT validation, summary import, and validation-artifact boundaries
2:scope: Use for alarm_app BDT work when the user wants deep repo mapping, R11/Summary Checklist debugging, or clarification about whether a workbook is production input vs one-off human validation evidence.
3:applies_to: cwd=/Users/mikawi/Developer/orange/alarm_app; reuse_rule=safe for this repo's BDT import/validation family, but real workbook paths and exact folder shapes are checkout-specific until rechecked
5:## Task 1: Deep dive BDT summary import and related service paths, success
9:- rollout_summaries/2026-06-01T05-32-38-kP20-bdt_summary_r11_hassan_lookup_fix.md (cwd=/Users/mikawi/Developer/orange/alarm_app, rollout_path=/Users/mikawi/.codex/sessions/2026/06/01/rollout-2026-06-01T08-32-38-019e81ab-788e-7291-b938-53bdf442a2f8.jsonl, updated_at=2026-06-01T05:56:36+00:00, thread_id=019e81ab-788e-7291-b938-53bdf442a2f8, parallel read-only deep dive across GUI import, storage, parser, validator, and tests)
10:- rollout_summaries/2026-06-01T05-35-57-CUSI-alarm_app_bdt_network_summary_obsidian_recap.md (cwd=/Users/mikawi/Developer/orange/alarm_app, rollout_path=/Users/mikawi/.codex/sessions/2026/06/01/rollout-2026-06-01T08-35-57-019e81ae-81b1-7a20-bd2a-144c55fc0500.jsonl, updated_at=2026-06-03T12:41:48+00:00, thread_id=019e81ae-81b1-7a20-bd2a-144c55fc0500, later Obsidian recap preserved the validated code-path conclusions, insight statuses, and correction history)
14:- BDT Summary, R11, Summary Checklist, data/catalog_import.py, data/catalog_store.py, db/repos/catalog_repo.py, bdt/parser.py, bdt/validator.py, data/loaders.py, summary_data, GitNexus, .venv, pytest
20:- rollout_summaries/2026-06-01T05-32-38-kP20-bdt_summary_r11_hassan_lookup_fix.md (cwd=/Users/mikawi/Developer/orange/alarm_app, rollout_path=/Users/mikawi/.codex/sessions/2026/06/01/rollout-2026-06-01T08-32-38-019e81ab-788e-7291-b938-53bdf442a2f8.jsonl, updated_at=2026-06-01T05:56:36+00:00, thread_id=019e81ab-788e-7291-b938-53bdf442a2f8, patched summary workbook discovery and added the HASSAN regression case)
24:- HASSAN, /Volumes/nvme 500/orange_developement_data/HASSAN, Huawei_BDT Summary_Last Update.xlsx, R11, No Summary sheet data available, external summary lookup, parent folder scan, summary-like workbook names, tests/test_parsers.py, by_site_date 7990
26:## Task 3: Inspect `BDT Acceptance Sheet_2026.xlsx` as human validation evidence, success
30:- rollout_summaries/2026-06-01T05-35-57-CUSI-alarm_app_bdt_network_summary_obsidian_recap.md (cwd=/Users/mikawi/Developer/orange/alarm_app, rollout_path=/Users/mikawi/.codex/sessions/2026/06/01/rollout-2026-06-01T08-35-57-019e81ae-81b1-7a20-bd2a-144c55fc0500.jsonl, updated_at=2026-06-03T12:41:48+00:00, thread_id=019e81ae-81b1-7a20-bd2a-144c55fc0500, comprehensive Excel MCP recap preserved the workbook structure and representative HASSAN examples)
34:- BDT Acceptance Sheet_2026.xlsx, Excel MCP, Accepted, Rejected, Final Status, severity, Batter ies Amp not real, human validation, acceptance workbook, Sheet1, Stolen - Not installed - Solar
40:- rollout_summaries/2026-06-01T05-35-57-CUSI-alarm_app_bdt_network_summary_obsidian_recap.md (cwd=/Users/mikawi/Developer/orange/alarm_app, rollout_path=/Users/mikawi/.codex/sessions/2026/06/01/rollout-2026-06-01T08-35-57-019e81ae-81b1-7a20-bd2a-144c55fc0500.jsonl, updated_at=2026-06-03T12:41:48+00:00, thread_id=019e81ae-81b1-7a20-bd2a-144c55fc0500, recap kept the mistake/correction sequence and separated it from later unrelated local files)
46:## Task 5: Write a durable Obsidian recap of the BDT/Network Summary session, success
50:- rollout_summaries/2026-06-01T05-35-57-CUSI-alarm_app_bdt_network_summary_obsidian_recap.md (cwd=/Users/mikawi/Developer/orange/alarm_app, rollout_path=/Users/mikawi/.codex/sessions/2026/06/01/rollout-2026-06-01T08-35-57-019e81ae-81b1-7a20-bd2a-144c55fc0500.jsonl, updated_at=2026-06-03T12:41:48+00:00, thread_id=019e81ae-81b1-7a20-bd2a-144c55fc0500, created the canonical Orange vault recap note with links back to the other battery/BDT notes)
54:- Obsidian, orange/2026-06-03 Alarm App BDT Network Summary Chat Summary.md, battery_backup_insights, battery_topology, session recap, Orange BDT Validation and Evidence Model, Orange Network Summary and BDT Snapshot Logging, obsidian://open
69:- BDT Summary import is a separate catalog pipeline from raw BDT validation: `import_bdt_summary_workbook` uses sheet names as reporting periods and merges per-period in SQLite and DuckDB, while raw BDTs go through `parse_bdt_file` and validation threads [Task 1]
72:- Summary discovery must still consider filenames containing `BDT` when they are clearly summary-like (`summary`, `weekly`, `battery update`, `acceptance`), and HASSAN-style trees may place the summary workbook one or two levels above the BDT files [Task 2]
73:- The real HASSAN smoke proved the fix: lookup moved from `by_site_date 0, by_site 0` to `by_site_date 7990, by_site 5116`, and `20` actual BDT files produced `16` matched summary rows [Task 2]
75:- The acceptance workbook is human validation / ground-truth evidence for comparing app output, not a raw BDT discharge workbook and not a production discovery rule [Task 3]

exec
/bin/zsh -lc 'git status --short && git log --oneline ce401c4d262c9362d3110036b9ea8f821d8a4719..HEAD && git diff --stat ce401c4d262c9362d3110036b9ea8f821d8a4719' in /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
 succeeded in 0ms:
 M .scratch/prds/chatgpt-chart-widget-ui.md
 M AGENTS.md
 M CLAUDE.md
?? .scratch/codex-review-pr17.md
?? .scratch/issues/chatgpt-chart-widget-ui/002-site-images-in-chatgpt.md
9f2c094 Add mcp_app/chart_widget package and chart-widget UI follow-up issues
02f9b5b Move ChatGPT chart surface from PNG images to Apps SDK widget
c2528ad Send generated charts through MCP image content
 .../001-donut-render-and-legend.md                 | 143 ++++
 .scratch/prds/chatgpt-chart-widget-ui.md           |  61 ++
 AGENTS.md                                          |  62 +-
 CLAUDE.md                                          |  60 +-
 llm_tools/charts.py                                | 185 +++++
 llm_tools/mcp_server.py                            |  71 +-
 llm_tools/openrouter_agent.py                      |   4 +-
 llm_tools/service.py                               | 764 +++++++++++++++++++--
 llm_tools/tools.py                                 | 113 ++-
 mcp_app/chart_widget/build.py                      |  19 +
 mcp_app/chart_widget/dist/chart.html               | 161 +++++
 mcp_app/chart_widget/package.json                  |   6 +
 mcp_app/chart_widget/src/chart_widget.ts           | 157 +++++
 tests/test_chat_panel.py                           |  14 +
 tests/test_e2e_backend.py                          | 102 ++-
 tests/test_llm_tools.py                            | 285 +++++++-
 ui/panels/chat_panel.py                            |  27 +-
 17 files changed, 2063 insertions(+), 171 deletions(-)

exec
/bin/zsh -lc 'gitnexus status -r /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604' in /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
 exited 1 in 130ms:
error: unknown option '-r'

exec
/bin/zsh -lc 'git diff ce401c4d262c9362d3110036b9ea8f821d8a4719 -- llm_tools/charts.py llm_tools/mcp_server.py llm_tools/openrouter_agent.py llm_tools/service.py llm_tools/tools.py ui/panels/chat_panel.py tests/test_llm_tools.py tests/test_e2e_backend.py tests/test_chat_panel.py mcp_app/chart_widget/src/chart_widget.ts mcp_app/chart_widget/build.py mcp_app/chart_widget/dist/chart.html' in /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
 succeeded in 0ms:
diff --git a/llm_tools/charts.py b/llm_tools/charts.py
new file mode 100644
index 0000000..9878c9a
--- /dev/null
+++ b/llm_tools/charts.py
@@ -0,0 +1,185 @@
+"""Shared chart catalog for AI, MCP, and computed chart reports."""
+
+from __future__ import annotations
+
+from dataclasses import asdict, dataclass
+from typing import Iterable
+
+
+@dataclass(frozen=True)
+class ChartSpec:
+    chart_id: str
+    label: str
+    chart_kind: str
+    family: str
+    description: str
+    renderable: bool = True
+    computed_report: bool = True
+
+    def to_dict(self) -> dict[str, object]:
+        return asdict(self)
+
+
+_CHARTS: tuple[ChartSpec, ...] = (
+    # Existing charts, preserved for compatibility.
+    ChartSpec("alarm_category_counts", "Alarm Category Counts", "bar", "alarm", "Count alarms by category or alarm name."),
+    ChartSpec("alarm_daily_counts", "Alarm Daily Counts", "bar", "alarm", "Count alarms per occurred date."),
+    ChartSpec("alarm_duration_by_category", "Alarm Duration By Category", "bar", "alarm", "Total alarm duration minutes by category."),
+    ChartSpec("bdt_verdict_counts", "BDT Verdict Counts", "bar", "bdt", "Count BDT validation verdicts."),
+    ChartSpec("bdt_duration_trend", "BDT Duration Trend", "bar", "bdt", "BDT discharge minutes by test date."),
+
+    # Alarm share/breakdown charts.
+    ChartSpec("alarm_category_share", "Alarm Category Share", "donut", "alarm", "Share of alarms by category."),
+    ChartSpec("vendor_alarm_share", "Vendor Alarm Share", "pie", "alarm", "Share of alarms by vendor."),
+    ChartSpec("network_type_share", "Network Type Share", "pie", "alarm", "Share of alarms by network type."),
+    ChartSpec("alarm_severity_share", "Alarm Severity Share", "pie", "alarm", "Share of alarms by severity when available."),
+    ChartSpec("cleared_vs_uncleared_share", "Cleared Vs Uncleared Share", "donut", "alarm", "Cleared alarms compared with active/uncleared alarms."),
+
+    # Time trend and comparative alarm charts.
+    ChartSpec("alarm_volume_trend", "Alarm Volume Trend", "line", "alarm", "Alarm volume over occurred date."),
+    ChartSpec("daily_power_alarm_trend", "Daily Power Alarm Trend", "line", "alarm", "Power alarm volume over time."),
+    ChartSpec("daily_down_alarm_trend", "Daily Down Alarm Trend", "line", "alarm", "Down alarm volume over time."),
+    ChartSpec("site_alarm_trend", "Site Alarm Trend", "line", "alarm", "Selected site alarm volume over time."),
+    ChartSpec("cumulative_alarm_volume", "Cumulative Alarm Volume", "line", "alarm", "Cumulative alarm count over time."),
+    ChartSpec("daily_alarms_by_category", "Daily Alarms By Category", "stacked_bar", "alarm", "Daily alarms split by category."),
+    ChartSpec("weekly_alarms_by_category", "Weekly Alarms By Category", "stacked_bar", "alarm", "Weekly alarms split by category."),
+    ChartSpec("stacked_alarm_category_area", "Stacked Alarm Category Area", "stacked_bar", "alarm", "Category volume over time as stacked totals."),
+    ChartSpec("stacked_vendor_area", "Stacked Vendor Area", "stacked_bar", "alarm", "Vendor volume over time as stacked totals."),
+    ChartSpec("vendor_by_category", "Vendor By Category", "stacked_bar", "alarm", "Vendor split by alarm category."),
+    ChartSpec("network_type_by_category", "Network Type By Category", "stacked_bar", "alarm", "Network type split by alarm category."),
+    ChartSpec("vendor_alarm_comparison", "Vendor Alarm Comparison", "grouped_bar", "alarm", "Compare alarm counts by vendor."),
+    ChartSpec("power_vs_down_by_site", "Power Vs Down By Site", "grouped_bar", "alarm", "Power and Down counts by site."),
+    ChartSpec("alarm_count_vs_duration_by_category", "Alarm Count Vs Duration By Category", "grouped_bar", "alarm", "Category alarm count beside total duration."),
+    ChartSpec("before_after_alarm_comparison", "Before After Alarm Comparison", "grouped_bar", "alarm", "Compare alarm counts across two periods when filters allow."),
+    ChartSpec("network_type_vendor_comparison", "Network Type Vendor Comparison", "grouped_bar", "alarm", "Compare vendor counts by network type."),
+
+    # Ranked and distribution charts.
+    ChartSpec("top_sites_by_alarm_count", "Top Sites By Alarm Count", "horizontal_bar", "alarm", "Sites with the most alarms."),
+    ChartSpec("top_sites_by_duration", "Top Sites By Duration", "horizontal_bar", "alarm", "Sites with the highest total duration."),
+    ChartSpec("top_sites_by_alarm_duration", "Top Sites By Alarm Duration", "horizontal_bar", "alarm", "Sites with the highest total duration."),
+    ChartSpec("top_alarm_names", "Top Alarm Names", "horizontal_bar", "alarm", "Most common alarm names."),
+    ChartSpec("top_alarm_ids", "Top Alarm IDs", "horizontal_bar", "alarm", "Most common alarm IDs."),
+    ChartSpec("uncleared_alarms_by_site", "Uncleared Alarms By Site", "horizontal_bar", "alarm", "Sites with the most uncleared alarms."),
+    ChartSpec("alarm_category_pareto", "Alarm Category Pareto", "pareto", "alarm", "Alarm categories ranked by count with cumulative impact."),
+    ChartSpec("alarm_duration_pareto", "Alarm Duration Pareto", "pareto", "alarm", "Sites/categories ranked by total duration."),
+    ChartSpec("site_alarm_pareto", "Site Alarm Pareto", "pareto", "alarm", "Sites ranked by alarm count with cumulative impact."),
+    ChartSpec("alarm_duration_distribution", "Alarm Duration Distribution", "histogram", "alarm", "Distribution of alarm durations."),
+    ChartSpec("duration_histogram", "Duration Histogram", "histogram", "alarm", "Distribution of alarm durations."),
+    ChartSpec("alarm_count_per_site_distribution", "Alarm Count Per Site Distribution", "histogram", "alarm", "Distribution of alarm counts across sites."),
+    ChartSpec("time_to_clear_distribution", "Time To Clear Distribution", "histogram", "alarm", "Distribution of time to clear alarms."),
+    ChartSpec("duration_boxplot_by_category", "Duration Boxplot By Category", "box", "alarm", "Duration spread by alarm category."),
+    ChartSpec("duration_boxplot_by_vendor", "Duration Boxplot By Vendor", "box", "alarm", "Duration spread by vendor."),
+    ChartSpec("mttr_by_site", "MTTR By Site", "horizontal_bar", "alarm", "Average clear time by site."),
+    ChartSpec("mttr_boxplot_by_network_type", "MTTR Boxplot By Network Type", "box", "alarm", "Clear-time spread by network type."),
+    ChartSpec("duration_vs_occurrence_time", "Duration Vs Occurrence Time", "scatter", "alarm", "Alarm duration compared with hour of occurrence."),
+    ChartSpec("site_alarm_count_vs_duration", "Site Alarm Count Vs Duration", "scatter", "alarm", "Site alarm count compared with total duration."),
+
+    # Heatmaps and timelines.
+    ChartSpec("alarm_heatmap_day_hour", "Alarm Heatmap Day Hour", "heatmap", "alarm", "Alarm frequency by day of week and hour."),
+    ChartSpec("alarm_heatmap_site_day", "Alarm Heatmap Site Day", "heatmap", "alarm", "Alarm frequency by site and day."),
+    ChartSpec("alarm_heatmap_category_hour", "Alarm Heatmap Category Hour", "heatmap", "alarm", "Alarm category by hour concentration."),
+    ChartSpec("vendor_alarm_heatmap_day", "Vendor Alarm Heatmap Day", "heatmap", "alarm", "Vendor alarm concentration by day."),
+    ChartSpec("network_type_alarm_heatmap", "Network Type Alarm Heatmap", "heatmap", "alarm", "Network type/category concentration."),
+    ChartSpec("daily_alarm_calendar", "Daily Alarm Calendar", "calendar_heatmap", "alarm", "Alarm intensity by calendar day."),
+    ChartSpec("daily_down_alarm_calendar", "Daily Down Alarm Calendar", "calendar_heatmap", "alarm", "Down alarm intensity by calendar day."),
+    ChartSpec("site_alarm_timeline", "Site Alarm Timeline", "timeline", "alarm", "Alarm intervals for a site."),
+    ChartSpec("power_down_incident_timeline", "Power Down Incident Timeline", "timeline", "alarm", "Power and Down event timeline."),
+    ChartSpec("uncleared_alarm_timeline", "Uncleared Alarm Timeline", "timeline", "alarm", "Active/uncleared alarm timeline."),
+    ChartSpec("site_outage_timeline", "Site Outage Timeline", "timeline", "alarm", "Outage duration blocks by site."),
+    ChartSpec("multi_site_alarm_timeline", "Multi Site Alarm Timeline", "timeline", "alarm", "Incident windows across multiple sites."),
+
+    # Backup-time charts.
+    ChartSpec("backup_time_by_site", "Backup Time By Site", "horizontal_bar", "backup", "Backup minutes by site."),
+    ChartSpec("backup_time_trend", "Backup Time Trend", "line", "backup", "Backup minutes over power/down dates."),
+    ChartSpec("backup_time_distribution", "Backup Time Distribution", "histogram", "backup", "Distribution of backup minutes."),
+    ChartSpec("backup_time_boxplot_by_region", "Backup Time Boxplot By Region", "box", "backup", "Backup spread by region/office when metadata is available."),
+    ChartSpec("top_sites_by_backup_failure", "Top Sites By Backup Failure", "horizontal_bar", "backup", "Worst backup sites by low backup time."),
+    ChartSpec("power_vs_down_timeline", "Power Vs Down Timeline", "timeline", "backup", "Power alarm window with Down event."),
+    ChartSpec("daily_backup_failure_calendar", "Daily Backup Failure Calendar", "calendar_heatmap", "backup", "Backup failures by calendar day."),
+    ChartSpec("backup_health_gauge", "Backup Health Gauge", "gauge", "backup", "Selected backup health score."),
+
+    # BDT/PM charts.
+    ChartSpec("bdt_verdict_share", "BDT Verdict Share", "donut", "bdt", "Share of BDT verdicts."),
+    ChartSpec("bdt_verdict_trend", "BDT Verdict Trend", "stacked_bar", "bdt", "BDT verdicts over time."),
+    ChartSpec("bdt_discharge_distribution", "BDT Discharge Distribution", "histogram", "bdt", "Distribution of discharge minutes."),
+    ChartSpec("bdt_discharge_boxplot", "BDT Discharge Boxplot", "box", "bdt", "Discharge minute spread."),
+    ChartSpec("bdt_discharge_by_battery_brand", "BDT Discharge By Battery Brand", "box", "bdt", "Discharge compared by battery brand."),
+    ChartSpec("bdt_health_vs_backup", "BDT Health Vs Backup", "scatter", "bdt", "Battery health compared with backup minutes when fields exist."),
+    ChartSpec("bdt_string_count_vs_backup", "BDT String Count Vs Backup", "scatter", "bdt", "Number of strings compared with backup minutes."),
+    ChartSpec("bdt_discharge_vs_end_voltage", "BDT Discharge Vs End Voltage", "scatter", "bdt", "Discharge minutes compared with end voltage."),
+    ChartSpec("num_strings_vs_backup_time", "Num Strings Vs Backup Time", "scatter", "bdt", "Battery strings compared with backup time."),
+    ChartSpec("bdt_end_voltage_distribution", "BDT End Voltage Distribution", "histogram", "bdt", "Distribution of BDT end voltage."),
+    ChartSpec("end_voltage_distribution", "End Voltage Distribution", "histogram", "bdt", "Distribution of BDT end voltage."),
+    ChartSpec("end_voltage_boxplot_by_battery_brand", "End Voltage Boxplot By Battery Brand", "box", "bdt", "End voltage spread by brand."),
+    ChartSpec("bdt_rule_failure_counts", "BDT Rule Failure Counts", "horizontal_bar", "bdt", "Most failed BDT validation rules."),
+    ChartSpec("bdt_rule_failure_by_site", "BDT Rule Failure By Site", "horizontal_bar", "bdt", "Sites failing the most BDT rules."),
+    ChartSpec("bdt_failure_heatmap_rule_site", "BDT Failure Heatmap Rule Site", "heatmap", "bdt", "BDT rule failures by site."),
+    ChartSpec("bdt_rule_failure_pareto", "BDT Rule Failure Pareto", "pareto", "bdt", "BDT rules ranked by failure impact."),
+    ChartSpec("bdt_failure_treemap", "BDT Failure Treemap", "treemap", "bdt", "Site to rule failure impact."),
+    ChartSpec("bdt_test_calendar", "BDT Test Calendar", "calendar_heatmap", "bdt", "BDT tests by calendar day."),
+    ChartSpec("bdt_test_history_timeline", "BDT Test History Timeline", "timeline", "bdt", "BDT tests over time for a site."),
+    ChartSpec("bdt_acceptance_rate_gauge", "BDT Acceptance Rate Gauge", "gauge", "bdt", "BDT acceptance percentage."),
+    ChartSpec("battery_brand_radar", "Battery Brand Radar", "radar", "bdt", "Battery brand comparison across available metrics."),
+
+    # PM/HT/site metadata and advanced charts.
+    ChartSpec("pm_status_share", "PM Status Share", "donut", "pm", "PM status share."),
+    ChartSpec("ht_weekly_pass_fail", "HT Weekly Pass Fail", "stacked_bar", "pm", "Weekly HT/PM pass/fail counts."),
+    ChartSpec("ht_meet_vs_not_meet", "HT Meet Vs Not Meet", "stacked_bar", "pm", "HT meet vs not-meet counts."),
+    ChartSpec("accepted_pm_by_week", "Accepted PM By Week", "line", "pm", "Accepted PM trend over time."),
+    ChartSpec("weekly_pm_acceptance_trend", "Weekly PM Acceptance Trend", "line", "pm", "PM accepted/rejected trend."),
+    ChartSpec("pm_rejection_reason_pareto", "PM Rejection Reason Pareto", "pareto", "pm", "PM rejection reasons ranked by impact."),
+    ChartSpec("rejected_pm_reasons", "Rejected PM Reasons", "horizontal_bar", "pm", "Top PM rejection reasons."),
+    ChartSpec("pm_rejection_heatmap_week_site", "PM Rejection Heatmap Week Site", "heatmap", "pm", "PM rejection by week/site."),
+    ChartSpec("pm_acceptance_calendar", "PM Acceptance Calendar", "calendar_heatmap", "pm", "PM accepted/rejected by calendar day."),
+    ChartSpec("pm_acceptance_rate_gauge", "PM Acceptance Rate Gauge", "gauge", "pm", "PM acceptance percentage."),
+    ChartSpec("site_metadata_coverage", "Site Metadata Coverage", "gauge", "metadata", "How many alarm sites have site metadata."),
+    ChartSpec("site_metadata_coverage_share", "Site Metadata Coverage Share", "donut", "metadata", "Sites with metadata compared with missing metadata."),
+    ChartSpec("metadata_coverage_gauge", "Metadata Coverage Gauge", "gauge", "metadata", "Site metadata coverage percentage."),
+    ChartSpec("site_region_alarm_treemap", "Site Region Alarm Treemap", "treemap", "metadata", "Region/office/site alarm impact."),
+    ChartSpec("vendor_network_category_treemap", "Vendor Network Category Treemap", "treemap", "metadata", "Vendor to network to category impact."),
+    ChartSpec("alarm_category_treemap", "Alarm Category Treemap", "treemap", "alarm", "Alarm category impact by count/duration."),
+    ChartSpec("pm_status_treemap", "PM Status Treemap", "treemap", "pm", "Week to site to PM status."),
+    ChartSpec("bdt_validation_funnel", "BDT Validation Funnel", "funnel", "bdt", "Files found to parsed to validated to accepted."),
+    ChartSpec("pm_acceptance_funnel", "PM Acceptance Funnel", "funnel", "pm", "Imported to reviewed to accepted to exported."),
+    ChartSpec("alarm_processing_funnel", "Alarm Processing Funnel", "funnel", "alarm", "Files scanned to loaded to normalized to cached."),
+    ChartSpec("site_metadata_funnel", "Site Metadata Funnel", "funnel", "metadata", "Sites found to complete dossier."),
+    ChartSpec("alarm_clearance_rate_gauge", "Alarm Clearance Rate Gauge", "gauge", "alarm", "Cleared alarm percentage."),
+    ChartSpec("site_risk_score_gauge", "Site Risk Score Gauge", "gauge", "metadata", "Combined site risk score."),
+    ChartSpec("site_health_radar", "Site Health Radar", "radar", "metadata", "Site health dimensions."),
+    ChartSpec("vendor_performance_radar", "Vendor Performance Radar", "radar", "alarm", "Vendor comparison across metrics."),
+    ChartSpec("network_type_radar", "Network Type Radar", "radar", "alarm", "Network type comparison across alarm metrics."),
+    ChartSpec("alarm_to_site_flow", "Alarm To Site Flow", "sankey", "alarm", "Alarm category to vendor to site flow."),
+    ChartSpec("pm_review_flow", "PM Review Flow", "sankey", "pm", "Imported to accepted/rejected/revise flow."),
+    ChartSpec("bdt_rule_flow", "BDT Rule Flow", "sankey", "bdt", "BDT test to failed rule to verdict flow."),
+    ChartSpec("site_context_flow", "Site Context Flow", "sankey", "metadata", "Site to metadata to alarms to BDT to PM status."),
+)
+
+CHART_SPECS: dict[str, ChartSpec] = {spec.chart_id: spec for spec in _CHARTS}
+
+
+def chart_type_ids(*, renderable_only: bool = False, computed_report_only: bool = False) -> list[str]:
+    specs: Iterable[ChartSpec] = CHART_SPECS.values()
+    if renderable_only:
+        specs = [spec for spec in specs if spec.renderable]
+    if computed_report_only:
+        specs = [spec for spec in specs if spec.computed_report]
+    return [spec.chart_id for spec in specs]
+
+
+def chart_type_description() -> str:
+    return ", ".join(chart_type_ids(computed_report_only=True))
+
+
+def chart_specs_payload(*, family: str = "", chart_kind: str = "", renderable_only: bool = False) -> list[dict[str, object]]:
+    family_key = str(family or "").strip().lower()
+    kind_key = str(chart_kind or "").strip().lower()
+    rows = []
+    for spec in CHART_SPECS.values():
+        if renderable_only and not spec.renderable:
+            continue
+        if family_key and spec.family != family_key:
+            continue
+        if kind_key and spec.chart_kind != kind_key:
+            continue
+        rows.append(spec.to_dict())
+    return rows
diff --git a/llm_tools/mcp_server.py b/llm_tools/mcp_server.py
index 8b83409..383c3f6 100644
--- a/llm_tools/mcp_server.py
+++ b/llm_tools/mcp_server.py
@@ -4,14 +4,46 @@ from __future__ import annotations
 
 import json
 import sys
+from pathlib import Path
 from typing import Any
 
 from .openrouter_agent import _model_safe_tool_result
-from .service import LocalDataService
+from .service import CHART_WIDGET_MIME_TYPE, CHART_WIDGET_URI, LocalDataService
 from .tools import dispatch_tool, tool_definitions_for_mcp
 
 SERVER_INFO = {"name": "alarm-viewer-local-data", "version": "0.1.0"}
 
+_WIDGET_NAME = "chart-widget"
+_WIDGET_TITLE = "Alarm Chart Widget"
+_WIDGET_HTML_PATH = Path(__file__).resolve().parents[1] / "mcp_app" / "chart_widget" / "dist" / "chart.html"
+
+
+def chart_widget_resource() -> dict[str, Any]:
+    return {
+        "uri": CHART_WIDGET_URI,
+        "name": _WIDGET_NAME,
+        "title": _WIDGET_TITLE,
+        "mimeType": CHART_WIDGET_MIME_TYPE,
+    }
+
+
+def chart_widget_html() -> str:
+    if not _WIDGET_HTML_PATH.exists():
+        raise FileNotFoundError(f"chart widget build artifact missing: {_WIDGET_HTML_PATH}")
+    return _WIDGET_HTML_PATH.read_text(encoding="utf-8")
+
+
+def read_chart_widget_resource(uri: str) -> dict[str, Any] | None:
+    if uri != CHART_WIDGET_URI:
+        return None
+    return {
+        "uri": CHART_WIDGET_URI,
+        "mimeType": CHART_WIDGET_MIME_TYPE,
+        "text": chart_widget_html(),
+        "_meta": {"ui": {"prefersBorder": True}},
+    }
+
+
 
 def _response(request_id: Any, result: Any) -> dict[str, Any]:
     return {"jsonrpc": "2.0", "id": request_id, "result": result}
@@ -35,7 +67,7 @@ class AlarmViewerMcpServer:
             return _response(request_id, {
                 "protocolVersion": "2024-11-05",
                 "serverInfo": SERVER_INFO,
-                "capabilities": {"tools": {}},
+                "capabilities": {"tools": {}, "resources": {}},
             })
 
         if method == "notifications/initialized":
@@ -44,6 +76,21 @@ class AlarmViewerMcpServer:
         if method == "tools/list":
             return _response(request_id, {"tools": tool_definitions_for_mcp()})
 
+        if method == "resources/list":
+            return _response(request_id, {"resources": [chart_widget_resource()]})
+
+        if method == "resources/read":
+            if params is None:
+                return _error(request_id, -32602, "resources/read params must be an object")
+            uri = str(params.get("uri") or "")
+            try:
+                resource = read_chart_widget_resource(uri)
+            except FileNotFoundError as exc:
+                return _error(request_id, -32002, str(exc))
+            if resource is None:
+                return _error(request_id, -32002, f"resource not found: {uri}")
+            return _response(request_id, {"contents": [resource]})
+
         if method == "tools/call":
             if params is None:
                 return _error(request_id, -32602, "tools/call params must be an object")
@@ -51,16 +98,20 @@ class AlarmViewerMcpServer:
             arguments = params.get("arguments") if "arguments" in params else {}
             result = dispatch_tool(self.service, name, arguments)
             safe_result = _model_safe_tool_result(result)
-            return _response(request_id, {
-                "content": [
-                    {
-                        "type": "text",
-                        "text": json.dumps(safe_result, default=str, ensure_ascii=False),
-                    }
-                ],
+            content = [
+                {
+                    "type": "text",
+                    "text": json.dumps(safe_result, default=str, ensure_ascii=False),
+                }
+            ]
+            response_payload = {
+                "content": content,
                 "structuredContent": safe_result,
                 "isError": isinstance(result, dict) and "error" in result,
-            })
+            }
+            if isinstance(result, dict) and isinstance(result.get("_meta"), dict):
+                response_payload["_meta"] = result["_meta"]
+            return _response(request_id, response_payload)
 
         return _error(request_id, -32601, f"method not found: {method}")
 
diff --git a/llm_tools/openrouter_agent.py b/llm_tools/openrouter_agent.py
index 292dd35..abf8718 100644
--- a/llm_tools/openrouter_agent.py
+++ b/llm_tools/openrouter_agent.py
@@ -50,7 +50,9 @@ IMPORTANT RULES:
 4. Never claim that missing data proves a condition; say when the local store has no matching records.
 5. The alarm rows card starts collapsed and can expand up to 100 rows.
 6. Use query_backup_times for questions about backup time, backup duration, or battery hold-up between Power and Down alarms.
-7. Use the host clock context for any time-sensitive answer."""
+7. Use list_chart_types when the user asks what charts are available or asks vaguely for the best chart.
+8. Use list_chart_types and get_chart_data when the user asks for chart-ready data; server-side PNG chart generation is not exposed as a chat tool.
+9. Use the host clock context for any time-sensitive answer."""
 
 SUMMARY_SYSTEM_PROMPT = """You compress Alarm Viewer assistant conversations.
 Preserve all user goals, key facts, tool findings, decisions, generated files,
diff --git a/llm_tools/service.py b/llm_tools/service.py
index fec0da7..ca92f24 100644
--- a/llm_tools/service.py
+++ b/llm_tools/service.py
@@ -5,6 +5,7 @@ from __future__ import annotations
 import base64
 import hashlib
 import json
+import math
 import re
 from dataclasses import asdict, is_dataclass, replace
 from datetime import date, datetime, timedelta, timezone
@@ -54,6 +55,7 @@ try:
     from alarm_app.db.repos import blob_repo
     from alarm_app.db.repos.pm_repo import load_all_validation_results
     from alarm_app.llm_tools import federated_site
+    from alarm_app.llm_tools.charts import CHART_SPECS, chart_specs_payload
 except ImportError:
     from bdt.export import build_bdt_export_sheets
     from core.battery_backup_insights import (
@@ -91,6 +93,7 @@ except ImportError:
     from db.repos import blob_repo
     from db.repos.pm_repo import load_all_validation_results
     from llm_tools import federated_site
+    from llm_tools.charts import CHART_SPECS, chart_specs_payload
 
 MAX_QUERY_LIMIT = 500
 MAX_BLOB_BYTES = 5 * 1024 * 1024
@@ -99,6 +102,9 @@ EXPORT_DIR = Path.home() / ".alarm_viewer" / "exports"
 ALLOWED_UPLOAD_SUFFIXES = {".csv", ".xls", ".xlsx"}
 MCP_DEFAULT_PAGE_LIMIT = 500
 MCP_MAX_PAGE_LIMIT = 500
+CHART_WIDGET_URI = "ui://widget/chart.html"
+CHART_WIDGET_MIME_TYPE = "text/html;profile=mcp-app"
+CHART_DATA_MAX_POINTS = 500
 _FIELD_ALIASES = {
     "site_name": ("site_name", "sitename", "name"),
     "area": ("area", "orange_area", "orangearea"),
@@ -229,6 +235,40 @@ def _sanitize_mcp_value(value: Any) -> Any:
     return _jsonable(value)
 
 
+def _chart_number(value: Any) -> float | None:
+    if value is None or isinstance(value, bool):
+        return None
+    try:
+        number = float(value)
+    except (TypeError, ValueError):
+        return None
+    if not math.isfinite(number):
+        return None
+    return number
+
+
+def _normalize_chart_point(point: Any) -> dict[str, Any]:
+    if not isinstance(point, dict):
+        point = {"label": str(point), "value": 0.0}
+    normalized = _sanitize_mcp_value(point)
+    if not isinstance(normalized, dict):
+        return {"label": str(normalized), "value": 0.0}
+    for numeric_key in ("value", "x", "y"):
+        if numeric_key in normalized:
+            number = _chart_number(normalized.get(numeric_key))
+            if number is None:
+                normalized.pop(numeric_key, None)
+            else:
+                normalized[numeric_key] = number
+    if "label" not in normalized or normalized.get("label") is None:
+        normalized["label"] = str(normalized.get("x") or "")
+    else:
+        normalized["label"] = str(normalized.get("label"))
+    if "value" not in normalized:
+        normalized["value"] = _chart_number(normalized.get("y")) or 0.0
+    return normalized
+
+
 def _max_timestamp(*values: Any) -> Any:
     latest: pd.Timestamp | None = None
     for value in values:
@@ -1437,41 +1477,441 @@ class LocalDataService:
             "export_path": str(export_path),
         }
 
-    def generate_graph(self, **kwargs) -> dict[str, Any]:
-        graph_type = str(kwargs.get("graph_type") or "alarm_category_counts").strip()
-        site_code = normalize_site_key(kwargs.get("site_code") or kwargs.get("site_text") or "")
-        title = str(kwargs.get("title") or graph_type.replace("_", " ").title())
-        if graph_type.startswith("alarm_"):
-            alarm_df = self._alarm_rows_for_sites(
-                {site_code} if site_code else set(self._alarm_reference_df()["site_id"].map(normalize_site_key).dropna()),
-                date_from=_date_value(kwargs.get("date_from")),
-                date_to=_date_value(kwargs.get("date_to")),
-            ) if site_code else self._with_alarm_source(lambda: alarm_store.query_alarms(alarm_store.AlarmQuery(
-                date_from=_date_value(kwargs.get("date_from")),
-                date_to=_date_value(kwargs.get("date_to")),
-                limit=None,
-                offset=0,
-            )))
-            labels, values = self._alarm_graph_series(alarm_df, graph_type)
-        elif graph_type in {"bdt_verdict_counts", "bdt_duration_trend"}:
-            rows = self._query_all_bdt_rows(
-                site_code=site_code,
-                date_from=_date_value(kwargs.get("date_from")),
-                date_to=_date_value(kwargs.get("date_to")),
-            )
+    def list_chart_types(self, **kwargs) -> dict[str, Any]:
+        charts = chart_specs_payload(
+            family=str(kwargs.get("family") or ""),
+            chart_kind=str(kwargs.get("chart_kind") or ""),
+            renderable_only=bool(kwargs.get("renderable_only", False)),
+        )
+        return {"charts": charts, "count": len(charts)}
+
+    def _chart_alarm_df(self, *, site_code: str, kwargs: dict[str, Any]) -> pd.DataFrame:
+        date_from = _date_value(kwargs.get("date_from"))
+        date_to = _date_value(kwargs.get("date_to"))
+        if site_code and kwargs.get("_prefer_site_slice"):
+            return self._alarm_rows_for_sites({site_code}, date_from=date_from, date_to=date_to)
+        q = alarm_store.AlarmQuery(
+            site_text=str(kwargs.get("site_text") or "") if not site_code else "",
+            site_scope_keys={normalize_site_key(site_code)} if site_code else None,
+            category=str(kwargs.get("category") or "All"),
+            vendor=str(kwargs.get("vendor") or "All"),
+            network_type=str(kwargs.get("network_type") or "All"),
+            date_from=date_from,
+            date_to=date_to,
+            sort_by="occurred_on",
+            sort_desc=False,
+            limit=None,
+            offset=0,
+        )
+        return self._with_alarm_source(lambda: alarm_store.query_alarms(q))
+
+    @staticmethod
+    def _series_from_counts(work: pd.DataFrame, column: str, *, top_n: int | None = None) -> tuple[list[str], list[float]]:
+        if column not in work.columns:
+            return [], []
+        counts = work[column].fillna("Unknown").replace("", "Unknown").value_counts()
+        if top_n:
+            counts = counts.head(top_n)
+        return counts.index.astype(str).tolist(), counts.astype(float).tolist()
+
+    @staticmethod
+    def _duration_minutes_by(work: pd.DataFrame, column: str, *, top_n: int | None = None) -> tuple[list[str], list[float]]:
+        if column not in work.columns or "_duration_secs" not in work.columns:
+            return [], []
+        grouped = work.groupby(column, dropna=False)["_duration_secs"].sum().sort_values(ascending=False) / 60.0
+        if top_n:
+            grouped = grouped.head(top_n)
+        return grouped.index.astype(str).tolist(), grouped.astype(float).tolist()
+
+    @staticmethod
+    def _daily_counts(work: pd.DataFrame, *, category: str = "") -> tuple[list[str], list[float]]:
+        if "occurred_on" not in work.columns:
+            return [], []
+        source = work
+        if category and "alarm_category" in source.columns:
+            source = source[source["alarm_category"].astype(str).str.lower() == category.lower()]
+        days = pd.to_datetime(source["occurred_on"], errors="coerce", format="mixed").dropna().dt.date
+        counts = days.value_counts().sort_index()
+        return [str(v) for v in counts.index.tolist()], counts.astype(float).tolist()
+
+    @staticmethod
+    def _histogram_series(values: pd.Series, *, bins: int = 8) -> tuple[list[str], list[float]]:
+        numeric = pd.to_numeric(values, errors="coerce").dropna()
+        if numeric.empty:
+            return [], []
+        if numeric.nunique() == 1:
+            value = float(numeric.iloc[0])
+            return [f"{value:g}"], [float(len(numeric))]
+        counts, edges = pd.cut(numeric, bins=min(bins, max(1, numeric.nunique())), retbins=True, duplicates="drop")
+        grouped = counts.value_counts().sort_index()
+        labels = [f"{interval.left:g}-{interval.right:g}" for interval in grouped.index]
+        return labels, grouped.astype(float).tolist()
+
+    @staticmethod
+    def _box_summary_series(work: pd.DataFrame, group_col: str, value_col: str) -> tuple[list[str], list[float]]:
+        if group_col not in work.columns or value_col not in work.columns:
+            return [], []
+        numeric = pd.to_numeric(work[value_col], errors="coerce")
+        grouped = work.assign(_chart_value=numeric).dropna(subset=["_chart_value"]).groupby(group_col, dropna=False)["_chart_value"].median().sort_values(ascending=False)
+        return grouped.index.astype(str).tolist(), grouped.astype(float).tolist()
+
+    @staticmethod
+    def _scatter_series_from_columns(work: pd.DataFrame, x_col: str, y_col: str, *, label_col: str = "site_id") -> list[dict[str, Any]]:
+        if x_col not in work.columns or y_col not in work.columns:
+            return []
+        rows = []
+        for _, row in work.iterrows():
+            x_val = pd.to_numeric(pd.Series([row.get(x_col)]), errors="coerce").iloc[0]
+            y_val = pd.to_numeric(pd.Series([row.get(y_col)]), errors="coerce").iloc[0]
+            if pd.isna(x_val) or pd.isna(y_val):
+                continue
+            rows.append({
+                "label": str(row.get(label_col) or row.get("site_code") or ""),
+                "x": float(x_val),
+                "y": float(y_val),
+                "value": float(y_val),
+            })
+        return rows
+
+    @staticmethod
+    def _labels_values_from_series(series: list[dict[str, Any]]) -> tuple[list[str], list[float]]:
+        return [str(point.get("label") or "") for point in series], [float(point.get("value") or 0.0) for point in series]
+
+    def _alarm_chart_series(self, alarm_df: pd.DataFrame, graph_type: str) -> tuple[list[str], list[float], list[dict[str, Any]]]:
+        if alarm_df is None or alarm_df.empty:
+            return [], [], []
+        work = alarm_df.copy()
+        category_col = "alarm_category" if "alarm_category" in work.columns else "alarm_name"
+        if graph_type in {"alarm_category_counts", "alarm_category_share", "alarm_category_pareto", "alarm_category_treemap"}:
+            labels, values = self._series_from_counts(work, category_col)
+        elif graph_type == "alarm_daily_counts":
+            labels, values = self._daily_counts(work)
+        elif graph_type in {"alarm_volume_trend", "site_alarm_trend", "cumulative_alarm_volume"}:
+            labels, values = self._daily_counts(work)
+            if graph_type == "cumulative_alarm_volume":
+                total = 0.0
+                cumulative = []
+                for value in values:
+                    total += value
+                    cumulative.append(total)
+                values = cumulative
+        elif graph_type == "daily_power_alarm_trend":
+            labels, values = self._daily_counts(work, category="Power")
+        elif graph_type == "daily_down_alarm_trend":
+            labels, values = self._daily_counts(work, category="Down")
+        elif graph_type in {"alarm_duration_by_category", "duration_boxplot_by_category", "alarm_count_vs_duration_by_category"}:
+            labels, values = self._duration_minutes_by(work, category_col)
+        elif graph_type in {"vendor_alarm_share", "vendor_alarm_comparison", "duration_boxplot_by_vendor", "vendor_performance_radar"}:
+            labels, values = self._series_from_counts(work, "vendor")
+        elif graph_type in {"network_type_share", "network_type_vendor_comparison", "network_type_radar"}:
+            labels, values = self._series_from_counts(work, "network_type")
+        elif graph_type == "alarm_severity_share":
+            labels, values = self._series_from_counts(work, "severity")
+        elif graph_type in {"cleared_vs_uncleared_share", "alarm_clearance_rate_gauge"}:
+            if "cleared_on" not in work.columns:
+                labels, values = [], []
+            else:
+                cleared = pd.to_datetime(work["cleared_on"], errors="coerce", format="mixed").notna()
+                labels, values = ["Cleared", "Uncleared"], [float(cleared.sum()), float((~cleared).sum())]
+        elif graph_type in {"top_sites_by_alarm_count", "site_alarm_pareto"}:
+            labels, values = self._series_from_counts(work, "site_id", top_n=20)
+        elif graph_type in {"top_sites_by_duration", "top_sites_by_alarm_duration", "alarm_duration_pareto", "mttr_by_site"}:
+            labels, values = self._duration_minutes_by(work, "site_id", top_n=20)
+        elif graph_type in {"top_alarm_names"}:
+            labels, values = self._series_from_counts(work, "alarm_name", top_n=20)
+        elif graph_type in {"top_alarm_ids"}:
+            labels, values = self._series_from_counts(work, "alarm_id", top_n=20)
+        elif graph_type == "uncleared_alarms_by_site":
+            if "cleared_on" in work.columns:
+                work = work[pd.to_datetime(work["cleared_on"], errors="coerce", format="mixed").isna()]
+            labels, values = self._series_from_counts(work, "site_id", top_n=20)
+        elif graph_type in {"alarm_duration_distribution", "duration_histogram", "time_to_clear_distribution"}:
+            labels, values = self._histogram_series(work.get("_duration_secs", pd.Series(dtype=float)) / 60.0)
+        elif graph_type == "alarm_count_per_site_distribution":
+            counts = work["site_id"].value_counts() if "site_id" in work.columns else pd.Series(dtype=float)
+            labels, values = self._histogram_series(counts)
+        elif graph_type in {"daily_alarms_by_category", "weekly_alarms_by_category", "stacked_alarm_category_area"}:
+            labels, values = self._series_from_counts(work, category_col)
+        elif graph_type in {"stacked_vendor_area", "vendor_by_category"}:
+            labels, values = self._series_from_counts(work, "vendor")
+        elif graph_type == "network_type_by_category":
+            labels, values = self._series_from_counts(work, "network_type")
+        elif graph_type in {"alarm_heatmap_day_hour", "daily_alarm_calendar", "daily_down_alarm_calendar"}:
+            if "occurred_on" not in work.columns:
+                labels, values = [], []
+            else:
+                times = pd.to_datetime(work["occurred_on"], errors="coerce", format="mixed").dropna()
+                if graph_type == "alarm_heatmap_day_hour":
+                    counts = times.to_frame(name="dt").assign(label=lambda df: df["dt"].dt.day_name().str[:3] + " " + df["dt"].dt.hour.astype(str).str.zfill(2)).label.value_counts().sort_index()
+                    labels, values = counts.index.astype(str).tolist(), counts.astype(float).tolist()
+                else:
+                    if graph_type == "daily_down_alarm_calendar" and "alarm_category" in work.columns:
+                        times = pd.to_datetime(work.loc[work["alarm_category"].astype(str).str.lower() == "down", "occurred_on"], errors="coerce", format="mixed").dropna()
+                    counts = times.dt.date.value_counts().sort_index()
+                    labels, values = [str(v) for v in counts.index], counts.astype(float).tolist()
+        elif graph_type in {"alarm_heatmap_site_day", "alarm_heatmap_category_hour", "vendor_alarm_heatmap_day", "network_type_alarm_heatmap"}:
+            base_col = "site_id" if graph_type == "alarm_heatmap_site_day" else category_col
+            if graph_type == "vendor_alarm_heatmap_day":
+                base_col = "vendor"
+            elif graph_type == "network_type_alarm_heatmap":
+                base_col = "network_type"
+            labels, values = self._series_from_counts(work, base_col, top_n=24)
+        elif graph_type in {"duration_vs_occurrence_time"}:
+            if "occurred_on" in work.columns and "_duration_secs" in work.columns:
+                hours = pd.to_datetime(work["occurred_on"], errors="coerce", format="mixed").dt.hour
+                scatter_df = work.assign(_hour=hours, _minutes=work["_duration_secs"] / 60.0)
+                series = self._scatter_series_from_columns(scatter_df, "_hour", "_minutes")
+                labels, values = self._labels_values_from_series(series)
+                return labels, values, series
+            labels, values = [], []
+        elif graph_type == "site_alarm_count_vs_duration":
+            if "site_id" in work.columns and "_duration_secs" in work.columns:
+                grouped = work.groupby("site_id").agg(count=("site_id", "size"), minutes=("_duration_secs", "sum")).reset_index()
+                grouped["minutes"] = grouped["minutes"] / 60.0
+                series = self._scatter_series_from_columns(grouped, "count", "minutes", label_col="site_id")
+                labels, values = self._labels_values_from_series(series)
+                return labels, values, series
+            labels, values = [], []
+        else:
+            labels, values = self._series_from_counts(work, category_col)
+        series = [{"label": str(label), "value": float(value)} for label, value in zip(labels, values, strict=False)]
+        return labels, values, series
+
+    def _backup_chart_series(self, graph_type: str, kwargs: dict[str, Any]) -> tuple[list[str], list[float], list[dict[str, Any]]]:
+        payload = self.query_backup_times(
+            site_text=str(kwargs.get("site_text") or kwargs.get("site_code") or ""),
+            category=str(kwargs.get("category") or "All"),
+            vendor=str(kwargs.get("vendor") or "All"),
+            network_type=str(kwargs.get("network_type") or "All"),
+            date_from=kwargs.get("date_from"),
+            date_to=kwargs.get("date_to"),
+            min_minutes=kwargs.get("min_minutes"),
+            limit=MAX_QUERY_LIMIT,
+            offset=0,
+        )
+        rows = payload.get("rows") if isinstance(payload, dict) else []
+        if not isinstance(rows, list):
+            rows = []
+        df = pd.DataFrame(rows)
+        if df.empty:
+            return [], [], []
+        minute_col = "backup_minutes" if "backup_minutes" in df.columns else "backup_time_minutes" if "backup_time_minutes" in df.columns else "minutes"
+        if graph_type in {"backup_time_distribution", "daily_backup_failure_calendar"}:
+            labels, values = self._histogram_series(df.get(minute_col, pd.Series(dtype=float)))
+        elif graph_type in {"backup_time_trend", "power_vs_down_timeline", "power_down_incident_timeline"} and "power_occurred_on" in df.columns:
+            times = pd.to_datetime(df["power_occurred_on"], errors="coerce", format="mixed").dt.date
+            labels = [str(value) for value in times.fillna("").tolist()]
+            values = pd.to_numeric(df.get(minute_col, pd.Series(dtype=float)), errors="coerce").fillna(0).astype(float).tolist()
+        else:
+            site_col = "site_id" if "site_id" in df.columns else "site_code"
+            if site_col in df.columns and minute_col in df.columns:
+                grouped = df.groupby(site_col, dropna=False)[minute_col].max().sort_values(ascending=False).head(20)
+                labels, values = grouped.index.astype(str).tolist(), pd.to_numeric(grouped, errors="coerce").fillna(0).astype(float).tolist()
+            else:
+                labels, values = [], []
+        series = [{"label": str(label), "value": float(value)} for label, value in zip(labels, values, strict=False)]
+        return labels, values, series
+
+    def _bdt_chart_series(self, graph_type: str, kwargs: dict[str, Any]) -> tuple[list[str], list[float], list[dict[str, Any]]]:
+        rows = self._query_all_bdt_rows(
+            site_code=normalize_site_key(kwargs.get("site_code") or "") if kwargs.get("site_code") else "",
+            date_from=_date_value(kwargs.get("date_from")),
+            date_to=_date_value(kwargs.get("date_to")),
+        )
+        if graph_type in {"bdt_verdict_counts", "bdt_duration_trend"}:
             labels, values = self._bdt_graph_series(rows, graph_type)
         else:
+            df = pd.DataFrame(rows)
+            if df.empty:
+                labels, values = [], []
+            elif graph_type in {"bdt_verdict_share", "bdt_verdict_trend", "bdt_acceptance_rate_gauge"}:
+                labels, values = self._series_from_counts(df, "overall_verdict")
+            elif graph_type in {"bdt_discharge_distribution", "bdt_discharge_boxplot"}:
+                labels, values = self._histogram_series(df.get("discharge_minutes", pd.Series(dtype=float)))
+            elif graph_type in {"bdt_discharge_by_battery_brand", "end_voltage_boxplot_by_battery_brand", "battery_brand_radar"}:
+                labels, values = self._box_summary_series(df, "battery_brand", "discharge_minutes")
+            elif graph_type in {"bdt_end_voltage_distribution", "end_voltage_distribution"}:
+                labels, values = self._histogram_series(df.get("end_voltage", pd.Series(dtype=float)))
+            elif graph_type in {"bdt_string_count_vs_backup", "num_strings_vs_backup_time"}:
+                series = self._scatter_series_from_columns(df, "num_strings", "discharge_minutes", label_col="site_code")
+                labels, values = self._labels_values_from_series(series)
+                return labels, values, series
+            elif graph_type == "bdt_discharge_vs_end_voltage":
+                series = self._scatter_series_from_columns(df, "end_voltage", "discharge_minutes", label_col="site_code")
+                labels, values = self._labels_values_from_series(series)
+                return labels, values, series
+            else:
+                labels, values = self._series_from_counts(df, "overall_verdict")
+        series = [{"label": str(label), "value": float(value)} for label, value in zip(labels, values, strict=False)]
+        return labels, values, series
+
+    def _chart_series_for_spec(self, graph_type: str, kwargs: dict[str, Any]) -> tuple[list[str], list[float], list[dict[str, Any]]]:
+        spec = CHART_SPECS.get(graph_type)
+        if spec is None:
+            return [], [], []
+        site_code = normalize_site_key(kwargs.get("site_code") or kwargs.get("site_text") or "")
+        if spec.family == "alarm":
+            alarm_df = self._chart_alarm_df(site_code=site_code, kwargs=kwargs)
+            if graph_type in {"alarm_category_counts", "alarm_daily_counts", "alarm_duration_by_category"}:
+                labels, values = self._alarm_graph_series(alarm_df, graph_type)
+                series = [{"label": str(label), "value": float(value)} for label, value in zip(labels, values, strict=False)]
+                return labels, values, series
+            return self._alarm_chart_series(alarm_df, graph_type)
+        if spec.family == "backup":
+            return self._backup_chart_series(graph_type, kwargs)
+        if spec.family == "bdt":
+            return self._bdt_chart_series(graph_type, kwargs)
+        # PM, HT, metadata, and advanced flow charts are catalogued now and can
+        # be rendered as empty placeholders until their source-specific
+        # aggregators are expanded.
+        return [], [], []
+
+    @staticmethod
+    def _chart_axis_labels(chart_kind: str) -> tuple[str, str]:
+        if chart_kind in {"line", "histogram", "heatmap", "scatter", "calendar_heatmap", "timeline"}:
+            return "X", "Value"
+        return "Category", "Count"
+
+    def get_chart_data(self, **kwargs) -> dict[str, Any]:
+        chart_id = str(kwargs.get("chart_id") or kwargs.get("graph_type") or "").strip()
+        spec = CHART_SPECS.get(chart_id)
+        if spec is None or not spec.renderable:
+            return {"error": f"unsupported chart_id: {chart_id}"}
+
+        raw_filters = kwargs.get("filters")
+        filters = dict(raw_filters) if isinstance(raw_filters, dict) else {}
+        for key in ("site_code", "site_text", "date_from", "date_to", "category", "vendor", "network_type", "min_minutes"):
+            if key in kwargs and kwargs.get(key) not in (None, ""):
+                filters[key] = kwargs.get(key)
+
+        raw_max_points = kwargs.get("max_points")
+        try:
+            max_points = int(raw_max_points) if raw_max_points is not None else CHART_DATA_MAX_POINTS
+        except (TypeError, ValueError):
+            max_points = CHART_DATA_MAX_POINTS
+        warnings: list[str] = []
+        if max_points < 0:
+            warnings.append(f"max_points raised from {max_points} to 0.")
+            max_points = 0
+        if max_points > CHART_DATA_MAX_POINTS:
+            warnings.append(f"max_points clamped from {max_points} to {CHART_DATA_MAX_POINTS}.")
+            max_points = CHART_DATA_MAX_POINTS
+
+        title = str(kwargs.get("title") or spec.label)
+        series_kwargs = dict(filters)
+        series_kwargs["_prefer_site_slice"] = True
+        labels, values, series = self._chart_series_for_spec(chart_id, series_kwargs)
+        if not series:
+            series = [{"label": str(label), "value": _chart_number(value) or 0.0} for label, value in zip(labels, values, strict=False)]
+        series = [_normalize_chart_point(point) for point in series]
+        total_points = len(series)
+        returned_series = series[:max_points] if max_points > 0 else []
+        if total_points > len(returned_series):
+            warnings.append(f"Series truncated from {total_points} to {len(returned_series)} points.")
+
+        labels = [str(point.get("label") or "") for point in returned_series]
+        values = [_chart_number(point.get("value")) or 0.0 for point in returned_series]
+        x_label, y_label = self._chart_axis_labels(spec.chart_kind)
+        empty_state = None
+        if total_points == 0:
+            empty_state = {
+                "title": "No chart data",
+                "message": "No rows matched the selected chart and filters.",
+            }
+
+        return {
+            "chart_id": chart_id,
+            "chart_kind": spec.chart_kind,
+            "title": title,
+            "labels": labels,
+            "values": values,
+            "series": returned_series,
+            "x_axis": {"label": x_label},
+            "y_axis": {"label": y_label},
+            "warnings": warnings,
+            "data_quality": {
+                "total_points": total_points,
+                "returned_points": len(returned_series),
+                "truncated": total_points > len(returned_series),
+            },
+            "query_context": {
+                "filters": _sanitize_mcp_value(filters),
+                "max_points": max_points,
+            },
+            "empty_state": empty_state,
+        }
+
+    def render_chart_widget(self, **kwargs) -> dict[str, Any]:
+        chart_id = str(kwargs.get("chart_id") or "").strip()
+        if not chart_id:
+            return {"error": "chart_id is required"}
+        chart_kind = str(kwargs.get("chart_kind") or "bar").strip() or "bar"
+        title = str(kwargs.get("title") or chart_id)
+        labels = kwargs.get("labels") if isinstance(kwargs.get("labels"), list) else []
+        values = kwargs.get("values") if isinstance(kwargs.get("values"), list) else []
+        series = kwargs.get("series") if isinstance(kwargs.get("series"), list) else []
+        series = [_normalize_chart_point(point) for point in series]
+        if not series:
+            series = [
+                {"label": str(label), "value": _chart_number(values[index] if index < len(values) else None) or 0.0}
+                for index, label in enumerate(labels)
+            ]
+        labels = [str(point.get("label") or "") for point in series]
+        values = [_chart_number(point.get("value")) or 0.0 for point in series]
+        warnings = kwargs.get("warnings") if isinstance(kwargs.get("warnings"), list) else []
+        data_quality = kwargs.get("data_quality") if isinstance(kwargs.get("data_quality"), dict) else {}
+        query_context = kwargs.get("query_context") if isinstance(kwargs.get("query_context"), dict) else {}
+        empty_state = kwargs.get("empty_state") if isinstance(kwargs.get("empty_state"), dict) else None
+        return {
+            "chart_id": chart_id,
+            "chart_kind": chart_kind,
+            "title": title,
+            "labels": _sanitize_mcp_value(labels),
+            "values": _sanitize_mcp_value(values),
+            "series": _sanitize_mcp_value(series),
+            "x_axis": _sanitize_mcp_value(kwargs.get("x_axis") if isinstance(kwargs.get("x_axis"), dict) else {}),
+            "y_axis": _sanitize_mcp_value(kwargs.get("y_axis") if isinstance(kwargs.get("y_axis"), dict) else {}),
+            "warnings": _sanitize_mcp_value(warnings),
+            "data_quality": _sanitize_mcp_value(data_quality),
+            "query_context": _sanitize_mcp_value(query_context),
+            "empty_state": _sanitize_mcp_value(empty_state),
+            "_meta": {
+                "openai/outputTemplate": CHART_WIDGET_URI,
+                "ui": {"resourceUri": CHART_WIDGET_URI},
+            },
+        }
+
+    def generate_graph(self, **kwargs) -> dict[str, Any]:
+        graph_type = str(kwargs.get("graph_type") or "alarm_category_counts").strip()
+        spec = CHART_SPECS.get(graph_type)
+        if spec is None or not spec.renderable:
             return {"error": f"unsupported graph_type: {graph_type}"}
 
+        site_code = normalize_site_key(kwargs.get("site_code") or kwargs.get("site_text") or "")
+        title = str(kwargs.get("title") or spec.label)
+        series_kwargs = dict(kwargs)
+        series_kwargs["_prefer_site_slice"] = True
+        labels, values, series = self._chart_series_for_spec(graph_type, series_kwargs)
+        if not series:
+            series = [{"label": str(label), "value": float(value)} for label, value in zip(labels, values, strict=False)]
+
         path = _safe_export_path(self.export_dir / "charts", f"{title}_{site_code or 'all'}", "png")
-        self._draw_bar_chart(path, title, labels, values)
+        self._draw_chart(path, title, labels, values, chart_kind=spec.chart_kind, series=series)
+        image_bytes = path.read_bytes()
+        width, height = Image.open(BytesIO(image_bytes)).size
         return {
             "path": str(path),
             "graph_type": graph_type,
+            "chart_kind": spec.chart_kind,
             "site_code": site_code,
-            "points": len(values),
+            "points": len(series) if series else len(values),
             "labels": labels,
             "values": values,
+            "series": _sanitize_mcp_value(series),
+            "mime_type": "image/png",
+            "image_base64": base64.b64encode(image_bytes).decode("ascii"),
+            "width": int(width),
+            "height": int(height),
         }
 
     def get_computed_report(self, **kwargs) -> dict[str, Any]:
@@ -1562,59 +2002,30 @@ class LocalDataService:
                 result["error"] = _sanitize_mcp_value(str(payload.get("error")))
             return result
 
-        alarm_chart_types = {
-            "alarm_category_counts",
-            "alarm_daily_counts",
-            "alarm_duration_by_category",
-        }
-        bdt_chart_types = {
-            "bdt_verdict_counts",
-            "bdt_duration_trend",
-        }
-
-        if report_type in alarm_chart_types:
-            q = alarm_store.AlarmQuery(
-                site_text=site_text if not site_code else "",
-                site_scope_keys={normalize_site_key(site_code)} if site_code else None,
-                category=category,
-                vendor=vendor,
-                network_type=network_type,
-                date_from=date_from,
-                date_to=date_to,
-                sort_by="occurred_on",
-                sort_desc=False,
-                limit=None,
-                offset=0,
-            )
+        chart_spec = CHART_SPECS.get(report_type)
+        if chart_spec is not None and chart_spec.computed_report:
             try:
-                alarm_df = self._with_alarm_source(lambda: alarm_store.query_alarms(q))
-            except Exception as exc:
-                return _computed_error_payload(exc, chart=True)
-            labels, values = self._alarm_graph_series(alarm_df, report_type)
-            series = [{"label": str(label), "value": _sanitize_mcp_value(value)} for label, value in zip(labels, values)]
-            payload = self._chart_page_payload(series, total=len(series), limit=limit, offset=offset)
-            payload["report_type"] = report_type
-            payload["labels"] = _sanitize_mcp_value(payload["labels"])
-            payload["values"] = _sanitize_mcp_value(payload["values"])
-            payload["series"] = [{"label": str(point["label"]), "value": _sanitize_mcp_value(point["value"])} for point in payload["series"]]
-            return payload
-
-        if report_type in bdt_chart_types:
-            try:
-                rows = self._query_all_bdt_rows(
-                    site_code=normalize_site_key(site_code) if site_code else "",
-                    date_from=date_from,
-                    date_to=date_to,
-                )
+                labels, values, series = self._chart_series_for_spec(report_type, {
+                    **kwargs,
+                    "site_code": site_code,
+                    "site_text": site_text,
+                    "date_from": kwargs.get("date_from"),
+                    "date_to": kwargs.get("date_to"),
+                    "category": category,
+                    "vendor": vendor,
+                    "network_type": network_type,
+                })
             except Exception as exc:
                 return _computed_error_payload(exc, chart=True)
-            labels, values = self._bdt_graph_series(rows, report_type)
-            series = [{"label": str(label), "value": _sanitize_mcp_value(value)} for label, value in zip(labels, values)]
+            if not series:
+                series = [{"label": str(label), "value": _sanitize_mcp_value(value)} for label, value in zip(labels, values, strict=False)]
+            series = [_sanitize_mcp_value(point) for point in series]
             payload = self._chart_page_payload(series, total=len(series), limit=limit, offset=offset)
             payload["report_type"] = report_type
+            payload["chart_kind"] = chart_spec.chart_kind
             payload["labels"] = _sanitize_mcp_value(payload["labels"])
             payload["values"] = _sanitize_mcp_value(payload["values"])
-            payload["series"] = [{"label": str(point["label"]), "value": _sanitize_mcp_value(point["value"])} for point in payload["series"]]
+            payload["series"] = [_sanitize_mcp_value(point) for point in payload["series"]]
             return payload
 
         if report_type in {
@@ -2222,6 +2633,219 @@ class LocalDataService:
             )
         image.save(path)
 
+    @classmethod
+    def _draw_chart(
+        cls,
+        path: Path,
+        title: str,
+        labels: list[str],
+        values: list[float],
+        *,
+        chart_kind: str,
+        series: list[dict[str, Any]] | None = None,
+    ) -> None:
+        kind = str(chart_kind or "bar").lower()
+        if kind in {"bar", "grouped_bar", "stacked_bar", "pareto", "funnel", "treemap", "radar", "sankey", "calendar_heatmap", "timeline", "box"}:
+            if kind in {"pie", "donut"}:  # defensive, handled below
+                cls._draw_pie_chart(path, title, labels, values, donut=kind == "donut")
+                return
+            if kind in {"horizontal_bar", "funnel"}:
+                cls._draw_horizontal_bar_chart(path, title, labels, values)
+                return
+            if kind in {"line", "radar", "sankey", "timeline"}:
+                cls._draw_line_chart(path, title, labels, values)
+                return
+            if kind in {"heatmap", "calendar_heatmap", "treemap"}:
+                cls._draw_heatmap_chart(path, title, labels, values)
+                return
+            if kind in {"histogram", "box"}:
+                cls._draw_bar_chart(path, title, labels, values)
+                return
+            cls._draw_bar_chart(path, title, labels, values)
+            return
+        if kind in {"pie", "donut"}:
+            cls._draw_pie_chart(path, title, labels, values, donut=kind == "donut")
+            return
+        if kind == "horizontal_bar":
+            cls._draw_horizontal_bar_chart(path, title, labels, values)
+            return
+        if kind == "line":
+            cls._draw_line_chart(path, title, labels, values)
+            return
+        if kind == "scatter":
+            cls._draw_scatter_chart(path, title, series or [])
+            return
+        if kind == "heatmap":
+            cls._draw_heatmap_chart(path, title, labels, values)
+            return
+        if kind == "gauge":
+            cls._draw_gauge_chart(path, title, values)
+            return
+        cls._draw_bar_chart(path, title, labels, values)
+
+    @classmethod
+    def _chart_canvas(cls, path: Path, title: str, *, width: int = 1200, height: int = 760):
+        path.parent.mkdir(parents=True, exist_ok=True)
+        image = Image.new("RGB", (width, height), "#10111a")
+        draw = ImageDraw.Draw(image)
+        title_font = cls._chart_font(24, bold=True)
+        title_lines = cls._wrap_chart_text(draw, title, title_font, width - 140)
+        title_text = "\n".join(title_lines)
+        bbox = draw.multiline_textbbox((0, 0), title_text, font=title_font, spacing=6)
+        draw.multiline_text(((width - (bbox[2] - bbox[0])) / 2, 24), title_text, fill="#d8def8", font=title_font, spacing=6)
+        return image, draw
+
+    @classmethod
+    def _draw_horizontal_bar_chart(cls, path: Path, title: str, labels: list[str], values: list[float]) -> None:
+        image, draw = cls._chart_canvas(path, title)
+        font = cls._chart_font(14)
+        value_font = cls._chart_font(13, bold=True)
+        if not values:
+            draw.text((104, 360), "No matching data", fill="#8f96ad", font=font)
+            image.save(path)
+            return
+        labels = labels[:20]
+        values = values[:20]
+        max_value = max(max(values), 1.0)
+        x0, y0, chart_w = 240, 112, 850
+        row_h = max(22, min(36, int(520 / max(len(values), 1))))
+        for idx, (label, value) in enumerate(zip(labels, values, strict=False)):
+            y = y0 + idx * (row_h + 6)
+            bar_w = int((float(value) / max_value) * chart_w)
+            draw.text((32, y + 3), cls._format_chart_label(label)[:26], fill="#b9c1dc", font=font)
+            draw.rectangle((x0, y, x0 + bar_w, y + row_h), fill="#7aa2ff")
+            draw.text((x0 + bar_w + 8, y + 3), f"{value:g}", fill="#d8def8", font=value_font)
+        image.save(path)
+
+    @classmethod
+    def _draw_pie_chart(cls, path: Path, title: str, labels: list[str], values: list[float], *, donut: bool = False) -> None:
+        image, draw = cls._chart_canvas(path, title)
+        font = cls._chart_font(14)
+        value_font = cls._chart_font(13, bold=True)
+        clean = [(label, float(value)) for label, value in zip(labels[:12], values[:12], strict=False) if float(value or 0) > 0]
+        if not clean:
+            draw.text((104, 360), "No matching data", fill="#8f96ad", font=font)
+            image.save(path)
+            return
+        total = sum(value for _, value in clean) or 1.0
+        colors = ["#7aa2ff", "#a6e3a1", "#f9e2af", "#f38ba8", "#cba6f7", "#89dceb", "#fab387", "#94e2d5"]
+        box = (120, 150, 620, 650)
+        start = -90.0
+        for idx, (label, value) in enumerate(clean):
+            extent = 360.0 * value / total
+            draw.pieslice(box, start, start + extent, fill=colors[idx % len(colors)])
+            start += extent
+        if donut:
+            draw.ellipse((260, 290, 480, 510), fill="#10111a")
+            pct = max(value for _, value in clean) / total * 100
+            draw.text((315, 385), f"{pct:.0f}%", fill="#d8def8", font=cls._chart_font(28, bold=True))
+        lx, ly = 700, 170
+        for idx, (label, value) in enumerate(clean):
+            y = ly + idx * 34
+            draw.rectangle((lx, y, lx + 20, y + 20), fill=colors[idx % len(colors)])
+            draw.text((lx + 32, y), f"{cls._format_chart_label(label)}  {value:g} ({value / total:.0%})", fill="#d8def8", font=value_font)
+        image.save(path)
+
+    @classmethod
+    def _draw_line_chart(cls, path: Path, title: str, labels: list[str], values: list[float]) -> None:
+        image, draw = cls._chart_canvas(path, title)
+        font = cls._chart_font(14)
+        if not values:
+            draw.text((104, 360), "No matching data", fill="#8f96ad", font=font)
+            image.save(path)
+            return
+        labels = labels[:80]
+        values = values[:80]
+        left, top, width, height = 104, 130, 1020, 460
+        draw.line((left, top, left, top + height), fill="#3a3d55", width=2)
+        draw.line((left, top + height, left + width, top + height), fill="#3a3d55", width=2)
+        max_value = max(max(values), 1.0)
+        denom = max(len(values) - 1, 1)
+        points = []
+        for idx, value in enumerate(values):
+            x = left + int(idx / denom * width)
+            y = top + height - int(float(value) / max_value * height)
+            points.append((x, y))
+        if len(points) == 1:
+            draw.ellipse((points[0][0] - 5, points[0][1] - 5, points[0][0] + 5, points[0][1] + 5), fill="#7aa2ff")
+        else:
+            draw.line(points, fill="#7aa2ff", width=4)
+            for x, y in points[::max(1, len(points) // 16)]:
+                draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill="#d8def8")
+        for idx in range(0, len(labels), max(1, len(labels) // 8)):
+            x = left + int(idx / denom * width)
+            draw.text((x - 24, top + height + 12), cls._format_chart_label(labels[idx])[:8], fill="#b9c1dc", font=font)
+        image.save(path)
+
+    @classmethod
+    def _draw_scatter_chart(cls, path: Path, title: str, series: list[dict[str, Any]]) -> None:
+        image, draw = cls._chart_canvas(path, title)
+        font = cls._chart_font(14)
+        points = []
+        for point in series[:200]:
+            try:
+                points.append((float(point.get("x")), float(point.get("y")), str(point.get("label") or "")))
+            except (TypeError, ValueError):
+                continue
+        if not points:
+            draw.text((104, 360), "No matching data", fill="#8f96ad", font=font)
+            image.save(path)
+            return
+        left, top, width, height = 104, 130, 980, 470
+        xs = [p[0] for p in points]
+        ys = [p[1] for p in points]
+        min_x, max_x = min(xs), max(xs) or 1.0
+        min_y, max_y = min(ys), max(ys) or 1.0
+        if min_x == max_x:
+            max_x += 1.0
+        if min_y == max_y:
+            max_y += 1.0
+        draw.line((left, top, left, top + height), fill="#3a3d55", width=2)
+        draw.line((left, top + height, left + width, top + height), fill="#3a3d55", width=2)
+        for x_val, y_val, _label in points:
+            x = left + int((x_val - min_x) / (max_x - min_x) * width)
+            y = top + height - int((y_val - min_y) / (max_y - min_y) * height)
+            draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill="#a6e3a1")
+        image.save(path)
+
+    @classmethod
+    def _draw_heatmap_chart(cls, path: Path, title: str, labels: list[str], values: list[float]) -> None:
+        image, draw = cls._chart_canvas(path, title)
+        font = cls._chart_font(12)
+        if not values:
+            draw.text((104, 360), "No matching data", fill="#8f96ad", font=font)
+            image.save(path)
+            return
+        labels = labels[:48]
+        values = values[:48]
+        cols = min(12, max(1, len(values)))
+        cell = 68
+        start_x, start_y = 100, 140
+        max_value = max(max(values), 1.0)
+        for idx, (label, value) in enumerate(zip(labels, values, strict=False)):
+            col, row = idx % cols, idx // cols
+            intensity = float(value) / max_value
+            blue = int(80 + 175 * intensity)
+            fill = f"#{40:02x}{90:02x}{blue:02x}"
+            x = start_x + col * (cell + 8)
+            y = start_y + row * (cell + 28)
+            draw.rectangle((x, y, x + cell, y + cell), fill=fill)
+            draw.text((x + 6, y + cell + 4), cls._format_chart_label(label)[:8], fill="#b9c1dc", font=font)
+        image.save(path)
+
+    @classmethod
+    def _draw_gauge_chart(cls, path: Path, title: str, values: list[float]) -> None:
+        image, draw = cls._chart_canvas(path, title)
+        font = cls._chart_font(18, bold=True)
+        value = float(values[0]) if values else 0.0
+        pct = max(0.0, min(1.0, value / 100.0 if value > 1 else value))
+        box = (250, 190, 950, 890)
+        draw.arc(box, 180, 360, fill="#3a3d55", width=36)
+        draw.arc(box, 180, 180 + int(180 * pct), fill="#a6e3a1", width=36)
+        draw.text((535, 430), f"{pct * 100:.0f}%", fill="#d8def8", font=cls._chart_font(42, bold=True))
+        draw.text((500, 500), "Current value", fill="#b9c1dc", font=font)
+        image.save(path)
+
     @staticmethod
     def _write_dataframe(df: pd.DataFrame, path: Path, fmt: str, sheet_name: str) -> None:
         if fmt == "csv":
diff --git a/llm_tools/tools.py b/llm_tools/tools.py
index 75f24f6..3c1b1c4 100644
--- a/llm_tools/tools.py
+++ b/llm_tools/tools.py
@@ -5,7 +5,8 @@ from __future__ import annotations
 import math
 from typing import Any
 
-from .service import LocalDataService
+from .charts import chart_type_description, chart_type_ids
+from .service import CHART_DATA_MAX_POINTS, CHART_WIDGET_URI, LocalDataService
 
 
 def _schema(properties: dict[str, Any], *, required: list[str] | None = None) -> dict[str, Any]:
@@ -279,43 +280,104 @@ TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
         }),
         "outputSchema": _output_schema(_PAGING_OUTPUT),
     },
-    "generate_graph": {
+    "list_chart_types": {
+        "description": "List supported chart types. For ChatGPT charts, call list_chart_types, then get_chart_data, then render_chart_widget.",
+        "inputSchema": _schema({
+            "family": {"type": "string", "description": "Optional chart family filter, such as alarm, backup, bdt, pm, or metadata."},
+            "chart_kind": {"type": "string", "description": "Optional chart kind filter, such as bar, donut, line, heatmap, or scatter."},
+            "renderable_only": {"type": "boolean", "description": "When true, return only charts that can be rendered as images."},
+        }),
+        "outputSchema": _output_schema({
+            "charts": _OBJECT_ROWS,
+            "count": {"type": "integer"},
+            "error": {"type": "string"},
+        }),
+    },
+    "get_chart_data": {
         "description": (
-            "Generate a PNG chart from local alarm or BDT data and return the image path plus chart data."
+            "Return validated structured chart data without creating an image. "
+            "Preferred ChatGPT chart flow: list_chart_types -> get_chart_data -> render_chart_widget."
         ),
         "inputSchema": _schema({
-            "graph_type": {
+            "chart_id": {
                 "type": "string",
-                "enum": [
-                    "alarm_category_counts",
-                    "alarm_daily_counts",
-                    "alarm_duration_by_category",
-                    "bdt_verdict_counts",
-                    "bdt_duration_trend",
-                ],
+                "enum": chart_type_ids(renderable_only=True),
+                "description": "Chart id from list_chart_types.",
             },
-            "site_code": {"type": "string"},
-            "site_text": {"type": "string"},
-            "date_from": {"type": "string"},
-            "date_to": {"type": "string"},
+            "filters": {
+                "type": "object",
+                "description": "Optional safe chart filters such as site_code, site_text, date_from, date_to, category, vendor, network_type, and min_minutes.",
+                "additionalProperties": True,
+            },
+            "max_points": {"type": "integer", "minimum": 0, "maximum": CHART_DATA_MAX_POINTS, "xClampMaximum": True},
+            "group_by": {"type": "string", "description": "Reserved grouping hint when supported by a chart."},
+            "sort_by": {"type": "string", "description": "Reserved sort hint when supported by a chart."},
+            "sort_direction": {"type": "string", "enum": ["asc", "desc"], "description": "Reserved sort direction hint."},
+        }, required=["chart_id"]),
+        "outputSchema": _output_schema({
+            "chart_id": {"type": "string"},
+            "chart_kind": {"type": "string"},
+            "title": {"type": "string"},
+            "labels": _STRING_LIST,
+            "values": _NUMBER_LIST,
+            "series": _OBJECT_ROWS,
+            "x_axis": _OBJECT_OUTPUT,
+            "y_axis": _OBJECT_OUTPUT,
+            "warnings": _STRING_LIST,
+            "data_quality": _OBJECT_OUTPUT,
+            "query_context": _OBJECT_OUTPUT,
+            "empty_state": _OBJECT_OUTPUT,
+            "error": {"type": "string"},
+        }),
+    },
+    "render_chart_widget": {
+        "description": (
+            "Render the Apps SDK chart widget from a validated get_chart_data payload. "
+            "Call get_chart_data first, then pass its structured payload here."
+        ),
+        "inputSchema": _schema({
+            "chart_id": {"type": "string"},
+            "chart_kind": {"type": "string"},
             "title": {"type": "string"},
-        }, required=["graph_type"]),
+            "labels": _STRING_LIST,
+            "values": _NUMBER_LIST,
+            "series": _OBJECT_ROWS,
+            "x_axis": _OBJECT_OUTPUT,
+            "y_axis": _OBJECT_OUTPUT,
+            "warnings": _STRING_LIST,
+            "data_quality": _OBJECT_OUTPUT,
+            "query_context": _OBJECT_OUTPUT,
+            "empty_state": _OBJECT_OUTPUT,
+        }, required=["chart_id", "chart_kind", "title", "labels", "values", "series"]),
         "outputSchema": _output_schema({
-            "path": {"type": "string"},
-            "graph_type": {"type": "string"},
-            "site_code": {"type": "string"},
-            "points": {"type": "integer"},
+            "chart_id": {"type": "string"},
+            "chart_kind": {"type": "string"},
+            "title": {"type": "string"},
             "labels": _STRING_LIST,
             "values": _NUMBER_LIST,
+            "series": _OBJECT_ROWS,
+            "x_axis": _OBJECT_OUTPUT,
+            "y_axis": _OBJECT_OUTPUT,
+            "warnings": _STRING_LIST,
+            "data_quality": _OBJECT_OUTPUT,
+            "query_context": _OBJECT_OUTPUT,
+            "empty_state": _OBJECT_OUTPUT,
+            "_meta": _OBJECT_OUTPUT,
             "error": {"type": "string"},
         }),
+        "_meta": {
+            "openai/outputTemplate": CHART_WIDGET_URI,
+            "ui": {"resourceUri": CHART_WIDGET_URI},
+            "openai/toolInvocation/invoking": "Rendering chart...",
+            "openai/toolInvocation/invoked": "Chart ready.",
+        },
     },
     "get_computed_report": {
         "description": "Read computed chart-like or report-like rows for backups and charts without creating files.",
         "inputSchema": _schema({
             "report_type": {
                 "type": "string",
-                "description": "Supported values: backup_times, alarm_category_counts, alarm_daily_counts, alarm_duration_by_category, bdt_verdict_counts, bdt_duration_trend, ht_meet, ht_weekly_summary, ht_consolidated_history, bdt_export, accepted_pm_report, or chart:* aliases.",
+                "description": f"Supported values: backup_times, {chart_type_description()}, ht_meet, ht_weekly_summary, ht_consolidated_history, bdt_export, accepted_pm_report, or chart:* aliases.",
             },
             "site_code": {"type": "string"},
             "site_id": {"type": "string"},
@@ -715,7 +777,8 @@ TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
     },
 }
 
-_WRITE_TOOL_NAMES = {"export_report", "generate_graph", "get_site_dossier"}
+_WRITE_TOOL_NAMES = {"export_report", "get_site_dossier"}
+_OPENROUTER_EXCLUDED_TOOL_NAMES = {"render_chart_widget"}
 
 
 def _mcp_annotations(name: str) -> dict[str, Any]:
@@ -736,6 +799,7 @@ def tool_definitions_for_mcp() -> list[dict[str, Any]]:
             "inputSchema": schema["inputSchema"],
             "outputSchema": schema["outputSchema"],
             "annotations": _mcp_annotations(name),
+            **({"_meta": schema["_meta"]} if "_meta" in schema else {}),
         }
         for name, schema in TOOL_SCHEMAS.items()
     ]
@@ -752,6 +816,7 @@ def tool_definitions_for_openrouter() -> list[dict[str, Any]]:
             },
         }
         for name, schema in TOOL_SCHEMAS.items()
+        if name not in _OPENROUTER_EXCLUDED_TOOL_NAMES
     ]
 
 
@@ -794,9 +859,13 @@ def _validate_tool_arguments(arguments: Any, input_schema: dict[str, Any]) -> di
             if field not in properties:
                 return f"unexpected property: {field}"
 
+    required_fields = set(input_schema.get("required", []))
+
     for field, value in args.items():
         field_schema = properties.get(field, {})
         expected_type = field_schema.get("type")
+        if value is None and field not in required_fields:
+            continue
         if expected_type == "number" and isinstance(value, float) and not math.isfinite(value):
             return f"{field} must be finite"
         if expected_type == "integer" and isinstance(value, float) and math.isinf(value):
diff --git a/mcp_app/chart_widget/build.py b/mcp_app/chart_widget/build.py
new file mode 100644
index 0000000..eaf22e7
--- /dev/null
+++ b/mcp_app/chart_widget/build.py
@@ -0,0 +1,19 @@
+from __future__ import annotations
+
+from pathlib import Path
+
+ROOT = Path(__file__).resolve().parent
+source = ROOT / "src" / "chart_widget.ts"
+out = ROOT / "dist" / "chart.html"
+text = source.read_text(encoding="utf-8")
+out.parent.mkdir(parents=True, exist_ok=True)
+out.write_text(
+    """
+<div id="chart-root"></div>
+<script>
+""".lstrip()
+    + text
+    + "\n</script>\n",
+    encoding="utf-8",
+)
+print(f"Built {out}")
diff --git a/mcp_app/chart_widget/dist/chart.html b/mcp_app/chart_widget/dist/chart.html
new file mode 100644
index 0000000..d0ba2c8
--- /dev/null
+++ b/mcp_app/chart_widget/dist/chart.html
@@ -0,0 +1,161 @@
+<div id="chart-root"></div>
+<script>
+const root = document.getElementById("chart-root");
+const SUPPORTED = new Set(["bar", "horizontal_bar", "line", "donut", "pie", "heatmap", "histogram", "scatter"]);
+
+function css() {
+  return `
+    <style>
+      :root { color-scheme: light dark; }
+      body { margin: 0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
+      .wrap { padding: 14px; color: #111827; background: #ffffff; }
+      @media (prefers-color-scheme: dark) { .wrap { color: #f3f4f6; background: #111827; } .muted { color: #9ca3af; } }
+      .title { font-size: 18px; font-weight: 700; margin-bottom: 6px; }
+      .muted { color: #6b7280; font-size: 12px; }
+      .meta { display: flex; gap: 8px; flex-wrap: wrap; margin: 8px 0 12px; }
+      .pill { border: 1px solid #d1d5db; border-radius: 999px; padding: 3px 8px; font-size: 12px; }
+      .warning { background: #fef3c7; color: #92400e; border-radius: 8px; padding: 8px; margin: 8px 0; }
+      .empty { border: 1px dashed #d1d5db; border-radius: 12px; padding: 20px; text-align: center; }
+      .bars { display: grid; gap: 8px; }
+      .bar-row { display: grid; grid-template-columns: minmax(90px, 30%) 1fr 56px; gap: 8px; align-items: center; font-size: 12px; }
+      .bar-track { height: 12px; border-radius: 999px; background: #e5e7eb; overflow: hidden; }
+      .bar-fill { height: 100%; border-radius: 999px; background: linear-gradient(90deg, #2563eb, #22c55e); }
+      svg { width: 100%; height: 260px; overflow: visible; }
+      .fallback { border: 1px solid #d1d5db; border-radius: 12px; padding: 12px; }
+      table { width: 100%; border-collapse: collapse; font-size: 12px; } th, td { text-align: left; border-bottom: 1px solid #e5e7eb; padding: 6px; }
+    </style>
+  `;
+}
+
+function escapeHtml(value) {
+  return String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char] || char));
+}
+
+function numberValue(value) {
+  const number = Number(value);
+  return Number.isFinite(number) ? number : 0;
+}
+
+function points(payload) {
+  if (payload && Array.isArray(payload.series) && payload.series.length) return payload.series;
+  const labels = payload && Array.isArray(payload.labels) ? payload.labels : [];
+  const values = payload && Array.isArray(payload.values) ? payload.values : [];
+  return labels.map((label, index) => ({ label, value: numberValue(values[index]) }));
+}
+
+function maxValue(items) {
+  return Math.max(1, ...items.map((item) => numberValue(item.value ?? item.y)));
+}
+
+function renderBars(items) {
+  const max = maxValue(items);
+  return `<div class="bars">${items.map((item) => {
+    const value = numberValue(item.value);
+    const pct = Math.max(0, Math.min(100, (value / max) * 100));
+    return `<div class="bar-row"><div>${escapeHtml(item.label)}</div><div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div><div>${escapeHtml(value)}</div></div>`;
+  }).join("")}</div>`;
+}
+
+function renderLine(items) {
+  const max = maxValue(items);
+  const width = 640;
+  const height = 220;
+  const step = items.length > 1 ? width / (items.length - 1) : width;
+  const coords = items.map((item, index) => {
+    const yValue = numberValue(item.value ?? item.y);
+    const x = items.length > 1 ? index * step : width / 2;
+    const y = height - (yValue / max) * (height - 20) + 10;
+    return `${x},${y}`;
+  }).join(" ");
+  return `<svg viewBox="0 0 ${width} ${height}"><polyline points="${coords}" fill="none" stroke="#2563eb" stroke-width="3"/>${coords.split(" ").filter(Boolean).map((pair) => {
+    const [x, y] = pair.split(",");
+    return `<circle cx="${x}" cy="${y}" r="4" fill="#22c55e"/>`;
+  }).join("")}</svg>`;
+}
+
+function renderScatter(items) {
+  const width = 640;
+  const height = 220;
+  const xs = items.map((item) => numberValue(item.x));
+  const ys = items.map((item) => numberValue(item.y ?? item.value));
+  const maxX = Math.max(1, ...xs);
+  const maxY = Math.max(1, ...ys);
+  return `<svg viewBox="0 0 ${width} ${height}">${items.map((item) => {
+    const x = (numberValue(item.x) / maxX) * (width - 30) + 15;
+    const y = height - (numberValue(item.y ?? item.value) / maxY) * (height - 30) - 15;
+    return `<circle cx="${x}" cy="${y}" r="5" fill="#2563eb"><title>${escapeHtml(item.label)}</title></circle>`;
+  }).join("")}</svg>`;
+}
+
+function renderDonut(items) {
+  const total = items.reduce((sum, item) => sum + Math.max(0, numberValue(item.value)), 0) || 1;
+  let offset = 0;
+  const colors = ["#2563eb", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4"];
+  const rings = items.map((item, index) => {
+    const value = Math.max(0, numberValue(item.value));
+    const dash = (value / total) * 100;
+    const circle = `<circle r="70" cx="110" cy="110" fill="transparent" stroke="${colors[index % colors.length]}" stroke-width="34" stroke-dasharray="${dash} ${100 - dash}" stroke-dashoffset="${-offset}"/>`;
+    offset += dash;
+    return circle;
+  }).join("");
+  return `<svg viewBox="0 0 420 220"><g transform="rotate(-90 110 110)">${rings}</g><circle cx="110" cy="110" r="48" fill="white" opacity="0.9"/><foreignObject x="220" y="20" width="190" height="180"><div xmlns="http://www.w3.org/1999/xhtml">${renderLegend(items)}</div></foreignObject></svg>`;
+}
+
+function renderLegend(items) {
+  return items.map((item) => `<div class="muted">${escapeHtml(item.label)}: ${escapeHtml(item.value)}</div>`).join("");
+}
+
+function renderTable(items) {
+  return `<div class="fallback"><div class="muted">Fallback table for advanced chart kind.</div><table><thead><tr><th>Label</th><th>Value</th></tr></thead><tbody>${items.map((item) => `<tr><td>${escapeHtml(item.label ?? item.x)}</td><td>${escapeHtml(item.value ?? item.y)}</td></tr>`).join("")}</tbody></table></div>`;
+}
+
+function renderChart(payload) {
+  const kind = String(payload.chart_kind || "bar");
+  const items = points(payload);
+  if (payload.empty_state || items.length === 0) {
+    return `<div class="empty"><strong>${escapeHtml(payload.empty_state?.title || "No chart data")}</strong><div class="muted">${escapeHtml(payload.empty_state?.message || "No rows matched the selected chart and filters.")}</div></div>`;
+  }
+  if (!SUPPORTED.has(kind)) return renderTable(items);
+  if (kind === "line") return renderLine(items);
+  if (kind === "scatter") return renderScatter(items);
+  if (kind === "donut" || kind === "pie") return renderDonut(items);
+  return renderBars(items);
+}
+
+function render(payload) {
+  if (!root) return;
+  const fallback = window.openai?.toolOutput || window.openai?.toolInput || {};
+  const data = payload && typeof payload === "object" ? payload : fallback;
+  const quality = data.data_quality || {};
+  const filters = data.query_context?.filters || {};
+  const itemCount = points(data).length;
+  const warningHtml = Array.isArray(data.warnings) && data.warnings.length
+    ? data.warnings.map((warning) => `<div class="warning">${escapeHtml(warning)}</div>`).join("")
+    : "";
+  root.innerHTML = `${css()}<div class="wrap">
+    <div class="title">${escapeHtml(data.title || data.chart_id || "Chart")}</div>
+    <div class="meta">
+      <span class="pill">${escapeHtml(data.chart_kind || "chart")}</span>
+      <span class="pill">${escapeHtml(quality.returned_points ?? itemCount)} shown / ${escapeHtml(quality.total_points ?? itemCount)} points</span>
+      ${Object.keys(filters).length ? `<span class="pill">Filters: ${escapeHtml(JSON.stringify(filters))}</span>` : ""}
+    </div>
+    ${warningHtml}
+    ${renderChart(data)}
+  </div>`;
+}
+
+render();
+
+window.addEventListener("message", (event) => {
+  if (event.source !== window.parent) return;
+  const message = event.data;
+  if (!message || message.jsonrpc !== "2.0") return;
+  if (message.method !== "ui/notifications/tool-result") return;
+  render(message.params?.structuredContent);
+}, { passive: true });
+
+window.addEventListener("openai:set_globals", (event) => {
+  render(event.detail?.globals?.toolOutput || window.openai?.toolOutput);
+}, { passive: true });
+
+</script>
diff --git a/mcp_app/chart_widget/src/chart_widget.ts b/mcp_app/chart_widget/src/chart_widget.ts
new file mode 100644
index 0000000..9447831
--- /dev/null
+++ b/mcp_app/chart_widget/src/chart_widget.ts
@@ -0,0 +1,157 @@
+const root = document.getElementById("chart-root");
+const SUPPORTED = new Set(["bar", "horizontal_bar", "line", "donut", "pie", "heatmap", "histogram", "scatter"]);
+
+function css() {
+  return `
+    <style>
+      :root { color-scheme: light dark; }
+      body { margin: 0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
+      .wrap { padding: 14px; color: #111827; background: #ffffff; }
+      @media (prefers-color-scheme: dark) { .wrap { color: #f3f4f6; background: #111827; } .muted { color: #9ca3af; } }
+      .title { font-size: 18px; font-weight: 700; margin-bottom: 6px; }
+      .muted { color: #6b7280; font-size: 12px; }
+      .meta { display: flex; gap: 8px; flex-wrap: wrap; margin: 8px 0 12px; }
+      .pill { border: 1px solid #d1d5db; border-radius: 999px; padding: 3px 8px; font-size: 12px; }
+      .warning { background: #fef3c7; color: #92400e; border-radius: 8px; padding: 8px; margin: 8px 0; }
+      .empty { border: 1px dashed #d1d5db; border-radius: 12px; padding: 20px; text-align: center; }
+      .bars { display: grid; gap: 8px; }
+      .bar-row { display: grid; grid-template-columns: minmax(90px, 30%) 1fr 56px; gap: 8px; align-items: center; font-size: 12px; }
+      .bar-track { height: 12px; border-radius: 999px; background: #e5e7eb; overflow: hidden; }
+      .bar-fill { height: 100%; border-radius: 999px; background: linear-gradient(90deg, #2563eb, #22c55e); }
+      svg { width: 100%; height: 260px; overflow: visible; }
+      .fallback { border: 1px solid #d1d5db; border-radius: 12px; padding: 12px; }
+      table { width: 100%; border-collapse: collapse; font-size: 12px; } th, td { text-align: left; border-bottom: 1px solid #e5e7eb; padding: 6px; }
+    </style>
+  `;
+}
+
+function escapeHtml(value) {
+  return String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char] || char));
+}
+
+function numberValue(value) {
+  const number = Number(value);
+  return Number.isFinite(number) ? number : 0;
+}
+
+function points(payload) {
+  if (payload && Array.isArray(payload.series) && payload.series.length) return payload.series;
+  const labels = payload && Array.isArray(payload.labels) ? payload.labels : [];
+  const values = payload && Array.isArray(payload.values) ? payload.values : [];
+  return labels.map((label, index) => ({ label, value: numberValue(values[index]) }));
+}
+
+function maxValue(items) {
+  return Math.max(1, ...items.map((item) => numberValue(item.value ?? item.y)));
+}
+
+function renderBars(items) {
+  const max = maxValue(items);
+  return `<div class="bars">${items.map((item) => {
+    const value = numberValue(item.value);
+    const pct = Math.max(0, Math.min(100, (value / max) * 100));
+    return `<div class="bar-row"><div>${escapeHtml(item.label)}</div><div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div><div>${escapeHtml(value)}</div></div>`;
+  }).join("")}</div>`;
+}
+
+function renderLine(items) {
+  const max = maxValue(items);
+  const width = 640;
+  const height = 220;
+  const step = items.length > 1 ? width / (items.length - 1) : width;
+  const coords = items.map((item, index) => {
+    const yValue = numberValue(item.value ?? item.y);
+    const x = items.length > 1 ? index * step : width / 2;
+    const y = height - (yValue / max) * (height - 20) + 10;
+    return `${x},${y}`;
+  }).join(" ");
+  return `<svg viewBox="0 0 ${width} ${height}"><polyline points="${coords}" fill="none" stroke="#2563eb" stroke-width="3"/>${coords.split(" ").filter(Boolean).map((pair) => {
+    const [x, y] = pair.split(",");
+    return `<circle cx="${x}" cy="${y}" r="4" fill="#22c55e"/>`;
+  }).join("")}</svg>`;
+}
+
+function renderScatter(items) {
+  const width = 640;
+  const height = 220;
+  const xs = items.map((item) => numberValue(item.x));
+  const ys = items.map((item) => numberValue(item.y ?? item.value));
+  const maxX = Math.max(1, ...xs);
+  const maxY = Math.max(1, ...ys);
+  return `<svg viewBox="0 0 ${width} ${height}">${items.map((item) => {
+    const x = (numberValue(item.x) / maxX) * (width - 30) + 15;
+    const y = height - (numberValue(item.y ?? item.value) / maxY) * (height - 30) - 15;
+    return `<circle cx="${x}" cy="${y}" r="5" fill="#2563eb"><title>${escapeHtml(item.label)}</title></circle>`;
+  }).join("")}</svg>`;
+}
+
+function renderDonut(items) {
+  const total = items.reduce((sum, item) => sum + Math.max(0, numberValue(item.value)), 0) || 1;
+  let offset = 0;
+  const colors = ["#2563eb", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4"];
+  const rings = items.map((item, index) => {
+    const value = Math.max(0, numberValue(item.value));
+    const dash = (value / total) * 100;
+    const circle = `<circle r="70" cx="110" cy="110" fill="transparent" stroke="${colors[index % colors.length]}" stroke-width="34" stroke-dasharray="${dash} ${100 - dash}" stroke-dashoffset="${-offset}"/>`;
+    offset += dash;
+    return circle;
+  }).join("");
+  return `<svg viewBox="0 0 420 220"><g transform="rotate(-90 110 110)">${rings}</g><circle cx="110" cy="110" r="48" fill="white" opacity="0.9"/><foreignObject x="220" y="20" width="190" height="180"><div xmlns="http://www.w3.org/1999/xhtml">${renderLegend(items)}</div></foreignObject></svg>`;
+}
+
+function renderLegend(items) {
+  return items.map((item) => `<div class="muted">${escapeHtml(item.label)}: ${escapeHtml(item.value)}</div>`).join("");
+}
+
+function renderTable(items) {
+  return `<div class="fallback"><div class="muted">Fallback table for advanced chart kind.</div><table><thead><tr><th>Label</th><th>Value</th></tr></thead><tbody>${items.map((item) => `<tr><td>${escapeHtml(item.label ?? item.x)}</td><td>${escapeHtml(item.value ?? item.y)}</td></tr>`).join("")}</tbody></table></div>`;
+}
+
+function renderChart(payload) {
+  const kind = String(payload.chart_kind || "bar");
+  const items = points(payload);
+  if (payload.empty_state || items.length === 0) {
+    return `<div class="empty"><strong>${escapeHtml(payload.empty_state?.title || "No chart data")}</strong><div class="muted">${escapeHtml(payload.empty_state?.message || "No rows matched the selected chart and filters.")}</div></div>`;
+  }
+  if (!SUPPORTED.has(kind)) return renderTable(items);
+  if (kind === "line") return renderLine(items);
+  if (kind === "scatter") return renderScatter(items);
+  if (kind === "donut" || kind === "pie") return renderDonut(items);
+  return renderBars(items);
+}
+
+function render(payload) {
+  if (!root) return;
+  const fallback = window.openai?.toolOutput || window.openai?.toolInput || {};
+  const data = payload && typeof payload === "object" ? payload : fallback;
+  const quality = data.data_quality || {};
+  const filters = data.query_context?.filters || {};
+  const itemCount = points(data).length;
+  const warningHtml = Array.isArray(data.warnings) && data.warnings.length
+    ? data.warnings.map((warning) => `<div class="warning">${escapeHtml(warning)}</div>`).join("")
+    : "";
+  root.innerHTML = `${css()}<div class="wrap">
+    <div class="title">${escapeHtml(data.title || data.chart_id || "Chart")}</div>
+    <div class="meta">
+      <span class="pill">${escapeHtml(data.chart_kind || "chart")}</span>
+      <span class="pill">${escapeHtml(quality.returned_points ?? itemCount)} shown / ${escapeHtml(quality.total_points ?? itemCount)} points</span>
+      ${Object.keys(filters).length ? `<span class="pill">Filters: ${escapeHtml(JSON.stringify(filters))}</span>` : ""}
+    </div>
+    ${warningHtml}
+    ${renderChart(data)}
+  </div>`;
+}
+
+render();
+
+window.addEventListener("message", (event) => {
+  if (event.source !== window.parent) return;
+  const message = event.data;
+  if (!message || message.jsonrpc !== "2.0") return;
+  if (message.method !== "ui/notifications/tool-result") return;
+  render(message.params?.structuredContent);
+}, { passive: true });
+
+window.addEventListener("openai:set_globals", (event) => {
+  render(event.detail?.globals?.toolOutput || window.openai?.toolOutput);
+}, { passive: true });
diff --git a/tests/test_chat_panel.py b/tests/test_chat_panel.py
index ff7cd98..d8344c4 100644
--- a/tests/test_chat_panel.py
+++ b/tests/test_chat_panel.py
@@ -9,6 +9,7 @@ from PyQt5.QtWidgets import QApplication, QLabel, QTableWidget
 from alarm_app.styles import STYLE_DARK, STYLE_LIGHT
 from alarm_app.ui.panels.chat_panel import (
     ChatPanel,
+    _graph_pixmap_from_result,
     _alarm_row_columns,
     _json_output_text,
     _normalize_message_text,
@@ -506,6 +507,19 @@ def test_message_bubble_width_caps_on_small_and_large_panels():
     assert ChatPanel._message_bubble_width(1000, "system") == 760
 
 
+def test_graph_pixmap_can_fall_back_to_base64_payload():
+    _ensure_qapp()
+    result = {
+        "path": "[local path redacted]",
+        "mime_type": "image/png",
+        "image_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4//8/AAX+Av4N70a4AAAAAElFTkSuQmCC",
+    }
+
+    pixmap = _graph_pixmap_from_result(result)
+
+    assert not pixmap.isNull()
+
+
 def test_display_graph_type_removes_underscores():
     assert ChatPanel._display_graph_type("alarm_daily_counts") == "Alarm Daily Counts"
     assert ChatPanel._display_graph_type(None) == "--"
diff --git a/tests/test_e2e_backend.py b/tests/test_e2e_backend.py
index 24cdfaf..44b17eb 100644
--- a/tests/test_e2e_backend.py
+++ b/tests/test_e2e_backend.py
@@ -264,7 +264,7 @@ class TestMcpConnectorE2E:
         assert payload["jsonrpc"] == "2.0"
         assert payload["id"] == 1
         assert payload["result"]["serverInfo"]["name"] == "alarm-viewer-local-data"
-        assert payload["result"]["capabilities"] == {"tools": {}}
+        assert payload["result"]["capabilities"] == {"tools": {}, "resources": {}}
 
     def test_mcp_tools_list_includes_chatgpt_safety_annotations(self, client, monkeypatch):
         monkeypatch.setenv("ALARM_MCP_TOKEN", "secret-token")
@@ -278,6 +278,15 @@ class TestMcpConnectorE2E:
 
         assert r.status_code == 200
         tools = {tool["name"]: tool for tool in r.json()["result"]["tools"]}
+        assert "generate_graph" not in tools
+        assert "list_chart_types" in tools
+        assert "get_chart_data" in tools
+        assert tools["render_chart_widget"]["_meta"] == {
+            "openai/outputTemplate": "ui://widget/chart.html",
+            "ui": {"resourceUri": "ui://widget/chart.html"},
+            "openai/toolInvocation/invoking": "Rendering chart...",
+            "openai/toolInvocation/invoked": "Chart ready.",
+        }
         assert tools["query_alarms"]["annotations"] == {"readOnlyHint": True}
         assert tools["export_report"]["annotations"] == {
             "readOnlyHint": False,
@@ -304,6 +313,97 @@ class TestMcpConnectorE2E:
         assert r.status_code == 400
         assert r.json()["detail"] == "MCP requests must use JSON-RPC 2.0"
 
+    def test_mcp_generate_graph_is_not_public_over_http(self, client, monkeypatch):
+        monkeypatch.setenv("ALARM_MCP_TOKEN", "secret-token")
+
+        r = client.post("/mcp?token=secret-token", json={
+            "jsonrpc": "2.0",
+            "id": "chart",
+            "method": "tools/call",
+            "params": {"name": "generate_graph", "arguments": {"graph_type": "alarm_category_counts"}},
+        })
+
+        assert r.status_code == 200
+        payload = r.json()["result"]
+        assert payload["isError"] is True
+        assert payload["structuredContent"] == {"error": "unknown tool: generate_graph"}
+        assert len(payload["content"]) == 1
+        assert payload["content"][0]["type"] == "text"
+
+    def test_mcp_resources_list_returns_chart_widget(self, client, monkeypatch):
+        monkeypatch.setenv("ALARM_MCP_TOKEN", "secret-token")
+
+        r = client.post("/mcp?token=secret-token", json={
+            "jsonrpc": "2.0",
+            "id": "resources",
+            "method": "resources/list",
+            "params": {},
+        })
+
+        assert r.status_code == 200
+        assert r.json()["result"]["resources"] == [
+            {
+                "uri": "ui://widget/chart.html",
+                "name": "chart-widget",
+                "title": "Alarm Chart Widget",
+                "mimeType": "text/html;profile=mcp-app",
+            }
+        ]
+
+
+    def test_mcp_resources_read_returns_chart_widget_html(self, client, monkeypatch):
+        monkeypatch.setenv("ALARM_MCP_TOKEN", "secret-token")
+
+        r = client.post("/mcp?token=secret-token", json={
+            "jsonrpc": "2.0",
+            "id": "resource",
+            "method": "resources/read",
+            "params": {"uri": "ui://widget/chart.html"},
+        })
+
+        assert r.status_code == 200
+        payload = r.json()
+        content = payload["result"]["contents"][0]
+        assert content["uri"] == "ui://widget/chart.html"
+        assert content["mimeType"] == "text/html;profile=mcp-app"
+        assert 'id="chart-root"' in content["text"]
+        assert "window.openai" in content["text"]
+        assert "ui/notifications/tool-result" in content["text"]
+
+    def test_mcp_render_chart_widget_returns_structured_data_and_ui_metadata(self, client, monkeypatch):
+        monkeypatch.setenv("ALARM_MCP_TOKEN", "secret-token")
+
+        r = client.post("/mcp?token=secret-token", json={
+            "jsonrpc": "2.0",
+            "id": "render",
+            "method": "tools/call",
+            "params": {
+                "name": "render_chart_widget",
+                "arguments": {
+                    "chart_id": "alarm_category_counts",
+                    "chart_kind": "bar",
+                    "title": "Alarm Category Counts",
+                    "labels": ["Power"],
+                    "values": [2.0],
+                    "series": [{"label": "Power", "value": 2.0}],
+                    "warnings": [],
+                    "data_quality": {"total_points": 1, "returned_points": 1, "truncated": False},
+                    "query_context": {"filters": {"site_code": "AAA001"}},
+                    "empty_state": None,
+                },
+            },
+        })
+
+        assert r.status_code == 200
+        payload = r.json()["result"]
+        assert payload["structuredContent"]["chart_id"] == "alarm_category_counts"
+        assert payload["structuredContent"]["series"] == [{"label": "Power", "value": 2.0}]
+        assert payload["_meta"] == {
+            "openai/outputTemplate": "ui://widget/chart.html",
+            "ui": {"resourceUri": "ui://widget/chart.html"},
+        }
+
+
 
 # ---------------------------------------------------------------------------
 # Alarm upsert + query
diff --git a/tests/test_llm_tools.py b/tests/test_llm_tools.py
index 10abf9b..c3823df 100644
--- a/tests/test_llm_tools.py
+++ b/tests/test_llm_tools.py
@@ -2,6 +2,9 @@ import base64
 import hashlib
 import json
 import operator
+import shutil
+import subprocess
+import sys
 from datetime import date
 from pathlib import Path
 from types import SimpleNamespace
@@ -12,6 +15,7 @@ import pandas as pd
 import alarm_app.llm_tools.openrouter_agent as openrouter_agent_mod
 import alarm_app.llm_tools.service as service_mod
 from alarm_app.data import alarm_store
+from alarm_app.llm_tools.charts import CHART_SPECS, chart_type_ids
 from alarm_app.llm_tools.mcp_server import AlarmViewerMcpServer
 from alarm_app.llm_tools.openrouter_agent import (
     CONTEXT_TOO_LARGE_MESSAGE,
@@ -731,14 +735,21 @@ def test_tool_definitions_are_available_for_mcp_and_openrouter():
     assert "get_computed_report" in mcp_names
     assert "get_computed_report" in openrouter_names
     assert "get_site_dossier" in mcp_names
-    assert "generate_graph" in mcp_names
+    assert "list_chart_types" in mcp_names
+    assert "list_chart_types" in openrouter_names
+    assert "get_chart_data" in mcp_names
+    assert "get_chart_data" in openrouter_names
+    assert "render_chart_widget" in mcp_names
+    assert "render_chart_widget" not in openrouter_names
+    assert "generate_graph" not in mcp_names
+    assert "generate_graph" not in openrouter_names
     assert "export_report" in openrouter_names
     assert "search_site_metadata" in mcp_names
     assert "query_site_metadata" in mcp_names
     assert "query_bdt_summary" in mcp_names
     assert "query_bdt_full" in mcp_names
     assert "get_site_alarm_context" in mcp_names
-    assert mcp_names == openrouter_names
+    assert openrouter_names == mcp_names - {"render_chart_widget"}
 
 
 def test_openrouter_tool_definitions_do_not_include_mcp_annotations():
@@ -780,6 +791,54 @@ def test_get_computed_report_schema_includes_expected_report_types():
     assert "accepted_pm_report" in description
 
 
+def test_chart_registry_drives_data_schema_and_discovery_tool():
+    graph_ids = chart_type_ids(renderable_only=True)
+    schema_ids = TOOL_SCHEMAS["get_chart_data"]["inputSchema"]["properties"]["chart_id"]["enum"]
+
+    assert schema_ids == graph_ids
+    assert "list_chart_types" in TOOL_SCHEMAS
+    assert "generate_graph" not in TOOL_SCHEMAS
+    assert "alarm_category_share" in graph_ids
+    assert "alarm_volume_trend" in graph_ids
+    assert "alarm_heatmap_day_hour" in graph_ids
+    assert "backup_time_by_site" in graph_ids
+    assert "bdt_rule_failure_counts" in graph_ids
+
+    service = LocalDataService()
+    result = dispatch_tool(service, "list_chart_types", {"family": "alarm", "renderable_only": True})
+
+    assert result["count"] >= 1
+    assert all(chart["family"] == "alarm" for chart in result["charts"])
+    assert {chart["chart_id"] for chart in result["charts"]}.issubset(set(graph_ids))
+    assert all(chart["chart_kind"] for chart in result["charts"])
+
+
+def test_chart_registry_contains_all_documented_chart_kinds():
+    kinds = {spec.chart_kind for spec in CHART_SPECS.values()}
+
+    for expected in {
+        "bar",
+        "horizontal_bar",
+        "pie",
+        "donut",
+        "line",
+        "stacked_bar",
+        "histogram",
+        "box",
+        "scatter",
+        "heatmap",
+        "calendar_heatmap",
+        "pareto",
+        "timeline",
+        "gauge",
+        "treemap",
+        "radar",
+        "sankey",
+        "funnel",
+    }:
+        assert expected in kinds
+
+
 def test_get_computed_report_schema_adds_period_and_section_fields():
     schema = TOOL_SCHEMAS["get_computed_report"]["inputSchema"]["properties"]
 
@@ -2959,6 +3018,185 @@ def test_get_site_dossier_exports_full_site_workbook(tmp_path, monkeypatch):
     assert Path(result["export_path"]).exists()
 
 
+def test_get_chart_data_returns_deterministic_structured_payload(tmp_path, monkeypatch):
+    service = LocalDataService(export_dir=tmp_path / "exports")
+    alarm_df = pd.DataFrame([
+        {"site_id": "AAA001", "alarm_category": "Power", "occurred_on": "2026-04-01"},
+        {"site_id": "AAA001", "alarm_category": "Down", "occurred_on": "2026-04-02"},
+        {"site_id": "AAA001", "alarm_category": "Power", "occurred_on": "2026-04-03"},
+    ])
+    monkeypatch.setattr(service, "_alarm_rows_for_sites", lambda site_keys, date_from=None, date_to=None, **kwargs: alarm_df)
+
+    result = service.get_chart_data(
+        chart_id="alarm_category_counts",
+        filters={"site_code": "AAA001"},
+        max_points=1,
+    )
+
+    assert result["chart_id"] == "alarm_category_counts"
+    assert result["chart_kind"] == "bar"
+    assert result["title"] == "Alarm Category Counts"
+    assert result["labels"] == ["Power"]
+    assert result["values"] == [2.0]
+    assert result["series"] == [{"label": "Power", "value": 2.0}]
+    assert result["x_axis"] == {"label": "Category"}
+    assert result["y_axis"] == {"label": "Count"}
+    assert result["warnings"] == ["Series truncated from 2 to 1 points."]
+    assert result["data_quality"] == {"total_points": 2, "returned_points": 1, "truncated": True}
+    assert result["query_context"]["filters"] == {"site_code": "AAA001"}
+    assert result["empty_state"] is None
+    assert "image_base64" not in result
+    assert "path" not in result
+
+
+def test_get_chart_data_clamps_max_points_and_reports_empty_state(tmp_path, monkeypatch):
+    service = LocalDataService(export_dir=tmp_path / "exports")
+    monkeypatch.setattr(service, "_alarm_rows_for_sites", lambda site_keys, date_from=None, date_to=None, **kwargs: pd.DataFrame())
+
+    result = service.get_chart_data(
+        chart_id="alarm_category_counts",
+        filters={"site_code": "AAA001"},
+        max_points=9999,
+    )
+
+    assert result["labels"] == []
+    assert result["values"] == []
+    assert result["series"] == []
+    assert result["warnings"] == ["max_points clamped from 9999 to 500."]
+    assert result["data_quality"] == {"total_points": 0, "returned_points": 0, "truncated": False}
+    assert result["empty_state"] == {
+        "title": "No chart data",
+        "message": "No rows matched the selected chart and filters.",
+    }
+
+
+def test_render_chart_widget_returns_apps_sdk_metadata():
+    service = LocalDataService()
+    payload = {
+        "chart_id": "alarm_category_counts",
+        "chart_kind": "bar",
+        "title": "Alarm Category Counts",
+        "labels": ["Power"],
+        "values": [2.0],
+        "series": [{"label": "Power", "value": 2.0}],
+        "x_axis": {"label": "Category"},
+        "y_axis": {"label": "Count"},
+        "warnings": [],
+        "data_quality": {"total_points": 1, "returned_points": 1, "truncated": False},
+        "query_context": {"filters": {"site_code": "AAA001"}},
+        "empty_state": None,
+    }
+
+    result = service.render_chart_widget(**payload)
+
+    assert result["chart_id"] == payload["chart_id"]
+    assert result["series"] == payload["series"]
+    assert result["_meta"] == {
+        "openai/outputTemplate": "ui://widget/chart.html",
+        "ui": {"resourceUri": "ui://widget/chart.html"},
+    }
+
+
+def test_mcp_server_exposes_chart_widget_resource_and_render_meta():
+    class _Service:
+        def render_chart_widget(self, **kwargs):
+            return {
+                **kwargs,
+                "_meta": {
+                    "openai/outputTemplate": "ui://widget/chart.html",
+                    "ui": {"resourceUri": "ui://widget/chart.html"},
+                },
+            }
+
+    server = AlarmViewerMcpServer(service=_Service())
+
+    initialized = server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
+    assert initialized["result"]["capabilities"]["resources"] == {}
+
+    listed = server.handle({"jsonrpc": "2.0", "id": 2, "method": "resources/list", "params": {}})
+    resources = listed["result"]["resources"]
+    assert resources == [
+        {
+            "uri": "ui://widget/chart.html",
+            "name": "chart-widget",
+            "title": "Alarm Chart Widget",
+            "mimeType": "text/html;profile=mcp-app",
+        }
+    ]
+
+    read = server.handle({
+        "jsonrpc": "2.0",
+        "id": 3,
+        "method": "resources/read",
+        "params": {"uri": "ui://widget/chart.html"},
+    })
+    content = read["result"]["contents"][0]
+    assert content["uri"] == "ui://widget/chart.html"
+    assert content["mimeType"] == "text/html;profile=mcp-app"
+    assert "window.openai" in content["text"]
+    assert "ui/notifications/tool-result" in content["text"]
+    assert 'id="chart-root"' in content["text"]
+    assert content["_meta"] == {"ui": {"prefersBorder": True}}
+
+    called = server.handle({
+        "jsonrpc": "2.0",
+        "id": 4,
+        "method": "tools/call",
+        "params": {
+            "name": "render_chart_widget",
+            "arguments": {
+                "chart_id": "alarm_category_counts",
+                "chart_kind": "bar",
+                "title": "Alarm Category Counts",
+                "labels": ["Power"],
+                "values": [1],
+                "series": [{"label": "Power", "value": 1}],
+            },
+        },
+    })
+    assert called["result"]["_meta"] == {
+        "openai/outputTemplate": "ui://widget/chart.html",
+        "ui": {"resourceUri": "ui://widget/chart.html"},
+    }
+    assert called["result"]["structuredContent"]["chart_id"] == "alarm_category_counts"
+
+
+def test_mcp_server_returns_resource_error_when_widget_build_missing(tmp_path, monkeypatch):
+    missing_widget = tmp_path / "missing" / "chart.html"
+    monkeypatch.setattr("alarm_app.llm_tools.mcp_server._WIDGET_HTML_PATH", missing_widget)
+    server = AlarmViewerMcpServer(service=LocalDataService())
+
+    response = server.handle({
+        "jsonrpc": "2.0",
+        "id": 1,
+        "method": "resources/read",
+        "params": {"uri": "ui://widget/chart.html"},
+    })
+
+    assert response["error"]["code"] == -32002
+    assert "chart widget build artifact missing" in response["error"]["message"]
+    assert "chart_widget.ts" not in response["error"]["message"]
+
+
+def test_chart_widget_package_builds(tmp_path):
+    package_path = Path(__file__).resolve().parents[1] / "mcp_app" / "chart_widget" / "package.json"
+    widget_dir = package_path.parent
+    temp_widget_dir = tmp_path / "chart_widget"
+    dist_path = temp_widget_dir / "dist" / "chart.html"
+
+    assert package_path.exists()
+    shutil.copytree(widget_dir, temp_widget_dir)
+    dist_path.unlink(missing_ok=True)
+    subprocess.run([sys.executable, "build.py"], cwd=temp_widget_dir, check=True)
+
+    html = dist_path.read_text(encoding="utf-8")
+    assert 'id="chart-root"' in html
+    assert "ui/notifications/tool-result" in html
+    assert "type ChartPoint" not in html
+    assert "declare global" not in html
+    assert " as HTMLElement" not in html
+
+
 def test_generate_graph_writes_png_from_alarm_data(tmp_path, monkeypatch):
     service = LocalDataService(export_dir=tmp_path / "exports")
     alarm_df = pd.DataFrame([
@@ -2966,15 +3204,56 @@ def test_generate_graph_writes_png_from_alarm_data(tmp_path, monkeypatch):
         {"site_id": "AAA001", "alarm_category": "Down", "occurred_on": "2026-04-02"},
         {"site_id": "AAA001", "alarm_category": "Power", "occurred_on": "2026-04-03"},
     ])
-    monkeypatch.setattr(service, "_alarm_rows_for_sites", lambda site_keys, date_from=None, date_to=None: alarm_df)
+    monkeypatch.setattr(service, "_alarm_rows_for_sites", lambda site_keys, date_from=None, date_to=None, **kwargs: alarm_df)
 
     result = service.generate_graph(graph_type="alarm_category_counts", site_code="AAA001")
 
     assert result["points"] == 2
+    assert result["chart_kind"] == "bar"
+    assert result["mime_type"] == "image/png"
+    assert result["width"] > 0
+    assert result["height"] > 0
+    assert base64.b64decode(result["image_base64"]).startswith(b"\x89PNG")
+    assert result["series"] == [{"label": "Power", "value": 2.0}, {"label": "Down", "value": 1.0}]
     assert Path(result["path"]).exists()
     assert Path(result["path"]).suffix == ".png"
 
 
+def test_generate_graph_supports_non_bar_chart_kinds(tmp_path, monkeypatch):
+    service = LocalDataService(export_dir=tmp_path / "exports")
+    alarm_df = pd.DataFrame([
+        {"site_id": "AAA001", "alarm_category": "Power", "occurred_on": "2026-04-01 03:00:00"},
+        {"site_id": "AAA001", "alarm_category": "Down", "occurred_on": "2026-04-01 04:00:00"},
+        {"site_id": "AAA001", "alarm_category": "Power", "occurred_on": "2026-04-02 04:00:00"},
+    ])
+    monkeypatch.setattr(service, "_alarm_rows_for_sites", lambda site_keys, date_from=None, date_to=None, **kwargs: alarm_df)
+
+    pie = service.generate_graph(graph_type="alarm_category_share", site_code="AAA001")
+    heatmap = service.generate_graph(graph_type="alarm_heatmap_day_hour", site_code="AAA001")
+
+    assert pie["chart_kind"] == "donut"
+    assert base64.b64decode(pie["image_base64"]).startswith(b"\x89PNG")
+    assert heatmap["chart_kind"] == "heatmap"
+    assert heatmap["points"] == 3
+    assert base64.b64decode(heatmap["image_base64"]).startswith(b"\x89PNG")
+
+
+def test_mcp_generate_graph_is_not_exposed_as_public_tool():
+    server = AlarmViewerMcpServer(service=LocalDataService())
+
+    response = server.handle({
+        "jsonrpc": "2.0",
+        "id": 1,
+        "method": "tools/call",
+        "params": {"name": "generate_graph", "arguments": {"graph_type": "alarm_category_counts"}},
+    })
+
+    content = response["result"]["content"]
+    assert len(content) == 1
+    assert response["result"]["isError"] is True
+    assert response["result"]["structuredContent"] == {"error": "unknown tool: generate_graph"}
+
+
 def test_alarm_source_selection_skips_empty_primary_dict_results(tmp_path, monkeypatch):
     primary = tmp_path / "alarms.duckdb"
     fallback = tmp_path / "alarms.local.duckdb"
diff --git a/ui/panels/chat_panel.py b/ui/panels/chat_panel.py
index 81b41f7..825246e 100644
--- a/ui/panels/chat_panel.py
+++ b/ui/panels/chat_panel.py
@@ -2,6 +2,7 @@
 
 from __future__ import annotations
 
+import base64
 import html
 import json
 import re
@@ -369,6 +370,22 @@ def _build_upload_context_lines(uploads: list[dict[str, str]]) -> list[str]:
     return lines
 
 
+def _graph_pixmap_from_result(result: dict) -> QPixmap:
+    path = str(result.get("path") or "")
+    pixmap = QPixmap(path)
+    if not pixmap.isNull():
+        return pixmap
+    encoded = str(result.get("image_base64") or result.get("base64") or "")
+    if not encoded:
+        return pixmap
+    try:
+        payload = base64.b64decode(encoded, validate=True)
+    except Exception:
+        return pixmap
+    pixmap.loadFromData(payload, str(result.get("mime_type") or "image/png").encode("ascii", errors="ignore"))
+    return pixmap
+
+
 def _output_paths(value: object) -> list[str]:
     paths: list[str] = []
 
@@ -1386,7 +1403,10 @@ class ChatPanel(QWidget):
             "Supported export_report report_type values include alarms, bdt_results, photo_manifest, site_alarm_report, accepted_pm_report, and bdt_export.",
             "Use site_alarm_report for uploaded VIP/site lists, accepted_pm_report for uploaded Accepted PM lists, and bdt_export for BDT validation workbook exports.",
             "Use get_site_dossier when the user asks for everything about one site: all alarms, BDT tests, rule details, photos, and discharge content.",
-            "Use generate_graph when the user asks for graphs/charts/trends; it creates a PNG chart from local data.",
+            "Use list_chart_types when the user asks what charts are available or asks vaguely for the best chart type.",
+            "Use get_chart_data when the user wants chart-ready labels, values, or series; server-side PNG chart generation is not exposed as a chat tool.",
+            "Use render_chart_widget only when an Apps SDK client needs to render a validated get_chart_data payload.",
+            "Use get_computed_report when the user wants report-like chart data without presentation metadata.",
             "Use query_backup_times when the user asks for backup time, backup duration, or battery hold-up between Power and Down alarms.",
         ]
         attrs = self.__dict__
@@ -1618,6 +1638,9 @@ class ChatPanel(QWidget):
             "get_photo_metadata": "Photo Metadata",
             "get_site_dossier": "Site Dossier",
             "get_site_full_context": "Site Full Context",
+            "list_chart_types": "Chart Types",
+            "get_chart_data": "Chart Data",
+            "render_chart_widget": "Chart Widget",
             "generate_graph": "Generated Graph",
             "read_photo_blob": "Photo Blob",
             "export_report": "Export Report",
@@ -2010,7 +2033,7 @@ class ChatPanel(QWidget):
             "points": result.get("points"),
         }))
         path = str(result.get("path") or "")
-        pixmap = QPixmap(path)
+        pixmap = _graph_pixmap_from_result(result)
         if not pixmap.isNull():
             btn_zoom = _make_assistant_button("Zoom Image")
             btn_zoom.clicked.connect(lambda _checked=False, p=path: self._open_image_preview(p, title=Path(p).name))

exec
/bin/zsh -lc "sed -n '1,260p' llm_tools/service.py && sed -n '260,620p' llm_tools/service.py && sed -n '620,980p' llm_tools/service.py" in /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
 succeeded in 0ms:
"""Guarded local data access for MCP/OpenRouter agents."""

from __future__ import annotations

import base64
import hashlib
import json
import math
import re
from dataclasses import asdict, is_dataclass, replace
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import func
from sqlalchemy import inspect as sa_inspect

try:
    from alarm_app.bdt.export import build_bdt_export_sheets
    from alarm_app.core.battery_backup_insights import (
        build_battery_backup_insight,
        coerce_number as _insight_number,
    )
    from alarm_app.core.backup_time import compute_backup_times
    from alarm_app.core.temp_alarm import (
        DEFAULT_HT_HISTORY_START_WEEK,
        _compute_ht_meet_frames,
        _filter_source_from_week,
        build_temp_alarm_summary,
        compute_ht_meet_rows,
    )
    from alarm_app.data import alarm_store, catalog_store, state
    from alarm_app.data.site_report import (
        build_pm_accept_report,
        build_site_alarm_report,
        collect_site_sheet_keys,
        infer_site_id_column,
        normalize_site_key,
        read_pm_accept_sheet,
    )
    from alarm_app.db import engine as db_engine
    from alarm_app.db.models import (
        BDTPhoto,
        BDTTest,
        BlobAsset,
        PMRuleCatalog,
        PMRuleResult,
        PMValidationRun,
        ReviewEvent,
        UploadedFile,
    )
    from alarm_app.db.repos import blob_repo
    from alarm_app.db.repos.pm_repo import load_all_validation_results
    from alarm_app.llm_tools import federated_site
    from alarm_app.llm_tools.charts import CHART_SPECS, chart_specs_payload
except ImportError:
    from bdt.export import build_bdt_export_sheets
    from core.battery_backup_insights import (
        build_battery_backup_insight,
        coerce_number as _insight_number,
    )
    from core.backup_time import compute_backup_times
    from core.temp_alarm import (
        DEFAULT_HT_HISTORY_START_WEEK,
        _compute_ht_meet_frames,
        _filter_source_from_week,
        build_temp_alarm_summary,
        compute_ht_meet_rows,
    )
    from data import alarm_store, catalog_store, state
    from data.site_report import (
        build_pm_accept_report,
        build_site_alarm_report,
        collect_site_sheet_keys,
        infer_site_id_column,
        normalize_site_key,
        read_pm_accept_sheet,
    )
    from db import engine as db_engine
    from db.models import (
        BDTPhoto,
        BDTTest,
        BlobAsset,
        PMRuleCatalog,
        PMRuleResult,
        PMValidationRun,
        ReviewEvent,
        UploadedFile,
    )
    from db.repos import blob_repo
    from db.repos.pm_repo import load_all_validation_results
    from llm_tools import federated_site
    from llm_tools.charts import CHART_SPECS, chart_specs_payload

MAX_QUERY_LIMIT = 500
MAX_BLOB_BYTES = 5 * 1024 * 1024
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
EXPORT_DIR = Path.home() / ".alarm_viewer" / "exports"
ALLOWED_UPLOAD_SUFFIXES = {".csv", ".xls", ".xlsx"}
MCP_DEFAULT_PAGE_LIMIT = 500
MCP_MAX_PAGE_LIMIT = 500
CHART_WIDGET_URI = "ui://widget/chart.html"
CHART_WIDGET_MIME_TYPE = "text/html;profile=mcp-app"
CHART_DATA_MAX_POINTS = 500
_FIELD_ALIASES = {
    "site_name": ("site_name", "sitename", "name"),
    "area": ("area", "orange_area", "orangearea"),
    "contractor": ("contractor",),
    "subcontractor": ("subcontractor", "sub_contractor", "subcontractor_name"),
    "office": ("office", "fm_office", "orange_office", "office_name"),
    "vip": ("vip", "is_vip", "vip_status"),
    "backup_status": ("backup_status", "backupstatus"),
    "battery_status": ("battery_status", "batterystatus"),
}
_RAW_JSON_FIELDS = {"raw_data_json", "original_headers_json", "evidence_json", "payload_json"}
_PATH_FIELD_NAMES = {"path", "local_path", "original_path", "source_path", "file_path"}
_LOCAL_PATH_REDACTED = "[local path redacted]"
_LOCAL_PATH_ROOTS = r"Users|private|var|tmp|Volumes|home|opt|usr|etc"
_LOCAL_PATH_EXTENSION_CHAIN = r"[A-Za-z0-9]{1,12}(?:\.[A-Za-z0-9]{1,12})*"
_LOCAL_PATH_TOKEN = r"[^\s\"'\n\r\t\f\v,;:)\]}]+"
_LOCAL_PATH_SPACE_WORD = r"[^\s\"'\n\r\t\f\v,;:)\]}\\/]+"
_LOCAL_PATH_PROSE_LEADERS = r"with|for|during|before|after|while|and|or|but|then|when|from|to|in|on|at|ratio|backup"
_LOCAL_PATH_SPACE_LEADER = rf"(?!(?i:{_LOCAL_PATH_PROSE_LEADERS})\b){_LOCAL_PATH_SPACE_WORD}"
_LOCAL_PATH_SPACE_CONTINUATION = (
    rf"(?:[ \t]+{_LOCAL_PATH_SPACE_LEADER}(?:[ \t]+{_LOCAL_PATH_SPACE_WORD})*[\\/]{_LOCAL_PATH_TOKEN})*"
)
_LOCAL_PATH_VALUE_PATTERN = re.compile(
    rf"(?<![\w:])(?:"
    rf"(?:/(?:{_LOCAL_PATH_ROOTS})(?:/[^\"'\n\r\t\f\v]+)*)"
    r"|"
    r"(?:[A-Za-z]:[\\/][^\"'\n\r\t\f\v]+)"
    r"|"
    r"(?:\\\\[^\"'\n\r\t\f\v]+)"
    r")"
)
_LOCAL_PATH_QUOTED_PATTERN = re.compile(
    rf"(?P<quote>[\"'])(?P<path>(?:/(?:{_LOCAL_PATH_ROOTS})(?:/[^\"'\n\r\t\f\v]+)*"
    r"|"
    r"[A-Za-z]:[\\/][^\"'\n\r\t\f\v]+"
    r"|"
    r"\\\\[^\"'\n\r\t\f\v]+))(?P=quote)"
)
_LOCAL_PATH_WITH_EXTENSION_PATTERN = re.compile(
    rf"(?<![\w:])(?:"
    rf"(?:/(?:{_LOCAL_PATH_ROOTS})(?:/[^\"'\n\r\t\f\v]+?)+\.(?:{_LOCAL_PATH_EXTENSION_CHAIN}))"
    r"|"
    rf"(?:[A-Za-z]:[\\/][^\"'\n\r\t\f\v]+?\.(?:{_LOCAL_PATH_EXTENSION_CHAIN}))"
    r"|"
    rf"(?:\\\\[^\"'\n\r\t\f\v]+?\.(?:{_LOCAL_PATH_EXTENSION_CHAIN}))"
    r")"
    r"(?=$|[\s,.;:)\]}\"'])"
)
_LOCAL_PATH_PATTERN = re.compile(
    rf"(?<![\w:])(?:"
    rf"(?:/(?:{_LOCAL_PATH_ROOTS})(?:/{_LOCAL_PATH_TOKEN})+)"
    r"|"
    rf"(?:[A-Za-z]:[\\/]{_LOCAL_PATH_TOKEN})"
    r"|"
    rf"(?:\\\\{_LOCAL_PATH_TOKEN})"
    r")"
    rf"{_LOCAL_PATH_SPACE_CONTINUATION}"
)


def _jsonable(value: Any) -> Any:
    if value is pd.NaT:
        return None
    if isinstance(value, (datetime, date, pd.Timestamp)):
        if pd.isna(value):
            return None
        return pd.Timestamp(value).isoformat()
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if value is not None and not isinstance(value, (list, dict, tuple, set)):
        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            pass
    return value


def _is_path_like_field(field: Any) -> bool:
    key_text = str(field)
    lowered = key_text.lower()
    if lowered in _PATH_FIELD_NAMES:
        return True
    if lowered.endswith("_path"):
        return True
    if "file_path" in lowered:
        return True
    return " " in key_text and "path" in lowered


def _looks_like_local_path(value: str) -> bool:
    value_text = value.strip()
    if not value_text:
        return False
    if not _LOCAL_PATH_VALUE_PATTERN.fullmatch(value_text):
        return False
    return "/" in value_text or "\\" in value_text


def _sanitize_local_paths_in_text(value: str) -> str:
    text = _LOCAL_PATH_QUOTED_PATTERN.sub(
        lambda match: f"{match.group('quote')}{_LOCAL_PATH_REDACTED}{match.group('quote')}",
        str(value),
    )
    text = _LOCAL_PATH_WITH_EXTENSION_PATTERN.sub(_LOCAL_PATH_REDACTED, text)
    return _LOCAL_PATH_PATTERN.sub(_LOCAL_PATH_REDACTED, text)


def _sanitize_mcp_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(_sanitize_key): _sanitize_mcp_value(v) for _sanitize_key, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_mcp_value(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_mcp_value(v) for v in value)
    if isinstance(value, set):
        return [_sanitize_mcp_value(v) for v in value]
    if isinstance(value, str):
        if _looks_like_local_path(value):
            return _LOCAL_PATH_REDACTED
        return _sanitize_local_paths_in_text(value)
    return _jsonable(value)


def _chart_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _normalize_chart_point(point: Any) -> dict[str, Any]:
    if not isinstance(point, dict):
        point = {"label": str(point), "value": 0.0}
    normalized = _sanitize_mcp_value(point)
    if not isinstance(normalized, dict):
        return {"label": str(normalized), "value": 0.0}
    for numeric_key in ("value", "x", "y"):
        if numeric_key in normalized:
            number = _chart_number(normalized.get(numeric_key))
            if number is None:
                normalized.pop(numeric_key, None)
                normalized.pop(numeric_key, None)
            else:
                normalized[numeric_key] = number
    if "label" not in normalized or normalized.get("label") is None:
        normalized["label"] = str(normalized.get("x") or "")
    else:
        normalized["label"] = str(normalized.get("label"))
    if "value" not in normalized:
        normalized["value"] = _chart_number(normalized.get("y")) or 0.0
    return normalized


def _max_timestamp(*values: Any) -> Any:
    latest: pd.Timestamp | None = None
    for value in values:
        candidate = pd.to_datetime(value, errors="coerce") if value is not None else pd.NaT
        if pd.isna(candidate):
            continue
        if latest is None or candidate > latest:
            latest = candidate
    return latest


def _sanitize_raw_json(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None

    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return None

    return json.dumps(_sanitize_mcp_value(parsed))


def _first_non_empty(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        return value if value.strip() else None
    return value


def _first_row_value(row: Any) -> Any:
    if isinstance(row, (tuple, list)):
        return row[0] if row else None
    mapping = getattr(row, "_mapping", None)
    if mapping is not None:
        try:
            return next(iter(mapping.values()))
        except StopIteration:
            return None
    return row


def _metadata_value_for_field(row: dict[str, Any], raw_rows: dict[str, Any], field: str) -> Any:
    aliases = _FIELD_ALIASES.get(field, (field,))
    for alias in aliases:
        if alias in row:
            value = _first_non_empty(row.get(alias))
            if value is not None:
                return value
    for alias in aliases:
        if alias in raw_rows:
            value = _first_non_empty(raw_rows.get(alias))
            if value is not None:
                return value
    return None


def _sanitize_source_errors(errors_by_source: dict[str, list[str]]) -> dict[str, list[str]]:
    def _sanitize(err: Any) -> str:
        if err is None:
            return ""
        if not isinstance(err, str):
            return _sanitize_mcp_value(str(err))
        sanitized = _sanitize_mcp_value(err)
        return str(sanitized)

    return {
        source: [
            _sanitize(err)
            for err in errors
        ]
        for source, errors in errors_by_source.items()
        if errors
    }


def _limit(value: Any, default: int = 100) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(0, min(parsed, MAX_QUERY_LIMIT))


def _mcp_limit(value: Any, default: int = MCP_DEFAULT_PAGE_LIMIT) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(0, min(parsed, MCP_MAX_PAGE_LIMIT))


def _mcp_offset(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = 0
    return max(parsed, 0)


def _sanitize_mcp_record(record: dict[str, Any], *, include_raw_json: bool = False) -> dict[str, Any]:
    expanded: dict[str, Any] = dict(record)
    raw_rows: dict[str, Any] | None = None
    raw_rows_sanitized: dict[str, Any] | None = None

    raw_value = expanded.get("raw_data_json")
    if isinstance(raw_value, str) and raw_value.strip():
        sanitized_raw_json = _sanitize_raw_json(raw_value)
        if sanitized_raw_json is not None and include_raw_json:
            expanded["raw_data_json"] = sanitized_raw_json
        try:
            parsed = json.loads(raw_value)
        except (TypeError, json.JSONDecodeError):
            parsed = None
        if isinstance(parsed, dict):
            raw_rows = parsed
            sanitized_raw_rows = _sanitize_mcp_value(parsed)
            raw_rows_sanitized = sanitized_raw_rows if isinstance(sanitized_raw_rows, dict) else None
            for key, value in parsed.items():
                expanded.setdefault(str(key), value)

    for field in ("evidence_json", "payload_json"):
        raw_value = expanded.get(field)
        if isinstance(raw_value, str) and raw_value.strip():
            sanitized_raw_json = _sanitize_raw_json(raw_value)
            if sanitized_raw_json is not None and include_raw_json:
                expanded[field] = sanitized_raw_json
            try:
                parsed = json.loads(raw_value)
            except (TypeError, json.JSONDecodeError):
                parsed = None
            if isinstance(parsed, dict):
                for key, value in parsed.items():
                    expanded.setdefault(str(key), value)

    headers_json = expanded.get("original_headers_json")
    if isinstance(headers_json, str) and headers_json.strip():
        try:
            headers = json.loads(headers_json)
        except (TypeError, json.JSONDecodeError):
            headers = None
        if isinstance(headers, dict) and raw_rows:
            for original_field, normalized_key in headers.items():
                key_text = str(original_field)
                source_key = str(normalized_key)
                if source_key in raw_rows:
                    expanded[key_text] = raw_rows[source_key]

    if "raw_data_json" in expanded and not include_raw_json:
        expanded.pop("raw_data_json", None)
    if "original_headers_json" in expanded and not include_raw_json:
        expanded.pop("original_headers_json", None)

    if "evidence_json" in expanded and not include_raw_json:
        expanded.pop("evidence_json", None)
    if "payload_json" in expanded and not include_raw_json:
        expanded.pop("payload_json", None)

    sanitized: dict[str, Any] = {}
    for key, value in expanded.items():
        key_text = str(key)
        if _is_path_like_field(key_text):
            continue
        if key_text in _RAW_JSON_FIELDS and isinstance(value, str) and include_raw_json:
            sanitized[key_text] = _sanitize_raw_json(value) or _sanitize_mcp_value(value)
            continue
        sanitized[key_text] = _sanitize_mcp_value(value)

    if include_raw_json and raw_rows_sanitized and isinstance(raw_rows_sanitized, dict):
        # keep normalized raw data sanitized if callers consume it via flattened keys too
        for key_text in list(sanitized.keys()):
            if key_text in raw_rows_sanitized:
                sanitized[key_text] = raw_rows_sanitized[key_text]
    return sanitized


def _sanitize_mcp_records(records: list[dict[str, Any]], *, include_raw_json: bool = False) -> list[dict[str, Any]]:
    return [
        _sanitize_mcp_record(record, include_raw_json=include_raw_json)
        for record in records
    ]


def _page_records(
    rows: list[dict[str, Any]],
    *,
    limit: int,
    offset: int,
    total: int | None = None,
) -> dict[str, Any]:
    if limit <= 0:
        page = []
    else:
        page = rows[offset:offset + limit]
    payload: dict[str, Any] = {
        "rows": page,
        "returned": len(page),
        "limit": limit,
        "offset": offset,
        "has_more": limit > 0 and (offset + len(page)) < (total if total is not None else len(rows)),
    }
    if total is not None:
        payload["total"] = total
    return payload


def _paged_payload_from_page(
    rows: list[dict[str, Any]],
    *,
    total: int,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    returned = len(rows)
    return {
        "rows": rows,
        "returned": returned,
        "limit": limit,
        "offset": offset,
        "has_more": limit > 0 and offset + returned < total,
        "total": total,
    }


def _date_value(value: Any) -> date | None:
    if value in (None, ""):
        return None
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return None
    return pd.Timestamp(ts).date()


def _datetime_value(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return None
    return pd.Timestamp(ts).to_pydatetime()


def _safe_export_path(base_dir: Path, name: str, suffix: str) -> Path:
    base_dir.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name or "export")).strip("._")
    if not stem:
        stem = "export"
    suffix = suffix if suffix.startswith(".") else f".{suffix}"
    stem = stem[:80]
    path = base_dir / f"{stem}{suffix}"
    index = 1
    while path.exists():
        path = base_dir / f"{stem}_{index}{suffix}"
        index += 1
    return path


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_allowlisted_source_file(upload: dict[str, Any]) -> tuple[Path | None, str | None]:
    path_value = str(upload.get("path") or "").strip()
    expected_suffix = str(upload.get("suffix") or "").lower()
    expected_sha = str(upload.get("sha256") or "").strip().lower()
    expected_size = upload.get("size")
    if not path_value or not expected_suffix or expected_size in (None, "") or not expected_sha:
        return None, "uploaded file integrity metadata is missing"
    try:
        expected_size_int = int(expected_size)
    except (TypeError, ValueError):
        return None, "uploaded file integrity metadata is missing"

    path = Path(path_value).expanduser()
    if not path.is_file():
        return None, "uploaded file is no longer available"
    suffix = path.suffix.lower()
    if suffix not in ALLOWED_UPLOAD_SUFFIXES:
        return None, "uploaded file type is not allowed"
    size = path.stat().st_size
    if size > MAX_UPLOAD_BYTES:
        return None, "uploaded file is too large"
    if size != expected_size_int:
        return None, "uploaded file changed after upload"

    if expected_suffix != suffix:
        return None, "uploaded file changed after upload"
    if _file_sha256(path) != expected_sha:
        return None, "uploaded file changed after upload"
    return path, None


def _validate_uploaded_file_record(upload: UploadedFile | Any) -> tuple[Path | None, str | None]:
    if upload is None:
        return None, "uploaded file is not available"

    original_path = str(getattr(upload, "original_path", "") or "").strip()
    if not original_path:
        return None, "uploaded file is not available"

    path = Path(original_path).expanduser()
    if not path.is_file():
        return None, "uploaded file is no longer available"

    suffix = path.suffix.lower()
    if suffix not in ALLOWED_UPLOAD_SUFFIXES:
        return None, "uploaded file type is not allowed"

    expected_size = getattr(upload, "file_size", None)
    expected_sha = str(getattr(upload, "file_sha256", "") or "").strip().lower()
    if expected_size in (None, "") or not expected_sha:
        return None, "uploaded file integrity metadata is missing"
    try:
        expected_size_int = int(expected_size)
    except (TypeError, ValueError):
        return None, "uploaded file integrity metadata is missing"
    if re.fullmatch(r"[0-9a-f]{64}", expected_sha) is None:
        return None, "uploaded file integrity metadata is missing"

    size = path.stat().st_size
    if size > MAX_UPLOAD_BYTES:
        return None, "uploaded file is too large"
    if size != expected_size_int:
        return None, "uploaded file changed after upload"

    if _file_sha256(path) != expected_sha:
        return None, "uploaded file changed after upload"

    return path, None


def _build_uploaded_file_session_query(session, source_file_id: str) -> UploadedFile | None:
    try:
        file_id = int(source_file_id)
    except (TypeError, ValueError):
        file_id = None

    query = session.query(UploadedFile)
    if file_id is not None:
        record = query.filter(UploadedFile.id == file_id).first()
        if record is not None:
            return record

    return query.filter(UploadedFile.file_sha256 == source_file_id.lower()).first()
    return query.filter(UploadedFile.file_sha256 == source_file_id.lower()).first()


def _df_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    safe = df.copy()
    for col in safe.columns:
        if pd.api.types.is_datetime64_any_dtype(safe[col]):
            safe[col] = safe[col].apply(lambda v: None if pd.isna(v) else pd.Timestamp(v).isoformat())
    return [_jsonable(row) for row in safe.to_dict(orient="records")]


class LocalDataService:
    """Read-only app-data facade with controlled export actions."""

    def __init__(self, *, export_dir: Path | None = None, upload_allowlist: dict[str, Any] | None = None):
        self.export_dir = Path(export_dir) if export_dir else EXPORT_DIR
        self.upload_allowlist: dict[str, dict[str, Any]] = {}
        for upload_id, upload in (upload_allowlist or {}).items():
            clean_id = str(upload_id or "").strip()
            if not clean_id:
                continue
            if isinstance(upload, dict):
                path = str(upload.get("path") or "").strip()
                name = str(upload.get("name") or "").strip()
                clean_upload: dict[str, Any] = {"path": path, "name": name}
                if "size" in upload:
                    clean_upload["size"] = upload.get("size")
                if "suffix" in upload:
                    clean_upload["suffix"] = str(upload.get("suffix") or "").lower()
                if "sha256" in upload:
                    clean_upload["sha256"] = str(upload.get("sha256") or "").lower()
            else:
                path = str(upload or "").strip()
                name = ""
                clean_upload = {"path": path, "name": name}
            if path:
                self.upload_allowlist[clean_id] = clean_upload

    def list_data_sources(self) -> dict[str, Any]:
        sqlite_tables: list[dict[str, Any]] = []
        sqlite_error = None
        try:
            engine = db_engine.create_engine()
            with engine.connect() as conn:
                inspector = sa_inspect(conn)
                for table in inspector.get_table_names():
                    try:
                        count = conn.exec_driver_sql(f'SELECT COUNT(*) FROM "{table}"').scalar()
                    except Exception:
                        count = None
                    sqlite_tables.append({"name": table, "rows": count})
        except Exception as exc:
            sqlite_error = str(exc)

        alarm_paths = [state.ALARM_DB_FILE, state.ALARM_DB_FALLBACK_FILE]
        duckdb_sources = []
        for path in alarm_paths:
            exists = Path(path).exists()
            row_count = 0
            duckdb_error = None
            if exists:
                previous = alarm_store.ALARM_DB_FILE
                try:
                    alarm_store.set_alarm_db_file(path)
                    row_count = alarm_store.count_alarms(alarm_store.AlarmQuery())
                except Exception as exc:
                    row_count = None
                    duckdb_error = str(exc)
                finally:
                    alarm_store.set_alarm_db_file(previous)
            duckdb_sources.append({
                "path": str(path),
                "exists": exists,
                "rows": row_count,
                "error": duckdb_error,
                "modified": datetime.fromtimestamp(Path(path).stat().st_mtime).isoformat() if exists else None,
            })

        return {
            "sqlite": {
                "path": str(db_engine.DB_PATH),
                "exists": Path(db_engine.DB_PATH).exists(),
                "tables": sqlite_tables,
                "error": sqlite_error,
            },
            "duckdb": duckdb_sources,
            "blob_storage": {
                "path": str(blob_repo.BLOB_DIR),
                "exists": Path(blob_repo.BLOB_DIR).exists(),
            },
            "exports": str(self.export_dir),
        }

    def get_current_time(self) -> dict[str, Any]:
        local_now = datetime.now().astimezone()
        utc_now = datetime.now(timezone.utc)
        return {
            "local_time": local_now.isoformat(timespec="seconds"),
            "utc_time": utc_now.isoformat(timespec="seconds"),
            "timezone": local_now.tzname() or "local",
        }

    def describe_federated_site_data(self, **kwargs) -> dict[str, Any]:
        return federated_site.describe_federated_site_data()

    def describe_admin_sql_views(self, **kwargs) -> dict[str, Any]:
        return federated_site.describe_admin_sql_views()

    def _admin_sql_view_frames(self) -> dict[str, pd.DataFrame]:
        page_size = federated_site.ROW_CAP
        safety_cap = federated_site.FEDERATED_MAX_SOURCE_ROWS
        self._admin_sql_source_warnings: list[str] = []

        def _add_warning(message: str) -> None:
            clean = str(message).strip()
            if clean and clean not in self._admin_sql_source_warnings:
                self._admin_sql_source_warnings.append(clean)

        bdt_payload_cache: dict[int, Any] = {}

        def _fetch_bdt_payload(offset: int) -> dict[str, Any]:
            if offset not in bdt_payload_cache:
                bdt_payload_cache[offset] = self.query_bdt_full(limit=page_size, offset=offset)
            cached = bdt_payload_cache[offset]
            return cached if isinstance(cached, dict) else {}

        def _collect_paged_rows(
            fetch_page: Any,
            *,
            field_name: str,
            source_name: str,
        ) -> list[dict[str, Any]]:
            rows: list[dict[str, Any]] = []
            offset = 0
            scanned = 0

            while True:
                page_payload = fetch_page(limit=page_size, offset=offset)
                page_rows = page_payload.get(field_name, []) if isinstance(page_payload, dict) else []
                if not isinstance(page_rows, list):
                    break

                for row in page_rows:
                    if scanned >= safety_cap:
                        break
                    if isinstance(row, dict):
                        rows.append(row)
                    scanned += 1

                if scanned >= safety_cap:
                    _add_warning(f"{source_name} source reached admin SQL safety cap")
                    break

                has_more = bool(page_payload.get("has_more")) if isinstance(page_payload, dict) else False
                if not has_more:
                    break

                if not page_rows:
                    break

                offset += len(page_rows)

            return rows

        def _collect_bdt_rows(fetch_page: Any, *, field_name: str) -> list[dict[str, Any]]:
            rows: list[dict[str, Any]] = []
            offset = 0
            scanned = 0

            while True:
                payload = fetch_page(offset)
                if not isinstance(payload, dict):
                    break

                section_payload = payload.get(field_name, {})
                section_rows = section_payload.get("rows", []) if isinstance(section_payload, dict) else []

                if not isinstance(section_rows, list):
                    break

                for row in section_rows:
                    if scanned >= safety_cap:
                        break
                    if isinstance(row, dict):
                        rows.append(row)
                    scanned += 1

                if scanned >= safety_cap:
                    _add_warning(f"{field_name} source reached admin SQL safety cap")
                    break

                section_has_more = bool(section_payload.get("has_more")) if isinstance(section_payload, dict) else False
                if not section_rows:
                    if section_has_more:
                        if offset >= safety_cap:
                            _add_warning(f"{field_name} source reached admin SQL safety cap")
                            break
                        offset += page_size
                        continue
                    break

                if not section_has_more:
                    break

                offset += len(section_rows)

            return rows

        def _first_present(row: dict[str, Any], *keys: str) -> Any:
            for key in keys:
                if key in row and row.get(key) is not None:
                    return row.get(key)
            return None

        def _project_view_rows(
            view_name: str,
            rows: list[dict[str, Any]],
            aliases: dict[str, tuple[str, ...]] | None = None,
        ) -> pd.DataFrame:
            aliases = aliases or {}
            declared_columns = list(federated_site.ADMIN_SQL_VIEWS[view_name])
            projected: list[dict[str, Any]] = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                projected.append({
                    column: _first_present(row, column, *aliases.get(column, ()))
                    for column in declared_columns
                })
            return pd.DataFrame(projected, columns=declared_columns)

        site_index = _collect_paged_rows(self.list_sites, field_name="rows", source_name="site_index_view")
        network = _collect_paged_rows(self.query_network_summary, field_name="rows", source_name="site_metadata_view")
        alarms = _collect_paged_rows(self.query_alarm_events, field_name="rows", source_name="alarm_events_view")

        bdt_summary = _collect_bdt_rows(_fetch_bdt_payload, field_name="bdt_summary")
        bdt_runs = _collect_bdt_rows(_fetch_bdt_payload, field_name="validation_runs")
        bdt_rules = _collect_bdt_rows(_fetch_bdt_payload, field_name="rule_results")
        photos = _collect_bdt_rows(_fetch_bdt_payload, field_name="photos")
        reviews = _collect_bdt_rows(_fetch_bdt_payload, field_name="review_events")
        return {
            "site_index_view": _project_view_rows("site_index_view", site_index),
            "site_metadata_view": _project_view_rows(
                "site_metadata_view",
                network,
                aliases={
                    "site_code": ("code", "Code", "site_id"),
                    "area": ("orange_area", "Orange Area", "area_code", "Area Code"),
                    "contractor": ("contractor", "Contractor"),
                    "battery_status": ("battery_status", "Battery Status", "battery_type", "Battery Type"),
                },
            ),
            "alarm_events_view": _project_view_rows(
                "alarm_events_view",
                alarms,
                aliases={
                    "duration_secs": ("_duration_secs",),
                    "category": ("category", "alarm_category"),
                    "severity": ("severity",),
                    "site_down": ("site_down", "site_down_flag"),
                },
            ),
            "alarm_summary_view": _project_view_rows("alarm_summary_view", [
                {
                    "site_id": row.get("site_id"),
                    "alarm_count": row.get("alarm_count"),
                    "latest_alarm_at": row.get("latest_alarm_at"),
                }
                for row in site_index
                if isinstance(row, dict)
            ]),
            "bdt_summary_view": _project_view_rows("bdt_summary_view", bdt_summary),
            "bdt_validation_runs_view": _project_view_rows(
                "bdt_validation_runs_view",
                bdt_runs,
                aliases={"site_id": ("site_code",)},
            ),
            "bdt_rule_results_view": _project_view_rows(
                "bdt_rule_results_view",
                bdt_rules,
                aliases={"site_id": ("site_code",)},
            ),
            "photo_metadata_view": _project_view_rows(
                "photo_metadata_view",
                photos,
                aliases={"site_id": ("site_code",)},
            ),
            "review_events_view": _project_view_rows(
                "review_events_view",
                reviews,
                aliases={"site_id": ("site_code",)},
            ),
        }

    def query_admin_readonly_sql(self, **kwargs) -> dict[str, Any]:
        sql = str(kwargs.get("sql") or "")
        limit = _mcp_limit(kwargs.get("limit"))
        offset = _mcp_offset(kwargs.get("offset"))
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

exec
/bin/zsh -lc "grep -n \"def list_chart_types\\|def get_chart_data\\|def render_chart_widget\\|def generate_graph\\|_chart\" -n llm_tools/service.py" in /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
 succeeded in 0ms:
238:def _chart_number(value: Any) -> float | None:
250:def _normalize_chart_point(point: Any) -> dict[str, Any]:
258:            number = _chart_number(normalized.get(numeric_key))
268:        normalized["value"] = _chart_number(normalized.get("y")) or 0.0
1185:    def _chart_page_payload(
1480:    def list_chart_types(self, **kwargs) -> dict[str, Any]:
1488:    def _chart_alarm_df(self, *, site_code: str, kwargs: dict[str, Any]) -> pd.DataFrame:
1555:        grouped = work.assign(_chart_value=numeric).dropna(subset=["_chart_value"]).groupby(group_col, dropna=False)["_chart_value"].median().sort_values(ascending=False)
1580:    def _alarm_chart_series(self, alarm_df: pd.DataFrame, graph_type: str) -> tuple[list[str], list[float], list[dict[str, Any]]]:
1680:    def _backup_chart_series(self, graph_type: str, kwargs: dict[str, Any]) -> tuple[list[str], list[float], list[dict[str, Any]]]:
1715:    def _bdt_chart_series(self, graph_type: str, kwargs: dict[str, Any]) -> tuple[list[str], list[float], list[dict[str, Any]]]:
1748:    def _chart_series_for_spec(self, graph_type: str, kwargs: dict[str, Any]) -> tuple[list[str], list[float], list[dict[str, Any]]]:
1754:            alarm_df = self._chart_alarm_df(site_code=site_code, kwargs=kwargs)
1759:            return self._alarm_chart_series(alarm_df, graph_type)
1761:            return self._backup_chart_series(graph_type, kwargs)
1763:            return self._bdt_chart_series(graph_type, kwargs)
1770:    def _chart_axis_labels(chart_kind: str) -> tuple[str, str]:
1775:    def get_chart_data(self, **kwargs) -> dict[str, Any]:
1803:        labels, values, series = self._chart_series_for_spec(chart_id, series_kwargs)
1805:            series = [{"label": str(label), "value": _chart_number(value) or 0.0} for label, value in zip(labels, values, strict=False)]
1806:        series = [_normalize_chart_point(point) for point in series]
1813:        values = [_chart_number(point.get("value")) or 0.0 for point in returned_series]
1814:        x_label, y_label = self._chart_axis_labels(spec.chart_kind)
1844:    def render_chart_widget(self, **kwargs) -> dict[str, Any]:
1853:        series = [_normalize_chart_point(point) for point in series]
1856:                {"label": str(label), "value": _chart_number(values[index] if index < len(values) else None) or 0.0}
1860:        values = [_chart_number(point.get("value")) or 0.0 for point in series]
1884:    def generate_graph(self, **kwargs) -> dict[str, Any]:
1894:        labels, values, series = self._chart_series_for_spec(graph_type, series_kwargs)
1899:        self._draw_chart(path, title, labels, values, chart_kind=spec.chart_kind, series=series)
2008:                labels, values, series = self._chart_series_for_spec(report_type, {
2023:            payload = self._chart_page_payload(series, total=len(series), limit=limit, offset=offset)
2518:    def _chart_font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
2537:    def _wrap_chart_text(cls, draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
2559:    def _format_chart_label(label: str) -> str:
2568:    def _draw_bar_chart(cls, path: Path, title: str, labels: list[str], values: list[float]) -> None:
2576:        font = cls._chart_font(14)
2577:        title_font = cls._chart_font(24, bold=True)
2578:        value_font = cls._chart_font(13, bold=True)
2579:        title_lines = cls._wrap_chart_text(draw, title, title_font, width - margin_left - margin_right)
2606:        usable_chart_h = chart_h - label_band_h - 18
2609:            bar_h = int((float(value) / max_value) * max(usable_chart_h, 24))
2622:            wrapped_label = cls._wrap_chart_text(draw, cls._format_chart_label(label), font, max(bar_w + 10, 90))
2637:    def _draw_chart(
2650:                cls._draw_pie_chart(path, title, labels, values, donut=kind == "donut")
2653:                cls._draw_horizontal_bar_chart(path, title, labels, values)
2656:                cls._draw_line_chart(path, title, labels, values)
2659:                cls._draw_heatmap_chart(path, title, labels, values)
2662:                cls._draw_bar_chart(path, title, labels, values)
2664:            cls._draw_bar_chart(path, title, labels, values)
2667:            cls._draw_pie_chart(path, title, labels, values, donut=kind == "donut")
2670:            cls._draw_horizontal_bar_chart(path, title, labels, values)
2673:            cls._draw_line_chart(path, title, labels, values)
2676:            cls._draw_scatter_chart(path, title, series or [])
2679:            cls._draw_heatmap_chart(path, title, labels, values)
2682:            cls._draw_gauge_chart(path, title, values)
2684:        cls._draw_bar_chart(path, title, labels, values)
2687:    def _chart_canvas(cls, path: Path, title: str, *, width: int = 1200, height: int = 760):
2691:        title_font = cls._chart_font(24, bold=True)
2692:        title_lines = cls._wrap_chart_text(draw, title, title_font, width - 140)
2699:    def _draw_horizontal_bar_chart(cls, path: Path, title: str, labels: list[str], values: list[float]) -> None:
2700:        image, draw = cls._chart_canvas(path, title)
2701:        font = cls._chart_font(14)
2702:        value_font = cls._chart_font(13, bold=True)
2715:            draw.text((32, y + 3), cls._format_chart_label(label)[:26], fill="#b9c1dc", font=font)
2721:    def _draw_pie_chart(cls, path: Path, title: str, labels: list[str], values: list[float], *, donut: bool = False) -> None:
2722:        image, draw = cls._chart_canvas(path, title)
2723:        font = cls._chart_font(14)
2724:        value_font = cls._chart_font(13, bold=True)
2741:            draw.text((315, 385), f"{pct:.0f}%", fill="#d8def8", font=cls._chart_font(28, bold=True))
2746:            draw.text((lx + 32, y), f"{cls._format_chart_label(label)}  {value:g} ({value / total:.0%})", fill="#d8def8", font=value_font)
2750:    def _draw_line_chart(cls, path: Path, title: str, labels: list[str], values: list[float]) -> None:
2751:        image, draw = cls._chart_canvas(path, title)
2752:        font = cls._chart_font(14)
2777:            draw.text((x - 24, top + height + 12), cls._format_chart_label(labels[idx])[:8], fill="#b9c1dc", font=font)
2781:    def _draw_scatter_chart(cls, path: Path, title: str, series: list[dict[str, Any]]) -> None:
2782:        image, draw = cls._chart_canvas(path, title)
2783:        font = cls._chart_font(14)
2812:    def _draw_heatmap_chart(cls, path: Path, title: str, labels: list[str], values: list[float]) -> None:
2813:        image, draw = cls._chart_canvas(path, title)
2814:        font = cls._chart_font(12)
2833:            draw.text((x + 6, y + cell + 4), cls._format_chart_label(label)[:8], fill="#b9c1dc", font=font)
2837:    def _draw_gauge_chart(cls, path: Path, title: str, values: list[float]) -> None:
2838:        image, draw = cls._chart_canvas(path, title)
2839:        font = cls._chart_font(18, bold=True)
2845:        draw.text((535, 430), f"{pct * 100:.0f}%", fill="#d8def8", font=cls._chart_font(42, bold=True))

exec
/bin/zsh -lc "sed -n '1160,1915p' llm_tools/service.py" in /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
 succeeded in 0ms:
            page = payload.get("rows") if isinstance(payload, dict) else []
            if not isinstance(page, list):
                break

            row_count = 0
            for row in page:
                if isinstance(row, dict):
                    all_rows.append(row)
                    row_count += 1

            if total is None:
                total = int(payload.get("total") or 0)

            if row_count < page_limit:
                break
            if total is not None and total <= len(all_rows):
                break

            offset += page_limit
            if offset > (total or (offset + row_count)):
                break

        return all_rows

    @staticmethod
    def _chart_page_payload(
        series: list[dict[str, Any]],
        *,
        total: int,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        page = series[offset:offset + limit] if limit > 0 else []
        return {
            "points": total,
            "labels": [point.get("label") for point in page],
            "values": [point.get("value") for point in page],
            "series": page,
            "returned": len(page),
            "limit": limit,
            "offset": offset,
            "has_more": limit > 0 and (offset + len(page)) < total,
            "total": total,
        }

    @staticmethod
    def _bdt_graph_series(rows: list[dict[str, Any]], graph_type: str) -> tuple[list[str], list[float]]:
        if graph_type == "bdt_verdict_counts":
            verdict_values = [row.get("overall_verdict") for row in rows if isinstance(row, dict)]
            counts = pd.Series(verdict_values).fillna("Unknown").value_counts()
            return counts.index.astype(str).tolist(), counts.astype(float).tolist()

        if graph_type == "bdt_duration_trend":
            trend_rows = [row for row in rows if isinstance(row, dict)]
            sorted_rows = sorted(trend_rows, key=lambda row: str(row.get("test_date") or ""))
            labels: list[str] = []
            values: list[float] = []
            for row in sorted_rows:
                value = row.get("discharge_minutes")
                if value is None:
                    continue
                labels.append(str(row.get("test_date") or "")[:10])
                values.append(float(value))
            return labels, values

        return [], []

    def alarm_stats(self, **kwargs) -> dict[str, Any]:
        site_raw = str(kwargs.get("site_code") or kwargs.get("site_id") or "").strip()
        site_text = str(kwargs.get("site_text") or "").strip()
        site_scope_keys: list[str] | None = None
        if site_raw and not site_text:
            normalized = catalog_store._normalize_site_id(site_raw)
            normalized_candidates = {site_raw, site_raw.upper()}
            if normalized:
                normalized_candidates.add(normalized)
                normalized_candidates.add(str(normalized).replace("-", ""))
            site_scope_keys = [value for value in normalized_candidates if value]

        q = alarm_store.AlarmQuery(
            site_text=site_text,
            site_scope_keys=site_scope_keys,
            category=str(kwargs.get("category") or "All"),
            vendor=str(kwargs.get("vendor") or "All"),
            network_type=str(kwargs.get("network_type") or "All"),
            date_from=_date_value(kwargs.get("date_from")),
            date_to=_date_value(kwargs.get("date_to")),
        )
        return self._with_alarm_source(lambda: alarm_store.stats(q)) or alarm_store.stats(q)

    def query_bdt_results(self, **kwargs) -> dict[str, Any]:
        limit = _limit(kwargs.get("limit"), default=100)
        offset = max(int(kwargs.get("offset") or 0), 0)
        site_code = str(kwargs.get("site_code") or "").strip().upper()
        overall = str(kwargs.get("overall") or "").strip()
        rule_id = str(kwargs.get("rule_id") or "").strip().upper()
        rule_verdict = str(kwargs.get("rule_verdict") or "").strip()
        date_from = _date_value(kwargs.get("date_from"))
        date_to = _date_value(kwargs.get("date_to"))

        session = db_engine.get_session()
        try:
            query = (
                session.query(PMValidationRun, BDTTest)
                .join(BDTTest, PMValidationRun.bdt_test_id == BDTTest.id)
                .order_by(PMValidationRun.run_at.desc())
            )
            if site_code:
                query = query.filter(BDTTest.site_code == site_code)
            if overall:
                query = query.filter(PMValidationRun.overall_verdict == overall)
            if date_from:
                query = query.filter(BDTTest.test_date >= date_from)
            if date_to:
                query = query.filter(BDTTest.test_date <= date_to)
            if rule_id or rule_verdict:
                query = query.join(PMRuleResult, PMRuleResult.validation_run_id == PMValidationRun.id)
                if rule_id:
                    query = query.join(PMRuleCatalog, PMRuleResult.rule_id == PMRuleCatalog.id)
                    query = query.filter(PMRuleCatalog.rule_code == rule_id)
                if rule_verdict:
                    query = query.filter(PMRuleResult.verdict == rule_verdict)

            total = query.count()
            rows = []
            for run, bdt in query.offset(offset).limit(limit).all():
                rows.append({
                    "validation_run_id": run.id,
                    "bdt_test_id": bdt.id,
                    "site_code": bdt.site_code,
                    "test_date": bdt.test_date,
                    "filename": self._filename_for_bdt(session, bdt),
                    "overall_verdict": run.overall_verdict,
                    "run_at": run.run_at,
                    "discharge_minutes": bdt.discharge_minutes,
                    "battery_brand": bdt.battery_brand,
                    "num_strings": bdt.num_strings,
                    "end_voltage": bdt.end_voltage,
                })
            return {"total": total, "rows": _jsonable(rows)}
        finally:
            session.close()

    def get_bdt_detail(self, **kwargs) -> dict[str, Any]:
        run_id = kwargs.get("validation_run_id")
        site_code = str(kwargs.get("site_code") or "").strip().upper()
        test_date = _date_value(kwargs.get("test_date"))
        session = db_engine.get_session()
        try:
            query = session.query(PMValidationRun, BDTTest).join(
                BDTTest,
                PMValidationRun.bdt_test_id == BDTTest.id,
            )
            if run_id:
                query = query.filter(PMValidationRun.id == int(run_id))
            elif site_code:
                query = query.filter(BDTTest.site_code == site_code)
                if test_date:
                    query = query.filter(BDTTest.test_date == test_date)
            else:
                return {"error": "validation_run_id or site_code is required"}
            run, bdt = query.order_by(PMValidationRun.run_at.desc()).first() or (None, None)
            if not run or not bdt:
                return {"error": "BDT validation result not found"}

            rules = []
            for rr, catalog in (
                session.query(PMRuleResult, PMRuleCatalog)
                .join(PMRuleCatalog, PMRuleResult.rule_id == PMRuleCatalog.id)
                .filter(PMRuleResult.validation_run_id == run.id)
                .order_by(PMRuleCatalog.rule_code.asc())
                .all()
            ):
                detail = rr.evidence_json
                try:
                    detail = json.loads(detail) if detail else ""
                except (TypeError, json.JSONDecodeError):
                    pass
                rules.append({
                    "rule_code": catalog.rule_code,
                    "rule_name": catalog.name,
                    "verdict": rr.verdict,
                    "detail": detail,
                })

            return _jsonable({
                "validation_run_id": run.id,
                "overall_verdict": run.overall_verdict,
                "run_at": run.run_at,
                "bdt": {
                    "id": bdt.id,
                    "filename": self._filename_for_bdt(session, bdt),
                    "site_code": bdt.site_code,
                    "site_name": bdt.site_name,
                    "test_date": bdt.test_date,
                    "time_in": bdt.time_in,
                    "time_out": bdt.time_out,
                    "battery_brand": bdt.battery_brand,
                    "battery_ah": bdt.battery_ah,
                    "battery_voltage": bdt.battery_voltage,
                    "num_strings": bdt.num_strings,
                    "num_batteries": bdt.num_batteries,
                    "num_modules": bdt.num_modules,
                    "start_voltage": bdt.start_voltage,
                    "end_voltage": bdt.end_voltage,
                    "discharge_minutes": bdt.discharge_minutes,
                    "discharge_readings": json.loads(bdt.discharge_readings_json or "[]"),
                    "string_discharge_readings": json.loads(bdt.string_discharge_readings_json or "[]"),
                },
                "rules": rules,
                "photos": self._photo_rows_for_bdt(session, bdt.id),
            })
        finally:
            session.close()

    def get_photo_metadata(self, **kwargs) -> dict[str, Any]:
        site_code = str(kwargs.get("site_code") or "").strip().upper()
        bdt_test_id = kwargs.get("bdt_test_id")
        limit = _limit(kwargs.get("limit"), default=100)
        session = db_engine.get_session()
        try:
            query = (
                session.query(BDTPhoto, BDTTest, BlobAsset)
                .join(BDTTest, BDTPhoto.bdt_test_id == BDTTest.id)
                .outerjoin(BlobAsset, BDTPhoto.blob_asset_id == BlobAsset.id)
            )
            if bdt_test_id:
                query = query.filter(BDTPhoto.bdt_test_id == int(bdt_test_id))
            if site_code:
                query = query.filter(BDTTest.site_code == site_code)
            rows = []
            for photo, bdt, blob in query.order_by(BDTTest.test_date.desc(), BDTPhoto.slot_index.asc()).limit(limit).all():
                rows.append(self._photo_row(photo, bdt, blob))
            return {"rows": _jsonable(rows), "row_count": len(rows)}
        finally:
            session.close()

    def read_photo_blob(self, **kwargs) -> dict[str, Any]:
        sha256 = str(kwargs.get("sha256") or "").strip().lower()
        if not sha256:
            return {"error": "sha256 is required"}
        session = db_engine.get_session()
        try:
            blob = session.query(BlobAsset).filter(BlobAsset.sha256 == sha256).first()
            if not blob:
                return {"error": "blob not found"}
            local_path = str(blob.local_path or "").strip()
            if not local_path:
                return {"error": "blob not found"}
            path = Path(local_path).expanduser().resolve(strict=False)
            blob_dir = Path(blob_repo.BLOB_DIR).expanduser().resolve(strict=False)
            if not path.is_relative_to(blob_dir):
                return {"error": "blob file is outside blob storage"}
            if not path.is_file():
                return {"error": "blob file missing"}
            mime_type = str(blob.mime_type or "").strip()
            if not mime_type:
                return {"error": "blob mime type is required"}
            if not mime_type.lower().startswith("image/"):
                return {"error": "blob mime type is not an image"}
            if path.stat().st_size > MAX_BLOB_BYTES:
                return {"error": f"blob too large; max {MAX_BLOB_BYTES} bytes"}
            content = path.read_bytes()
            if len(content) > MAX_BLOB_BYTES:
                return {"error": f"blob too large; max {MAX_BLOB_BYTES} bytes"}
            actual_sha = hashlib.sha256(content).hexdigest()
            stored_sha = str(blob.sha256 or "").strip().lower()
            if actual_sha != sha256 or actual_sha != stored_sha:
                return {"error": "blob hash mismatch"}
            try:
                Image.open(BytesIO(content)).verify()
            except Exception:
                return {"error": "blob content is not a valid image"}
            return {
                "sha256": stored_sha,
                "mime_type": mime_type,
                "base64": base64.b64encode(content).decode("ascii"),
            }
        finally:
            session.close()

    def get_site_dossier(self, **kwargs) -> dict[str, Any]:
        site_code = normalize_site_key(kwargs.get("site_code") or kwargs.get("site_text") or "")
        if not site_code:
            return {"error": "site_code is required"}
        alarm_df = self._alarm_rows_for_sites(
            {site_code},
            date_from=_date_value(kwargs.get("date_from")),
            date_to=_date_value(kwargs.get("date_to")),
        )
        bdt_payload = self.query_bdt_results(
            site_code=site_code,
            date_from=kwargs.get("date_from"),
            date_to=kwargs.get("date_to"),
            limit=MAX_QUERY_LIMIT,
        )
        bdt_rows = bdt_payload.get("rows", []) if isinstance(bdt_payload, dict) else []
        bdt_details = []
        for row in bdt_rows[:_limit(kwargs.get("bdt_detail_limit"), default=MAX_QUERY_LIMIT)]:
            if isinstance(row, dict) and row.get("validation_run_id"):
                bdt_details.append(self.get_bdt_detail(validation_run_id=row["validation_run_id"]))

        export_path = self._export_site_dossier_workbook(
            site_code=site_code,
            alarm_df=alarm_df,
            bdt_rows=[row for row in bdt_rows if isinstance(row, dict)],
            bdt_details=[detail for detail in bdt_details if isinstance(detail, dict) and "error" not in detail],
        )

        return {
            "site_code": site_code,
            "alarm_total": len(alarm_df),
            "alarm_stats": self._site_alarm_summary(alarm_df),
            "alarm_rows": _df_records(alarm_df.head(_limit(kwargs.get("alarm_preview_limit"), default=50))),
            "bdt_total": int(bdt_payload.get("total") or len(bdt_rows)) if isinstance(bdt_payload, dict) else len(bdt_rows),
            "bdt_rows": _jsonable(bdt_rows[:_limit(kwargs.get("bdt_preview_limit"), default=50)]),
            "bdt_details": _jsonable(bdt_details),
            "export_path": str(export_path),
        }

    def list_chart_types(self, **kwargs) -> dict[str, Any]:
        charts = chart_specs_payload(
            family=str(kwargs.get("family") or ""),
            chart_kind=str(kwargs.get("chart_kind") or ""),
            renderable_only=bool(kwargs.get("renderable_only", False)),
        )
        return {"charts": charts, "count": len(charts)}

    def _chart_alarm_df(self, *, site_code: str, kwargs: dict[str, Any]) -> pd.DataFrame:
        date_from = _date_value(kwargs.get("date_from"))
        date_to = _date_value(kwargs.get("date_to"))
        if site_code and kwargs.get("_prefer_site_slice"):
            return self._alarm_rows_for_sites({site_code}, date_from=date_from, date_to=date_to)
        q = alarm_store.AlarmQuery(
            site_text=str(kwargs.get("site_text") or "") if not site_code else "",
            site_scope_keys={normalize_site_key(site_code)} if site_code else None,
            category=str(kwargs.get("category") or "All"),
            vendor=str(kwargs.get("vendor") or "All"),
            network_type=str(kwargs.get("network_type") or "All"),
            date_from=date_from,
            date_to=date_to,
            sort_by="occurred_on",
            sort_desc=False,
            limit=None,
            offset=0,
        )
        return self._with_alarm_source(lambda: alarm_store.query_alarms(q))

    @staticmethod
    def _series_from_counts(work: pd.DataFrame, column: str, *, top_n: int | None = None) -> tuple[list[str], list[float]]:
        if column not in work.columns:
            return [], []
        counts = work[column].fillna("Unknown").replace("", "Unknown").value_counts()
        if top_n:
            counts = counts.head(top_n)
        return counts.index.astype(str).tolist(), counts.astype(float).tolist()

    @staticmethod
    def _duration_minutes_by(work: pd.DataFrame, column: str, *, top_n: int | None = None) -> tuple[list[str], list[float]]:
        if column not in work.columns or "_duration_secs" not in work.columns:
            return [], []
        grouped = work.groupby(column, dropna=False)["_duration_secs"].sum().sort_values(ascending=False) / 60.0
        if top_n:
            grouped = grouped.head(top_n)
        return grouped.index.astype(str).tolist(), grouped.astype(float).tolist()

    @staticmethod
    def _daily_counts(work: pd.DataFrame, *, category: str = "") -> tuple[list[str], list[float]]:
        if "occurred_on" not in work.columns:
            return [], []
        source = work
        if category and "alarm_category" in source.columns:
            source = source[source["alarm_category"].astype(str).str.lower() == category.lower()]
        days = pd.to_datetime(source["occurred_on"], errors="coerce", format="mixed").dropna().dt.date
        counts = days.value_counts().sort_index()
        return [str(v) for v in counts.index.tolist()], counts.astype(float).tolist()

    @staticmethod
    def _histogram_series(values: pd.Series, *, bins: int = 8) -> tuple[list[str], list[float]]:
        numeric = pd.to_numeric(values, errors="coerce").dropna()
        if numeric.empty:
            return [], []
        if numeric.nunique() == 1:
            value = float(numeric.iloc[0])
            return [f"{value:g}"], [float(len(numeric))]
        counts, edges = pd.cut(numeric, bins=min(bins, max(1, numeric.nunique())), retbins=True, duplicates="drop")
        grouped = counts.value_counts().sort_index()
        labels = [f"{interval.left:g}-{interval.right:g}" for interval in grouped.index]
        return labels, grouped.astype(float).tolist()

    @staticmethod
    def _box_summary_series(work: pd.DataFrame, group_col: str, value_col: str) -> tuple[list[str], list[float]]:
        if group_col not in work.columns or value_col not in work.columns:
            return [], []
        numeric = pd.to_numeric(work[value_col], errors="coerce")
        grouped = work.assign(_chart_value=numeric).dropna(subset=["_chart_value"]).groupby(group_col, dropna=False)["_chart_value"].median().sort_values(ascending=False)
        return grouped.index.astype(str).tolist(), grouped.astype(float).tolist()

    @staticmethod
    def _scatter_series_from_columns(work: pd.DataFrame, x_col: str, y_col: str, *, label_col: str = "site_id") -> list[dict[str, Any]]:
        if x_col not in work.columns or y_col not in work.columns:
            return []
        rows = []
        for _, row in work.iterrows():
            x_val = pd.to_numeric(pd.Series([row.get(x_col)]), errors="coerce").iloc[0]
            y_val = pd.to_numeric(pd.Series([row.get(y_col)]), errors="coerce").iloc[0]
            if pd.isna(x_val) or pd.isna(y_val):
                continue
            rows.append({
                "label": str(row.get(label_col) or row.get("site_code") or ""),
                "x": float(x_val),
                "y": float(y_val),
                "value": float(y_val),
            })
        return rows

    @staticmethod
    def _labels_values_from_series(series: list[dict[str, Any]]) -> tuple[list[str], list[float]]:
        return [str(point.get("label") or "") for point in series], [float(point.get("value") or 0.0) for point in series]

    def _alarm_chart_series(self, alarm_df: pd.DataFrame, graph_type: str) -> tuple[list[str], list[float], list[dict[str, Any]]]:
        if alarm_df is None or alarm_df.empty:
            return [], [], []
        work = alarm_df.copy()
        category_col = "alarm_category" if "alarm_category" in work.columns else "alarm_name"
        if graph_type in {"alarm_category_counts", "alarm_category_share", "alarm_category_pareto", "alarm_category_treemap"}:
            labels, values = self._series_from_counts(work, category_col)
        elif graph_type == "alarm_daily_counts":
            labels, values = self._daily_counts(work)
        elif graph_type in {"alarm_volume_trend", "site_alarm_trend", "cumulative_alarm_volume"}:
            labels, values = self._daily_counts(work)
            if graph_type == "cumulative_alarm_volume":
                total = 0.0
                cumulative = []
                for value in values:
                    total += value
                    cumulative.append(total)
                values = cumulative
        elif graph_type == "daily_power_alarm_trend":
            labels, values = self._daily_counts(work, category="Power")
        elif graph_type == "daily_down_alarm_trend":
            labels, values = self._daily_counts(work, category="Down")
        elif graph_type in {"alarm_duration_by_category", "duration_boxplot_by_category", "alarm_count_vs_duration_by_category"}:
            labels, values = self._duration_minutes_by(work, category_col)
        elif graph_type in {"vendor_alarm_share", "vendor_alarm_comparison", "duration_boxplot_by_vendor", "vendor_performance_radar"}:
            labels, values = self._series_from_counts(work, "vendor")
        elif graph_type in {"network_type_share", "network_type_vendor_comparison", "network_type_radar"}:
            labels, values = self._series_from_counts(work, "network_type")
        elif graph_type == "alarm_severity_share":
            labels, values = self._series_from_counts(work, "severity")
        elif graph_type in {"cleared_vs_uncleared_share", "alarm_clearance_rate_gauge"}:
            if "cleared_on" not in work.columns:
                labels, values = [], []
            else:
                cleared = pd.to_datetime(work["cleared_on"], errors="coerce", format="mixed").notna()
                labels, values = ["Cleared", "Uncleared"], [float(cleared.sum()), float((~cleared).sum())]
        elif graph_type in {"top_sites_by_alarm_count", "site_alarm_pareto"}:
            labels, values = self._series_from_counts(work, "site_id", top_n=20)
        elif graph_type in {"top_sites_by_duration", "top_sites_by_alarm_duration", "alarm_duration_pareto", "mttr_by_site"}:
            labels, values = self._duration_minutes_by(work, "site_id", top_n=20)
        elif graph_type in {"top_alarm_names"}:
            labels, values = self._series_from_counts(work, "alarm_name", top_n=20)
        elif graph_type in {"top_alarm_ids"}:
            labels, values = self._series_from_counts(work, "alarm_id", top_n=20)
        elif graph_type == "uncleared_alarms_by_site":
            if "cleared_on" in work.columns:
                work = work[pd.to_datetime(work["cleared_on"], errors="coerce", format="mixed").isna()]
            labels, values = self._series_from_counts(work, "site_id", top_n=20)
        elif graph_type in {"alarm_duration_distribution", "duration_histogram", "time_to_clear_distribution"}:
            labels, values = self._histogram_series(work.get("_duration_secs", pd.Series(dtype=float)) / 60.0)
        elif graph_type == "alarm_count_per_site_distribution":
            counts = work["site_id"].value_counts() if "site_id" in work.columns else pd.Series(dtype=float)
            labels, values = self._histogram_series(counts)
        elif graph_type in {"daily_alarms_by_category", "weekly_alarms_by_category", "stacked_alarm_category_area"}:
            labels, values = self._series_from_counts(work, category_col)
        elif graph_type in {"stacked_vendor_area", "vendor_by_category"}:
            labels, values = self._series_from_counts(work, "vendor")
        elif graph_type == "network_type_by_category":
            labels, values = self._series_from_counts(work, "network_type")
        elif graph_type in {"alarm_heatmap_day_hour", "daily_alarm_calendar", "daily_down_alarm_calendar"}:
            if "occurred_on" not in work.columns:
                labels, values = [], []
            else:
                times = pd.to_datetime(work["occurred_on"], errors="coerce", format="mixed").dropna()
                if graph_type == "alarm_heatmap_day_hour":
                    counts = times.to_frame(name="dt").assign(label=lambda df: df["dt"].dt.day_name().str[:3] + " " + df["dt"].dt.hour.astype(str).str.zfill(2)).label.value_counts().sort_index()
                    labels, values = counts.index.astype(str).tolist(), counts.astype(float).tolist()
                else:
                    if graph_type == "daily_down_alarm_calendar" and "alarm_category" in work.columns:
                        times = pd.to_datetime(work.loc[work["alarm_category"].astype(str).str.lower() == "down", "occurred_on"], errors="coerce", format="mixed").dropna()
                    counts = times.dt.date.value_counts().sort_index()
                    labels, values = [str(v) for v in counts.index], counts.astype(float).tolist()
        elif graph_type in {"alarm_heatmap_site_day", "alarm_heatmap_category_hour", "vendor_alarm_heatmap_day", "network_type_alarm_heatmap"}:
            base_col = "site_id" if graph_type == "alarm_heatmap_site_day" else category_col
            if graph_type == "vendor_alarm_heatmap_day":
                base_col = "vendor"
            elif graph_type == "network_type_alarm_heatmap":
                base_col = "network_type"
            labels, values = self._series_from_counts(work, base_col, top_n=24)
        elif graph_type in {"duration_vs_occurrence_time"}:
            if "occurred_on" in work.columns and "_duration_secs" in work.columns:
                hours = pd.to_datetime(work["occurred_on"], errors="coerce", format="mixed").dt.hour
                scatter_df = work.assign(_hour=hours, _minutes=work["_duration_secs"] / 60.0)
                series = self._scatter_series_from_columns(scatter_df, "_hour", "_minutes")
                labels, values = self._labels_values_from_series(series)
                return labels, values, series
            labels, values = [], []
        elif graph_type == "site_alarm_count_vs_duration":
            if "site_id" in work.columns and "_duration_secs" in work.columns:
                grouped = work.groupby("site_id").agg(count=("site_id", "size"), minutes=("_duration_secs", "sum")).reset_index()
                grouped["minutes"] = grouped["minutes"] / 60.0
                series = self._scatter_series_from_columns(grouped, "count", "minutes", label_col="site_id")
                labels, values = self._labels_values_from_series(series)
                return labels, values, series
            labels, values = [], []
        else:
            labels, values = self._series_from_counts(work, category_col)
        series = [{"label": str(label), "value": float(value)} for label, value in zip(labels, values, strict=False)]
        return labels, values, series

    def _backup_chart_series(self, graph_type: str, kwargs: dict[str, Any]) -> tuple[list[str], list[float], list[dict[str, Any]]]:
        payload = self.query_backup_times(
            site_text=str(kwargs.get("site_text") or kwargs.get("site_code") or ""),
            category=str(kwargs.get("category") or "All"),
            vendor=str(kwargs.get("vendor") or "All"),
            network_type=str(kwargs.get("network_type") or "All"),
            date_from=kwargs.get("date_from"),
            date_to=kwargs.get("date_to"),
            min_minutes=kwargs.get("min_minutes"),
            limit=MAX_QUERY_LIMIT,
            offset=0,
        )
        rows = payload.get("rows") if isinstance(payload, dict) else []
        if not isinstance(rows, list):
            rows = []
        df = pd.DataFrame(rows)
        if df.empty:
            return [], [], []
        minute_col = "backup_minutes" if "backup_minutes" in df.columns else "backup_time_minutes" if "backup_time_minutes" in df.columns else "minutes"
        if graph_type in {"backup_time_distribution", "daily_backup_failure_calendar"}:
            labels, values = self._histogram_series(df.get(minute_col, pd.Series(dtype=float)))
        elif graph_type in {"backup_time_trend", "power_vs_down_timeline", "power_down_incident_timeline"} and "power_occurred_on" in df.columns:
            times = pd.to_datetime(df["power_occurred_on"], errors="coerce", format="mixed").dt.date
            labels = [str(value) for value in times.fillna("").tolist()]
            values = pd.to_numeric(df.get(minute_col, pd.Series(dtype=float)), errors="coerce").fillna(0).astype(float).tolist()
        else:
            site_col = "site_id" if "site_id" in df.columns else "site_code"
            if site_col in df.columns and minute_col in df.columns:
                grouped = df.groupby(site_col, dropna=False)[minute_col].max().sort_values(ascending=False).head(20)
                labels, values = grouped.index.astype(str).tolist(), pd.to_numeric(grouped, errors="coerce").fillna(0).astype(float).tolist()
            else:
                labels, values = [], []
        series = [{"label": str(label), "value": float(value)} for label, value in zip(labels, values, strict=False)]
        return labels, values, series

    def _bdt_chart_series(self, graph_type: str, kwargs: dict[str, Any]) -> tuple[list[str], list[float], list[dict[str, Any]]]:
        rows = self._query_all_bdt_rows(
            site_code=normalize_site_key(kwargs.get("site_code") or "") if kwargs.get("site_code") else "",
            date_from=_date_value(kwargs.get("date_from")),
            date_to=_date_value(kwargs.get("date_to")),
        )
        if graph_type in {"bdt_verdict_counts", "bdt_duration_trend"}:
            labels, values = self._bdt_graph_series(rows, graph_type)
        else:
            df = pd.DataFrame(rows)
            if df.empty:
                labels, values = [], []
            elif graph_type in {"bdt_verdict_share", "bdt_verdict_trend", "bdt_acceptance_rate_gauge"}:
                labels, values = self._series_from_counts(df, "overall_verdict")
            elif graph_type in {"bdt_discharge_distribution", "bdt_discharge_boxplot"}:
                labels, values = self._histogram_series(df.get("discharge_minutes", pd.Series(dtype=float)))
            elif graph_type in {"bdt_discharge_by_battery_brand", "end_voltage_boxplot_by_battery_brand", "battery_brand_radar"}:
                labels, values = self._box_summary_series(df, "battery_brand", "discharge_minutes")
            elif graph_type in {"bdt_end_voltage_distribution", "end_voltage_distribution"}:
                labels, values = self._histogram_series(df.get("end_voltage", pd.Series(dtype=float)))
            elif graph_type in {"bdt_string_count_vs_backup", "num_strings_vs_backup_time"}:
                series = self._scatter_series_from_columns(df, "num_strings", "discharge_minutes", label_col="site_code")
                labels, values = self._labels_values_from_series(series)
                return labels, values, series
            elif graph_type == "bdt_discharge_vs_end_voltage":
                series = self._scatter_series_from_columns(df, "end_voltage", "discharge_minutes", label_col="site_code")
                labels, values = self._labels_values_from_series(series)
                return labels, values, series
            else:
                labels, values = self._series_from_counts(df, "overall_verdict")
        series = [{"label": str(label), "value": float(value)} for label, value in zip(labels, values, strict=False)]
        return labels, values, series

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

exec
/bin/zsh -lc "sed -n '1520,1685p' llm_tools/service.py" in /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
 succeeded in 0ms:
            return [], []
        grouped = work.groupby(column, dropna=False)["_duration_secs"].sum().sort_values(ascending=False) / 60.0
        if top_n:
            grouped = grouped.head(top_n)
        return grouped.index.astype(str).tolist(), grouped.astype(float).tolist()

    @staticmethod
    def _daily_counts(work: pd.DataFrame, *, category: str = "") -> tuple[list[str], list[float]]:
        if "occurred_on" not in work.columns:
            return [], []
        source = work
        if category and "alarm_category" in source.columns:
            source = source[source["alarm_category"].astype(str).str.lower() == category.lower()]
        days = pd.to_datetime(source["occurred_on"], errors="coerce", format="mixed").dropna().dt.date
        counts = days.value_counts().sort_index()
        return [str(v) for v in counts.index.tolist()], counts.astype(float).tolist()

    @staticmethod
    def _histogram_series(values: pd.Series, *, bins: int = 8) -> tuple[list[str], list[float]]:
        numeric = pd.to_numeric(values, errors="coerce").dropna()
        if numeric.empty:
            return [], []
        if numeric.nunique() == 1:
            value = float(numeric.iloc[0])
            return [f"{value:g}"], [float(len(numeric))]
        counts, edges = pd.cut(numeric, bins=min(bins, max(1, numeric.nunique())), retbins=True, duplicates="drop")
        grouped = counts.value_counts().sort_index()
        labels = [f"{interval.left:g}-{interval.right:g}" for interval in grouped.index]
        return labels, grouped.astype(float).tolist()

    @staticmethod
    def _box_summary_series(work: pd.DataFrame, group_col: str, value_col: str) -> tuple[list[str], list[float]]:
        if group_col not in work.columns or value_col not in work.columns:
            return [], []
        numeric = pd.to_numeric(work[value_col], errors="coerce")
        grouped = work.assign(_chart_value=numeric).dropna(subset=["_chart_value"]).groupby(group_col, dropna=False)["_chart_value"].median().sort_values(ascending=False)
        return grouped.index.astype(str).tolist(), grouped.astype(float).tolist()

    @staticmethod
    def _scatter_series_from_columns(work: pd.DataFrame, x_col: str, y_col: str, *, label_col: str = "site_id") -> list[dict[str, Any]]:
        if x_col not in work.columns or y_col not in work.columns:
            return []
        rows = []
        for _, row in work.iterrows():
            x_val = pd.to_numeric(pd.Series([row.get(x_col)]), errors="coerce").iloc[0]
            y_val = pd.to_numeric(pd.Series([row.get(y_col)]), errors="coerce").iloc[0]
            if pd.isna(x_val) or pd.isna(y_val):
                continue
            rows.append({
                "label": str(row.get(label_col) or row.get("site_code") or ""),
                "x": float(x_val),
                "y": float(y_val),
                "value": float(y_val),
            })
        return rows

    @staticmethod
    def _labels_values_from_series(series: list[dict[str, Any]]) -> tuple[list[str], list[float]]:
        return [str(point.get("label") or "") for point in series], [float(point.get("value") or 0.0) for point in series]

    def _alarm_chart_series(self, alarm_df: pd.DataFrame, graph_type: str) -> tuple[list[str], list[float], list[dict[str, Any]]]:
        if alarm_df is None or alarm_df.empty:
            return [], [], []
        work = alarm_df.copy()
        category_col = "alarm_category" if "alarm_category" in work.columns else "alarm_name"
        if graph_type in {"alarm_category_counts", "alarm_category_share", "alarm_category_pareto", "alarm_category_treemap"}:
            labels, values = self._series_from_counts(work, category_col)
        elif graph_type == "alarm_daily_counts":
            labels, values = self._daily_counts(work)
        elif graph_type in {"alarm_volume_trend", "site_alarm_trend", "cumulative_alarm_volume"}:
            labels, values = self._daily_counts(work)
            if graph_type == "cumulative_alarm_volume":
                total = 0.0
                cumulative = []
                for value in values:
                    total += value
                    cumulative.append(total)
                values = cumulative
        elif graph_type == "daily_power_alarm_trend":
            labels, values = self._daily_counts(work, category="Power")
        elif graph_type == "daily_down_alarm_trend":
            labels, values = self._daily_counts(work, category="Down")
        elif graph_type in {"alarm_duration_by_category", "duration_boxplot_by_category", "alarm_count_vs_duration_by_category"}:
            labels, values = self._duration_minutes_by(work, category_col)
        elif graph_type in {"vendor_alarm_share", "vendor_alarm_comparison", "duration_boxplot_by_vendor", "vendor_performance_radar"}:
            labels, values = self._series_from_counts(work, "vendor")
        elif graph_type in {"network_type_share", "network_type_vendor_comparison", "network_type_radar"}:
            labels, values = self._series_from_counts(work, "network_type")
        elif graph_type == "alarm_severity_share":
            labels, values = self._series_from_counts(work, "severity")
        elif graph_type in {"cleared_vs_uncleared_share", "alarm_clearance_rate_gauge"}:
            if "cleared_on" not in work.columns:
                labels, values = [], []
            else:
                cleared = pd.to_datetime(work["cleared_on"], errors="coerce", format="mixed").notna()
                labels, values = ["Cleared", "Uncleared"], [float(cleared.sum()), float((~cleared).sum())]
        elif graph_type in {"top_sites_by_alarm_count", "site_alarm_pareto"}:
            labels, values = self._series_from_counts(work, "site_id", top_n=20)
        elif graph_type in {"top_sites_by_duration", "top_sites_by_alarm_duration", "alarm_duration_pareto", "mttr_by_site"}:
            labels, values = self._duration_minutes_by(work, "site_id", top_n=20)
        elif graph_type in {"top_alarm_names"}:
            labels, values = self._series_from_counts(work, "alarm_name", top_n=20)
        elif graph_type in {"top_alarm_ids"}:
            labels, values = self._series_from_counts(work, "alarm_id", top_n=20)
        elif graph_type == "uncleared_alarms_by_site":
            if "cleared_on" in work.columns:
                work = work[pd.to_datetime(work["cleared_on"], errors="coerce", format="mixed").isna()]
            labels, values = self._series_from_counts(work, "site_id", top_n=20)
        elif graph_type in {"alarm_duration_distribution", "duration_histogram", "time_to_clear_distribution"}:
            labels, values = self._histogram_series(work.get("_duration_secs", pd.Series(dtype=float)) / 60.0)
        elif graph_type == "alarm_count_per_site_distribution":
            counts = work["site_id"].value_counts() if "site_id" in work.columns else pd.Series(dtype=float)
            labels, values = self._histogram_series(counts)
        elif graph_type in {"daily_alarms_by_category", "weekly_alarms_by_category", "stacked_alarm_category_area"}:
            labels, values = self._series_from_counts(work, category_col)
        elif graph_type in {"stacked_vendor_area", "vendor_by_category"}:
            labels, values = self._series_from_counts(work, "vendor")
        elif graph_type == "network_type_by_category":
            labels, values = self._series_from_counts(work, "network_type")
        elif graph_type in {"alarm_heatmap_day_hour", "daily_alarm_calendar", "daily_down_alarm_calendar"}:
            if "occurred_on" not in work.columns:
                labels, values = [], []
            else:
                times = pd.to_datetime(work["occurred_on"], errors="coerce", format="mixed").dropna()
                if graph_type == "alarm_heatmap_day_hour":
                    counts = times.to_frame(name="dt").assign(label=lambda df: df["dt"].dt.day_name().str[:3] + " " + df["dt"].dt.hour.astype(str).str.zfill(2)).label.value_counts().sort_index()
                    labels, values = counts.index.astype(str).tolist(), counts.astype(float).tolist()
                else:
                    if graph_type == "daily_down_alarm_calendar" and "alarm_category" in work.columns:
                        times = pd.to_datetime(work.loc[work["alarm_category"].astype(str).str.lower() == "down", "occurred_on"], errors="coerce", format="mixed").dropna()
                    counts = times.dt.date.value_counts().sort_index()
                    labels, values = [str(v) for v in counts.index], counts.astype(float).tolist()
        elif graph_type in {"alarm_heatmap_site_day", "alarm_heatmap_category_hour", "vendor_alarm_heatmap_day", "network_type_alarm_heatmap"}:
            base_col = "site_id" if graph_type == "alarm_heatmap_site_day" else category_col
            if graph_type == "vendor_alarm_heatmap_day":
                base_col = "vendor"
            elif graph_type == "network_type_alarm_heatmap":
                base_col = "network_type"
            labels, values = self._series_from_counts(work, base_col, top_n=24)
        elif graph_type in {"duration_vs_occurrence_time"}:
            if "occurred_on" in work.columns and "_duration_secs" in work.columns:
                hours = pd.to_datetime(work["occurred_on"], errors="coerce", format="mixed").dt.hour
                scatter_df = work.assign(_hour=hours, _minutes=work["_duration_secs"] / 60.0)
                series = self._scatter_series_from_columns(scatter_df, "_hour", "_minutes")
                labels, values = self._labels_values_from_series(series)
                return labels, values, series
            labels, values = [], []
        elif graph_type == "site_alarm_count_vs_duration":
            if "site_id" in work.columns and "_duration_secs" in work.columns:
                grouped = work.groupby("site_id").agg(count=("site_id", "size"), minutes=("_duration_secs", "sum")).reset_index()
                grouped["minutes"] = grouped["minutes"] / 60.0
                series = self._scatter_series_from_columns(grouped, "count", "minutes", label_col="site_id")
                labels, values = self._labels_values_from_series(series)
                return labels, values, series
            labels, values = [], []
        else:
            labels, values = self._series_from_counts(work, category_col)
        series = [{"label": str(label), "value": float(value)} for label, value in zip(labels, values, strict=False)]
        return labels, values, series

    def _backup_chart_series(self, graph_type: str, kwargs: dict[str, Any]) -> tuple[list[str], list[float], list[dict[str, Any]]]:
        payload = self.query_backup_times(
            site_text=str(kwargs.get("site_text") or kwargs.get("site_code") or ""),
            category=str(kwargs.get("category") or "All"),
            vendor=str(kwargs.get("vendor") or "All"),
            network_type=str(kwargs.get("network_type") or "All"),

exec
/bin/zsh -lc "sed -n '1,260p' llm_tools/tools.py && sed -n '260,560p' llm_tools/tools.py" in /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
 succeeded in 0ms:
"""Tool registry shared by MCP and OpenRouter entrypoints."""

from __future__ import annotations

import math
from typing import Any

from .charts import chart_type_description, chart_type_ids
from .service import CHART_DATA_MAX_POINTS, CHART_WIDGET_URI, LocalDataService


def _schema(properties: dict[str, Any], *, required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


def _output_schema(properties: dict[str, Any] | None = None, *, required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties or {},
        "required": required or [],
        "additionalProperties": True,
    }


_OBJECT_OUTPUT = {"type": "object", "additionalProperties": True}
_OBJECT_ROWS = {"type": "array", "items": _OBJECT_OUTPUT}
_STRING_LIST = {"type": "array", "items": {"type": "string"}}
_NUMBER_LIST = {"type": "array", "items": {"type": "number"}}
_PAGING_PROPERTIES = {
    "limit": {"type": "integer", "minimum": 0, "maximum": 500, "xClampMaximum": True},
    "offset": {"type": "integer", "minimum": 0},
}
_PAGING_OUTPUT = {
    "rows": _OBJECT_ROWS,
    "returned": {"type": "integer"},
    "limit": {"type": "integer"},
    "offset": {"type": "integer"},
    "has_more": {"type": "boolean"},
    "total": {"type": "integer"},
    "error": {"type": "string"},
}


TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "list_data_sources": {
        "description": "List local Alarm Viewer storage sources, table row counts, DuckDB alarm stores, blob storage, and export path.",
        "inputSchema": _schema({}),
        "outputSchema": _output_schema({
            "sqlite": _OBJECT_OUTPUT,
            "duckdb": _OBJECT_ROWS,
            "blob_storage": _OBJECT_OUTPUT,
            "exports": {"type": "string"},
            "error": {"type": "string"},
        }),
    },
    "get_current_time": {
        "description": "Return the current local machine time and timezone for date-aware answers.",
        "inputSchema": _schema({}),
        "outputSchema": _output_schema({
            "local_time": {"type": "string"},
            "utc_time": {"type": "string"},
            "timezone": {"type": "string"},
            "error": {"type": "string"},
        }),
    },
    "query_alarms": {
        "description": "Read alarm rows from the local DuckDB alarm store using safe filters and pagination.",
        "inputSchema": _schema({
            "site_text": {"type": "string", "description": "Site id/text filter."},
            "category": {"type": "string", "description": "Alarm category such as Power, Down, Door, or All."},
            "vendor": {"type": "string"},
            "network_type": {"type": "string"},
            "date_from": {"type": "string", "description": "Inclusive date, YYYY-MM-DD."},
            "date_to": {"type": "string", "description": "Inclusive date, YYYY-MM-DD."},
            "sort_by": {"type": "string"},
            "sort_desc": {"type": "boolean"},
            "limit": {"type": "integer", "minimum": 0, "maximum": 100},
            "offset": {"type": "integer", "minimum": 0},
        }),
        "outputSchema": _output_schema({
            "rows": _OBJECT_ROWS,
            "row_count": {"type": "integer"},
            "error": {"type": "string"},
        }),
    },
    "query_alarm_events": {
        "description": "Read all stored alarm rows from the local DuckDB alarm store with safe filters, sorting, and pagination.",
        "inputSchema": _schema({
            "site_text": {"type": "string", "description": "Fuzzy site id/name filter."},
            "site_code": {"type": "string", "description": "Alias for normalized Site ID."},
            "site_id": {"type": "string", "description": "Alias for normalized Site ID."},
            "category": {"type": "string", "description": "Alarm category such as Power, Down, Door, or All."},
            "vendor": {"type": "string"},
            "network_type": {"type": "string"},
            "date_from": {"type": "string", "description": "Inclusive date, YYYY-MM-DD."},
            "date_to": {"type": "string", "description": "Inclusive date, YYYY-MM-DD."},
            "sort_by": {"type": "string", "description": "Sortable column name."},
            "sort_direction": {"type": "string", "enum": ["asc", "desc"], "description": "Sort direction."},
            "sort_desc": {"type": "boolean", "description": "Deprecated explicit sort direction flag (overridden by sort_direction when provided)."},
            **_PAGING_PROPERTIES,
        }),
        "outputSchema": _output_schema(_PAGING_OUTPUT),
    },
    "query_backup_times": {
        "description": "Compute backup-time site results from local alarms and return sites whose hold-up exceeds a threshold.",
        "inputSchema": _schema({
            "site_text": {"type": "string", "description": "Site id/text filter."},
            "category": {"type": "string", "description": "Alarm category such as Power, Down, or All."},
            "vendor": {"type": "string"},
            "network_type": {"type": "string"},
            "date_from": {"type": "string", "description": "Inclusive date, YYYY-MM-DD."},
            "date_to": {"type": "string", "description": "Inclusive date, YYYY-MM-DD."},
            "min_minutes": {"type": "number", "minimum": 0},
            "limit": {"type": "integer", "minimum": 0, "maximum": 500},
            "offset": {"type": "integer", "minimum": 0},
        }),
        "outputSchema": _output_schema({
            "rows": _OBJECT_ROWS,
            "row_count": {"type": "integer"},
            "total_count": {"type": "integer"},
            "site_count": {"type": "integer"},
            "site_ids": _STRING_LIST,
            "min_minutes": {"type": "number"},
            "threshold_minutes": {"type": "number"},
            "error": {"type": "string"},
        }),
    },
    "alarm_stats": {
        "description": "Return aggregate alarm statistics for safe filters without loading all rows.",
        "inputSchema": _schema({
            "site_text": {"type": "string"},
            "category": {"type": "string"},
            "vendor": {"type": "string"},
            "network_type": {"type": "string"},
            "date_from": {"type": "string"},
            "date_to": {"type": "string"},
        }),
        "outputSchema": _output_schema({
            "total": {"type": "integer"},
            "power": {"type": "integer"},
            "down": {"type": "integer"},
            "door": {"type": "integer"},
            "temp": {"type": "integer"},
            "sites": {"type": "integer"},
            "avg_duration_secs": {"type": "number"},
            "error": {"type": "string"},
        }),
    },
    "query_bdt_results": {
        "description": "Read BDT validation run summaries from the local app DB.",
        "inputSchema": _schema({
            "site_code": {"type": "string"},
            "overall": {"type": "string", "description": "Overall BDT verdict."},
            "rule_id": {"type": "string", "description": "Rule code such as R3 or R10."},
            "rule_verdict": {"type": "string", "description": "Rule verdict such as Accepted, Rejected, Revise, No data."},
            "date_from": {"type": "string"},
            "date_to": {"type": "string"},
            "limit": {"type": "integer", "minimum": 0, "maximum": 500},
            "offset": {"type": "integer", "minimum": 0},
        }),
        "outputSchema": _output_schema({
            "total": {"type": "integer"},
            "rows": _OBJECT_ROWS,
            "error": {"type": "string"},
        }),
    },
    "get_bdt_detail": {
        "description": "Read one BDT validation detail with rules, discharge readings, and photo metadata.",
        "inputSchema": _schema({
            "validation_run_id": {"type": "integer"},
            "site_code": {"type": "string"},
            "test_date": {"type": "string"},
        }),
        "outputSchema": _output_schema({
            "validation_run_id": {"type": "integer"},
            "overall_verdict": {"type": "string"},
            "run_at": {},
            "bdt": _OBJECT_OUTPUT,
            "rules": _OBJECT_ROWS,
            "photos": _OBJECT_ROWS,
            "error": {"type": "string"},
        }),
    },
    "get_photo_metadata": {
        "description": "Read BDT photo metadata from the local app DB without returning image bytes.",
        "inputSchema": _schema({
            "site_code": {"type": "string"},
            "bdt_test_id": {"type": "integer"},
            "limit": {"type": "integer", "minimum": 0, "maximum": 500},
        }),
        "outputSchema": _output_schema({
            "rows": _OBJECT_ROWS,
            "row_count": {"type": "integer"},
            "error": {"type": "string"},
        }),
    },
    "get_site_dossier": {
        "description": (
            "Build a complete site dossier from local DuckDB alarms and BDT DB data. "
            "Returns alarm previews, BDT summaries/details, and exports a full XLSX with alarms, BDT rules, photos, and discharge content."
        ),
        "inputSchema": _schema({
            "site_code": {"type": "string", "description": "Required normalized or raw site code."},
            "site_text": {"type": "string"},
            "date_from": {"type": "string"},
            "date_to": {"type": "string"},
            "alarm_preview_limit": {"type": "integer", "minimum": 0, "maximum": 500},
            "bdt_preview_limit": {"type": "integer", "minimum": 0, "maximum": 500},
            "bdt_detail_limit": {"type": "integer", "minimum": 0, "maximum": 500},
        }),
        "outputSchema": _output_schema({
            "site_code": {"type": "string"},
            "alarm_total": {"type": "integer"},
            "alarm_stats": _OBJECT_OUTPUT,
            "alarm_rows": _OBJECT_ROWS,
            "bdt_total": {"type": "integer"},
            "bdt_rows": _OBJECT_ROWS,
            "bdt_details": _OBJECT_ROWS,
            "export_path": {"type": "string"},
            "error": {"type": "string"},
        }),
    },
    "describe_federated_site_data": {
        "description": "Describe the curated fields, sources, filters, operators, and examples for federated site data queries.",
        "inputSchema": _schema({}),
        "outputSchema": _output_schema(),
    },
    "describe_admin_sql_views": {
        "description": "Describe approved read-only SQL views available to trusted admin SQL queries.",
        "inputSchema": _schema({}),
        "outputSchema": _output_schema(),
    },
    "query_admin_readonly_sql": {
        "description": "Run trusted read-only SQL against approved MCP views only. Results are capped at 500 rows and sanitized.",
        "inputSchema": _schema({
            "sql": {"type": "string", "description": "SELECT/WITH query against approved views from describe_admin_sql_views."},
            **_PAGING_PROPERTIES,
        }, required=["sql"]),
        "outputSchema": _output_schema(_PAGING_OUTPUT),
    },
    "query_federated_site_data": {
        "description": "Query selected fields from federated site data with whitelisted filters, joined by Site ID.",
        "inputSchema": _schema({
            "select": _STRING_LIST,
            "sources": _STRING_LIST,
            "site_filters": _OBJECT_OUTPUT,
            "section_filters": _OBJECT_OUTPUT,
            "section_match_mode": {"type": "string", "enum": ["filter_nested_only", "require_matching_sites"]},
            "include_sections": _STRING_LIST,
            **_PAGING_PROPERTIES,
        }),
        "outputSchema": _output_schema(_PAGING_OUTPUT),
    },
    "get_all_sites_full_context": {
        "description": "Return a page of sites with operational base fields and limited nested per-site context sections.",
        "description": "Return a page of sites with operational base fields and limited nested per-site context sections.",
        "inputSchema": _schema({
            "site_filters": _OBJECT_OUTPUT,
            "section_filters": _OBJECT_OUTPUT,
            "section_match_mode": {"type": "string", "enum": ["filter_nested_only", "require_matching_sites"]},
            "metadata_limit": {"type": "integer", "minimum": 0, "maximum": 500, "xClampMaximum": True},
            "alarm_limit": {"type": "integer", "minimum": 0, "maximum": 500, "xClampMaximum": True},
            "bdt_limit": {"type": "integer", "minimum": 0, "maximum": 500, "xClampMaximum": True},
            "date_from": {"type": "string"},
            "date_to": {"type": "string"},
            "category": {"type": "string"},
            "vendor": {"type": "string"},
            "network_type": {"type": "string"},
            "reporting_period": {"type": "string"},
            "period": {"type": "string"},
            "week": {"type": "string"},
            "overall": {"type": "string"},
            "rule_id": {"type": "string"},
            "rule_verdict": {"type": "string"},
            **_PAGING_PROPERTIES,
        }),
        "outputSchema": _output_schema(_PAGING_OUTPUT),
    },
    "list_chart_types": {
        "description": "List supported chart types. For ChatGPT charts, call list_chart_types, then get_chart_data, then render_chart_widget.",
        "inputSchema": _schema({
            "family": {"type": "string", "description": "Optional chart family filter, such as alarm, backup, bdt, pm, or metadata."},
            "chart_kind": {"type": "string", "description": "Optional chart kind filter, such as bar, donut, line, heatmap, or scatter."},
            "renderable_only": {"type": "boolean", "description": "When true, return only charts that can be rendered as images."},
        }),
        "outputSchema": _output_schema({
            "charts": _OBJECT_ROWS,
            "count": {"type": "integer"},
            "error": {"type": "string"},
        }),
    },
    "get_chart_data": {
        "description": (
            "Return validated structured chart data without creating an image. "
            "Preferred ChatGPT chart flow: list_chart_types -> get_chart_data -> render_chart_widget."
        ),
        "inputSchema": _schema({
            "chart_id": {
                "type": "string",
                "enum": chart_type_ids(renderable_only=True),
                "description": "Chart id from list_chart_types.",
            },
            "filters": {
                "type": "object",
                "description": "Optional safe chart filters such as site_code, site_text, date_from, date_to, category, vendor, network_type, and min_minutes.",
                "additionalProperties": True,
            },
            "max_points": {"type": "integer", "minimum": 0, "maximum": CHART_DATA_MAX_POINTS, "xClampMaximum": True},
            "group_by": {"type": "string", "description": "Reserved grouping hint when supported by a chart."},
            "sort_by": {"type": "string", "description": "Reserved sort hint when supported by a chart."},
            "sort_direction": {"type": "string", "enum": ["asc", "desc"], "description": "Reserved sort direction hint."},
        }, required=["chart_id"]),
        "outputSchema": _output_schema({
            "chart_id": {"type": "string"},
            "chart_kind": {"type": "string"},
            "title": {"type": "string"},
            "labels": _STRING_LIST,
            "values": _NUMBER_LIST,
            "series": _OBJECT_ROWS,
            "x_axis": _OBJECT_OUTPUT,
            "y_axis": _OBJECT_OUTPUT,
            "warnings": _STRING_LIST,
            "data_quality": _OBJECT_OUTPUT,
            "query_context": _OBJECT_OUTPUT,
            "empty_state": _OBJECT_OUTPUT,
            "error": {"type": "string"},
        }),
    },
    "render_chart_widget": {
        "description": (
            "Render the Apps SDK chart widget from a validated get_chart_data payload. "
            "Call get_chart_data first, then pass its structured payload here."
        ),
        "inputSchema": _schema({
            "chart_id": {"type": "string"},
            "chart_kind": {"type": "string"},
            "title": {"type": "string"},
            "labels": _STRING_LIST,
            "values": _NUMBER_LIST,
            "series": _OBJECT_ROWS,
            "x_axis": _OBJECT_OUTPUT,
            "y_axis": _OBJECT_OUTPUT,
            "warnings": _STRING_LIST,
            "data_quality": _OBJECT_OUTPUT,
            "query_context": _OBJECT_OUTPUT,
            "empty_state": _OBJECT_OUTPUT,
        }, required=["chart_id", "chart_kind", "title", "labels", "values", "series"]),
        "outputSchema": _output_schema({
            "chart_id": {"type": "string"},
            "chart_kind": {"type": "string"},
            "title": {"type": "string"},
            "labels": _STRING_LIST,
            "values": _NUMBER_LIST,
            "series": _OBJECT_ROWS,
            "x_axis": _OBJECT_OUTPUT,
            "y_axis": _OBJECT_OUTPUT,
            "warnings": _STRING_LIST,
            "data_quality": _OBJECT_OUTPUT,
            "query_context": _OBJECT_OUTPUT,
            "empty_state": _OBJECT_OUTPUT,
            "_meta": _OBJECT_OUTPUT,
            "error": {"type": "string"},
        }),
        "_meta": {
            "openai/outputTemplate": CHART_WIDGET_URI,
            "ui": {"resourceUri": CHART_WIDGET_URI},
            "openai/toolInvocation/invoking": "Rendering chart...",
            "openai/toolInvocation/invoked": "Chart ready.",
        },
    },
    "get_computed_report": {
        "description": "Read computed chart-like or report-like rows for backups and charts without creating files.",
        "inputSchema": _schema({
            "report_type": {
                "type": "string",
                "description": f"Supported values: backup_times, {chart_type_description()}, ht_meet, ht_weekly_summary, ht_consolidated_history, bdt_export, accepted_pm_report, or chart:* aliases.",
            },
            "site_code": {"type": "string"},
            "site_id": {"type": "string"},
            "site_text": {"type": "string", "description": "Site fuzzy text filter for alarm-derived report types."},
            "export_week": {"type": "string", "description": "Required HT/summary period input (e.g. W01-26)."},
            "week_label": {"type": "string", "description": "Alias for export_week."},
            "source_file_id": {"type": "string", "description": "Allowlisted uploaded file id for source-file report types."},
            "section": {"type": "string", "description": "Section selector for bdt_export."},
            "health_pct": {"type": "number", "minimum": 0},
            "date_from": {"type": "string", "description": "Inclusive date, YYYY-MM-DD."},
            "date_to": {"type": "string", "description": "Inclusive date, YYYY-MM-DD."},
            "category": {"type": "string", "description": "Alarm category such as Power, Down, Door, or All."},
            "vendor": {"type": "string"},
            "network_type": {"type": "string"},
            "min_minutes": {"type": "number", "minimum": 0},
            "include_raw_json": {"type": "boolean", "description": "Include flattened raw JSON fields in row results."},
            **_PAGING_PROPERTIES,
        }, required=["report_type"]),
        "outputSchema": _output_schema({
            "report_type": {"type": "string"},
            "rows": _OBJECT_ROWS,
            "returned": {"type": "integer"},
            "limit": {"type": "integer"},
            "offset": {"type": "integer"},
            "has_more": {"type": "boolean"},
            "total": {"type": "integer"},
            "row_count": {"type": "integer"},
            "site_count": {"type": "integer"},
            "site_ids": _STRING_LIST,
            "min_minutes": {"type": "number"},
            "threshold_minutes": {"type": "number"},
            "points": {"type": "integer"},
            "labels": _STRING_LIST,
            "values": _NUMBER_LIST,
            "series": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string"},
                        "value": {"type": "number"},
                    },
                    "additionalProperties": True,
                },
            },
            "error": {"type": "string"},
            "required": {
                "type": "array",
                "items": {"type": "string"},
            },
            "action": {"type": "string"},
            "section": {"type": "string"},
            "sections": {
                "type": "array",
                "items": {"type": "string"},
            },
            "export_week": {"type": "string"},
            "week_label": {"type": "string"},
            "sheet_name": {"type": "string"},
            "site_column": {"type": "string"},
            "date_column": {"type": "string"},
            "status_column": {"type": "string"},
            "health_pct": {"type": "number"},
            "source_file_id": {"type": "string"},
        }),
    },
    "read_photo_blob": {
        "description": "Read one stored photo blob by SHA-256 as base64. Use only when the user explicitly asks to inspect an image.",
        "inputSchema": _schema({
            "sha256": {"type": "string"},
        }, required=["sha256"]),
        "outputSchema": _output_schema({
            "sha256": {"type": "string"},
            "mime_type": {"type": "string"},
            "base64": {"type": "string"},
            "error": {"type": "string"},
        }),
    },
    "export_report": {
        "description": (
            "Create a CSV/XLSX export under the controlled local exports directory. "
            "Use site_alarm_report with an uploaded VIP/site-list CSV/XLSX, "
            "accepted_pm_report with an uploaded Accepted PM CSV/XLSX, and "
            "bdt_export for full BDT validation exports."
        ),
        "inputSchema": _schema({
            "report_type": {
                "type": "string",
                "enum": [
                    "alarms",
                    "bdt_results",
                    "photo_manifest",
                    "site_alarm_report",
                    "accepted_pm_report",
                    "bdt_export",
                ],
            },
            "format": {"type": "string", "enum": ["csv", "xlsx"]},
            "name": {"type": "string"},
            "source_file_id": {
                "type": "string",
                "description": (
                    "Opaque upload ID from the chat context. Required for site_alarm_report "
                    "and accepted_pm_report when the file was uploaded through chat; optional "
                    "for bdt_export to restrict the export to uploaded site codes."
                ),
            },
            "health_pct": {
                "type": "number",
                "description": "BDT health percentage threshold used by accepted PM and BDT exports.",
            },
            "site_text": {"type": "string"},
            "site_code": {"type": "string"},
            "category": {"type": "string"},
            "overall": {"type": "string"},
            "rule_id": {"type": "string"},
            "rule_verdict": {"type": "string"},
            "date_from": {"type": "string"},
            "date_to": {"type": "string"},
            "limit": {"type": "integer", "minimum": 0, "maximum": 500},
            "offset": {"type": "integer", "minimum": 0},
        }, required=["report_type"]),
        "outputSchema": _output_schema({
            "path": {"type": "string"},
            "rows": {"type": "integer"},
            "format": {"type": "string"},
            "report_type": {"type": "string"},
            "source_file_id": {"type": "string"},
            "sheet_name": {"type": "string"},
            "site_column": {"type": "string"},
            "date_column": {"type": "string"},
            "status_column": {"type": "string"},
            "site_count": {"type": "integer"},
            "alarm_rows": {"type": "integer"},
            "bdt_results": {"type": "integer"},
            "sheets": _STRING_LIST,
            "error": {"type": "string"},
        }),
    },
    "search_site_metadata": {
        "description": "Search imported Site Metadata Catalog rows by site text, area, subcontractor/contractor, or backup/battery status.",
        "inputSchema": _schema({
            "site_text": {"type": "string"},
            "site_code": {"type": "string"},
            "site_id": {"type": "string"},
            "area": {"type": "string"},
            "subcontractor": {"type": "string"},
            "contractor": {"type": "string"},
            "backup_status": {"type": "string"},
            "battery_status": {"type": "string"},
            "limit": {"type": "integer", "minimum": 0, "maximum": 500},
        }),
        "outputSchema": _output_schema({
            "rows": _OBJECT_ROWS,
            "row_count": {"type": "integer"},
            "error": {"type": "string"},
        }),
    },
    "query_site_metadata": {
        "description": "Read normalized site metadata from the local DuckDB catalog for a given site code.",
        "inputSchema": _schema({
            "site_code": {"type": "string", "description": "Normalized or raw site code."},
            "site_id": {"type": "string", "description": "Alias for site_code."},
        }),
        "outputSchema": _output_schema({
            "site_id": {"type": "string"},
            "rows": _OBJECT_ROWS,
            "row_count": {"type": "integer"},
            "error": {"type": "string"},
        }),
    },
    "query_bdt_summary": {
        "description": "Read BDT summary catalog rows from the local DuckDB catalog with optional filters.",
        "inputSchema": _schema({
            "site_code": {"type": "string", "description": "Normalized or raw site code."},
            "site_id": {"type": "string", "description": "Alias for site_code."},
            "reporting_period": {"type": "string"},
            "period": {"type": "string", "description": "Alias for reporting_period."},
            "week": {"type": "string"},
            "date_from": {"type": "string", "description": "Inclusive date, YYYY-MM-DD."},

exec
/bin/zsh -lc "sed -n '560,920p' llm_tools/tools.py" in /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
 succeeded in 0ms:
            "date_from": {"type": "string", "description": "Inclusive date, YYYY-MM-DD."},
            "date_to": {"type": "string", "description": "Inclusive date, YYYY-MM-DD."},
            "limit": {"type": "integer", "minimum": 0, "maximum": 500},
            "offset": {"type": "integer", "minimum": 0},
        }),
        "outputSchema": _output_schema({
            "rows": _OBJECT_ROWS,
            "total": {"type": "integer"},
            "error": {"type": "string"},
        }),
    },
    "query_bdt_full": {
        "description": "Read BDT summary, validation runs, rules, photos, and review events for one site period with shared pagination.",
        "inputSchema": _schema({
            "site_code": {"type": "string", "description": "Normalized or raw site code."},
            "site_id": {"type": "string", "description": "Alias for site_code."},
            "reporting_period": {"type": "string"},
            "period": {"type": "string", "description": "Alias for reporting_period."},
            "week": {"type": "string"},
            "date_from": {"type": "string", "description": "Inclusive date, YYYY-MM-DD."},
            "date_to": {"type": "string", "description": "Inclusive date, YYYY-MM-DD."},
            "overall": {"type": "string", "description": "Overall BDT verdict."},
            "rule_id": {"type": "string", "description": "Rule code such as R3 or R10."},
            "rule_verdict": {"type": "string", "description": "Rule verdict such as Accepted, Rejected, Revise, No data."},
            "include_raw_json": {"type": "boolean", "description": "Include raw JSON payload fields."},
            **_PAGING_PROPERTIES,
        }),
        "outputSchema": _output_schema({
            "bdt_summary": _output_schema(_PAGING_OUTPUT),
            "validation_runs": _output_schema(_PAGING_OUTPUT),
            "bdt_tests": _output_schema(_PAGING_OUTPUT),
            "rule_results": _output_schema(_PAGING_OUTPUT),
            "photos": _output_schema(_PAGING_OUTPUT),
            "review_events": _output_schema(_PAGING_OUTPUT),
            "error": {"type": "string"},
        }),
    },
    "list_sites": {
        "description": (
            "Read-only inventory index across all known sites, with optional filters for metadata, statuses, and data source presence."
        ),
        "inputSchema": _schema({
            "site_text": {"type": "string", "description": "Match normalized site id or site_name."},
            "site_code": {"type": "string", "description": "Alias for site_text."},
            "site_id": {"type": "string", "description": "Alias for site_text."},
            "area": {"type": "string"},
            "contractor": {"type": "string"},
            "subcontractor": {"type": "string"},
            "backup_status": {"type": "string"},
            "battery_status": {"type": "string"},
            "has_metadata": {"type": "boolean"},
            "has_alarms": {"type": "boolean"},
            "has_bdt_summary": {"type": "boolean"},
            "has_bdt_validation": {"type": "boolean"},
            "has_bdt": {"type": "boolean"},
            **_PAGING_PROPERTIES,
        }),
        "outputSchema": _output_schema(_PAGING_OUTPUT),
    },
    "query_network_summary": {
        "description": "Read full imported Network Summary/Site Metadata rows with normalized and original workbook-header fields.",
        "inputSchema": _schema({
            "site_text": {"type": "string", "description": "Site id/text filter."},
            "site_id": {"type": "string", "description": "Alias for site_code."},
            "site_code": {"type": "string", "description": "Alias for site_id."},
            "area": {"type": "string"},
            "subcontractor": {"type": "string"},
            "contractor": {"type": "string"},
            "backup_status": {"type": "string"},
            "battery_status": {"type": "string"},
            "include_raw_json": {"type": "boolean"},
            **_PAGING_PROPERTIES,
        }),
        "outputSchema": _output_schema(_PAGING_OUTPUT),
    },
    "get_site_alarm_context": {
        "description": "Return combined alarm statistics and recent alarm rows for a given site.",
        "inputSchema": _schema({
            "site_code": {"type": "string", "description": "Normalized or raw site code."},
            "site_id": {"type": "string", "description": "Alias for site_code."},
            "date_from": {"type": "string", "description": "Inclusive date, YYYY-MM-DD."},
            "date_to": {"type": "string", "description": "Inclusive date, YYYY-MM-DD."},
            "limit": {"type": "integer", "minimum": 0, "maximum": 500},
        }),
        "outputSchema": _output_schema({
            "site_code": {"type": "string"},
            "alarm_stats": _OBJECT_OUTPUT,
            "alarm_rows": _OBJECT_ROWS,
            "alarm_total": {"type": "integer"},
            "error": {"type": "string"},
        }),
    },
    "get_site_full_context": {
        "description": "Return one-site full context including network summary, alarm statistics, alarm rows, and BDT sections.",
        "inputSchema": _schema({
            "site_code": {"type": "string", "description": "Normalized or raw site code."},
            "site_id": {"type": "string", "description": "Alias for site_code."},
            "metadata_limit": {"type": "integer", "minimum": 0, "maximum": 500, "xClampMaximum": True},
            "metadata_offset": {"type": "integer", "minimum": 0},
            "alarm_limit": {"type": "integer", "minimum": 0, "maximum": 500, "xClampMaximum": True},
            "alarm_offset": {"type": "integer", "minimum": 0},
            "bdt_limit": {"type": "integer", "minimum": 0, "maximum": 500, "xClampMaximum": True},
            "bdt_offset": {"type": "integer", "minimum": 0},
            "date_from": {"type": "string", "description": "Inclusive date, YYYY-MM-DD."},
            "date_to": {"type": "string", "description": "Inclusive date, YYYY-MM-DD."},
            "category": {"type": "string", "description": "Alarm category such as Power, Down, Door, or All."},
            "vendor": {"type": "string"},
            "network_type": {"type": "string"},
            "reporting_period": {"type": "string", "description": "BDT reporting period alias."},
            "period": {"type": "string", "description": "Alias for reporting_period."},
            "week": {"type": "string"},
            "overall": {"type": "string", "description": "Filter BDT runs by overall verdict."},
            "rule_id": {"type": "string", "description": "Filter BDT rule results by rule code."},
            "rule_verdict": {"type": "string", "description": "Filter BDT rule results by verdict."},
            "include_raw_json": {"type": "boolean", "description": "Include raw JSON payload fields."},
        }),
        "outputSchema": _output_schema({
            "site_id": {"type": "string"},
            "site_code": {"type": "string"},
            "network_summary": _output_schema(_PAGING_OUTPUT),
            "alarm_stats": _OBJECT_OUTPUT,
            "alarm_rows": _output_schema(_PAGING_OUTPUT),
            "bdt_summary": _output_schema(_PAGING_OUTPUT),
            "validation_runs": _output_schema(_PAGING_OUTPUT),
            "bdt_tests": _output_schema(_PAGING_OUTPUT),
            "rule_results": _output_schema(_PAGING_OUTPUT),
            "photos": _output_schema(_PAGING_OUTPUT),
            "review_events": _output_schema(_PAGING_OUTPUT),
            "bdt_error": {"type": "string"},
            "error": {"type": "string"},
        }),
    },
    "get_sites_context_report": {
        "description": "Return workbook-like all-sites context by sheet, with manifest and pagination metadata.",
        "inputSchema": _schema({
            "sheet": {"type": "string", "description": "Optional sheet name (case-insensitive). If omitted, returns manifest."},
            "site_text": {"type": "string", "description": "Site id/text filter."},
            "site_code": {"type": "string", "description": "Alias for site_text."},
            "site_id": {"type": "string", "description": "Alias for site_text."},
            "area": {"type": "string"},
            "contractor": {"type": "string"},
            "subcontractor": {"type": "string"},
            "backup_status": {"type": "string"},
            "battery_status": {"type": "string"},
            "has_metadata": {"type": "boolean"},
            "has_alarms": {"type": "boolean"},
            "has_bdt_summary": {"type": "boolean"},
            "has_bdt_validation": {"type": "boolean"},
            "has_bdt": {"type": "boolean"},
            "category": {"type": "string", "description": "Alarm category such as Power, Down, Door, or All."},
            "vendor": {"type": "string"},
            "network_type": {"type": "string"},
            "date_from": {"type": "string", "description": "Inclusive date, YYYY-MM-DD."},
            "date_to": {"type": "string", "description": "Inclusive date, YYYY-MM-DD."},
            "reporting_period": {"type": "string", "description": "BDT reporting period."},
            "period": {"type": "string", "description": "Alias for reporting_period."},
            "week": {"type": "string"},
            "overall": {"type": "string", "description": "Filter BDT validation runs by overall verdict."},
            "rule_id": {"type": "string", "description": "Filter BDT rule results by rule code."},
            "rule_verdict": {"type": "string", "description": "Filter BDT rule results by verdict."},
            "include_raw_json": {"type": "boolean", "description": "Include raw JSON payload fields."},
            **_PAGING_PROPERTIES,
        }),
        "outputSchema": _output_schema({
            "sheets": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "total": {"type": "integer"},
                        "available": {"type": "boolean"},
                    },
                    "additionalProperties": True,
                },
            },
            "sheet": {"type": "string"},
            "rows": _OBJECT_ROWS,
            "returned": {"type": "integer"},
            "limit": {"type": "integer"},
            "offset": {"type": "integer"},
            "has_more": {"type": "boolean"},
            "total": {"type": "integer"},
            "error": {"type": "string"},
            "error_sheet": {"type": "string"},
        }),
    },
    "query_battery_backup_insights": {
        "description": (
            "Read-only operational battery/backup insights by linking Network Summary metadata with BDT summary, "
            "BDT tests, validation runs, rules, and photo evidence."
        ),
        "inputSchema": _schema({
            "site_text": {"type": "string", "description": "Site id/text filter."},
            "site_code": {"type": "string", "description": "Alias for site_text."},
            "site_id": {"type": "string", "description": "Alias for site_text."},
            "area": {"type": "string"},
            "contractor": {"type": "string"},
            "subcontractor": {"type": "string"},
            "backup_status": {"type": "string"},
            "battery_status": {"type": "string"},
            "has_bdt": {"type": "boolean"},
            "has_bdt_summary": {"type": "boolean"},
            "has_bdt_validation": {"type": "boolean"},
            "date_from": {"type": "string", "description": "Inclusive BDT test date, YYYY-MM-DD."},
            "date_to": {"type": "string", "description": "Inclusive BDT test date, YYYY-MM-DD."},
            "reporting_period": {"type": "string", "description": "BDT reporting period."},
            "period": {"type": "string", "description": "Alias for reporting_period."},
            "week": {"type": "string"},
            "overall": {"type": "string", "description": "Filter BDT validation runs by overall verdict."},
            "min_backup_minutes": {"type": "number", "description": "Minimum measured BDT discharge minutes considered dependable."},
            "backup_minutes_tolerance": {"type": "number", "description": "Allowed absolute minute difference between Network Summary and BDT measured backup."},
            **_PAGING_PROPERTIES,
        }),
        "outputSchema": _output_schema(_PAGING_OUTPUT | {
            "source_errors": _OBJECT_OUTPUT,
        }),
    },
}

_WRITE_TOOL_NAMES = {"export_report", "get_site_dossier"}
_OPENROUTER_EXCLUDED_TOOL_NAMES = {"render_chart_widget"}


def _mcp_annotations(name: str) -> dict[str, Any]:
    if name in _WRITE_TOOL_NAMES:
        return {
            "readOnlyHint": False,
            "openWorldHint": False,
            "destructiveHint": False,
        }
    return {"readOnlyHint": True}


def tool_definitions_for_mcp() -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "description": schema["description"],
            "inputSchema": schema["inputSchema"],
            "outputSchema": schema["outputSchema"],
            "annotations": _mcp_annotations(name),
            **({"_meta": schema["_meta"]} if "_meta" in schema else {}),
        }
        for name, schema in TOOL_SCHEMAS.items()
    ]


def tool_definitions_for_openrouter() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": schema["description"],
                "parameters": schema["inputSchema"],
            },
        }
        for name, schema in TOOL_SCHEMAS.items()
        if name not in _OPENROUTER_EXCLUDED_TOOL_NAMES
    ]


def _type_matches(value: Any, expected_type: str) -> bool:
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        if isinstance(value, bool):
            return False
        if isinstance(value, int):
            return True
        return isinstance(value, float) and value.is_integer()
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    return True


def _validate_tool_arguments(arguments: Any, input_schema: dict[str, Any]) -> dict[str, Any] | str:
    if arguments is None:
        args: dict[str, Any] = {}
    elif isinstance(arguments, dict):
        args = dict(arguments)
    else:
        return "arguments must be an object"

    if input_schema.get("type") == "object" and not isinstance(args, dict):
        return "arguments must be an object"

    properties = input_schema.get("properties", {})
    for field in input_schema.get("required", []):
        if field not in args:
            return f"missing required property: {field}"

    if input_schema.get("additionalProperties") is False:
        for field in args:
            if field not in properties:
                return f"unexpected property: {field}"

    required_fields = set(input_schema.get("required", []))

    for field, value in args.items():
        field_schema = properties.get(field, {})
        expected_type = field_schema.get("type")
        if value is None and field not in required_fields:
            continue
        if expected_type == "number" and isinstance(value, float) and not math.isfinite(value):
            return f"{field} must be finite"
        if expected_type == "integer" and isinstance(value, float) and math.isinf(value):
            return f"{field} must be finite"
        if expected_type and not _type_matches(value, expected_type):
            return f"{field} must be {expected_type}"
        if expected_type == "integer" and isinstance(value, float):
            value = int(value)
            args[field] = value

        enum_values = field_schema.get("enum")
        if enum_values is not None and value not in enum_values:
            return f"{field} must be one of: {', '.join(str(item) for item in enum_values)}"

        if expected_type in {"integer", "number"}:
            minimum = field_schema.get("minimum")
            if minimum is not None and value < minimum:
                return f"{field} must be >= {minimum}"
            maximum = field_schema.get("maximum")
            if maximum is not None and value > maximum:
                if field_schema.get("xClampMaximum"):
                    args[field] = maximum
                else:
                    return f"{field} must be <= {maximum}"

    return args


def dispatch_tool(service: LocalDataService, name: str, arguments: Any = None) -> Any:
    if name not in TOOL_SCHEMAS:
        return {"error": f"unknown tool: {name}"}

    validated_args = _validate_tool_arguments(arguments, TOOL_SCHEMAS[name]["inputSchema"])
    if isinstance(validated_args, str):
        return {"error": f"invalid arguments for {name}: {validated_args}"}

    method = getattr(service, name, None)
    if method is None or not callable(method):
        return {"error": f"tool unavailable: {name}"}
    try:
        return method(**validated_args)
    except Exception as exc:
        return {"error": f"{name} failed: {exc}"}

exec
/bin/zsh -lc 'git diff ce401c4d262c9362d3110036b9ea8f821d8a4719 -- llm_tools/openrouter_agent.py llm_tools/mcp_server.py web/routers/mcp.py mcp_app/chart_widget/src/chart_widget.ts mcp_app/chart_widget/build.py mcp_app/chart_widget/dist/chart.html' in /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
 succeeded in 0ms:
diff --git a/llm_tools/mcp_server.py b/llm_tools/mcp_server.py
index 8b83409..383c3f6 100644
--- a/llm_tools/mcp_server.py
+++ b/llm_tools/mcp_server.py
@@ -4,14 +4,46 @@ from __future__ import annotations
 
 import json
 import sys
+from pathlib import Path
 from typing import Any
 
 from .openrouter_agent import _model_safe_tool_result
-from .service import LocalDataService
+from .service import CHART_WIDGET_MIME_TYPE, CHART_WIDGET_URI, LocalDataService
 from .tools import dispatch_tool, tool_definitions_for_mcp
 
 SERVER_INFO = {"name": "alarm-viewer-local-data", "version": "0.1.0"}
 
+_WIDGET_NAME = "chart-widget"
+_WIDGET_TITLE = "Alarm Chart Widget"
+_WIDGET_HTML_PATH = Path(__file__).resolve().parents[1] / "mcp_app" / "chart_widget" / "dist" / "chart.html"
+
+
+def chart_widget_resource() -> dict[str, Any]:
+    return {
+        "uri": CHART_WIDGET_URI,
+        "name": _WIDGET_NAME,
+        "title": _WIDGET_TITLE,
+        "mimeType": CHART_WIDGET_MIME_TYPE,
+    }
+
+
+def chart_widget_html() -> str:
+    if not _WIDGET_HTML_PATH.exists():
+        raise FileNotFoundError(f"chart widget build artifact missing: {_WIDGET_HTML_PATH}")
+    return _WIDGET_HTML_PATH.read_text(encoding="utf-8")
+
+
+def read_chart_widget_resource(uri: str) -> dict[str, Any] | None:
+    if uri != CHART_WIDGET_URI:
+        return None
+    return {
+        "uri": CHART_WIDGET_URI,
+        "mimeType": CHART_WIDGET_MIME_TYPE,
+        "text": chart_widget_html(),
+        "_meta": {"ui": {"prefersBorder": True}},
+    }
+
+
 
 def _response(request_id: Any, result: Any) -> dict[str, Any]:
     return {"jsonrpc": "2.0", "id": request_id, "result": result}
@@ -35,7 +67,7 @@ class AlarmViewerMcpServer:
             return _response(request_id, {
                 "protocolVersion": "2024-11-05",
                 "serverInfo": SERVER_INFO,
-                "capabilities": {"tools": {}},
+                "capabilities": {"tools": {}, "resources": {}},
             })
 
         if method == "notifications/initialized":
@@ -44,6 +76,21 @@ class AlarmViewerMcpServer:
         if method == "tools/list":
             return _response(request_id, {"tools": tool_definitions_for_mcp()})
 
+        if method == "resources/list":
+            return _response(request_id, {"resources": [chart_widget_resource()]})
+
+        if method == "resources/read":
+            if params is None:
+                return _error(request_id, -32602, "resources/read params must be an object")
+            uri = str(params.get("uri") or "")
+            try:
+                resource = read_chart_widget_resource(uri)
+            except FileNotFoundError as exc:
+                return _error(request_id, -32002, str(exc))
+            if resource is None:
+                return _error(request_id, -32002, f"resource not found: {uri}")
+            return _response(request_id, {"contents": [resource]})
+
         if method == "tools/call":
             if params is None:
                 return _error(request_id, -32602, "tools/call params must be an object")
@@ -51,16 +98,20 @@ class AlarmViewerMcpServer:
             arguments = params.get("arguments") if "arguments" in params else {}
             result = dispatch_tool(self.service, name, arguments)
             safe_result = _model_safe_tool_result(result)
-            return _response(request_id, {
-                "content": [
-                    {
-                        "type": "text",
-                        "text": json.dumps(safe_result, default=str, ensure_ascii=False),
-                    }
-                ],
+            content = [
+                {
+                    "type": "text",
+                    "text": json.dumps(safe_result, default=str, ensure_ascii=False),
+                }
+            ]
+            response_payload = {
+                "content": content,
                 "structuredContent": safe_result,
                 "isError": isinstance(result, dict) and "error" in result,
-            })
+            }
+            if isinstance(result, dict) and isinstance(result.get("_meta"), dict):
+                response_payload["_meta"] = result["_meta"]
+            return _response(request_id, response_payload)
 
         return _error(request_id, -32601, f"method not found: {method}")
 
diff --git a/llm_tools/openrouter_agent.py b/llm_tools/openrouter_agent.py
index 292dd35..abf8718 100644
--- a/llm_tools/openrouter_agent.py
+++ b/llm_tools/openrouter_agent.py
@@ -50,7 +50,9 @@ IMPORTANT RULES:
 4. Never claim that missing data proves a condition; say when the local store has no matching records.
 5. The alarm rows card starts collapsed and can expand up to 100 rows.
 6. Use query_backup_times for questions about backup time, backup duration, or battery hold-up between Power and Down alarms.
-7. Use the host clock context for any time-sensitive answer."""
+7. Use list_chart_types when the user asks what charts are available or asks vaguely for the best chart.
+8. Use list_chart_types and get_chart_data when the user asks for chart-ready data; server-side PNG chart generation is not exposed as a chat tool.
+9. Use the host clock context for any time-sensitive answer."""
 
 SUMMARY_SYSTEM_PROMPT = """You compress Alarm Viewer assistant conversations.
 Preserve all user goals, key facts, tool findings, decisions, generated files,
diff --git a/mcp_app/chart_widget/build.py b/mcp_app/chart_widget/build.py
new file mode 100644
index 0000000..eaf22e7
--- /dev/null
+++ b/mcp_app/chart_widget/build.py
@@ -0,0 +1,19 @@
+from __future__ import annotations
+
+from pathlib import Path
+
+ROOT = Path(__file__).resolve().parent
+source = ROOT / "src" / "chart_widget.ts"
+out = ROOT / "dist" / "chart.html"
+text = source.read_text(encoding="utf-8")
+out.parent.mkdir(parents=True, exist_ok=True)
+out.write_text(
+    """
+<div id="chart-root"></div>
+<script>
+""".lstrip()
+    + text
+    + "\n</script>\n",
+    encoding="utf-8",
+)
+print(f"Built {out}")
diff --git a/mcp_app/chart_widget/dist/chart.html b/mcp_app/chart_widget/dist/chart.html
new file mode 100644
index 0000000..d0ba2c8
--- /dev/null
+++ b/mcp_app/chart_widget/dist/chart.html
@@ -0,0 +1,161 @@
+<div id="chart-root"></div>
+<script>
+const root = document.getElementById("chart-root");
+const SUPPORTED = new Set(["bar", "horizontal_bar", "line", "donut", "pie", "heatmap", "histogram", "scatter"]);
+
+function css() {
+  return `
+    <style>
+      :root { color-scheme: light dark; }
+      body { margin: 0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
+      .wrap { padding: 14px; color: #111827; background: #ffffff; }
+      @media (prefers-color-scheme: dark) { .wrap { color: #f3f4f6; background: #111827; } .muted { color: #9ca3af; } }
+      .title { font-size: 18px; font-weight: 700; margin-bottom: 6px; }
+      .muted { color: #6b7280; font-size: 12px; }
+      .meta { display: flex; gap: 8px; flex-wrap: wrap; margin: 8px 0 12px; }
+      .pill { border: 1px solid #d1d5db; border-radius: 999px; padding: 3px 8px; font-size: 12px; }
+      .warning { background: #fef3c7; color: #92400e; border-radius: 8px; padding: 8px; margin: 8px 0; }
+      .empty { border: 1px dashed #d1d5db; border-radius: 12px; padding: 20px; text-align: center; }
+      .bars { display: grid; gap: 8px; }
+      .bar-row { display: grid; grid-template-columns: minmax(90px, 30%) 1fr 56px; gap: 8px; align-items: center; font-size: 12px; }
+      .bar-track { height: 12px; border-radius: 999px; background: #e5e7eb; overflow: hidden; }
+      .bar-fill { height: 100%; border-radius: 999px; background: linear-gradient(90deg, #2563eb, #22c55e); }
+      svg { width: 100%; height: 260px; overflow: visible; }
+      .fallback { border: 1px solid #d1d5db; border-radius: 12px; padding: 12px; }
+      table { width: 100%; border-collapse: collapse; font-size: 12px; } th, td { text-align: left; border-bottom: 1px solid #e5e7eb; padding: 6px; }
+    </style>
+  `;
+}
+
+function escapeHtml(value) {
+  return String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char] || char));
+}
+
+function numberValue(value) {
+  const number = Number(value);
+  return Number.isFinite(number) ? number : 0;
+}
+
+function points(payload) {
+  if (payload && Array.isArray(payload.series) && payload.series.length) return payload.series;
+  const labels = payload && Array.isArray(payload.labels) ? payload.labels : [];
+  const values = payload && Array.isArray(payload.values) ? payload.values : [];
+  return labels.map((label, index) => ({ label, value: numberValue(values[index]) }));
+}
+
+function maxValue(items) {
+  return Math.max(1, ...items.map((item) => numberValue(item.value ?? item.y)));
+}
+
+function renderBars(items) {
+  const max = maxValue(items);
+  return `<div class="bars">${items.map((item) => {
+    const value = numberValue(item.value);
+    const pct = Math.max(0, Math.min(100, (value / max) * 100));
+    return `<div class="bar-row"><div>${escapeHtml(item.label)}</div><div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div><div>${escapeHtml(value)}</div></div>`;
+  }).join("")}</div>`;
+}
+
+function renderLine(items) {
+  const max = maxValue(items);
+  const width = 640;
+  const height = 220;
+  const step = items.length > 1 ? width / (items.length - 1) : width;
+  const coords = items.map((item, index) => {
+    const yValue = numberValue(item.value ?? item.y);
+    const x = items.length > 1 ? index * step : width / 2;
+    const y = height - (yValue / max) * (height - 20) + 10;
+    return `${x},${y}`;
+  }).join(" ");
+  return `<svg viewBox="0 0 ${width} ${height}"><polyline points="${coords}" fill="none" stroke="#2563eb" stroke-width="3"/>${coords.split(" ").filter(Boolean).map((pair) => {
+    const [x, y] = pair.split(",");
+    return `<circle cx="${x}" cy="${y}" r="4" fill="#22c55e"/>`;
+  }).join("")}</svg>`;
+}
+
+function renderScatter(items) {
+  const width = 640;
+  const height = 220;
+  const xs = items.map((item) => numberValue(item.x));
+  const ys = items.map((item) => numberValue(item.y ?? item.value));
+  const maxX = Math.max(1, ...xs);
+  const maxY = Math.max(1, ...ys);
+  return `<svg viewBox="0 0 ${width} ${height}">${items.map((item) => {
+    const x = (numberValue(item.x) / maxX) * (width - 30) + 15;
+    const y = height - (numberValue(item.y ?? item.value) / maxY) * (height - 30) - 15;
+    return `<circle cx="${x}" cy="${y}" r="5" fill="#2563eb"><title>${escapeHtml(item.label)}</title></circle>`;
+  }).join("")}</svg>`;
+}
+
+function renderDonut(items) {
+  const total = items.reduce((sum, item) => sum + Math.max(0, numberValue(item.value)), 0) || 1;
+  let offset = 0;
+  const colors = ["#2563eb", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4"];
+  const rings = items.map((item, index) => {
+    const value = Math.max(0, numberValue(item.value));
+    const dash = (value / total) * 100;
+    const circle = `<circle r="70" cx="110" cy="110" fill="transparent" stroke="${colors[index % colors.length]}" stroke-width="34" stroke-dasharray="${dash} ${100 - dash}" stroke-dashoffset="${-offset}"/>`;
+    offset += dash;
+    return circle;
+  }).join("");
+  return `<svg viewBox="0 0 420 220"><g transform="rotate(-90 110 110)">${rings}</g><circle cx="110" cy="110" r="48" fill="white" opacity="0.9"/><foreignObject x="220" y="20" width="190" height="180"><div xmlns="http://www.w3.org/1999/xhtml">${renderLegend(items)}</div></foreignObject></svg>`;
+}
+
+function renderLegend(items) {
+  return items.map((item) => `<div class="muted">${escapeHtml(item.label)}: ${escapeHtml(item.value)}</div>`).join("");
+}
+
+function renderTable(items) {
+  return `<div class="fallback"><div class="muted">Fallback table for advanced chart kind.</div><table><thead><tr><th>Label</th><th>Value</th></tr></thead><tbody>${items.map((item) => `<tr><td>${escapeHtml(item.label ?? item.x)}</td><td>${escapeHtml(item.value ?? item.y)}</td></tr>`).join("")}</tbody></table></div>`;
+}
+
+function renderChart(payload) {
+  const kind = String(payload.chart_kind || "bar");
+  const items = points(payload);
+  if (payload.empty_state || items.length === 0) {
+    return `<div class="empty"><strong>${escapeHtml(payload.empty_state?.title || "No chart data")}</strong><div class="muted">${escapeHtml(payload.empty_state?.message || "No rows matched the selected chart and filters.")}</div></div>`;
+  }
+  if (!SUPPORTED.has(kind)) return renderTable(items);
+  if (kind === "line") return renderLine(items);
+  if (kind === "scatter") return renderScatter(items);
+  if (kind === "donut" || kind === "pie") return renderDonut(items);
+  return renderBars(items);
+}
+
+function render(payload) {
+  if (!root) return;
+  const fallback = window.openai?.toolOutput || window.openai?.toolInput || {};
+  const data = payload && typeof payload === "object" ? payload : fallback;
+  const quality = data.data_quality || {};
+  const filters = data.query_context?.filters || {};
+  const itemCount = points(data).length;
+  const warningHtml = Array.isArray(data.warnings) && data.warnings.length
+    ? data.warnings.map((warning) => `<div class="warning">${escapeHtml(warning)}</div>`).join("")
+    : "";
+  root.innerHTML = `${css()}<div class="wrap">
+    <div class="title">${escapeHtml(data.title || data.chart_id || "Chart")}</div>
+    <div class="meta">
+      <span class="pill">${escapeHtml(data.chart_kind || "chart")}</span>
+      <span class="pill">${escapeHtml(quality.returned_points ?? itemCount)} shown / ${escapeHtml(quality.total_points ?? itemCount)} points</span>
+      ${Object.keys(filters).length ? `<span class="pill">Filters: ${escapeHtml(JSON.stringify(filters))}</span>` : ""}
+    </div>
+    ${warningHtml}
+    ${renderChart(data)}
+  </div>`;
+}
+
+render();
+
+window.addEventListener("message", (event) => {
+  if (event.source !== window.parent) return;
+  const message = event.data;
+  if (!message || message.jsonrpc !== "2.0") return;
+  if (message.method !== "ui/notifications/tool-result") return;
+  render(message.params?.structuredContent);
+}, { passive: true });
+
+window.addEventListener("openai:set_globals", (event) => {
+  render(event.detail?.globals?.toolOutput || window.openai?.toolOutput);
+}, { passive: true });
+
+</script>
diff --git a/mcp_app/chart_widget/src/chart_widget.ts b/mcp_app/chart_widget/src/chart_widget.ts
new file mode 100644
index 0000000..9447831
--- /dev/null
+++ b/mcp_app/chart_widget/src/chart_widget.ts
@@ -0,0 +1,157 @@
+const root = document.getElementById("chart-root");
+const SUPPORTED = new Set(["bar", "horizontal_bar", "line", "donut", "pie", "heatmap", "histogram", "scatter"]);
+
+function css() {
+  return `
+    <style>
+      :root { color-scheme: light dark; }
+      body { margin: 0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
+      .wrap { padding: 14px; color: #111827; background: #ffffff; }
+      @media (prefers-color-scheme: dark) { .wrap { color: #f3f4f6; background: #111827; } .muted { color: #9ca3af; } }
+      .title { font-size: 18px; font-weight: 700; margin-bottom: 6px; }
+      .muted { color: #6b7280; font-size: 12px; }
+      .meta { display: flex; gap: 8px; flex-wrap: wrap; margin: 8px 0 12px; }
+      .pill { border: 1px solid #d1d5db; border-radius: 999px; padding: 3px 8px; font-size: 12px; }
+      .warning { background: #fef3c7; color: #92400e; border-radius: 8px; padding: 8px; margin: 8px 0; }
+      .empty { border: 1px dashed #d1d5db; border-radius: 12px; padding: 20px; text-align: center; }
+      .bars { display: grid; gap: 8px; }
+      .bar-row { display: grid; grid-template-columns: minmax(90px, 30%) 1fr 56px; gap: 8px; align-items: center; font-size: 12px; }
+      .bar-track { height: 12px; border-radius: 999px; background: #e5e7eb; overflow: hidden; }
+      .bar-fill { height: 100%; border-radius: 999px; background: linear-gradient(90deg, #2563eb, #22c55e); }
+      svg { width: 100%; height: 260px; overflow: visible; }
+      .fallback { border: 1px solid #d1d5db; border-radius: 12px; padding: 12px; }
+      table { width: 100%; border-collapse: collapse; font-size: 12px; } th, td { text-align: left; border-bottom: 1px solid #e5e7eb; padding: 6px; }
+    </style>
+  `;
+}
+
+function escapeHtml(value) {
+  return String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char] || char));
+}
+
+function numberValue(value) {
+  const number = Number(value);
+  return Number.isFinite(number) ? number : 0;
+}
+
+function points(payload) {
+  if (payload && Array.isArray(payload.series) && payload.series.length) return payload.series;
+  const labels = payload && Array.isArray(payload.labels) ? payload.labels : [];
+  const values = payload && Array.isArray(payload.values) ? payload.values : [];
+  return labels.map((label, index) => ({ label, value: numberValue(values[index]) }));
+}
+
+function maxValue(items) {
+  return Math.max(1, ...items.map((item) => numberValue(item.value ?? item.y)));
+}
+
+function renderBars(items) {
+  const max = maxValue(items);
+  return `<div class="bars">${items.map((item) => {
+    const value = numberValue(item.value);
+    const pct = Math.max(0, Math.min(100, (value / max) * 100));
+    return `<div class="bar-row"><div>${escapeHtml(item.label)}</div><div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div><div>${escapeHtml(value)}</div></div>`;
+  }).join("")}</div>`;
+}
+
+function renderLine(items) {
+  const max = maxValue(items);
+  const width = 640;
+  const height = 220;
+  const step = items.length > 1 ? width / (items.length - 1) : width;
+  const coords = items.map((item, index) => {
+    const yValue = numberValue(item.value ?? item.y);
+    const x = items.length > 1 ? index * step : width / 2;
+    const y = height - (yValue / max) * (height - 20) + 10;
+    return `${x},${y}`;
+  }).join(" ");
+  return `<svg viewBox="0 0 ${width} ${height}"><polyline points="${coords}" fill="none" stroke="#2563eb" stroke-width="3"/>${coords.split(" ").filter(Boolean).map((pair) => {
+    const [x, y] = pair.split(",");
+    return `<circle cx="${x}" cy="${y}" r="4" fill="#22c55e"/>`;
+  }).join("")}</svg>`;
+}
+
+function renderScatter(items) {
+  const width = 640;
+  const height = 220;
+  const xs = items.map((item) => numberValue(item.x));
+  const ys = items.map((item) => numberValue(item.y ?? item.value));
+  const maxX = Math.max(1, ...xs);
+  const maxY = Math.max(1, ...ys);
+  return `<svg viewBox="0 0 ${width} ${height}">${items.map((item) => {
+    const x = (numberValue(item.x) / maxX) * (width - 30) + 15;
+    const y = height - (numberValue(item.y ?? item.value) / maxY) * (height - 30) - 15;
+    return `<circle cx="${x}" cy="${y}" r="5" fill="#2563eb"><title>${escapeHtml(item.label)}</title></circle>`;
+  }).join("")}</svg>`;
+}
+
+function renderDonut(items) {
+  const total = items.reduce((sum, item) => sum + Math.max(0, numberValue(item.value)), 0) || 1;
+  let offset = 0;
+  const colors = ["#2563eb", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4"];
+  const rings = items.map((item, index) => {
+    const value = Math.max(0, numberValue(item.value));
+    const dash = (value / total) * 100;
+    const circle = `<circle r="70" cx="110" cy="110" fill="transparent" stroke="${colors[index % colors.length]}" stroke-width="34" stroke-dasharray="${dash} ${100 - dash}" stroke-dashoffset="${-offset}"/>`;
+    offset += dash;
+    return circle;
+  }).join("");
+  return `<svg viewBox="0 0 420 220"><g transform="rotate(-90 110 110)">${rings}</g><circle cx="110" cy="110" r="48" fill="white" opacity="0.9"/><foreignObject x="220" y="20" width="190" height="180"><div xmlns="http://www.w3.org/1999/xhtml">${renderLegend(items)}</div></foreignObject></svg>`;
+}
+
+function renderLegend(items) {
+  return items.map((item) => `<div class="muted">${escapeHtml(item.label)}: ${escapeHtml(item.value)}</div>`).join("");
+}
+
+function renderTable(items) {
+  return `<div class="fallback"><div class="muted">Fallback table for advanced chart kind.</div><table><thead><tr><th>Label</th><th>Value</th></tr></thead><tbody>${items.map((item) => `<tr><td>${escapeHtml(item.label ?? item.x)}</td><td>${escapeHtml(item.value ?? item.y)}</td></tr>`).join("")}</tbody></table></div>`;
+}
+
+function renderChart(payload) {
+  const kind = String(payload.chart_kind || "bar");
+  const items = points(payload);
+  if (payload.empty_state || items.length === 0) {
+    return `<div class="empty"><strong>${escapeHtml(payload.empty_state?.title || "No chart data")}</strong><div class="muted">${escapeHtml(payload.empty_state?.message || "No rows matched the selected chart and filters.")}</div></div>`;
+  }
+  if (!SUPPORTED.has(kind)) return renderTable(items);
+  if (kind === "line") return renderLine(items);
+  if (kind === "scatter") return renderScatter(items);
+  if (kind === "donut" || kind === "pie") return renderDonut(items);
+  return renderBars(items);
+}
+
+function render(payload) {
+  if (!root) return;
+  const fallback = window.openai?.toolOutput || window.openai?.toolInput || {};
+  const data = payload && typeof payload === "object" ? payload : fallback;
+  const quality = data.data_quality || {};
+  const filters = data.query_context?.filters || {};
+  const itemCount = points(data).length;
+  const warningHtml = Array.isArray(data.warnings) && data.warnings.length
+    ? data.warnings.map((warning) => `<div class="warning">${escapeHtml(warning)}</div>`).join("")
+    : "";
+  root.innerHTML = `${css()}<div class="wrap">
+    <div class="title">${escapeHtml(data.title || data.chart_id || "Chart")}</div>
+    <div class="meta">
+      <span class="pill">${escapeHtml(data.chart_kind || "chart")}</span>
+      <span class="pill">${escapeHtml(quality.returned_points ?? itemCount)} shown / ${escapeHtml(quality.total_points ?? itemCount)} points</span>
+      ${Object.keys(filters).length ? `<span class="pill">Filters: ${escapeHtml(JSON.stringify(filters))}</span>` : ""}
+    </div>
+    ${warningHtml}
+    ${renderChart(data)}
+  </div>`;
+}
+
+render();
+
+window.addEventListener("message", (event) => {
+  if (event.source !== window.parent) return;
+  const message = event.data;
+  if (!message || message.jsonrpc !== "2.0") return;
+  if (message.method !== "ui/notifications/tool-result") return;
+  render(message.params?.structuredContent);
+}, { passive: true });
+
+window.addEventListener("openai:set_globals", (event) => {
+  render(event.detail?.globals?.toolOutput || window.openai?.toolOutput);
+}, { passive: true });

exec
/bin/zsh -lc "sed -n '1,160p' web/routers/mcp.py && sed -n '1,140p' llm_tools/mcp_server.py" in /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
 succeeded in 0ms:
"""HTTP MCP endpoint for ChatGPT connectors."""

from __future__ import annotations

import os
import secrets
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response

try:
    from alarm_app.data import state
    from alarm_app.llm_tools.mcp_server import AlarmViewerMcpServer
except ImportError:
    from data import state  # type: ignore[no-redef]
    from llm_tools.mcp_server import AlarmViewerMcpServer  # type: ignore[no-redef]


router = APIRouter(tags=["mcp"])


def _expected_token() -> str:
    env_token = os.environ.get("ALARM_MCP_TOKEN", "").strip()
    if env_token:
        return env_token
    saved = state.load_state() or {}
    return str(saved.get("chatgpt_mcp_token") or "").strip()


def _supplied_token(request: Request, query_token: str | None) -> str:
    if query_token:
        return query_token.strip()
    auth = request.headers.get("authorization", "")
    scheme, _, value = auth.partition(" ")
    if scheme.lower() == "bearer":
        return value.strip()
    return ""


def _require_token(request: Request, query_token: str | None) -> None:
    expected = _expected_token()
    if not expected:
        raise HTTPException(status_code=503, detail="ChatGPT MCP connector token is not configured")
    supplied = _supplied_token(request, query_token)
    if not supplied or not secrets.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.get("/mcp")
@router.get("/mcp/")
def mcp_endpoint_probe(request: Request, token: str | None = None):
    _require_token(request, token)
    return {
        "name": "alarm-viewer-local-data",
        "transport": "streamable-http",
        "endpoint": "/mcp",
        "methods": ["POST"],
    }


@router.head("/mcp")
@router.head("/mcp/")
def mcp_endpoint_head(request: Request, token: str | None = None):
    _require_token(request, token)
    return Response(status_code=200)


@router.post("/mcp")
@router.post("/mcp/")
def handle_mcp_request(body: dict[str, Any], request: Request, token: str | None = None):
    _require_token(request, token)
    if body.get("jsonrpc") != "2.0":
        raise HTTPException(status_code=400, detail="MCP requests must use JSON-RPC 2.0")

    result = AlarmViewerMcpServer().handle(body)
    if result is None:
        return Response(status_code=202)
    return result
"""Minimal stdio MCP server for local Alarm Viewer data."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from .openrouter_agent import _model_safe_tool_result
from .service import CHART_WIDGET_MIME_TYPE, CHART_WIDGET_URI, LocalDataService
from .tools import dispatch_tool, tool_definitions_for_mcp

SERVER_INFO = {"name": "alarm-viewer-local-data", "version": "0.1.0"}

_WIDGET_NAME = "chart-widget"
_WIDGET_TITLE = "Alarm Chart Widget"
_WIDGET_HTML_PATH = Path(__file__).resolve().parents[1] / "mcp_app" / "chart_widget" / "dist" / "chart.html"


def chart_widget_resource() -> dict[str, Any]:
    return {
        "uri": CHART_WIDGET_URI,
        "name": _WIDGET_NAME,
        "title": _WIDGET_TITLE,
        "mimeType": CHART_WIDGET_MIME_TYPE,
    }


def chart_widget_html() -> str:
    if not _WIDGET_HTML_PATH.exists():
        raise FileNotFoundError(f"chart widget build artifact missing: {_WIDGET_HTML_PATH}")
    return _WIDGET_HTML_PATH.read_text(encoding="utf-8")


def read_chart_widget_resource(uri: str) -> dict[str, Any] | None:
    if uri != CHART_WIDGET_URI:
        return None
    return {
        "uri": CHART_WIDGET_URI,
        "mimeType": CHART_WIDGET_MIME_TYPE,
        "text": chart_widget_html(),
        "_meta": {"ui": {"prefersBorder": True}},
    }



def _response(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


class AlarmViewerMcpServer:
    def __init__(self, service: LocalDataService | None = None):
        self.service = service or LocalDataService()

    def handle(self, request: dict[str, Any]) -> dict[str, Any] | None:
        method = request.get("method")
        request_id = request.get("id")
        raw_params = request.get("params")
        params = raw_params if isinstance(raw_params, dict) else ({} if raw_params is None else None)

        if method == "initialize":
            return _response(request_id, {
                "protocolVersion": "2024-11-05",
                "serverInfo": SERVER_INFO,
                "capabilities": {"tools": {}, "resources": {}},
            })

        if method == "notifications/initialized":
            return None

        if method == "tools/list":
            return _response(request_id, {"tools": tool_definitions_for_mcp()})

        if method == "resources/list":
            return _response(request_id, {"resources": [chart_widget_resource()]})

        if method == "resources/read":
            if params is None:
                return _error(request_id, -32602, "resources/read params must be an object")
            uri = str(params.get("uri") or "")
            try:
                resource = read_chart_widget_resource(uri)
            except FileNotFoundError as exc:
                return _error(request_id, -32002, str(exc))
            if resource is None:
                return _error(request_id, -32002, f"resource not found: {uri}")
            return _response(request_id, {"contents": [resource]})

        if method == "tools/call":
            if params is None:
                return _error(request_id, -32602, "tools/call params must be an object")
            name = str(params.get("name") or "")
            arguments = params.get("arguments") if "arguments" in params else {}
            result = dispatch_tool(self.service, name, arguments)
            safe_result = _model_safe_tool_result(result)
            content = [
                {
                    "type": "text",
                    "text": json.dumps(safe_result, default=str, ensure_ascii=False),
                }
            ]
            response_payload = {
                "content": content,
                "structuredContent": safe_result,
                "isError": isinstance(result, dict) and "error" in result,
            }
            if isinstance(result, dict) and isinstance(result.get("_meta"), dict):
                response_payload["_meta"] = result["_meta"]
            return _response(request_id, response_payload)

        return _error(request_id, -32601, f"method not found: {method}")


def main() -> None:
    server = AlarmViewerMcpServer()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = server.handle(request)
        except Exception as exc:
            response = _error(None, -32603, str(exc))
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()

exec
/bin/zsh -lc 'pytest -q tests/test_llm_tools.py::test_chart_registry_drives_data_schema_and_discovery_tool tests/test_llm_tools.py::test_render_chart_widget_returns_apps_sdk_metadata tests/test_llm_tools.py::test_mcp_server_exposes_chart_widget_resource_and_render_meta tests/test_e2e_backend.py::TestMcpHttpEndpoint::test_mcp_resources_read_returns_chart_widget_html' in /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
 exited 4 in 474ms:
ERROR: found no collectors for /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604/tests/test_llm_tools.py::test_chart_registry_drives_data_schema_and_discovery_tool

ERROR: found no collectors for /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604/tests/test_llm_tools.py::test_render_chart_widget_returns_apps_sdk_metadata

ERROR: found no collectors for /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604/tests/test_llm_tools.py::test_mcp_server_exposes_chart_widget_resource_and_render_meta

ERROR: found no collectors for /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604/tests/test_e2e_backend.py::TestMcpHttpEndpoint::test_mcp_resources_read_returns_chart_widget_html


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
__________________ ERROR collecting tests/test_e2e_backend.py __________________
ImportError while importing test module '/Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604/tests/test_e2e_backend.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/opt/homebrew/Cellar/python@3.14/3.14.0/Frameworks/Python.framework/Versions/3.14/lib/python3.14/importlib/__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/test_e2e_backend.py:12: in <module>
    from fastapi.testclient import TestClient
E   ModuleNotFoundError: No module named 'fastapi'
=========================== short test summary info ============================
ERROR tests/test_llm_tools.py
ERROR tests/test_e2e_backend.py
2 errors in 0.14s

exec
/bin/zsh -lc 'ls -d .venv venv 2>/dev/null || true; .venv/bin/python -V 2>/dev/null || true' in /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
 succeeded in 0ms:
.venv
Python 3.13.3

exec
/bin/zsh -lc '.venv/bin/pytest -q tests/test_llm_tools.py::test_chart_registry_drives_data_schema_and_discovery_tool tests/test_llm_tools.py::test_render_chart_widget_returns_apps_sdk_metadata tests/test_llm_tools.py::test_mcp_server_exposes_chart_widget_resource_and_render_meta tests/test_e2e_backend.py::TestMcpHttpEndpoint::test_mcp_resources_read_returns_chart_widget_html' in /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
 exited 4 in 2600ms:

no tests ran in 1.25s
ERROR: not found: /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604/tests/test_e2e_backend.py::TestMcpHttpEndpoint::test_mcp_resources_read_returns_chart_widget_html
(no match in any of [<Module test_e2e_backend.py>])


exec
/bin/zsh -lc "grep -n \"resources_read\\|class TestMcp\\|chart_registry\\|render_chart_widget\" tests/test_e2e_backend.py tests/test_llm_tools.py | head -50" in /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
 succeeded in 0ms:
tests/test_e2e_backend.py:121:class TestMcpConnectorE2E:
tests/test_e2e_backend.py:284:        assert tools["render_chart_widget"]["_meta"] == {
tests/test_e2e_backend.py:354:    def test_mcp_resources_read_returns_chart_widget_html(self, client, monkeypatch):
tests/test_e2e_backend.py:373:    def test_mcp_render_chart_widget_returns_structured_data_and_ui_metadata(self, client, monkeypatch):
tests/test_e2e_backend.py:381:                "name": "render_chart_widget",
tests/test_llm_tools.py:742:    assert "render_chart_widget" in mcp_names
tests/test_llm_tools.py:743:    assert "render_chart_widget" not in openrouter_names
tests/test_llm_tools.py:752:    assert openrouter_names == mcp_names - {"render_chart_widget"}
tests/test_llm_tools.py:794:def test_chart_registry_drives_data_schema_and_discovery_tool():
tests/test_llm_tools.py:816:def test_chart_registry_contains_all_documented_chart_kinds():
tests/test_llm_tools.py:3073:def test_render_chart_widget_returns_apps_sdk_metadata():
tests/test_llm_tools.py:3090:    result = service.render_chart_widget(**payload)
tests/test_llm_tools.py:3102:        def render_chart_widget(self, **kwargs):
tests/test_llm_tools.py:3146:            "name": "render_chart_widget",

exec
/bin/zsh -lc '.venv/bin/pytest -q tests/test_llm_tools.py::test_chart_registry_drives_data_schema_and_discovery_tool tests/test_llm_tools.py::test_render_chart_widget_returns_apps_sdk_metadata tests/test_llm_tools.py::test_mcp_server_exposes_chart_widget_resource_and_render_meta tests/test_e2e_backend.py::TestMcpConnectorE2E::test_mcp_resources_read_returns_chart_widget_html' in /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
 succeeded in 2450ms:
....                                                                     [100%]
4 passed in 1.56s

exec
/bin/zsh -lc "sed -n '1,220p' .scratch/prds/chatgpt-chart-widget-ui.md; sed -n '1,220p' .scratch/issues/chatgpt-chart-widget-ui/001-donut-render-and-legend.md" in /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
 succeeded in 0ms:
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
---
title: ChatGPT chart widget — donut readability, legend, empty state
label: ready-for-agent
type: AFK
priority: P1
blocked_by: None
parent: ../../prds/chatgpt-chart-widget-ui.md
---

# 001 — Donut readability, legend, and empty state polish

## Problems addressed

The first end-to-end render of the Apps SDK chart widget in ChatGPT exposed real UX problems in `mcp_app/chart_widget/src/chart_widget.ts` even though the data contract and tool flow are working.

1. **Donut wedges are visually indistinguishable when there are many small slices.** For `Network Type Share` (7 categories) and similar pie/donut kinds, slices below ~1% collapse into a thin sliver or disappear entirely, so `CS: 5` and `5G: 53,364` look the same as a much larger value.
2. **Legend uses the same color stack as the wedges, but the legend sits as a plain stacked text block to the right of the donut** with no visual association between each color and its label. Users cannot tell which slice is which without reading numbers.
3. **Legend values are right-aligned and unaligned with the wedge ring**, so the chart looks broken at a glance.
4. **`Alarm Severity Share` renders as `pie` (donut) but the data is empty.** The widget shows the empty-state panel _inside the same card_ but the surrounding title/pills still imply a populated chart. There is no per-chart "no data" affordance distinct from the empty state, and the legend does not appear.
5. **Title pills read `0 shown / 0 points`** for empty charts, which is technically correct but visually confusing; users expect to see the empty-state message where the chart would be, not pills that look like real numbers.

## Acceptance criteria

- [ ] Donut/pie rendering in `renderDonut` produces wedges large enough to read for slices down to 0.5% of total: minimum wedge arc ~3° and a labeled `Other (<1%)` bucket that groups all sub-1% slices.
- [ ] Legend is rendered as a two-column key next to the donut: color swatch + label + value, aligned to the same baseline; hover on a wedge highlights its legend row.
- [ ] Title pills are suppressed on empty charts; the empty-state message is the primary content and is centered in the card body.
- [ ] When `rendered_count == 0`, the pill row is replaced by a single subtle "no data" hint line, not `0 shown / 0 points`.
- [ ] Build artifact `mcp_app/chart_widget/dist/chart.html` is rebuilt by `python mcp_app/chart_widget/build.py` and is browser-valid.
- [ ] Updated `tests/test_llm_tools.py::test_chart_widget_package_builds` still passes when run in an isolated `tmp_path` copy (no repo mutation).
- [ ] No `mcp_app/chart_widget/src/chart_widget.ts` regression: the `ui/notifications/tool-result` parent-message handler and `window.openai` fallback still both work.

## Constraints

- Edit only `mcp_app/chart_widget/src/chart_widget.ts` and `mcp_app/chart_widget/dist/chart.html` (regenerated by `build.py`).
- Do not change `mcp_app/chart_widget/build.py`; it stays a trivial embed-script wrapper.
- Do not change tool contracts in `llm_tools/service.py` or `llm_tools/tools.py`; the widget receives the same `structuredContent` shape.
- Do not add a charting library. Keep the widget self-contained, browser-valid JavaScript with no external network calls.
- Treat all `structuredContent` as untrusted: escape labels, titles, and pill text.
- The architecture rule: widget code lives under `mcp_app/`, separate from `ui/`/`web/`.

## Context

- File: `mcp_app/chart_widget/src/chart_widget.ts`
  - `renderDonut(items)` currently emits a 6-color ring plus a stacked `<div class="muted">` legend. Add a `palette` argument, bucket sub-1% values, and switch to a swatch-led legend list.
  - `render(payload)` builds the pills block. Skip the count pill when `data.data_quality?.returned_points === 0 && data.data_quality?.total_points === 0` and show a "no data" hint instead.
  - `points(payload)` already handles the empty case; the donut path must respect it.
- Screenshot evidence from the first ChatGPT run: `alarm_severity_share` showed `0 shown / 0 points` plus the empty-state panel simultaneously; `network_type_share` donut had `CS: 5` and `Others: 52` indistinguishable as wedge-only colors.

## Verification

After the change:

1. `python mcp_app/chart_widget/build.py` rebuilds the dist HTML without errors.
2. `python -m pytest tests/test_llm_tools.py -k chart_widget_package_builds` passes (it copies the widget into `tmp_path` before building).
3. Open `mcp_app/chart_widget/dist/chart.html` in a browser, dispatch a synthetic `message` event with `method: "ui/notifications/tool-result"` and `params.structuredContent` for a 4- and 7-category donut; confirm wedges, legend, and empty state render correctly.

## Stop condition

Done when all acceptance criteria pass, the dist HTML is regenerated, and the targeted test still passes. Do not refactor widget helpers beyond the affected renderers.

---

## GPT-5.5 Agent Prompt

```
## Outcome

Polish the donut/pie renderer in
/Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604/mcp_app/chart_widget/src/chart_widget.ts
so that sub-1% slices remain visible, the legend is a proper swatch-led
key aligned with the ring, and empty charts show a single "no data"
affordance instead of the misleading 0-shown pills. Rebuild the dist HTML.

## Success criteria

1. Donut/pie rendering produces wedges readable down to 0.5% of total: a
   minimum wedge arc of ~3°, and all sub-1% slices are merged into one
   "Other (<1%)" bucket with the sum of their values.
2. The legend next to the donut is a vertical list of rows; each row has
   a color swatch, the label, and the value, all baseline-aligned.
   Hovering a wedge highlights its legend row.
3. When data_quality.returned_points == 0 and data_quality.total_points == 0,
   the chart card suppresses the count pills and centers a single "no
   data" message in the card body; the legend does not render.
4. The build artifact
   mcp_app/chart_widget/dist/chart.html is regenerated by
   `python mcp_app/chart_widget/build.py` and remains browser-valid
   (no TypeScript syntax, no module imports).
5. python -m pytest tests/test_llm_tools.py -k chart_widget_package_builds
   passes (it copies the widget into tmp_path before building, so it
   must not be broken by the changes).
6. The ui/notifications/tool-result parent-message handler and the
   window.openai fallback both still receive chart payloads.

## Constraints

- Edit only mcp_app/chart_widget/src/chart_widget.ts and
  mcp_app/chart_widget/dist/chart.html (regenerated by build.py).
- Do not modify mcp_app/chart_widget/build.py.
- Do not modify llm_tools/service.py, llm_tools/tools.py, or any test
  files; the widget still receives the existing structuredContent shape.
- Do not add a charting library. Keep the widget self-contained
  browser-valid JavaScript with no external network calls.
- Treat all structuredContent as untrusted: escape labels, titles, and
  pill text before injecting as HTML.
- Architecture rule: widget code lives under mcp_app/, separate from
  ui/, web/, and core/. Do not import from those layers.

## Context

File: mcp_app/chart_widget/src/chart_widget.ts
- renderDonut(items) currently emits a 6-color ring plus a stacked
  <div class="muted"> legend. Add a palette argument (cycled for slices
  > 1%), bucket sub-1% values, and switch to a swatch-led legend list.
- render(payload) builds the pill block. Skip the count pill when
  data.data_quality?.returned_points === 0 && data.data_quality?.total_points
  === 0 and show a centered "no data" hint instead.
- The existing message handler window.addEventListener("message", ...) for
  ui/notifications/tool-result and the window.addEventListener("openai:set_globals", ...)
  fallback must keep working unchanged.

Screenshot evidence from the first ChatGPT run:
- alarm_severity_share showed "0 shown / 0 points" pills plus the empty
  state panel simultaneously.
- network_type_share donut had CS: 5 and Others: 52 indistinguishable as
  wedge-only colors; legend was a stacked text block with no swatches.

## Verification

1. python mcp_app/chart_widget/build.py runs without errors and writes a
   new dist/chart.html.
2. python -m pytest tests/test_llm_tools.py -k chart_widget_package_builds
   passes.
3. Open dist/chart.html in a browser, dispatch a synthetic message event
   with method "ui/notifications/tool-result" and params.structuredContent
   for a 4-category donut, a 7-category donut, and an empty donut; confirm
   the visual results match the success criteria.

## Stop condition

Done when all success criteria pass and the targeted test still passes.
Do not refactor widget helpers beyond the affected renderers.
```

exec
/bin/zsh -lc "git show ce401c4d262c9362d3110036b9ea8f821d8a4719:llm_tools/service.py | grep -n \"def generate_graph\\|def _alarm_graph_series\\|_alarm_rows_for_sites\" | head -30 && git show ce401c4d262c9362d3110036b9ea8f821d8a4719:llm_tools/service.py | sed -n '1430,1515p'" in /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
 succeeded in 0ms:
1405:        alarm_df = self._alarm_rows_for_sites(
1440:    def generate_graph(self, **kwargs) -> dict[str, Any]:
1445:            alarm_df = self._alarm_rows_for_sites(
1848:        alarm_df = self._alarm_rows_for_sites(
2003:    def _alarm_rows_for_sites(
2028:        return self._alarm_rows_for_sites(site_keys, date_from=date_from, date_to=date_to)
2084:    def _alarm_graph_series(alarm_df: pd.DataFrame, graph_type: str) -> tuple[list[str], list[float]]:
            "site_code": site_code,
            "alarm_total": len(alarm_df),
            "alarm_stats": self._site_alarm_summary(alarm_df),
            "alarm_rows": _df_records(alarm_df.head(_limit(kwargs.get("alarm_preview_limit"), default=50))),
            "bdt_total": int(bdt_payload.get("total") or len(bdt_rows)) if isinstance(bdt_payload, dict) else len(bdt_rows),
            "bdt_rows": _jsonable(bdt_rows[:_limit(kwargs.get("bdt_preview_limit"), default=50)]),
            "bdt_details": _jsonable(bdt_details),
            "export_path": str(export_path),
        }

    def generate_graph(self, **kwargs) -> dict[str, Any]:
        graph_type = str(kwargs.get("graph_type") or "alarm_category_counts").strip()
        site_code = normalize_site_key(kwargs.get("site_code") or kwargs.get("site_text") or "")
        title = str(kwargs.get("title") or graph_type.replace("_", " ").title())
        if graph_type.startswith("alarm_"):
            alarm_df = self._alarm_rows_for_sites(
                {site_code} if site_code else set(self._alarm_reference_df()["site_id"].map(normalize_site_key).dropna()),
                date_from=_date_value(kwargs.get("date_from")),
                date_to=_date_value(kwargs.get("date_to")),
            ) if site_code else self._with_alarm_source(lambda: alarm_store.query_alarms(alarm_store.AlarmQuery(
                date_from=_date_value(kwargs.get("date_from")),
                date_to=_date_value(kwargs.get("date_to")),
                limit=None,
                offset=0,
            )))
            labels, values = self._alarm_graph_series(alarm_df, graph_type)
        elif graph_type in {"bdt_verdict_counts", "bdt_duration_trend"}:
            rows = self._query_all_bdt_rows(
                site_code=site_code,
                date_from=_date_value(kwargs.get("date_from")),
                date_to=_date_value(kwargs.get("date_to")),
            )
            labels, values = self._bdt_graph_series(rows, graph_type)
        else:
            return {"error": f"unsupported graph_type: {graph_type}"}

        path = _safe_export_path(self.export_dir / "charts", f"{title}_{site_code or 'all'}", "png")
        self._draw_bar_chart(path, title, labels, values)
        return {
            "path": str(path),
            "graph_type": graph_type,
            "site_code": site_code,
            "points": len(values),
            "labels": labels,
            "values": values,
        }

    def get_computed_report(self, **kwargs) -> dict[str, Any]:
        report_type = str(kwargs.get("report_type") or "").strip().lower()
        if report_type.startswith("chart:"):
            report_type = report_type[len("chart:"):].strip()

        include_raw_json = bool(kwargs.get("include_raw_json", False))
        limit = _mcp_limit(kwargs.get("limit"))
        offset = _mcp_offset(kwargs.get("offset"))
        site_code = str(kwargs.get("site_code") or kwargs.get("site_id") or "").strip()
        site_text = str(kwargs.get("site_text") or "").strip()
        date_from = _date_value(kwargs.get("date_from"))
        date_to = _date_value(kwargs.get("date_to"))
        category = str(kwargs.get("category") or "All")
        vendor = str(kwargs.get("vendor") or "All")
        network_type = str(kwargs.get("network_type") or "All")
        export_week = str(kwargs.get("export_week") or "").strip()
        week_label = str(kwargs.get("week_label") or "").strip()
        source_file_id = str(kwargs.get("source_file_id") or "").strip()
        section = str(kwargs.get("section") or "").strip()

        def _missing_inputs_error(required_fields: list[str], action: str) -> dict[str, Any]:
            return {
                "error": f"missing required fields: {', '.join(required_fields)}",
                "required": required_fields,
                "action": action,
                "report_type": report_type,
            }

        def _computed_error_payload(error: Any, *, chart: bool = False) -> dict[str, Any]:
            payload: dict[str, Any] = {
                "report_type": report_type,
                "rows": [],
                "returned": 0,
                "limit": limit,
                "offset": offset,
                "has_more": False,
                "total": 0,
                "error": _sanitize_mcp_value(str(error)),
            }

exec
/bin/zsh -lc "sed -n '3100,3220p' tests/test_llm_tools.py; sed -n '250,400p' tests/test_e2e_backend.py" in /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
 succeeded in 0ms:
def test_mcp_server_exposes_chart_widget_resource_and_render_meta():
    class _Service:
        def render_chart_widget(self, **kwargs):
            return {
                **kwargs,
                "_meta": {
                    "openai/outputTemplate": "ui://widget/chart.html",
                    "ui": {"resourceUri": "ui://widget/chart.html"},
                },
            }

    server = AlarmViewerMcpServer(service=_Service())

    initialized = server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert initialized["result"]["capabilities"]["resources"] == {}

    listed = server.handle({"jsonrpc": "2.0", "id": 2, "method": "resources/list", "params": {}})
    resources = listed["result"]["resources"]
    assert resources == [
        {
            "uri": "ui://widget/chart.html",
            "name": "chart-widget",
            "title": "Alarm Chart Widget",
            "mimeType": "text/html;profile=mcp-app",
        }
    ]

    read = server.handle({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "resources/read",
        "params": {"uri": "ui://widget/chart.html"},
    })
    content = read["result"]["contents"][0]
    assert content["uri"] == "ui://widget/chart.html"
    assert content["mimeType"] == "text/html;profile=mcp-app"
    assert "window.openai" in content["text"]
    assert "ui/notifications/tool-result" in content["text"]
    assert 'id="chart-root"' in content["text"]
    assert content["_meta"] == {"ui": {"prefersBorder": True}}

    called = server.handle({
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "render_chart_widget",
            "arguments": {
                "chart_id": "alarm_category_counts",
                "chart_kind": "bar",
                "title": "Alarm Category Counts",
                "labels": ["Power"],
                "values": [1],
                "series": [{"label": "Power", "value": 1}],
            },
        },
    })
    assert called["result"]["_meta"] == {
        "openai/outputTemplate": "ui://widget/chart.html",
        "ui": {"resourceUri": "ui://widget/chart.html"},
    }
    assert called["result"]["structuredContent"]["chart_id"] == "alarm_category_counts"


def test_mcp_server_returns_resource_error_when_widget_build_missing(tmp_path, monkeypatch):
    missing_widget = tmp_path / "missing" / "chart.html"
    monkeypatch.setattr("alarm_app.llm_tools.mcp_server._WIDGET_HTML_PATH", missing_widget)
    server = AlarmViewerMcpServer(service=LocalDataService())

    response = server.handle({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "resources/read",
        "params": {"uri": "ui://widget/chart.html"},
    })

    assert response["error"]["code"] == -32002
    assert "chart widget build artifact missing" in response["error"]["message"]
    assert "chart_widget.ts" not in response["error"]["message"]


def test_chart_widget_package_builds(tmp_path):
    package_path = Path(__file__).resolve().parents[1] / "mcp_app" / "chart_widget" / "package.json"
    widget_dir = package_path.parent
    temp_widget_dir = tmp_path / "chart_widget"
    dist_path = temp_widget_dir / "dist" / "chart.html"

    assert package_path.exists()
    shutil.copytree(widget_dir, temp_widget_dir)
    dist_path.unlink(missing_ok=True)
    subprocess.run([sys.executable, "build.py"], cwd=temp_widget_dir, check=True)

    html = dist_path.read_text(encoding="utf-8")
    assert 'id="chart-root"' in html
    assert "ui/notifications/tool-result" in html
    assert "type ChartPoint" not in html
    assert "declare global" not in html
    assert " as HTMLElement" not in html


def test_generate_graph_writes_png_from_alarm_data(tmp_path, monkeypatch):
    service = LocalDataService(export_dir=tmp_path / "exports")
    alarm_df = pd.DataFrame([
        {"site_id": "AAA001", "alarm_category": "Power", "occurred_on": "2026-04-01"},
        {"site_id": "AAA001", "alarm_category": "Down", "occurred_on": "2026-04-02"},
        {"site_id": "AAA001", "alarm_category": "Power", "occurred_on": "2026-04-03"},
    ])
    monkeypatch.setattr(service, "_alarm_rows_for_sites", lambda site_keys, date_from=None, date_to=None, **kwargs: alarm_df)

    result = service.generate_graph(graph_type="alarm_category_counts", site_code="AAA001")

    assert result["points"] == 2
    assert result["chart_kind"] == "bar"
    assert result["mime_type"] == "image/png"
    assert result["width"] > 0
    assert result["height"] > 0
    assert base64.b64decode(result["image_base64"]).startswith(b"\x89PNG")
    assert result["series"] == [{"label": "Power", "value": 2.0}, {"label": "Down", "value": 1.0}]
    assert Path(result["path"]).exists()
    assert Path(result["path"]).suffix == ".png"

        assert r.status_code == 200

    def test_mcp_initialize_over_http(self, client, monkeypatch):
        monkeypatch.setenv("ALARM_MCP_TOKEN", "secret-token")

        r = client.post("/mcp?token=secret-token", json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {},
        })

        assert r.status_code == 200
        payload = r.json()
        assert payload["jsonrpc"] == "2.0"
        assert payload["id"] == 1
        assert payload["result"]["serverInfo"]["name"] == "alarm-viewer-local-data"
        assert payload["result"]["capabilities"] == {"tools": {}, "resources": {}}

    def test_mcp_tools_list_includes_chatgpt_safety_annotations(self, client, monkeypatch):
        monkeypatch.setenv("ALARM_MCP_TOKEN", "secret-token")

        r = client.post("/mcp?token=secret-token", json={
            "jsonrpc": "2.0",
            "id": "tools",
            "method": "tools/list",
            "params": {},
        })

        assert r.status_code == 200
        tools = {tool["name"]: tool for tool in r.json()["result"]["tools"]}
        assert "generate_graph" not in tools
        assert "list_chart_types" in tools
        assert "get_chart_data" in tools
        assert tools["render_chart_widget"]["_meta"] == {
            "openai/outputTemplate": "ui://widget/chart.html",
            "ui": {"resourceUri": "ui://widget/chart.html"},
            "openai/toolInvocation/invoking": "Rendering chart...",
            "openai/toolInvocation/invoked": "Chart ready.",
        }
        assert tools["query_alarms"]["annotations"] == {"readOnlyHint": True}
        assert tools["export_report"]["annotations"] == {
            "readOnlyHint": False,
            "openWorldHint": False,
            "destructiveHint": False,
        }

    def test_mcp_notification_returns_empty_202(self, client, monkeypatch):
        monkeypatch.setenv("ALARM_MCP_TOKEN", "secret-token")

        r = client.post("/mcp?token=secret-token", json={
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        })

        assert r.status_code == 202
        assert r.content == b""

    def test_mcp_invalid_json_rpc_returns_400(self, client, monkeypatch):
        monkeypatch.setenv("ALARM_MCP_TOKEN", "secret-token")

        r = client.post("/mcp?token=secret-token", json={"method": "tools/list"})

        assert r.status_code == 400
        assert r.json()["detail"] == "MCP requests must use JSON-RPC 2.0"

    def test_mcp_generate_graph_is_not_public_over_http(self, client, monkeypatch):
        monkeypatch.setenv("ALARM_MCP_TOKEN", "secret-token")

        r = client.post("/mcp?token=secret-token", json={
            "jsonrpc": "2.0",
            "id": "chart",
            "method": "tools/call",
            "params": {"name": "generate_graph", "arguments": {"graph_type": "alarm_category_counts"}},
        })

        assert r.status_code == 200
        payload = r.json()["result"]
        assert payload["isError"] is True
        assert payload["structuredContent"] == {"error": "unknown tool: generate_graph"}
        assert len(payload["content"]) == 1
        assert payload["content"][0]["type"] == "text"

    def test_mcp_resources_list_returns_chart_widget(self, client, monkeypatch):
        monkeypatch.setenv("ALARM_MCP_TOKEN", "secret-token")

        r = client.post("/mcp?token=secret-token", json={
            "jsonrpc": "2.0",
            "id": "resources",
            "method": "resources/list",
            "params": {},
        })

        assert r.status_code == 200
        assert r.json()["result"]["resources"] == [
            {
                "uri": "ui://widget/chart.html",
                "name": "chart-widget",
                "title": "Alarm Chart Widget",
                "mimeType": "text/html;profile=mcp-app",
            }
        ]


    def test_mcp_resources_read_returns_chart_widget_html(self, client, monkeypatch):
        monkeypatch.setenv("ALARM_MCP_TOKEN", "secret-token")

        r = client.post("/mcp?token=secret-token", json={
            "jsonrpc": "2.0",
            "id": "resource",
            "method": "resources/read",
            "params": {"uri": "ui://widget/chart.html"},
        })

        assert r.status_code == 200
        payload = r.json()
        content = payload["result"]["contents"][0]
        assert content["uri"] == "ui://widget/chart.html"
        assert content["mimeType"] == "text/html;profile=mcp-app"
        assert 'id="chart-root"' in content["text"]
        assert "window.openai" in content["text"]
        assert "ui/notifications/tool-result" in content["text"]

    def test_mcp_render_chart_widget_returns_structured_data_and_ui_metadata(self, client, monkeypatch):
        monkeypatch.setenv("ALARM_MCP_TOKEN", "secret-token")

        r = client.post("/mcp?token=secret-token", json={
            "jsonrpc": "2.0",
            "id": "render",
            "method": "tools/call",
            "params": {
                "name": "render_chart_widget",
                "arguments": {
                    "chart_id": "alarm_category_counts",
                    "chart_kind": "bar",
                    "title": "Alarm Category Counts",
                    "labels": ["Power"],
                    "values": [2.0],
                    "series": [{"label": "Power", "value": 2.0}],
                    "warnings": [],
                    "data_quality": {"total_points": 1, "returned_points": 1, "truncated": False},
                    "query_context": {"filters": {"site_code": "AAA001"}},
                    "empty_state": None,
                },
            },
        })

        assert r.status_code == 200
        payload = r.json()["result"]
        assert payload["structuredContent"]["chart_id"] == "alarm_category_counts"
        assert payload["structuredContent"]["series"] == [{"label": "Power", "value": 2.0}]

exec
/bin/zsh -lc "git diff ce401c4d262c9362d3110036b9ea8f821d8a4719 -- llm_tools/service.py | sed -n '1,180p'" in /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
 succeeded in 0ms:
diff --git a/llm_tools/service.py b/llm_tools/service.py
index fec0da7..ca92f24 100644
--- a/llm_tools/service.py
+++ b/llm_tools/service.py
@@ -5,6 +5,7 @@ from __future__ import annotations
 import base64
 import hashlib
 import json
+import math
 import re
 from dataclasses import asdict, is_dataclass, replace
 from datetime import date, datetime, timedelta, timezone
@@ -54,6 +55,7 @@ try:
     from alarm_app.db.repos import blob_repo
     from alarm_app.db.repos.pm_repo import load_all_validation_results
     from alarm_app.llm_tools import federated_site
+    from alarm_app.llm_tools.charts import CHART_SPECS, chart_specs_payload
 except ImportError:
     from bdt.export import build_bdt_export_sheets
     from core.battery_backup_insights import (
@@ -91,6 +93,7 @@ except ImportError:
     from db.repos import blob_repo
     from db.repos.pm_repo import load_all_validation_results
     from llm_tools import federated_site
+    from llm_tools.charts import CHART_SPECS, chart_specs_payload
 
 MAX_QUERY_LIMIT = 500
 MAX_BLOB_BYTES = 5 * 1024 * 1024
@@ -99,6 +102,9 @@ EXPORT_DIR = Path.home() / ".alarm_viewer" / "exports"
 ALLOWED_UPLOAD_SUFFIXES = {".csv", ".xls", ".xlsx"}
 MCP_DEFAULT_PAGE_LIMIT = 500
 MCP_MAX_PAGE_LIMIT = 500
+CHART_WIDGET_URI = "ui://widget/chart.html"
+CHART_WIDGET_MIME_TYPE = "text/html;profile=mcp-app"
+CHART_DATA_MAX_POINTS = 500
 _FIELD_ALIASES = {
     "site_name": ("site_name", "sitename", "name"),
     "area": ("area", "orange_area", "orangearea"),
@@ -229,6 +235,40 @@ def _sanitize_mcp_value(value: Any) -> Any:
     return _jsonable(value)
 
 
+def _chart_number(value: Any) -> float | None:
+    if value is None or isinstance(value, bool):
+        return None
+    try:
+        number = float(value)
+    except (TypeError, ValueError):
+        return None
+    if not math.isfinite(number):
+        return None
+    return number
+
+
+def _normalize_chart_point(point: Any) -> dict[str, Any]:
+    if not isinstance(point, dict):
+        point = {"label": str(point), "value": 0.0}
+    normalized = _sanitize_mcp_value(point)
+    if not isinstance(normalized, dict):
+        return {"label": str(normalized), "value": 0.0}
+    for numeric_key in ("value", "x", "y"):
+        if numeric_key in normalized:
+            number = _chart_number(normalized.get(numeric_key))
+            if number is None:
+                normalized.pop(numeric_key, None)
+            else:
+                normalized[numeric_key] = number
+    if "label" not in normalized or normalized.get("label") is None:
+        normalized["label"] = str(normalized.get("x") or "")
+    else:
+        normalized["label"] = str(normalized.get("label"))
+    if "value" not in normalized:
+        normalized["value"] = _chart_number(normalized.get("y")) or 0.0
+    return normalized
+
+
 def _max_timestamp(*values: Any) -> Any:
     latest: pd.Timestamp | None = None
     for value in values:
@@ -1437,41 +1477,441 @@ class LocalDataService:
             "export_path": str(export_path),
         }
 
-    def generate_graph(self, **kwargs) -> dict[str, Any]:
-        graph_type = str(kwargs.get("graph_type") or "alarm_category_counts").strip()
-        site_code = normalize_site_key(kwargs.get("site_code") or kwargs.get("site_text") or "")
-        title = str(kwargs.get("title") or graph_type.replace("_", " ").title())
-        if graph_type.startswith("alarm_"):
-            alarm_df = self._alarm_rows_for_sites(
-                {site_code} if site_code else set(self._alarm_reference_df()["site_id"].map(normalize_site_key).dropna()),
-                date_from=_date_value(kwargs.get("date_from")),
-                date_to=_date_value(kwargs.get("date_to")),
-            ) if site_code else self._with_alarm_source(lambda: alarm_store.query_alarms(alarm_store.AlarmQuery(
-                date_from=_date_value(kwargs.get("date_from")),
-                date_to=_date_value(kwargs.get("date_to")),
-                limit=None,
-                offset=0,
-            )))
-            labels, values = self._alarm_graph_series(alarm_df, graph_type)
-        elif graph_type in {"bdt_verdict_counts", "bdt_duration_trend"}:
-            rows = self._query_all_bdt_rows(
-                site_code=site_code,
-                date_from=_date_value(kwargs.get("date_from")),
-                date_to=_date_value(kwargs.get("date_to")),
-            )
+    def list_chart_types(self, **kwargs) -> dict[str, Any]:
+        charts = chart_specs_payload(
+            family=str(kwargs.get("family") or ""),
+            chart_kind=str(kwargs.get("chart_kind") or ""),
+            renderable_only=bool(kwargs.get("renderable_only", False)),
+        )
+        return {"charts": charts, "count": len(charts)}
+
+    def _chart_alarm_df(self, *, site_code: str, kwargs: dict[str, Any]) -> pd.DataFrame:
+        date_from = _date_value(kwargs.get("date_from"))
+        date_to = _date_value(kwargs.get("date_to"))
+        if site_code and kwargs.get("_prefer_site_slice"):
+            return self._alarm_rows_for_sites({site_code}, date_from=date_from, date_to=date_to)
+        q = alarm_store.AlarmQuery(
+            site_text=str(kwargs.get("site_text") or "") if not site_code else "",
+            site_scope_keys={normalize_site_key(site_code)} if site_code else None,
+            category=str(kwargs.get("category") or "All"),
+            vendor=str(kwargs.get("vendor") or "All"),
+            network_type=str(kwargs.get("network_type") or "All"),
+            date_from=date_from,
+            date_to=date_to,
+            sort_by="occurred_on",
+            sort_desc=False,
+            limit=None,
+            offset=0,
+        )
+        return self._with_alarm_source(lambda: alarm_store.query_alarms(q))
+
+    @staticmethod
+    def _series_from_counts(work: pd.DataFrame, column: str, *, top_n: int | None = None) -> tuple[list[str], list[float]]:
+        if column not in work.columns:
+            return [], []
+        counts = work[column].fillna("Unknown").replace("", "Unknown").value_counts()
+        if top_n:
+            counts = counts.head(top_n)
+        return counts.index.astype(str).tolist(), counts.astype(float).tolist()
+
+    @staticmethod
+    def _duration_minutes_by(work: pd.DataFrame, column: str, *, top_n: int | None = None) -> tuple[list[str], list[float]]:
+        if column not in work.columns or "_duration_secs" not in work.columns:
+            return [], []
+        grouped = work.groupby(column, dropna=False)["_duration_secs"].sum().sort_values(ascending=False) / 60.0
+        if top_n:
+            grouped = grouped.head(top_n)
+        return grouped.index.astype(str).tolist(), grouped.astype(float).tolist()
+
+    @staticmethod
+    def _daily_counts(work: pd.DataFrame, *, category: str = "") -> tuple[list[str], list[float]]:
+        if "occurred_on" not in work.columns:
+            return [], []
+        source = work
+        if category and "alarm_category" in source.columns:
+            source = source[source["alarm_category"].astype(str).str.lower() == category.lower()]
+        days = pd.to_datetime(source["occurred_on"], errors="coerce", format="mixed").dropna().dt.date
+        counts = days.value_counts().sort_index()
+        return [str(v) for v in counts.index.tolist()], counts.astype(float).tolist()
+
+    @staticmethod
+    def _histogram_series(values: pd.Series, *, bins: int = 8) -> tuple[list[str], list[float]]:
+        numeric = pd.to_numeric(values, errors="coerce").dropna()
+        if numeric.empty:
+            return [], []
+        if numeric.nunique() == 1:
+            value = float(numeric.iloc[0])
+            return [f"{value:g}"], [float(len(numeric))]
+        counts, edges = pd.cut(numeric, bins=min(bins, max(1, numeric.nunique())), retbins=True, duplicates="drop")
+        grouped = counts.value_counts().sort_index()
+        labels = [f"{interval.left:g}-{interval.right:g}" for interval in grouped.index]
+        return labels, grouped.astype(float).tolist()
+
+    @staticmethod
+    def _box_summary_series(work: pd.DataFrame, group_col: str, value_col: str) -> tuple[list[str], list[float]]:
+        if group_col not in work.columns or value_col not in work.columns:
+            return [], []
+        numeric = pd.to_numeric(work[value_col], errors="coerce")

exec
/bin/zsh -lc "nl -ba llm_tools/service.py | sed -n '1488,1505p'; nl -ba llm_tools/service.py | sed -n '1792,1805p'" in /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
 succeeded in 0ms:
  1488	    def _chart_alarm_df(self, *, site_code: str, kwargs: dict[str, Any]) -> pd.DataFrame:
  1489	        date_from = _date_value(kwargs.get("date_from"))
  1490	        date_to = _date_value(kwargs.get("date_to"))
  1491	        if site_code and kwargs.get("_prefer_site_slice"):
  1492	            return self._alarm_rows_for_sites({site_code}, date_from=date_from, date_to=date_to)
  1493	        q = alarm_store.AlarmQuery(
  1494	            site_text=str(kwargs.get("site_text") or "") if not site_code else "",
  1495	            site_scope_keys={normalize_site_key(site_code)} if site_code else None,
  1496	            category=str(kwargs.get("category") or "All"),
  1497	            vendor=str(kwargs.get("vendor") or "All"),
  1498	            network_type=str(kwargs.get("network_type") or "All"),
  1499	            date_from=date_from,
  1500	            date_to=date_to,
  1501	            sort_by="occurred_on",
  1502	            sort_desc=False,
  1503	            limit=None,
  1504	            offset=0,
  1505	        )
  1792	        warnings: list[str] = []
  1793	        if max_points < 0:
  1794	            warnings.append(f"max_points raised from {max_points} to 0.")
  1795	            max_points = 0
  1796	        if max_points > CHART_DATA_MAX_POINTS:
  1797	            warnings.append(f"max_points clamped from {max_points} to {CHART_DATA_MAX_POINTS}.")
  1798	            max_points = CHART_DATA_MAX_POINTS
  1799	
  1800	        title = str(kwargs.get("title") or spec.label)
  1801	        series_kwargs = dict(filters)
  1802	        series_kwargs["_prefer_site_slice"] = True
  1803	        labels, values, series = self._chart_series_for_spec(chart_id, series_kwargs)
  1804	        if not series:
  1805	            series = [{"label": str(label), "value": _chart_number(value) or 0.0} for label, value in zip(labels, values, strict=False)]

exec
/bin/zsh -lc "nl -ba llm_tools/service.py | sed -n '1888,1900p'" in /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
 succeeded in 0ms:
  1888	            return {"error": f"unsupported graph_type: {graph_type}"}
  1889	
  1890	        site_code = normalize_site_key(kwargs.get("site_code") or kwargs.get("site_text") or "")
  1891	        title = str(kwargs.get("title") or spec.label)
  1892	        series_kwargs = dict(kwargs)
  1893	        series_kwargs["_prefer_site_slice"] = True
  1894	        labels, values, series = self._chart_series_for_spec(graph_type, series_kwargs)
  1895	        if not series:
  1896	            series = [{"label": str(label), "value": float(value)} for label, value in zip(labels, values, strict=False)]
  1897	
  1898	        path = _safe_export_path(self.export_dir / "charts", f"{title}_{site_code or 'all'}", "png")
  1899	        self._draw_chart(path, title, labels, values, chart_kind=spec.chart_kind, series=series)
  1900	        image_bytes = path.read_bytes()

exec
/bin/zsh -lc 'grep -n "def _model_safe_tool_result" -A80 llm_tools/openrouter_agent.py' in /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
 succeeded in 0ms:
132:def _model_safe_tool_result(value: Any) -> Any:
133-    if isinstance(value, dict):
134-        redacted: dict[str, Any] = {}
135-        for key, item in value.items():
136-            key_text = str(key)
137-            if key_text in PATH_KEYS or key_text.endswith("_path"):
138-                redacted[key_text] = _LOCAL_PATH_REDACTED if item else item
139-            else:
140-                redacted[key_text] = _model_safe_tool_result(item)
141-        return redacted
142-    if isinstance(value, list):
143-        return [_model_safe_tool_result(item) for item in value]
144-    if isinstance(value, str):
145-        return _redact_model_bound_text(value)
146-    return value
147-
148-
149-def _truncate_text_to_chars(text: str, max_chars: int) -> str:
150-    if len(text) <= max_chars:
151-        return text
152-    marker = CONTEXT_TRUNCATION_MARKER
153-    if max_chars <= len(marker) + 20:
154-        return marker.strip()[:max_chars]
155-    available = max_chars - len(marker)
156-    head_chars = max(1, available // 2)
157-    tail_chars = max(0, available - head_chars)
158-    tail = text[-tail_chars:] if tail_chars else ""
159-    return f"{text[:head_chars]}{marker}{tail}"
160-
161-
162-def _payload_char_count(
163-    messages: list[dict[str, Any]],
164-    tools: list[dict[str, Any]],
165-    model: str,
166-) -> int:
167-    payload: dict[str, Any] = {"model": model, "messages": messages}
168-    if tools:
169-        payload["tools"] = tools
170-        payload["tool_choice"] = "auto"
171-    return len(json.dumps(payload, ensure_ascii=False, default=str))
172-
173-
174-def _bounded_openrouter_messages(
175-    messages: list[dict[str, Any]],
176-    tools: list[dict[str, Any]],
177-    model: str,
178-    *,
179-    max_chars: int | None = None,
180-) -> list[dict[str, Any]]:
181-    budget = CONTEXT_BUDGET_MAX_CHARS if max_chars is None else max_chars
182-    bounded: list[dict[str, Any]] = []
183-    for message in messages:
184-        copied = dict(message)
185-        content = copied.get("content")
186-        if isinstance(content, str):
187-            copied["content"] = _truncate_text_to_chars(content, min(CONTEXT_MESSAGE_MAX_CHARS, budget))
188-        bounded.append(copied)
189-
190-    if _payload_char_count(bounded, tools, model) <= budget:
191-        return bounded
192-
193-    protected_tail_count = min(CONTEXT_MIN_RECENT_MESSAGES, max(2, len(bounded) // 2))
194-    protected_tail_start = max(0, len(bounded) - protected_tail_count)
195-    dropped: set[int] = set()
196-    for idx, message in enumerate(bounded):
197-        if idx >= protected_tail_start or idx in dropped:
198-            continue
199-        if message.get("role") == "system":
200-            continue
201-        if message.get("tool_call_id") or message.get("tool_calls"):
202-            continue
203-        dropped.add(idx)
204-        next_idx = idx + 1
205-        if next_idx < protected_tail_start:
206-            next_message = bounded[next_idx]
207-            if (
208-                next_message.get("role") in {"user", "assistant"}
209-                and not next_message.get("tool_call_id")
210-                and not next_message.get("tool_calls")
211-            ):
212-                dropped.add(next_idx)

exec
/bin/zsh -lc 'git diff --check ce401c4d262c9362d3110036b9ea8f821d8a4719' in /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
 succeeded in 0ms:
exec
/bin/zsh -lc 'grep -n "def _alarm_rows_for_sites" -A45 llm_tools/service.py' in /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
 succeeded in 0ms:
2414:    def _alarm_rows_for_sites(
2415-        self,
2416-        site_keys: set[str],
2417-        *,
2418-        date_from: date | None = None,
2419-        date_to: date | None = None,
2420-    ) -> pd.DataFrame:
2421-        if not site_keys:
2422-            return pd.DataFrame()
2423-        query = alarm_store.AlarmQuery(
2424-            site_scope_keys=site_keys,
2425-            date_from=date_from,
2426-            date_to=date_to,
2427-            sort_by="occurred_on",
2428-            limit=None,
2429-            offset=0,
2430-        )
2431-        return self._with_alarm_source(lambda: alarm_store.query_alarms(query))
2432-
2433-    def _alarm_rows_for_pm_sheet(self, pm_df: pd.DataFrame, site_col: str, date_col: str) -> pd.DataFrame:
2434-        site_keys = collect_site_sheet_keys(pm_df, site_col)
2435-        dates = pd.to_datetime(pm_df[date_col], errors="coerce", format="mixed")
2436-        valid_dates = [pd.Timestamp(v).date() for v in dates.dropna().tolist()]
2437-        date_from = min(valid_dates) - timedelta(days=1) if valid_dates else None
2438-        date_to = max(valid_dates) + timedelta(days=1) if valid_dates else None
2439-        return self._alarm_rows_for_sites(site_keys, date_from=date_from, date_to=date_to)
2440-
2441-    def _export_site_dossier_workbook(
2442-        self,
2443-        *,
2444-        site_code: str,
2445-        alarm_df: pd.DataFrame,
2446-        bdt_rows: list[dict[str, Any]],
2447-        bdt_details: list[dict[str, Any]],
2448-    ) -> Path:
2449-        path = _safe_export_path(self.export_dir, f"site_dossier_{site_code}", "xlsx")
2450-        rules: list[dict[str, Any]] = []
2451-        photos: list[dict[str, Any]] = []
2452-        discharge_rows: list[dict[str, Any]] = []
2453-        for detail in bdt_details:
2454-            bdt = detail.get("bdt") if isinstance(detail.get("bdt"), dict) else {}
2455-            run_id = detail.get("validation_run_id")
2456-            for rule in detail.get("rules", []) if isinstance(detail.get("rules"), list) else []:
2457-                if isinstance(rule, dict):
2458-                    rules.append({"validation_run_id": run_id, **rule})
2459-            for photo in detail.get("photos", []) if isinstance(detail.get("photos"), list) else []:

exec
/bin/zsh -lc 'cat mcp_app/chart_widget/package.json' in /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
 succeeded in 0ms:
{
  "scripts": {
    "build": "python build.py"
  },
  "devDependencies": {}
}

exec
/bin/zsh -lc ".venv/bin/pytest -q tests/test_llm_tools.py -k 'chart or graph or tool_definitions'" in /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604
 succeeded in 2067ms:
......................                                                   [100%]
22 passed, 302 deselected in 1.37s

codex
The new chart data path can return incorrect results for common filtered site-scoped chart requests. Targeted chart tests pass, but they do not cover this filter combination.

Review comment:

- [P2] Preserve alarm filters for site-scoped charts — /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604/llm_tools/service.py:1491-1492
  When `get_chart_data` or `generate_graph` is called with a `site_code` plus filters like `category`, `vendor`, or `network_type`, this early return uses `_alarm_rows_for_sites`, which only applies site/date filters. The chart then aggregates all alarm rows for the site instead of the requested subset, so e.g. a Power-only site chart can still include Down/vendor/network rows. Use the `AlarmQuery` path or filter the returned site slice before building the series.
The new chart data path can return incorrect results for common filtered site-scoped chart requests. Targeted chart tests pass, but they do not cover this filter combination.

Review comment:

- [P2] Preserve alarm filters for site-scoped charts — /Users/mikawi/.config/superpowers/worktrees/alarm_app/agent-main-worktree-20260604/llm_tools/service.py:1491-1492
  When `get_chart_data` or `generate_graph` is called with a `site_code` plus filters like `category`, `vendor`, or `network_type`, this early return uses `_alarm_rows_for_sites`, which only applies site/date filters. The chart then aggregates all alarm rows for the site instead of the requested subset, so e.g. a Power-only site chart can still include Down/vendor/network rows. Use the `AlarmQuery` path or filter the returned site slice before building the series.
