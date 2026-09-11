
from flask import jsonify

import requests

import iot_api_client as iot
from iot_api_client.rest import ApiException
from iot_api_client.configuration import Configuration
import iot_api_client.apis.tags.things_v2_api as thingApi
import iot_api_client.apis.tags.properties_v2_api as propertiesApi
 
import mylogger
import time
from roomstatus import RoomStatus 
from time import sleep


logger = mylogger.getlogger(__name__)

MAX_ATTEMPTS=3
RETRY_DELAY_IOT=3  #avoids exceeding API rate limiting

TOKEN_MAX_ATTEMPTS=5      #token endpoint can be transiently rate-limited (429) or down (5xx)
TOKEN_RETRY_BASE_DELAY=2  #seconds; multiplied by attempt number for linear backoff
TOKEN_REQUEST_TIMEOUT=15  #seconds; avoids hanging forever on a stalled connection
 

class IotClient:
    
    PNAME_CUREVMSG = "curevmsg"
    PNAME_BUSYNOW = "busynow"
    PNAME_CUREVSTART="curevstart"
    PNAME_CUREVEND="curevend"
    PNAME_CUREVTM="curevtm"
    PNAME_CUREVORGANIZER="curevorganizer"
    PNAME_CUREVID="curevid"

    PNAME_NEXTEVMSG="nextevmsg"
    PNAME_NEXTEVSTART="nextevstart"
    PNAME_NEXTEVTM="nextevtm"
    PNAME_NEXTEVEND="nextevend"
    PNAME_NEXTEVORGANIZER="nextevorganizer"
    PNAME_NEXTEVID = "nextevid"
            
    HOST = "https://api2.arduino.cc/iot"
    TOKEN_URL = "https://api2.arduino.cc/iot/v1/clients/token"

    client_id=""
    client_secret=""
    org_id=""
    

    def __init__(self,client_id,client_secret,org_id):
        self.client_id=client_id
        self.client_secret=client_secret
        self.org_id=org_id
        self._thingid_cache = {}  # room_name -> thingid
        self._token = None
        self._token_expiry = 0


    def get_token(self):
        now = time.time()
        #reuse cached token until shortly before expiry to avoid refetching every call
        if self._token is not None and now < self._token_expiry:
            return self._token
        start = time.time()
        #fetch directly with requests (instead of oauthlib) so we control retries,
        #timeouts, and can log the real HTTP status/body when Arduino rejects us.
        #oauthlib collapses every non-token response into a generic
        #"(missing_token) Missing access token parameter." which hides the cause.
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "audience": self.HOST,
        }
        last_error = None
        for attempt in range(1, TOKEN_MAX_ATTEMPTS + 1):
            try:
                resp = requests.post(
                    self.TOKEN_URL,
                    data=data,
                    headers={"content-type": "application/x-www-form-urlencoded"},
                    timeout=TOKEN_REQUEST_TIMEOUT,
                )
                if resp.status_code == 200:
                    token = resp.json()
                    if not token.get("access_token"):
                        #200 with no token is unexpected; treat as retryable
                        raise ValueError("token response missing access_token: " + resp.text)
                    logger.debug("Token retrieval took secs=" + str(time.time() - start))
                    expires_in = token.get("expires_in", 300)
                    self._token = token
                    self._token_expiry = now + expires_in - 30  #30s safety margin
                    return token
                #non-200: log the real reason (429 rate-limit, 401 bad key, 5xx outage...)
                last_error = "HTTP {}: {}".format(resp.status_code, resp.text)
                logger.error(
                    "IOTCLIENT: token fetch failed attempt {}/{}: {}".format(
                        attempt, TOKEN_MAX_ATTEMPTS, last_error))
                #a 401/403 is a credential problem and won't fix itself by retrying
                if resp.status_code in (401, 403):
                    break
            except (requests.RequestException, ValueError) as e:
                last_error = str(e)
                logger.error(
                    "IOTCLIENT: token fetch error attempt {}/{}: {}".format(
                        attempt, TOKEN_MAX_ATTEMPTS, last_error))
            if attempt < TOKEN_MAX_ATTEMPTS:
                sleep(TOKEN_RETRY_BASE_DELAY * attempt)  #linear backoff
        raise RuntimeError("Unable to obtain IoT Cloud token: " + str(last_error))


    def init_client(self,token):
        # configure and instance the API client
        client_config = Configuration(host=self.HOST)
        client_config.access_token = token.get("access_token")
        if self.org_id!="":
            client = iot.ApiClient(client_config,header_name="X-Organization",header_value=self.org_id)
        else :
            client = iot.ApiClient(client_config)
        return client


    def get_room_status_retry(self,room_name):
        sleep(1)
        roomstatus_iot=self.get_room_status(room_name)
        attempts = 1
        while(roomstatus_iot.is_valid()==False and attempts<=MAX_ATTEMPTS):
            sleep(RETRY_DELAY_IOT)
            attempts=attempts+1
            roomstatus_iot=self.get_room_status(room_name)
        return roomstatus_iot 


    def get_room_status(self,room_name):
        token = self.get_token()
        client = self.init_client(token)
        things_api = thingApi.ThingsV2Api(client)
        properties_api = propertiesApi.PropertiesV2Api(client)
        room=RoomStatus()
        properties=[]
        md={}
        try:
            thingid = self._thingid_cache.get(room_name)
            if thingid is None:
                things = things_api.things_v2_list()
                sleep(RETRY_DELAY_IOT)
                if things.response.status!=200:
                    logger.error("IoT API returned status "+str(things.response.status))
                    room.valid=False
                    return room
                for thing in things.body:
                    if thing["name"] == room_name:
                        thingid = thing["id"]
                        self._thingid_cache[room_name] = thingid
                        logger.debug(f"Found and cached thingid for {room_name}: {thingid}")
                        break
            if thingid is None:
                logger.info(f"Did not find thing corresponding to room: {room_name}")
                room.valid=False
                return room
            room.name=room_name
            md["thingid"]=thingid
            properties=properties_api.properties_v2_list(path_params={'id': thingid})
            room.valid=True
        except ApiException as e:
            room.valid=False
            logger.error("IOTCLIENT: Exception in get room status: {}".format(e))
            return room

        #creates cache of property ids
        #in addition to copying variables in room object
        for property in properties.body:
            #print(property)
            md[property["name"]]=property["id"]
            value = property["last_value"]
            if value is None:
                value = ""
            if property["name"]==self.PNAME_CUREVMSG:
                room.curevmsg=value
            if property["name"]==self.PNAME_BUSYNOW:
                room.busynow=value
            if property["name"]==self.PNAME_CUREVSTART:
                room.curevstart=value
            if property["name"]==self.PNAME_CUREVEND:
                room.curevend=value
            if property["name"]==self.PNAME_CUREVTM:
                room.curevtm=value
            if property["name"]==self.PNAME_CUREVORGANIZER:
                room.curevorganizer=value
            if property["name"]==self.PNAME_CUREVID:
                room.curevid=value    
            if property["name"]==self.PNAME_NEXTEVMSG:
                room.nextevmsg=value
            if property["name"]==self.PNAME_NEXTEVSTART:
                room.nextevstart=value
            if property["name"]==self.PNAME_NEXTEVTM:
                room.nextevtm=value
            if property["name"]==self.PNAME_NEXTEVEND:
                room.nextevend=value
            if property["name"]==self.PNAME_NEXTEVORGANIZER:
                room.nextevorganizer=value
            if property["name"]==self.PNAME_NEXTEVID:
                room.nextevid=value    
        room.metadata=md

        return room


    def update_room_status(self,newstatus,current):
        token = self.get_token()
        client = self.init_client(token)
        properties_api = propertiesApi.PropertiesV2Api(client)
        
        tid = current.metadata.get("thingid","")
        if tid is None or tid =="":
            logger.error("ERROR: Unable to update status in iotcloud, no thingid")
            return
        
        try:
            if current.curevmsg!=newstatus.curevmsg:
                self.update_property(properties_api,current,newstatus,tid,self.PNAME_CUREVMSG)
            if current.curevstart!=newstatus.curevstart:
                self.update_property(properties_api,current,newstatus,tid,self.PNAME_CUREVSTART)
            if current.curevend!=newstatus.curevend:
                self.update_property(properties_api,current,newstatus,tid,self.PNAME_CUREVEND)
            if current.curevtm!=newstatus.curevtm:
                self.update_property(properties_api,current,newstatus,tid,self.PNAME_CUREVTM)
            if current.curevorganizer!=newstatus.curevorganizer:
                self.update_property(properties_api,current,newstatus,tid,self.PNAME_CUREVORGANIZER)
            if current.curevid!=newstatus.curevid:
                self.update_property(properties_api,current,newstatus,tid,self.PNAME_CUREVID)
            if current.nextevmsg!=newstatus.nextevmsg:
                self.update_property(properties_api,current,newstatus,tid,self.PNAME_NEXTEVMSG)
            if current.nextevstart!=newstatus.nextevstart:
                self.update_property(properties_api,current,newstatus,tid,self.PNAME_NEXTEVSTART)
            if current.nextevend!=newstatus.nextevend:
                self.update_property(properties_api,current,newstatus,tid,self.PNAME_NEXTEVEND)
            if current.nextevtm!=newstatus.nextevtm:
                self.update_property(properties_api,current,newstatus,tid,self.PNAME_NEXTEVTM) 
            if current.nextevorganizer!=newstatus.nextevorganizer:
                self.update_property(properties_api,current,newstatus,tid,self.PNAME_NEXTEVORGANIZER)
            if current.nextevid!=newstatus.nextevid:
                self.update_property(properties_api,current,newstatus,tid,self.PNAME_NEXTEVID)
            if current.busynow!=newstatus.busynow:
                self.update_property(properties_api,current,newstatus,tid,self.PNAME_BUSYNOW)

        except ApiException as e:
            logger.error("IOTCLIENT: Error in update_room_status: {}".format(e))



    def update_property(self,properties_api,current,newstatus,tid,pname):
        pid = current.metadata.get(pname,"")
        if (pname == self.PNAME_BUSYNOW):
            value = newstatus.busynow
        if (pname == self.PNAME_CUREVMSG):
            value = newstatus.curevmsg
        if (pname == self.PNAME_CUREVSTART):
            value = newstatus.curevstart
        if (pname == self.PNAME_CUREVEND):
            value = newstatus.curevend
        if (pname == self.PNAME_CUREVTM):
            value = newstatus.curevtm
        if (pname == self.PNAME_CUREVORGANIZER):
            value = newstatus.curevorganizer
        if (pname == self.PNAME_CUREVID):
            value = newstatus.curevid
        if (pname == self.PNAME_NEXTEVMSG):
            value = newstatus.nextevmsg
        if (pname == self.PNAME_NEXTEVSTART):
            value = newstatus.nextevstart
        if (pname == self.PNAME_NEXTEVEND):
            value = newstatus.nextevend
        if (pname == self.PNAME_NEXTEVTM):
            value = newstatus.nextevtm
        if (pname == self.PNAME_NEXTEVORGANIZER):
            value = newstatus.nextevorganizer
        if (pname == self.PNAME_NEXTEVID):
            value = newstatus.nextevid
        logger.info("UPDATE: "+tid+"/"+pid+"/"+pname+"="+str(value))
        params = {"id": tid, "pid": pid}
        attempts = 1
        while attempts <= MAX_ATTEMPTS:
            try:
                properties_api.properties_v2_publish(path_params=params, body={'value': value})
                sleep(1)
                return
            except ApiException as e:
                logger.error("IOTCLIENT: Error in update_property attempt {}/{}: {}".format(attempts, MAX_ATTEMPTS, e))
                attempts += 1
                if attempts <= MAX_ATTEMPTS:
                    sleep(RETRY_DELAY_IOT)
