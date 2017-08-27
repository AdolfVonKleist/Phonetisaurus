#!/usr/bin/env python
import phonetisaurus
from itertools import izip

def Phoneticize (model, args) :
    """Python wrapper function for g2p bindings.

    Python wrapper function for g2p bindings.  Most basic possible example.
    Intended as a template for doing something more useful.

    Args:
        model (str): The g2p fst model to load.
        args (obj): The argparse object with user specified options.
    """

    results = model.Phoneticize (
        args.token,
        args.nbest,
        args.beam,
        args.thresh,
        args.write_fsts,
        args.accumulate,
        args.pmass
    )

    for result in results :
        uniques = [model.FindOsym (u) for u in result.Uniques]
        print ("{0:0.2f}\t{1}".format (result.PathWeight, " ".join (uniques)))
        print ("-------")

        #Should always be equal length
        for ilab, olab, weight in izip (result.ILabels,
                                        result.OLabels,
                                        result.PathWeights) :
            print ("{0}:{1}:{2:0.2f}".format (
                model.FindIsym (ilab),
                model.FindOsym (olab),
                weight
            ))

    return


if __name__ == "__main__" :
    import argparse, sys

    example = "{0} --model model.fst --word \"test\"".format (sys.argv [0])
    parser  = argparse.ArgumentParser (description=example)
    parser.add_argument ("--model", "-m", help="Phonetisaurus G2P model.",
                         required=True)
    group   = parser.add_mutually_exclusive_group (required=True)
    group.add_argument ("--word", "-w", help="Input word in lower case.")
    group.add_argument ("--wlist", "-wl", help="Provide a wordlist.")
    parser.add_argument ("--nbest", "-n", help="NBest",
                         default=1, type=int)
    parser.add_argument ("--beam", "-b", help="Search beam",
                         default=500, type=int)
    parser.add_argument ("--thresh", "-t", help="NBest threshold.",
                         default=10., type=float)
    parser.add_argument ("--write_fsts", "-wf", help="Write decoded fsts "
                         "to disk", default=False, action="store_true")
    parser.add_argument ("--accumulate", "-a", help="Accumulate probs across "
                         "unique pronunciations.", default=False,
                         action="store_true")
    parser.add_argument ("--pmass", "-p", help="Target probability mass.",
                         default=0.0, type=float)
    parser.add_argument ("--verbose", "-v", help="Verbose mode.",
                         default=False, action="store_true")
    args = parser.parse_args ()

    if args.verbose :
        for key,val in args.__dict__.iteritems () :
            print ("{0}:  {1}".format (key, val))

    model = phonetisaurus.Phonetisaurus (args.model)

    if args.word :
        args.token = args.word
        Phoneticize (model, args)

    else :
        with open (args.wlist, "r") as ifp :
            for word in ifp :
                word = word.decode ("utf8").strip ()
                args.token = word
                Phoneticize (model, args)
                print "-----------------------"
                print ""
