//+------------------------------------------------------------------+
//| M1_Exporter.mq5 — ICYQuant shadow-trading data bridge            |
//|                                                                  |
//| Appends every completed EURUSD M1 bar to a CSV that the Python   |
//| shadow runner tails. Data only — no trading logic lives here,    |
//| by design: the signal must be computed by the bit-exact Python   |
//| replica, not re-implemented in MQL5.                             |
//|                                                                  |
//| Install: copy to MQL5/Experts/, compile, attach to EURUSD M1.    |
//| Output: MQL5/Files/ICYQuant/EURUSD_M1_live.csv                   |
//|   columns: server_time,open,high,low,close,tick_volume           |
//| Note the terminal's Files folder path for the runner's --csv.    |
//+------------------------------------------------------------------+
#property strict
#property version   "1.00"

input string InpFileName   = "ICYQuant/EURUSD_M1_live.csv";
input int    InpBackfill   = 500;   // bars written once at startup

int      g_handle = INVALID_HANDLE;
datetime g_last_bar = 0;

int OnInit()
  {
   if(FileIsExist(InpFileName) == false)
     {
      // header for a fresh file
      int h = FileOpen(InpFileName, FILE_WRITE|FILE_CSV|FILE_ANSI, ',');
      if(h != INVALID_HANDLE)
        {
         FileWrite(h, "server_time", "open", "high", "low", "close",
                   "tick_volume");
         FileClose(h);
        }
     }
   // one-time backfill so the runner can build its 12-bar lookback
   MqlRates rates[];
   int got = CopyRates(_Symbol, PERIOD_M1, 1, InpBackfill, rates);
   if(got > 0)
     {
      int h = FileOpen(InpFileName, FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI, ',');
      if(h != INVALID_HANDLE)
        {
         FileSeek(h, 0, SEEK_END);
         for(int i = 0; i < got; i++)
            FileWrite(h,
                      TimeToString(rates[i].time, TIME_DATE|TIME_MINUTES),
                      DoubleToString(rates[i].open,  _Digits),
                      DoubleToString(rates[i].high,  _Digits),
                      DoubleToString(rates[i].low,   _Digits),
                      DoubleToString(rates[i].close, _Digits),
                      (long)rates[i].tick_volume);
         g_last_bar = rates[got - 1].time;
         FileClose(h);
        }
     }
   Print("M1_Exporter ready, backfilled ", got, " bars");
   return(INIT_SUCCEEDED);
  }

void OnTick()
  {
   datetime t = iTime(_Symbol, PERIOD_M1, 1);   // last COMPLETED bar
   if(t == 0 || t == g_last_bar)
      return;
   MqlRates r[1];
   if(CopyRates(_Symbol, PERIOD_M1, t, 1, r) != 1)
      return;
   int h = FileOpen(InpFileName, FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI, ',');
   if(h == INVALID_HANDLE)
      return;
   FileSeek(h, 0, SEEK_END);
   FileWrite(h,
             TimeToString(r[0].time, TIME_DATE|TIME_MINUTES),
             DoubleToString(r[0].open,  _Digits),
             DoubleToString(r[0].high,  _Digits),
             DoubleToString(r[0].low,   _Digits),
             DoubleToString(r[0].close, _Digits),
             (long)r[0].tick_volume);
   FileClose(h);
   g_last_bar = t;
  }
//+------------------------------------------------------------------+
