#include <fst/fstlib.h>
using namespace fst;

int main (int argc, char *argv []) {

  VectorFst<StdArc>* fst = new VectorFst<StdArc> ();
  fst->AddState ();
  fst->SetStart (0);
  fst->SetFinal (0, TropicalWeight::One ());
  fst->AddArc (0, StdArc (1, 1, TropicalWeight::One (), 0));
  fst->Write ("test.fst");

  cout << "THIS WAS A TEST" << endl;

  return 0;
}
