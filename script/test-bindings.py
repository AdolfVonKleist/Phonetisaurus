#!/usr/bin/python
# Copyright (c) [2014-], Yandex, LLC
# Author: jorono@yandex-team.ru (Josef Robert Novak)
# All rights reserved.
#
#   Redistribution and use in source and binary forms, with or without
#   modification, are permitted #provided that the following conditions
#   are met:
#
#   * Redistributions of source code must retain the above copyright
#   notice, this list of conditions and the following disclaimer.
#   * Redistributions in binary form must reproduce the above
#   copyright notice, this list of #conditions and the following
#   disclaimer in the documentation and/or other materials provided
#   with the distribution.
#
#   THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
#   "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
#   LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
#   FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
#   COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT,
#   INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
#   (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
#   SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
#   HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
#   STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
#   ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED
#   OF THE POSSIBILITY OF SUCH DAMAGE.
#
# \file
# Just a script to test out the bindings - no server involved here.
from rnnlm.RnnLM import RnnLMPy
import re, time


if __name__=="__main__":
    import sys, argparse, math
    
    example = "USAGE: {0} --rnnlm test.rnnlm --test sents.txt".format(sys.argv[0])
    parser  = argparse.ArgumentParser (description = example)
    parser.add_argument ("--rnnlm",   "-r", help="The input rnnlm.", required=True)
    parser.add_argument ("--test",    "-t", help="The test sentences to evaluate.", 
                         required=True)
    parser.add_argument ("--iters",    "-i", help="Test iterations.", type=int, 
                         default=1)
    parser.add_argument ("--verbose", "-v", help="Verbose mode.", default=False, 
                         action="store_true")
    args = parser.parse_args ()

    if args.verbose :
        for k,v in args.__dict__.iteritems () :
            print k, "=", v

    rnn = RnnLMPy (args.rnnlm)

    sents = [ re.split (r"\s+", s.replace("\n"," </s>")) for s in \
                  open (args.test,"r").readlines() ]

    total = 0.0
    start = time.time ()
    for x in xrange (args.iters):
        for sent in sents :
            result = rnn.EvaluateSentence (sent)
            if args.verbose :
                print "{0:.4f}\t{1}".format (result.sent_prob, " ".join(sent))
                for i, p in enumerate(result.word_probs) :
                    print "{0:.4f}\t{1}".format (math.pow(10,p), sent[i])
                print ""
            total += result.sent_prob
    end = time.time ()

    print "Tested: {0}".format (len(sents) * args.iters)
    print "Total prob (log10): {0:.4f}".format (total)
    print "Total time (s): {0:.4f}".format (end - start)
    print "Avg request (s): {0:.4f}".format ((end-start)/(len(sents) * args.iters))
