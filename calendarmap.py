import json
from threading import Lock

class CalendarMap:
    
    calendars = {}    
    ids = {}           
    lock = Lock()
    wakeup_events=[]

    REASON_REGULAR="WAKEUP_REGULAR"
    REASON_CALENDARCHANGE="WAKEUP_CALENDARCHANGE"

    def acquireLock(self):
        self.lock.acquire()
        return
    
    def releaseLock(self):
        self.lock.release()
        return


    def pushWakeup(self,reason,calendar_name):
        self.wakeup_events.append({ "reason": reason, "calendar_name":calendar_name})

    def popWakeup(self):
        if self.wakeup_events:
            return self.wakeup_events.pop() 
        else:
            return {}
    
    
   
    
    def setCalendar(self,name,value):
        self.calendars[name]=value
        return 


    def getCalendar(self,name):
        if name in self.calendars:
            return self.calendars[name]
        return ""

    def setCalendarId(self,name,value):
        self.ids[name]=value
        return 
    
    def getCalendarId(self,name):
        if name in self.ids:
            return self.ids[name]
        return ""


    def __init__(self):
         
         return
    

    def toJSON(self):
        return json.dumps(self.__dict__)


    def is_valid(self):
        return self.valid
 

    def __str__(self): 
        return self.__dict__.__str__()


     