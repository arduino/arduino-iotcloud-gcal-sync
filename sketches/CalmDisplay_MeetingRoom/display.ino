
void displayUpdate() {
      gfx.fillScreen(TFT_WHITE);

  Serial.println("display update");
  Serial.println(curevmsg);

topBar();

  float CurrentCard_width;
  int CurrentCard_bg_color;
  int CurrentCard_fg_color;
  String CurrentCard_label;
  String CurrentCard_title;
  String CurrentCard_info;

  String newLine = "\n";

  int NextCard_bg_color = TFT_DARKCYAN;
  int NextCard_fg_color = TFT_WHITE;
  String NextCard_label = "Next Meeting";
  String NextCard_title = nextevmsg;
  String NextCard_info = nextevtm;

  int DisplayNext;

  gfx.setFont(&fonts::Roboto_Thin_24);
  gfx.setTextSize(1);

  if (curevmsg.substring(0, 4) == "Free") {
  // ROOM FREE
    CurrentCard_bg_color = 0xF5F5;
    CurrentCard_fg_color = TFT_BLACK;

    if (nextevstart.length() < 10) {
      //  MEETING AHEAD TODAY
      //  CurrentCard_label="Free until ";
      //  CurrentCard_info = nextevstart;
      NextCard_title = wrap(nextevmsg, 15);
      CurrentCard_title = "Vacant until " + newLine + nextevstart;
      CurrentCard_width = (w / 3) * 1.8;
      DisplayNext = 1;
    }
    else {
      //  NO MEETING AHEAD TODAY
      //  CurrentCard_label="Free all day";
      CurrentCard_label = "";
      CurrentCard_title = "Vacant all day";
      CurrentCard_info = "";
      DisplayNext = 0;
      CurrentCard_width = w;
    }
  }
  else {
  // ROOM BUSY
      CurrentCard_bg_color = TFT_BLACK;
      CurrentCard_fg_color = TFT_WHITE;
      CurrentCard_label = "Busy until";
      CurrentCard_info = curevend;
      CurrentCard_title = wrap(curevmsg,17);
    
    if (nextevstart.length() < 10) {
      DisplayNext = 1;
      NextCard_title = wrap(nextevmsg, 15);
      CurrentCard_width = (w / 3) * 1.8;
    }
    else {
      DisplayNext = 0;
      CurrentCard_width = w;

    }
  }


  gfx.setFont(&fonts::Roboto_Thin_24);
  gfx.setTextSize(2);
  gfx.setTextColor(CurrentCard_fg_color); // 文字色を黒、背景色を白に指定
  gfx.setTextDatum(middle_left);
  gfx.setTextScroll(true);

  gfx.setCursor(0, ((h - topbarHeight) / 2) + topbarHeight);
  gfx.setScrollRect(pad, topbarHeight, CurrentCard_width - pad * 2, h);
  gfx.fillRect(0, topbarHeight, CurrentCard_width, (h - topbarHeight), CurrentCard_bg_color);
  gfx.print(CurrentCard_title);

  gfx.setCursor(0, pad * 2 + topbarHeight);
  gfx.setTextSize(1);
  gfx.println(CurrentCard_label);
  gfx.println(CurrentCard_info);

  if (DisplayNext == 1) {
    gfx.setTextColor(NextCard_fg_color); // 文字色を黒、背景色を白に指定
    gfx.setScrollRect(CurrentCard_width + 20, topbarHeight, w - CurrentCard_width - (pad * 2), h);
    gfx.fillRect(CurrentCard_width, topbarHeight, w - CurrentCard_width, (h - topbarHeight), NextCard_bg_color);

    gfx.setCursor(0, pad * 2 + topbarHeight);
    gfx.println(NextCard_label);
    gfx.print(NextCard_info);


    gfx.setCursor(0, ((h - topbarHeight) / 2) + topbarHeight);
    gfx.setTextSize(1.3);
    gfx.print(NextCard_title);
  }
  else {
    // do not display next event
  }

}

void displayDisconnected() {
  topBar();
  gfx.setFont(&fonts::Roboto_Thin_24);
  gfx.setTextSize(1.6);
  gfx.setTextColor(TFT_BLACK, TFT_WHITE); // 文字色を黒、背景色を白に指定
  gfx.setTextDatum(middle_center);
  gfx.setTextScroll(true);
  gfx.drawString("Disconnected", w / 2, h / 2);
}

void displayConnecting() {
  topBar();
  gfx.setFont(&fonts::Roboto_Thin_24);
  gfx.setTextSize(1.6);
  gfx.setTextColor(TFT_BLACK, TFT_WHITE); // 文字色を黒、背景色を白に指定
  gfx.setTextDatum(middle_center);
  gfx.setTextScroll(true);
  gfx.drawString("Disconnected", w / 2, h / 2);
}

void topBar() {
  gfx.setSwapBytes(true); // Abilita la conversione dell'ordine dei byte.

  gfx.setFont(&fonts::Roboto_Thin_24);
  gfx.setTextSize(1.6);
  gfx.setTextColor(TFT_BLACK, TFT_WHITE); // 文字色を黒、背景色を白に指定
  gfx.setTextDatum(middle_left);
  gfx.setTextScroll(true);

  gfx.pushImage(w - pad - 200, topbarHeight / 2 - 12, 200, 27, IotLogo);

  gfx.setCursor(0, topbarHeight / 2);
  gfx.setScrollRect(pad, 0, w - pad, topbarHeight);
  gfx.print("Orange Room");

  gfx.setScrollRect(w - pad - 370, 0, 400, topbarHeight);
  gfx.setTextDatum(middle_right);
  gfx.setTextSize(1);
  gfx.print("Powered by");


}
