/*
 phonetisaurus-arpa2wfst.cc

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
using namespace std;
#include <include/ARPA2WFST.h>
#include <include/util.h>

using namespace fst;

DEFINE_string (lm, "", "Input ARPA format LM.");
DEFINE_string (eps, "<eps>", "Epsilon symbol.");
DEFINE_string (sb, "<s>", "Sentence begin token.");
DEFINE_string (se, "</s>", "Sentence end token.");
DEFINE_string (split, "}", "Character separating grapheme/phoneme info.");
DEFINE_string (skip, "_", "Character indicating insertions/deletions.");
DEFINE_string (tie, "|", "Character separating multi-token subsequences.");
DEFINE_string (ssyms, "", "Output filename for state symbols tables (default: do not print).");
DEFINE_string (ofile, "", "Output file for writing. (STDOUT)");

int main (int argc, char* argv []) {
  cerr << "GitRevision: " << GIT_REVISION << endl;
  string usage = "arpa2wfsa - Transform an ARPA LM into an "
    "equivalent WFSA.\n\n Usage: ";
  set_new_handler (FailedNewHandler);
  PhonetisaurusSetFlags (usage.c_str(), &argc, &argv, false);

  if (FLAGS_lm.compare ("") == 0) {
    cerr << "You must supply an ARPA format lm "
      "to --lm for conversion!" << endl;
    return 0;
  }
    
  cerr << "Initializing..." << endl;
  ARPA2WFST* converter = new ARPA2WFST (FLAGS_lm, FLAGS_eps, FLAGS_sb, 
					FLAGS_se, FLAGS_split, FLAGS_skip, 
					FLAGS_tie);
  cerr << "Converting..." << endl;
  converter->arpa_to_wfst ();
  
  converter->arpafst.Write (FLAGS_ofile);

  if (FLAGS_ssyms.compare ("") != 0) {
    converter->ssyms->WriteText (FLAGS_ssyms);
  }
  
  delete converter;

  return 0;
}
