
void initializeCloud(){
  initProperties();
  ArduinoCloud.begin(ArduinoIoTPreferredConnection);  // Connect to Arduino IoT Cloud
  setDebugMessageLevel(4);                            // The default is 0 (only errors). Maximum is 4
  ArduinoCloud.printDebugInfo();
}

void initializeDisplay(){
   Display.begin();
  Touch.begin();
  backlight.begin();
}

void initializeUI() {
    lv_textarea_set_text(ui_RoomName, room_name.c_str());
    lv_obj_set_style_text_font(ui_CurEvTitle, &lv_font_montserrat_48, LV_PART_MAIN| LV_STATE_DEFAULT);
    char timeStr[6];
    sprintf(timeStr, "%02d:%02d", currentTime.hour, currentTime.minute);
    lv_textarea_set_text(ui_Clock, timeStr);  // Update the clock label
}

void eventsetup() {
  lv_obj_add_event_cb(ui_BookBtn, booking_panel, LV_EVENT_CLICKED, NULL);  /*Assign an event callback*/
  lv_obj_add_event_cb(ui_CloseBtn, close_booking, LV_EVENT_CLICKED, NULL); /*Assign an event callback*/

  lv_obj_add_event_cb(ui_CancelBtn, cancel_meeting_UI_update, LV_EVENT_PRESSED, NULL);
lv_obj_add_event_cb(ui_CancelBtn, cancelMeeting, LV_EVENT_CLICKED, &currentEvent.id);
  // Inside your ui setup function where buttons are initialized
  // Add these event callbacks
  lv_obj_add_event_cb(ui_Btn1, send_booking_UI_update, LV_EVENT_PRESSED, &booking_until);
  lv_obj_add_event_cb(ui_Btn4, send_booking_UI_update, LV_EVENT_PRESSED, &booking_30);
  lv_obj_add_event_cb(ui_Btn3, send_booking_UI_update, LV_EVENT_PRESSED, &booking_60);
  lv_obj_add_event_cb(ui_Btn2, send_booking_UI_update, LV_EVENT_PRESSED, &booking_90);

  lv_obj_add_event_cb(ui_Btn1, send_booking, LV_EVENT_CLICKED, &booking_until);
  lv_obj_add_event_cb(ui_Btn4, send_booking, LV_EVENT_CLICKED, &booking_30);
  lv_obj_add_event_cb(ui_Btn3, send_booking, LV_EVENT_CLICKED, &booking_60);
  lv_obj_add_event_cb(ui_Btn2, send_booking, LV_EVENT_CLICKED, &booking_90);
}