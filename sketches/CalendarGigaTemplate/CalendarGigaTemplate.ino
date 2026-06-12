#include "arduino_secrets.h"
#include "lvgl_giga_squareline.h" // library to overwrite custom lv_conf.h file
#include "Arduino_H7_Video.h"
#include <Arduino_GigaDisplay.h>
#include "Arduino_GigaDisplayTouch.h"
// lvgl - Version: 8.3.11
#include <lvgl.h>
#include "ui.h" // Squareline studio lib export
#include "thingProperties.h" // Cloud Variables definition and other IoT cloud utilities
#include <stdio.h>  // Include stdio for sprintf
#include <WiFi.h>
#include <WiFiSSLClient.h>
#include "utilities.h"
#include <ArduinoJson.h>
WiFiSSLClient client;

char server[] = SECRET_SERVER;
char googleToken[] = SECRET_TOKEN;
char clientId[] = SECRET_CLIENT_ID;

String room_state;
bool booking_sent = false;
bool initialization = true;
Timer timer(1000);  // Instantiate Timer object

const int ITALY_TIMEZONE_OFFSET = 3600;  // Italian timezone (+1 hour)

Arduino_H7_Video Display(800, 480, GigaDisplayShield);
Arduino_GigaDisplayTouch Touch;
GigaDisplayBacklight backlight;

EventPanel currentEvent;
EventPanel nextEvent;

TimeComponents currentTime;

bool parseEventDate(String dateStr, TimeComponents &date) {
  // Attempt to parse the date string into year, month, and day components
  return sscanf(dateStr.c_str(), "%d-%d-%d", &date.year, &date.month, &date.day) == 3;
}

void setup() {
Serial.begin(115200);
 initializeCloud();
 initializeDisplay();
ui_init();
  eventsetup();
}

void loop() {
  ArduinoCloud.update();
  lv_timer_handler();
  checkAndUpdateWiFiStatus();
  
  if (WiFi.status() == WL_CONNECTED)  {
  if (timer.hasIntervalElapsed()) {
      timeclock();  // function to be called once every second
    }
    if(initialization){
      initializeUI();
      initialization = false;
    }
  }
}


// Function to change the current event title
void update_current_event_title(const char* new_title) {
  lv_textarea_set_text(ui_CurEvTitle, new_title);
}

// Function to change the current event end time
void update_current_event_end_time(const char* new_end_time) {
  lv_textarea_set_text(ui_CurEvTimeEnd, new_end_time);
}

// Function to change the width of the current event container
void update_current_event_width(uint8_t width_percent) {
  if (width_percent > 100) {
    width_percent = 100;  // Limit the width to a maximum of 100%
  }
  lv_coord_t new_width = (lv_pct(width_percent));  // Calculate the new width as a percentage
  lv_obj_set_width(ui_CurEv, new_width);           // Set the new width for the current event container
}

void debuggingPrint() {
  Serial.println("The room state is: " + get_room_state());
  Serial.println("Current Event End: " + curevend);
  Serial.println("Current Event ID: " + curevid);
  Serial.println("Current Event Message: " + curevmsg);
  Serial.println("Current Event Organizer: " + curevorganizer);
  Serial.println("Current Event Start: " + curevstart);
  Serial.println("Current Event Time: " + curevtm);
  Serial.println("Next Event End: " + nextevend);
  Serial.println("Next Event Message: " + nextevmsg);
  Serial.println("Next Event Organizer: " + nextevorganizer);
  Serial.println("Next Event Start: " + nextevstart);
  Serial.println("Next Event Time: " + nextevtm);
  Serial.println("Room Currently Busy: " + String(busynow));  // Convert int to String for concatenation
}

void onBusynowChange() {
  room_state = get_room_state();
}
void onCurevendChange() {
  room_state = get_room_state();
}
void onCurevmsgChange() {
  room_state = get_room_state();
}
void onCurevstartChange() {
  room_state = get_room_state();
}
void onCurevtmChange() {
  room_state = get_room_state();
}
void onNextevendChange() {
  room_state = get_room_state();
}
void onNextevmsgChange() {
  room_state = get_room_state();
}
void onNextevstartChange() {
  room_state = get_room_state();
}
void onNextevtmChange() {
  room_state = get_room_state();
}
void onRoomNameChange()  {
 lv_textarea_set_text(ui_RoomName, room_name.c_str());
}


// // Function to determine the state of the meeting room
// Break down get_room_state() into smaller, reusable functions
String determineRoomState() {
  if (busynow == 0) {
    if (NoMeetingNext()) {
      return "FreeFree"; // Room is free now and no meeting ahead today
    } else {
      return "FreeBusy"; // Room is free now but there is a meeting ahead today
    }
  } else { // Room is currently busy
    if (NoMeetingNext()) {
      int curevendHour = curevend.substring(0, 2).toInt(); // Extract the hour part and convert to integer
      if (curevendHour >= 19) {
        return "BusyAllDay"; // Room is busy now and ends after 19.
      } else {
        return "BusyFree";  // Room is busy now but no meeting ahead for the day
      }
    } else {
      return "BusyBusy";  // Room is busy now and there is a meeting ahead today
    }
  }
}

void prepareCurrentEventPanel() {
  currentEvent.id = curevid;
  currentEvent.title = curevmsg;
  currentEvent.timeStart = curevstart;
  currentEvent.timeEnd = curevend;
  currentEvent.isBusy = busynow;
  currentEvent.start.hour = currentEvent.timeStart.substring(0, 2).toInt();
  currentEvent.start.minute = currentEvent.timeStart.substring(3, 5).toInt();
  currentEvent.end.hour = currentEvent.timeEnd.substring(0, 2).toInt();
  currentEvent.end.minute = currentEvent.timeEnd.substring(3, 5).toInt();
  currentEvent.isPrivate = curevmsg.startsWith("Private") && curevmsg.endsWith("Meeting");
  if (curevmsg.startsWith("::") && curevmsg.endsWith("::")) {
    currentEvent.title = "Room Reserved";
    currentEvent.isDeletable = true;
  } else {
    currentEvent.organizer = curevorganizer;
    currentEvent.isDeletable = false;
  }
  NoMeetingNext() && !currentEvent.isBusy ? currentEvent.isAllDay = true : currentEvent.isAllDay = false;
  if (
      (currentEvent.isBusy && ((currentEvent.end.hour * 60 + currentEvent.end.minute) - (currentTime.hour*60 + currentTime.minute)) >= 60) 
  ||  (!currentEvent.isBusy && ((nextEvent.start.hour * 60 + nextEvent.start.minute) - (currentTime.hour*60 + currentTime.minute)) >= 60)
  ||  (currentEvent.isBusy && (currentEvent.end.hour > 17 || currentTime.hour > 17))
  )
  {
    currentEvent.isAllDay = true;
  } 
}

void prepareNextEventPanel() {
  NoMeetingNext() ? nextEvent.isBusy = false : nextEvent.isBusy = true;
  nextEvent.id = nextevid;
  nextEvent.title = nextevmsg;
  nextEvent.timeStart = nextevstart;
  nextEvent.start.hour = nextEvent.timeStart.substring(0, 2).toInt();
  nextEvent.start.minute = nextEvent.timeStart.substring(3, 5).toInt();
  nextEvent.end.hour = nextEvent.timeEnd.substring(0, 2).toInt();
  nextEvent.end.minute = nextEvent.timeEnd.substring(3, 5).toInt();
  nextEvent.timeEnd = nextevend;
  nextEvent.organizer = nextevorganizer;
  nextEvent.isPrivate = nextevmsg.startsWith("Private") && nextevmsg.endsWith("Meeting");
  
     if (currentEvent.isBusy && !NoMeetingNext() && ((nextEvent.start.hour*60 + nextEvent.start.minute) - (currentEvent.end.hour * 60 + currentEvent.end.minute)) >= 60 ){
      nextEvent.isBusy = false;
      nextEvent.title = "Available from\n" + currentEvent.timeEnd + " to " + nextEvent.timeStart;
    }  else if(currentEvent.isBusy && NoMeetingNext()){
      nextEvent.title = "Free for the rest of the day";
    }

}

// Updated get_room_state() function
String get_room_state() {
  prepareCurrentEventPanel();
  prepareNextEventPanel();
  String roomState = determineRoomState();
  if (roomState.startsWith("Busy")) {
    currentEvent.timeEnd = "Until " + curevend;
  } 
  updateCurrentEventUI();
  updateNextEventUI();
  return roomState;
}





