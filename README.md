# Arduino IoTCloud - Google GCalendar Sync

This service integrates with Google Calendar and provides two different functions:
* gcalwatch.py - a convenient REST api to get notifications from Google Calendar when a calendar changes, and for booking the room for an immediate meeting. Implemented with Flask.
* updater.py - an automated syncrhonization process room status in Google Calendar and a corresponding Thing status in Arduino IoTCloud

Pre-requisites in Arduino IoTCloud:
* for each room named "room_name" listed configuration, there has to be a corresponding Thing in Arduino IoTCloud with Thing name = room_name
* the Thing in IoTCloud is prepared upfront with the following variables:
   * busynow (integer) = 0 if the room is currently free, 1 if the room is currently busy
   * curevmtg (string) = "current event meeting" = description of the meeting in progress, or a sentence like "free until..." if no meeting in progress
   * curevstart (string) = start time of current meeting if any
   * curevend (string) = end time of current meeting if any
   * curevtm (string) = summary indication of time interval (e.g. 15:00-18:00) of current meeting if any
   * nextevmtg (string) = "next event meeting" = description of the next upcoming meeting in this room, if any
   * nextevstart (string) = start time of next meeting if any
   * nextevend (string) = end time of next meeting if any
   * nextevtm (string) = summary indication of time interval (e.g. 15:00-18:00) of next meeting if any

## How it works

![Arch diagram](/images/gcalsync.png?raw=true)

In terms of deployment, here the situation:
* gcalwatch is a Flask app deployed as a container in Google Cloud Platform (using Cloud Run) that exposes an HTTP(s) endpoint providing basic authentication
* updater is a python program that runs in a container deployed on GCP again but using Compute or GKE because it needs to be always running

When updater starts, it performs a call (arrow 1 in the diagram) to gcalwatch/start_watching for each of the calendars that needs to be watched; the list of calendars corresponding to each room and the URL where gcalwatch is deployed are found in configuration (see below).
The /start_watching endpoing then calls Google Calendar API (2) and register itself (the /webhook endpoint) for change notifications; 
in this way, each time the calendar of a room changes, gcalwatch /webhook endpoint will be called by Google Calendar (3).
When /webhook is called (3), gcalwatch extracts the next 10 events from the calendar and sends a message using Pub/Sub service on a topic called "roomcalendar_events"; 10 events are ensuring that at least the next 2 hours are covered (considering a meaningful meeting duration).
Updater is registered on the same Pub/Sub topic and receives a notification for the change (5), copying all events in its memory.
Updater has a continuous flow of work based on two events A) notification of calendar change and B) regular check every minute. Each time A or B happens, updater will check the content of its memory of next events, and compute the current status of each room and the next event happening. Then, it will call Arduino Cloud via REST API (7) to compare the computed status with the Thing status for each room, and perform needed updates. The regular "each minute" check ensures that room status is updated at the start of a meeting.
Notice that there might be a case when for an entire hour or more there is no calendar change; for this reason, updater has an additional duty to perform an extraction of the next 10 events from each calendar every hour (arrow 6).

The flow is quite complex but the goal is:
* minimize calls to Google Calendar, which complains if the volume is too high and returns errors - the fact that updater is keeping a memory of next events ensures this
* quickly react to a new meeting so that the room displays are always up to date - the notification flow ensures this



## Configuration 

In order to be able to talk to Google Calendar API, the following configuration must be performed:
* create a project in Google Compute Cloud
* enable Calendar API for that project
* create a serviceaccount with Editor role on the project
* create a key associated to the service account and save the credential file in JSON format as "calendar_credentials.json"
The configuration file "calendar_credentials.json" will be used to connect to Google Calendar API

Each calendar in Google Calendar that needs to be configured in order to give edit rights to the same service account.

Additionally, we need to inform the program of which rooms we want to monitor and how to connect to Arduino IoTCloud.
For this prupose, create a file "config.json" with the following structure:

```

{
    "iot_client_secret":"----your client secret here ----",
    "iot_client_id":"----your client id here ----",
    "iot_organization_id":"-----optional, can be used to indicate an orgid if the user is using a plan with organization----",
    "gcal_watch_function_url":"----indicate here the address of gcalwatch function after it's deployed",
    "rooms":[
        {
            "room_name":"blue_room",
            "gcal_calendar_id":"----your gcal ID here ----"
        }
    ]
}

```

Both calendar_credentials.json and config.json files must be stored in Cloud Storage in a bucket named "/roomcal-config" in the same project. The program will use default credentials to lookup for this configuration bucket at startup.

The program also uses another bucket "/roomcal-watch-ids" (that can be created empty) to store all resource identifiers that Google Calendar assigns when a notification channel is created on a calendar. In this way, those resource ids can be used later on if the notification must be disabled.


## REST service

* GET /meetings  - returns JSON object representing room status with next two meetings
required parameters:
* Authorization header "Authorization: Bearer ---YOUR IOTCLOUD CLIENT SECRET HERE---"
* URL param: client_id   (from IoTCloud)
* URL param: room_name

* POST /meetings  - creates new meeting starting now 
    ** start time is rounded to 15 mins slots
    ** returns 201 if created successfully, or proper error code otherwise
required parameters:
* Authorization header "Authorization: Bearer ---YOUR IOTCLOUD CLIENT SECRET HERE---"
* Required JSON POST body:
``
{
    "room_name":"blue_room",
    "client_id":"---YOUR IOTCLOUD CLIENT ID HERE---"
}
``
* optional parameter: duration_mins (in POST json body as well), defaults to 60 mins
