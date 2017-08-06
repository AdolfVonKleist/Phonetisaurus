#ifndef SRC_INCLUDE_LATTICEPRUNER_H_
#define SRC_INCLUDE_LATTICEPRUNER_H_
/*
 LatticePruner.hpp

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
*/
#include <fst/fstlib.h>
#include <vector>
#include "./util.h"
using namespace std;

namespace fst {
class LatticePruner {
  /*
    Generic pruning/re-weighting class for simple WFST lattices.
    Implements several simple pruning methods including the following:
       - Arc penalization
       - N-best extraction via ShortestPath()
       - Arc-based beam pruning via Prune()
       - Forward-Backward pruning
    These may be combined into a cascade as well.
  */
 public:
  // Basics declarations
  vector<LogWeight> alpha, beta;
  LabelData         penalties;
  bool              penalize;
  int               nbest;
  bool              fb;
  TropicalWeight    beam;

  // Constructors
  LatticePruner ();
  // Used with M2MFstAligner we should have a symbol-based penalty model to use
  LatticePruner (LabelData _penalties, TropicalWeight _beam, int _nbest,
                 bool _fb, bool _penalize);
  // Otherwise just use an arbitrary lattice/WFST so no penalizing
  LatticePruner (TropicalWeight _beam, int _nbest, bool _fb);

  void prune_fst (VectorFst<StdArc>* fst);

 private:
  VectorFst<StdArc> _nbest_prune (VectorFst<StdArc>* fst);
  void _penalize_arcs (VectorFst<StdArc>* fst);
  void _forward_backward (VectorFst<StdArc>* fst);
};
}  // namespace fst
#endif  // SRC_INCLUDE_LATTICEPRUNER_H_
