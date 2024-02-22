import datetime
import json
import mylogger
from gcalclient import GCalClient
from flask import Flask, request, jsonify, abort
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.auth import default 
from googleapiclient.discovery import build
from google.auth.exceptions import RefreshError
from google.cloud import storage
from google.oauth2 import service_account
from google.cloud import pubsub_v1
import urllib.parse
from roomstatus import RoomStatus


SCOPES = ['https://www.googleapis.com/auth/calendar',
        'https://www.googleapis.com/auth/calendar.events',
        'https://www.googleapis.com/auth/devstorage.read_write',
        'https://www.googleapis.com/auth/pubsub']
 

BUCKET_NAME = "roomcal-watch-ids"
CONFIG_BUCKET_NAME="roomcal-config"
TOPIC_NAME="roomcalendar_events"
WATCH_ID="gcalwatch_v4"

app = Flask(__name__)

logger = mylogger.getlogger(__name__)

 
# Function to get the next events from now
def get_next_events(calendar_client,calendar_id, num_events=10):
    logger.info("Extracting events from calendar "+calendar_id)
    now = datetime.datetime.utcnow().isoformat() + 'Z' # 'Z' indicates UTC time
    events_result = calendar_client.events().list(calendarId=calendar_id, timeMin=now,
                                        maxResults=num_events, singleEvents=True,
                                        orderBy='startTime').execute()
    events = events_result.get('items', [])
    return events


def watch_calendar(calendar_client,calendar_id,url):
    logger.info("Starting to watch "+calendar_id+" watchid="+WATCH_ID)
    request = calendar_client.events().watch(calendarId=calendar_id, body={
        'id': WATCH_ID,
        'type': 'web_hook',
        'address': url
    })
    response = request.execute()
    logger.info(response)
    return response

def unwatch_calendar(calendar_client,watch_id,resource_id):
    request = calendar_client.channels().stop(body={                          
        'id': watch_id,
        'resourceId': resource_id
    })
    logger.info("Stopping to watch "+watch_id)
    response = request.execute()
    return response

def store_watch_resourceid(storage_client,room_name,response):
    bucket = storage_client.bucket(BUCKET_NAME)
    objname=room_name+".json"
    content = {
        "response":response
    }
    blob = bucket.blob(objname)
    with blob.open("w") as f:
        json.dump(content,f)
    

def read_watch_resourceid(storage_client,room_name):
    bucket = storage_client.bucket(BUCKET_NAME)
    objname=room_name+".json"
    blob = bucket.blob(objname)
 
    result={}
    try:
        with blob.open("r") as f:
            content = json.load(f)
        resp = content["response"]
        resource_id=resp["resourceId"]
        watch_id=resp["id"]
        result = { "resource_id": resource_id, "watch_id":watch_id }
    except Exception as e:
        logger.error('An error occurred: %s' % e)
    return result


def extract_calendar_id(calendar_uri):
    #https://www.googleapis.com/calendar/v3/calendars/URIISHERE/events?alt=json
    result = urllib.parse.unquote(calendar_uri)
    pos = result.find("/v3/calendars/")
    if pos!=-1:
        pos = pos+14
        result = result[pos:len(result)]
    pos = result.find("/events?alt=json")
    if pos!=-1:
        result = result[0:pos]
    return result


def get_credentials():
    #test only 
    #creds = service_account.Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
    creds, project_id = default(scopes=SCOPES)
    creds.project_id=project_id
    logger.debug("Get credentials "+creds.project_id)
    return creds 

#################### routes

# Function to handle webhook notifications
@app.route('/webhook', methods=['POST'])
def handle_webhook():
    logger.info("Webhook Notification Received:")
    props = dict(request.headers)
    logger.info(props)
    if props["X-Goog-Channel-Id"]!=WATCH_ID:
        logger.info("Ignoring notification, was for different watchid version "+props["X-Goog-Channel-Id"])
        return jsonify({'status': 'success'})

    calendar_uri = props["X-Goog-Resource-Uri"]
    #this is the full URI of the calendar so we need to strip out some parts
    calendar_id = extract_calendar_id(calendar_uri)
    
    storage_client = storage.Client(credentials=get_credentials())
    #retrieve config
    bucket = storage_client.bucket(CONFIG_BUCKET_NAME)
    blob = bucket.blob("config.json")
    with blob.open("r") as f:
        config = json.load(f)
    
    rooms=config.get("rooms",[])
    room_name=""
    for room in rooms:
       if room.get("gcal_calendar_id","")==calendar_id:
           room_name=room.get("room_name","")
    logger.info("Notification received for room "+room_name+" calendarid="+calendar_id)
    if room_name!="":
        logger.info("Extracting events and sending message for room "+room_name)
        
        creds = get_credentials()
        calendar_client = build('calendar', 'v3', credentials=creds)
        
        events = get_next_events(calendar_client,calendar_id)
        logger.info("Extracted "+json.dumps(events))
        
        publisher = pubsub_v1.PublisherClient(credentials=creds)
        projectid = creds.project_id
        
        topic_path = "projects/"+projectid+"/topics/"+TOPIC_NAME
        data = json.dumps({ "room_name":room_name, "events":events })
        future = publisher.publish(topic_path, data.encode('utf-8'))
        result = future.result()
        logger.info(f"Published message {data} to {topic_path} - {result}")
        
    return jsonify({'status': 'success'})


@app.route('/start_watching',methods=['POST'])
def startwatching():
    content = request.get_json(True)
    #read auth data from request
    client_id = content.get("client_id","")
    room_name = content.get("room_name","")
    authh = request.headers.get("Authorization","Bearer ")
    client_secret = authh[7:len(authh)]
    if room_name=="" or client_secret=="" or client_id=="":
        abort(400,"Required parameters in request body are missing")

    creds = get_credentials()
    calendar_client = build('calendar', 'v3',credentials=creds)
    storage_client = storage.Client(credentials=creds)
    
    #retrieve config
    bucket = storage_client.bucket(CONFIG_BUCKET_NAME)
    blob = bucket.blob("config.json")
    with blob.open("r") as f:
        config = json.load(f)
    
    
    rooms=config.get("rooms",[])
    config_client_id=config.get("iot_client_id","")
    #allow only requests with the same client_id as the one configured
    if client_id!=config_client_id:
        abort(401,"ERROR - Client not authorized")
    
    calendar_id = ""
    for room in rooms:
        if room.get("room_name","")==room_name:
            calendar_id=room.get("gcal_calendar_id","")

    if calendar_id=="":
        abort(400,"Required parameter not matching configuration for room_name="+room_name)

    logger.info("Executing request to watch room "+room_name)
    watch_url=config.get("gcal_watch_function_url","")+"/webhook"
    #first, stop any existing watch created by this function to avoid double watching
    ids = read_watch_resourceid(storage_client,room_name)
    if "resource_id" in ids:
        unwatch_calendar(calendar_client,ids["watch_id"],ids["resource_id"])

    #now setup a watch for this calendar
    response = watch_calendar(calendar_client,calendar_id,watch_url)

    #write watchid in cloud storage bucket
    store_watch_resourceid(storage_client,room_name,response)
    storage_client.close()
    
    return jsonify(response)




@app.route("/meeting/<id>",methods=['DELETE'])
def delete_meeting(id):
    content = request.get_json(True)
    #read auth data from request
    client_id = content.get("client_id","")
    room_name = content.get("room_name","")
    authh = request.headers.get("Authorization","Bearer ")
    client_secret = authh[7:len(authh)]
    
    if room_name=="" or client_secret=="" or client_id=="":
        abort(400,"Required parameters in request body are missing")
    
    storage_client = storage.Client()
    #retrieve config
    bucket = storage_client.bucket(CONFIG_BUCKET_NAME)
    blob = bucket.blob("config.json")
    with blob.open("r") as f:
        config = json.load(f)
    
    config_client_id=config.get("iot_client_id","")
    #allow only requests with the same client_id as the one configured
    if client_id!=config_client_id:
        abort(401,"ERROR - Client not authorized")
    
    rooms=config.get("rooms",[])
    config_client_id=config.get("iot_client_id","")
    #allow only requests with the same client_id as the one configured
    if client_id!=config_client_id:
        abort(401,"ERROR - Client not authorized")

    calendar_id = ""
    for room in rooms:
        if room.get("room_name","")==room_name:
            calendar_id=room.get("gcal_calendar_id","")

    if calendar_id=="":
        abort(400,"Required parameter not matching configuration for room_name="+room_name)

    gcalc = GCalClient(calendar_id,room_name)

    attempts=1
    deletedok=False
    while deletedok==False and attempts<3:
        deletedok = gcalc.delete_meeting(id)
        attempts = attempts+1

    if deletedok: 
        logger.info("Meeting deleted")
        return "Meeting deleted",201
    else: 
        logger.error("Could not delete meeting")
        abort(500,"ERROR - could not delete meeting")



@app.route("/meetings",methods=['POST'])
def new_meeting():
    content = request.get_json(True)
    #read auth data from request
    client_id = content.get("client_id","")
    duration_str = content.get("duration_mins","60")
    room_name = content.get("room_name","")
    authh = request.headers.get("Authorization","Bearer ")
    client_secret = authh[7:len(authh)]
    
    if room_name=="" or client_secret=="" or client_id=="":
        abort(400,"Required parameters in request body are missing")
    
    storage_client = storage.Client()
    #retrieve config
    bucket = storage_client.bucket(CONFIG_BUCKET_NAME)
    blob = bucket.blob("config.json")
    with blob.open("r") as f:
        config = json.load(f)
    
    rooms=config.get("rooms",[])
    config_client_id=config.get("iot_client_id","")
    #allow only requests with the same client_id as the one configured
    if client_id!=config_client_id:
        abort(401,"ERROR - Client not authorized")

    calendar_id = ""
    for room in rooms:
        if room.get("room_name","")==room_name:
            calendar_id=room.get("gcal_calendar_id","")

    if calendar_id=="":
        abort(400,"Required parameter not matching configuration for room_name="+room_name)

    gcalc = GCalClient(calendar_id,room_name)

    duration_mins = int(duration_str)
    roomstatus = gcalc.get_calendar_status()
    if (roomstatus.busynow==RoomStatus.BUSY):
        abort(400,"Could not insert new meeting, room already busy")

    attempts=1
    insertedok=False
    while insertedok==False and attempts<3:
        insertedok = gcalc.insert_instantmeeting(duration_mins)
        attempts = attempts+1

    if insertedok: 
        logger.info("Meeting created")
        return "Meeting created",201
    else: 
        logger.error("Could not insert meeting")
        abort(500,"ERROR - could not insert meeting")




if __name__ == '__main__':
    logger.info("Startup")
    
    app.run(debug=True)
 