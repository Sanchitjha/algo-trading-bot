"""
Session & News filter — prevents trading during low-liquidity
or high-volatility (news) periods.
"""

from datetime import datetime, time
from config.strategy_rules import SESSION_FILTERS, DAY_FILTERS, NEWS_FILTER


def parse_time(t: str) -> time:
    """Parse 'HH:MM' string to time object."""
    h, m = t.split(':')
    return time(int(h), int(m))


def is_session_allowed(now: datetime | None = None) -> tuple[bool, str]:
    """
    Check if current time falls within an allowed trading session.
    Returns (allowed, reason).
    """
    if not SESSION_FILTERS['enabled']:
        return True, "Session filter disabled"

    if now is None:
        now = datetime.utcnow()

    current_time = now.time()
    weekday = now.weekday()  # 0=Mon, 6=Sun

    # ── Day filters ──
    # Skip Sunday before market opens
    if weekday == 6:  # Sunday
        cutoff = parse_time(DAY_FILTERS['skip_sunday_before'])
        if current_time < cutoff:
            return False, "Sunday — market not yet open"

    # Skip Friday evening
    if weekday == 4:  # Friday
        cutoff = parse_time(DAY_FILTERS['skip_friday_after'])
        if current_time >= cutoff:
            return False, "Friday evening — gap risk, no new trades"

    # Skip Saturday entirely
    if weekday == 5:
        return False, "Saturday — market closed"

    # ── Session filters ──
    allowed_sessions = SESSION_FILTERS['allowed_sessions']
    in_session = False
    session_name = "none"

    # London session
    london_open  = parse_time(SESSION_FILTERS['london_open'])
    london_close = parse_time(SESSION_FILTERS['london_close'])

    # NY session
    ny_open  = parse_time(SESSION_FILTERS['ny_open'])
    ny_close = parse_time(SESSION_FILTERS['ny_close'])

    # NY overlap (highest liquidity)
    overlap_start = parse_time(SESSION_FILTERS['ny_overlap_start'])
    overlap_end   = parse_time(SESSION_FILTERS['ny_overlap_end'])

    # Asian session
    asian_open  = parse_time(SESSION_FILTERS['asian_open'])
    asian_close = parse_time(SESSION_FILTERS['asian_close'])

    if 'ny_overlap' in allowed_sessions:
        if overlap_start <= current_time <= overlap_end:
            in_session = True
            session_name = "London/NY overlap"

    if 'london' in allowed_sessions:
        if london_open <= current_time <= london_close:
            in_session = True
            session_name = "London"

    if 'new_york' in allowed_sessions:
        if ny_open <= current_time <= ny_close:
            in_session = True
            session_name = "New York"

    if 'asian' in allowed_sessions:
        if asian_open <= current_time <= asian_close:
            in_session = True
            session_name = "Asian"

    if not in_session:
        return False, f"Outside allowed sessions ({', '.join(allowed_sessions)})"

    return True, f"In {session_name} session"


def is_news_window(now: datetime | None = None) -> tuple[bool, str]:
    """
    Check if we're within a news blackout window.
    In production, this would query ForexFactory/Investing.com API.
    For now, returns False (no news detected) — plug in your feed.
    """
    if not NEWS_FILTER['enabled']:
        return False, "News filter disabled"

    # TODO: Integrate with economic calendar API
    # Example integration points:
    #   - ForexFactory RSS/scrape
    #   - Investing.com economic calendar API
    #   - MQL5 economic calendar
    #
    # When integrated:
    #   1. Fetch upcoming events for next 60 minutes
    #   2. Filter by impact_levels (high)
    #   3. Check if any event is within pause_minutes_before
    #   4. Return True if in blackout window

    return False, "No high-impact news detected"


def can_trade_now(now: datetime | None = None) -> tuple[bool, str]:
    """
    Master filter: combines session + news checks.
    Returns (allowed, reason).
    """
    # Check session
    session_ok, session_reason = is_session_allowed(now)
    if not session_ok:
        return False, session_reason

    # Check news blackout
    in_news, news_reason = is_news_window(now)
    if in_news:
        return False, f"News blackout: {news_reason}"

    return True, session_reason
