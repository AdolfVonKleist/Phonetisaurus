## README.md ##
=========

Phonetisaurus G2P
#### !WARNING: In Flux! ####
A lot of things are changing.

CONTACT: phonetisaurus@gmail.com

### Dependencies: ###
  * OpenFst (Prefer >= 1.4)

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
####Rebuild configure####
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
#### phonetisaurus-g2p ####
```
 #Coming back soon!
 # $ bin/phonetisaurus-g2p --help
```
