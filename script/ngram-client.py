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
# Toy client to connect to the server and run through a test set.
import socket, sys, struct
import json, math
from json import encoder
encoder.FLOAT_REPR = lambda o: format(o, '.4f')


class NGramClient ( ) :
    """
     Client to connect to and generate requests
     for the NGramServer.  This is some real bare-bones
     stuff right here.
    """
    def __init__ (self, host='localhost', socket=8000) :
        self.host   = host
        self.socket = socket
        self.conn  = self._setup ( )

    def _setup (self) :
        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        conn.connect((self.host, self.socket))
        return conn

    def _teardown (self) :
        self.conn.close()

    def G2PRequest (self, words, nbest=1, band=500, prune=10.) :
        """
         An example request builder for the G2P server.
        """
        request_dict = {
            'g2p' : 
            {
                'words' : words, 
                'nbest' : nbest,
                'band'  : band,
                'prune' : prune
            }
        }
                 
        request  = json.dumps (request_dict)
        result   = self.conn.send (request)
        data     = self.conn.recv (4)
        size     = struct.unpack ("!L", data)[0]
        data     = self.conn.recv (size)
        response = json.loads (data)

        return response

    def ARPARequest (self, sents) :
        """
         An example request builder for the ARPA server.
         Basically the same as the RnnLM one.
        """
        request_dict = {
            'arpa' : 
            {
                'sents' : sents
            }
        }
                 
        request  = json.dumps (request_dict)
        result   = self.conn.send (request)
        data     = self.conn.recv (4)
        size     = struct.unpack ("!L", data)[0]
        data     = self.conn.recv (size)
        response = json.loads (data)

        return response

    def RnnLMRequest (self, sents) :
        """
         An example request builder for the RnnLM server.
         Basically the same as the ARPA one.
        """
        request_dict = {
            'rnnlm' : 
            {
                'sents' : sents
            }
        }
                 
        request  = json.dumps (request_dict)
        result   = self.conn.send (request)
        data     = self.conn.recv (4)
        size     = struct.unpack ("!L", data)[0]
        data     = self.conn.recv (size)
        response = json.loads (data)

        return response

    def PhoneRnnLMRequest (self, sents) :
        """
         An example request builder for the PhoneRnnLM server.
         Exactly the same as the RnnLM server.  The input sequences
         should just be phoneme strings though.
         Basically the same as the ARPA one.
        """
        request_dict = {
            'prnnlm' : 
            {
                'sents' : sents
            }
        }
                 
        request  = json.dumps (request_dict)
        result   = self.conn.send (request)
        data     = self.conn.recv (4)
        size     = struct.unpack ("!L", data)[0]
        data     = self.conn.recv (size)
        response = json.loads (data)

        return response


def print_nbest (scores, index=1) :
    print scores['word'], index
    scores['nbest'].sort (key=lambda x: x[index], reverse=True)
    for pron in scores['nbest'] :
        print "{0:.4f}\t{1}".format (pron[index], pron[0])
    print "#################"
    print ""


if __name__ == "__main__" :
    import sys, argparse, math

    example = "USAGE: {0} --word TESTING --nbest 5 --lambdas '.7,.25,.05'".format(sys.argv[0])
    parser  = argparse.ArgumentParser (description = example)
    parser.add_argument ("--word",    "-w", help="Input word for evaluation.", required=True)
    parser.add_argument ("-models",   "-m", help="Models to try the server with.", default="g2p,arpa,rnnlm")
    parser.add_argument ("--nbest",   "-n", help="N-best for G2P", default=5, type=int)
    parser.add_argument ("--prune",   "-p", help="Pruning threshold for G2P", default=10., type=float)
    parser.add_argument ("--band",    "-b", help="Band threshold for G2P", default=500, type=int)
    parser.add_argument ("--lambdas", "-l", help="Interpolation weights for rescoring.", 
                         default=".25,.25,.25,.25")
    parser.add_argument ("--verbose", "-v", help="Verbose mode.", default=False, action="store_true")
    args = parser.parse_args ()

    if args.verbose :
        for k,v in args.__dict__.iteritems ():
            print k, "=", v

    lambdas = [ float(l) for l in args.lambdas.split(",") ]

    client  = NGramClient ()

    print "Raw G2P:"
    response  = client.G2PRequest ([args.word], args.nbest, args.band, args.prune)
    print json.dumps(response, 
                     separators=(',', ':'), 
                     sort_keys=True,
                     indent=2)
    rescores  = []

    def DoOneARPA (joint) :
        print joint
        arpar = client.ARPARequest ([joint])
        print -arpar['arpa'][0]['total'] * math.log(10)
        for chunk in  arpar['arpa'][0]['scores']:
            print "{0}\t{1:.4f}\t{2}".format (chunk[0], -chunk[1]*math.log(10), chunk[2])        

    def DoOneRnnLM (joint) :
        print joint
        arpar = client.RnnLMRequest ([joint])
        print -arpar['rnnlm'][0]['total'] * math.log(10)
        for chunk in  arpar['rnnlm'][0]['scores']:
            print "{0}\t{1:.4f}".format (chunk[0], -chunk[1]*math.log(10))        

    #DoOneARPA (response['g2p'][0][0]['joint'])
    print "\nPhoneme-only ARPA:"
    DoOneARPA  (response['g2p'][0][0]['pron'])

    print "\nG2P RnnLM:"
    DoOneRnnLM (response['g2p'][0][0]['joint'])

