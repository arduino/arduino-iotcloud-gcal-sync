# Copilot Instructions

## Architecture

This service syncs Google Calendar room status to Arduino IoT Cloud Things. It consists of two independently deployed components:

- **`gcalwatch.py`** — Flask REST API deployed on GCP Cloud Run. Receives Google Calendar webhook notifications, extracts upcoming events, and publishes them to a Pub/Sub topic (`roomcalendar_events`). Also exposes endpoints to create/delete instant meetings.
- **`updater.py`** — Long-running process deployed on GCP Compute/GKE. Subscribes to the same Pub/Sub topic via `receiver_task.py`, keeps an in-memory cache of events per room (`CalendarMap`), and syncs computed room status to Arduino IoT Cloud Things via REST API (`IotClient`).

### Data flow

1. `updater` calls `gcalwatch /start_watching` for each room at startup
2. `gcalwatch` registers a webhook with Google Calendar API
3. Google Calendar pushes change notifications to `gcalwatch /webhook`
4. `gcalwatch` fetches next 10 events and publishes them to Pub/Sub
5. `receiver_task` (thread inside `updater`) receives Pub/Sub messages, updates `CalendarMap`, and wakes the main loop
6. `updater` compares computed `RoomStatus` from calendar events vs current IoT Cloud Thing properties, and updates IoT Cloud if they differ
7. A regular wakeup every 60 seconds re-evaluates status; at minute 55 of each hour, events are re-downloaded from Google Calendar for extra sync

### Key modules

- **`RoomStatus`** — Data class representing a room's current/next event state. Equality comparison drives update decisions.
- **`CalendarMap`** — Thread-safe in-memory store of events per room with a wakeup event queue (reasons: `REASON_CALENDARCHANGE`, `REASON_REGULAR`).
- **`GCalClient`** — Google Calendar API wrapper. Parses raw event data into `RoomStatus`. Handles instant meeting creation with 15-minute time slot rounding.
- **`IotClient`** — Arduino IoT Cloud API client using OAuth2 client credentials. Maps `RoomStatus` fields to IoT Thing properties (`busynow`, `curevmsg`, `curevstart`, etc.).
- **`mylogger`** — Thin wrapper around Python `logging` with format: `%(asctime)s [%(levelname)s] %(name)s: %(message)s [%(threadName)s]`.

## Build & Run

- **Python 3.10**, dependencies in `requirements.txt`
- Install: `pip install -r requirements.txt`
- **gcalwatch** (Flask): `gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 gcalwatch:app` (see `docker/gcalwatch.Dockerfile`)
- **updater**: `python updater.py` (see `docker/updater.Dockerfile`)
- No test suite exists in the repository

## Configuration

Both components read configuration from GCP Cloud Storage:
- Bucket `roomcalendar-config`: contains `config.json` (rooms, IoT credentials, gcalwatch URL) and `calendar_credentials.json` (Google service account key)
- Bucket `roomcalendar-watch-ids`: stores Google Calendar watch resource IDs per room

Authentication uses GCP default credentials (`google.auth.default`) in production (workload identity).

## Conventions

- All modules use `mylogger.getlogger(__name__)` for logging — do not use `print()` or raw `logging`.
- Retry pattern: loops with `MAX_ATTEMPTS` and `sleep()` delays (e.g., `RETRY_DELAY_IOT=3`, `RETRY_DELAY_GCAL=1`). Maintain this pattern for new API calls.
- Thread synchronization uses `threading.Condition` for wakeup signals and `threading.Lock` (inside `CalendarMap`) for shared state access.
- IoT Cloud Thing property names are short abbreviated strings (e.g., `curevmsg`, `nextevtm`, `busynow`) — keep this naming convention when adding new properties.
- Authentication to gcalwatch endpoints uses `Authorization: Bearer <iot_client_secret>` header, validated against `config.json`.
