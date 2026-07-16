//+------------------------------------------------------------------+
//|  ICTOSLevels.mq5                                                  |
//|  Draws ICT levels computed by ICT Trading OS on the chart:        |
//|   • Order Blocks / Fair Value Gaps  → labelled colored rectangles |
//|   • Market structure / liquidity     → labelled dotted lines      |
//|   • Dealing range + Fibonacci grid   → EQ, OTE (buy/sell) zones    |
//|  Reads MQL5\Files\ictos_levels_<SYMBOL>.csv written by the bridge. |
//|  Install: copy to MQL5\Indicators\, compile (F7), drag on chart.  |
//+------------------------------------------------------------------+
#property indicator_chart_window
#property indicator_plots 0
#property strict

input int  RefreshSeconds  = 5;     // re-read the file every N seconds
input int  ZoneBarsBack     = 150;  // how far left objects extend
input int  ZoneBarsForward  = 50;   // how far right (into the future)
input bool ShowFibonacci    = true; // draw the dealing-range fib grid + OTE
input bool ShowLabels       = true; // text labels on every object

string PFX = "ICTOS_";
int    g_id = 0;

//--- meta parsed from the file
string M_symbol = "";
double M_price = 0, M_rangeHigh = 0, M_rangeLow = 0, M_eq = 0;
string M_pd = "";

int OnInit() { EventSetTimer(RefreshSeconds); DrawAll(); return(INIT_SUCCEEDED); }
void OnDeinit(const int reason) { EventKillTimer(); ObjectsDeleteAll(0, PFX); ChartRedraw(); }
void OnTimer() { DrawAll(); }
int  OnCalculate(const int r, const int p, const datetime &t[], const double &o[],
                 const double &h[], const double &l[], const double &c[],
                 const long &tv[], const long &v[], const int &s[]) { return(r); }

//--- helpers -------------------------------------------------------
datetime LeftTime()  { int n=Bars(_Symbol,_Period); int b=(ZoneBarsBack<n-1)?ZoneBarsBack:n-1; return iTime(_Symbol,_Period,b); }
datetime RightTime() { return TimeCurrent() + PeriodSeconds()*ZoneBarsForward; }

void Label(string name, datetime t, double price, string text, color col, int size=8, ENUM_ANCHOR_POINT anc=ANCHOR_LEFT)
{
   if(!ShowLabels) return;
   ObjectCreate(0, name, OBJ_TEXT, 0, t, price);
   ObjectSetString(0, name, OBJPROP_TEXT, text);
   ObjectSetInteger(0, name, OBJPROP_COLOR, col);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, size);
   ObjectSetInteger(0, name, OBJPROP_ANCHOR, anc);
}

void HLine(string name, double price, color col, ENUM_LINE_STYLE style, int width=1)
{
   datetime t1=LeftTime(), t2=RightTime();
   ObjectCreate(0, name, OBJ_TREND, 0, t1, price, t2, price);
   ObjectSetInteger(0, name, OBJPROP_COLOR, col);
   ObjectSetInteger(0, name, OBJPROP_STYLE, style);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, width);
   ObjectSetInteger(0, name, OBJPROP_RAY_RIGHT, false);
}

void Band(string name, double hi, double lo, color col)
{
   datetime t1=LeftTime(), t2=RightTime();
   ObjectCreate(0, name, OBJ_RECTANGLE, 0, t1, hi, t2, lo);
   ObjectSetInteger(0, name, OBJPROP_COLOR, col);
   ObjectSetInteger(0, name, OBJPROP_FILL, true);
   ObjectSetInteger(0, name, OBJPROP_BACK, true);
}

//--- legend (fixed screen corner) ---------------------------------
void Legend()
{
   string rows[5];
   rows[0] = M_symbol + "  ICT OS Levels";
   rows[1] = "▮ green = bullish   ▮ red = bearish";
   rows[2] = "box = OB/FVG   dotted = structure/liquidity";
   rows[3] = "blue = fib   gold = OTE   yellow = equilibrium";
   rows[4] = (M_pd!="" ? ("price is in "+M_pd) : "");
   for(int i=0;i<5;i++)
   {
      if(StringLen(rows[i])==0) continue;
      string nm = PFX+"LEG"+IntegerToString(i);
      ObjectCreate(0, nm, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, nm, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, nm, OBJPROP_XDISTANCE, 8);
      ObjectSetInteger(0, nm, OBJPROP_YDISTANCE, 18 + i*15);
      ObjectSetString(0, nm, OBJPROP_TEXT, rows[i]);
      ObjectSetInteger(0, nm, OBJPROP_FONTSIZE, i==0?9:8);
      ObjectSetInteger(0, nm, OBJPROP_COLOR, i==0?clrGold:clrSilver);
   }
}

//--- fibonacci grid off the dealing range -------------------------
void FibLevel(double pct, string tag, color col, int width=1)
{
   double price = M_rangeLow + (M_rangeHigh - M_rangeLow) * pct;
   string nm = PFX+"FIB"+DoubleToString(pct,3);
   HLine(nm, price, col, STYLE_DASH, width);
   Label(nm+"_T", RightTime(), price, tag+"  "+DoubleToString(price,_Digits), col, 8, ANCHOR_LEFT);
}

void DrawFibonacci()
{
   if(!ShowFibonacci || M_rangeHigh<=M_rangeLow) return;
   double rng = M_rangeHigh - M_rangeLow;
   // OTE zones (62-79% of the retracement): sell zone in premium (upper),
   // buy zone in discount (lower).
   Band(PFX+"OTE_SELL", M_rangeLow+rng*0.786, M_rangeLow+rng*0.618, C'60,50,10');
   Label(PFX+"OTE_SELL_T", LeftTime(), M_rangeLow+rng*0.70, "Premium OTE (sell)", clrGold, 8, ANCHOR_LEFT);
   Band(PFX+"OTE_BUY",  M_rangeLow+rng*0.382, M_rangeLow+rng*0.214, C'10,50,20');
   Label(PFX+"OTE_BUY_T", LeftTime(), M_rangeLow+rng*0.30, "Discount OTE (buy)", clrLimeGreen, 8, ANCHOR_LEFT);
   // Fib lines
   FibLevel(0.0,  "0% (low)",  clrSteelBlue);
   FibLevel(0.236,"23.6%",     clrSteelBlue);
   FibLevel(0.382,"38.2%",     clrSteelBlue);
   FibLevel(0.618,"61.8%",     clrSteelBlue);
   FibLevel(0.786,"78.6%",     clrSteelBlue);
   FibLevel(1.0,  "100% (high)",clrSteelBlue);
   // Equilibrium (50%) — highlighted
   double eq = (M_eq>0)? M_eq : (M_rangeLow+rng*0.5);
   HLine(PFX+"EQ", eq, clrYellow, STYLE_SOLID, 1);
   Label(PFX+"EQ_T", RightTime(), eq, "EQUILIBRIUM 50%  "+DoubleToString(eq,_Digits), clrYellow, 8, ANCHOR_LEFT);
}

//--- main ----------------------------------------------------------
void DrawAll()
{
   ObjectsDeleteAll(0, PFX);
   g_id = 0;

   string fname = "ictos_levels_" + _Symbol + ".csv";
   if(!FileIsExist(fname)) { ChartRedraw(); return; }
   int fh = FileOpen(fname, FILE_READ|FILE_TXT|FILE_ANSI);
   if(fh == INVALID_HANDLE) { ChartRedraw(); return; }

   while(!FileIsEnding(fh))
   {
      string line = FileReadString(fh);
      if(StringLen(line)==0) continue;

      string p[];
      int n = StringSplit(line, ',', p);
      if(n<1) continue;

      if(p[0] == "#META")
      {
         if(n>=7){ M_symbol=p[1]; M_price=StringToDouble(p[2]); M_rangeHigh=StringToDouble(p[3]);
                   M_rangeLow=StringToDouble(p[4]); M_eq=StringToDouble(p[5]); M_pd=p[6]; }
         continue;
      }
      if(n<6) continue;

      string kind=p[0], typ=p[1], dir=p[2], tf=p[3];
      double hi=StringToDouble(p[4]), lo=StringToDouble(p[5]);
      if(hi<=0 && lo<=0) continue;

      bool bull = (dir=="bullish");
      color col = bull ? clrLimeGreen : clrTomato;
      string arrow = bull ? "▲" : "▼";
      string full = TypeName(typ)+" "+arrow+" "+tf;
      string nm = PFX+"Z"+IntegerToString(g_id++);

      if(kind=="line")
      {
         HLine(nm, hi, col, STYLE_DOT, 1);
         Label(nm+"_T", LeftTime(), hi, full+"  "+DoubleToString(hi,_Digits), col, 8, ANCHOR_LEFT);
      }
      else
      {
         Band(nm, hi, lo, bull ? C'12,45,25' : C'55,18,18');
         Label(nm+"_T", LeftTime(), (hi+lo)/2.0, full, col, 8, ANCHOR_LEFT);
      }
   }
   FileClose(fh);

   DrawFibonacci();
   Legend();
   ChartRedraw();
}

string TypeName(string t)
{
   if(t=="OB")        return "Order Block";
   if(t=="FVG")       return "Fair Value Gap";
   if(t=="LIQUIDITY") return "Liquidity";
   if(t=="MSS")       return "Structure Shift";
   return t;
}
//+------------------------------------------------------------------+
