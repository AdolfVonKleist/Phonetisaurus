#include <fst/fstlib.h>
#include "PhonetisaurusOmega.hpp"
#include "FstPathFinder.hpp"
#include "util.hpp"
using namespace fst;

typedef struct PerpDatum { int nstates; double perp; } PerpDatum;

PerpDatum phoneticize_word( PhonetisaurusOmega* _decoder, 
			    vector<string> _input, string _sep, bool _words, 
			    bool _scores, int _verbose
			    ){
  /*
    Compute the perplexity for a single word.
  */

  cerr << "Getting ready" << endl;
  vector<string>    tokens = tokenize_entry( &_input.at(0), &_sep, &_decoder->isyms );
  vector<vector<string> > p_tokens;
  for( int i=1; i<_input.size(); i++ ){
    string psep = " ";
    vector<string> phons = tokenize_entry( &_input.at(i), &psep, &_decoder->osyms );
    p_tokens.push_back(phons);
  }
  cerr << "Phoneticizing.." << endl;
  VectorFst<StdArc> pfsa   = _decoder->phoneticize( &tokens, false );

  TopSort(&pfsa);
  cerr << "Computing perp..." << endl;
  StdArc::Weight total = StdArc::Weight::One();
  for( StateIterator<VectorFst<StdArc> > siter(pfsa); !siter.Done(); siter.Next() ){
    StdArc::StateId st = siter.Value();
    for( ArcIterator<VectorFst<StdArc> > aiter(pfsa,st); !aiter.Done(); aiter.Next() ){
      StdArc arc = aiter.Value();
      if( _verbose > 1 )
        cout << st << "\t" << arc.nextstate << "\t" << _decoder->isyms.Find(arc.ilabel) << "}" << _decoder->osyms.Find(arc.olabel) 
             << "\t" << -1*(-1*(arc.weight.Value())/log(10)) << endl;
      total = Times(total,arc.weight);
    }
    if( pfsa.Final(st)!=StdArc::Weight::Zero() ){
      total = Times(total,pfsa.Final(st));
      if( _verbose > 1 )
        cout << "Final(" << st << "): " << pfsa.Final(st) << endl;
    }
  }

  double neglog10prob = -1*(-1*total.Value()/log(10));
  if( _verbose > 1 ){
    cout << "-log10prob: " << neglog10prob << endl;
    cout << "Tokens: " << pfsa.NumStates() << endl;
    cout << "Sents: 1" << endl;
    cout << "log10 perp ( pow(10, -log10prob/(tokens+sents)) ): " << pow(10.,(neglog10prob/pfsa.NumStates())) <<  endl;
  }
  PerpDatum perp = { pfsa.NumStates(), neglog10prob };
  return perp;
}


DEFINE_string( model,   "",    "The input WFST G2P model, in compact format. REQUIRED" );
DEFINE_string( input,   "",    "The input word or test file. REQUIRED" );
DEFINE_string( sep,     "",    "The separator substring for input words. Default=''" );
DEFINE_string( far_suf, "far", "NOT IMPLEMENTED. The suffix to append to the output .far archive. Default='far'" );
DEFINE_bool  ( isfile,  false, "--input is a file. Default=false" );
DEFINE_string( decoder_type,   "fsa_eps", "Decoding type.  Must be one of 'fst_phi', 'fsa_phi', or 'fsa_eps'.");
DEFINE_bool  ( words,   true,  "Show the input words in the output. Default=true" );
DEFINE_bool  ( scores,  true,  "Show the final scores for the pronunciation hypotheses. Default=true" ); 
DEFINE_bool  ( map,     false, "Use the Maximum A-Posteriori (MAP) decoder. Default=false" );
DEFINE_bool  ( lmbr,    false, "Use the Lattice Minimum-Bayes Risk (LMBR) decoder. Default=false" );
DEFINE_bool  ( logopt,  false, "Optimize the result in the log semiring." );
DEFINE_bool  ( infar,   false, "NOT IMPLEMENTED. The input file is a .far archive.  Default=false" );
DEFINE_bool  ( allow_ins,   false, "Allow phoneme insertions when building the input FSA." );
DEFINE_bool  ( outfar,  false, "NOT IMPLEMENTED. The result should be output as a .far archive.  Default=false" );
DEFINE_int32 ( beam,    -1,   "Beam width to use during pruning (this is a bit hacky). Default=-1 (full lattice)" );
DEFINE_int32 ( nbest,   1,     "Show the n-best pronunciation hypotheses. Default=1" );
DEFINE_int32 ( order,   6,     "LMBR maximum N-gram order. Default=6" );
DEFINE_double( alpha,   0.6,   "LMBR alhpa LM scale factor. Default=0.6" );
DEFINE_double( prec,    0.85,  "LMBR precision factor.  Default=0.85" );
DEFINE_double( ratio,   0.72,  "LMBR ratio factor. Default=0.72" );
DEFINE_string( omodel,    "", "Write the (possibly modified) model out to file 'omodel', if specified." );
DEFINE_int32 ( verbose, 1,     "Verbosity level.  Higher is more verbose. Default=1" );
DEFINE_string( pron,    "",    "The target pronunciation for a word." );

int main( int argc, char** argv ){

  string usage = "phonetisaurus-perp.\n\n Usage: ";
  set_new_handler(FailedNewHandler);
  SetFlags(usage.c_str(), &argc, &argv, false);
  if( FLAGS_model.compare("")==0 || FLAGS_input.compare("")==0 ){
    cout << "Both --model, and --input must be set!" << endl;
    exit(1);
  }

  PhonetisaurusOmega* decoder = new PhonetisaurusOmega( 
		     FLAGS_model.c_str(), FLAGS_decoder_type, FLAGS_logopt, FLAGS_beam, 
		     FLAGS_nbest, FLAGS_lmbr, FLAGS_order, FLAGS_alpha,
		     FLAGS_prec, FLAGS_ratio, FLAGS_verbose, FLAGS_allow_ins
		    );
  set<int> skips;
  skips.insert(0);
  skips.insert(1);
  skips.insert(2);
  FstPathFinder* p = new FstPathFinder( skips );

  vector<string> input;
  input.push_back(FLAGS_input);
  input.push_back(FLAGS_pron);
  phoneticize_word( decoder, input, FLAGS_sep, FLAGS_words, FLAGS_scores, FLAGS_verbose );


  delete p;
  delete decoder;
  return 0;
}
