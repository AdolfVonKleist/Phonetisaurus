/*
 ARPA2WFST.hpp

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
#ifndef SRC_INCLUDE_ARPA2WFST_H_
#define SRC_INCLUDE_ARPA2WFST_H_
#include <float.h>
#include <fst/fstlib.h>
#include <string>
#include <vector>
#include "./util.h"
using namespace fst;

class ARPA2WFST {
  /*
      Transform a statistical language model in ARPA format
      to an equivalent Weighted Finite-State Acceptor.
      This implementation adopts the Google format for the output
      WFSA.  This differs from previous implementations in several ways:

       Start-state and <s> arcs:
       * There are no explicit sentence-begin (<s>) arcs
       * There is a single <s> start-state.

       Final-state and </s> arcs:
       * There are no explicit sentence-end (</s>) arcs
       * There is no explicit </s> state
       * NGrams ending in </s> are designated as final
            states, and any probability is assigned
            to the final weight of said state.
  */

 public:
  ifstream   arpa_lm_fp;
  string     arpa_lm_file;
  string     line;
  size_t     max_order;
  size_t     current_order;

  // Default values
  string     eps;      // epsilon symbol
  string     sb;       // sentence begin tag
  string     se;       // sentence end tag
  string     split;    // delimiter separating input/output in G2P ARPA file
  string     skip;     // graphemic null
  string     tie;      // tie for clusters

  // WFST stuff
  VectorFst<StdArc>  arpafst;
  SymbolTable*   ssyms;
  SymbolTable*   isyms;
  SymbolTable*   osyms;

  ARPA2WFST (string lm, string eps, string sb, string se,
             string split, string skip, string tie)
      : eps (eps), sb (sb), se (se), split (split), skip (skip), tie (tie) {
    arpa_lm_fp.open (lm.c_str ());
    arpa_lm_file  = lm;
    current_order = 0;
    max_order     = 0;

    // Initialize the fst and symbol tables
    ssyms = new SymbolTable ("ssyms");
    isyms = new SymbolTable ("isyms");
    osyms = new SymbolTable ("osyms");

    arpafst.AddState ();
    arpafst.SetStart (0);
    ssyms->AddSymbol (sb);
    ssyms->AddSymbol (se);

    isyms->AddSymbol (eps);
    isyms->AddSymbol (tie);
    isyms->AddSymbol (skip);

    osyms->AddSymbol (eps);
    osyms->AddSymbol (tie);
    osyms->AddSymbol (skip);
  }

  void arpa_to_wfst () {
    /*
    Convert an ARPA format Statistical Language Model to WFST format suitable
    for use with phonetisaurus-g2p.  In this implementation we adopt the Google
    convention where the the sentence-begin (<s>) and sentence-end (</s>) tokens
    are represented *implicitly*, without arcs, and the model has multiple final
    states.

    This simplifies downstream processing for pronunciation generation, and has
    the added desirable side-effect of achieving a significant reduction in the
    number of transitions in the resulting WFST model.

    The model is expected to be in the following standardized format:

         \data\
         ngram 1=M
         ngram 2=M
         ...
         ngram N=M

         \1-grams:
         p(w)      w     bow(w)
         ...
         \2-grams:
         p(v,w)    v w   bow(v,w)
         ...
         \3-grams:
         p(u,v,w)  u v w

         \end\

    where M refers to the number of unique NGrams for this order,
    and N refers to the maximum NGram order of the model.
    Similarly, p(w) refers to the probability of NGram 'w', and
    bow(w) refers to the back-off weight for NGram 'w'.  The highest
    order of the model does not have back-off weights.  Back-off
    weights equal to 0.0 in log-base 10 may be omitted to save space,
    and NGrams ending in sentence-end (</s>) naturally do not have
    back-off weights.

    The NGram columns are separated by a single tab (\t).

    */

    if (arpa_lm_fp.is_open ()) {
      while (arpa_lm_fp.good ()) {
        getline (arpa_lm_fp, line);
        if (current_order > 0 && line.compare ("") != 0 \
            && line.compare (0, 1, "\\") != 0) {
          // Split the input using '\s+' as a delimiter
          vector<string> ngram;
          istringstream iss (line);
          copy (istream_iterator<string>(iss),
                istream_iterator<string>(),
                back_inserter<vector<string> >(ngram));
          double prob = atof (ngram.front ().c_str ());
          ngram.erase (ngram.begin ());
          double bow  = 0.0;
          if (ngram.size () > current_order) {
            bow = atof (ngram.back ().c_str ());
            ngram.pop_back ();
          }
          // We have a unigram model
          if (max_order == 1) {
            // Assume unigram ARPA model has a <s>
            // sentence-begin line.  Is this true?
            if (ngram.front ().compare (sb) == 0) {
              continue;
            } else if (ngram.front ().compare (se) == 0) {
              _make_final (sb, log10_2tropical (prob));
            } else {
              _make_arc (sb, sb, ngram.at (0), prob);
            }
            // We have a higher order model
          }else if (current_order == 1) {
            if (ngram.front ().compare (sb) == 0) {
              _make_arc (sb, eps, eps, bow);
            }else if (ngram.back ().compare (se) == 0) {
              _make_final (eps, prob);
            }else{
              _make_arc (eps, ngram.front (), ngram.front (), prob);
              _make_arc (ngram.front (), eps, eps, bow);
            }
          }else if (current_order < max_order) {
            string isym = ngram.back ();
            string s_st = _join (ngram.begin (), ngram.end () - 1);
            if (isym.compare (se) == 0) {
              _make_final (s_st, prob);
            }else{
              string e_st = _join (ngram.begin (), ngram.end ());
              string b_st = _join (ngram.begin () + 1, ngram.end ());
              _make_arc (s_st, e_st, isym, prob);
              _make_arc (e_st, b_st, eps, bow);
            }
          }else if (current_order == max_order) {
            string isym = ngram.back ();
            string s_st = _join (ngram.begin (), ngram.end () - 1);
            if (isym.compare (se) == 0) {
              _make_final (s_st, prob);
            }else{
              string e_st = _join (ngram.begin() + 1, ngram.end ());
              _make_arc (s_st, e_st, isym, prob);
            }
          }
        }else if (line.size() > 4 && line.compare (0, 5, "ngram") == 0) {
          for (size_t i = 0; i < line.size (); i++)
            if (line.compare (i, 1, "=") == 0)
              line.at (i) = ' ';
          vector<string> parts;
          istringstream iss (line);
          copy (istream_iterator<string>(iss),
                istream_iterator<string>(),
                back_inserter<vector<string> >(parts));
          // Make sure there is at least one n-gram for max order!
          if (atoi (parts [2].c_str()) > 0)
            max_order = (size_t)atoi (parts [1].c_str ()) > max_order \
              ? atoi (parts [1].c_str ()) : max_order;
          // cerr << "MaxOrder: " << max_order << endl;
          // max_order = (size_t)atoi(&line[6])>max_order ?
          // atoi(&line[6]) : max_order;
        }else if (line.compare ("\\data\\") == 0) {
          continue;
        }else if (line.compare ("\\end\\") == 0) {
          break;
        }else if (line.size() > 0 && line.compare (0, 1, "\\") == 0) {
          line.replace (0, 1, "");
          if (line.compare (1, 1, "-" ) == 0)
            line.replace (1, 7, "");
          else  // Will work up to N=99.
            line.replace (2, 7, "");
          current_order = atoi (&line [0]);
        }
      }
      arpa_lm_fp.close();

      _patch_labels (isyms, true);
      _patch_labels (osyms, false);
      arpafst.SetInputSymbols (isyms);
      arpafst.SetOutputSymbols (osyms);
    }else{
      cout << "Unable to open file: " << arpa_lm_file << endl;
    }
  }

 private:
  double log10_2tropical (double val) {
    /*
    Convert an ARPA-standard log10(val) value to the
    tropical/log semiring, which is -logE(val).
    Make sure that the result is a valid number.

    The decoder will work even if the values are BadNumbers
    or Infinity, but fstinfo will treat the result as malformed.
    */

    val = log(10.0) * val * -1.0;

    if( !(val <= DBL_MAX && val >= -DBL_MAX) )
      val = 999.0;

    if( val != val )
      val = 999.0;

    return val;
  }

  void _make_arc (string istate, string ostate, string isym, double weight) {
    // Build up an arc for the WFST.  Weights default to the Log semiring.
    int is_id = ssyms->Find (istate);
    int os_id = ssyms->Find (ostate);
    if (is_id == -1) {
      is_id = arpafst.AddState();
      ssyms->AddSymbol (istate, is_id);
    }
    if (os_id == -1) {
      os_id = arpafst.AddState ();
      ssyms->AddSymbol (ostate, os_id);
    }
    weight = log10_2tropical (weight);

    vector<string> io = tokenize_utf8_string (&isym, &split);
    if (io.size () == 2) {
      /*
      Keep everything as it is: helpful for rescoring and reranking.
    if( io[0]==skip )
      io[0] = eps;
    if( io[1]==skip )
      io[1] = eps;
      */
      arpafst.AddArc (is_id, StdArc (isyms->AddSymbol (io [0]),
                                     osyms->AddSymbol (io [1]),
                                     weight, os_id));
    }else{
      arpafst.AddArc (is_id, StdArc (isyms->AddSymbol (isym),
                                     osyms->AddSymbol (isym),
                                     weight, os_id));
    }

    return;
  }

  void _make_final (string fstate, double weight) {
    /*
    Make a state final, and convert the input weight as needed.
    */

    weight = log10_2tropical (weight);
    int sid = ssyms->Find (fstate);
    if (sid == -1) {
      sid = arpafst.AddState ();
      ssyms->AddSymbol (fstate, sid);
    }
    arpafst.SetFinal (sid, weight);

    return;
  }

  string _join (vector<string>::iterator start,
                vector<string>::iterator end) {
    // Join the elements of a string vector into a single string
    stringstream ss;
    for (vector<string>::iterator it = start; it < end; it++) {
      if (it != start)
        ss << ",";
      ss << *it;
    }
    return ss.str ();
  }


  void _patch_labels (SymbolTable* syms, bool input) {
    /*
    Patch all labels.  In some edge cases it is possible
    to end up grapheme subsequences: e.g. 'QU' where one or
    both tokens is only mapped to the multi-subsequence.  In thise
    case the independent 'Q' and/or 'U' token will never appear
    in isolation.
    This bit resolves this by:

       a.) finding and adding these missing subsequence tokens
       b.) adding backoff loops to the LM

    */
    for (unsigned int i = 3; i < syms->NumSymbols(); i++) {
      string sym = syms->Find (i);
      vector<string> parts  = tokenize_utf8_string (&sym, &tie);
      if (parts.size() > 1) {
        for (unsigned int j = 0; j < parts.size (); j++) {
          if (syms->Find (parts [j]) == -1) {
            // Add the missing symbol
            int k = syms->AddSymbol (parts [j]);
            // Add a backoff loop mapped to the 'skip'
            if (input == true)
              arpafst.AddArc (1, StdArc (k, 2, 99, 1));
            else
              arpafst.AddArc (1, StdArc (2, k, 99, 1));
          }
        }
      }
    }
  }
};

#endif  // SRC_INCLUDE_ARPA2WFST_H_

