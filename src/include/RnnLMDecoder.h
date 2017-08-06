#ifndef SRC_INCLUDE_RNNLMDECODER_H_
#define SRC_INCLUDE_RNNLMDECODER_H_

#include <fst/fstlib.h>
#include <include/LegacyRnnLMDecodable.h>
#include <include/LegacyRnnLMHash.h>
#include <include/util.h>
#include <string>
#include <vector>
#include <unordered_set>

using fst::VectorFst;
using fst::ArcIterator;
using fst::StateIterator;
using fst::StdArc;
using fst::Heap;
using std::vector;
using std::unordered_set;


class Token {
 public:
  Token (int hsize, int max_order)
    : word (0), weight (0.0), total (0.0),
      g (0.0), prev (NULL), state (0), key (-1) {
    hlayer.resize (hsize, 1.0);
    history.resize (max_order, 0);

    HashHistory ();
  }

  Token (Token* tok, int w, int s)
    : word (w), weight (0.0), total (0.0),
      g (0.0), prev (tok), state (s), key (-1) {
    // Copy an existing token and update the
    //  various layers as needed
    hlayer.resize (tok->hlayer.size(), 0.0);
    history.resize (tok->history.size (), 0);

    // Would it be more efficient to perform the hash
    //  by iterating back throug the parent tokens?
    for (int i = tok->history.size () - 1; i > 0; i--)
      history [i] = tok->history [i - 1];
    history [0] = tok->word;

    HashHistory ();
  }

  void HashHistory () {
    hhash = state * 7853;
    for (int i = 0; i < history.size (); i++)
      hhash = hhash * 7877 + history [i];
  }

  int word;
  mutable double weight;
  mutable double total;
  mutable double g;
  mutable Token* prev;
  int state;
  mutable int key;
  mutable vector<double> hlayer;
  mutable vector<int> history;
  size_t hhash;
};

class TokenCompare {
 public:
  bool operator () (const Token& t1, const Token& t2) const {
    return (t1.state == t2.state &&
            t1.word == t2.word &&
            t1.hhash == t2.hhash);
    /*
     return (t1.state == t2.state &&
            t1.word == t2.word);
    */
  }
};

class TokenHash {
 public:
  size_t operator () (const Token& t) const {
    return t.state * kPrime0 + t.word * kPrime1 + t.hhash * kPrime2;
    // return t.state * kPrime0 + t.word * kPrime1;
  }
 private:
  static const size_t kPrime0;
  static const size_t kPrime1;
  static const size_t kPrime2;
};
const size_t TokenHash::kPrime0 = 7853;
const size_t TokenHash::kPrime1 = 7867;
const size_t TokenHash::kPrime2 = 7873;


class TokenPointerCompare {
 public:
  bool operator () (const Token* t1, const Token* t2) const {
    return (t1->g < t2->g);
  }
};

class Chunk {
 public:
  Chunk (int word, double cost, double total)
    : w (word), c (cost), t (total) { }
  int w;
  double c;
  double t;
  template<class H>
  vector<string> Tokenize (char gpdelim, char gdelim, H& h,
                           bool graphemes = false) const {
    vector<string> gp_elems;
    Split (h.vocab_[w].word, gpdelim, gp_elems);
    vector<string> elems;
    if (graphemes == true)
      Split (gp_elems [0], gdelim, elems);
    else if (gp_elems.size () == 2)
      Split (gp_elems [1], gdelim, elems);
    return elems;
  }
};

class SimpleResult {
 public:
  SimpleResult (string word, vector<double> scores,
                vector<string> pronunciations)
    : word (word), scores (scores), pronunciations (pronunciations) { }

  SimpleResult () { }

  string word;
  vector<double> scores;
  vector<string> pronunciations;
};

/* Standalone function for convenience */
template<class H>
VectorFst<StdArc> WordToRnnLMFst (const vector<string>& word, H& h) {
  VectorFst<StdArc> fst;
  fst.AddState ();
  fst.SetStart (0);
  for (int i = 0; i < word.size (); i++) {
    int hash = h.HashInput (word.begin () + i,
                              word.begin () + i + 1);
    fst.AddState ();
    fst.AddArc (i, StdArc (hash, hash, StdArc::Weight::One(), i + 1));
  }

  for (int i = 0; i < word.size (); i++) {
    for (int j = 2; j <= 3; j++) {
      if (i + j <= word.size ()) {
        int hash = h.HashInput (word.begin () + i, word.begin () + i + j);
        if (h.imap.find (hash) != h.imap.end ())
          fst.AddArc (i, StdArc (hash, hash, StdArc::Weight::One (), i + j));
      }
    }
  }
  fst.SetFinal (word.size (), StdArc::Weight::One ());

  return fst;
}

template <class D>
class RnnLMDecoder {
 public:
  typedef D Decodable;
  typedef vector<vector<Chunk> > RawResults;
  typedef Heap<Token*, TokenPointerCompare> Queue;
  typedef unordered_set<Token, TokenHash, TokenCompare> TokenSet;

  explicit RnnLMDecoder (Decodable& decodable)
    : d (decodable) { }

  double Heuristic (int nstate, int nstates, double hcost) {
    int factor = nstates - nstate - 1;
    if (factor > 0)
      return factor * hcost;
    return 0.0;
  }

  VectorFst<StdArc> WordToRnnLMFst (const vector<string>& word) {
    VectorFst<StdArc> fst;
    fst.AddState ();
    fst.SetStart (0);
    for (int i = 0; i < word.size (); i++) {
      int hash = d.h.HashInput (word.begin () + i,
                              word.begin () + i + 1);
      fst.AddState ();
      fst.AddArc (i, StdArc (hash, hash, StdArc::Weight::One(), i + 1));
    }

    for (int i = 0; i < word.size (); i++) {
      for (int j = 2; j <= 3; j++) {
        if (i + j <= word.size ()) {
          int hash = d.h.HashInput (word.begin () + i, word.begin () + i + j);
          if (d.h.imap.find (hash) != d.h.imap.end ())
            fst.AddArc (i, StdArc (hash, hash, StdArc::Weight::One (), i + j));
        }
      }
    }
    fst.SetFinal (word.size (), StdArc::Weight::One ());

    return fst;
  }

  SimpleResult Decode (const vector<string>& word, int beam, int kMax,
                     int nbest, double thresh, const string& gpdelim,
                     const string& gdelim, const string& skip) {
    RawResults raw_results = DecodeRaw (word, beam, kMax, nbest, thresh);
    SimpleResult simple_result;
    stringstream word_ss;
    for (int i = 0; i < word.size (); i++)
      if (i != word.size () - 1)
        word_ss << word [i];
    simple_result.word = word_ss.str ();

    for (int i = 0; i < raw_results.size (); i++) {
      const vector<Chunk>& result = raw_results [i];
      stringstream pronunciation_ss;
      for (vector<Chunk>::const_iterator it = result.begin ();
           it != result.end (); ++it) {
        vector<string> chunk_vec = \
          it->Tokenize<LegacyRnnLMHash> (static_cast<char>(*gpdelim.c_str ()),
                                         static_cast<char>(*gdelim.c_str ()),
                                         d.h);
        for (int j = 0; j < chunk_vec.size (); j++) {
          if (chunk_vec [j].compare (skip) != 0)
            pronunciation_ss << chunk_vec [j];
          else
            continue;

          if (!(it == result.end () && j != chunk_vec.size () - 1))
            pronunciation_ss << " ";
        }
        if (it+1 == result.end ())
          simple_result.scores.push_back (it->t);
      }
      simple_result.pronunciations.push_back (pronunciation_ss.str ());
    }

    return simple_result;
  }

  RawResults DecodeRaw (const vector<string>& word, int beam, int kMax,
                        int nbest, double thresh = 0.0) {
    VectorFst<StdArc> fst = WordToRnnLMFst (word);
    for (int i = 0; i < sQueue.size (); i++)
      sQueue [i].Clear ();
    sQueue.resize (fst.NumStates () + 1);

    Initialize ();
    int n = 0;
    for (StateIterator<VectorFst<StdArc> > siter (fst);
         !siter.Done(); siter.Next ()) {
      int s = siter.Value ();
      int k = 0;
      while (!sQueue [s].Empty () && k < kMax && n < nbest) {
        Token* top = sQueue [s].Pop ();
        if (fst.Final (top->state) != StdArc::Weight::Zero ()) {
          // Token* a = (Token*)&(*top);
          Token* a = reinterpret_cast<Token*>(top);
          if (n > 0 && thresh > 0.0)
            if (a->total - results [0][results [0].size () - 1].t > thresh)
              break;

          vector<Chunk> result;
          while (a->prev != NULL) {
            result.push_back (Chunk (a->word, a->weight, a->total));
            a = reinterpret_cast<Token*> (a->prev);
          }
          reverse (result.begin (), result.end ());
          results.push_back (result);
          n++;
          continue;
        }

        for (ArcIterator<VectorFst<StdArc> > aiter (fst, top->state);
             !aiter.Done (); aiter.Next ()) {
          const StdArc& arc = aiter.Value ();
          const vector<int>& map = d.h.imap [arc.ilabel];

          for (int i = 0; i < map.size (); i++) {
            Token ntoken (reinterpret_cast<Token*>(top), map [i],
                          arc.nextstate);
            ntoken.weight = -log (d.ComputeNet ((*top), &ntoken));
            if (ntoken.weight > beam)
              continue;

            ntoken.total += top->total + ntoken.weight;
            // Heuristic here if we use one (we don't)
            ntoken.g = ntoken.total;

            TokenSet::iterator niterator = pool.find (ntoken);

            if (niterator == pool.end ()) {
              pool.insert (ntoken);
              Token* npointer = (Token*)&(*pool.find (ntoken));
              sQueue [arc.nextstate].Insert (npointer);
            } else {
              if (ntoken.g < niterator->g) {
                niterator->weight  = ntoken.weight;
                niterator->total   = ntoken.total;
                niterator->prev    = ntoken.prev;
                niterator->history = ntoken.history;
                niterator->g       = ntoken.g;
                niterator->hlayer  = ntoken.hlayer;
                sQueue [arc.nextstate].Insert ((Token*)&(*niterator));
              }
            }
          }
        }
        k++;
      }
    }
    return results;
  }

  RawResults  results;


 private:
  void Initialize () {
    pool.clear ();
    results.clear ();

    Token start (d.hsize, d.max_order);
    pool.insert (start);
    TokenSet::iterator prev = pool.find (start);
    prev->key = sQueue [0].Insert (reinterpret_cast<Token*>(&prev));
    return;
  }

  Decodable& d;
  vector<Queue> sQueue;
  TokenSet pool;
};
#endif  // SRC_INCLUDE_RNNLMDECODER_H_
