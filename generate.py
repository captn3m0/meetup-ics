# /// script
# dependencies = [
#   "ics==0.7.2",
#   "python-dotenv==1.2.1",
#   "tatsu==5.16.0",
# ]
# ///

import json
import os
from ics import Calendar, Event
from ics.grammar.parse import ContentLine
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import http.client
import json

def generate_ics(output_file: str):
    """
    Fetches events from the Meetup API, filters out online events, and generates an ICS file.
    """
    # Load the Meetup API token from the environment
    load_dotenv()
    access_token = os.getenv("MEETUP_AUTH_ACCESS_TOKEN")
    if not access_token:
        raise ValueError("MEETUP_AUTH_ACCESS_TOKEN is not set in the environment or .env file")

    # Define the API endpoint and payload
    url = "https://www.meetup.com/gql2"
    headers = {
        "Content-Type": "application/json",
        "Cookie": f"__meetup_auth_access_token={access_token}",
        "Accept-Encoding": "gzip"
    }
    payload = {
        "operationName": "getEventsFromYourGroups",
        "variables": {
            "first": 15,
            "startDate": datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00Z")
        },
        "extensions": {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": "d482ec317a04ce4fca6357d6873ffeaeff933c7d359d78f272f928c6a69e1b1b"
            }
        }
    }

    # Make the API request
    # Prepare the HTTP connection and request
    conn = http.client.HTTPSConnection("www.meetup.com")
    payload_str = json.dumps(payload)
    conn.request("POST", "/gql2", body=payload_str, headers=headers)

    # Get the response
    response = conn.getresponse()
    if response.status != 200:
        raise ValueError(f"Failed to fetch events: {response.status} {response.reason}")

    # Parse the response JSON
    events = json.loads(response.read().decode())
    conn.close()

    calendar = Calendar()

    # Set calendar properties using the .extra attribute for proper RFC5545 compliance
    calendar.extra.extend([
        ContentLine(name="PRODID", value="-//Berlin Meetup Events//EN"),
        ContentLine(name="CALSCALE", value="GREGORIAN"),
        ContentLine(name="METHOD", value="PUBLISH"),
        ContentLine(name="X-WR-CALNAME", value="Berlin Meetup Events"),
        ContentLine(name="X-WR-CALDESC", value="In-person meetup events in Berlin"),
        ContentLine(name="X-WR-TIMEZONE", value="Europe/Berlin")
    ])

    if not events or not events.get("data") or not events["data"].get("self") or not events["data"]["self"].get("eventsFromGroups"):
        print("API response:", json.dumps(events, indent=2))  # Debugging output
        raise ValueError("Invalid or empty response from the API")

    for event in events["data"]["self"]["eventsFromGroups"]["edges"]:
        event_node = event.get("node", {})

        # Skip online events
        if event_node.get("eventType") == "ONLINE":
            continue

        # Skip events without proper datetime information
        if not event_node.get("dateTime"):
            print(f"Skipping event '{event_node.get('title', 'Unnamed')}' - missing datetime")
            continue

        ics_event = Event()
        ics_event.name = event_node.get("title", "Unnamed Event")

        # Set event times
        try:
            # Parse the datetime from the API response
            event_datetime = datetime.fromisoformat(event_node["dateTime"].replace('Z', '+00:00'))
            ics_event.begin = event_datetime

            # Set end time (assume 2 hours if duration not specified)
            duration_ms = event_node.get("duration")
            if duration_ms and isinstance(duration_ms, (int, float)):
                duration_hours = duration_ms / 3600000
            else:
                duration_hours = 2.0  # Default 2 hours
            ics_event.end = event_datetime.replace(microsecond=0) + timedelta(hours=duration_hours)

        except (ValueError, TypeError) as e:
            print(f"Skipping event '{event_node.get('title', 'Unnamed')}' - invalid datetime: {e}")
            continue

        # Set location
        venue = event_node.get("venue", {})
        if venue:
            address_parts = []
            if venue.get("address"):
                address_parts.append(venue["address"])
            if venue.get("city"):
                address_parts.append(venue["city"])
            ics_event.location = ", ".join(address_parts) if address_parts else venue.get("name", "Unknown Venue")
        else:
            ics_event.location = "Berlin, Germany"

        # Set URL
        ics_event.url = event_node.get("eventUrl", "")

        # Set description
        group_name = event_node.get("group", {}).get("name", "No Group Info")
        description = f"Group: {group_name}"
        if event_node.get("description"):
            description += f"\n\n{event_node['description']}"
        if event_node.get("eventUrl"):
            description += f"\n\nEvent URL: {event_node['eventUrl']}"
        ics_event.description = description

        # Set required timestamps
        ics_event.created = datetime.now(timezone.utc)
        ics_event.last_modified = datetime.now(timezone.utc)

        # Generate a unique ID based on the existing ID
        ics_event.uid = f"{event_node['id']}@berlin-meetup-events.com"

        calendar.events.add(ics_event)

    with open(output_file, "w", encoding="utf-8") as f:
        f.writelines(calendar)

if __name__ == "__main__":
    output_file = "out/berlin.ics"  # Default output file path
    generate_ics(output_file)
