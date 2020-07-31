/*
 phonetisaurus-g2pfst.cc

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
#include <fst/fstlib.h>
using namespace std;
#include <include/PhonetisaurusScript.h>
#include <include/util.h>
#include <iomanip>
using namespace fst;

typedef unordered_map<int, vector<PathData> > RMAP;

void PrintPathData (const vector<PathData>& results, string FLAGS_word,
		    const SymbolTable* osyms, bool print_scores = true,
		    bool nlog_probs = true) {
  for (int i = 0; i < results.size (); i++) {
    cout << FLAGS_word << "\t";
    if (print_scores == true) {
      if (nlog_probs == true) 
	cout << results [i].PathWeight << "\t";
      else
	cout << std::setprecision (3) << exp (-results [i].PathWeight) << "\t";
    }
    
    for (int j = 0; j < results [i].Uniques.size (); j++) {
      cout << osyms->Find (results [i].Uniques [j]);
      if (j < results [i].Uniques.size () - 1)
	cout << " ";
    }
    cout << endl;
  }    
}

void EvaluateWordlist (PhonetisaurusScript& decoder, vector<string> corpus,
		       int FLAGS_beam, int FLAGS_nbest, bool FLAGS_reverse,
		       string FLAGS_skip, double FLAGS_thresh, string FLAGS_gsep,
		       bool FLAGS_write_fsts, bool FLAGS_print_scores,
		       bool FLAGS_accumulate, double FLAGS_pmass,
		       bool FLAGS_nlog_probs) {
  for (int i = 0; i < corpus.size (); i++) {
    vector<PathData> results = decoder.Phoneticize (corpus [i], FLAGS_nbest,
						    FLAGS_beam, FLAGS_thresh,
						    FLAGS_write_fsts,
						    FLAGS_accumulate, FLAGS_pmass);
    PrintPathData (results, corpus [i],
		   decoder.osyms_,
		   FLAGS_print_scores,
		   FLAGS_nlog_probs);
  }
}


DEFINE_string (model, "", "Input FST G2P model.");
DEFINE_string (word, "", "Input word to phoneticize.");
DEFINE_string (wordlist, "", "Input wordlist to phoneticize");
DEFINE_string (gsep, "", "Grapheme separator.");
DEFINE_string (skip, "_", "Phoneme skip marker.");
DEFINE_int32 (nbest, 1, "N-best hypotheses to output.");
DEFINE_int32 (beam, 10000, "Decoder beam.");
DEFINE_double (thresh, 99.0, "N-best comparison threshold.");
DEFINE_double (pmass, 0.0, "Percent of probability mass (0.0 < p <= 1.0).");
DEFINE_bool (write_fsts, false, "Write the output FSTs for debugging.");
DEFINE_bool (reverse, false, "Reverse input word.");
DEFINE_bool (print_scores, true, "Print scores in output.");
DEFINE_bool (accumulate, false, "Accumulate weights for unique output prons.");
DEFINE_bool (nlog_probs, true, "Default scores vals are negative logs. "
	     "Otherwise exp (-val).");
int main (int argc, char* argv []) {
  cerr << "GitRevision: " << GIT_REVISION << endl;
  string usage = "phonetisaurus-g2pfst - joint N-gram decoder.\n\n Usage: ";
  set_new_handler (FailedNewHandler);
  PhonetisaurusSetFlags (usage.c_str(), &argc, &argv, false);

  if (FLAGS_model.compare ("") == 0) {
    cerr << "You must supply an FST model to --model" << endl;
    exit (1);
  } else {
    std::ifstream model_ifp (FLAGS_model);
    if (!model_ifp.good ()) {
      cout << "Failed to open --model file '"
	   << FLAGS_model << "'" << endl;
      exit (1);
    }
  }

  if (FLAGS_pmass < 0.0 || FLAGS_pmass > 1) {
    cout << "--pmass must be a float value between 0.0 and 1.0." << endl;
    exit (1);
  }
  if (FLAGS_pmass == 0.0)
    FLAGS_pmass = 99.0;
  else
    FLAGS_pmass = -log (FLAGS_pmass);
  
  bool use_wordlist = false;
  if (FLAGS_wordlist.compare ("") != 0) {
    std::ifstream wordlist_ifp (FLAGS_wordlist);
    if (!wordlist_ifp.good ()) {
      cout << "Failed to open --wordlist file '"
	   << FLAGS_wordlist << "'" << endl;
      exit (1);
    } else {
      use_wordlist = true;
    }
  }

  if (FLAGS_wordlist.compare ("") == 0 && FLAGS_word.compare ("") == 0) {
    cout << "Either --wordlist or --word must be set!" << endl;
    exit (1);
  }

  if (use_wordlist == true) {
    vector<string> corpus;
    LoadWordList (FLAGS_wordlist, &corpus);
    
    PhonetisaurusScript decoder (FLAGS_model, FLAGS_gsep);
    EvaluateWordlist (
	    decoder, corpus, FLAGS_beam, FLAGS_nbest, FLAGS_reverse,
	    FLAGS_skip, FLAGS_thresh, FLAGS_gsep, FLAGS_write_fsts,
	    FLAGS_print_scores, FLAGS_accumulate, FLAGS_pmass,
	    FLAGS_nlog_probs
	  );
  } else {
    PhonetisaurusScript decoder (FLAGS_model, FLAGS_gsep);
    vector<PathData> results = decoder.Phoneticize (
		         FLAGS_word, FLAGS_nbest, FLAGS_beam, FLAGS_thresh,
			 FLAGS_write_fsts, FLAGS_accumulate, FLAGS_pmass
		       );
    PrintPathData (results, FLAGS_word,
		   decoder.osyms_,
		   FLAGS_print_scores,
		   FLAGS_nlog_probs);
  }
  
  return 0;
}
