// PhonetisaurusRex.h

// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//
// Copyright 2005-2010 Google, Inc.
// Author: allauzen@google.com (Cyril Allauzen)
//
// 2014-04-20
// Author: josef.robert.novak@gmail.com (Josef Novak)
// Refactored in order support a 'filter' template argument which
// has the effect of disambiguating the n-best based on some user-
// supplied/determined criteria.
//
// In the case of the G2P this allows us to (fairly) efficiently
// extract just the n-best unique pronunciations, given some
// user-defined concept of 'unique' - e.g. not including epsilons
// or deletions, and ensuring that tied subsequences map to the
// same unique sequence.
//
// The underlying n-best algorithm is fundamentally unchanged from
// the original shorted-path.h code.

//
// \file
// Functions to find shortest paths in an FST.
#ifndef SRC_INCLUDE_PHONETISAURUSREX_H_
#define SRC_INCLUDE_PHONETISAURUSREX_H_
#include <include/util.h>
#include <fst/fstlib.h>
#include <unordered_map>
#include <unordered_set>
#include <functional>
#include <string>
#include <vector>
#include <utility>
using namespace fst;

struct VectorIntHash {
  size_t operator () (const vector<int>& v) const {
    size_t result = 0;
    hash<int> hash_fn;

    for (size_t i = 0; i < v.size(); i++)
      result ^= hash_fn (v[i]) + 0x9e3779b9 + (result << 6)
        + (result >> 2);
    return result;
  }
};

inline bool operator==(const vector<int>& x, const vector<int>& y) {
  if (x.size() != y.size())
    return false;
  for (size_t i = 0; i < x.size(); i++)
    if (x[i] != y[i])
      return false;
  return true;
}

typedef unordered_map<int, vector<int> > SymbolMap12M;
typedef unordered_map<vector<int>, int, VectorIntHash> SymbolMapM21;
typedef unordered_set<int> VetoSet;

int LoadClusters (const SymbolTable* syms, SymbolMap12M* clusters,
                  SymbolMapM21* invclusters) {
  /*
    Compute the set of 'clustered' graphemes learned during
    the alignment process. This information is encoded in
    the input symbols table.
  */
  string tie = syms->Find (1);
  size_t max_len = 1;
  for (size_t i = 2; i < syms->NumSymbols(); i++) {
    string sym = syms->Find (i);
    vector<int> cluster;
    if (sym.find(tie) != string::npos) {
      char* tmpstring = const_cast<char *> (sym.c_str());
      char* p = strtok (tmpstring, tie.c_str());
      while (p) {
        cluster.push_back (syms->Find(p));
        p = strtok (NULL, tie.c_str());
      }

      clusters->insert(pair<int, vector<int> >(i, cluster));
      invclusters->insert(pair<vector<int>, int>(cluster, i));
      max_len = (cluster.size() > max_len) ? cluster.size() : max_len;
    } else {
      cluster.push_back (i);
      clusters->insert(pair<int, vector<int> >(i, cluster));
      invclusters->insert(pair<vector<int>, int>(cluster, i));
    }
  }
  return max_len;
}

template <class Arc>
void Entry2FSA (const vector<int>& word, VectorFst<Arc>* fsa, size_t maxlen,
                const SymbolMapM21& invmap, bool superfinal = false) {
  fsa->AddState ();
  fsa->SetStart (0);
  size_t j;
  for (size_t i = 0; i < word.size(); i++) {
    j = 1;
    fsa->AddArc (i, Arc (word[i], word[i], Arc::Weight::One(), i + j));
    j++;

    while (j <= maxlen && i + j <= (size_t)word.size()) {
      vector<int> subv (&word[i], &word[i+j]);
      SymbolMapM21::const_iterator invmap_iter = invmap.find (subv);
      if (invmap_iter != invmap.end())
        fsa->AddArc (i, Arc (invmap_iter->second, invmap_iter->second,
                             Arc::Weight::One(), i+j));
      j++;
    }
    fsa->AddState ();
  }

  if (superfinal) {
    fsa->AddState();
    fsa->AddArc (word.size(), Arc (0, 0, Arc::Weight::One(), word.size()+1));
    fsa->AddState();
    fsa->AddArc (word.size()+1, Arc (1, 1, Arc::Weight::One(), word.size()+2));
    fsa->SetFinal (word.size()+2, Arc::Weight::One());
  } else {
    fsa->SetFinal (word.size(), Arc::Weight::One());
  }
}

struct Path {
  Path () : PathWeight (0.0) {}
  float PathWeight;
  vector<float> PathWeights;
  vector<int> ILabels;
  // The original vector of olabels
  vector<int> OLabels;
  // The hash-key vector of olabels
  // This one is filtered so we only
  // store unique pronunciations in the final
  // n-best list.  For example, epsilon labels are
  // removed, and any tied token subsequences are
  // expanded so the path is a list of monophones.
  vector<int> unique_olabels;
};
typedef unordered_map<vector<int>, Path, VectorIntHash>::iterator piter;

template <class Arc>
class IdentityPathFilter {
 public:
  IdentityPathFilter () {}
  unordered_map<vector<int>, Path, VectorIntHash> path_map;
  vector<vector<int> > ordered_paths;

  void Extend (Path* path, const Arc& arc) {
    // Skip any completely empty arcs
    if (arc.ilabel == 0 && arc.olabel == 0
        && arc.weight == Arc::Weight::One())
      return;

    if (arc.olabel != 0 && arc.olabel != 1 && arc.olabel != 2)
      path->unique_olabels.push_back (arc.olabel);

    path->ILabels.push_back (arc.ilabel);
    path->OLabels.push_back (arc.olabel);
    path->PathWeights.push_back (arc.weight.Value());
  }
};


template <class Arc>
class M2MPathFilter {
 public:
  M2MPathFilter (const SymbolMap12M& label_map, const VetoSet& veto_set)
    : label_map_(label_map), veto_set_(veto_set) { }
  unordered_map<vector<int>, Path, VectorIntHash> path_map;
  vector<vector<int> > ordered_paths;

  void Extend (Path* path, const Arc& arc) {
    if (arc.ilabel == 0 && arc.olabel == 0
        && arc.weight == Arc::Weight::One())
      return;

    SymbolMap12M::const_iterator iter = label_map_.find (arc.olabel);
    if (iter != label_map_.end()) {
      const vector<int>& tokens = iter->second;
      for (int i = 0; i < tokens.size(); i++)
        if (veto_set_.find (tokens[i]) == veto_set_.end())
          path->unique_olabels.push_back (tokens[i]);
    }

    path->ILabels.push_back (arc.ilabel);
    path->OLabels.push_back (arc.olabel);
    path->PathWeights.push_back (arc.weight.Value());
    path->PathWeight += arc.weight.Value();
  }

 private:
  const SymbolMap12M& label_map_;
  const VetoSet&  veto_set_;
};


template<class Arc, class RevArc, class PathFilter>
void NShortestPathSpecialized (const Fst<RevArc> &ifst,
                               MutableFst<Arc> *ofst,
                   const vector<typename Arc::Weight> &distance,
                   size_t beam,
                   size_t nbest,
                   PathFilter* path_filter,
                   bool accumulate = false,
                   float delta = kDelta,
                   typename Arc::Weight weight_threshold = Arc::Weight::Zero (),
                   typename Arc::StateId state_threshold = kNoStateId) {
  typedef typename Arc::StateId StateId;
  typedef typename Arc::Weight Weight;
  typedef pair<StateId, Weight> Pair;

  if (nbest <= 0) return;
  if ((Weight::Properties () & (kPath | kSemiring)) != (kPath | kSemiring)) {
    FSTERROR() << "NShortestPath: Weight needs to have the "
               << "path property and be distributive: "
               << Weight::Type ();
    ofst->SetProperties (kError, kError);
    return;
  }
  ofst->DeleteStates ();
  ofst->SetInputSymbols (ifst.InputSymbols ());
  ofst->SetOutputSymbols (ifst.OutputSymbols ());
  // Each state in 'ofst' corresponds to a path with weight w from the
  // initial state of 'ifst' to a state s in 'ifst', that can be
  // characterized by a pair (s,w).  The vector 'pairs' maps each
  // state in 'ofst' to the corresponding pair maps states in OFST to
  // the corresponding pair (s,w).
  vector<Pair> pairs;
  // The supefinal state is denoted by -1, 'compare' knows that the
  // distance from 'superfinal' to the final state is 'Weight::One()',
  // hence 'distance[superfinal]' is not needed.
  StateId superfinal = -1;
  fst::internal::ShortestPathCompare<StateId, Weight>
    compare(pairs, distance, superfinal, delta);
  vector<StateId> heap;
  // 'r[s + 1]', 's' state in 'fst', is the number of states in 'ofst'
  // which corresponding pair contains 's' ,i.e. , it is number of
  // paths computed so far to 's'. Valid for 's == -1' (superfinal).
  vector<int> r;
  NaturalLess<Weight> less;
  if (ifst.Start () == kNoStateId ||
      distance.size () <= ifst.Start () ||
      distance [ifst.Start ()] == Weight::Zero () ||
      less (weight_threshold, Weight::One ()) ||
      state_threshold == 0) {
    if (ifst.Properties (kError, false)) ofst->SetProperties (kError, kError);
    return;
  }
  ofst->SetStart (ofst->AddState ());
  StateId final = ofst->AddState ();
  ofst->SetFinal(final, Weight::One ());
  while (pairs.size () <= final)
    pairs.push_back (Pair (kNoStateId, Weight::Zero ()));
  pairs [final] = Pair (ifst.Start(), Weight::One ());
  heap.push_back (final);
  Weight limit = Times (distance [ifst.Start ()], weight_threshold);

  // Treat 'n' like a beam. npaths contains target number of unique paths
  while (!heap.empty ()) {
    pop_heap (heap.begin (), heap.end (), compare);
    StateId state = heap.back ();
    Pair p = pairs [state];
    heap.pop_back ();
    Weight d = p.first == superfinal ? Weight::One () :
      p.first < distance.size () ? distance [p.first] : Weight::Zero ();

    if (less (limit, Times (d, p.second)) ||
        (state_threshold != kNoStateId &&
         ofst->NumStates () >= state_threshold))
      continue;

    while (r.size () <= p.first + 1) r.push_back (0);
    ++r[p.first + 1];

    // This is extended to 'filter' for unique paths based
    // on some sort of user-defined function.  Unlike the
    // existing 'unique' functionality in the original this
    // provides for an arbitrary definition of uniqueness, and
    // by avoiding determinization ensures that ngram-weights
    // will not be moved or smeared
    if (p.first == superfinal) {
      ofst->AddArc(ofst->Start (), Arc (0, 0, Weight::One (), state));
      StateId tstate = state;
      Path one_path;
      while (ofst->Final (tstate) == Weight::Zero ()) {
        for (ArcIterator<Fst<Arc> > aiter (*ofst, tstate);
             !aiter.Done (); aiter.Next ()) {
          const Arc& tarc = aiter.Value ();
          tstate = tarc.nextstate;
          path_filter->Extend (&one_path, tarc);
        }
      }

      piter pit = path_filter->path_map.find (one_path.unique_olabels);
      if (pit == path_filter->path_map.end ()) {
        path_filter->path_map.insert(
          pair<vector<int>, Path> (one_path.unique_olabels, one_path));
        path_filter->ordered_paths.push_back (one_path.unique_olabels);

        if (path_filter->ordered_paths.size () >= nbest)
          break;
      } else if (accumulate == true) {
        pit->second.PathWeight = Plus (
                 LogWeight (pit->second.PathWeight),
                 LogWeight (one_path.PathWeight)
           ).Value ();
      }
    }

    if ((p.first == superfinal) && (r [p.first + 1] == beam))
      break;

    if (r [p.first + 1] > beam) continue;
    if (p.first == superfinal) continue;
    for (ArcIterator< Fst<RevArc> > aiter (ifst, p.first);
         !aiter.Done ();
         aiter.Next ()) {
      const RevArc &rarc = aiter.Value();
      Arc arc(rarc.ilabel, rarc.olabel, rarc.weight.Reverse (), rarc.nextstate);
      Weight w = Times (p.second, arc.weight);
      StateId next = ofst->AddState ();
      pairs.push_back (Pair (arc.nextstate, w));
      arc.nextstate = state;
      ofst->AddArc (next, arc);
      heap.push_back (next);
      push_heap (heap.begin (), heap.end(), compare);
    }

    Weight finalw = ifst.Final (p.first).Reverse ();
    if (finalw != Weight::Zero ()) {
      Weight w = Times (p.second, finalw);
      StateId next = ofst->AddState ();
      pairs.push_back (Pair (superfinal, w));
      ofst->AddArc (next, Arc(0, 0, finalw, state));
      heap.push_back (next);
      push_heap (heap.begin (), heap.end (), compare);
    }
  }
  Connect (ofst);
  if (ifst.Properties (kError, false)) ofst->SetProperties (kError, kError);
  ofst->SetProperties (
    ShortestPathProperties (ofst->Properties (kFstProperties, false)),
    kFstProperties);
}


template<class Arc, class Queue, class ArcFilter, class PathFilter>
void ShortestPathSpecialized(const Fst<Arc> &ifst, MutableFst<Arc> *ofst,
                  vector<typename Arc::Weight> *distance,
                  PathFilter* path_filter,
                  size_t beam,
                  const ShortestPathOptions<Arc, Queue, ArcFilter> &opts,
                  bool accumulate = false) {
  typedef typename Arc::StateId StateId;
  typedef typename Arc::Weight Weight;
  typedef ReverseArc<Arc> ReverseArc;

  size_t nbest = opts.nshortest;
  if (nbest <= 0) return;
  if ((Weight::Properties () & (kPath | kSemiring)) != (kPath | kSemiring)) {
    FSTERROR() << "ShortestPath: n-shortest: Weight needs to have the "
               << "path property and be distributive: "
               << Weight::Type ();
    ofst->SetProperties (kError, kError);
    return;
  }
  if (!opts.has_distance) {
    ShortestDistance (ifst, distance, opts);
    if (distance->size () == 1 && !(*distance) [0].Member ()) {
      ofst->SetProperties (kError, kError);
      return;
    }
  }
  // Algorithm works on the reverse of 'fst' : 'rfst', 'distance' is
  // the distance to the final state in 'rfst', 'ofst' is built as the
  // reverse of the tree of n-shortest path in 'rfst'.
  VectorFst<ReverseArc> rfst;
  Reverse(ifst, &rfst);
  Weight d = Weight::Zero();
  for (ArcIterator< VectorFst<ReverseArc> > aiter(rfst, 0);
       !aiter.Done (); aiter.Next ()) {
    const ReverseArc &arc = aiter.Value ();
    StateId s = arc.nextstate - 1;
    if (s < distance->size())
      d = Plus (d, Times (arc.weight.Reverse(), (*distance)[s]));
  }
  distance->insert (distance->begin(), d);

  // Specialize the 'uniqueness' property for our needs
  NShortestPathSpecialized (
              rfst, ofst, *distance, beam, nbest,
              path_filter, accumulate, opts.delta,
              opts.weight_threshold, opts.state_threshold
            );

  distance->erase (distance->begin());
}
#endif  // SRC_INCLUDE_PHONETISAURUSREX_H_
