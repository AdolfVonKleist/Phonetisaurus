README.txt

AUTHOR: Josef Robert Novak
CONTACT:
  jorono@yandex-team.ru
  josef.robert.novak@gmail.com

2014-04-13
Added some simple bindings and test scripts for RNNLM.  
Should make it much easier and faster to incorporate 
rescoring experiments for the G2P.

This incorporates Mikolov's rnnlmlib v0.3e.  One modification
was made: protected vars were switched to public to provide
access to the binding code.

You should be able to verify that this version of rnnlm, and
the ngram-client + ngram-server produce the same probs for 
the test model trained by the example.sh script in this version
of RNNLM, and the given test data.

NOTE: You MUST however train models with the -independent flag
 as the bindings are currently hard-wired to this for the G2P.

If the python complains, you may need to add the current directory
to your $LD_LIBRARY_PATH, or whatever directory you store the 
shared object (.so, .so.0, RnnLM.so) files in.

-------------------

Josef Robert Novak
2012-10-15

Phonetisaurus: a WFST-based G2P Conversion toolkit

Phonetisaurus is released under the BSD-2 license.

Phonetisaurus contains 2 pieces of 3rd-party code,
 which are both located in the src/3rdparty directory,
  * google's sparsehash:
    + http://code.google.com/p/sparsehash/
      which is released under the BSD-3 license
  * UTF8-CPP:
    + http://utfcpp.sourceforge.net/
      which is released under a BSD-like/compatible license 
      (see src/3rdparty/utfcpp/utf8.h header file for details)

Phonetisaurus also relies on the OpenFst library
  * http://www.openfst.org
  * which is released under the Apache-2.0 license

Please see the googlecode repository for tutorial information:
 * http://code.google.com/p/phonetisaurus
 * http://code.google.com/p/phonetisaurus/wiki/FSMNLPTutorial

