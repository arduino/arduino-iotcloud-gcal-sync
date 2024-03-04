from roomstatus import RoomStatus
from datetime import datetime,timezone,timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from google.auth import default 
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.cloud import storage
import json
import socket
import mylogger
import sys
from time import time,sleep

BUCKET_NAME = "roomcalendar-config"

SCOPES = ['https://www.googleapis.com/auth/pubsub',
        'https://www.googleapis.com/auth/devstorage.read_write',
        'https://www.googleapis.com/auth/calendar',
        'https://www.googleapis.com/auth/calendar.events']

logger = mylogger.getlogger(__name__)


RETRY_DELAY_GCAL = 1
MAX_ATTEMPTS=3

class GCalClient:

    calendarId =""
    room_name="" 

    def __init__(self,calendarId,room_name):
        self.calendarId=calendarId
        self.room_name=room_name
        return


    def set_nextev_dates(self,startd,endd,tomorrow,result):
        #utility to set next events dates in right format
        #if it's within the day use only H:M otherwise put day in front
        if (startd<tomorrow):
            result.nextevstart = datetime.strftime(startd,"%H:%M")
            result.nextevend = datetime.strftime(endd,"%H:%M")
            result.nextevtm=result.nextevstart+"-"+result.nextevend
        else: 
            enddayofmonth = datetime.strftime(endd,"%Y-%m-%d")
            startdayofmonth=datetime.strftime(startd,"%Y-%m-%d")
            if (enddayofmonth!=startdayofmonth):
                #this is a multi-day event
                #and it is in progress, hence the current day is
                #fully busy
                result.nextevend = datetime.strftime(endd,"%b %d")
                result.nextevstart = datetime.strftime(startd,"%b %d")
                result.nextevtm = result.nextevstart+"-"+result.nextevend
            else:
                result.nextevstart = datetime.strftime(startd,"%Y-%m-%d %H:%M")
                result.nextevend = datetime.strftime(endd,"%H:%M")
                result.nextevtm = datetime.strftime(startd,"%a %d %b %H:%M") \
                                +"-"+result.nextevend
        

    def get_next_events(self):
        
        events=()
        attempts = 1
        retrievedok = False
        while(not retrievedok and attempts<MAX_ATTEMPTS):
            try:
                logger.info('Getting the upcoming events')
                service=self.get_gcalclient()
                now = datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time    
                events_result = service.events().list(
                        calendarId=self.calendarId,  \
                        timeMin=now,  \
                        maxResults=10, singleEvents=True,\
                        orderBy='startTime').execute()
                
                events = events_result.get('items', [])
                logger.debug(events)
                retrievedok = True
            except (RuntimeError,TimeoutError,socket.timeout) as error:
                retrievedok=False
                logger.error('GCALCLIENT: An error occurred: %s' % error)
            except Exception as e:
                retrievedok=False
                logger.error('GCALCLIENT: Unexpected error: %s', e)
            if not retrievedok:
                sleep(RETRY_DELAY_GCAL)
                attempts=attempts+1
        return events


    def get_calendar_status(self):
        result = RoomStatus()
        events = self.get_next_events()
        if not events:
            logger.debug('No upcoming events found.')
            result.valid = False 
            return result
        result = self.get_calendar_status_from_events(events)
        return result


    def get_calendar_status_from_events(self,events):
        result = RoomStatus()
        result.valid = True
        if not events:
            logger.debug('No upcoming events found.')
            return result

        # Fetches the first 2 events
        result.name=self.room_name
        evno = 0
        organizer = ""
        eventid = ""
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            status='confirmed'
            if 'attendees' in event:
                attendees = event['attendees']
                for attendee in attendees:
                    #look for the attendee with key 'self' which
                    #is the owner of this calendar
                    #and check if it was accepted
                    if 'self' in attendee:
                        status = attendee['responseStatus']
                    if "organizer" in attendee and attendee["organizer"] is True:
                        organizer = attendee["email"]
            eventid = event['id']
            summary = "Private Meeting"
            if "summary" in event:
                    summary = event["summary"]
            logger.debug(f"Event summary {summary} status: {status}")

            startd=datetime.strptime(start,"%Y-%m-%dT%H:%M:%S%z")
            endd=datetime.strptime(end,"%Y-%m-%dT%H:%M:%S%z")

            tomorrow = datetime.now(timezone.utc) \
                        .replace(hour=0, minute=0, second=0, microsecond=0) \
                        + timedelta(days=1)

            if status!='declined':
                #we will count and consider only accepted events
                evno = evno+1

            if status!='declined' and evno==1:
                #first event will tell if room is busy
                #if started before now, event is current
                if (startd<datetime.now(timezone.utc)):
                    result.busynow = RoomStatus.BUSY
                    result.curevmsg = summary
                    result.curevorganizer = organizer
                    result.curevid = eventid
                    enddayofmonth = datetime.strftime(endd,"%Y-%m-%d")
                    startdayofmonth=datetime.strftime(startd,"%Y-%m-%d")
                    if (enddayofmonth!=startdayofmonth):
                        #this is a multi-day event
                        #and it is in progress, hence the current day is
                        #fully busy
                        result.curevend = datetime.strftime(endd,"%b %d")
                        result.curevstart = datetime.strftime(startd,"%b %d")
                        result.curevtm = result.curevstart+"-"+result.curevend
                    else:
                        result.curevend = datetime.strftime(endd,"%H:%M")
                        result.curevstart = datetime.strftime(startd,"%H:%M")
                        result.curevtm = result.curevstart+"-"+result.curevend
                else:
                    #didn't start before now. will it start today ? 
                    #if starts today, calculate free until time
                    result.busynow = RoomStatus.FREE
                    if (startd<tomorrow):
                        result.curevmsg = "Free until "+datetime.strftime(startd,"%H:%M")
                    else: 
                        #else is free all day
                        result.curevmsg = "Free all day"
                            
                    #sets next events details
                    self.set_nextev_dates(startd,endd,tomorrow,result)
                    result.nextevmsg = summary
                    result.nextevorganizer=organizer 
                    result.nextevid = eventid
                    
            if status!='declined' and evno==2:
                #second event is useful only if room is busy to set next mtg details
                if result.busynow==RoomStatus.BUSY:
                    result.nextevmsg = summary
                    result.nextevid = eventid 
                    self.set_nextev_dates(startd,endd,tomorrow,result)
                    result.nextevorganizer=organizer 

        return result


    def get_gcalclient(self):
        creds,project_id = default(scopes=SCOPES)
        storage_client = storage.Client(credentials=creds)
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob("calendar_credentials.json")
        with blob.open("r") as f:
            info = json.load(f)
    
        creds = service_account.Credentials.from_service_account_info(info=info)
        creds = creds.with_scopes(scopes=SCOPES)
        logger.debug("Credentials "+creds.service_account_email) 
        service = build('calendar', 'v3', credentials=creds)
        return service

     

    def insert_instantmeeting(self,duration_mins):
        #https://developers.google.com/calendar/api/v3/reference/events/insert#examples
        startdt = datetime.utcnow()
        mins = startdt.minute
        #round minutes to 00,15,30,45
        mins = mins - (mins % 15)
        startdt = startdt.replace(minute=mins, second=0, microsecond=0)
        #round duration to multiples of 15mins
        duration_mins = int(duration_mins / 15)*15
        enddt = startdt+timedelta(minutes=duration_mins)
        startstr = datetime.strftime(startdt,"%Y-%m-%dT%H:%M:%S+0000")   
        endstr = datetime.strftime(enddt,"%Y-%m-%dT%H:%M:%S+0000")   

        try:
            logger.info('Inserting instant meeting')
            
            service=self.get_gcalclient()

            meetid = "im_"+startstr
            event = {
                'summary': '::Meeting::',
                'description': meetid,
                'start': {
                    'dateTime': startstr,
                    'timeZone': "UTC"
                },
                'end': {
                    'dateTime': endstr,
                    'timeZone': "UTC"
                }
                }
            logger.debug(event)
            event = service.events().insert(calendarId=self.calendarId, body=event).execute() 
            return True

        except (RuntimeError,TimeoutError,socket.timeout,HttpError) as error:
            logger.error('GCALCLIENT: An error occurred: %s' % error)
            return False

    def delete_meeting(self,id):
        
        try:
            service = self.get_gcalclient()
        
            logger.info('Deleting meeting '+id)
            service.events().delete(calendarId=self.calendarId, eventId=id).execute() 
            return True

        except (RuntimeError,TimeoutError,socket.timeout,HttpError) as error:
            logger.error('GCALCLIENT: An error occurred: %s' % error)
            return False
