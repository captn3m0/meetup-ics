# /// script
# dependencies = [
#   "ics==0.7.2",
#   "python-dotenv==1.2.1",
# ]
# ///

import json
import os
from ics import Calendar, Event
from datetime import datetime, timezone
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
                "sha256Hash": "0956d4cd0b90bfec326b58d4411948898be61747cd7a6e73005c7c924699ada5"
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

    if not events or not events.get("data") or not events["data"].get("self") or not events["data"]["self"].get("eventsFromGroups"):
        print("API response:", json.dumps(events, indent=2))  # Debugging output
        raise ValueError("Invalid or empty response from the API")

    for event in events["data"]["self"]["eventsFromGroups"]["edges"]:
        if event.get("node", {}).get("eventType") == "ONLINE":
            continue

        ics_event = Event()
        ics_event.name = event["node"].get("title", "Unnamed Event")
        venue = event["node"].get("venue", {})
        ics_event.location = venue.get("address", venue.get("name", "Unknown Venue")) or "Online Event"
        ics_event.url = event["node"].get("eventUrl", "")
        group_name = event["node"].get("group", {}).get("name", "No Group Info")
        description = f"Group: {group_name}"
        if event["node"].get("description"):
            description += f"\n\n{event['node']['description']}"
        ics_event.description = description

        # Generate a unique ID based on the existing ID
        ics_event.uid = f"{event['node']['id']}@berlin-events"

        calendar.events.add(ics_event)

    with open(output_file, "w", encoding="utf-8") as f:
        f.writelines(calendar)

if __name__ == "__main__":
    output_file = "out/berlin.ics"  # Default output file path
    generate_ics(output_file)
