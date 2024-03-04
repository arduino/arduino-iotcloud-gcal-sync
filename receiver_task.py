
from time import sleep
from datetime import datetime, timezone
import os
import mylogger
import json
from calendarmap import CalendarMap
from google.auth import default 
from google.cloud import pubsub_v1
from google.oauth2 import service_account


SCOPES = ['https://www.googleapis.com/auth/pubsub']

global calendar_map
global newdata_cond

logger = mylogger.getlogger(__name__)


def callback(message):
    global calendar_map
    global newdata_cond
    #read and ack message
    data = message.data.decode('utf-8')
    message.ack()
    #copy events in calendarmap
    obj = json.loads(data)
    room_name=obj["room_name"]
    logger.info(f"Received message: {room_name}")
    calendar_map.acquireLock()
    calendar_map.setCalendar(room_name,obj["events"])
    calendar_map.pushWakeup(CalendarMap.REASON_CALENDARCHANGE,room_name)
    calendar_map.releaseLock()
    with newdata_cond:
        newdata_cond.notify_all()
    
def get_credentials():
    #using local credential just for testing, not recommended
    #in production this is not needed because with workload identity
    #the machine will use the proper service account to initialize clients
    #creds = service_account.Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
    creds,project_id = default(scopes=SCOPES) 
    creds.project_id=project_id
    return creds


def receiver_task(cm,cond):
    global calendar_map
    global newdata_cond
    newdata_cond=cond
    calendar_map=cm
    logger.info("Initializing receiver thread")
    
    creds = get_credentials()

    # Initialize the Publisher client
    projectid = creds.project_id
    subscriber = pubsub_v1.SubscriberClient(credentials=creds)
    subscription_path = "projects/"+projectid+"/subscriptions/roomcalendar_events-sub"
    subscriber.subscribe(subscription_path, callback=callback)
    logger.info(f"Subscribed to messages from {subscription_path}")
    while True:
        try:
            current_time = datetime.now()
            current_seconds = current_time.second
            sleep(60-current_seconds)
            current_time = datetime.now()
            logger.info("SEND wake up REGULAR!")
            calendar_map.acquireLock()
            calendar_map.pushWakeup(CalendarMap.REASON_REGULAR,"")
            calendar_map.releaseLock()
            with newdata_cond:
                newdata_cond.notify_all()
        except Exception as e:
            logger.error(e)
            calendar_map.releaseLock()        
            sleep(5)
            #try to reconnect in case it was a problem with pubsub
            subscriber = pubsub_v1.SubscriberClient(credentials=creds)
            subscriber.subscribe(subscription_path, callback=callback)
            logger.info(f"Subscribed to messages from {subscription_path}")
            