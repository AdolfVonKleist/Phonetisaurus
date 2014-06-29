/*
 *  Phonetisaurus.cpp 
 *  
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
#include <stdio.h>
#include <string>
#include <fst/fstlib.h>
#include <iostream>
#include <set>
#include <algorithm>
#include "FstPathFinder.hpp"
#include "Phonetisaurus.hpp"

using namespace fst;

Phonetisaurus::Phonetisaurus( ) {
    //Default constructor
}

Phonetisaurus::Phonetisaurus( const char* _g2pmodel_file, bool _mbrdecode, float _alpha, float _precision, float _ratio, int _order ) {
    //Base constructor.  Load the clusters file, the models and setup shop.
    mbrdecode = _mbrdecode;
    alpha = _alpha;
    precision = _precision;
    ratio = _ratio;
    order = _order;
    eps  = "<eps>";
    sb   = "<s>";
    se   = "</s>";
    skip = "_";
    
    g2pmodel = StdVectorFst::Read( _g2pmodel_file );

    isyms = (SymbolTable*)g2pmodel->InputSymbols(); 
    tie  = isyms->Find(1); //The separator symbol is reserved for index 1
    skipSeqs.insert(isyms->Find(eps));
    skipSeqs.insert(isyms->Find(sb));
    skipSeqs.insert(isyms->Find(se));
    skipSeqs.insert(isyms->Find(skip));
    
    osyms = (SymbolTable*)g2pmodel->OutputSymbols(); 
    
    loadClusters( );
    
    epsMapper = makeEpsMapper( );
    
    //We need make sure the g2pmodel is arcsorted
    ILabelCompare<StdArc> icomp;
    ArcSort( g2pmodel, icomp );
}


void Phonetisaurus::loadClusters( ){
    /*
     Load the clusters file containing the list of 
     subsequences generated during multiple-to-multiple alignment
    */
    
    for( size_t i = 2; i < isyms->NumSymbols(); i++ ){
        string sym = isyms->Find( i );
        
        if( sym.find(tie) != string::npos ){
            char* tmpstring = (char *)sym.c_str();
            char* p = strtok(tmpstring, tie.c_str());
            vector<string> cluster;
            
            while (p) {
                cluster.push_back(p);
                p = strtok(NULL, tie.c_str());
            }
            
            clusters[cluster] = i;
        }
    }
    return;
}

StdVectorFst Phonetisaurus::makeEpsMapper( ){
    /*
     Generate a mapper FST to transform unwanted output symbols
     to the epsilon symbol.
     
     This can be used to remove unwanted symbols from the final 
     result, but in tests was 7x slower than manual removal
     via the FstPathFinder object.
     */
    
    StdVectorFst mfst;
    mfst.AddState();
    mfst.SetStart(0);
    
    set<string>::iterator sit;
    for( size_t i=0; i< osyms->NumSymbols(); i++ ){
        if( skipSeqs.find(i)!=skipSeqs.end() )
            mfst.AddArc( 0, StdArc( i, 0, 0, 0 ) );
        else
            mfst.AddArc( 0, StdArc( i, i, 0, 0 ) );
    }
    mfst.SetFinal(0, 0);
    ILabelCompare<StdArc> icomp;
    ArcSort( &mfst, icomp );
    mfst.SetInputSymbols( osyms );
    mfst.SetOutputSymbols( osyms );
    
    return mfst;
}

StdVectorFst Phonetisaurus::entryToFSA( vector<string> entry ){
    /*
     Transform an input spelling/pronunciation into an equivalent
     FSA, adding extra arcs as needed to accomodate clusters.
    */
    
    StdVectorFst efst;
    efst.AddState();
    efst.SetStart(0);

    efst.AddState();
    efst.AddArc( 0, StdArc( isyms->Find( sb ), isyms->Find( sb ), 0, 1 ));
    size_t i=0;
    
    //Build the basic FSA
    for( i=0; i<entry.size(); i++){
        efst.AddState();
        string ch = entry[i];
        efst.AddArc( i+1, StdArc( isyms->Find(ch), isyms->Find(ch), 0, i+2 ));
        if( i==0 ) 
            continue;
        
    }
    
    //Add any cluster arcs
    map<vector<string>,int>::iterator it_i;
    for( it_i=clusters.begin(); it_i!=clusters.end(); it_i++ ){
        vector<string>::iterator it_j;
        vector<string>::iterator start = entry.begin();
        vector<string> cluster = (*it_i).first;
        while( it_j != entry.end() ){
            it_j = search( start, entry.end(), cluster.begin(), cluster.end() );
            if( it_j != entry.end() ){
                efst.AddArc( it_j-entry.begin()+1, StdArc( 
                        (*it_i).second,                     //input symbol
                        (*it_i).second,                     //output symbol
                        0,                                  //weight
                        it_j-entry.begin()+cluster.size()+1 //destination state
                    ) );
                start = it_j+cluster.size();
            }
        }
    }
    
    efst.AddState();
    efst.AddArc( i+1, StdArc( isyms->Find( se ), isyms->Find( se ), 0, i+2));
    efst.SetFinal( i+2, 0 );
    efst.SetInputSymbols( isyms );
    efst.SetOutputSymbols( isyms );
    return efst;
}

int Phonetisaurus::_compute_thetas( int wlen ){
  /*
    Theta values are computed on a per-word basis
    We scale the maximum order by the length of the input word.
    Higher MBR N-gram orders favor longer pronunciation hypotheses.
    Thus a high N-gram order coupled with a short word will
    favor longer pronunciations with more insertions.

      p=.63, r=.48
      p=.85, r=.72
    .918
    Compute the N-gram Theta factors for the
    model.  These are a function of,
      N:  The maximum N-gram order
      T:  The total number of 1-gram tokens 
      p:  The 1-gram precision
      r:  A constant ratio
       
    1) T may be selected arbitrarily.
    2) Default values are selected from Tromble 2008
  */
  thetas.clear();
  float T = 10.0;
  int N   = min( wlen+1, order );
  //cout << "N: " << N << endl;
  //Theta0 is basically an insertion penalty
  // -1/T
  float ip = -0.3;
  thetas.push_back( -1/T );
  for( int n=1; n<=order; n++ )
      thetas.push_back( 1.0/((N*T*precision) * (pow(ratio,(n-1)))) );
  return N;
}

vector<PathData> Phonetisaurus::phoneticize( vector<string> entry, int nbest, int beam ){
    /*
     Generate pronunciation/spelling hypotheses for an 
     input entry.
    */
    StdVectorFst result;
    StdVectorFst epsMapped;
    StdVectorFst shortest;
    StdVectorFst efst = entryToFSA( entry );
    StdVectorFst smbr;
    int N = _compute_thetas( entry.size() );

    /*Phi matching - 
      For some reason this performs MUCH worse than 
      with standard epsilon transitions.  Why?
    //<phi> is fixed to ID=2
    PM* pm = new PM( *g2pmodel, MATCH_INPUT, 2 );
    ComposeFstOptions<StdArc, PM> opts;
    opts.gc_limit = 0;
    opts.matcher1 = new PM(efst, MATCH_NONE,  kNoLabel);
    opts.matcher2 = pm;
    ComposeFst<StdArc> phicompose(efst, *g2pmodel, opts);
    VectorFst<StdArc> result(phicompose);
    */
    Compose( efst, *g2pmodel, &result );

    Project(&result, PROJECT_OUTPUT);
    //result.Write("result-lattice.fst");
    if( mbrdecode==true ){
      ShortestPath( result, &smbr, beam );
      VectorFst<LogArc> logfst;
      Map( smbr, &logfst, StdToLogMapper() );
      RmEpsilon(&logfst);
      VectorFst<LogArc> detlogfst;
      //cout << "pre-determinize" << endl;
      Determinize(logfst, &detlogfst);
      //cout << "pre-minimize" << endl;
      Minimize(&detlogfst);
      detlogfst.SetInputSymbols(g2pmodel->OutputSymbols());
      detlogfst.SetOutputSymbols(g2pmodel->OutputSymbols());
      //cout << "build MBRDecoder" << endl;
      //cout << "order: " << order << " alpha: " << endl;
      //detlogfst.Write("abbreviate.fst");
      MBRDecoder mbrdecoder( N, &detlogfst, alpha, thetas );
      //cout << "decode" << endl;
      mbrdecoder.build_decoder( );
      Map( *mbrdecoder.omegas[N-1], &result, LogToStdMapper() );
      skipSeqs.clear();
      string eps1 = "<eps>";
      string sb1  = "<s>";
      string se1 = "</s>";
      string sk1 = "_";
      *osyms = *(mbrdecoder.omegas[N-1]->OutputSymbols());
      osyms->AddSymbol(sk1);
      skipSeqs.insert(osyms->Find(eps1));
      skipSeqs.insert(osyms->Find(sb1));
      skipSeqs.insert(osyms->Find(se1));
      skipSeqs.insert(osyms->Find(sk1));
    }
    //cout << "Finished MBR stuff!" << endl;
    if( nbest > 1 ){
        //This is a cheesy hack. 
        ShortestPath( result, &shortest, beam );
    }else{
        ShortestPath( result, &shortest, 1 );
    }
    /*
    VectorFst<LogArc>* logResult = new VectorFst<LogArc>();
    Map(result, logResult, StdToLogMapper());
    logResult->SetInputSymbols(g2pmodel->OutputSymbols());
    logResult->SetOutputSymbols(g2pmodel->OutputSymbols());
    logResult->Write("ph-lattice.fst");
    */
    RmEpsilon( &shortest );
    FstPathFinder pathfinder( skipSeqs );
    pathfinder.extract_all_paths( shortest );
    
    return pathfinder.paths;
}


bool Phonetisaurus::printPaths( vector<PathData> paths, unsigned int nbest, string correct, string word ){
  /*
     Convenience function to print out a path vector.
     Will print only the first N unique entries.
  */

  set<string> seen;
  set<string>::iterator sit;
    
  string onepath;
  size_t k;
  bool empty_path = true;
  for( k=0; k < paths.size(); k++ ){
    if ( k >= nbest )
      break;
        
    size_t j;
    for( j=0; j < paths[k].path.size(); j++ ){
      if( paths[k].path[j]==2 ) continue;
      string sym = osyms->Find(paths[k].path[j]);
      if( sym.compare("_")==0 ) continue;
      if( sym != tie )
	replace( 
		sym.begin(), 
		sym.end(), 
		*tie.c_str(),
                        ' '
		 );
      onepath += sym;
            
      if( j != paths[k].path.size()-1 )
	onepath += " ";
    }
    if( onepath == "" )
      continue;
    empty_path = false;
    if( word != "" )
      cout << word << "\t";
    cout << paths[k].cost << "\t" << onepath;
    if( correct != "" )
      cout << "\t" << correct;
    cout << endl;
    onepath = "";
  }
  return empty_path;
}
