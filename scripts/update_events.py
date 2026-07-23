#!/usr/bin/env python3
"""Render upcoming Luma events into the marked block in index.html."""

import html
import json
import pathlib
import re
import sys
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

CALENDAR_ID = "cal-xqAChriSV15CC7R"
API_URL = (
    "https://api.lu.ma/calendar/get-items"
    f"?calendar_api_id={CALENDAR_ID}&period=future&pagination_limit=20"
)
CALENDAR_URL = f"https://luma.com/calendar/{CALENDAR_ID}"

ROOT = pathlib.Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.html"

START = "<!-- LUMA:START -->"
END = "<!-- LUMA:END -->"


def fetch_events():
    request = urllib.request.Request(API_URL, headers={"User-Agent": "kernel-ebpf-meetup-site"})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)

    events = []
    for entry in payload.get("entries", []):
        event = entry.get("event") or {}
        if event.get("visibility") != "public":
            continue
        events.append(event)
    events.sort(key=lambda e: e["start_at"])
    return events


def local_start(event):
    started = datetime.fromisoformat(event["start_at"].replace("Z", "+00:00"))
    try:
        return started.astimezone(ZoneInfo(event.get("timezone") or "UTC"))
    except Exception:
        return started.astimezone(timezone.utc)


def location_of(event):
    geo = event.get("geo_address_info") or {}
    place = geo.get("city_state") or geo.get("full_address")
    if place:
        return f"📍 {place}"
    if event.get("location_type") == "online":
        return "💻 Online"
    return "📍 Location TBD"


def render_card(event):
    start = local_start(event)
    url = f"https://luma.com/{event['url']}"
    time_label = start.strftime("%a %-I:%M %p").replace("AM", "AM").replace("PM", "PM")

    return f"""                    <a class="event-card" href="{html.escape(url)}">
                        <div class="event-date">
                            <span class="event-month">{start.strftime('%b').upper()}</span>
                            <span class="event-day">{start.day}</span>
                        </div>
                        <div class="event-body">
                            <h3>{html.escape(event['name'])}</h3>
                            <p class="event-time">{html.escape(time_label)}</p>
                            <p class="event-location">{html.escape(location_of(event))}</p>
                            <span class="event-rsvp">RSVP on Luma →</span>
                        </div>
                    </a>"""


def render_block(events):
    if events:
        cards = "\n".join(render_card(event) for event in events)
        body = f"""                <div class="event-grid">
{cards}
                </div>"""
    else:
        body = f"""                <p class="event-empty">No meetups are scheduled right now. <a href="{CALENDAR_URL}">Subscribe to our calendar</a> to hear about the next one first.</p>"""

    return f"""{START}
            <div class="section">
                <h2>Upcoming Meetups</h2>
{body}
                <p class="event-footnote">Dates and locations come straight from our <a href="{CALENDAR_URL}">Luma calendar</a>.</p>
            </div>
            {END}"""


def main():
    try:
        events = fetch_events()
    except Exception as error:
        print(f"failed to fetch Luma events: {error}", file=sys.stderr)
        return 1

    source = INDEX.read_text()
    if START not in source or END not in source:
        print(f"markers {START} / {END} not found in index.html", file=sys.stderr)
        return 1

    updated = re.sub(
        re.escape(START) + r".*?" + re.escape(END),
        lambda _: render_block(events),
        source,
        flags=re.DOTALL,
    )

    if updated == source:
        print(f"{len(events)} event(s), index.html already up to date")
        return 0

    INDEX.write_text(updated)
    print(f"{len(events)} event(s) written to index.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
