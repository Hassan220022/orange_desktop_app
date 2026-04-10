"""Date and filter computation -- pure Python, no Qt."""

import re

import pandas as pd


def compute_date_mask(
    occurred: pd.Series,
    *,
    use_range: bool,
    from_date,
    to_date,
    use_days: bool,
    manual_days,
) -> pd.Series | None:
    """Return a boolean mask combining the range and specific-days filters.

    Parameters
    ----------
    occurred : pd.Series
        Datetime-like series of alarm occurrence timestamps.
    use_range : bool
        Whether the From/To range filter is active.
    from_date, to_date : date-like
        Inclusive range boundaries. ``to_date`` is treated as inclusive through
        23:59:59 of that day. Accepts anything ``pd.Timestamp`` can parse.
    use_days : bool
        Whether the specific-days filter is active.
    manual_days : iterable of pd.Timestamp (or date-like)
        Exact days to include when ``use_days`` is True. Each value is
        normalized to midnight before comparison.

    Returns
    -------
    pd.Series or None
        Boolean mask aligned to ``occurred``'s index. Returns ``None`` when
        neither sub-filter is active (caller should treat that as a no-op).
        NaT rows are always masked out when a mask is returned.
    """
    # Ensure we work with a Series (callers may pass a DatetimeIndex).
    if not isinstance(occurred, pd.Series):
        occurred = pd.Series(occurred)
    if not pd.api.types.is_datetime64_any_dtype(occurred):
        occurred = pd.to_datetime(occurred, errors="coerce")

    masks: list[pd.Series] = []

    if use_range:
        fd = pd.Timestamp(from_date)
        td = pd.Timestamp(to_date) + pd.Timedelta(
            hours=23, minutes=59, seconds=59)
        masks.append((occurred >= fd) & (occurred <= td))

    if use_days:
        normalized = {pd.Timestamp(d).normalize() for d in (manual_days or [])}
        if normalized:
            masks.append(occurred.dt.normalize().isin(normalized))
        else:
            masks.append(pd.Series(False, index=occurred.index))

    if not masks:
        return None

    combined = masks[0]
    for extra in masks[1:]:
        combined = combined | extra
    return combined & occurred.notna()


def parse_manual_days(raw: str) -> tuple[set[pd.Timestamp], list[str]]:
    """Parse a string of comma/space/semicolon-separated dates.

    Returns a tuple of (set of valid Timestamps normalized to midnight,
    list of tokens that failed to parse).
    """
    days: set[pd.Timestamp] = set()
    invalid: list[str] = []
    tokens = [t for t in re.split(r"[\s,;]+", raw.strip()) if t]
    for token in tokens:
        parsed = pd.to_datetime(token, errors="coerce")
        if pd.isna(parsed):
            invalid.append(token)
            continue
        days.add(pd.Timestamp(parsed).normalize())
    return days, invalid
