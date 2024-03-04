
from flask import jsonify

from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session

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


    def get_token(self):
        start = time.time()
        oauth_client = BackendApplicationClient(client_id=self.client_id)
        oauth = OAuth2Session(client=oauth_client)
        token = oauth.fetch_token(
            token_url=self.TOKEN_URL,
            client_id=self.client_id,
            client_secret=self.client_secret,
            include_client_id=True,
            audience=self.HOST
        )
        logger.debug("Token retrieval took secs=" +str(time.time()-start))
        return token


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
        sleep(RETRY_DELAY_IOT)
        roomstatus_iot=self.get_room_status(room_name)
        attempts = 1
        while(roomstatus_iot.is_valid()==False and attempts<MAX_ATTEMPTS):
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
            things = things_api.things_v2_list()
            sleep(RETRY_DELAY_IOT)
            if things.response.status==200:
                for thing in things.body: 
                    if thing["name"] == room_name:
                        logger.debug(f"Found thing: {thing}")
                        room.name=room_name
                        md["thingid"]=thing["id"]
                        properties=properties_api.properties_v2_list(path_params={'id': thing["id"]})  
                room.valid=True
            else:
                logger.warn("IoT API returned status "+things.response.status)
                room.valid=False
        except ApiException as e:
            room.valid=False 
            logger.error("IOTCLIENT: Exception in get room status: {}".format(e))
            return room

        if room.name!=room_name:
            #didn't find any thing with this room name
            logger.warn(f"Did not find thing corresponding to room: {room_name}")
            room.valid=False
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
        try:
            logger.info("UPDATE: "+tid+"/"+pid+"/"+pname+"="+str(value))
            params = dict()
            params["id"]=tid
            params["pid"]=pid
            properties_api.properties_v2_publish( path_params=params, body={'value':value} )
            sleep(RETRY_DELAY_IOT)
        except ApiException as e:
            logger.error("IOTCLIENT: Error in update_property: {}".format(e))
