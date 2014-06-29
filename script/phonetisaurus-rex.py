#!/usr/bin/python
import sys, os, itertools
sys.path.append (os.getcwd())
from phonetisaurus import Phonetisaurus


def LoadTestSet (testfile) :
    words = []
    for entry in open (testfile, "r") :
        words.append(entry.strip())
    return words

def PhoneticizeWord (model, word, nbest, band, prune, write, max_order=0) :
    prons = model.Phoneticize (word, nbest, band, prune, write)
    for pron in prons :
        phones = " ".join([ model.FindOsym (p) for p in pron.Uniques ])
        print "{0}\t{1:.4f}\t{2}".format (word, pron.PathWeight, phones)
        bow   = 0.0
        order = 2
        for w, g, p in itertools.izip (pron.PathWeights, pron.ILabels, pron.OLabels):
            if g == 0 and p == 0:
                bow += w
                order -= 1
            else:
                print "{0}:{1}\t{2:.4f}\t{3}".\
                    format (model.FindIsym (g), model.FindOsym (p), w+bow, order)
                if order < max_order:
                    order += 1
                bow = 0.0
        print "</s>\t{0:.4f}\t{1}".\
            format (bow, order+1 if order < max_order else order)
        print ""
    return 

def PhoneticizeTestSet (model, words, nbest, band, prune, write, max_order=0) :

    for word in words :
        PhoneticizeWord (model, word, nbest, band, prune, max_order)

    return

if __name__ == "__main__" :
    import sys, argparse

    example = "USAGE: {0} --model g2p.fst --testset test.txt".format (sys.argv[0])
    parser  = argparse.ArgumentParser (description = example)

    group   = parser.add_mutually_exclusive_group (required=True)
    group.add_argument ("--testset", "-t", help="Input test set to evaluate.")
    group.add_argument ("--word", "-w", help="Input word to evaluate.")

    parser.add_argument ("--model",   "-m", help="Input G2P model.", required=True)
    parser.add_argument ("--nbest",   "-n", help="N-best results.", default=1, type=int)
    parser.add_argument ("--band",    "-b", help="Band for n-best search", default=10000, type=int)
    parser.add_argument ("--prune",   "-p", help="Pruning threshold for n-best.", default=99, type=float)
    parser.add_argument ("--write",   "-r", help="Write out the FSTs.", default=False, action="store_true")
    parser.add_argument ("--max_order", "-o", help="Maximum ngram order for input model.  "
                         "Used only for formatting purposes.", default=0, type=int)
    parser.add_argument ("--verbose", "-v", help="Verbose mode", default=False, action="store_true")
    args = parser.parse_args ()
    
    if args.verbose :
        for k,v in args.__dict__.iteritems ():
            print k, "=", v

    #Load the G2P model
    g2p    = Phonetisaurus (args.model)

    words  = []
    if args.testset :
        words  = LoadTestSet (args.testset)
        PhoneticizeTestSet (g2p, words, args.nbest, args.band, 
                            args.prune, args.write, max_order=args.max_order)
    else :
        PhoneticizeWord (g2p, args.word, args.nbest, args.band, 
                         args.prune, args.write, max_order=args.max_order)
