#ifndef RNNLM_DECODER_H__
#define RNNLM_DECODER_H__

#include <fst/fstlib.h>
#include <include/LegacyRnnLMDecodable.h>
#include <include/LegacyRnnLMHash.h>
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
    //Copy an existing token and update the 
    // various layers as needed
    hlayer.resize (tok->hlayer.size(), 0.0);
    history.resize (tok->history.size (), 0);

    //Would it be more efficient to perform the hash 
    // by iterating back throug the parent tokens?
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
    //return t.state * kPrime0 + t.word * kPrime1;
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

struct Chunk {
 public:
  Chunk (int word, double cost, double total) 
    : w (word), c (cost), t (total) { }
  int w;
  double c;
  double t;
};

template <class D>
class RnnLMDecoder {
 public:
  typedef D Decodable;
  typedef vector<vector<Chunk> > Results;
  typedef Heap<Token*, TokenPointerCompare, false> Queue;
  typedef unordered_set<Token, TokenHash, TokenCompare> TokenSet;

  RnnLMDecoder (Decodable& decodable) 
    : d (decodable) { }

  double Heuristic (int nstate, int nstates, double hcost) {
    int factor = nstates - nstate - 1;
    if (factor > 0) 
      return factor * hcost;
    return 0.0;
  }

  Results Decode (VectorFst<StdArc>& fst, int beam, int kMax, int nbest) {
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
	  Token* a = (Token*)&(*top);
	  vector<Chunk> result;
	  while (a->prev != NULL) {
	    result.push_back (Chunk (a->word, a->weight, a->total));
	    a = (Token*)a->prev;
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
	    Token ntoken ((Token*)&(*top), map [i], arc.nextstate);
	    ntoken.weight = -log (d.ComputeNet ((*top), &ntoken));
	    if (ntoken.weight > beam)
	      continue;

	    ntoken.total += top->total + ntoken.weight;
	    //Heuristic here if we use one (we don't)
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

  Results  results;


 private:
  void Initialize () {
    pool.clear ();
    results.clear ();
    
    Token start (d.hsize, d.max_order);
    pool.insert (start);
    TokenSet::iterator prev = pool.find (start);
    prev->key = sQueue [0].Insert ((Token*)&(*prev));
    return;
  }

  Decodable& d;
  vector<Queue> sQueue;
  TokenSet pool;
};
#endif // RNNLM_DECODER_H__
