String wrap(String s, int limit) {

  int space = 0;
  int i = 0;
  int line = 0;
  while (i < s.length()) {

    if (s.substring(i, i + 1) == " ") {
      space = i;
    }
    if (line > limit - 1) {
      s = s.substring(0, space) + "~" + s.substring(space + 1);
      line = 0;
    }
    i++; line++;
  }
  s.replace("~", "\n");
  return s;
}
