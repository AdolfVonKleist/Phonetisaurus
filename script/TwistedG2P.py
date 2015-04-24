#!/usr/bin/env python
# Copyright (c) Twisted Matrix Laboratories.
# Transformed into a cheesy ngram-server by JRN
# See LICENSE for details.
#
# Copyright (c) [2014], Yandex, LLC
# Author: jorono@yandex-team.ru (Josef Robert Novak)
#
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
# An n-gram server for the Phonetisaurus G2P system.
from twisted.internet.protocol import Protocol, Factory
from twisted.internet import reactor

import struct, re, json, sys, os
sys.path.append (os.getcwd())
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

formatters = {"g2pfst": FormatG2PResult}

# This is just about the simplest possible ngram server
class NgramServer (Protocol):
    
    def __init__ (self, models) :
        self.models = models
        self.req_size = None
        self.__data   = ""
        
    def dataReceived (self, data):
        """
        Manage the incoming data from the current request.
        
        Manage the data from the current requenst.  Check 
        that the full expected request has been received. If
        not, keep appending to the buffer.  If we have everything
        then forward the request to the g2p server.
        TODO: There is probably a more 'twisted' way to do this.

        Args:
            data (str): The raw data in string format.

        Returns:
            Nothing: Calls requestReceived () 
        """
        if self.req_size == None :
            self.req_size = struct.unpack ("!L", data [0:4]) [0]
            if len (self.__data) + len (data) < self.req_size :
                self.__data += data [4:]
            else :
                self.__data += data [4:]
                self.requestReceived (self.__data)
                self.__data = ""
                self.req_size = None
        else :
            if len (self.__data) + len (data) < self.req_size :
                self.__data += data
            else :
                self.__data += data
                self.requestReceived (self.__data)
                self.__data = ""
                self.req_size = None

    def requestReceived (self, data) :
        """
         Compute the probability of the requested sentence
         using the requested G2P model.
        """
        request  = json.loads (data)
        response = {"Errors": []}
        # Check that the user requested a model
        if not "model" in request :
            response ["Errors"].append ("Required parameter: 'model' missing.")
        elif not "params" in request :
            response ["Errors"].append ("Required parameter: 'params' missing.")
        elif not request ["model"] in self.models :
            available_models = ", ".join (self.models.keys ())
            error_message = "Model: {0} not found.  Available models: {1}.".\
                            format (request ["model"], available_models)
            response ["Errors"].append (error_message)
        else :
            for param in ["words", "nbest", "band", "prune"] :
                if not param in request ["params"] :
                    response ["Errors"].append ("Param: {0} not found.".\
                                                format (param))
        #If there were any errors here, respond with them
        if len (response ["Errors"]) > 0 :
            response_string = json.dumps (response)
            self.transport.write (struct.pack ("!L", len (response_string)))
            self.transport.write (response_string)
            return
        
        mname  = request ["model"]
        params = request ["params"]
        response [mname] = []
        for word in params['words'] :
            try :
                result = self.models [mname]["model"].Phoneticize (
                    word.encode ("utf8"),
                    params["nbest"],
                    params["band"],
                    params["prune"],
                    False)
                mtype  = self.models [mname]["type"]
                result = formatters [mtype] (result, self.models [mname]["model"])
                response [mname].append (result)
            except :
                response ["Errors"].append ("G2P failed for model: {0},"\
                                            "word: {1}".format (mname, word))

        #Package everything we learned and send it back
        response_string = json.dumps (response)
        #First send the size of the full response so the client 
        # will be able to know how much to read
        self.transport.write(struct.pack("!L", len(response_string)))
        #Finally send the response
        self.transport.write(response_string)


def ParseG2PConf (args, loader) :
    """
    Load the configuration file and parse arguments.

    Load the configuration file and parse any explicit arguments.
    Explicit arguments override any configuration file defaults.
    Check that files exist, and no reserved names are overridden.

    Args:
        args (ArgumentParser): An instance of the argparse parser.

    Returns:
        dict: A validated configuration dictionary for the server.
    """
    _conf = {}

    if args.conf :
        #Try to load the JSON configuration file
        if os.path.isfile (args.conf) :
            _conf = json.loads (open (args.conf, "r").read ())
        else :
            raise TypeError ("Failed to read config file: {0}".\
                             format (args.conf))

        #Validate the loaded configuration file
        for section in _conf :
            if section == "main" :
                if ("path" in _conf [section]) or ("type" in _conf [section]) :
                    raise ValueError ("Found model in reserved 'main' section")
            else :
                if (not "path" in _conf [section]) or \
                   (not os.path.isfile (_conf [section]["path"])) :
                    raise ValueError ("Model section {0}: missing or invalid "\
                                      "'path' param".format (section))
                elif (not "type" in _conf [section]) or \
                    (not _conf [section]["type"] in loader.keys ()) :
                    raise ValueError ("Model section {0}: missing or invalid "\
                                      "'type' param".format (section))
    
    #Process any explicit user-supplied arguments. These will 
    # override anything that they overlap with in the config file.
    if args.g2pfst :
        for model in args.g2pfst :
            if not os.path.isfile (model) :
                raise TypeError ("Model '{0}' does not exist!".format (model))
       
            mname = os.path.split (model) [1]
            if mname == "main" :
                raise ValueError ("Name 'main' is reserved.")
            
            _conf [mname]  = {"path": model, "type": "g2pfst"}

    if args.ip_address :
        if not "main" in _conf:
            _conf ["main"] = {"ip_address": args.ip_address}
        else :
            _conf ["main"]["ip_address"] = args.ip_address
    
    if args.port :
        if not "main" in _conf :
            _conf ["main"] = {"port": args.port}
        else :
            _conf ["main"]["port"] = args.port

    #Doublecheck that we actually have a valid server configuration
    if not "main" in _conf :
        print >> sys.stderr, "No 'main' section. Defaulting to localhost:8111"
        _conf ["main"] = {"ip_address": "localhost", "port": 8111}
    elif not "ip_address" in _conf ["main"] :
        print >> sys.stderr, "No 'ip_address' supplied. Defaulting to localhost."
        _conf ["main"]["ip_address"] = "localhost"
    elif not "port" in _conf ["main"] :
        print >> sys.stderr, "No 'port' supplied. Defaulting to '8111'."
        _conf ["main"]["port"] = 8111
    
    #Finally, try to load each of the models supplied in the config file.
    _models = {}
    for mname in _conf :
        if mname == "main" :
            continue
        _models [mname] = _conf [mname]
        mtype = _models [mname]["type"]
        mpath = _models [mname]["path"]
        try :
            _models [mname]["model"] = loader [mtype] (mpath)
            #_models [mname]["model"] = Phonetisaurus (mpath)
        except :
            raise RuntimeError ("Failed to load model: {0}!".format (mname))

    #All configuration parsing is done.  If we made it this far, we should
    # really have a valid server configuration.
    return _conf ["main"], _models

class G2PFactory (Factory) :
    """
    Factory subclass for G2P server. 

    Factory subclass for G2P server.  This is required
    in order to pass the G2P models successfully to the 
    service via the twistd daemonizer.
    """
    def __init__ (self, models) :
        self.models = models

    def buildProtocol (self, addr) :
        return NgramServer (self.models)


def setupReactor (conf, models) :
    factory = G2PFactory (models)

    reactor.listenTCP (conf ["port"], 
                       factory,
                       interface=conf ["ip_address"])
    reactor.run ()



if __name__ == '__main__':
    import sys, argparse, json, os
    
    #Sanity test without the twisted server.
    example = "USAGE: {0} --conf g2p.json --g2p test.g2p.fst ".format (sys.argv[0])
    parser  = argparse.ArgumentParser (description = example)
    parser.add_argument ("--conf", "-c", help="JSON format configuration "\
                         "file.  Explicit options will override this.")
    parser.add_argument ("--g2pfst",     "-g",  
                         help="Standard PhonetisaurusG2P model.",
                         action="append")
    parser.add_argument ("--port",    "-p",  help="Port to run the server on",
                         type=int)
    parser.add_argument ("--ip_address", "-ip", help="IP address to run on.",
                         type=str)
    parser.add_argument ("--verbose", "-v",  help="Verbose mode", 
                         default=False, action="store_true")
    args = parser.parse_args ()
    if not (args.conf or args.g2pfst) :
        parser.error ("Either --conf, or --g2pfst, or both must be supplied!")
    
    if args.verbose :
        for k,v in args.__dict__.iteritems () :
            print k, "=", v

    conf, models = ParseG2PConf (args, {"g2pfst": Phonetisaurus})
    if args.verbose :
        print conf
        print models

    setupReactor (conf, models)
    
