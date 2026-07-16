//+------------------------------------------------------------------+
//|  ICTOSLevels.mq5                                                  |
//|  Draws ICT levels (order blocks, FVGs, liquidity, structure)      |
//|  computed by the ICT Trading OS app. The app's bridge writes      |
//|  MQL5\Files\ictos_levels_<SYMBOL>.csv; this indicator reads it and |
//|  draws the zones on the current chart, refreshing on a timer.      |
//|                                                                    |
//|  Install: copy to <terminal>\MQL5\Indicators\, compile (F7) in     |
//|  MetaEditor, then drag it onto the chart of the symbol you want.   |
//|  Push levels from the app: Signals page → "Draw on MT5 chart".     |
//+------------------------------------------------------------------+
#property indicator_chart_window
#property indicator_plots 0
#property strict

input int    RefreshSeconds = 5;      // how often to re-read the file
input int    ZoneBarsBack    = 120;   // how far left the zone rectangles extend
input int    ZoneBarsForward = 40;    // how far right (into the future)
input uchar  ZoneOpacity     = 25;    // 0-255 fill alpha (visual only)

string PREFIX = "ICTOS_";

int OnInit()
{
   EventSetTimer(RefreshSeconds);
   DrawAll();
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   ObjectsDeleteAll(0, PREFIX);
   ChartRedraw();
}

void OnTimer() { DrawAll(); }

int OnCalculate(const int rates_total, const int prev_calculated,
                const datetime &time[], const double &open[], const double &high[],
                const double &low[], const double &close[], const long &tick_volume[],
                const long &volume[], const int &spread[]) { return(rates_total); }

void DrawAll()
{
   ObjectsDeleteAll(0, PREFIX);

   string fname = "ictos_levels_" + Symbol() + ".csv";
   if(!FileIsExist(fname)) { ChartRedraw(); return; }

   int h = FileOpen(fname, FILE_READ | FILE_TXT | FILE_ANSI);
   if(h == INVALID_HANDLE) { ChartRedraw(); return; }

   int nbars = Bars(Symbol(), PERIOD_CURRENT);
   int back  = (ZoneBarsBack < nbars - 1) ? ZoneBarsBack : nbars - 1;
   datetime t1 = iTime(Symbol(), PERIOD_CURRENT, back);
   datetime t2 = TimeCurrent() + PeriodSeconds() * ZoneBarsForward;

   int idx = 0;
   while(!FileIsEnding(h))
   {
      string line = FileReadString(h);
      if(StringLen(line) == 0) continue;
      if(StringGetCharacter(line, 0) == '#') continue;   // meta line

      string p[];
      if(StringSplit(line, ',', p) < 6) continue;
      string kind = p[0], typ = p[1], dir = p[2], tf = p[3];
      double hi = StringToDouble(p[4]);
      double lo = StringToDouble(p[5]);
      if(hi <= 0 && lo <= 0) continue;

      color c = (dir == "bullish") ? clrLimeGreen : clrTomato;
      string nm = PREFIX + IntegerToString(idx++);

      if(kind == "line")
      {
         ObjectCreate(0, nm, OBJ_TREND, 0, t1, hi, t2, hi);
         ObjectSetInteger(0, nm, OBJPROP_COLOR, c);
         ObjectSetInteger(0, nm, OBJPROP_STYLE, STYLE_DOT);
         ObjectSetInteger(0, nm, OBJPROP_RAY_RIGHT, false);
      }
      else
      {
         ObjectCreate(0, nm, OBJ_RECTANGLE, 0, t1, hi, t2, lo);
         ObjectSetInteger(0, nm, OBJPROP_COLOR, c);
         ObjectSetInteger(0, nm, OBJPROP_FILL, true);
         ObjectSetInteger(0, nm, OBJPROP_BACK, true);
      }
      // label to the right of the zone
      string lname = nm + "_T";
      ObjectCreate(0, lname, OBJ_TEXT, 0, t2, (hi + lo) / 2.0);
      ObjectSetString(0, lname, OBJPROP_TEXT, typ + " " + tf);
      ObjectSetInteger(0, lname, OBJPROP_COLOR, c);
      ObjectSetInteger(0, lname, OBJPROP_FONTSIZE, 7);
      ObjectSetInteger(0, lname, OBJPROP_ANCHOR, ANCHOR_LEFT);
   }
   FileClose(h);
   ChartRedraw();
}
//+------------------------------------------------------------------+
