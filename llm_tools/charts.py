"""Shared chart catalog for AI, MCP, and computed chart reports."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable


@dataclass(frozen=True)
class ChartSpec:
    chart_id: str
    label: str
    chart_kind: str
    family: str
    description: str
    # Defaults are False: new specs must explicitly opt in once a verified
    # aggregator exists. This stops list_chart_types(renderable_only=True)
    # from advertising every catalog entry, including ones whose series
    # builder falls through to an unrelated count or returns empty.
    renderable: bool = False
    computed_report: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


_CHARTS: tuple[ChartSpec, ...] = (
    # Existing charts, preserved for compatibility. Opted in to renderable
    # only when the service has a verified aggregator for the chart id.
    ChartSpec("alarm_category_counts", "Alarm Category Counts", "bar", "alarm", "Count alarms by category or alarm name.", renderable=True, computed_report=True),
    ChartSpec("alarm_daily_counts", "Alarm Daily Counts", "bar", "alarm", "Count alarms per occurred date.", renderable=True, computed_report=True),
    ChartSpec("alarm_duration_by_category", "Alarm Duration By Category", "bar", "alarm", "Total alarm duration minutes by category.", renderable=True, computed_report=True),
    ChartSpec("bdt_verdict_counts", "BDT Verdict Counts", "bar", "bdt", "Count BDT validation verdicts.", renderable=True, computed_report=True),
    ChartSpec("bdt_duration_trend", "BDT Duration Trend", "bar", "bdt", "BDT discharge minutes by test date.", renderable=True, computed_report=True),

    # Alarm share/breakdown charts.
    ChartSpec("alarm_category_share", "Alarm Category Share", "donut", "alarm", "Share of alarms by category.", renderable=True, computed_report=True),
    ChartSpec("vendor_alarm_share", "Vendor Alarm Share", "pie", "alarm", "Share of alarms by vendor.", renderable=True, computed_report=True),
    ChartSpec("network_type_share", "Network Type Share", "pie", "alarm", "Share of alarms by network type.", renderable=True, computed_report=True),
    ChartSpec("alarm_severity_share", "Alarm Severity Share", "pie", "alarm", "Share of alarms by severity when available.", renderable=True, computed_report=True),
    ChartSpec("cleared_vs_uncleared_share", "Cleared Vs Uncleared Share", "donut", "alarm", "Cleared alarms compared with active/uncleared alarms.", renderable=True, computed_report=True),
    ChartSpec("alarm_clearance_rate_gauge", "Alarm Clearance Rate Gauge", "gauge", "alarm", "Cleared alarm percentage.", renderable=True, computed_report=True),

    # Time trend and comparative alarm charts.
    ChartSpec("alarm_volume_trend", "Alarm Volume Trend", "line", "alarm", "Alarm volume over occurred date.", renderable=True, computed_report=True),
    ChartSpec("daily_power_alarm_trend", "Daily Power Alarm Trend", "line", "alarm", "Power alarm volume over time.", renderable=True, computed_report=True),
    ChartSpec("daily_down_alarm_trend", "Daily Down Alarm Trend", "line", "alarm", "Down alarm volume over time.", renderable=True, computed_report=True),
    ChartSpec("site_alarm_trend", "Site Alarm Trend", "line", "alarm", "Selected site alarm volume over time.", renderable=True, computed_report=True),
    ChartSpec("cumulative_alarm_volume", "Cumulative Alarm Volume", "line", "alarm", "Cumulative alarm count over time.", renderable=True, computed_report=True),
    ChartSpec("daily_alarms_by_category", "Daily Alarms By Category", "stacked_bar", "alarm", "Daily alarms split by category.", renderable=True, computed_report=True),
    ChartSpec("weekly_alarms_by_category", "Weekly Alarms By Category", "stacked_bar", "alarm", "Weekly alarms split by category.", renderable=True, computed_report=True),
    ChartSpec("stacked_alarm_category_area", "Stacked Alarm Category Area", "stacked_bar", "alarm", "Category volume over time as stacked totals.", renderable=True, computed_report=True),
    ChartSpec("stacked_vendor_area", "Stacked Vendor Area", "stacked_bar", "alarm", "Vendor volume over time as stacked totals.", renderable=True, computed_report=True),
    ChartSpec("vendor_by_category", "Vendor By Category", "stacked_bar", "alarm", "Vendor split by alarm category.", renderable=True, computed_report=True),
    ChartSpec("network_type_by_category", "Network Type By Category", "stacked_bar", "alarm", "Network type split by alarm category.", renderable=True, computed_report=True),
    ChartSpec("vendor_alarm_comparison", "Vendor Alarm Comparison", "grouped_bar", "alarm", "Compare alarm counts by vendor.", renderable=True, computed_report=True),
    ChartSpec("power_vs_down_by_site", "Power Vs Down By Site", "grouped_bar", "alarm", "Power and Down counts by site.", renderable=True, computed_report=True),
    ChartSpec("alarm_count_vs_duration_by_category", "Alarm Count Vs Duration By Category", "grouped_bar", "alarm", "Category alarm count beside total duration.", renderable=True, computed_report=True),
    ChartSpec("network_type_vendor_comparison", "Network Type Vendor Comparison", "grouped_bar", "alarm", "Compare vendor counts by network type.", renderable=True, computed_report=True),

    # Ranked and distribution charts.
    ChartSpec("top_sites_by_alarm_count", "Top Sites By Alarm Count", "horizontal_bar", "alarm", "Sites with the most alarms.", renderable=True, computed_report=True),
    ChartSpec("top_sites_by_duration", "Top Sites By Duration", "horizontal_bar", "alarm", "Sites with the highest total duration.", renderable=True, computed_report=True),
    ChartSpec("top_sites_by_alarm_duration", "Top Sites By Alarm Duration", "horizontal_bar", "alarm", "Sites with the highest total duration.", renderable=True, computed_report=True),
    ChartSpec("top_alarm_names", "Top Alarm Names", "horizontal_bar", "alarm", "Most common alarm names.", renderable=True, computed_report=True),
    ChartSpec("top_alarm_ids", "Top Alarm IDs", "horizontal_bar", "alarm", "Most common alarm IDs.", renderable=True, computed_report=True),
    ChartSpec("uncleared_alarms_by_site", "Uncleared Alarms By Site", "horizontal_bar", "alarm", "Sites with the most uncleared alarms.", renderable=True, computed_report=True),
    ChartSpec("alarm_category_pareto", "Alarm Category Pareto", "pareto", "alarm", "Alarm categories ranked by count with cumulative impact.", renderable=True, computed_report=True),
    ChartSpec("alarm_duration_pareto", "Alarm Duration Pareto", "pareto", "alarm", "Sites/categories ranked by total duration.", renderable=True, computed_report=True),
    ChartSpec("site_alarm_pareto", "Site Alarm Pareto", "pareto", "alarm", "Sites ranked by alarm count with cumulative impact.", renderable=True, computed_report=True),
    ChartSpec("alarm_duration_distribution", "Alarm Duration Distribution", "histogram", "alarm", "Distribution of alarm durations.", renderable=True, computed_report=True),
    ChartSpec("duration_histogram", "Duration Histogram", "histogram", "alarm", "Distribution of alarm durations.", renderable=True, computed_report=True),
    ChartSpec("alarm_count_per_site_distribution", "Alarm Count Per Site Distribution", "histogram", "alarm", "Distribution of alarm counts across sites.", renderable=True, computed_report=True),
    ChartSpec("time_to_clear_distribution", "Time To Clear Distribution", "histogram", "alarm", "Distribution of time to clear alarms.", renderable=True, computed_report=True),
    ChartSpec("duration_boxplot_by_category", "Duration Boxplot By Category", "box", "alarm", "Duration spread by alarm category.", renderable=True, computed_report=True),
    ChartSpec("duration_boxplot_by_vendor", "Duration Boxplot By Vendor", "box", "alarm", "Duration spread by vendor.", renderable=True, computed_report=True),
    ChartSpec("mttr_by_site", "MTTR By Site", "horizontal_bar", "alarm", "Average clear time by site.", renderable=True, computed_report=True),
    ChartSpec("duration_vs_occurrence_time", "Duration Vs Occurrence Time", "scatter", "alarm", "Alarm duration compared with hour of occurrence.", renderable=True, computed_report=True),
    ChartSpec("site_alarm_count_vs_duration", "Site Alarm Count Vs Duration", "scatter", "alarm", "Site alarm count compared with total duration.", renderable=True, computed_report=True),

    # Heatmaps and timelines.
    ChartSpec("alarm_heatmap_day_hour", "Alarm Heatmap Day Hour", "heatmap", "alarm", "Alarm frequency by day of week and hour.", renderable=True, computed_report=True),
    ChartSpec("alarm_heatmap_site_day", "Alarm Heatmap Site Day", "heatmap", "alarm", "Alarm frequency by site and day.", renderable=True, computed_report=True),
    ChartSpec("alarm_heatmap_category_hour", "Alarm Heatmap Category Hour", "heatmap", "alarm", "Alarm category by hour concentration.", renderable=True, computed_report=True),
    ChartSpec("vendor_alarm_heatmap_day", "Vendor Alarm Heatmap Day", "heatmap", "alarm", "Vendor alarm concentration by day.", renderable=True, computed_report=True),
    ChartSpec("network_type_alarm_heatmap", "Network Type Alarm Heatmap", "heatmap", "alarm", "Network type/category concentration.", renderable=True, computed_report=True),
    ChartSpec("daily_alarm_calendar", "Daily Alarm Calendar", "calendar_heatmap", "alarm", "Alarm intensity by calendar day.", renderable=True, computed_report=True),
    ChartSpec("daily_down_alarm_calendar", "Daily Down Alarm Calendar", "calendar_heatmap", "alarm", "Down alarm intensity by calendar day.", renderable=True, computed_report=True),

    # Backup-time charts.
    ChartSpec("backup_time_by_site", "Backup Time By Site", "horizontal_bar", "backup", "Backup minutes by site.", renderable=True, computed_report=True),
    ChartSpec("backup_time_trend", "Backup Time Trend", "line", "backup", "Backup minutes over power/down dates.", renderable=True, computed_report=True),
    ChartSpec("backup_time_distribution", "Backup Time Distribution", "histogram", "backup", "Distribution of backup minutes.", renderable=True, computed_report=True),
    ChartSpec("top_sites_by_backup_failure", "Top Sites By Backup Failure", "horizontal_bar", "backup", "Worst backup sites by low backup time.", renderable=True, computed_report=True),
    ChartSpec("power_vs_down_timeline", "Power Vs Down Timeline", "timeline", "backup", "Power alarm window with Down event.", renderable=True, computed_report=True),
    ChartSpec("daily_backup_failure_calendar", "Daily Backup Failure Calendar", "calendar_heatmap", "backup", "Backup failures by calendar day.", renderable=True, computed_report=True),

    # BDT charts with verified aggregators.
    ChartSpec("bdt_verdict_counts", "BDT Verdict Counts", "bar", "bdt", "Count BDT validation verdicts.", renderable=True, computed_report=True),
    ChartSpec("bdt_duration_trend", "BDT Duration Trend", "bar", "bdt", "BDT discharge minutes by test date.", renderable=True, computed_report=True),
    ChartSpec("bdt_verdict_share", "BDT Verdict Share", "donut", "bdt", "Share of BDT verdicts.", renderable=True, computed_report=True),
    ChartSpec("bdt_verdict_trend", "BDT Verdict Trend", "stacked_bar", "bdt", "BDT verdicts over time.", renderable=True, computed_report=True),

    # BDT rule-failure charts. Catalogued for discoverability but NOT
    # opted in: _bdt_chart_series has no rule-result aggregator, so these
    # would otherwise fall through to the overall_verdict count and report
    # wrong data. Keep them off until a real rule-aggregation branch exists.
    ChartSpec("bdt_rule_failure_counts", "BDT Rule Failure Counts", "horizontal_bar", "bdt", "Most failed BDT validation rules."),
    ChartSpec("bdt_rule_failure_by_site", "BDT Rule Failure By Site", "horizontal_bar", "bdt", "Sites failing the most BDT rules."),
    ChartSpec("bdt_failure_heatmap_rule_site", "BDT Failure Heatmap Rule Site", "heatmap", "bdt", "BDT rule failures by site."),
    ChartSpec("bdt_rule_failure_pareto", "BDT Rule Failure Pareto", "pareto", "bdt", "BDT rules ranked by failure impact."),

    # PM/HT/site metadata and advanced charts.
    ChartSpec("pm_status_share", "PM Status Share", "donut", "pm", "PM status share."),
    ChartSpec("ht_weekly_pass_fail", "HT Weekly Pass Fail", "stacked_bar", "pm", "Weekly HT/PM pass/fail counts."),
    ChartSpec("ht_meet_vs_not_meet", "HT Meet Vs Not Meet", "stacked_bar", "pm", "HT meet vs not-meet counts."),
    ChartSpec("accepted_pm_by_week", "Accepted PM By Week", "line", "pm", "Accepted PM trend over time."),
    ChartSpec("weekly_pm_acceptance_trend", "Weekly PM Acceptance Trend", "line", "pm", "PM accepted/rejected trend."),
    ChartSpec("pm_rejection_reason_pareto", "PM Rejection Reason Pareto", "pareto", "pm", "PM rejection reasons ranked by impact."),
    ChartSpec("rejected_pm_reasons", "Rejected PM Reasons", "horizontal_bar", "pm", "Top PM rejection reasons."),
    ChartSpec("pm_rejection_heatmap_week_site", "PM Rejection Heatmap Week Site", "heatmap", "pm", "PM rejection by week/site."),
    ChartSpec("pm_acceptance_calendar", "PM Acceptance Calendar", "calendar_heatmap", "pm", "PM accepted/rejected by calendar day."),
    ChartSpec("pm_acceptance_rate_gauge", "PM Acceptance Rate Gauge", "gauge", "pm", "PM acceptance percentage."),
    ChartSpec("site_metadata_coverage", "Site Metadata Coverage", "gauge", "metadata", "How many alarm sites have site metadata."),
    ChartSpec("site_metadata_coverage_share", "Site Metadata Coverage Share", "donut", "metadata", "Sites with metadata compared with missing metadata."),
    ChartSpec("metadata_coverage_gauge", "Metadata Coverage Gauge", "gauge", "metadata", "Site metadata coverage percentage."),
    ChartSpec("site_region_alarm_treemap", "Site Region Alarm Treemap", "treemap", "metadata", "Region/office/site alarm impact."),
    ChartSpec("vendor_network_category_treemap", "Vendor Network Category Treemap", "treemap", "metadata", "Vendor to network to category impact."),
    ChartSpec("alarm_category_treemap", "Alarm Category Treemap", "treemap", "alarm", "Alarm category impact by count/duration."),
    ChartSpec("pm_status_treemap", "PM Status Treemap", "treemap", "pm", "Week to site to PM status."),
    ChartSpec("bdt_validation_funnel", "BDT Validation Funnel", "funnel", "bdt", "Files found to parsed to validated to accepted."),
    ChartSpec("pm_acceptance_funnel", "PM Acceptance Funnel", "funnel", "pm", "Imported to reviewed to accepted to exported."),
    ChartSpec("alarm_processing_funnel", "Alarm Processing Funnel", "funnel", "alarm", "Files scanned to loaded to normalized to cached."),
    ChartSpec("site_metadata_funnel", "Site Metadata Funnel", "funnel", "metadata", "Sites found to complete dossier."),
    ChartSpec("site_risk_score_gauge", "Site Risk Score Gauge", "gauge", "metadata", "Combined site risk score."),
    ChartSpec("site_health_radar", "Site Health Radar", "radar", "metadata", "Site health dimensions."),
    ChartSpec("vendor_performance_radar", "Vendor Performance Radar", "radar", "alarm", "Vendor comparison across metrics."),
    ChartSpec("network_type_radar", "Network Type Radar", "radar", "alarm", "Network type comparison across alarm metrics."),
    ChartSpec("alarm_to_site_flow", "Alarm To Site Flow", "sankey", "alarm", "Alarm category to vendor to site flow."),
    ChartSpec("pm_review_flow", "PM Review Flow", "sankey", "pm", "Imported to accepted/rejected/revise flow."),
    ChartSpec("bdt_rule_flow", "BDT Rule Flow", "sankey", "bdt", "BDT test to failed rule to verdict flow."),
    ChartSpec("site_context_flow", "Site Context Flow", "sankey", "metadata", "Site to metadata to alarms to BDT to PM status."),
)

CHART_SPECS: dict[str, ChartSpec] = {spec.chart_id: spec for spec in _CHARTS}


def chart_type_ids(*, renderable_only: bool = False, computed_report_only: bool = False) -> list[str]:
    specs: Iterable[ChartSpec] = CHART_SPECS.values()
    if renderable_only:
        specs = [spec for spec in specs if spec.renderable]
    if computed_report_only:
        specs = [spec for spec in specs if spec.computed_report]
    return [spec.chart_id for spec in specs]


def chart_type_description() -> str:
    return ", ".join(chart_type_ids(computed_report_only=True))


def chart_specs_payload(*, family: str = "", chart_kind: str = "", renderable_only: bool = False) -> list[dict[str, object]]:
    family_key = str(family or "").strip().lower()
    kind_key = str(chart_kind or "").strip().lower()
    rows = []
    for spec in CHART_SPECS.values():
        if renderable_only and not spec.renderable:
            continue
        if family_key and spec.family != family_key:
            continue
        if kind_key and spec.chart_kind != kind_key:
            continue
        rows.append(spec.to_dict())
    return rows
