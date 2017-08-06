#ifndef SRC_INCLUDE_LEGACYRNNLMREADER_H_
#define SRC_INCLUDE_LEGACYRNNLMREADER_H_
#include <string>
#include "./rnnlmlib.h"
using std::string;

template<class D, class H>
class LegacyRnnLMReader {
 public:
  typedef D Decodable;
  typedef H Hasher;

  explicit LegacyRnnLMReader (const string& rnnlm_file) {
    srand (1);
    // We don't actually need or use any of this
    rnnlm_.setLambda (0.75);
    rnnlm_.setRegularization (0.0000001);
    rnnlm_.setDynamic (false);
    rnnlm_.setRnnLMFile (const_cast<char*> (rnnlm_file.c_str ()));
    rnnlm_.setRandSeed (1);
    rnnlm_.useLMProb (false);
    rnnlm_.setDebugMode (1);
    // This will actually load the thing
    rnnlm_.restoreNet ();
  }

  Decodable CopyLegacyRnnLM (Hasher& h, int max_order = 5) {
    // Copy static data that can be shared by all tokens
    Decodable d (h, rnnlm_.layer0_size, rnnlm_.layer1_size,
                 rnnlm_.layer2_size, rnnlm_.direct_order,
                 max_order);
    for (int i = 0; i < rnnlm_.layer0_size * rnnlm_.layer1_size; i++)
      d.syn0.push_back (static_cast<double> (rnnlm_.syn0 [i].weight));

    for (int i = 0; i < rnnlm_.layer1_size * rnnlm_.layer2_size; i++)
      d.syn1.push_back (static_cast<double> (rnnlm_.syn1 [i].weight));

    for (int i = 0; i < rnnlm_.direct_size; i++)
      d.synd.push_back (static_cast<double> (rnnlm_.syn_d [i]));

    return d;
  }

  Hasher CopyVocabHash (const string g_delim, const string gp_delim) {
    Hasher h (rnnlm_.class_size, g_delim, gp_delim);
    for (int i = 0; i < rnnlm_.vocab_size; i++) {
      string word = rnnlm_.vocab [i].word;
      h.AddWordToVocab (word, rnnlm_.vocab [i].cn);
    }
    h.SortVocab ();
    h.SetClasses ();
    for (int i = 0; i < h.vocab_.size (); i++)
      h.MapToken (h.vocab_[i].word);

    return h;
  }

  Hasher CopyVocabHash () {
    Hasher h (rnnlm_.class_size);
    for (int i = 0; i < rnnlm_.vocab_size; i++) {
      string word = rnnlm_.vocab [i].word;
      h.AddWordToVocab (word, rnnlm_.vocab [i].cn);
    }
    h.SortVocab ();
    h.SetClasses ();
    for (int i = 0; i < h.vocab_.size (); i++)
      h.MapToken (h.vocab_[i].word);

    return h;
  }

 private:
  CRnnLM rnnlm_;  // 1The actual model
};
#endif  // SRC_INCLUDE_LEGACYRNNLMREADER_H_
