#!/usr/bin/env python
import os, re, phonetisaurus, json
from bottle import route, run, template, request, response
from itertools import izip
from collections import namedtuple, defaultdict

#Globals, oh no!
_g2pmodel = None
_lexicon  = defaultdict (list)


###############################
# Utilities
def _phoneticize (model, args) :
    """
    Python wrapper function for g2p.
    """

    results = model.Phoneticize (
        args.token.encode ("utf8"),
        args.nbest,
        args.beam,
        args.thresh,
        args.write_fsts,
        args.accumulate,
        args.pmass
    )

    pronunciations = []
    for result in results :
        pronunciation = [model.FindOsym (u) for u in result.Uniques]
        yield u"{0}".format (u" ".join (pronunciation))

def _loadLexicon (lexiconfile) :
    with open (lexiconfile, "r") as ifp :
        for entry in ifp :
            word, pron = re.split (ur"\t", entry.decode ("utf8").strip ())
            _lexicon [word].append (pron)
    return

def _defaultArgs (userargs) :
    args = namedtuple ('args', [
        'token', 'nbest', 'beam', 'thresh', 'write_fsts',
        'accumulate', 'pmass'
    ])

    args.token  = ""
    args.nbest  = int (userargs.get ("nbest", 2))
    args.beam   = int (userargs.get ("beam", 500))
    args.thresh = float (userargs.get ("thresh", 10.))
    args.pmass = float (userargs.get ("pmass", 0.0))
    args.write_fsts = False
    args.accumulate = userargs.get (
        "accumulate",
        False
    )
    return args
###############################



@route ('/phoneticize/list', method="POST")
def PhoneticizeList () :
    """Phoneticize a list of words.

    Phoneticize a list of words.  This will do a simple lookup for
    the word in the reference lexicon, and backoff to the G2P server
    in the event that it finds no entry.
    """
    default_args = _defaultArgs (request.forms)

    wlist  = request.files.get ("wordlist")

    words = re.split (ur"\n", wlist.file.read ().decode ("utf8"))

    lexicon = []
    for word in words :
        if re.match (ur"^\s*$", word) or u"<" in word or u"[" in word :
            continue
                     
        default_args.token = word.lower ()
        if default_args.token in _lexicon :
            for pronunciation in _lexicon [default_args.token] :
                lexicon.append (u"{0}\t{1}".format (word, pronunciation))
        else :
            for pronunciation in _phoneticize (_g2pmodel, default_args) :
                lexicon.append (u"{0}\t{1}".format (word, pronunciation))

    response.set_header('Access-Control-Allow-Origin', '*')

    return u"\n".join (lexicon).encode ("utf8")



if __name__ == '__main__':
    import sys, argparse

    example = "{0} --host localhost --port 8080"\
              "--model g2p.fst --lexicon ref.lexicon"
    example = example.format (sys.argv [0])
    parser  = argparse.ArgumentParser (description=example)
    parser.add_argument ("--host", "-hs", help="IP to host the service on.",
                         default="localhost")
    parser.add_argument ("--port", "-p", help="Port to use for hosting.",
                         default=8080, type=int)
    parser.add_argument ("--model", "-m", help="Phonetisaurus G2P model.",
                         required=True)
    parser.add_argument ("--lexicon", "-l", help="Reference lexicon.",
                         required=True)
    parser.add_argument ("--verbose", "-v", help="Verbose mode.",
                         default=False, action="store_true")
    args = parser.parse_args ()
    
    if args.verbose :
        for key,val in args.__dict__.iteritems () :
            print >> sys.stderr, "{0}:\t{1}".format (key, val)
            
    _g2pmodel = phonetisaurus.Phonetisaurus (args.model)
    _loadLexicon (args.lexicon)

    run (host=args.host, port=args.port, debug=False)
