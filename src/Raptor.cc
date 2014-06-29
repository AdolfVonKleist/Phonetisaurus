#include <fst/fstlib.h>
#include "RnnLMPy.h"
#include "PhonetisaurusRex.h"
using namespace fst;

struct Token {
  Token () { }

  Token (int state, float weight, const Token* prev, int sym, vector<string> history)
    : state_(state), weight_(weight), prev_(prev), sym_(sym), history_(history) { }

  Token (int state, float weight, const Token* prev) 
    : state_(state), weight_(weight), prev_(prev), sym_(0) { }

  Token (int state, float weight)
    : state_(state), weight_(weight), sym_(0) { }

  int state_;
  float weight_;
  const Token* prev_;
  int sym_;
  vector<string> history_;
};

struct tokencompare {
  bool operator() (const Token& x, const Token& y) {
    return (x.weight_ == y.weight_ && x.state_ == y.state_);
  }
};


template <class T>
class TokenCompare {
 public:
  TokenCompare () {}
  bool operator()(const T& x, const T& y) {
    return x.weight_ <= y.weight_;
  }
};


struct TC {
  bool operator() (const Token& x, const Token& y) const {
    return (x.weight_ == y.weight_ 
	    && x.state_ == y.state_ 
	    && x.sym_ == y.sym_);
  }
};



class TokenHash {
 public:
  size_t operator() (const Token& t) const {
    return t.state_ * kPrime0 + t.weight_ * kPrime1 + t.sym_;
  }
 private:
  static const size_t kPrime0;
  static const size_t kPrime1;
};


const size_t TokenHash::kPrime0 = 7853;
const size_t TokenHash::kPrime1 = 7867;


int main (int argc, char* argv[]) {
  VectorFst<StdArc>* model = VectorFst<StdArc>::Read (argv[1]);
  ifstream infile (argv[3]);
  string word;
  while (getline (infile, word)) {
    
      //string word = argv[3];

  const SymbolTable* isyms = model->InputSymbols ();
  const SymbolTable* osyms = model->OutputSymbols ();
  SymbolMap12M imap, omap;
  SymbolMapM21 invimap, invomap;
  string delim = "";
  int imax = LoadClusters (isyms, &imap, &invimap);
  int omax = LoadClusters (osyms, &omap, &invomap);
  VectorFst<StdArc>* fst = new VectorFst<StdArc> ();
  vector<int> entry = tokenize2ints ((string*)&word, &delim, isyms);
  Entry2FSA (entry, fst, imax, invimap, true);
  fst->SetInputSymbols (isyms);
  fst->SetOutputSymbols (isyms);
  
  //SymbolTable* syms = SymbolTable::ReadText (argv[2]);
  RnnLMPy rnnlm (argv[2]);
  int nbest = atoi (argv[4]);
  float beam = atof (argv[5]);

  Token t (0, 0.0, NULL);
  typedef tr1::unordered_set<Token, TokenHash, TC> USet;
  USet uset;
  TokenCompare<Token> comp();
  Heap<Token, TokenCompare<Token>, false> heap;

  heap.Insert(t);
  uset.insert (t);
  vector<Token> last;

  while (!heap.Empty() && last.size() < nbest) {
    //fst->Final (heap.Top().state_) == StdArc::Weight::Zero()) {
    //if (last.size() > 3)
    //  break;
    Token n = heap.Pop();
    USet::iterator titer = uset.find (n);

    for (ArcIterator<VectorFst<StdArc> > aiter(*fst, n.state_); 
	 !aiter.Done(); aiter.Next()) {
      const StdArc& arc = aiter.Value();
      string label = isyms->Find (arc.ilabel);
      if (arc.ilabel > 1) {
	vector<int> chunks = rnnlm.GetJointVocab (label);
	float best_chunk = -999;
	for (int i = 0; i < chunks.size(); i++) {
	  string chunk = rnnlm.GetString (chunks[i]);
	  vector<string> history = titer->history_;
	  history.push_back (chunk);

	  UttResult result = rnnlm.EvaluateSentence (history);
	  if (result.sent_prob > best_chunk)
	    best_chunk = result.sent_prob;
	  else if (abs (best_chunk - result.sent_prob) > beam)
	    continue;
	  Token q (arc.nextstate, 
		   -1 * result.sent_prob,
		   &(*titer), 
		   arc.ilabel, 
		   history
	    );
	  uset.insert (q);
	  heap.Insert (q);
	  if (fst->Final (arc.nextstate) != StdArc::Weight::Zero()) {
	    last.push_back (q);
	  }
	}
      } else if (arc.ilabel == 0) {
	vector<string> history = titer->history_;
	history.push_back ("</s>");
	UttResult result = rnnlm.EvaluateSentence (history);
	/*
	for (int j = 0; j < history.size(); j++)
	  cout << history[j] << " ";
	cout << result.sent_prob << " " << n.state_ << endl;
	*/
	Token q (arc.nextstate, 
		 -1 * result.sent_prob,
		 &(*titer), 
		 arc.ilabel, 
		 history
	  );
	uset.insert (q);
	heap.Insert (q);
      } else if (arc.ilabel == 1) {
	if (fst->Final (arc.nextstate) != StdArc::Weight::Zero()) {
	  last.push_back (*titer);
	}
      }
    }
  }

  for (int j = 0; j < last.size(); j++) {
    vector<Token> vv;
    Token* tp = &last[j];

    cout << tp->weight_  << "\t";
    for (int i = 0; i < tp->history_.size(); i++)
      cout << tp->history_[i] << ((i == tp->history_.size()) ? "" : " ");
    cout << endl;
  }
  /*
  while (tp->prev_ != NULL) {
    vv.push_back(*tp);
    tp = (Token*)tp->prev_;
  }
  vv.push_back(*tp);
  
  for (int i = vv.size()-1; i >= 0; i--)
    cout << isyms->Find (vv[i].sym_) << " ";
  cout << endl;
  */
  }
  return 1;
}
