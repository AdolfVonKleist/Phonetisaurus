## README.md ##
=========

Phonetisaurus G2P
#### !WARNING: In Flux! ####
A lot of things are changing.
  * Last stable version from Google code (includes downloads).  All ~2015 academic papers also refer to this:
    * https://code.google.com/p/phonetisaurus/
  
#### Documentation: ####
  * http://adolfvonkleist.github.io/Phonetisaurus/

#### Contact: ####
  * phonetisaurus@gmail.com

### Dependencies: ###
  * OpenFst (Prefer >= 1.4, compile with all extensions)
    * ``` $ ./configure --enable-static --enable-shared --enable-far \
      --enable-lookahead-fsts --enable-const-fsts --enable-pdt \
      --enable-ngram-fsts --enable-linear-fsts CC=gcc-4.9```

### Basic Build [Linux/OSX]: ###
Use the existing setup.  This should be fine for most Linux distributions
as well as newer versions of OSX.
```
 $ cd src/
 $ ./configure
 $ make
```

Use a special location for OpenFst, parallel build with 2 cores
```
 $ ./configure --with-openfst-libs=/home/ubuntu/openfst-1.4.1/lib \
          --with-openfst-includes=/home/ubuntu/openfst-1.4.1/include
 $ make -j 2 all
```

Use custom g++ under OSX (note: OpenFst must also be compiled with this
custom g++ alternative)
```
 $ ./configure --with-openfst-libs=/home/osx/openfst-1.4.1gcc/lib \
          --with-openfst-includes=/home/osx/openfst-1.4.1gcc/include \
	  CXX=g++-4.9
 $ make -j 2 all
```
#### Rebuild configure ####
If you need to rebuild the configure script you can do so:
```
 $ cd .autoconf
 $ autoconf -o ../configure
 $ cd ../
 $ make -j2 all
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
