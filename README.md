## Phonetisaurus G2P ##
[![Build Status](https://travis-ci.org/AdolfVonKleist/Phonetisaurus.svg?branch=master)](https://travis-ci.org/AdolfVonKleist/Phonetisaurus)

This repository contains scripts suitable for training, evaluating and using grapheme-to-phoneme
models for speech recognition using the OpenFst framework.  The current build requires OpenFst
version 1.6.0 or later, and the examples below use version 1.7.2.

The repository includes C++ binaries suitable for training, compiling, and evaluating G2P models.
It also some simple python bindings which may be used to extract individual
multigram scores, alignments, and to dump the raw lattices in .fst format for each word.

The python scripts and bindings were tested most recently with python v3.8.5.

Standalone distributions related to previous INTERSPEECH papers, as well as the complete, exported
final version of the old google-code repository are available via ```git-lfs``` in a separate
repository:
  * https://github.com/AdolfVonKleist/phonetisaurus-downloads

#### Contact: ####
  * phonetisaurus@gmail.com

#### Scratch Build for OpenFst v1.7.2 and Ubuntu 20.04 ####
This build was tested via AWS EC2 with a fresh Ubuntu 20.04 base, and m4.large instance.

```
$ sudo apt-get update
# Basics
$ sudo apt-get install git g++ autoconf-archive make libtool
# Python bindings
$ sudo apt-get install python-setuptools python-dev
# mitlm (to build a quick play model)
$ sudo apt-get install gfortran
```

Create a work directory of your choice:
```
$ mkdir g2p
$ cd g2p/
```

Next grab and install OpenFst-1.7.2:
```
$ wget http://www.openfst.org/twiki/pub/FST/FstDownload/openfst-1.7.2.tar.gz
$ tar -xvzf openfst-1.7.2.tar.gz
$ cd openfst-1.7.2
# Minimal configure, compatible with current defaults for Kaldi
$ ./configure --enable-static --enable-shared --enable-far --enable-ngram-fsts
$ make -j 
# Now wait a while...
$ sudo make install
# Extend your LD_LIBRARY_PATH .bashrc (assumes OpenFst installed to default location):
$ echo 'export LD_LIBRARY_PATH=${LD_LIBRARY_PATH}:/usr/local/lib:/usr/local/lib/fst' \
     >> ~/.bashrc
$ source ~/.bashrc
$ cd ..
```

Checkout the latest Phonetisaurus from master and compile without bindings:
```
$ git clone https://github.com/AdolfVonKleist/Phonetisaurus.git
$ cd Phonetisaurus
# if OpenFst is installed in the default location:
$ ./configure
# if OpenFst is installed in a special location:
$ ./configure \
      --with-openfst-includes=${OFST_PATH}/openfst-1.7.2/include \
      --with-openfst-libs=${OFST_PATH}/openfst-1.7.2/lib
$ make
$ sudo make install
$ cd ..
```

Checkout the latest Phonetisaurus from master and compile with python3 bindings:
```
$ git clone https://github.com/AdolfVonKleist/Phonetisaurus.git
$ cd Phonetisaurus
$ sudo pip3 install pybindgen
# if OpenFst is installed in the default location:
$ PYTHON=python3 ./configure --enable-python
# if OpenFst is installed in a special location:
$ PYTHON=python3 ./configure \
      --with-openfst-includes=${OFST_PATH}/openfst-1.7.2/include \
      --with-openfst-libs=${OFST_PATH}/openfst-1.7.2/lib \
      --enable-python
$ make
$ sudo make install
$ cd python
$ cp ../.libs/Phonetisaurus.so .
$ sudo python3 setup.py install
$ cd ../..
```

Grab and install mitlm to build a quick test model with the cmudict (5m):
```
$ git clone https://github.com/mitlm/mitlm.git
$ cd mitlm/
$ ./autogen.sh
$ make
$ sudo make install
$ cd ..
```

Grab a copy of the latest version of CMUdict and clean it up a bit:
```
$ mkdir example
$ cd example
$ wget https://raw.githubusercontent.com/cmusphinx/cmudict/master/cmudict.dict
# Clean it up a bit and reformat:
$ cat cmudict.dict \
  | perl -pe 's/\([0-9]+\)//;
              s/\s+/ /g; s/^\s+//;
              s/\s+$//; @_ = split (/\s+/);
              $w = shift (@_);
              $_ = $w."\t".join (" ", @_)."\n";' \
  > cmudict.formatted.dict
```

Train a complete model with default parameters using the wrapper script.
NOTE: this assumes the tool was compiled with the python3 bindings:
```
$ phonetisaurus-train --lexicon cmudict.formatted.dict --seq2_del
INFO:phonetisaurus-train:2017-07-09 16:35:31:  Checking command configuration...
INFO:phonetisaurus-train:2017-07-09 16:35:31:  Checking lexicon for reserved characters: '}', '|', '_'...
INFO:phonetisaurus-train:2017-07-09 16:35:31:  Aligning lexicon...
INFO:phonetisaurus-train:2017-07-09 16:37:44:  Training joint ngram model...
INFO:phonetisaurus-train:2017-07-09 16:37:46:  Converting ARPA format joint n-gram model to WFST format...
INFO:phonetisaurus-train:2017-07-09 16:37:59:  G2P training succeeded: train/model.fst
```

Generate pronunciations for a word list using the wrapper script:
```
$ phonetisaurus-apply --model train/model.fst --word_list test.wlist
test  T EH1 S T
jumbotron  JH AH1 M B OW0 T R AA0 N
excellent  EH1 K S AH0 L AH0 N T
eggselent  EH1 G S L AH0 N T
```

Generate pronunciations for a word list using the wrapper script.
Filter against a reference lexicon, add n-best, and run in verbose mode,
and generate :
```
$ phonetisaurus-apply --model train/model.fst --word_list test.wlist -n 2 -g -v -l cmudict.formatted.dict
DEBUG:phonetisaurus-apply:2017-07-09 16:48:22:  Checking command configuration...
DEBUG:phonetisaurus-apply:2017-07-09 16:48:22:  beam:  10000
DEBUG:phonetisaurus-apply:2017-07-09 16:48:22:  greedy:  True
DEBUG:phonetisaurus-apply:2017-07-09 16:48:22:  lexicon_file:  cmudict.formatted.dict
DEBUG:phonetisaurus-apply:2017-07-09 16:48:22:  model:  train/model.fst
DEBUG:phonetisaurus-apply:2017-07-09 16:48:22:  nbest:  2
DEBUG:phonetisaurus-apply:2017-07-09 16:48:22:  thresh:  99.0
DEBUG:phonetisaurus-apply:2017-07-09 16:48:22:  verbose:  True
DEBUG:phonetisaurus-apply:2017-07-09 16:48:22:  Loading lexicon from file...
DEBUG:phonetisaurus-apply:2017-07-09 16:48:22:  Applying G2P model...
GitRevision: kaldi-1-g5028ba-dirty
eggselent  26.85  EH1 G S L AH0 N T
eggselent  28.12  EH1 G Z L AH0 N T
excellent  0.00  EH1 K S AH0 L AH0 N T
excellent  19.28  EH1 K S L EH1 N T
jumbotron  0.00  JH AH1 M B OW0 T R AA0 N
jumbotron  17.30  JH AH1 M B OW0 T R AA2 N
test  0.00  T EH1 S T
test  11.56  T EH2 S T
```

Generate pronunciations using the alternative % of total probability mass constraint,
and print the resulting scores as human readable, normalized probabilities rather than
raw negative log scores:
```
phonetisaurus-apply --model train/model.fst --word_list Phonetisaurus/script/words.list -v -a -p 0.85 -pr
DEBUG:phonetisaurus-apply:2017-07-30 11:55:58:  Checking command configuration...
DEBUG:phonetisaurus-apply:2017-07-30 11:55:58:  accumulate:  True
DEBUG:phonetisaurus-apply:2017-07-30 11:55:58:  beam:  10000
DEBUG:phonetisaurus-apply:2017-07-30 11:55:58:  greedy:  False
DEBUG:phonetisaurus-apply:2017-07-30 11:55:58:  lexicon_file:  None
DEBUG:phonetisaurus-apply:2017-07-30 11:55:58:  logger:  <logging.Logger object at 0x7fdaa93d2410>
DEBUG:phonetisaurus-apply:2017-07-30 11:55:58:  model:  train/model.fst
DEBUG:phonetisaurus-apply:2017-07-30 11:55:58:  nbest:  100
DEBUG:phonetisaurus-apply:2017-07-30 11:55:58:  pmass:  0.85
DEBUG:phonetisaurus-apply:2017-07-30 11:55:58:  probs:  True
DEBUG:phonetisaurus-apply:2017-07-30 11:55:58:  thresh:  99.0
DEBUG:phonetisaurus-apply:2017-07-30 11:55:58:  verbose:  True
DEBUG:phonetisaurus-apply:2017-07-30 11:55:58:  phonetisaurus-g2pfst --model=train/model.fst --nbest=100 --beam=10000 --thresh=99.0 --accumulate=true --pmass=0.85 --nlog_probs=false --wordlist=Phonetisaurus/script/words.list
DEBUG:phonetisaurus-apply:2017-07-30 11:55:58:  Applying G2P model...
GitRevision: kaldi-2-g6e7c04-dirty
test  0.68  T EH1 S T
test  0.21  T EH2 S T
right  0.81  R AY1 T
right  0.13  R AY0 T
junkify  0.64  JH AH1 NG K AH0 F AY2
junkify  0.23  JH AH1 NG K IH0 F AY2
```

Align, estimate, and convert a joint n-gram model step-by-step:
```
# Align the dictionary (5m-10m)
$ phonetisaurus-align --input=cmudict.formatted.dict \
  --ofile=cmudict.formatted.corpus --seq1_del=false
# Train an n-gram model (5s-10s):
$ estimate-ngram -o 8 -t cmudict.formatted.corpus \
  -wl cmudict.o8.arpa
# Convert to OpenFst format (10s-20s):
$ phonetisaurus-arpa2wfst --lm=cmudict.o8.arpa --ofile=cmudict.o8.fst
$ cd
```

Test the manual model with the wrapper script:
```
$ cd Phonetisaurus/script
$ ./phoneticize.py -m ~/example/cmudict.o8.fst -w testing
  11.24   T EH1 S T IH0 NG
  -------
  t:T:3.31
  e:EH1:2.26
  s:S:2.61
  t:T:0.21
  i:IH0:2.66
  n|g:NG:0.16
  <eps>:<eps>:0.01
```

Test the G2P servlet [requires compilation of bindings and module install]:
```
$ nohup script/g2pserver.py -m ~/train/model.fst -l ~/cmudict.formatted.dict &
$ curl -s -F "wordlist=@words.list" http://localhost:8080/phoneticize/list
test    T EH1 S T
right   R AY1 T
junkify JH AH1 NG K AH0 F AY2
junkify JH AH1 NG K IH0 F AY2
```

Use a special location for OpenFst, parallel build with 2 cores
```
 $ ./configure --with-openfst-libs=/home/ubuntu/openfst-1.6.2/lib \
          --with-openfst-includes=/home/ubuntu/openfst-1.6.2/include
 $ make -j 2 all
```

Use custom g++ under OSX (Note: OpenFst must also be compiled with this
custom g++ alternative [untested with v1.6.2])
```
 $ ./configure --with-openfst-libs=/home/osx/openfst-1.6.2gcc/lib \
          --with-openfst-includes=/home/osx/openfst-1.6.2gcc/include \
          CXX=g++-4.9
 $ make -j 2 all
```

#### Rebuild configure ####
If you need to rebuild the configure script you can do so:
```
 $ autoreconf -i
```

### Install [Linux]: ###
```
 $ sudo make install
```

### Uninstall [Linux]: ###
```
 $ sudo make uninstall
```

### Usage: ###
#### phonetisaurus-align ####
```
 $ bin/phonetisaurus-align --help
```
#### phonetisaurus-arpa2wfst ####
```
 $ bin/phonetisaurus-arpa2wfst --help
```
#### phonetisaurus-g2prnn ####
```
 $ bin/phonetisaurus-g2prnn --help
```
#### phonetisaurus-g2pfst ####
```
 $ bin/phonetisaurus-g2pfst --help
```

### Docker: ###

Docker images are hosted on: https://hub.docker.com/r/phonetisaurus/phonetisaurus

The images can be used in one of 3 ways:

  * directly, to process files on your computer without needing to install/compile anything (apart from docker)
  * as a base image for another project (using the `FROM` statement)
  * to copy portions of the binaries or libraries into a new image (using the `COPY --from=` statement) - most of the files are in `/usr/local/bin` and `/usr/local/lib`

To use the program directly, you need to mount the local folder with the required files (eg. models, word lists, etc) into the Docker container under the `/work` path, as this is the default workdir in the image. Then you can call the programs directly after the name of the image, for example:
```
docker run --rm -it -v $PWD:/work phonetisaurus/phonetisaurus "phonetisaurus-apply -m model.fst -wl test.wlist"
```

You can also use the `bash` program to simply enter the interactive shell and run everything from there.

### Misc: ###
cpplint command:
```
 $ ./cpplint.py --filter=-whitespace/parens,-whitespace/braces,\
      -legal/copyright,-build/namespaces,-runtime/references\
      src/include/util.h
```
