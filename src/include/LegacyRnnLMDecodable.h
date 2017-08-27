#ifndef SRC_INCLUDE_LEGACYRNNLMDECODABLE_H_
#define SRC_INCLUDE_LEGACYRNNLMDECODABLE_H_
#include <vector>
using std::vector;

// Fast exponent implementation from RnnLM
/*
static union {
  double d;
  struct{
    int j,i;
  } n;
} d2i;
#define EXP_A (1048576/M_LN2)
#define EXP_C 60801
#define FAST_EXP(y)(d2i.n.i=EXP_A*(y)+(1072693248-EXP_C),d2i.d)
*/

#ifdef __cplusplus
#define cast_uint32_t static_cast<uint32_t>
#else
#define cast_uint32_t (uint32_t)
#endif
static inline float fastpow2 (float p) {
  float offset = (p < 0) ? 1.0f : 0.0f;
  float clipp = (p < -126) ? -126.0f : p;
  int w = clipp;
  float z = clipp - w + offset;
  union {uint32_t i; float f;} v = {
    cast_uint32_t (
        (1 << 23) * (clipp + 121.2740575f + 27.7280233f /
                     (4.84252568f - z) - 1.49012907f * z)
    )
  };

  return v.f;
}

static inline float FAST_EXP (float p) {
  return fastpow2 (1.442695040f * p);
}


template<class T, class H>
class LegacyRnnLMDecodable {
 public:
  LegacyRnnLMDecodable (H& hash, int i, int h, int o, int d, int m)
    : h (hash), isize (i), hsize (h), osize (o), order (d), max_order (m) { }

  double ComputeNet (const T& p, T* t) {
    vector<double> olayer;
    olayer.resize (osize, 0.0);

    for (int j = 0; j < hsize; j++)
      for (int i = 0; i < hsize; i++)
        t->hlayer [j] += p.hlayer [i] * syn0 [i + h.vocab_.size () + j * isize];

    for (int i = 0; i < hsize; i++)
      if (p.word != -1)
        t->hlayer [i] += syn0 [p.word + i * (hsize + h.vocab_.size ())];

    for (int i = 0; i < hsize; i++) {
      if (t->hlayer [i] > 50)
        t->hlayer [i] = 50;
      if (t->hlayer [i] < -50)
        t->hlayer [i] = -50;
      t->hlayer [i] = 1 / (1 + FAST_EXP (-t->hlayer [i]));
    }

    for (int j = h.vocab_.size (); j < osize; j++)
      for (int i = 0; i < hsize; i++)
        olayer [j] += t->hlayer [i] * syn1 [i + j * hsize];

    // Begin class direct connection activations
    if (synd.size () > 0) {
      // Feature hash begin
      vector<uint64> hash;
      hash.resize (max_order, 0);

      for (int i = 0; i < order; i++) {
        if (i > 0)
          if (t->history [i - 1] == -1)
            break;
        hash [i] = h.primes_[0] * h.primes_[1];
        for (int j = 1; j <= i; j++)
          hash [i] +=
            h.primes_[(i * h.primes_[j] + j) % h.primes_.size ()]
            * static_cast<uint64>(t->history [j - 1] + 1);

        hash [i] = hash [i] % (synd.size () / 2);
      }
      // Feature hash end
      for (int i = h.vocab_.size (); i < osize; i++) {
        for (int j = 0; j < order; j++) {
          if (hash [j]) {
            olayer [i] += synd [hash [j]];
            hash [j]++;
          } else {
            break;
          }
        }
      }
    }
    // End class direct connection activations

    double sum = 0;
    // Softmax on classes
    for (int i = h.vocab_.size (); i < osize; i++) {
      if (olayer [i] > 50)
        olayer [i] = 50;
      if (olayer [i] < -50)
        olayer [i] = -50;
      double val = FAST_EXP (olayer [i]);
      sum += val;
      olayer [i] = val;
    }
    for (int i = h.vocab_.size (); i < osize; i++)
      olayer [i] /= sum;

    // 1->2 word activations
    if (t->word != -1) {
      int begin = h.class_sizes_[h.vocab_[t->word].class_index].begin;
      int end   = h.class_sizes_[h.vocab_[t->word].class_index].end;
      for (int j = begin; j <= end; j++)
        for (int i = 0; i < hsize; i++)
          olayer [j] += t->hlayer [i] * syn1 [i + j * hsize];

      // Begin word direct connection activations
      if (synd.size () > 0) {
        // Begin feature hashing
        uint64 hash [max_order];
        for (int i = 0; i < order; i++)
          hash [i] = 0;

        for (int i = 0; i < order; i++) {
          if (i > 0)
            if (t->history [i - 1] == -1)
              break;

          hash [i] = h.primes_[0] * h.primes_[1]
            * static_cast<uint64> (h.vocab_[t->word].class_index + 1);

          for (int j = 1; j <= i; j++)
            hash [i] += h.primes_[(i * h.primes_[j] + j) % h.primes_.size ()]
              * static_cast<uint64> (t->history [j - 1] + 1);

          hash [i] = (hash [i] % (synd.size () / 2)) + (synd.size () / 2);
        }
        // End feature hashing

        for (int i = begin; i <= end; i++) {
          for (int j = 0; j < order; j++) {
            if (hash [j]) {
              olayer [i] += synd [hash [j]];
              hash [j]++;
              hash [j] = hash [j] % synd.size ();
            } else {
              break;
            }
          }
        }
      }
      // End word direct connection activations

      sum = 0.0;
      for (int i = begin; i <= end; i++) {
        if (olayer [i] > 50)
          olayer [i] = 50;
        if (olayer [i] < -50)
          olayer [i] = -50;
        olayer [i] = FAST_EXP (olayer [i]);
        sum += olayer [i];
      }
      for (int i = begin; i <= end; i++)
        olayer [i] /= sum;
    }

    return olayer [t->word]
      * olayer [h.vocab_.size () + h.vocab_[t->word].class_index];
  }

  // We need the synapses and the vocabulary hash
  H& h;
  int isize;
  int hsize;
  int osize;
  int order;
  int max_order;
  vector<double> syn0;
  vector<double> syn1;
  vector<double> synd;
};
#endif  // SRC_INCLUDE_LEGACYRNNLMDECODABLE_H_
