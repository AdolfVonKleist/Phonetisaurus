#!/usr/bin/env python
import phonetisaurus

def Phoneticize (model, args) :
    """
    Python wrapper function for g2p.
    """

    results = model.Phoneticize (
        args.token, 
        args.nbest, 
        args.beam, 
        args.thresh, 
        args.write_fsts
    )

    for result in results :
        uniques = [model.FindOsym (u) for u in result.Uniques]
        print ("{0:0.2f}\t{1}".format (result.PathWeight, " ".join (uniques)))
        print ("-------")
        ilabs   = [model.FindIsym (i) for i in result.ILabels]
        olabs   = [model.FindOsym (o) for o in result.OLabels]
        weights = [w for w in result.PathWeights]

        assert len (ilabs) == len (olabs)
        assert len (weights) == len (olabs)

        for index, ilab in enumerate (ilabs) :
            print ("{0}:{1}:{2}".format (
                ilab, 
                olabs [index],
                weights [index]
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
    parser.add_argument ("--write_fsts", "-wf", help="Write decoded fsts to disk",
                         default=False, action="store_true")
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

                
