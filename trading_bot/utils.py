"""Small shared utilities."""

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Timezone-naive UTC timestamp.

    We keep timestamps naive internally so they compare consistently with each
    other, while still being UTC. This avoids the deprecated ``utcnow()``.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)