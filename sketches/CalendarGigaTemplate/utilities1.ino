
TimeComponents timeclock() {
  time_t rawtime;
  struct tm* info;
  time(&rawtime);
  rawtime += ITALY_TIMEZONE_OFFSET;  // Adjust for Italian timezone (+1 hour)
  info = localtime(&rawtime);

  // Format the time into a string
  char timeStr[6];  // Buffer to hold time string, e.g., "HH:MM"
  sprintf(timeStr, "%02d:%02d", info->tm_hour, info->tm_min);
  // Update the clock label only when seconds are 01
  if (info->tm_sec == 1) {
    lv_textarea_set_text(ui_Clock, timeStr);  // Update the clock label
    debuggingPrint();
  } else if (info->tm_min == 1) {
    if (info->tm_hour < 20 || info->tm_hour > 7) {
      backlight.set(100);
    } else {
      backlight.set(0);
    }
  }
  currentTime.month = info->tm_mon + 1;
  currentTime.day = info->tm_mday;
  currentTime.hour = info->tm_hour;
  currentTime.minute = info->tm_min;
  currentTime.second = info->tm_sec;

  return currentTime;
}

// Function to parse time in "HH:MM" format and convert it to minutes since midnight
int timeToMinutes(const String& timeStr) {
  int hour = timeStr.substring(0, 2).toInt();
  int minute = timeStr.substring(3, 5).toInt();
  return hour * 60 + minute;
}

// Function to calculate the time difference
int calculateTimeDifference(const String& nextEventStartTime) {
  // Get the current time
  time_t rawtime;
  struct tm* info;
  time(&rawtime);
  rawtime += 3600;  // Adjust for timezone if needed
  info = localtime(&rawtime);

  // Format current time as a string "HH:MM"
  char currentTimeStr[6];
  sprintf(currentTimeStr, "%02d:%02d", info->tm_hour, info->tm_min);

  // Convert current time and next event start time to minutes
  int currentTimeInMinutes = timeToMinutes(currentTimeStr);
  int nextEventTimeInMinutes = timeToMinutes(nextEventStartTime);

  // Calculate the difference
  int timeDiff = nextEventTimeInMinutes - currentTimeInMinutes;

  // If the difference is negative, it means the next event is on the next day
  if (timeDiff < 0) {
    timeDiff += 24 * 60;  // Add 24 hours worth of minutes
  }
  Serial.println("nextevmin " + nextEventTimeInMinutes);
  Serial.println("curtevmin " + currentTimeInMinutes);
  Serial.println("timediff " + timeDiff);

  return timeDiff;
}


String parseOrganizerName(const String& email) {
  int splitIndex = email.indexOf('.');  // Find the position of the dot
  if (splitIndex == -1) return "";      // Return empty if the format is not as expected

  String firstName = email.substring(0, splitIndex);                      // Extract first name
  String lastName = email.substring(splitIndex + 1, email.indexOf('@'));  // Extract last name

  // Capitalize the first letter of the first and last name
  firstName.setCharAt(0, firstName.charAt(0) & 0x5f);  // Convert to uppercase
  lastName.setCharAt(0, lastName.charAt(0) & 0x5f);    // Convert to uppercase

  return firstName + ". " + lastName;  // Combine and return the formatted name
}




void updateButtonMatrix() {
  int timeDiff;
  if(NoMeetingNext()){
      timeDiff = calculateTimeDifference("23:59");
  }
  else{
      timeDiff = calculateTimeDifference(nextevstart);
  }
  String untilString;

  // Determine the number of buttons to show based on timeDiff
  int buttonsToShow = (timeDiff / 15)+1;
  if(room_state=="FreeFree"){
  untilString = "ALL DAY";  // Concatenation using Arduino String
  }
  else{
  untilString = "UNTIL " + nextevstart;  // Concatenation using Arduino String
  }

  // Hide all buttons initially
  lv_obj_add_flag(ui_Btn1, LV_OBJ_FLAG_HIDDEN);
  lv_obj_add_flag(ui_Btn2, LV_OBJ_FLAG_HIDDEN);
  lv_obj_add_flag(ui_Btn3, LV_OBJ_FLAG_HIDDEN);
  lv_obj_add_flag(ui_Btn4, LV_OBJ_FLAG_HIDDEN);

if(buttonsToShow < 2){
lv_textarea_set_text(ui_BookingTitle, "Book now"); 
} else{
  lv_textarea_set_text(ui_BookingTitle, "Book now for"); 
}

  // Show buttons based on buttonsToShow
  if (buttonsToShow > 0) lv_obj_clear_flag(ui_Btn1, LV_OBJ_FLAG_HIDDEN);
  if (buttonsToShow > 2) lv_obj_clear_flag(ui_Btn4, LV_OBJ_FLAG_HIDDEN);
  if (buttonsToShow > 4) lv_obj_clear_flag(ui_Btn3, LV_OBJ_FLAG_HIDDEN);
  if (buttonsToShow > 6) lv_obj_clear_flag(ui_Btn2, LV_OBJ_FLAG_HIDDEN);

  lv_label_set_text(ui_BtnLabel1, untilString.c_str());
}

void reserveMeetingRoom(int durationMins) {
  if (client.connect(server, 443)) {
    Serial.println("Connected to server");
    // Prepare JSON payload
    DynamicJsonDocument doc(256);
    doc["room_name"] = room_name_api; //"jupiter_room";
    doc["client_id"] = clientId;
    doc["duration_mins"] = durationMins + 14;
    String payload;
    serializeJson(doc, payload);

    // Prepare and send POST request
    client.println("POST /meetings HTTP/1.1\r");
    client.print("Host: ");
    client.println(server + String("\r"));
    client.println("Content-Type: application/json\r");
    client.print("Content-Length: ");
    client.println(payload.length());
    client.println("Connection: close\r");
    client.print("Authorization: Bearer ");
    client.println(googleToken + String("\r"));
    client.println();       // End of headers
    client.print(payload);  // Send payload
    Serial.println(payload);
    Serial.println(payload.length());
    Serial.println("Request sent");

    // Wait for the server's response
    Serial.println("Waiting for response...");
    while (client.connected()) {
      if (client.available()) {
        char c = client.read();
        Serial.write(c);
      }
    }

    Serial.println("\nResponse complete");
    client.stop();  // Close the connection
    booking_sent = true;
  } else {
    Serial.println("Connection failed");
  }
}

static void cancelMeeting(lv_event_t* e) {
  String* meetingIdPtr = (String*)lv_event_get_user_data(e);
  if (client.connect(server, 443)) {
    String meetingID = *meetingIdPtr;
    Serial.println("Connected to server");

    // Prepare JSON payload
    DynamicJsonDocument doc(256);
    doc["room_name"] = room_name_api; //"jupiter_room";
    doc["client_id"] = clientId;
    String payload;
    serializeJson(doc, payload);

    // Prepare and send DELETE request
    client.println("DELETE /meeting/" + meetingID + " HTTP/1.1\r");
    client.print("Host: ");
    client.println(server + String("\r"));
    client.println("Content-Type: application/json\r");
    client.print("Content-Length: ");
    client.println(payload.length());
    client.println("Connection: close\r");
    client.print("Authorization: Bearer ");
    client.println(googleToken + String("\r"));
    client.println();       // End of headers
    client.print(payload);  // Send payload

    Serial.println("Request sent");

    // Wait for the server's response
    Serial.println("Waiting for response...");
    while (client.connected()) {
      if (client.available()) {
        char c = client.read();
        Serial.write(c);
      }
    }

    Serial.println("\nResponse complete");
    client.stop();  // Close the connection
  } else {
    Serial.println("Connection failed");
  }
}



// Helper function to convert minutes back to a time string "HH:MM"
String minutesToTimeStr(int minutes) {
  char timeStr[6];
  sprintf(timeStr, "%02d:%02d", minutes / 60, minutes % 60);
  return String(timeStr);
}

// Function to subtract 15 minutes from the next event start time
String subtractFifteenMinutes(const String& nextEventStartTime) {
  int nextEventTimeInMinutes = timeToMinutes(nextEventStartTime);

  // Subtract 15 minutes
  int adjustedTimeInMinutes = nextEventTimeInMinutes - 15;

  // Handle case where subtraction results in a time on the previous day
  if (adjustedTimeInMinutes < 0) {
    adjustedTimeInMinutes += 24 * 60;  // Add 24 hours worth of minutes
  }

  return minutesToTimeStr(adjustedTimeInMinutes);
}

static void booking_panel(lv_event_t* event) {
  lv_obj_clear_flag(ui_Booking, LV_OBJ_FLAG_HIDDEN);
}

static void close_booking(lv_event_t* event) {
  lv_obj_add_flag(ui_Booking, LV_OBJ_FLAG_HIDDEN);
}

static void cancel_meeting_UI_update(lv_event_t* event) {
  update_current_event_title("Canceling meeting");
  update_current_event_end_time("Waiting for Google response...");
  lv_obj_add_flag(ui_CancelBtn, LV_OBJ_FLAG_HIDDEN);
}


static void send_booking_UI_update(lv_event_t* e) {
  booking_info_t* info = (booking_info_t*)lv_event_get_user_data(e);
  update_current_event_end_time("Waiting for Google response...");
  lv_obj_add_flag(ui_CancelBtn, LV_OBJ_FLAG_HIDDEN);
  lv_obj_add_flag(ui_BookBtn, LV_OBJ_FLAG_HIDDEN);
  lv_obj_add_flag(ui_Booking, LV_OBJ_FLAG_HIDDEN);
  if (info->isUntil) {
    if (room_state == "FreeFree") {
      String untilString = "Reserving room for the rest of the day";
      update_current_event_title(untilString.c_str());
    } else {
      String untilString = "Reserving room until " + nextevstart;
      update_current_event_title(untilString.c_str());
    }
  } else {
    update_current_event_title(info->title);
  }
}

static void send_booking(lv_event_t* e) {
  booking_info_t* info = (booking_info_t*)lv_event_get_user_data(e);
  if (info->isUntil) {
    int duration;
    if (room_state == "FreeFree") {
      if(currentTime.hour < 18){
      duration = calculateTimeDifference("20:00");
      }
      else{
      duration = calculateTimeDifference("23:59")+1;
      }
      reserveMeetingRoom(duration);
    } else {
      duration = calculateTimeDifference(nextevstart);
      reserveMeetingRoom(duration);
    }
  } else {
    reserveMeetingRoom(info->duration);
  }
}

void updateCurrentEventUI() {
    // Set colors and styles depending on isBusy and isAllDay
uint32_t bgColor;
uint32_t textColor;
uint8_t widthPercent;
const lv_font_t* titleSize;
    lv_textarea_set_text(ui_CurEvTitle, currentEvent.title.c_str());
    lv_textarea_set_text(ui_CurEvTimeEnd, currentEvent.timeEnd.c_str());
    lv_textarea_set_text(ui_CurEvOrganizer, parseOrganizerName(currentEvent.organizer).c_str());
    
    if(currentEvent.isBusy){
      bgColor = 0x008184;
      textColor = 0xF7F9F9;
      lv_obj_clear_flag(ui_CurEvTimeEnd, LV_OBJ_FLAG_HIDDEN);  // Make the cancel button visible
      lv_obj_add_flag(ui_BookBtn, LV_OBJ_FLAG_HIDDEN);  // Make the cancel button visible

      if(currentEvent.isDeletable){
        lv_obj_add_flag(ui_CurEvOrganizer, LV_OBJ_FLAG_HIDDEN);    // Hide the cancel button
        lv_obj_clear_flag(ui_CancelBtn, LV_OBJ_FLAG_HIDDEN);  // Make the cancel button visible
      }
      else{
        currentEvent.organizer.isEmpty()||currentEvent.isPrivate ? lv_obj_add_flag(ui_CurEvOrganizer, LV_OBJ_FLAG_HIDDEN) : lv_obj_clear_flag(ui_CurEvOrganizer, LV_OBJ_FLAG_HIDDEN);  // Make the curevorganizer visible
      lv_obj_add_flag(ui_CancelBtn, LV_OBJ_FLAG_HIDDEN);    // Hide the cancel button
      }
    }
    else{
      bgColor = 0xECF1F1;
      textColor = 0x008184;
      lv_obj_clear_flag(ui_BookBtn, LV_OBJ_FLAG_HIDDEN);  // Make the book button visible
      lv_obj_add_flag(ui_CancelBtn, LV_OBJ_FLAG_HIDDEN);    // Hide the cancel button
      updateButtonMatrix();
      lv_obj_add_flag(ui_CurEvOrganizer, LV_OBJ_FLAG_HIDDEN);  // Make the curevorg invisible
      lv_obj_add_flag(ui_CurEvTimeEnd, LV_OBJ_FLAG_HIDDEN);  // Make the curevend invisible
    }
  
    if(currentEvent.isAllDay){
      widthPercent = 100;
    }
    else{
      widthPercent = 60;
    }

    titleSize =  &lv_font_montserrat_48;
    lv_coord_t new_width = (lv_pct(widthPercent)); // Calculate the new width as a percentage

    lv_obj_set_style_bg_color(ui_CurEv, lv_color_hex(bgColor), LV_PART_MAIN | LV_STATE_DEFAULT);
    lv_obj_set_style_text_color(ui_CurEvTitle, lv_color_hex(textColor), LV_PART_MAIN | LV_STATE_DEFAULT);
    lv_obj_set_style_text_color(ui_CurEvTimeEnd, lv_color_hex(textColor), LV_PART_MAIN | LV_STATE_DEFAULT);
    lv_obj_set_width(ui_CurEv, new_width); // Set the new width for the current event container

}

void updateNextEventUI() {
    // Set colors based on whether the room is busy or free for the next event
    uint32_t bgColor;
    uint32_t textColor;
    // Set the text content for the next event UI elements
    lv_textarea_set_text(ui_NextEvTitle, nextEvent.title.c_str());
    lv_textarea_set_text(ui_NextEvTimeStart, nextEvent.timeStart.c_str());
    lv_textarea_set_text(ui_NextEvTimeEnd, nextEvent.timeEnd.c_str());
    lv_textarea_set_text(ui_NextEvOrganizer, parseOrganizerName(nextEvent.organizer).c_str());

    if(nextEvent.isBusy) {
        // Define colors for when the next event indicates the room is busy
        bgColor = 0x006D70; // Darker background for busy
        textColor = 0xF7F9F9; // Light text for contrast
       // lv_obj_clear_flag(ui_NextEvOrganizer, LV_OBJ_FLAG_HIDDEN);
        lv_obj_clear_flag(ui_NextGroup, LV_OBJ_FLAG_HIDDEN);
        nextEvent.organizer.isEmpty()||nextEvent.isPrivate ? lv_obj_add_flag(ui_NextEvOrganizer, LV_OBJ_FLAG_HIDDEN) : lv_obj_clear_flag(ui_NextEvOrganizer, LV_OBJ_FLAG_HIDDEN);  

    } else {
        // Define colors for when the next event indicates the room is free
        bgColor = 0xECF1F1; // Lighter background for free
        textColor = 0x008184; // Darker text for readability
        lv_obj_add_flag(ui_NextEvOrganizer, LV_OBJ_FLAG_HIDDEN);
        lv_obj_add_flag(ui_NextGroup, LV_OBJ_FLAG_HIDDEN);
      //  lv_textarea_set_text(ui_NextEvTitle, String("Free for the rest of the day").c_str());
    }
    // Update the background and text color of the next event panel
    lv_obj_set_style_bg_color(ui_Next, lv_color_hex(bgColor), LV_PART_MAIN | LV_STATE_DEFAULT);
    lv_obj_set_style_text_color(ui_NextEvTitle, lv_color_hex(textColor), LV_PART_MAIN | LV_STATE_DEFAULT);
    lv_obj_set_style_text_color(ui_NextEvTimeStart, lv_color_hex(textColor), LV_PART_MAIN | LV_STATE_DEFAULT);
    lv_obj_set_style_text_color(ui_NextEvTimeEnd, lv_color_hex(textColor), LV_PART_MAIN | LV_STATE_DEFAULT);
}

void checkAndUpdateWiFiStatus() {
  if (WiFi.status() != WL_CONNECTED) {
    currentEvent.title = "CONNECTING";
    currentEvent.timeEnd = "Waiting for WiFi network...";
    currentEvent.organizer = "";
    currentEvent.isAllDay = true;
    currentEvent.isBusy = true;
    updateCurrentEventUI();
  }
}

bool NoMeetingNext() {
  // Validate input strings for emptiness, which could indicate incorrect or missing data
  if (nextevtm.length() == 0 || nextevtm.length() == 0) {
    // Assume a meeting might be ahead if inputs are invalid, to err on the side of caution
    return false;
  }
  // Check if the first character of nextEventTime is a letter; this indicates no meeting ahead
  if (!isAlpha(nextevtm.charAt(0))) {
    return false; // A non-letter start suggests a meeting is indeed scheduled
  }
  // Initialize a Date struct for the event's date and parse the event start date
  TimeComponents eventDate;
  if (!parseEventDate(nextevstart, eventDate)) {
    // If the date cannot be parsed, assume the format is incorrect and a meeting might be ahead
    return false;
  }
  // Compare the event date against the current date to determine if they are on the same day
  bool isDifferentDay = (currentTime.day != eventDate.day || currentTime.month != eventDate.month);
  return isDifferentDay; // Return true if no meeting is ahead, false if on the same day
}
