#include <fst/fstlib.h>
#include "util.hpp"
#include "PhonetisaurusE2F.hpp"
using namespace fst;


void compute_fsm( PhonetisaurusE2F* e2f, vector<string>* tokens, bool make_fst, bool use_comp ){
  //WFSA=0, MFSA=1, WFST=2, MFST=3
  if( make_fst == false ){
    if( use_comp == true )
      e2f->entry_to_fsa_w( tokens );
    else
      e2f->entry_to_fsa_m( tokens );
  }else{
    if( use_comp == true )
      e2f->entry_to_fst_w( tokens );
    else
      e2f->entry_to_fst_m( tokens );
  }
  return;
}

DEFINE_string( model,     "",    "The input WFST G2P model, in compact format. REQUIRED" );
DEFINE_string( input,     "",    "The input word or test file. REQUIRED" );
DEFINE_string( sep,       "",    "The separator substring for input words. Default=''" );
DEFINE_bool  ( isfile,    false, "--input is a file. Default=false" );
DEFINE_bool  ( make_fst,  false, "Generate an FST, instead of an FSA." );
DEFINE_bool  ( use_comp,  false, "Use FST composition, not the mechanical approach.");
DEFINE_int32 ( iters,     1,     "Number of iterations to average the timing over.");
DEFINE_bool  ( verbose,   false, "Use verbose mode.");
DEFINE_bool  ( isword,    false, "Input is a single word.");
DEFINE_bool  ( allow_ins, false, "Allow phoneme insertions.");

int main( int argc, char* argv[] ){
  string usage = "pE2F word to FSM conversion script.\n\n Usage: ";
  set_new_handler(FailedNewHandler);
  SetFlags(usage.c_str(), &argc, &argv, false);
  if( FLAGS_model.compare("")==0 || FLAGS_input.compare("")==0 ){
    cout << "Both --model, and --input must be set!" << endl;
    exit(1);
  }

  //BEGIN SETUP
  VectorFst<StdArc>* g2pm = VectorFst<StdArc>::Read(FLAGS_model);
  string entry = FLAGS_input;
  string sep   = FLAGS_sep;
  EncodeMapper<StdArc>* encoder = new EncodeMapper<StdArc>(kEncodeLabels, ENCODE);
  SymbolTable isyms = SymbolTable(*g2pm->InputSymbols());
  SymbolTable osyms = SymbolTable(*g2pm->OutputSymbols());
  isyms.WriteText("t.isyms");
  osyms.WriteText("t.osyms");
  Encode(g2pm, encoder);
  PhonetisaurusE2F e2f(encoder->table(), FLAGS_verbose, FLAGS_allow_ins, &isyms, &osyms);
  timespec start, end, elapsed;
  double nelapsed, iter_nelapsed;
  //END SETUP

  if( FLAGS_isword==true ){
    vector<string> tokens = tokenize_entry( &entry, &sep, &isyms );
    compute_fsm( &e2f, &tokens, FLAGS_make_fst, FLAGS_use_comp );
    e2f.word.Write("outputword.fst");
    isyms.WriteText("output.isyms");
    osyms.WriteText("output.osyms");
    return 1;
  }

  ifstream test_fp;
  int states = 0;
  int arcs   = 0;
  double entries = 0.;
  iter_nelapsed = 0.;
  for( int i=0; i<FLAGS_iters; i++ ){
    test_fp.open( FLAGS_input.c_str() );
    string line;
    string delim = "\t";
    entries = nelapsed = 0.0;
    states  = arcs = 0;

    if( test_fp.is_open() ){
      while( test_fp.good() ){
	getline( test_fp, line );
	if( line.compare(" ")==0 || line.compare("")==0 )
	  continue;
	vector<string> parts  = tokenize_utf8_string( &line, &delim );
	vector<string> tokens = tokenize_entry( &parts.at(0), &sep, &isyms );
	
	start = get_time();
	compute_fsm( &e2f, &tokens, FLAGS_make_fst, FLAGS_use_comp );
	end = get_time();

	states += e2f.word.NumStates();
	for( StateIterator<VectorFst<StdArc> > siter(e2f.word); !siter.Done(); siter.Next() ){
	  StdArc::StateId sid = siter.Value();
	  arcs += e2f.word.NumArcs(sid);
	}
	e2f.word = VectorFst<StdArc>();

	elapsed = diff(start, end);
	nelapsed += elapsed.tv_nsec;
	entries += 1;
      }
      test_fp.close();
    }else{
      cout << "Problem opening test file..." << endl;
    }
    iter_nelapsed += nelapsed/entries;
    cerr << "Entries: " << entries << " Iter Elapsed (nsec): " << nelapsed << " Avg (nsec): " << nelapsed/entries << endl;
  }
  cout << "Avg #States: " << states/entries << " Avg #Arcs: " << arcs/entries << endl;
  cerr << "Iters: " << FLAGS_iters << " Total Avg (nsec): " << iter_nelapsed / FLAGS_iters << endl;
  return 1;
}
