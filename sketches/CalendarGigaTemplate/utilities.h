struct TimeComponents{
    uint8_t year;
    uint8_t month;
    uint8_t day;
    uint8_t hour;
    uint8_t minute;
    uint8_t second;
};

struct EventPanel{
    String title;
    String timeStart;
    String timeEnd;
    String organizer;
    String id;
    TimeComponents start;
    TimeComponents end;
    bool isPrivate = false;
    bool isBusy = false;
    bool isAllDay = false;
    bool isDeletable = false;
};

struct booking_info_t{
  int duration;
  const char* title;
  bool isUntil = false;
};

booking_info_t booking_30 = { 30, "Reserving room for 15-30 mins", false };
booking_info_t booking_60 = { 60, "Reserving room for 45-60 mins", false };
booking_info_t booking_90 = { 90, "Reserving room for 75-90 mins", false };
booking_info_t booking_until = { 0, "", true };


class Timer {
  private:
    unsigned long previousMillis;
    unsigned long interval;

  public:
    Timer(unsigned long intervalMillis) {
      interval = intervalMillis;
      previousMillis = 0;
    }

    bool hasIntervalElapsed() {
      unsigned long currentMillis = millis();
      if (currentMillis - previousMillis >= interval) {
        previousMillis = currentMillis;
        return true;
      }
      return false;
    }
};

void onCurevidChange()  {
}
void onCurevorganizerChange()  {
}
void onNextevidChange()  {
}
void onNextevorganizerChange()  {
}
void onApiRoomNameChange()  {
}
void onRoomNameApiChange()  {
}
