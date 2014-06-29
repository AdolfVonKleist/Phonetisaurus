#!/usr/bin/env python
# Copyright (c) Twisted Matrix Laboratories.
# Transformed into a cheesy ngram-server by JRN
# See LICENSE for details.
#
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
# A simplistic example of an ngram-server for the rnnlm bindings.
# This is based on the twisted-python echo-server example.
# It fields requests in the form of a string, and returns a JSON
# object consisting of the sentence-prob given the RNNLM, as well 
# as the probabilities of the individual tokens. There are also some
# stubs for KenLM, but we don't use these currently for the G2P.
from twisted.internet.protocol import Protocol, Factory
from twisted.internet import reactor
import struct, re, json, sys, os
sys.path.append (os.getcwd())
import kenlm, rnnlm
from phonetisaurus import Phonetisaurus

# For some reason this has no effect in OSX+Python2.7
from json import encoder
encoder.FLOAT_REPR = lambda o: format(o, '.4f')



### Protocol Implementation
def FormatARPAResult (response, sent) :
    # Have to add </s>
    words = sent.split (" ") + ['</s>']
    result = {}
    result['scores'] = [(w,s[0],s[1]) for w,s in zip (words,response)]
    result['total']  = sum ([s[1] for s in result['scores']])

    return result

def FormatRnnLMResult (response, words) :
    result = {}
    result['scores'] = [(w,s) for w,s in zip (response.words, response.word_probs)]
    result['total']  = response.sent_prob

    return result

def mapsym (sym) :
    if sym == "<eps>":
        return "_"
    return sym

def FormatG2PResult (responses, m):
    """
      Format the G2P response object.  Return
      a dictionary/list that we can easily serialize
      and return in a JSON response.
    """
    prons = []
    for response in responses :
        # Rebuild the original joint-token sequence
        joint = [ "{0}}}{1}".format (m.FindIsym(g),mapsym (m.FindOsym(p)))
                  for g, p in zip (response.ILabels, response.OLabels) 
                  if not (g == 0 and p == 0)]
        pron = {
            'score' : response.PathWeight,
            'pron'  : " ".join([m.FindOsym(p) 
                                 for p in response.Uniques]),
            'joint' : " ".join(joint)
        }
        prons.append (pron)

    return prons


# This is just about the simplest possible ngram server
class NgramServer (Protocol):
    def dataReceived(self, data):
        """
         Compute the probability of the requested sentence
         for both a standard n-gram model, and an rnnlm
        """

        request  = json.loads (data)
        response = {}
        # Process a G2P request - how did this turn out so ugly lookin!
        if 'g2p' in request :
            response['g2p'] = []
            for word in request['g2p']['words'] :
                response['g2p'].append (FormatG2PResult \
                                        (models['g2p'].Phoneticize \
                                         (word, request['g2p']['nbest'], 
                                          request['g2p']['band'],
                                          request['g2p']['prune'], False), 
                                         models['g2p']))
        # Process a request for standard ARPA LM via KenLM bindings
        elif 'arpa' in request :
            response['arpa'] = []
            for sent in request['arpa']['sents'] :
                response['arpa'].append (FormatARPAResult \
                                         (models['arpa'].full_scores (sent),
                                          sent))
        # Process a request for an RnnLM via the RnnLM bindings
        elif 'rnnlm' in request :
            response['rnnlm'] = []
            for sent in request['rnnlm']['sents'] :
                # Have to add </s>
                words = sent.split (" ") + ['</s>']
                response['rnnlm'].append (FormatRnnLMResult \
                                          (models['rnnlm'].EvaluateSentence (words),
                                           words))
        elif 'prnnlm' in request :
            response['prnnlm'] = []
            for sent in request['prnnlm']['sents'] :
                # Have to add </s>
                words = sent.split (" ") + ['</s>']
                response['prnnlm'].append (FormatRnnLMResult \
                                          (models['prnnlm'].EvaluateSentence (words),
                                           words))
        #Package everything we learned and send it back
        response_string = json.dumps (response)

        #First send the size of the full response so the client 
        # will be able to know how much to read
        self.transport.write(struct.pack("!L", len(response_string)))
        #Finally send the response
        self.transport.write(response_string)


def main (models, port=8000) :
    f = Factory()
    f.protocol = NgramServer
    f.protocol.models = models
    reactor.listenTCP(port, f)
    reactor.run()

if __name__ == '__main__':
    import sys, argparse
    
    example = "USAGE: {0} --g2p test.g2p.fst --arpa test.arpa.bin "\
              "--rnnlm test.rnnlm".format (sys.argv[0])
    parser  = argparse.ArgumentParser (description = example)
    # Each of these model 'types' should ultimately permit a list
    parser.add_argument ("--g2p",     "-g",  help="PhonetisaurusG2P model.")
    parser.add_argument ("--arpa",    "-a",  help="ARPA model in KenLM binary.")
    parser.add_argument ("--rnnlm",   "-r",  help="RnnLM to use.")
    parser.add_argument ("--prnnlm",  "-pr", help="Phoneme RnnLM to use.")
    parser.add_argument ("--port",    "-p",  help="Port to run the server on",
                         type=int, default=8000)
    parser.add_argument ("--verbose", "-v",  help="Verbose mode", default=False, 
                         action="store_true")
    args = parser.parse_args ()

    if args.verbose :
        for k,v in args.__dict__.iteritems () :
            print k, "=", v

    models = {}
    if args.g2p :
        models['g2p']   = Phonetisaurus (args.g2p)
    if args.arpa : 
        models['arpa']  = kenlm.LanguageModel (args.arpa)
    if args.rnnlm : 
        models['rnnlm'] = rnnlm.RnnLMPy (args.rnnlm)
    if args.prnnlm :
        models['prnnlm'] = rnnlm.RnnLMPy (args.prnnlm)

    main (models)
    
