import json
from twisted.application import service, internet
from twisted.internet.protocol import Factory
import TwistedG2P
from phonetisaurus import Phonetisaurus

class ArgParser () :
    """
    Parse the arguments in the configuration file.
    """
    def __init__ (self, config_file) :
        self.conf = config_file
        self.g2pfst     = None
        self.ip_address = None
        self.port       = None


def GetG2PService () :
    """
    
    """
    args = ArgParser ("phonetisaurus-config.json")
    conf, models = TwistedG2P.ParseG2PConf (args, {"g2pfst": Phonetisaurus})
    factory = TwistedG2P.G2PFactory (models)

    return internet.TCPServer (conf ["port"], 
                               factory, 
                               interface=conf ["ip_address"])

application = service.Application ("Phonetisaurus G2P")
service     = GetG2PService ()
service.setServiceParent (application)
