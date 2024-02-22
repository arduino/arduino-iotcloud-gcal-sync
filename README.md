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
``
{
    "iot_client_secret":"----your client secret here ----",
    "iot_client_id":"----your client id here ----",
    "rooms":[
        {
            "room_name":"blue_room",
            "gcal_calendar_id":"----your gcal ID here ----"
        }
    ]
}
``

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
