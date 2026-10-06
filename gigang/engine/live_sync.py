"""Feed newly collected records into the same engine used by the dashboard."""
from gigang.collectors.team_collector import get_team_security_events


def sync_live_events(context):
    engine = context.correlation_engine
    events = get_team_security_events()
    fresh = [event for event in events if event.event_id not in engine._processed_event_ids]
    if not fresh:
        return 0
    engine.ingest_events(sorted(fresh, key=lambda event: event.timestamp))
    context.team_events = events
    return len(fresh)
