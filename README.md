README.md
=========

AUTHOR: Josef Robert Novak

CONTACT:
  josef.robert.novak@gmail.com

NOTE:
-----
The installation instructions below have been tested on
Ubuntu 14.04.  Changes will probably be required still for
compilation on OSX.

DEPENDENCIES
------------
### python 2.7+: ###

 - python headers and twisted infrastructure:

        $ sudo apt-get install python-dev python-twisted


### Modules: ###
 - OpenFst (v1.4+):

        $ wget http://openfst.org/twiki/pub/FST/FstDownload/openfst-1.4.1.tar.gz
        $ tar -xvzf openfst-1.4.1.tar.gz
        $ cd openfst-1.4.1
        $ ./configure --enable-compact-fsts --enable-const-fsts \
            --enable-far --enable-lookahead-fsts --enable-pdt --ngram-fsts
        $ sudo make install

 - OpenGrm (1.2+):

        $ wget http://openfst.cs.nyu.edu/twiki/pub/GRM/NGramDownload/opengrm-ngram-1.2.1.tar.gz
        $ tar -xvzf opengrm-ngram-1.2.1.tar.gz
        $ cd opengrm-ngram-1.2.1
        $ ./configure
        $ sudo make install


INSTALL
-------
After installing the dependencies it should be sufficient to build the module.
```
$ cd src
$ make -j 4
$ sudo make install
$ cd ..
$ sudo python setup.py install
```

TEST
----
Test the installation with the example CMU dict model.
```
$ cd script/
$ wget https://www.dropbox.com/s/vlmlfq52rpbkniv/cmu-eg.me-kn.8g.arpa.gz?dl=0 -O test.arpa.gz
$ gunzip test.arpa.gz
$ phonetisaurus-arpa2wfst-omega --lm=test.arpa --ofile=test.fst

# Start the twisted service.  NOTE: run with '-noy' to run in foreground.
$ twistd -y g2pservice.tac

# Actually run the client
# NOTE: '-m app-id' should be a model available
#       to the server.  This is configured with the
#       'phonetisaurus-config.json' config file.
$ ./g2p-client.py -m app-id -w TEST
TEST T EH S T
$ ./g2p-client.py -m app-id -w TEST -n 3
TEST T EH S T
TEST T AH S T
TEST T IH S T

# Run with a word list
$ ./g2p-client.py -m app-id -wl wordlist -n 2
TEST              T EH S T
TEST              T AH S T
BRING             B R IH NG
BRING             B ER IH NG
EVALUATE          IH V AE L Y UW EY T
EVALUATE          IY V AE L Y UW EY T

# Shutdown the twisted server
$ kill -9 `cat twistd.pid`
```


LEGACY STUFF:
---------

2014-06-10
Added a toy decoder to illustrate direct decoding with a 
joint sequence RNNLM.  Slow but it works.

2014-04-13
Added some simple bindings and test scripts for RNNLM.  
Should make it much easier and faster to incorporate 
rescoring experiments for the G2P.

This incorporates Mikolov's rnnlmlib v0.3e.  One modification
was made: protected vars were switched to public to provide
access to the binding code.

You should be able to verify that this version of rnnlm, and
the ngram-client + ngram-server produce the same probs for 
the test model trained by the example.sh script in this version
of RNNLM, and the given test data.

NOTE: You MUST however train models with the -independent flag
 as the bindings are currently hard-wired to this for the G2P.

If the python complains, you may need to add the current directory
to your $LD_LIBRARY_PATH, or whatever directory you store the 
shared object (.so, .so.0, RnnLM.so) files in.

-------------------

Josef Robert Novak
2012-10-15

Phonetisaurus: a WFST-based G2P Conversion toolkit

Phonetisaurus is released under the BSD-2 license.

Phonetisaurus contains 2 pieces of 3rd-party code,
 which are both located in the src/3rdparty directory,
  * google's sparsehash:
    + http://code.google.com/p/sparsehash/
      which is released under the BSD-3 license
  * UTF8-CPP:
    + http://utfcpp.sourceforge.net/
      which is released under a BSD-like/compatible license 
      (see src/3rdparty/utfcpp/utf8.h header file for details)

Phonetisaurus also relies on the OpenFst library
  * http://www.openfst.org
  * which is released under the Apache-2.0 license

Please see the googlecode repository for tutorial information:
 * http://code.google.com/p/phonetisaurus
 * http://code.google.com/p/phonetisaurus/wiki/FSMNLPTutorial

