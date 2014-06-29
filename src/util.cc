/*
 Copyright (c) [2012-], Josef Robert Novak
 All rights reserved.

 Redistribution and use in source and binary forms, with or without
  modification, are permitted #provided that the following conditions
  are met:

  * Redistributions of source code must retain the above copyright 
    notice, this list of conditions and the following disclaimer.
    * Redistributions in binary form must reproduce the above 
    copyright notice, this list of #conditions and the following 
    disclaimer in the documentation and/or other materials provided 
    with the distribution.

 THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS 
 "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT 
 LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS 
 FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE 
 COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, 
 INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES 
 (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR 
 SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) 
 HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, 
 STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) 
 ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED 
 OF THE POSSIBILITY OF SUCH DAMAGE.
*
*/
#include "util.h"
using namespace fst;


string vec2str( vector<string> vec, string sep ){
  string ss;
  for(size_t i = 0; i < vec.size(); ++i){
    if(i != 0)
      ss += sep;
    ss += vec[i];
  }
  return ss;
}

string itoas( int i ){
  std::stringstream ostring;
  ostring << i;
  return ostring.str();
}

vector<string> tokenize_utf8_string( string* utf8_string, string* delimiter ) {
  /*
     Support for tokenizing a utf-8 string. Adapted to also support a delimiter.
     Note that leading, trailing or multiple consecutive delimiters will result in 
     empty vector elements.  Normally should not be a problem but just in case.
     Also note that any tokens that cannot be found in the model symbol table will be
     deleted from the input word prior to grapheme-to-phoneme conversion.

     http://stackoverflow.com/questions/2852895/c-iterate-or-split-utf-8-string-into-array-of-symbols#2856241
  */
  char* str   = (char*)utf8_string->c_str(); // utf-8 string
  char* str_i = str;                         // string iterator
  char* str_j = str;
  char* end   = str+strlen(str)+1;           // end iterator
  vector<string> string_vec;
  if( delimiter->compare("") != 0 )
    string_vec.push_back("");

  do {
    str_j = str_i;
    utf8::uint32_t code = utf8::next(str_i, end); // get 32 bit code of a utf-8 symbol
    if (code == 0)
      continue;
    int start = strlen(str) - strlen(str_j);
    int end   = strlen(str) - strlen(str_i);
    int len   = end - start;
      
    if( delimiter->compare("")==0 ){
      string_vec.push_back( utf8_string->substr(start,len) );
    }else{
      if( delimiter->compare(utf8_string->substr(start,len))==0 )
        string_vec.push_back("");
      else
        string_vec[string_vec.size()-1] += utf8_string->substr(start,len);
    }
  } while ( str_i < end );
  
  return string_vec;
}


vector<string> tokenize_entry(string* testword, string* sep, SymbolTable* syms ){
  vector<string> tokens = tokenize_utf8_string( testword, sep );
  vector<string> entry;
  for( unsigned int i=0; i<tokens.size(); i++ ){
    if( syms->Find(tokens.at(i)) != -1 ){
      entry.push_back(tokens.at(i));
    }else{
      cerr << "Symbol: '" << tokens.at(i)
           << "' not found in input symbols table." << endl
           << "Mapping to null..." << endl;
    }
  }

  return entry;
}

vector<int> tokenize2ints (string* testword, string* sep, const SymbolTable* syms) {
  vector<string> tokens = tokenize_utf8_string (testword, sep);
  vector<int> entry;
  for (unsigned int i=0; i<tokens.size(); i++) {
    int label = syms->Find (tokens[i]);
    if (label == -1)
      cerr << "Symbol: '" << tokens[i]
           << "' not found in input symbols table." << endl
           << "Mapping to null..." << endl;
    else
      entry.push_back (label);
  }

  return entry;
}

#ifdef __MACH__
timespec get_time( ){
  clock_serv_t cclock;
  mach_timespec_t mts;
  host_get_clock_service(mach_host_self(), REALTIME_CLOCK, &cclock);
  clock_get_time(cclock, &mts);

  timespec ts = {mts.tv_sec, mts.tv_nsec};
  return ts;
}
#else
timespec get_time( ){
  timespec ts;
  clock_gettime(CLOCK_REALTIME, &ts);
  return ts;
}
#endif

timespec diff(timespec start, timespec end){
  timespec temp;
  if ((end.tv_nsec-start.tv_nsec)<0) {
    temp.tv_sec = end.tv_sec-start.tv_sec-1;
    temp.tv_nsec = 1000000000+end.tv_nsec-start.tv_nsec;
  } else {
    temp.tv_sec = end.tv_sec-start.tv_sec;
    temp.tv_nsec = end.tv_nsec-start.tv_nsec;
  }
  return temp;
}
