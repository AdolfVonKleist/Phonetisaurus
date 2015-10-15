#include <fst/fstlib.h>
#include "LegacyRnnLMHash.h"
#include "RnnLMDecoder.h"
#include "LegacyRnnLMDecodable.h"
#include "LegacyRnnLMReader.h"
using namespace fst;

//typedef std::unordered_map<std::string, std::vector<int> > FMAP;
typedef std::unordered_map<int, std::vector<int> > FMAP;

template<class H>
void LoadFeatureConf (const H&h, FMAP* fmap, std::string& featurefilename) {
  std::ifstream ifp (featurefilename.c_str ());
  std::string prefix = "#";
  std::string line;

  if (ifp.is_open ()) {
    while (ifp.good ()) {
      getline (ifp, line);
      if (line.empty ())
	continue;

      std::vector<int> ids;
      int id;
      std::string word;
      if (!line.compare (0, prefix.size (), prefix))
	continue;
      
      std::stringstream ss (line);
      ss >> word;
      while (ss >> id)
	ids.push_back (id);
      cout << "Item: " << word << " " << h.GetWordId (word) << endl;
      (*fmap) [h.GetWordId (word)] = ids;
    }
    ifp.close ();
  }
}

typedef LegacyRnnLMDecodable<Token, LegacyRnnLMHash> Decodable;
DEFINE_string (rnnlm,   "", "The input RnnLM model.");
DEFINE_string (feats,   "", "Auxiliary features conf file.");

int main (int argc, char* argv []) {
  string usage = "feature-reader --rnnlm=test.rnnlm --feats=features.conf\n\n Usage: ";
  set_new_handler (FailedNewHandler);
  SetFlags (usage.c_str (), &argc, &argv, false);

  LegacyRnnLMReader<Decodable, LegacyRnnLMHash> reader (FLAGS_rnnlm);
  LegacyRnnLMHash h = reader.CopyVocabHash ();

  FMAP fmap;

  LoadFeatureConf (h, &fmap, FLAGS_feats);

  for (FMAP::iterator it = fmap.begin (); it != fmap.end (); ++it) {
    std::cout << it->first << "\t";
    const std::vector<int>& feats = (*it).second;
    for (int i = 0; i < feats.size (); i++)
      cout << feats [i] << ((i == feats.size ()) ? "" : " ");
    cout << endl;
  }
			    
  return 0;
}
