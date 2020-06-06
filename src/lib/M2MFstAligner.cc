/*
 M2MFstAligner.cpp

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
#include "include/M2MFstAligner.h"


M2MFstAligner::M2MFstAligner () {
  //Default constructor
}

M2MFstAligner::M2MFstAligner (bool seq1_del, bool seq2_del,
                  unsigned int seq1_max, unsigned int seq2_max,
                  string seq1_sep, string seq2_sep,
                  string s1s2_sep, string eps, string skip,
                  bool penalize, bool penalize_em,
                  bool restrict, bool grow)
  : seq1_del (seq1_del), seq2_del (seq2_del), seq1_max (seq1_max),
    seq2_max (seq2_max), seq1_sep (seq1_sep), seq2_sep (seq2_sep),
    s1s2_sep (s1s2_sep), eps (eps), skip (skip), penalize (penalize),
    penalize_em (penalize_em), restrict (restrict), grow (grow) {

  //Base constructor.  Determine whether or not to allow deletions in
  //seq1 and seq2 as well as the maximum allowable subsequence size.
  skipSeqs.insert (0);
  isyms = new SymbolTable("syms");

  //Add all the important symbols to the table.  We can store these
  // in the model that we train and then attach them to the fst model
  // if we want to use it later on.
  //Thus, in addition to eps->0, we reserve symbol ids 1-4 as well.
  isyms->AddSymbol (eps);
  isyms->AddSymbol (skip);

  //The '_' as a separator here is dangerous
  isyms->AddSymbol (seq1_sep + "_" + seq2_sep);
  isyms->AddSymbol (s1s2_sep);
  string s1_del_str = seq1_del ? "true" : "false";
  string s2_del_str = seq2_del ? "true" : "false";
  string s1_max_str = itoas (seq1_max);
  string s2_max_str = itoas (seq2_max);
  string model_params = s1_del_str + "_" + s2_del_str + "_" \
    + s1_max_str + "_" + s2_max_str;
  isyms->AddSymbol (model_params);
  total     = LogWeight::Zero ();
  prevTotal = LogWeight::Zero ();
  //penalties.set_empty_key(0);
}

M2MFstAligner::M2MFstAligner (string model_file, bool penalize,
                  bool penalize_em, bool restrict)
  : penalize (penalize), penalize_em (penalize_em), restrict (restrict) {
  /*
    Initialize the aligner with a previously trained model.
    The model requires that the first several symbols in the
    symbols table contain the separator and other bookkeeping info.
  */
  //penalties.set_empty_key(0);
  VectorFst<LogArc>* model = VectorFst<LogArc>::Read (model_file);
  for (StateIterator<VectorFst<LogArc> > siter (*model);
       !siter.Done (); siter.Next ()) {

    LogArc::StateId q = siter.Value ();
    for( ArcIterator<VectorFst<LogArc> > aiter (*model, q);
     !aiter.Done (); aiter.Next ()) {

      const LogArc& arc = aiter.Value ();
      alignment_model.insert (pair<LogArc::Label, LogWeight>
                  (arc.ilabel,arc.weight));
    }
  }

  isyms = (SymbolTable*)model->InputSymbols ();
  int i = 0;
  eps   = isyms->Find (i);//Can't write '0' here for some reason...
  skip  = isyms->Find (1);
  string tie = "_"; //tie to pack parameters

  string sseps = isyms->Find (2);
  vector<string> seps = tokenize_utf8_string (&sseps, &tie);
  seq1_sep = seps [0];
  seq2_sep = seps [1];
  s1s2_sep = isyms->Find (3);

  string sparams = isyms->Find (4);
  vector<string> params = tokenize_utf8_string (&sparams, &tie);
  seq1_del = params [0].compare ("true") ? false : true;
  seq2_del = params [1].compare ("true") ? false : true;
  seq1_max = atoi (params [2].c_str ());
  seq2_max = atoi (params [3].c_str ());
}

void M2MFstAligner::write_model (string model_file) {
  /*
    Write the alignment model to disk using a single-state WFSA.
  */
  VectorFst<LogArc> model;
  model.AddState ();
  model.SetStart (0);
  model.SetFinal (0, LogWeight::One ());

  map<LogArc::Label,LogWeight>::iterator it;
  for (it = alignment_model.begin (); it != alignment_model.end (); it++)
    model.AddArc (0, LogArc( (*it).first, (*it).first, (*it).second, 0));

  model.SetInputSymbols (isyms);
  model.Write (model_file);

  return;
}

void M2MFstAligner::expectation () {
  /*
    Here we compute the arc posteriors.  This routine is almost
    fun to implement in the FST paradigm.
  */
  //omp_set_num_threads (4);
  //#pragma omp parallel for
  for (unsigned int i = 0; i < fsas.size (); i++) {
    //Compute Forward and Backward probabilities
    vector<LogWeight> alpha, beta;
    ShortestDistance (fsas.at (i), &alpha);
    ShortestDistance (fsas.at (i), &beta, true);

    //Compute the normalized Gamma probabilities and
    // update our running tally
    for (StateIterator<VectorFst<LogArc> > siter (fsas.at (i));
     !siter.Done (); siter.Next ()) {
      const LogArc::StateId q = siter.Value ();
      for (ArcIterator<VectorFst<LogArc> > aiter (fsas.at (i), q);
           !aiter.Done (); aiter.Next ()) {
        const LogArc& arc = aiter.Value ();
        const LogWeight& gamma = Divide (
                                   Times (Times (alpha [q], arc.weight),
                                   beta [arc.nextstate]), beta [0]
                                 );
        // Check for any BadValue results, otherwise add to the tally.
        // We call this 'prev_alignment_model' which may seem misleading, but
        // this conventions leads to 'alignment_model' being the final version.
        if (gamma.Value () == gamma.Value ()) {
          prev_alignment_model [arc.ilabel]
            = Plus (prev_alignment_model [arc.ilabel], gamma);
          total = Plus (total, gamma);
        }
      }
    }

    alpha.clear ();
    beta.clear ();
  }
}


void M2MFstAligner::_conditional_max (bool y_given_x) {
  /*
    Compute the conditional distribution, P(Y|X) using the WFST paradigm.
    This is bassed on the approach from Shu and Hetherington 2002.
    It is assumed that all WFSTs and operations use the Log semiring.

    Given:
           FST1 = P(X,Y)
    Compute:
           FST2 = P(X)
             := Map_inv(Det(RmEps(Proj_i(FST1))))
           FST3 = P(Y|X)
             := Compose(FST2,FST1)

    Proj_i:  project on input labels
    RmEps:   epsilon removal
    Det:     determinize
    Map_inv: invert weights

    Notes: An analogous process may be used to compute P(X|Y).  In this
      case one would project on OUTPUT labels - Proj_o, and reverse the
      composition order to Compose(FST1,FST2).

    Future work:
      What we are doing here in terms of *generating* the JOINT fst each
      time is really just a dumb hack.  We *should* encode the model in an
      FST and encode the individual lattices, rather than doing the hacky
      manual label encoding that we currently rely on.
  */

  //Joint distribution that we start with
  VectorFst<LogArc>* joint  = new VectorFst<LogArc> ();
  SymbolTable* misyms = new SymbolTable ("misyms");
  SymbolTable* mosyms = new SymbolTable ("mosyms");
  joint->AddState ();
  joint->AddState ();
  joint->SetStart (0);
  joint->SetFinal (1, LogArc::Weight::One ());

  map<LogArc::Label,LogWeight>::iterator it;
  for (it = prev_alignment_model.begin ();
       it != prev_alignment_model.end (); it++) {
    string isym = isyms->Find ((*it).first);
    vector<string> io = tokenize_utf8_string (&isym, &s1s2_sep);
    LogArc arc (
             misyms->AddSymbol (io [0]),
             mosyms->AddSymbol (io [1]),
             (*it).second,
             1
           );
    joint->AddArc (0, arc);
  }

  //VectorFst<LogArc>* joint  = new VectorFst<LogArc>();
  //Push<LogArc,REWEIGHT_TO_FINAL>(*_joint, joint, kPushWeights);
  //joint->SetFinal(1,LogWeight::One());
  joint->Write ("m2mjoint.fst");
  //BEGIN COMPUTE MARGINAL P(X)
  VectorFst<LogArc>* dmarg;
  if (y_given_x)
    dmarg = new VectorFst<LogArc> (ProjectFst<LogArc> (*joint, PROJECT_INPUT));
  else
    dmarg = new VectorFst<LogArc> (ProjectFst<LogArc> (*joint, PROJECT_OUTPUT));

  RmEpsilon (dmarg);
  VectorFst<LogArc>* marg = new VectorFst<LogArc> ();
  Determinize (*dmarg, marg);
  ArcMap (marg, InvertWeightMapper<LogArc> ());

  if (y_given_x)
    ArcSort (marg, OLabelCompare<LogArc> ());
  else
    ArcSort (marg, ILabelCompare<LogArc> ());
  //END COMPUTE MARGINAL P(X)
  marg->Write ("marg.fst");

  //CONDITIONAL P(Y|X)
  VectorFst<LogArc>* cond = new VectorFst<LogArc> ();
  if (y_given_x)
    Compose (*marg, *joint, cond);
  else
    Compose (*joint, *marg, cond);
  //cond now contains the conditional distribution P(Y|X)
  cond->Write ("cond.fst");
  //Now update the model with the new values
  for (MutableArcIterator<VectorFst<LogArc> > aiter (cond, 0);
       !aiter.Done (); aiter.Next ()) {
    LogArc arc = aiter.Value ();
    string lab = misyms->Find (arc.ilabel) + "}" + mosyms->Find (arc.olabel);
    int labi   = isyms->Find (lab);
    alignment_model [labi] = arc.weight;
    prev_alignment_model [labi] = LogWeight::Zero ();
  }

  delete joint;
  delete marg;
  delete cond;
  delete dmarg;
  delete misyms;
  delete mosyms;

  return;
}


float M2MFstAligner::maximization (bool lastiter) {
  // Maximization. Standard approach is simple count normalization.
  // The 'penalize' option penalizes links by total length.  Results
  // seem to be inconclusive. Probably get an improvement by
  // distinguishing between gaps and insertions, etc.
  bool cond = false;
  float change = abs (total.Value () - prevTotal.Value ());
  if (cond == false) {
    map<LogArc::Label,LogWeight>::iterator it;
    prevTotal = total;

    //Normalize and iterate to the next model.  We apply it dynamically
    // during the expectation step.
    for (it = prev_alignment_model.begin ();
     it != prev_alignment_model.end (); it++) {
      alignment_model [(*it).first] = Divide ((*it).second, total);
      (*it).second = LogWeight::Zero ();
    }
  }else{
    _conditional_max (true);
  }


  for (unsigned int i = 0; i < fsas.size(); i++) {
    for (StateIterator<VectorFst<LogArc> > siter (fsas [i]);
     !siter.Done (); siter.Next ()) {
      LogArc::StateId q = siter.Value ();
      for (MutableArcIterator<VectorFst<LogArc> > aiter (&fsas [i], q);
       !aiter.Done (); aiter.Next ()) {
        LogArc arc = aiter.Value ();

        if (penalize_em == true) {
          LabelDatum* ld = &penalties [arc.ilabel];
          if (ld->lhs > 1 && ld->rhs > 1) {
            arc.weight = 99;
          } else if (ld->lhsE == false && ld->rhsE == false) {
            arc.weight = arc.weight.Value () * ld->tot;
          }
          /*
            else{
            arc.weight = arc.weight.Value() * (ld->tot+10);
            }
          */
          if (arc.weight == LogWeight::Zero () || arc.weight != arc.weight)
            arc.weight = 99;
        } else {
          arc.weight = alignment_model [arc.ilabel];
        }
        aiter.SetValue (arc);
      }
    }
  }

  total = LogWeight::Zero ();
  return change;
}


void M2MFstAligner::Sequences2FST (VectorFst<LogArc>* fst, int s1m, int s2m,
                                   vector<string>* seq1, vector<string>* seq2) {
  /*
    Build an FST that represents all possible alignments between seq1 and seq2,
    given the parameter values input by the user.  Here we encode the input and
    output labels, in fact creating a WFSA.  This simplifies the training
    process, but means that we can only easily compute a joint maximization.
    In practice joint maximization seems to give the best results anyway, so it
    probably doesn't matter.

    Note: this also performs the initizization routine.  It performs a UNIFORM
    initialization meaning that every non-null alignment sequence is eventually
    initialized to 1/Num(unique_alignments). It might be more appropriate to
    consider subsequence length here, but for now we stick to the m2m-aligner
    approach.

    TODO: Add an FST version and support for conditional maximization.  May be
    useful for languages like Japanese where there is a distinct imbalance in
    the seq1->seq2 length correspondences.
  */
  int istate=0; int ostate=0;
  for (unsigned int i = 0; i <= seq1->size (); i++) {
    for (unsigned int j = 0; j <= seq2->size (); j++) {
      fst->AddState ();
      istate = i * (seq2->size () + 1) + j;

      //Epsilon arcs for seq1
      if (seq1_del == true)
        for (unsigned int l = 1; l <= s2m; l++) {
          if (j + l <= seq2->size ()) {
            vector<string> subseq2 (seq2->begin () + j, seq2->begin () + j + l);
            int is = isyms->AddSymbol (
                       skip + s1s2_sep + vec2str (subseq2, seq2_sep)
                     );
            ostate = i * (seq2->size () + 1) + (j + l);
            LogArc arc (is, is, 99, ostate);
            fst->AddArc (istate, arc);
          }
        }

      //Epsilon arcs for seq2
      if (seq2_del == true)
        for (unsigned int k = 1; k <= s1m; k++) {
          if (i + k <= seq1->size ()) {
            vector<string> subseq1 (seq1->begin () + i, seq1->begin () + i + k);
            int is = isyms->AddSymbol (
                       vec2str (subseq1, seq1_sep) + s1s2_sep + skip
                     );
            ostate = (i + k) * (seq2->size () + 1) + j;
            LogArc arc (is, is, 99, ostate);
            fst->AddArc (istate, arc);
          }
        }

      //All the other arcs
      for (unsigned int k = 1; k <= s1m; k++) {
        for (unsigned int l = 1; l <= s2m; l++) {
          if (i + k <= seq1->size () && j + l <= seq2->size ()) {
            vector<string> subseq1 (seq1->begin () + i, seq1->begin () + i + k);
            string s1 = vec2str (subseq1, seq1_sep);
            vector<string> subseq2 (seq2->begin () + j, seq2->begin () + j + l);
            string s2 = vec2str (subseq2, seq2_sep);
            //This says only 1-M and N-1 allowed, no M-N links!
            if (restrict == true && l > 1 && k > 1)
              continue;

            int is = isyms->AddSymbol (s1 + s1s2_sep + s2);
            ostate = (i + k) * (seq2->size () + 1) + (j + l);
            LogArc arc (is, is, LogWeight::One ().Value () * (k + l), ostate);
            fst->AddArc (istate, arc);
            //During the initialization phase, just count non-eps transitions
            //We currently initialize to uniform probability so there is also
            // no need to tally anything here.
          }
        }
      }

    }
  }

  fst->SetStart (0);
  fst->SetFinal (
    ((seq1->size () + 1) * (seq2->size () + 1)) - 1, LogWeight::One ()
  );

  //Unless seq1_del==true && seq2_del==true we will have unconnected states
  // thus we need to run connect to clean out these states
  if (seq1_del == false || seq2_del == false)
    Connect (fst);

  if (fst->NumStates () == 0) {
    cerr << "Alignment failed: ";
    for (int a = 0; a < seq1->size (); a++)
      cerr << (*seq1)[a] << (a == seq1->size () - 1 ? "\n" : " ");
  }
}

void M2MFstAligner::Sequences2FST (VectorFst<LogArc>* fst,
                                   vector<string>* seq1, vector<string>* seq2) {

  int s1m = seq1_max;
  int s2m = seq2_max;
  Sequences2FST (fst, s1m, s2m, seq1, seq2);
  while (grow == true && fst->NumStates () == 0) {
    fst->DeleteStates ();
    s1m += 1;
    s2m += 1;
    Sequences2FST (fst, s1m, s2m, seq1, seq2);
  }

  //Only add arcs that are in the FINAL fst to the model
  for (StateIterator<VectorFst<LogArc> > siter (*fst);
       !siter.Done (); siter.Next ()) {

    LogArc::StateId q = siter.Value ();
    for (ArcIterator<VectorFst<LogArc> > aiter (*fst, q);
         !aiter.Done (); aiter.Next ()) {
      const LogArc& arc = aiter.Value ();

      if (prev_alignment_model.find (arc.ilabel)
          == prev_alignment_model.end ()) {
        prev_alignment_model.insert (
          pair<LogArc::Label,LogWeight> (arc.ilabel, arc.weight)
        );

        string sym = isyms->Find (arc.ilabel);
        size_t del = sym.find ("}");
        size_t chu = sym.find ("|");
        int k = 1; int l = 1;

        if (chu != string::npos) {
          if (chu < del)
            k += 1;
          else
            l += 1;
        }
        _compute_penalties (arc.ilabel, k, l, false, false);
      } else {
        prev_alignment_model [arc.ilabel]
          = Plus (prev_alignment_model [arc.ilabel], arc.weight);
      }
      total = Plus (total, arc.weight);
    }
  }

  return;
}

void M2MFstAligner::Sequences2FSTNoInit (VectorFst<LogArc>* fst,
                                         vector<string>* seq1,
                                         vector<string>* seq2) {
  /*
    Build an FST that represents all possible alignments between seq1 and
    seq2, given the parameter values input by the user.  Here we encode
    the input and output labels, in fact creating a WFSA.  This simplifies
    the training process, but means that we can only easily compute a joint
    maximization.  In practice joint maximization seems to give the best
    results anyway, so it probably doesn't matter.
  */
  int istate = 0; int ostate = 0;
  for (unsigned int i = 0; i <= seq1->size (); i++) {
    for (unsigned int j = 0; j <= seq2->size (); j++) {
      fst->AddState ();
      istate = i * (seq2->size () + 1) + j;

      //Epsilon arcs for seq1
      if (seq1_del == true)
        for (unsigned int l = 1; l <= seq2_max; l++) {
          if (j+l <= seq2->size ()) {
            vector<string> subseq2 (seq2->begin () + j, seq2->begin () + j + l);
            int is = isyms->Find (
                       skip + s1s2_sep + vec2str (subseq2, seq2_sep)
                     );
            ostate = i * (seq2->size () + 1) + (j + l);
            LogArc arc (is, is, alignment_model [is], ostate);
            _compute_penalties (arc.ilabel, 1, l, true, false);
            fst->AddArc (istate, arc);
          }
        }

      //Epsilon arcs for seq2
      if (seq2_del == true)
        for (unsigned int k = 1; k <= seq1_max; k++) {
          if (i + k <= seq1->size ()) {
            vector<string> subseq1 (seq1->begin () + i, seq1->begin () + i + k);
            int is = isyms->Find (vec2str (subseq1, seq1_sep) + s1s2_sep + skip);
            ostate = (i + k) * (seq2->size () + 1) + j;
            LogArc arc (is, is, alignment_model [is], ostate);
            _compute_penalties (arc.ilabel, k, 1, false, true);
            fst->AddArc (istate, arc);
          }
        }

      //All the other arcs
      for (unsigned int k = 1; k <= seq1_max; k++) {
        for (unsigned int l = 1; l <= seq2_max; l++) {
          if (i + k <= seq1->size () && j + l <= seq2->size ()) {
            vector<string> subseq1 (seq1->begin () + i, seq1->begin () + i + k);
            string s1 = vec2str (subseq1, seq1_sep);
            vector<string> subseq2 (seq2->begin () + j, seq2->begin () + j + l);
            string s2 = vec2str (subseq2, seq2_sep);
            if (restrict == true && l > 1 && k > 1)
              continue;
            int is = isyms->Find (s1 + s1s2_sep + s2);
            ostate = (i + k) * (seq2->size () + 1) + (j + l);
            LogArc arc (is, is, alignment_model [is], ostate);
            _compute_penalties (arc.ilabel, k, l, false, false);
            fst->AddArc (istate, arc);
          }
        }
      }
    }
  }

  fst->SetStart (0);
  fst->SetFinal (((seq1->size () + 1) * (seq2->size () + 1)) - 1,
                 LogWeight::One ());
  //Unless seq1_del==true && seq2_del==true we will have unconnected states
  // thus we need to run connect to clean out these states
  if (seq1_del == false || seq2_del == false)
    Connect (fst);

  return;
}

//Build the composed alignment FST and add it to the list of training data
void M2MFstAligner::entry2alignfst (vector<string> seq1, vector<string> seq2) {
  VectorFst<LogArc> fst;
  Sequences2FST (&fst, &seq1, &seq2);
  fsas.push_back (fst);

  return;
}

void M2MFstAligner::entry2alignfstnoinit (vector<string> seq1,
                                          vector<string> seq2,
                                          int nbest, string lattice) {
  /*
    There is a pre-trained alignment model, so just use the model
    parameters to weight the alignment arcs. This could probably be
    merged with "entry2alignfst()", but we'll leave it for now.
  */
  VectorFst<LogArc> fst;
  Sequences2FSTNoInit (&fst, &seq1, &seq2);
  fsas.push_back (fst);

  return;
}

void M2MFstAligner::_compute_penalties (LogArc::Label label, int lhs,
                                        int rhs, bool lhsE, bool rhsE) {
  /*
    Precompute exponential penalties for all possible alignment units.
  */

  LabelDatum ld;
  ld.lhs  = lhs;   ld.rhs = rhs;
  ld.lhsE = lhsE; ld.rhsE = rhsE;

  ld.max  = max (lhs, rhs);
  ld.tot  = lhs + rhs;

  penalties.insert (LabelData::value_type (label, ld));

  return;
}

