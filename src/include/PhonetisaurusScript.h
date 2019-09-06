/*
 PhonetisaurusPy.h

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
// \file
// This implements the scripting interface for the FST-based
// decoder.  The associated classes are suitable for
// construction of command-line utilities and bindings for
// scripting languages such as Python.
//
#ifndef SRC_INCLUDE_PHONETISAURUSSCRIPT_H_
#define SRC_INCLUDE_PHONETISAURUSSCRIPT_H_
#include "PhonetisaurusRex.h"
#include <sys/types.h>
#include <sys/stat.h>
#include <string>
#include <vector>
/*! \struct PathData
    \brief Response data.

    The PathData structure is used to encapsulate
    a single FST G2P result.
*/
struct PathData {
  PathData () {}
  PathData (float PathWeight_, const std::vector<float>& PathWeights_,
       const std::vector<int>& ILabels_, const std::vector<int>& OLabels_,
       const std::vector<int>& Uniques_)
    : PathWeight (PathWeight_), PathWeights (PathWeights_),
      ILabels (ILabels_), OLabels (OLabels_), Uniques(Uniques_) {}

  float PathWeight;
  std::vector<float> PathWeights;
  std::vector<int>   ILabels;
  std::vector<int>   OLabels;
  // Contains only 'interesting' phone labels
  std::vector<int>   Uniques;
};

/*! \class PhonetisaurusScript
    \brief A wrapper class encapsulating the FST G2P decoder.

    A wrapper class for the FST G2P decoder.  Suitable for
    incorporation into commandline binaries and bindings
    for various scripting languages.
*/
class PhonetisaurusScript {
 public:
  explicit PhonetisaurusScript (std::string model) : delim_("") {
    struct stat buffer;
    if (!(stat (model.c_str(), &buffer) == 0))
      throw std::exception();

    // this is solving the memory leak problem
    VectorFst<StdArc>* model_temp;
    model_temp = (VectorFst<StdArc>::Read(model));
    model_ = *model_temp;
    delete model_temp;

    // model_ = *(VectorFst<StdArc>::Read(model));
    ArcSort (&model_, ILabelCompare<StdArc> ());
    isyms_ = model_.InputSymbols ();
    osyms_ = model_.OutputSymbols ();
    imax_  = LoadClusters (isyms_, &imap_, &invimap_);
    omax_  = LoadClusters (osyms_, &omap_, &invomap_);
    veto_set_.insert (0);
    veto_set_.insert (1);
    veto_set_.insert (2);
  }

  PhonetisaurusScript (std::string model, std::string delim) : delim_(delim) {
    struct stat buffer;
    if (!(stat (model.c_str(), &buffer) == 0))
      throw std::exception();

    // this is solving the memory leak problem
    VectorFst<StdArc>* model_temp;
    model_temp = (VectorFst<StdArc>::Read(model));
    model_ = *model_temp;
    delete model_temp;
    // model_ = *(VectorFst<StdArc>::Read(model));
    ArcSort (&model_, ILabelCompare<StdArc> ());
    isyms_ = model_.InputSymbols ();
    osyms_ = model_.OutputSymbols ();
    imax_  = LoadClusters (isyms_, &imap_, &invimap_);
    omax_  = LoadClusters (osyms_, &omap_, &invomap_);
    veto_set_.insert (0);
    veto_set_.insert (1);
    veto_set_.insert (2);
  }

  // The actual phoneticizer routine
  std::vector<PathData> Phoneticize (const std::string& word, int nbest = 1,
                      int beam = 10000, float threshold = 99,
                      bool write_fsts = false,
                      bool accumulate = false,
                      double pmass = 99.0) {
    VectorFst<StdArc>* fst = new VectorFst<StdArc> ();
    std::vector<int> entry = tokenize2ints (
                          const_cast<std::string*> (&word),
                          &delim_, isyms_
                        );
    Entry2FSA (entry, fst, imax_, invimap_);

    fst->SetInputSymbols (isyms_);
    fst->SetOutputSymbols (isyms_);

    // Useful for debugging; print the input word machine
    if (write_fsts)
      fst->Write (word + ".fst");

    VectorFst<StdArc> ofst;

    StdArc::Weight weight_threshold = threshold;
    StdArc::StateId state_threshold = kNoStateId;
    AnyArcFilter<StdArc> arc_filter;
    std::vector<StdArc::Weight> distance;

    VectorFst<StdArc>* ifst = new VectorFst<StdArc>();
    Compose(*fst, model_, ifst);

    // Useful for debugging; print the g2p lattice
    if (write_fsts)
      ifst->Write (word+".lat.fst");

    AutoQueue<StdArc::StateId> state_queue (*ifst, &distance, arc_filter);

    M2MPathFilter<StdArc> path_filter (omap_, veto_set_);

    ShortestPathOptions<StdArc, AutoQueue<StdArc::StateId>,
                      AnyArcFilter<StdArc> >
      opts (&state_queue, arc_filter, nbest, false, false,
            kDelta, false, weight_threshold,
            state_threshold);

    ShortestPathSpecialized (*ifst, &ofst, &distance,
                             &path_filter, beam, opts, accumulate);

    std::vector<PathData> paths;
    float total = 99.0;
    if (pmass < 99.0) {
      for (size_t i = 0; i < path_filter.ordered_paths.size(); i++) {
        const std::vector<int>& u = path_filter.ordered_paths [i];
        const Path& orig = path_filter.path_map [u];
        total = Plus (LogWeight (total), LogWeight (orig.PathWeight)).Value ();
      }
    }

    LogWeight nbest_pmass = 99.0;
    for (size_t i = 0; i < path_filter.ordered_paths.size(); i++) {
      const std::vector<int>& u = path_filter.ordered_paths [i];
      const Path& orig = path_filter.path_map [u];
      float pweight = orig.PathWeight;
      if (pmass < 99.0) {
        pweight = pweight - total;
        nbest_pmass = Plus (
                        LogWeight (nbest_pmass),
                        LogWeight (pweight)
                      ).Value ();
      }

      PathData path = PathData (
                  pweight, orig.PathWeights,
                  orig.ILabels, orig.OLabels, orig.unique_olabels
                );
      paths.push_back (path);

      // We are greedy with this, in order to ensure that if pmass =~ -log (.8),
      // and we have h1 = -log (.5), and h2 = -log (.4) that we get both.
      if (pmass < 99.0 && nbest_pmass.Value () < pmass)
        break;
    }

    // Make sure that we clean up
    delete fst;
    delete ifst;
    return paths;
  }

  // Helper functions for the bindings
  std::string FindIsym (int symbol_id) {
    return isyms_->Find (symbol_id);
  }

  int FindIsym (const std::string& symbol) {
    return isyms_->Find (symbol);
  }

  std::string FindOsym (int symbol_id) {
    return osyms_->Find (symbol_id);
  }

  int FindOsym (const std::string& symbol) {
    return osyms_->Find (symbol);
  }

  const SymbolTable* isyms_;
  const SymbolTable* osyms_;

 private:
  VectorFst<StdArc> model_;
  SymbolMap12M imap_, omap_;
  SymbolMapM21 invimap_, invomap_;
  int imax_;
  int omax_;
  VetoSet veto_set_;
  std::string delim_;
};
#endif  // SRC_INCLUDE_PHONETISAURUSSCRIPT_H_
