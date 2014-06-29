#include <fst/fstlib.h>
using namespace fst;


int main( int arc, char* argv[] ){

  VectorFst<StdArc>* lm = VectorFst<StdArc>::Read(argv[1]);
  SymbolTable* syms = (SymbolTable*)lm->InputSymbols();
  syms->WriteText(argv[2]);

  return 1;
}
