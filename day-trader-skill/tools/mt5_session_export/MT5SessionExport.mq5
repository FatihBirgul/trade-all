// One-shot read-only script. Compile in MetaEditor, then run manually once.
// No trade, account balance, login, SymbolSelect, or connection changes.
#property script_show_inputs
#property version "1.00"

#define OUTPUT_FILE "session_evidence_v1.json"
#define MAX_SESSIONS 64

bool SafeLabel(const string value)
  {
   int n=StringLen(value);
   if(n<1 || n>80) return false;
   for(int i=0;i<n;i++)
     {
      ushort c=StringGetCharacter(value,i);
      if(!((c>='A' && c<='Z') || (c>='a' && c<='z') ||
           (c>='0' && c<='9') || c=='-' || c=='_' || c=='.')) return false;
     }
   return true;
  }

string UtcStamp()
  {
   MqlDateTime parts;
   TimeToStruct(TimeGMT(),parts);
   return StringFormat("%04d-%02d-%02dT%02d:%02d:%02dZ",
                       parts.year,parts.mon,parts.day,
                       parts.hour,parts.min,parts.sec);
  }

string Sessions(const string symbol,const ENUM_DAY_OF_WEEK day,
                const bool quote,int &count,bool &complete)
  {
   string result="[";
   count=0;
   complete=false;
   for(int index=0;index<MAX_SESSIONS;index++)
     {
      datetime start_time=0,end_time=0;
      ResetLastError();
      bool found=(quote ? SymbolInfoSessionQuote(symbol,day,(uint)index,start_time,end_time)
                        : SymbolInfoSessionTrade(symbol,day,(uint)index,start_time,end_time));
      if(!found)
        {
         complete=(GetLastError()==0);
         break;
        }
      // The MQL5 reference says to ignore the returned date. Keep seconds
      // from midnight, including a zero end for a session crossing midnight.
      int start_seconds=(int)((long)start_time%86400);
      int end_seconds=(int)((long)end_time%86400);
      if(count>0) result+=",";
      result+=StringFormat("{\"index\":%d,\"from_seconds\":%d,\"to_seconds\":%d}",
                           index,start_seconds,end_seconds);
      count++;
     }
   return result+"]";
  }

void OnStart()
  {
   const string server=AccountInfoString(ACCOUNT_SERVER);
   if(!SafeLabel(server))
     {
      Print("Session export refused: broker server label unavailable or unsafe");
      return;
     }
   string symbols[4]={"XAUUSDc","EURUSDc","GBPUSDc","USDJPYc"};
   for(int s=0;s<4;s++)
     {
      bool custom=false;
      if(!SymbolExist(symbols[s],custom) || custom)
        {
         Print("Session export refused: exact broker symbol unavailable");
         return;
        }
     }
   string payload="{\"schema_version\":\"mt5-session-evidence-1\",";
   payload+="\"source_type\":\"MT5_CURRENT_WEEKLY_SCHEDULE\",";
   payload+="\"broker_server\":\""+server+"\",";
   payload+="\"collected_at_utc\":\""+UtcStamp()+"\",";
   payload+="\"time_representation\":\"SECONDS_FROM_MIDNIGHT_SERVER_SESSION\",";
   payload+="\"source_code_version\":\"mt5-session-export-1\",";
   payload+="\"source_functions\":[\"SymbolInfoSessionQuote\",\"SymbolInfoSessionTrade\"],";
   payload+="\"provenance\":\"MQL5_SCRIPT_LOCAL_READ_ONLY\",";
   payload+="\"effective_from_utc\":null,\"effective_to_utc\":null,\"symbols\":[";
   for(int s=0;s<4;s++)
     {
      if(s>0) payload+=",";
      payload+="{\"broker_symbol\":\""+symbols[s]+"\",\"days\":[";
      for(int d=0;d<7;d++)
        {
         if(d>0) payload+=",";
         int quote_count=0,trade_count=0;
         bool quote_complete=false,trade_complete=false;
         ENUM_DAY_OF_WEEK day=(ENUM_DAY_OF_WEEK)d; // MQL5: Sunday=0.
         string quote=Sessions(symbols[s],day,true,quote_count,quote_complete);
         string trade=Sessions(symbols[s],day,false,trade_count,trade_complete);
         string complete=(quote_complete && trade_complete ? "true" : "false");
         payload+=StringFormat("{\"day_of_week\":%d,\"quote_sessions\":",d)+quote;
         payload+=",\"trade_sessions\":"+trade;
         payload+=StringFormat(",\"quote_count\":%d,\"trade_count\":%d,",quote_count,trade_count);
         payload+="\"enumeration_complete\":"+complete+"}";
        }
      payload+="]}";
     }
   payload+="]}";
   int file=FileOpen(OUTPUT_FILE,FILE_WRITE|FILE_TXT|FILE_ANSI,0,CP_UTF8);
   if(file==INVALID_HANDLE)
     {
      Print("Session export refused: cannot open output file");
      return;
     }
   FileWriteString(file,payload);
   FileFlush(file);
   FileClose(file);
   Print("Read-only weekly session export written to MQL5/Files/"+OUTPUT_FILE);
  }
