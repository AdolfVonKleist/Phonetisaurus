/*
 Arpa2Fst.cpp

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
#include "Arpa2Fst.hpp"
	
Arpa2OpenFST::Arpa2OpenFST( ) {
	//Default constructor.
	cout << "Class ARPA2TextFST requires an input ARPA-format LM..." << endl;
}
	
Arpa2OpenFST::Arpa2OpenFST( 
			   string arpa_lm, string _eps, string _phi, string _split, 
			   string _start, string _sb, string _se, string _delim, string _null_sep 
			    ) {
  
  arpa_lm_fp.open( arpa_lm.c_str() );
  arpa_lm_file = arpa_lm;
  max_order    = 0;
  eps          = _eps;
  phi          = _phi;
  split        = _split;
  start        = _start;
  sb           = _sb;
  se           = _se;
  delim        = _delim;
  null_sep     = _null_sep;

  //Initialize the fst and symbol tables
  ssyms = new SymbolTable("ssyms");
  isyms = new SymbolTable("isyms");
  osyms = new SymbolTable("osyms");

  arpafst.AddState(); 
  arpafst.SetStart(0);
  ssyms->AddSymbol(start);
  ssyms->AddSymbol(se);

  arpafst.AddState();
  arpafst.SetFinal(1,0.0);

  isyms->AddSymbol(eps);
  isyms->AddSymbol(split);
  isyms->AddSymbol(phi);

  osyms->AddSymbol(eps);
  osyms->AddSymbol(split);
  osyms->AddSymbol(phi);
}

double Arpa2OpenFST::log10_2tropical( double val ) {
  val = log(10.0) * val * -1.0;
  if( !(val <= DBL_MAX && val >= -DBL_MAX) )
    val = 99.0;
  if( val != val )
    val = 99.0;
  return val;  
}
	
void Arpa2OpenFST::make_arc( string istate, string ostate, string isym, string osym, double weight ){
  //Build up an arc for the WFST.  Weights default to the Log semiring.
  if( ssyms->Find(istate) == -1 ){
    int new_ssym_id = arpafst.AddState();
    ssyms->AddSymbol( istate, new_ssym_id );
  }
  if( ssyms->Find(ostate) == -1 ){
    int new_ssym_id = arpafst.AddState();
    ssyms->AddSymbol( ostate, new_ssym_id );
  }
  weight = log10_2tropical(weight);

  vector<string> io = tokenize_utf8_string( &isym, &delim );
  if( io.size()==2 ){
    if( io[0].compare(null_sep)==0 )
      io[0] = eps;
    arpafst.AddArc( ssyms->Find(istate), StdArc( isyms->AddSymbol(io[0]), osyms->AddSymbol(io[1]), weight, ssyms->Find(ostate)) );
  }else{
    arpafst.AddArc( ssyms->Find(istate), StdArc( isyms->AddSymbol(isym), osyms->AddSymbol(osym), weight, ssyms->Find(ostate)) );
  }

  return;
}
	
string Arpa2OpenFST::join( vector<string> &tokens, string sep, int start, int end ){
  //Join the elements of a string vector into a single string
  stringstream ss;
  for( int i=start; i<end; i++ ){
    if(i != start)
      ss << sep;
    ss << tokens[i];
  }
  return ss.str();
}
	
void Arpa2OpenFST::generateFST ( ) {
  if( arpa_lm_fp.is_open() ){
    make_arc( 
	     start,           //Input state label
	     sb,              //Output state label
	     sb,              //Input label
	     sb,              //Output label
	     0.0              //Weight
	      );
    while( arpa_lm_fp.good() ){
      getline( arpa_lm_fp, line );
			
      if( current_order > 0 && line.compare("") != 0 && line.compare(0,1,"\\") != 0 ){
	//Process data based on N-gram order
	vector<string> tokens;
	istringstream iss(line);
				
	copy( istream_iterator<string>(iss),
	      istream_iterator<string>(),
	      back_inserter<vector<string> >(tokens)
	      );
	//Handle the unigrams
	if( current_order == 1 ){
	  if( tokens[1].compare(se) == 0 ){
	    make_arc( eps, se, se, se, atof(tokens[0].c_str()) 
		      );
	  }else if( tokens[1].compare(sb) == 0 ){
	    double weight = tokens.size()==3 ? atof(tokens[2].c_str()) : 0.0;
	    make_arc( sb, eps, eps, eps, weight );
	  }else{
	    double weight = tokens.size()==3 ? atof(tokens[2].c_str()) : 0.0;
	    make_arc( tokens[1], eps, eps, eps, weight );
	    make_arc( eps, tokens[1], tokens[current_order], tokens[current_order], atof(tokens[0].c_str()) );
	  }
	  //Handle the middle-order N-grams
	}else if( current_order < max_order ){
	  if( tokens[current_order].compare(se) == 0 ){
	    make_arc( 
		     join(tokens, ",", 1, current_order), 
		     tokens[current_order], 
		     tokens[current_order], 
		     tokens[current_order], 
		     atof(tokens[0].c_str()) 
		      );
	  }else{
	    double weight = tokens.size()==current_order+2 ? atof(tokens[tokens.size()-1].c_str()) : 0.0;
	    make_arc( 
		     join(tokens, ",", 1, current_order+1), 
		     join(tokens, ",", 2, current_order+1), 
		     eps, 
		     eps, 
		     weight
		      );
	    make_arc( 
		     join(tokens, ",", 1, current_order), 
		     join(tokens, ",", 1, current_order+1), 
		     tokens[current_order], 
		     tokens[current_order], 
		     atof(tokens[0].c_str())
		      );
	  }
	  //Handle the N-order N-grams
	}else if( current_order==max_order ){
	  if( tokens[current_order].compare(se) == 0 ){
	    make_arc( 
		     join(tokens, ",", 1, current_order), 
		     tokens[current_order], 
		     tokens[current_order], 
		     tokens[current_order], 
		     atof(tokens[0].c_str()) 
		      );
	  }else{
	    make_arc( 
		     join(tokens, ",", 1, current_order), 
		     join(tokens, ",", 2, current_order+1), 
		     tokens[current_order], 
		     tokens[current_order], 
		     atof(tokens[0].c_str())
		      );
	  }
	}
      }
      
      //Parse the header/footer/meta-data.  This is not foolproof.
      //Random header info starting with '\' or 'ngram', etc. may cause problems.
      if( line.size() > 4 && line.compare( 0, 5, "ngram" ) == 0 )
	max_order = (size_t)atoi(&line[6])>max_order ? atoi(&line[6]) : max_order;
      else if( line.compare( "\\data\\" ) == 0 )
	continue;
      else if( line.compare( "\\end\\" ) == 0 )
	break;
      else if( line.size() > 0 && line.compare( 0, 1, "\\" ) == 0 ){
	line.replace(0, 1, "");
	if( line.compare( 1, 1, "-" ) == 0 )
	  line.replace(1, 7, "");
	else //Will work up to N=99. 
	  line.replace(2, 7, "");
	current_order = atoi(&line[0]);
      }
    }
    arpa_lm_fp.close();
  }else{
    cout << "Unable to open file: " << arpa_lm_file << endl;
  }
}




