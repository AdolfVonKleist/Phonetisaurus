#!/usr/bin/python
import re, os

def trainNGramLibrary( prefix, order=3, method="kneser_ney", verbose=False, m2maligner=False, test=False, bins=1, nbest=False ):

    if m2maligner:
        if verbose: print "Converting from m2m-aligner format..."
        command = "./m2mformat.py PREFIX.m2m.corpus > PREFIX.corpus"
        command = command.replace("PREFIX",prefix)
        os.system(command)
    if nbest==False or not method=="witten_bell":
        if verbose: print "Extracting symbols..."
        command = "ngramsymbols < PREFIX.corpus > PREFIXORDER.syms"
        command = command.replace("PREFIX",prefix).replace("ORDER",str(order))
        os.system(command)


        if verbose: print "Running farcompile strings..."
        command = "/usr/local/bin/farcompilestrings --symbols=PREFIXORDER.syms --keep_symbols=1 PREFIX.corpus > PREFIXORDER.far"
        command = command.replace("PREFIX",prefix).replace("ORDER",str(order))
        os.system(command)
        prefix = prefix+str(order)

    if verbose: print "Running ngramcount..."
    command = "ngramcount --order=ORDER PREFIX.far > PREFIX.cnts"
    command = command.replace("PREFIX",prefix).replace("ORDER",str(order))
    os.system(command)

    if verbose: print "Running ngrammake..."
    command = "ngrammake --v=2 --bins=BINS --method=METHOD PREFIX.cnts > PREFIX.mod"
    command = command.replace("METHOD",method).replace("PREFIX",prefix).replace("BINS",str(bins))
    os.system(command)

    if verbose: print "Running ngramprint..."
    command = "ngramprint --ARPA PREFIX.mod > PREFIX.arpa"
    command = command.replace("PREFIX",prefix)
    os.system(command)

    if verbose: print "Converting to WFST format..."
    command = "../phonetisaurus-arpa2wfst-omega --lm=PREFIX.arpa > PREFIX.fst"
    command = command.replace("PREFIX",prefix)
    os.system(command)

    if test:
        if verbose: print "Running evaluation..."
        if "g014b2b" in prefix:
            command = "./phonetisaurus-calculateER-omega --modelfile PREFIX.fst --testfile g014b2b.test.fix.bsf --prefix PREFIX --decoder_type fsa_eps"
            command = command.replace("PREFIX",prefix)
            os.system(command)
        elif "g014a2" in prefix:
            command = "./phonetisaurus-calculateER-omega --modelfile PREFIX.fst --testfile g014a2.test.tabbed.bsf --prefix PREFIX --decoder_type fsa_eps"
            command = command.replace("PREFIX",prefix)
            os.system(command)
        else:
            print "No test support for this corpus."
    return


if __name__=="__main__":
    import sys, argparse, os

    example = """%s --prefix PREFIX --method kneser_ney --order 3 "" """ % sys.argv[0]
    parser = argparse.ArgumentParser(description=example)
    parser.add_argument('--prefix',     "-p", help="The prefix for the training corpus.  Expects 'PREFIX.corpus'.", required=True )
    parser.add_argument('--order',      "-o", help="The maximum ngram order for the model. (3)", type=int, required=False, default=3 )
    parser.add_argument('--method',     "-m", help="The smoothing method. (kneser_ney) [kneser_ney, absolute, witten_bell, unsmoothed]", required=False, default="kneser_ney" )
    parser.add_argument('--m2maligner', "-a", help="m2m-aligner was used instead of phonetisaurus. (false)", required=False, default=False, action="store_true" )
    parser.add_argument('--test',       "-t", help="Run the evaluation. (false)", required=False, default=False, action="store_true" )
    parser.add_argument('--nbest',      "-n", help="Use n-best alignments (requires method=witten_bell, only supported by phonetisaurus-align).", required=False, default=False, action="store_true" )
    parser.add_argument('--verbose',    "-v", help="Verbose mode.", required=False, default=False, action="store_true" )
    parser.add_argument('--bins',       "-b", help="Number of discount bins to utilize.  Only releveant to 'absolute' and 'kneser_ney' smoothing methods. (1)", required=False, default=1, type=int )

    args = parser.parse_args()

    if args.verbose:
        for attr, value in args.__dict__.iteritems():
            print attr, "=", value
    
    trainNGramLibrary( 
        args.prefix, order=args.order, method=args.method, 
        verbose=args.verbose, m2maligner=args.m2maligner, 
        test=args.test, bins=args.bins, nbest=args.nbest 
        )
