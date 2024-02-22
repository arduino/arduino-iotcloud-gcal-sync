from threading import Thread,Condition
import json
import mylogger
from time import sleep
from receiver_task import receiver_task
from calendarmap import CalendarMap
from gcalclient import GCalClient
from datetime import datetime
from iotclient import IotClient
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.oauth2 import service_account
from google.auth import default 
from google.cloud import storage

import requests

logger = mylogger.getlogger(__name__)


BUCKET_NAME = "roomcal-config"
SCOPES = ['https://www.googleapis.com/auth/pubsub',
        'https://www.googleapis.com/auth/devstorage.read_write',
        'https://www.googleapis.com/auth/calendar',
        'https://www.googleapis.com/auth/calendar.events']

MAX_ATTEMPTS=3
RETRY_DELAY_IOT=1
 
def start_watching_calendar(client_id,client_secret,room_name,watchurl):
    logger.info("Start watching calendar "+room_name)
    headers={"Authorization":"Bearer "+client_secret}
    data = {'room_name': room_name, 'client_id': client_id}   
    try:
        requests.post(watchurl, json=data,headers=headers)
    except requests.HTTPError as e:
        logger.error("HTTP error occurred:", e)
    except requests.RequestException as e:
        logger.error("Error occurred during request:", e)
    except Exception as e:
        logger.error(e)
    return
 
def update_if_needed(iotc,room_name,iot_room_status,gcal_room_status):
    if gcal_room_status.is_valid() and iot_room_status.is_valid() and gcal_room_status != iot_room_status:
            #need to update roomstatus in iot
            attempts = 1
            updateok = False
            while not updateok and attempts<MAX_ATTEMPTS:
                logger.info(f"Updating room {room_name} in IoTCloud...")
                iotc.update_room_status(gcal_room_status,iot_room_status)
                #leave some time for property propagation
                sleep(5)
                iot_room_status = iotc.get_room_status_retry(room_name) 
                if iot_room_status.is_valid() and iot_room_status==gcal_room_status:
                    updateok = True
                else:
                    logger.info("Retrying update, still not OK")
                    attempts=attempts+1
            if not updateok:
                logger.info("Unable to perform update after multiple attempts, stopping")
    return 

def get_credentials():
    #using local credential just for testing, not recommended
    #in production this is not needed because with workload identity
    #the machine will use the proper service account to initialize clients
    #creds = service_account.Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
    creds,project_id = default(scopes=SCOPES)
    return creds
 

def watch_and_update_iot(): 
    version = "20240222"
    logger.info("_________________________________________________")
    logger.info("Starting backend for calendar update...v"+version)
    logger.debug("Opening configuration from config.json")   
    storage_client = storage.Client(credentials=get_credentials())
    
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob("config.json")
    with blob.open("r") as f:
        config = json.load(f)

    logger.debug(config)

    client_secret=config.get("iot_client_secret","")
    client_id=config.get("iot_client_id","")
    org_id=config.get("iot_organization_id","")
    gcal_watchurl=config.get("gcal_watch_function_url","")+"/start_watching"
    iotc=IotClient(client_id,client_secret,org_id)

    cm = CalendarMap()
    
    rooms = config.get("rooms",[])
    logger.info("Starting to watch calendar for all rooms...")
    room_names=[]
    for room in rooms:
        #prepares client and downloads events for the first population
        calendar_id = room.get("gcal_calendar_id","")
        room_name = room.get("room_name","")
        room_names.append(room_name)
        calendar_client=GCalClient(calendar_id,room_name)
        events = calendar_client.get_next_events()
        cm.setCalendar(room_name,events)
        cm.setCalendarId(room_name,calendar_id)
        start_watching_calendar(client_id,client_secret,room_name,gcal_watchurl)

    #used to get notified by the receiver thread
    newdata_cond = Condition()
    #start separate thread to receive notification messages that update events
    logger.info("Starting a thread to receive notifications...")    
    thread = Thread(target=receiver_task, args=[cm,newdata_cond])
    thread.name = "notification_receiver"
    thread.start()
    sleep(1)

    while True:
        try:
            with newdata_cond:
                # Wait until data is available
                newdata_cond.wait()
                cm.acquireLock()
                # WAKEUP call received from receiver_task, now Process the data
                #pop out all calls which happened (can be multiple)
                done_processing = False
                while not done_processing:
                    wakeupcall=cm.popWakeup()
                    if "reason" in wakeupcall:
                        logger.info("WAKEUP>"+wakeupcall["reason"]+".."+wakeupcall["calendar_name"])
                        if wakeupcall["reason"]==cm.REASON_CALENDARCHANGE:
                            #process calendar based on already received events
                            room_name = wakeupcall["calendar_name"]
                            calendar_client=GCalClient(calendar_id,room_name)
                            events = cm.getCalendar(room_name)
                            gcal_room_status = calendar_client.get_calendar_status_from_events(events)
                            logger.debug(gcal_room_status)
                            iot_room_status = iotc.get_room_status_retry(room_name)
                            logger.debug(iot_room_status)
                            update_if_needed(iotc,room_name,iot_room_status,gcal_room_status)
                            
                        
                        if wakeupcall["reason"]==cm.REASON_REGULAR:
                            #if we are at min 55 of the hour, to be sure about sync, re-downloads events from calendar
                            current_time = datetime.now()
                            current_mins = current_time.minute
                            if current_mins==55:
                                logger.info("Downloading room calendars for extra sync before hour end")
                                for room_name in room_names:
                                    calendar_client=GCalClient(cm.getCalendarId(room_name),room_name)
                                    events = calendar_client.get_next_events()                        
                                    cm.setCalendar(room_name,events)


                            #process all calendars to see if since the time is different there is a different status
                            for room_name in room_names:
                                calendar_client=GCalClient(cm.getCalendarId(room_name),room_name)
                                events = cm.getCalendar(room_name)
                                gcal_room_status = calendar_client.get_calendar_status_from_events(events)
                                logger.debug(gcal_room_status)
                                iot_room_status = iotc.get_room_status_retry(room_name)
                                logger.debug(iot_room_status)
                                update_if_needed(iotc,room_name,iot_room_status,gcal_room_status)
                    else :
                        done_processing=True
                cm.releaseLock()
                
        except Exception as e:
            logger.error(e)
            cm.releaseLock()
            sleep(60) #try to see if with a delay it can be retried
 

if __name__ == '__main__':
    watch_and_update_iot()   
    
    
    