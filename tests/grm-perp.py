#!/usr/bin/python
import sys, os

def print_symbol_table( prefix="test" ):
    command = "./get-syms PREFIX.fst PREFIX.isyms"
    command = command.replace("PREFIX", prefix)
    print command
    os.system(command)
    return

def convert_lm( lm, prefix="test" ):
    command = "ngramread --ARPA ARPALM > PREFIX.fst"
    command = command.replace("ARPALM",lm).replace("PREFIX",prefix)
    print command
    os.system(command)

    print_symbol_table( prefix=prefix )

    return

def compute_perplexity( lm, test, prefix="test", arpa=False ):
    if arpa==True:
        convert_lm( lm, prefix=prefix )

    command = "farcompilestrings --generate_keys=1 --symbols=PREFIX.isyms TEST PREFIX.far"
    command = command.replace("PREFIX", prefix).replace("TEST", test)
    os.system(command)
    
    command = "ngramperplexity --v=2 PREFIX.fst PREFIX.far"
    command = command.replace("PREFIX", prefix)
    os.system(command)
    return

if __name__=="__main__":
    import sys, argparse, os, subprocess

    if subprocess.call(["type", "ngramperplexity"], 
        stdout=subprocess.PIPE, stderr=subprocess.PIPE) != 0:
        print "GRM utilities not found!  Please install OpenGRM:"
        print "   http://www.openfst.org/twiki/bin/view/GRM/NGramLibrary"
        sys.exit(0)

    example = """%s --prefix PREFIX --arpa""" % sys.argv[0]
    parser = argparse.ArgumentParser(description=example)
    parser.add_argument('--lm',         "-l", help="The input LM in ARPA or WFSA format.", required=True )
    parser.add_argument('--test',       "-t", help="The input list of sentences to evaluate.", required=True )
    parser.add_argument('--prefix',     "-p", help="The prefix for the output files.", required=False, default="test" )
    parser.add_argument('--arpa',       "-a", help="Input is in ARPA format, conver to WFSA.", default=False, action="store_true" )
    parser.add_argument('--verbose',    "-v", help="Verbose mode.", default=False, action="store_true" )

    args = parser.parse_args()

    if args.verbose:
        for attr, value in args.__dict__.iteritems():
            print attr, "=", value

            
    compute_perplexity( args.lm, args.test, prefix=args.prefix, 
                        arpa=args.arpa )
