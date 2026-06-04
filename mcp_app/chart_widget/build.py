from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
source = ROOT / "src" / "chart_widget.ts"
out = ROOT / "dist" / "chart.html"
text = source.read_text(encoding="utf-8")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(
    """
<div id="chart-root"></div>
<script>
""".lstrip()
    + text
    + "\n</script>\n",
    encoding="utf-8",
)
print(f"Built {out}")
