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
#include <include/PhonetisaurusScript.h>
#include <include/util.h>
#ifdef _GNUC_
#include <omp.h>
#endif
using namespace fst;

typedef unordered_map<int, vector<PathData> > RMAP;

void PrintPathData (const vector<PathData>& results, string FLAGS_word,
		    const SymbolTable* osyms) {
  for (int i = 0; i < results.size (); i++) {
    cout << FLAGS_word << "\t";
    cout << results [i].PathWeight << "\t";
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
		       bool FLAGS_write_fsts) {
  for (int i = 0; i < corpus.size (); i++) {
    vector<PathData> results = decoder.Phoneticize (corpus [i], FLAGS_nbest,
						    FLAGS_beam, FLAGS_thresh,
						    FLAGS_write_fsts);
    PrintPathData (results, corpus [i], decoder.osyms_);
  }
}

void ThreadedEvalaateWordlist (string FLAGS_model, vector<string> corpus,
			       int FLAGS_beam, int FLAGS_nbest, 
			       bool FLAGS_reverse, string FLAGS_skip,
			       double FLAGS_thresh, string FLAGS_gsep,
			       bool FLAGS_write_fsts, int FLAGS_threads) {
  int csize = corpus.size ();
  RMAP rmap;
  SymbolTable osyms;
  
#pragma omp parallel for
  for (int x = 0; x < FLAGS_threads; x++) {
    PhonetisaurusScript decoder (FLAGS_model, FLAGS_gsep);
    if (x == 0)
      osyms = *decoder.osyms_;
    int start = x * (csize / FLAGS_threads);
    int end   = (x == FLAGS_threads - 1) ? csize \
      : start + (csize / FLAGS_threads);
    for (int i = start; i < end; i++) {
      vector<PathData> results = decoder.Phoneticize (corpus [i], FLAGS_nbest,
						    FLAGS_beam, FLAGS_thresh,
						    FLAGS_write_fsts);
      rmap [i] = results;
    }
  }

  for (int i = 0; i < csize; i++) {
    const vector<PathData> results = rmap [i];
    PrintPathData (results, corpus [i], &osyms);
  }
}

DEFINE_string (model, "", "Input FST G2P model.");
DEFINE_string (word, "", "Input word to phoneticize.");
DEFINE_string (wordlist, "", "Input wordlist to phoneticize");
DEFINE_string (gsep, "", "Grapheme separator.");
DEFINE_string (skip, "_", "Phoneme skip marker.");
DEFINE_int32  (nbest, 1, "N-best hypotheses to output.");
DEFINE_int32  (beam, 10000, "Decoder beam.");
DEFINE_int32  (threads, 1, "Number of parallel threads.");
DEFINE_double (thresh, 99.0, "N-best comparison threshold.");
DEFINE_bool   (write_fsts, false, "Write the output FSTs for debugging.");
DEFINE_bool   (reverse, false, "Reverse input word.");

int main (int argc, char* argv []) {
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
  }

  #ifndef __GNUC__
  omp_set_num_threads (FLAGS_threads);
  #endif

  
  if (use_wordlist == true) {
    vector<string> corpus;
    LoadWordList (FLAGS_wordlist, &corpus);
    
    if (FLAGS_threads > 1) {
      cout << "TODO: Current OpenMP parallel output is non-deterministic." << endl;
      /*
      ThreadedEvalaateWordlist (FLAGS_model, corpus, FLAGS_beam,
				FLAGS_nbest, FLAGS_reverse, FLAGS_skip,
				FLAGS_thresh, FLAGS_gsep, FLAGS_write_fsts,
				FLAGS_threads);
      */
    } else {
      PhonetisaurusScript decoder (FLAGS_model, FLAGS_gsep);
      EvaluateWordlist (decoder, corpus, FLAGS_beam, FLAGS_nbest,
			FLAGS_reverse, FLAGS_skip, FLAGS_thresh,
			FLAGS_gsep, FLAGS_write_fsts);
    }
  } else {
    PhonetisaurusScript decoder (FLAGS_model, FLAGS_gsep);
    vector<PathData> results = decoder.Phoneticize (FLAGS_word, FLAGS_nbest,
						    FLAGS_beam, FLAGS_thresh,
						    FLAGS_write_fsts);
    PrintPathData (results, FLAGS_word, decoder.osyms_);
  }
  
  return 0;
}
