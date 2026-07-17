//+------------------------------------------------------------------+
//|  ICTOSLevels.mq5                                                  |
//|  Draws ICT Trading OS levels on the chart — CLEANLY:              |
//|   • by default shows ONLY zones for THIS chart's timeframe, so    |
//|     5m/15m/1h/4h charts each stay uncluttered;                    |
//|   • bright colour-coded zones with clear labels;                  |
//|   • dealing-range Fibonacci grid, equilibrium + OTE (buy/sell).   |
//|  Reads MQL5\Files\ictos_levels_<SYMBOL>.csv (written by the bridge)|
//+------------------------------------------------------------------+
#property indicator_chart_window
#property indicator_plots 0
#property strict

input bool MatchChartTimeframe = true;  // show only zones for THIS chart's TF
input int  MaxZones            = 6;      // cap zones drawn (nearest first)
input bool ShowFibonacci       = true;   // dealing-range fib grid + OTE + EQ
input bool ShowLabels          = true;
input bool ShowChecklist       = true;   // top-right how-to-read-it panel
input int  ZoneBarsBack        = 120;
input int  ZoneBarsForward     = 30;

string PFX = "ICTOS_";
int    g_id = 0;

string M_symbol=""; double M_price=0,M_rangeHigh=0,M_rangeLow=0,M_eq=0; string M_pd="";

int OnInit(){ EventSetTimer(5); DrawAll(); return(INIT_SUCCEEDED); }
void OnDeinit(const int r){ EventKillTimer(); ObjectsDeleteAll(0,PFX); ChartRedraw(); }
void OnTimer(){ DrawAll(); }
int OnCalculate(const int r,const int p,const datetime &t[],const double &o[],const double &h[],
                const double &l[],const double &c[],const long &tv[],const long &v[],const int &s[]){return r;}

//--- helpers -------------------------------------------------------
datetime LeftTime(){ int n=Bars(_Symbol,_Period); int b=(ZoneBarsBack<n-1)?ZoneBarsBack:n-1; return iTime(_Symbol,_Period,b); }
datetime RightTime(){ return TimeCurrent()+PeriodSeconds()*ZoneBarsForward; }

string ChartTF()
{
   switch(_Period){
      case PERIOD_M5:  return "5m";
      case PERIOD_M15: return "15m";
      case PERIOD_H1:  return "1h";
      case PERIOD_H4:  return "4h";
   }
   return "";
}

string TypeName(string t)
{
   if(t=="OB")        return "Order Block";
   if(t=="FVG")       return "Fair Value Gap";
   if(t=="LIQUIDITY") return "Liquidity";
   if(t=="MSS")       return "Structure Shift";
   return t;
}

void Label(string name,datetime t,double price,string text,color col,int size=9)
{
   if(!ShowLabels) return;
   ObjectCreate(0,name,OBJ_TEXT,0,t,price);
   ObjectSetString(0,name,OBJPROP_TEXT,text);
   ObjectSetInteger(0,name,OBJPROP_COLOR,col);
   ObjectSetInteger(0,name,OBJPROP_FONTSIZE,size);
   ObjectSetInteger(0,name,OBJPROP_ANCHOR,ANCHOR_LEFT);
}

void HLine(string name,double price,color col,ENUM_LINE_STYLE st,int w=1)
{
   ObjectCreate(0,name,OBJ_TREND,0,LeftTime(),price,RightTime(),price);
   ObjectSetInteger(0,name,OBJPROP_COLOR,col);
   ObjectSetInteger(0,name,OBJPROP_STYLE,st);
   ObjectSetInteger(0,name,OBJPROP_WIDTH,w);
   ObjectSetInteger(0,name,OBJPROP_RAY_RIGHT,false);
}

void Band(string name,double hi,double lo,color bright,color tint)
{
   // Highlighted zone = subtle filled tint BEHIND the candles + a crisp bright
   // outline on top. MT5 rectangles carry a single colour, so we draw two:
   // one filled (tint, back) for the highlight and one outline (bright, front).
   ObjectCreate(0,name,OBJ_RECTANGLE,0,LeftTime(),hi,RightTime(),lo);
   ObjectSetInteger(0,name,OBJPROP_COLOR,tint);
   ObjectSetInteger(0,name,OBJPROP_FILL,true);
   ObjectSetInteger(0,name,OBJPROP_BACK,true);

   string bn=name+"_B";
   ObjectCreate(0,bn,OBJ_RECTANGLE,0,LeftTime(),hi,RightTime(),lo);
   ObjectSetInteger(0,bn,OBJPROP_COLOR,bright);
   ObjectSetInteger(0,bn,OBJPROP_WIDTH,2);
   ObjectSetInteger(0,bn,OBJPROP_FILL,false);
   ObjectSetInteger(0,bn,OBJPROP_BACK,false);
}

void Wash(string name,double hi,double lo,color tint)
{
   // Filled background region (no border) behind the candles — used to shade the
   // whole premium / discount half of the dealing range.
   ObjectCreate(0,name,OBJ_RECTANGLE,0,LeftTime(),hi,RightTime(),lo);
   ObjectSetInteger(0,name,OBJPROP_COLOR,tint);
   ObjectSetInteger(0,name,OBJPROP_FILL,true);
   ObjectSetInteger(0,name,OBJPROP_BACK,true);
}

void Legend()
{
   string tf = ChartTF();
   string rows[4];
   rows[0]= M_symbol+"  ICT OS — "+(MatchChartTimeframe && tf!="" ? tf+" zones" : "all zones");
   rows[1]="OB/FVG boxes: green=bullish  red=bearish";
   rows[2]="orange=liquidity  aqua=structure  blue=fib  yellow=EQ";
   rows[3]="PREMIUM half=green(sell)  DISCOUNT half=red(buy)"+(M_pd!=""?("   now: "+M_pd):"");
   for(int i=0;i<4;i++){
      string nm=PFX+"LEG"+IntegerToString(i);
      ObjectCreate(0,nm,OBJ_LABEL,0,0,0);
      ObjectSetInteger(0,nm,OBJPROP_CORNER,CORNER_LEFT_UPPER);
      ObjectSetInteger(0,nm,OBJPROP_XDISTANCE,8);
      ObjectSetInteger(0,nm,OBJPROP_YDISTANCE,18+i*16);
      ObjectSetString(0,nm,OBJPROP_TEXT,rows[i]);
      ObjectSetInteger(0,nm,OBJPROP_FONTSIZE,i==0?10:8);
      ObjectSetInteger(0,nm,OBJPROP_COLOR,i==0?clrGold:clrGainsboro);
   }
}

void ChkRow(int i,string text,color col,int size)
{
   string nm=PFX+"CHK"+IntegerToString(i);
   ObjectCreate(0,nm,OBJ_LABEL,0,0,0);
   ObjectSetInteger(0,nm,OBJPROP_CORNER,CORNER_RIGHT_UPPER);
   ObjectSetInteger(0,nm,OBJPROP_ANCHOR,ANCHOR_RIGHT_UPPER);
   ObjectSetInteger(0,nm,OBJPROP_XDISTANCE,8);
   ObjectSetInteger(0,nm,OBJPROP_YDISTANCE,18+i*16);
   ObjectSetString(0,nm,OBJPROP_TEXT,text);
   ObjectSetInteger(0,nm,OBJPROP_FONTSIZE,size);
   ObjectSetInteger(0,nm,OBJPROP_COLOR,col);
}

void Checklist()
{
   // Top-right "how to read it" panel — the trade decision flow in order.
   if(!ShowChecklist) return;
   ChkRow(0,"— HOW TO READ —",clrGold,10);
   ChkRow(1,"1. Bias: structure (aqua) + higher TF",clrGainsboro,8);
   ChkRow(2,"2. Right half only:",clrGainsboro,8);
   ChkRow(3,"      SELL in green PREMIUM",clrLime,8);
   ChkRow(4,"      BUY in red DISCOUNT",clrRed,8);
   ChkRow(5,"3. Wait for price in bright OTE band",clrGainsboro,8);
   ChkRow(6,"4. OB/FVG box inside OTE = entry",clrGainsboro,8);
   ChkRow(7,"5. Target opposite liquidity (orange)",clrOrange,8);
   ChkRow(8,"Never BUY green / SELL red",clrYellow,9);
}

void FibLevel(double pct,string tag,color col)
{
   double price=M_rangeLow+(M_rangeHigh-M_rangeLow)*pct;
   string nm=PFX+"FIB"+DoubleToString(pct,3);
   HLine(nm,price,col,STYLE_DASH,1);
   Label(nm+"_T",RightTime(),price,tag+"  "+DoubleToString(price,_Digits),col,8);
}

void DrawFibonacci()
{
   if(!ShowFibonacci || M_rangeHigh<=M_rangeLow) return;
   double rng=M_rangeHigh-M_rangeLow;
   double eq=(M_eq>0)?M_eq:(M_rangeLow+rng*0.5);

   // ---- Premium / Discount zones (the halves of the dealing range) ----------
   // Premium = everything ABOVE equilibrium -> the SELL area (green highlight).
   Wash(PFX+"PREMIUM",M_rangeHigh,eq,C'0,32,0');
   Label(PFX+"PREMIUM_T",LeftTime(),(M_rangeHigh+eq)/2.0,"PREMIUM  ▲ sell area (above EQ)",clrLime,10);
   // Discount = everything BELOW equilibrium -> the BUY area (red highlight).
   Wash(PFX+"DISCOUNT",eq,M_rangeLow,C'40,0,0');
   Label(PFX+"DISCOUNT_T",LeftTime(),(eq+M_rangeLow)/2.0,"DISCOUNT  ▼ buy area (below EQ)",clrRed,10);

   // ---- OTE (optimal trade entry) sub-zones, brighter, inside each half -----
   // Premium OTE = 61.8-78.6% retracement -> best SELL entries.
   Band(PFX+"OTE_SELL",M_rangeLow+rng*0.786,M_rangeLow+rng*0.618,clrLime,C'0,70,0');
   Label(PFX+"OTE_SELL_T",RightTime(),M_rangeLow+rng*0.702,"Premium OTE 62-79% (sell)",clrLime,8);
   // Discount OTE = 21.4-38.2% retracement -> best BUY entries.
   Band(PFX+"OTE_BUY",M_rangeLow+rng*0.382,M_rangeLow+rng*0.214,clrRed,C'80,0,0');
   Label(PFX+"OTE_BUY_T",RightTime(),M_rangeLow+rng*0.298,"Discount OTE 21-38% (buy)",clrRed,8);

   FibLevel(0.0,"0% (low)",clrDeepSkyBlue);
   FibLevel(0.236,"23.6%",clrDeepSkyBlue);
   FibLevel(0.382,"38.2%",clrDeepSkyBlue);
   FibLevel(0.618,"61.8%",clrDeepSkyBlue);
   FibLevel(0.786,"78.6%",clrDeepSkyBlue);
   FibLevel(1.0,"100% (high)",clrDeepSkyBlue);

   HLine(PFX+"EQ",eq,clrYellow,STYLE_SOLID,2);
   Label(PFX+"EQ_T",RightTime(),eq,"EQUILIBRIUM 50%  "+DoubleToString(eq,_Digits),clrYellow,9);
}

//--- main ----------------------------------------------------------
void DrawAll()
{
   ObjectsDeleteAll(0,PFX);
   g_id=0;
   string want = ChartTF();

   string fname="ictos_levels_"+_Symbol+".csv";
   if(!FileIsExist(fname)){ ChartRedraw(); return; }
   int fh=FileOpen(fname,FILE_READ|FILE_TXT|FILE_ANSI);
   if(fh==INVALID_HANDLE){ ChartRedraw(); return; }

   int drawn=0;
   while(!FileIsEnding(fh))
   {
      string line=FileReadString(fh);
      if(StringLen(line)==0) continue;
      string p[]; int n=StringSplit(line,',',p);
      if(n<1) continue;
      if(p[0]=="#META"){
         if(n>=7){ M_symbol=p[1]; M_price=StringToDouble(p[2]); M_rangeHigh=StringToDouble(p[3]);
                   M_rangeLow=StringToDouble(p[4]); M_eq=StringToDouble(p[5]); M_pd=p[6]; }
         continue;
      }
      if(n<6) continue;
      string kind=p[0],typ=p[1],dir=p[2],tf=p[3];
      double hi=StringToDouble(p[4]),lo=StringToDouble(p[5]);
      if(hi<=0 && lo<=0) continue;

      // Keep this chart clean: only its own timeframe (file is sorted nearest-first).
      if(MatchChartTimeframe && want!="" && tf!=want) continue;
      if(drawn>=MaxZones) continue;
      drawn++;

      bool bull=(dir=="bullish");
      string full=TypeName(typ)+" "+(bull?"▲":"▼")+" "+tf;
      string nm=PFX+"Z"+IntegerToString(g_id++);

      if(kind=="line"){
         color lc = (typ=="LIQUIDITY") ? clrOrange : clrAqua;   // structure vs liquidity
         HLine(nm,hi,lc,(typ=="LIQUIDITY")?STYLE_DOT:STYLE_DASH,2);
         Label(nm+"_T",LeftTime(),hi,full+"  "+DoubleToString(hi,_Digits),lc,9);
      } else {
         color bright = bull?clrLime:clrRed;                    // bright, high-contrast
         color tint   = bull?C'0,45,0':C'50,0,0';               // subtle fill highlight
         Band(nm,hi,lo,bright,tint);
         Label(nm+"_T",LeftTime(),(hi+lo)/2.0,full,bright,9);
      }
   }
   FileClose(fh);

   DrawFibonacci();
   Legend();
   Checklist();
   ChartRedraw();
}
//+------------------------------------------------------------------+
