// RnnLMWrapper.h
//
// Copyright (c) [2013-], Yandex, LLC
// Author: jorono@yandex-team.ru (Josef Robert Novak)
// All rights reserved.
/*
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
/// \file
/// Python bindings for RnnLM.  These only correspond
/// to basic evaluation functions, not training. By default
/// the evaluations utilizes the -independent convention from
/// the original rnnlm tool.  This is all we are interested in
/// for G2P evaluations.
#ifndef SRC_INCLUDE_RNNLMPY_H_
#define SRC_INCLUDE_RNNLMPY_H_

#include <fst/fstlib.h>
#include <string>
#include <vector>
#include "./rnnlmlib.h"

using namespace fst;

typedef struct UttResult {
  UttResult () : sent_prob(0.0) {}
  double sent_prob;
  vector<double> word_probs;
  vector<string> words;
} UttResult;

class RnnLMPy {
 public:
  explicit RnnLMPy (string rnnlm_file) {
    srand (1);
    rnnlm_.setLambda (0.75);
    rnnlm_.setRegularization (0.0000001);
    rnnlm_.setDynamic (false);
    rnnlm_.setRnnLMFile (const_cast<char*> (rnnlm_file.c_str()));
    rnnlm_.setRandSeed (1);
    rnnlm_.useLMProb (false);
    rnnlm_.setDebugMode (1);
    rnnlm_.restoreNet ();
  }

  vector<int> GetJointVocab (string& token) {
    return rnnlm_.SearchJointVocab (token);
  }

  string GetString (int id) {
    return rnnlm_.token_map[id];
  }

  UttResult EvaluateSentence (vector<string> words) {
    /*
      Note that the user is responsible for explicitly
      providing the sentence-end token in the words vector!
    */
    int a, word, last_word;
    UttResult result;
    string delim = "}";

    last_word = 0;
    rnnlm_.copyHiddenLayerToInput ();
    if (rnnlm_.bptt > 0) {
      for (a = 0; a < rnnlm_.bptt + rnnlm_.bptt_block; a++)
        rnnlm_.bptt_history[a] = 0;
    }
    for (a = 0; a < MAX_NGRAM_ORDER; a++)
      rnnlm_.history[a] = 0;
    rnnlm_.netReset();

    // Check the G2P tokens
    for (size_t i = 0; i < words.size(); i++) {
      word = rnnlm_.searchVocab (const_cast<char*> (words[i].c_str()));
      /*
      vector<string> toks = tokenize_utf8_string (&words[i], &delim);
      cout << toks[0] << endl;
      vector<int>& tokens = rnnlm_.SearchJointVocab (toks[0]);
      float tscore = -999;
      for (int j = 0; j < tokens.size(); j++) {
        cout << "  " << tokens[j] << "\t"
             << rnnlm_.token_map[tokens[j]] << "\t";
        rnnlm_.computeNet (last_word, tokens[j]);
        float tval =  log10 (rnnlm_.neu2[rnnlm_.vocab[tokens[j]].class_index
                             + rnnlm_.vocab_size].ac
                             * rnnlm_.neu2[tokens[j]].ac);
        if (tval > tscore) {
          tscore = tval;
          word = tokens[j];
        }
        cout << tval << endl;
      }
      /////////////////////
      */
      result.words.push_back (rnnlm_.token_map[word]);
      rnnlm_.computeNet (last_word, word);


      if (word != -1) {
        result.word_probs.push_back (
            log10 (rnnlm_.neu2[rnnlm_.vocab[word].class_index
                   + rnnlm_.vocab_size].ac
                   * rnnlm_.neu2[word].ac));
        result.sent_prob += result.word_probs.back ();
      } else {
        // cout << "-1\t0\tOOV" << endl;
        result.word_probs.push_back (0.0);
      }

      rnnlm_.copyHiddenLayerToInput ();
      if (last_word != -1)
        rnnlm_.neu0[last_word].ac = 0;

      last_word = word;
      for (a = MAX_NGRAM_ORDER - 1; a > 0; a--)
        rnnlm_.history[a] = rnnlm_.history[a-1];
      rnnlm_.history[0] = last_word;
    }

    return result;
  }

 private:
  CRnnLM rnnlm_;  // The actual rnnlm
};

#endif  // SRC_INCLUDE_RNNLMPY_H_
