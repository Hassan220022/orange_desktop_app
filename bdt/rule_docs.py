"""In-app reference documentation for the BDT validation rules.

Each entry maps a rule code (``R1``\u2026``R11``) to a self-contained HTML
body shown by :class:`alarm_app.ui.dialogs.BdtRulesReferenceDialog`.
Section bodies are written in plain language for field engineers
\u2014 no code identifiers, internal field names, or implementation
details. Every numeric threshold is rendered from the user's current
:class:`~alarm_app.bdt.validator.BDTTolerances` bundle and the live
battery-health setting, so the document always matches whatever values
the user has saved.
"""
from __future__ import annotations

from collections.abc import Iterator

try:
    from alarm_app.bdt.validator import BDTTolerances
    from alarm_app.constants import BDT_DEFAULT_HEALTH_PCT
except ImportError:
    from bdt.validator import BDTTolerances
    from constants import BDT_DEFAULT_HEALTH_PCT


def _fmt(value, decimals: int = 2) -> str:
    """Format ``value`` with up to ``decimals`` digits, trimming trailing zeros."""
    try:
        formatted = f"{float(value):.{max(int(decimals), 0)}f}"
    except (TypeError, ValueError):
        return str(value)
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    return formatted or "0"


def _resolve_context(tolerances: BDTTolerances | None,
                     health_pct: int | float | None) -> dict[str, str]:
    """Build the substitution dictionary used by every section template."""
    tol = tolerances if tolerances is not None else BDTTolerances.defaults()
    health = int(health_pct) if health_pct is not None else int(BDT_DEFAULT_HEALTH_PCT)
    return {
        "power_min": _fmt(tol.power_timing_min, 0),
        "string_a": _fmt(tol.string_ampere_a),
        "discharge_a": _fmt(tol.discharge_current_a),
        "start_a": _fmt(tol.start_ampere_a),
        "end_v_min": _fmt(tol.end_voltage_min),
        "end_v_max": _fmt(tol.end_voltage_max),
        "completion_min": _fmt(tol.completion_minutes, 0),
        "network_min": _fmt(tol.min_backup_minutes_for_battery_rules, 0),
        "sizing_pct": _fmt(tol.sizing_fractional_tolerance * 100.0, 1),
        "sizing_floor": _fmt(tol.sizing_minutes_floor, 0),
        "health": str(health),
    }


# ---------------------------------------------------------------------------
# Section bodies. ``{name}`` placeholders are replaced at render time with
# values from the user's current settings.
# ---------------------------------------------------------------------------


INTRO_HTML: str = """
<h2>How BDT Validation and Insights Work</h2>
<p>Each BDT file goes through a series of checks. Every check produces
one of these outcomes:</p>
<ul>
  <li><b>Accepted</b> &mdash; the check passed.</li>
  <li><b>Rejected</b> &mdash; the check failed.</li>
  <li><b>Revise</b> &mdash; the result needs a person to look at it.</li>
  <li><b>N/A</b> &mdash; the check couldn't run (for example, no alarm
  history was loaded).</li>
  <li><b>Skipped</b> &mdash; the check needs a working battery, but this
  site is flagged as no-battery or faulty.</li>
</ul>
<p>The overall verdict for a file is the worst outcome among its checks.
Any <b>Rejected</b> &rarr; the file is Rejected. Otherwise any
<b>Revise</b> &rarr; the file is Revise. Otherwise the file is
<b>Accepted</b>.</p>
<p>There is no R4. The numbering jumps from R3 to R5 because R4 was
retired. The active checks are <b>R1, R2, R3, R5, R6, R7, R8, R9, R10,
R11</b>.</p>
<p>If the battery is flagged as <i>no battery</i> or <i>faulty</i>, the
seven battery-dependent checks (R2, R3, R5, R6, R7, R8, R9) are skipped
because there is no usable battery to test. The whole file is still
declined, while R1, R10, and R11 remain visible as evidence checks for
photos, door alarm, and summary consistency.</p>
<p>If <b>Network Summary</b> strongly declares no usable backup battery
(zero backup, stolen, removed, zero strings, or backup below
<b>{network_min} minutes</b>), the BDT can run as a <b>component check</b>.
Battery-dependent rules are skipped, infrastructure checks still run, and
the canonical verdict remains one of Accepted, Revise, or Rejected. When
the infrastructure checks pass, the table can display
<b>Accepted (component check - no backup battery)</b>.</p>
<p>The BDT table also shows <b>Insight Status</b> and
<b>Insight Severity</b>. Those are not extra pass/fail rules. They are
cross-checks between Network Summary and BDT evidence, used to show
whether the battery is actually reliable, untested, mismatched, or
missing.</p>
<p>All numbers shown in the sections below come from your current
settings. To change them, close this window and click
<b>Open Parameters</b>.</p>
"""


R1_HTML: str = """
<h2>R1 &mdash; Photos</h2>
<p>Checks that the BDT file contains the required photos of the
<b>rectifier</b> and the <b>batteries</b>.</p>
<h3>What passes and what fails</h3>
<ul>
  <li>Both required photo categories are present &rarr; <b>Accepted</b>.</li>
  <li>One or more required photos are missing &rarr; <b>Rejected</b>.</li>
  <li>Any photo is flagged as AI-generated &rarr; <b>Rejected</b>.</li>
  <li>The photos cannot be analysed clearly &rarr; <b>Revise</b> for a
  manual look.</li>
</ul>
<p>R1 catches files that are submitted without evidence photos and
files where the photos look fabricated.</p>
"""


R2_HTML: str = """
<h2>R2 &mdash; Power Alarm + Duration</h2>
<p>Checks that a power-cut alarm exists in the alarm history and lines
up with your test.</p>
<h3>How R2 decides</h3>
<ul>
  <li>The power-cut alarm may start up to <b>{power_min} minutes</b>
  before or after the test start time.</li>
  <li>The expected duration comes from the highest reached minute in the
  BDT discharge table, not from Time Out minus Time In.</li>
  <li>R2 compares candidate paths: <b>Power &rarr; Down</b> and
  <b>Power &rarr; Power Cleared</b>.</li>
  <li>A Power clear can be after handwritten Time Out as long as the
  Power duration still matches the discharge-duration within
  <b>{power_min} minutes</b>.</li>
  <li>If no matching Power alarm is found for the site on the test date,
  R2 fails.</li>
  <li>If the closest alarm is outside the {power_min}-minute window on
  start time, end time, or duration, R2 fails.</li>
</ul>
<p>Wider settings forgive small clock differences between the site and
the alarm system.</p>
"""


R3_HTML: str = """
<h2>R3 &mdash; Rectifier vs String Current</h2>
<p>Compares the rectifier's main current reading against the total of
all string current readings. They should be close because the strings
share the same load.</p>
<h3>How R3 decides</h3>
<ul>
  <li>Acceptable difference: up to <b>{string_a} A</b>.</li>
  <li>If the gap is bigger than that on any reading, R3 fails for that
  reading.</li>
  <li>If no string-level data is recorded, R3 reports <b>N/A</b>.</li>
</ul>
<p>The rectifier reading should never be larger than the sum of the
strings &mdash; current cannot appear from outside the strings &mdash;
so R3 only allows the gap to go in one direction.</p>
"""


R5_HTML: str = """
<h2>R5 &mdash; Starting Battery Current</h2>
<p>Checks that the battery is not already charging or discharging when
the test starts. The battery should be idle just before the rectifier
is unplugged.</p>
<h3>How R5 decides</h3>
<ul>
  <li>The starting battery current must be less than
  <b>{start_a} A</b>.</li>
  <li>If the recorded value is at or above that, R5 fails.</li>
  <li>If the field is missing on the BDT sheet, R5 reports <b>N/A</b>.</li>
</ul>
"""


R6_HTML: str = """
<h2>R6 &mdash; End Voltage Range</h2>
<p>Checks that the test ended properly. R6 is an <b>OR</b> rule
&mdash; either condition is enough to pass.</p>
<h3>How R6 decides</h3>
<ul>
  <li>The discharge ran for at least <b>{completion_min} minutes</b>,
  <i>or</i></li>
  <li>The end voltage landed between <b>{end_v_min} V</b> and
  <b>{end_v_max} V</b>.</li>
</ul>
<p>If the test ran the full {completion_min}-minute target, the end
voltage doesn't matter. If the test stopped early because the voltage
dropped to the cutoff, the test still counts as a valid end provided
the end voltage is in the acceptable range. Otherwise R6 fails.</p>
<p>If no end voltage is recorded, R6 reports <b>N/A</b>.</p>
"""


R7_HTML: str = """
<h2>R7 &mdash; Voltage and Current Trend</h2>
<p>As a battery drains, voltage should drop while current rises. R7
confirms that pattern in the discharge readings.</p>
<h3>How R7 decides</h3>
<ul>
  <li>R7 looks at every reading where both voltage and current were
  recorded.</li>
  <li>If voltage tends to fall while current tends to rise &rarr;
  <b>Accepted</b>.</li>
  <li>If both move in the same direction &rarr; <b>Rejected</b>
  (the readings look fabricated).</li>
  <li>If there are too few readings, or the values don't change at all,
  R7 reports <b>N/A</b>.</li>
</ul>
<p>This check catches obviously-copied linear-trend data.</p>
"""


R8_HTML: str = """
<h2>R8 &mdash; Expected vs Actual Test Time</h2>
<p>Compares your measured discharge time against how long the battery
should theoretically last, based on its size, voltage, and load.</p>
<h3>What gets used</h3>
<ul>
  <li>Battery size, number of strings, voltage, and the load measured
  before the rectifier was unplugged.</li>
  <li>Battery health, currently set to <b>{health}%</b>, used to
  estimate the expected time for lead-acid batteries. Lithium batteries
  are checked a different way and ignore this number.</li>
</ul>
<h3>How R8 decides</h3>
<p>R8 splits into two cases:</p>
<ul>
  <li><b>Battery should outlast the {completion_min}-minute target</b>
  &rarr; R8 passes as long as the test ran the full
  {completion_min} minutes.</li>
  <li><b>Battery should finish within the target</b> &rarr; the actual
  test time must be within <b>{sizing_pct}%</b> of the expected time,
  or at least <b>{sizing_floor} minutes</b>, whichever is bigger.
  Anything further off &rarr; R8 fails.</li>
</ul>
<p>If the BDT sheet is missing the battery sizing data needed to
estimate the expected time, R8 fails because the test cannot be
properly judged.</p>
<p>R8 uses three settings together:</p>
<ul>
  <li><b>Completion target</b> &mdash; what counts as a full test
  (also used by R6).</li>
  <li><b>{sizing_pct}% gap</b> &mdash; how tight the comparison should
  be relative to the expected time.</li>
  <li><b>{sizing_floor}-minute floor</b> &mdash; protects small
  batteries from a tolerance that would otherwise be unreasonably tight.</li>
</ul>
"""


R9_HTML: str = """
<h2>R9 &mdash; Discharge Current Stability</h2>
<p>Checks that the discharge current readings stay close to the first
reading throughout the test. Big swings usually mean the load was
changed mid-test.</p>
<h3>How R9 decides</h3>
<ul>
  <li>The first reading is treated as the baseline.</li>
  <li>Every later reading must be within <b>{discharge_a} A</b> of
  that baseline.</li>
  <li>The first reading that drifts further &rarr; R9 fails on that
  reading.</li>
  <li>If there are fewer than two readings, R9 reports <b>N/A</b>.</li>
</ul>
"""


R10_HTML: str = """
<h2>R10 &mdash; Door Alarm</h2>
<p>A BDT requires opening the cabinet, which raises a door alarm at
the site. R10 looks for that door alarm in the alarm history during
the test window.</p>
<h3>How R10 decides</h3>
<ul>
  <li>Door evidence is strict: <b>alarm_category</b> must be Door, with
  usable <b>occurred_on</b> and <b>cleared_on</b> timestamps.</li>
  <li>A door alarm at the same site, on the same date, inside the
  test window &rarr; <b>Accepted</b>; R10 applies no tolerance outside
  the BDT time window.</li>
  <li>No matching door alarm &rarr; <b>Rejected</b> (a real BDT
  should produce one).</li>
  <li>No alarm history loaded for that site &rarr; <b>N/A</b>.</li>
  <li>The test date can't be read from the BDT sheet &rarr;
  <b>Revise</b>.</li>
</ul>
<p>This check helps catch tests that exist only on paper.</p>
"""


R11_HTML: str = """
<h2>R11 &mdash; Summary Sheet Match</h2>
<p>Cross-checks the values written on the BDT sheets against the
matching values on the Summary sheet. The two sheets should agree.</p>
<h3>What gets compared</h3>
<ul>
  <li><b>Group A</b> infrastructure fields: site code, PLD value,
  rectifier brand, number of modules, and test date.</li>
  <li><b>Group B1</b> battery inventory: battery brand, voltage, number
  of strings, and number of batteries.</li>
  <li><b>Group B2</b> discharge results: start voltage, start current,
  end voltage, end current, and discharge time in minutes.</li>
</ul>
<p>Real BDT tests check Group A, Group B1, and Group B2. Faulty-present
battery cases check Group A and Group B1. No-battery and Network Summary
component-check cases check Group A only.</p>
<h3>How R11 decides</h3>
<ul>
  <li><b>0 mismatches</b> &rarr; <b>Accepted</b>.</li>
  <li><b>1, 2, or 3 mismatches</b> &rarr; <b>Revise</b> (likely typos,
  worth a manual review).</li>
  <li><b>4 or more mismatches</b> &rarr; <b>Rejected</b> (the two
  sheets clearly disagree).</li>
  <li>If no comparable fields exist on either sheet &rarr; <b>N/A</b>.</li>
</ul>
"""


INSIGHTS_HTML: str = """
<h2>Battery Backup Insights</h2>
<p>Insights connect <b>Network Summary</b> with the BDT evidence. They
answer a different question from the rule verdict: not only whether a
BDT file passed, but whether the site really has a usable backup plan
that matches the field evidence.</p>
<h3>How to read the insight columns</h3>
<ul>
  <li><b>Insight Status</b> is the main business meaning for the row.</li>
  <li><b>Insight Severity</b> is the priority level: low, medium, or high.</li>
  <li><b>Network Summary Freshness</b> compares the Network Summary snapshot
  date with the BDT test date. If Network Summary is older than the BDT, a
  matching value can still be stale and must not be treated as final proof.</li>
  <li>A high severity row should be investigated before trusting the
  battery backup claim.</li>
</ul>
<h3>Insight statuses</h3>
<ul>
  <li><b>Critical Site With Weak Backup</b> &mdash; the site is marked as
  important, for example VIP, 5G, or nodal/transport, and the measured
  BDT discharge is below the backup threshold. This means the battery may
  exist, but the site may still fail quickly during a power cut.</li>
  <li><b>Network Summary / BDT Mismatch</b> &mdash; Network Summary and
  BDT disagree. Examples: battery type does not match, string count does
  not match, Network Summary says backup is good but BDT measured weak
  backup, or backup minutes differ materially.</li>
  <li><b>Battery Technology Upgrade Detected</b> &mdash; Network Summary
  appears to describe an older lead-acid setup while the BDT shows a
  lithium setup. Raw values such as 12V to 48V, 16 batteries to 3 modules,
  or 4 strings to 3 strings are treated as an upgrade pattern first, not
  as ordinary mismatch noise. The row still needs evidence review,
  especially if Network Summary is older than the BDT.</li>
  <li><b>Battery Exists - BDT Failed</b> &mdash; Network Summary declares
  a battery, but the latest BDT validation is rejected, revise, failed,
  no-data, or has failed rules. The battery may be installed, but the test
  evidence does not prove reliable backup.</li>
  <li><b>Battery Exists - No BDT</b> &mdash; Network Summary declares
  battery backup, but no BDT summary, test, or validation was found. This
  means the battery exists on paper only until field evidence is added.</li>
  <li><b>Battery Exists - BDT Not Validated</b> &mdash; BDT data exists,
  but no validation run was found. The test may have been imported, but
  it has not been checked against the rules yet.</li>
  <li><b>No Battery Declared</b> &mdash; Network Summary does not show a
  usable battery setup. This can be caused by blank/no battery type, zero
  strings, zero backup minutes, zero-backup status, or a reason such as
  stolen or removed battery.</li>
  <li><b>Component Check - No Backup Battery</b> &mdash; Network Summary
  strongly says no usable backup exists, so BDT validation checks the
  site infrastructure without treating skipped battery rules as a failed
  battery discharge test.</li>
  <li><b>Battery Exists - BDT Passed</b> &mdash; Network Summary says the
  battery exists, the latest BDT validation is accepted, and no configured
  mismatch was detected. This is the strongest positive status.</li>
  <li><b>Battery Exists - BDT Present</b> &mdash; Network Summary says
  battery exists and some BDT evidence is present, but there is not enough
  evidence to classify the row as passed, failed, or mismatched.</li>
  <li><b>Insufficient Data</b> &mdash; the available Network Summary and
  BDT evidence is not enough to make a clear classification.</li>
  <li><b>Insight Unavailable</b> &mdash; fallback status shown only if
  the insight calculation fails for that row. The BDT row is still shown,
  but the insight could not be calculated.</li>
</ul>
<h3>What this helps validate</h3>
<ul>
  <li>Whether the site has a declared battery in Network Summary.</li>
  <li>Whether a BDT actually exists for that site.</li>
  <li>Whether the BDT was validated by the rules.</li>
  <li>Whether the measured BDT backup supports the claimed backup plan.</li>
  <li>Whether Network Summary and field evidence disagree.</li>
  <li>Whether the Network Summary record was fresh enough to support that BDT.</li>
</ul>
"""


SETTINGS_HTML: str = """
<h2>Where these numbers come from</h2>
<p>Every threshold shown above is read from your saved settings:</p>
<ul>
  <li>Battery health and the {completion_min}-minute completion target.</li>
  <li>The {power_min}-minute timing and discharge-duration match tolerance for R2.</li>
  <li>The {network_min} minutes Network Summary backup threshold that
  decides when battery-dependent BDT rules are skipped for component
  checks.</li>
  <li>The {string_a} A gap for rectifier vs strings (R3).</li>
  <li>The {start_a} A starting current limit (R5).</li>
  <li>The {end_v_min}\u2013{end_v_max} V end-voltage range (R6).</li>
  <li>The {sizing_pct}% / {sizing_floor}-minute sizing tolerances (R8).</li>
  <li>The {discharge_a} A current-stability allowance (R9).</li>
</ul>
<p>To change any of them, close this window and click
<b>Open Parameters</b>.</p>
"""


# Ordered so the navigator and "scroll all" view follow the same layout.
RULE_DOCS: tuple[tuple[str, str, str], ...] = (
    ("intro", "Overview", INTRO_HTML),
    ("R1", "R1 \u2014 Photos", R1_HTML),
    ("R2", "R2 \u2014 Power Alarm + Duration", R2_HTML),
    ("R3", "R3 \u2014 Rectifier vs String Current", R3_HTML),
    ("R5", "R5 \u2014 Starting Battery Current", R5_HTML),
    ("R6", "R6 \u2014 End Voltage Range", R6_HTML),
    ("R7", "R7 \u2014 Voltage and Current Trend", R7_HTML),
    ("R8", "R8 \u2014 Expected vs Actual Test Time", R8_HTML),
    ("R9", "R9 \u2014 Discharge Current Stability", R9_HTML),
    ("R10", "R10 \u2014 Door Alarm", R10_HTML),
    ("R11", "R11 \u2014 Summary Sheet Match", R11_HTML),
    ("insights", "Battery Backup Insights", INSIGHTS_HTML),
    ("settings", "Where these numbers come from", SETTINGS_HTML),
)


def _render(template: str, context: dict[str, str]) -> str:
    """Substitute ``{name}`` placeholders, leaving plain text untouched."""
    if not context or "{" not in template:
        return template
    try:
        return template.format(**context)
    except (KeyError, IndexError):
        return template


def iter_rule_docs(*, tolerances: BDTTolerances | None = None,
                   health_pct: int | float | None = None
                   ) -> Iterator[tuple[str, str, str]]:
    """Yield ``(key, title, html)`` triples in display order."""
    context = _resolve_context(tolerances, health_pct)
    for key, title, template in RULE_DOCS:
        yield key, title, _render(template, context)


def rule_doc(key: str, *, tolerances: BDTTolerances | None = None,
             health_pct: int | float | None = None) -> str | None:
    """Return the HTML body for a single section by key (e.g. ``"R8"``)."""
    for k, _title, html in iter_rule_docs(tolerances=tolerances,
                                          health_pct=health_pct):
        if k == key:
            return html
    return None


def full_rules_html(*, tolerances: BDTTolerances | None = None,
                    health_pct: int | float | None = None,
                    body_only: bool = False) -> str:
    """Concatenate every section into a single HTML document.

    Each section is wrapped in an anchor named after its key so the
    navigator can jump to it via ``QTextBrowser.scrollToAnchor``.
    """
    chunks: list[str] = []
    for key, _title, html in iter_rule_docs(tolerances=tolerances,
                                            health_pct=health_pct):
        chunks.append(f'<a name="{key}"></a>{html}')
    body = "\n".join(chunks)
    if body_only:
        return body
    return (
        '<html><body style="font-family: Inter, \'Segoe UI\', sans-serif;">'
        + body
        + "</body></html>"
    )
