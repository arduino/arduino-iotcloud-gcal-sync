# arduino-iotcloud-gcal-sync

Python backend service that syncs Google Calendar room bookings to Arduino IoT Cloud variables,
driving physical room display devices (Arduino Giga R1, M5Stack Paper, MKR IoT Carrier).

## Architecture

Two components deployed on GCP:

- **gcalwatch.py** — Flask API on Cloud Run: receives Google Calendar webhooks, publishes
  events to Pub/Sub, exposes REST endpoints for instant meeting create/delete.
- **updater.py** — Long-running daemon on Compute Engine: subscribes to Pub/Sub, syncs room
  status to Arduino IoT Cloud every minute + full refresh at :55.

Supporting modules: `gcalclient.py`, `iotclient.py`, `calendarmap.py`, `roomstatus.py`,
`receiver_task.py`, `mylogger.py`.

## Secrets — never commit

The repo is public. These files must never be committed:

- `config.json` — Arduino IoT Cloud credentials + room-to-calendar mapping.
  See `config.example.json` for the expected structure.
- `calendar_credentials.json` — GCP service account key for Google Calendar API access.

At runtime, both files are fetched from GCP Cloud Storage at container startup.
The Compute Engine VM uses an attached service account (no JSON key needed for GCP APIs).

## Docker

- `docker/gcalwatch.Dockerfile` — image for the Cloud Run Flask API
- `docker/updater.Dockerfile` — image for the Compute Engine daemon

## Deployment

CI/CD via GitHub Actions (see `.github/workflows/`). Authentication to GCP uses
Workload Identity Federation — no long-lived service account keys in GitHub Secrets.
