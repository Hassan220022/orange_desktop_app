"""In-app reference documentation for the BDT validation rules.

Each entry maps a rule code (``R1``…``R11``) to a self-contained HTML body
shown by :class:`alarm_app.ui.dialogs.BdtRulesReferenceDialog`. The intro
section explains the verdict model and how tolerances flow through the
code; per-rule sections describe inputs, tolerances, and the calculation.

Keeping the content as plain HTML strings (rather than markdown) avoids
adding a runtime dependency on a markdown-to-HTML library and lets
``QTextBrowser`` render the document natively.
"""
from __future__ import annotations

from typing import Iterator


INTRO_HTML: str = """
<h2>BDT Validation Rules &mdash; Overview</h2>
<p>Every Battery Discharge Test (BDT) file is run through a sequence of
independent rules. Each rule emits one of four verdicts:</p>
<ul>
  <li><b>Accepted</b> &mdash; rule passed.</li>
  <li><b>Rejected</b> &mdash; rule failed.</li>
  <li><b>Revise</b> &mdash; inconclusive (e.g. missing field); a human needs to look.</li>
  <li><b>N/A</b> &mdash; rule is not applicable (e.g. no alarm data loaded).</li>
</ul>
<p>The aggregate test verdict on the results table follows the worst rule
verdict: any <b>Rejected</b> &rarr; Rejected; otherwise any <b>Revise</b>
&rarr; Revise; otherwise <b>Accepted</b>.</p>
<p>There is <b>no R4</b> &mdash; the rule numbering jumps from R3 directly
to R5 because R4 was retired earlier. The active rules are
<b>R1, R2, R3, R5, R6, R7, R8, R9, R10, R11</b> (10 rules total).</p>
<p>When a battery is flagged as <i>No Battery</i> or <i>Faulty Battery</i>
by the upfront <code>bdt_battery_status()</code> check, the seven
battery-dependent rules (R2, R3, R5, R6, R7, R8, R9) are emitted with
verdict <b>Skipped</b> and the file's overall verdict is decided from
R1, R10, R11 only.</p>
<p>The user-configurable thresholds described below appear under
<b>Settings &rarr; BDT Validation Parameters &rarr; Validation
Tolerances</b>. The defaults shown are applied when the user has not
edited them.</p>
"""


R1_HTML: str = """
<h2>R1 &mdash; Photos</h2>
<p><i>Verifies the BDT file contains the required evidence photos for the
rectifier and battery setup.</i></p>

<h3>Inputs</h3>
<ul>
  <li><code>photo_slots</code> &mdash; image slots discovered in the workbook.</li>
  <li><code>photo_categories_found</code> &mdash; labels assigned by the photo classifier (<i>rectifier</i>, <i>batteries</i>, &hellip;).</li>
  <li><code>required_photo_categories</code> &mdash; defaults to <code>["rectifier", "batteries"]</code>.</li>
  <li><code>required_photo_count</code> &mdash; integer threshold (default <b>2</b>).</li>
  <li><code>photo_count</code> &mdash; integer fallback when slot mapping is unavailable.</li>
  <li><code>photo_detection_mode</code> &mdash; <code>"deferred"</code> skips photo decoding; the rule then falls back to count-only.</li>
  <li><code>photo_mapping_confidence</code> &mdash; <code>"low"</code> short-circuits to N/A.</li>
</ul>

<h3>SynthID short-circuit</h3>
<p>Before any of the branches below run, if any photo slot's
<code>verification.synthid.status == "detected"</code>, the rule rejects
immediately with a list of the AI-flagged slot labels. This is the catch
for fraudulent images.</p>

<h3>Decision tree</h3>
<p>First matching branch wins:</p>
<ol>
  <li><b>Deferred mode + no slots</b> &rarr; use <code>photo_count</code>:
    <ul>
      <li><code>count == 0</code> &rarr; Rejected.</li>
      <li><code>count &gt;= required_photo_count</code> &rarr; Accepted.</li>
      <li>otherwise &rarr; Revise (<code>missing = required_photo_count - count</code>).</li>
    </ul>
  </li>
  <li><b>Mapping confidence "low"</b> &rarr; N/A.</li>
  <li><b>Categories were classified</b> &rarr; require every entry in
  <code>required_photo_categories</code> to be in <code>photo_categories_found</code>:
    <ul>
      <li>all present &rarr; Accepted.</li>
      <li>any missing &rarr; Rejected (lists what's missing and what was found).</li>
    </ul>
  </li>
  <li><b>Slots present, no category metadata</b> &rarr; count filled slots:
    <ul>
      <li><code>filled == 0</code> &rarr; Rejected.</li>
      <li><code>filled &gt;= required_photo_count</code> &rarr; Accepted.</li>
      <li>otherwise &rarr; Revise.</li>
    </ul>
  </li>
  <li><b>No slots at all</b> &rarr; integer <code>photo_count</code> fallback (same logic as branch 1).</li>
</ol>

<h3>Tolerances</h3>
<p><i>None.</i> R1 is purely structural.</p>
"""


R2_HTML: str = """
<h2>R2 &mdash; Power Alarm + Duration</h2>
<p><i>Verifies a real Power-cut alarm exists in the alarm history that
lines up with the BDT start time and discharge duration.</i></p>

<h3>Inputs</h3>
<ul>
  <li>BDT: <code>test_date</code>, <code>time_in</code>, <code>discharge_readings</code>, <code>site_code</code>.</li>
  <li>Alarm history: rows where <code>site_id == bdt.site_code</code> and
  <code>alarm_category == "power"</code> (with a <code>file_source</code> keyword fallback).</li>
</ul>

<h3>Tolerance</h3>
<ul>
  <li><b><code>power_timing_min</code></b> &mdash; minutes (default <b>15</b>). The window is symmetric <code>&plusmn;tol_min</code>.</li>
</ul>

<h3>Calculation</h3>
<ol>
  <li>Build the BDT start timestamp:
  <code>start_ts = test_date + time_in</code> (parsed from
  <code>HH:MM:SS</code>, <code>HH:MM</code>, or 12-hour formats).</li>
  <li>Determine the achieved discharge minutes:
  <code>discharge_minutes = max reached minute in the discharge table that has a V or A reading</code>
  (NOT the planned target &mdash; this is what physically happened).</li>
  <li>Build the expected end timestamp:
  <code>expected_end_ts = start_ts + discharge_minutes</code>.</li>
  <li>Find Power alarms for <code>site_code</code> whose <code>occurred_on</code>
  is on the same calendar date as <code>test_date</code>. None &rarr;
  <b>Rejected</b> ("Power was never cut from the grid").</li>
  <li>For each candidate, compute
  <code>start_diff_min = |occurred_on - start_ts|</code> in minutes. Drop
  candidates with <code>start_diff_min &gt; tol_min</code>. None left &rarr;
  <b>Rejected</b> with the closest miss.</li>
  <li>For each surviving Power alarm, attempt two paths:
    <ul>
      <li><b>Power &rarr; Cleared path</b>:
      <code>alarm_duration_min = cleared_on - occurred_on</code>;
      <code>duration_diff_min = |alarm_duration_min - discharge_minutes|</code>.</li>
      <li><b>Power &rarr; Down path</b>: any Down alarm at the same site
      whose <code>occurred_on</code> is in
      <code>[start_ts - tol, expected_end_ts + tol]</code> and
      <code>&gt;= power_start</code>.</li>
    </ul>
  </li>
  <li>Pick the attempt with the smallest <code>start_diff_min</code>
  (tiebreaker: smallest <code>end_diff_min</code> or
  <code>duration_diff_min</code>). <b>Accept</b> iff
  <code>duration_diff_min &lt;= tol_min</code>. Otherwise <b>Reject</b>.</li>
</ol>

<p><b>Why this design:</b> the alarm history is noisy and clocks drift,
so the rule checks both that a Power alarm started near the test time
AND that the alarm cleared (or a Down event followed) at the right time,
within one shared tolerance window.</p>
"""


R3_HTML: str = """
<h2>R3 &mdash; String vs Bus Bar Ampere</h2>
<p><i>Compares the rectifier's bus-bar reading against the sum of
per-string readings to make sure the string discharge data is
internally consistent.</i></p>

<h3>Inputs</h3>
<ul>
  <li><code>bdt.discharge_readings</code> &mdash; list of
  <code>(label, V, A)</code> from the main discharge table; only the A
  value (rectifier reading) is used.</li>
  <li><code>bdt.string_discharge_readings</code> &mdash; list-of-lists,
  one entry per discharge label, each containing
  <code>(volt, amp)</code> per string.</li>
</ul>

<h3>Tolerance</h3>
<ul>
  <li><b><code>string_ampere_a</code></b> &mdash; amps (default <b>3.0</b>).
  The acceptable band is the <b>one-sided</b>
  <code>[-string_ampere_a, 0]</code>.</li>
</ul>

<h3>Calculation</h3>
<p>For every reading in the main table that has an ampere value:</p>
<pre>strings_sum_a = sum of all string amperes for that label
bus_bar_a     = rectifier ampere from main table
diff          = bus_bar_a - strings_sum_a
acceptable    = -string_ampere_a &lt;= diff &lt;= 0
</pre>
<p>Any single label outside the band &rarr; <b>Rejected</b> with that
label's diff. All in band &rarr; <b>Accepted</b>. No string data &rarr;
<b>N/A</b>.</p>

<p><b>Why one-sided:</b> a rectifier reading <i>higher</i> than the sum
of strings would imply current flowing outside the strings, which is
physically impossible at this point in the circuit. So measurement
noise can only push the diff in the negative direction.</p>
"""


R5_HTML: str = """
<h2>R5 &mdash; Starting I-Battery Ampere</h2>
<p><i>Ensures the I-Battery current is approximately zero before the
rectifier is disconnected (i.e. the battery wasn't already discharging
when the test started).</i></p>

<h3>Inputs</h3>
<ul><li><code>bdt.ibat_before_test</code></li></ul>

<h3>Tolerance</h3>
<ul>
  <li><b><code>start_ampere_a</code></b> &mdash; amps (default <b>0.5</b>).
  The check is <code>|ibat_before_test| &lt; start_ampere_a</code>
  (strict less-than).</li>
</ul>

<h3>Calculation</h3>
<p>Trivial &mdash; one comparison. Missing field &rarr; <b>N/A</b>.</p>
"""


R6_HTML: str = """
<h2>R6 &mdash; End Voltage Range</h2>
<p><i>Asserts the test either ran long enough to count as complete OR
finished at an acceptable end voltage.</i></p>

<h3>Inputs</h3>
<ul>
  <li><code>bdt.end_voltage</code></li>
  <li><code>bdt.discharge_minutes</code></li>
</ul>

<h3>Tolerances</h3>
<ul>
  <li><b><code>completion_minutes</code></b> &mdash; minutes (default <b>180</b>); the discharge target ceiling.</li>
  <li><b><code>end_voltage_min</code></b> / <b><code>end_voltage_max</code></b> &mdash; volts (default <b>45.0</b> / <b>47.0</b>); the acceptable end-voltage window.</li>
</ul>

<h3>Calculation</h3>
<p>This is an <b>OR rule</b>:</p>
<pre>in_voltage_range = end_voltage_min &lt;= bdt.end_voltage &lt;= end_voltage_max
passed = (discharge_minutes &gt;= completion_minutes) OR in_voltage_range</pre>
<p>Either condition is sufficient. Missing <code>end_voltage</code>
&rarr; <b>N/A</b>.</p>

<p><b>Why an OR:</b> a test that ran the full target counts as a
complete pass regardless of where the voltage ended up; conversely, a
test that hit the lower-voltage cutoff before the target is also a
valid stop. Both signals individually justify acceptance.</p>
"""


R7_HTML: str = """
<h2>R7 &mdash; V/A Inverse Relationship</h2>
<p><i>Confirms voltage and current trended inversely during the
discharge &mdash; i.e. as the battery drains, voltage drops and
current is pulled harder. Catches obviously-fabricated linear-trend
data.</i></p>

<h3>Inputs</h3>
<ul>
  <li><code>bdt.discharge_readings</code> &mdash; only rows with both
  V and A present are used.</li>
</ul>

<h3>Tolerances</h3>
<p><i>None</i> &mdash; the threshold is hardcoded at
<code>correlation &lt; 0</code>. (Could be exposed later if needed.)</p>

<h3>Calculation</h3>
<ol>
  <li>Collect the (V, A) pairs into NumPy arrays.</li>
  <li>Need at least 3 pairs and non-constant variance on both arrays.
  Otherwise &rarr; <b>N/A</b>.</li>
  <li><code>corr = np.corrcoef(v_array, a_array)[0, 1]</code> (Pearson).</li>
  <li><code>passed = corr &lt; 0</code>.</li>
</ol>
<p>The detail message reports <code>corr</code> to 3 decimals so
reviewers can see how far it is from 0. A correlation of <code>-0.001</code>
technically passes; a <i>positive</i> correlation (V going up while A
goes up) is a strong fabrication signal.</p>
"""


R8_HTML: str = """
<h2>R8 &mdash; Sizing vs Actual</h2>
<p><i>Compares the measured discharge minutes against the theoretical
backup minutes derived from the battery specs and the actual load.</i></p>

<h3>Theoretical backup formula</h3>
<pre>load_w        = start_voltage * start_ampere      # load power, from "Before disconnecting Rectifier"
efficiency    = 1.0 if battery is Lithium else health_pct
capacity_wh   = battery_ah * battery_voltage * num_strings * efficiency
theoretical_h = capacity_wh / load_w
theoretical_m = theoretical_h * 60</pre>
<p>If any of <code>battery_ah</code>, <code>battery_voltage</code>,
<code>num_strings</code>, <code>start_voltage</code>,
<code>start_ampere</code> is missing or non-positive, the function
returns <code>None</code> and R8 is <b>Rejected</b> with detail
"Cannot compute theoretical duration".</p>

<h3>Tolerances</h3>
<ul>
  <li><b><code>completion_minutes</code></b> &mdash; minutes (default <b>180</b>); the test cap (shared with R6).</li>
  <li><b><code>sizing_fractional_tolerance</code></b> &mdash; fraction (default <b>0.15</b> = 15%); the fractional window.</li>
  <li><b><code>sizing_minutes_floor</code></b> &mdash; minutes (default <b>15</b>); the floor on the window.</li>
</ul>

<h3>Decision</h3>
<p><b>Branch A &mdash; <code>theoretical &gt; completion_minutes</code></b>:
the battery can outlast the test cap, so we only check whether the test
reached the cap.</p>
<pre>passed = actual_minutes &gt;= completion_minutes</pre>

<p><b>Branch B &mdash; <code>theoretical &lt;= completion_minutes</code></b>:
compare actual vs theoretical with a tolerance window.</p>
<pre>fractional_window = theoretical_minutes * sizing_fractional_tolerance
window            = max(fractional_window, sizing_minutes_floor)
delta             = |theoretical_minutes - actual_minutes|
passed            = delta &lt;= window</pre>
<p>The detail message correctly attributes which limb won &mdash; when
<code>sizing_minutes_floor &gt; fractional_window</code> it says
"15 min floor", otherwise it says "15% of theoretical".</p>

<h3>Why three knobs for one rule</h3>
<ul>
  <li><b><code>completion_minutes</code></b> answers <i>"what counts as a complete test?"</i> (used by both R6 and R8).</li>
  <li><b><code>sizing_fractional_tolerance</code></b> answers <i>"how tight should the window be relative to size?"</i></li>
  <li><b><code>sizing_minutes_floor</code></b> answers <i>"how tight is too tight for tiny batteries?"</i> (a 4 AH battery's 15% would be unreasonably small).</li>
</ul>

<p>R8 is the <b>only rule that never returns N/A</b> &mdash; if the
inputs are missing, it's a Reject, because a BDT without sizing data is
unreviewable.</p>
"""


R9_HTML: str = """
<h2>R9 &mdash; Discharge Current Tolerance</h2>
<p><i>Checks that current readings during discharge stay close to the
baseline reading throughout the test (catches readings that drift
because the load was changed mid-test).</i></p>

<h3>Inputs</h3>
<ul>
  <li><code>bdt.discharge_readings</code> &mdash; only rows with an ampere value are used.</li>
</ul>

<h3>Tolerance</h3>
<ul>
  <li><b><code>discharge_current_a</code></b> &mdash; amps (default <b>1.0</b>).
  The first-row reading is the baseline; every subsequent row must be
  within <code>&plusmn;discharge_current_a</code> of the baseline.</li>
</ul>

<h3>Calculation</h3>
<pre>baseline = readings[0].ampere
for label, current in readings[1:]:
    if |current - baseline| &gt; discharge_current_a:
        return Rejected with that label
return Accepted</pre>

<p>Fewer than 2 readings &rarr; <b>N/A</b>.</p>
"""


R10_HTML: str = """
<h2>R10 &mdash; Door Alarm Condition</h2>
<p><i>Requires a same-site Door alarm during the BDT test window
&mdash; physical access to the cabinet should produce a door alarm
in the alarm history.</i></p>

<h3>Inputs</h3>
<ul>
  <li>BDT: <code>site_code</code>, <code>test_date</code>, plus
  <code>_build_test_window(bdt)</code> which derives
  <code>[window_start, window_end]</code> from <code>time_in</code> and
  reached discharge minutes.</li>
  <li>Alarm history: rows whose <code>alarm_category == "door"</code>
  (or <code>alarm_name</code>/<code>file_source</code> contains "door"),
  same <code>site_id</code>, same <code>occurred_on</code> calendar date.</li>
</ul>

<h3>Tolerances</h3>
<p><i>None.</i> This rule is binary on existence within the test window.</p>

<h3>Calculation</h3>
<ol>
  <li>Filter alarms to same-site + same-date + door-keyword.</li>
  <li>If a <code>[window_start, window_end]</code> is available, prefer
  alarms inside it; with <code>strict_window=True</code>, require it.</li>
  <li>Any matching door alarm &rarr; <b>Accepted</b> (detail shows count).
  None &rarr; <b>Rejected</b>. Empty alarm history &rarr; <b>N/A</b>.
  Unparseable test date &rarr; <b>Revise</b>.</li>
</ol>

<p><b>Why this matters:</b> a BDT requires opening the cabinet, which
in NMS data always raises a door alarm. Tests with no door alarm are
usually fabricated paperwork.</p>
"""


R11_HTML: str = """
<h2>R11 &mdash; Summary Checklist</h2>
<p><i>Cross-checks parsed BDT values against the corresponding fields
on the workbook's Summary sheet (or external summary lookup) to detect
inconsistencies between sheets.</i></p>

<h3>Inputs</h3>
<ul>
  <li><code>bdt.summary_data</code> &mdash; a dict produced by the parser
  from the Summary sheet, or matched from an external lookup.</li>
  <li>A fixed list of 14 fields below.</li>
</ul>

<h3>Tolerances</h3>
<p><i>None.</i> Field-level comparison uses domain-aware matching:
numeric values are compared numerically with small slack; voltages are
compared with <code>_value_close_enough</code>; strings are normalized
before equality.</p>

<h3>Cross-checked fields</h3>
<table border="1" cellpadding="4" cellspacing="0">
<tr><th>BDT side</th><th>Summary side</th></tr>
<tr><td><code>site_code</code></td><td><code>Short Code</code></td></tr>
<tr><td><code>pld_value</code></td><td><code>PLVD Value</code></td></tr>
<tr><td><code>rectifier_brand</code></td><td><code>Rectifier Brand</code></td></tr>
<tr><td><code>num_modules</code></td><td><code># of Modules</code></td></tr>
<tr><td><code>battery_brand</code></td><td><code>Battery Brand</code></td></tr>
<tr><td><code>battery_voltage</code></td><td><code>Battery Volt</code></td></tr>
<tr><td><code>num_strings</code></td><td><code>No of String</code></td></tr>
<tr><td><code>num_batteries</code></td><td><code>No of Batteries</code></td></tr>
<tr><td><code>start_voltage</code></td><td><code>Start Volt</code></td></tr>
<tr><td><code>start_ampere</code></td><td><code>Start Amp</code></td></tr>
<tr><td><code>end_voltage</code></td><td><code>End Volt</code></td></tr>
<tr><td><code>end_ampere</code></td><td><code>End Amp</code></td></tr>
<tr><td><code>discharge_minutes</code></td><td><code>Discharge time( Mins)</code></td></tr>
<tr><td><code>test_date</code> (YYYY-MM-DD)</td><td><code>Test Date</code></td></tr>
</table>

<h3>Calculation</h3>
<ol>
  <li>For each pair, look up the summary value. If both BDT and Summary
  are blank, skip.</li>
  <li>Otherwise increment <code>checked</code> and compare with
  <code>_values_match</code>. Mismatch &rarr; record
  <code>"BDT='x' vs Summary='y'"</code>.</li>
  <li><code>checked == 0</code> &rarr; <b>N/A</b> ("No comparable fields found").</li>
  <li><code>mismatches == 0</code> &rarr; <b>Accepted</b>.</li>
  <li><code>1 &lt;= mismatches &lt; 4</code> &rarr; <b>Revise</b> (typically a transcription typo).</li>
  <li><code>mismatches &gt;= 4</code> &rarr; <b>Rejected</b> (the two sheets are clearly inconsistent).</li>
</ol>

<p>The detail prints up to 5 mismatches plus a "+N more" tail.</p>
"""


PLUMBING_HTML: str = """
<h2>How tolerances flow through the code</h2>
<pre>load_state["bdt_tolerances"]               (~/.alarm_viewer/state.json)
        |
        v
BDTTolerances.from_dict(...)               (bad/None values fall back to defaults)
        |
        v
BdtParametersDialog                        (one spinbox per field;
        |                                   "Reset to defaults" restores)
        v
BdtValidationPanel._run_validation         (loads persisted bundle, hands to thread)
        |
        v
BDTValidationThread(tolerances=...)        (passed through unchanged)
        |
        v
validate_bdt(..., tolerances=...)          (legacy tolerance= / power_timing_tol=
        |                                   kwargs still honoured)
        v
each rule reads only the field(s) it needs from the bundle</pre>
<p>Rules without tolerance arguments (R1, R7, R10, R11) are unaffected
by user edits &mdash; they don't have tunable thresholds.</p>
"""


# Ordered so the navigator and "scroll all" view follow the same layout.
RULE_DOCS: tuple[tuple[str, str, str], ...] = (
    ("intro", "Overview", INTRO_HTML),
    ("R1", "R1 — Photos", R1_HTML),
    ("R2", "R2 — Power Alarm + Duration", R2_HTML),
    ("R3", "R3 — String vs Bus Bar Ampere", R3_HTML),
    ("R5", "R5 — Starting I-Battery Ampere", R5_HTML),
    ("R6", "R6 — End Voltage Range", R6_HTML),
    ("R7", "R7 — V/A Inverse Relationship", R7_HTML),
    ("R8", "R8 — Sizing vs Actual", R8_HTML),
    ("R9", "R9 — Discharge Current Tolerance", R9_HTML),
    ("R10", "R10 — Door Alarm Condition", R10_HTML),
    ("R11", "R11 — Summary Checklist", R11_HTML),
    ("plumbing", "How tolerances flow", PLUMBING_HTML),
)


def iter_rule_docs() -> Iterator[tuple[str, str, str]]:
    """Yield ``(key, title, html)`` triples in display order."""
    yield from RULE_DOCS


def rule_doc(key: str) -> str | None:
    """Return the HTML body for a single section by key (e.g. ``"R8"``)."""
    for k, _title, html in RULE_DOCS:
        if k == key:
            return html
    return None


def full_rules_html(*, body_only: bool = False) -> str:
    """Concatenate every section into a single HTML document.

    Used as the default body of :class:`BdtRulesReferenceDialog` so
    Ctrl+F and "scroll" reading work over the entire reference. Each
    section is wrapped in an anchor named after its key so the
    navigator can jump to it via ``QTextBrowser.scrollToAnchor``.
    """
    chunks: list[str] = []
    for key, _title, html in RULE_DOCS:
        chunks.append(f'<a name="{key}"></a>{html}')
    body = "\n".join(chunks)
    if body_only:
        return body
    return (
        '<html><body style="font-family: Inter, \'Segoe UI\', sans-serif;">'
        + body
        + "</body></html>"
    )
