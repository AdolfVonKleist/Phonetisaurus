# Makefile
#
# Copyright (c) [2012-], Josef Robert Novak
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
#  modification, are permitted #provided that the following conditions
#  are met:
#
#  * Redistributions of source code must retain the above copyright 
#    notice, this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above 
#    copyright notice, this list of #conditions and the following 
#    disclaimer in the documentation and/or other materials provided 
#    with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS 
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT 
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS 
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE 
# COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, 
# INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES 
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR 
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) 
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, 
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) 
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED 
# OF THE POSSIBILITY OF SUCH DAMAGE.
BINDIR=bin
LIBDIR=lib
ROOT=$(shell pwd)
INSTALLBIN=/usr/local/bin
INSTALLLIB=/usr/local/lib

CC=g++

UNAME := $(shell uname)
ifeq ($(UNAME), Darwin)
LIBS=-lfst -ldl -lm -Wall -Wno-sign-compare
endif

ifeq ($(UNAME), Linux)
LIBS=-lfst -ldl -lm -lrt
CC=g++ -std=c++0x -fPIC -Wall -Wno-sign-compare
endif


OUT =: $(OBJS) $(BINDIR)/phonetisaurus-align $(BINDIR)/phonetisaurus-arpa2wfst \
	$(BINDIR)/phonetisaurus-g2prnn $(BINDIR)/rnnlm
CFLAGS ?= -O2     
THIRD_PARTIES_INCLUDE ?= -I3rdparty/sparsehash -I3rdparty/utfcpp \
	-I3rdparty/rnnlm

EXTRA := $(CFLAGS) $(THIRD_PARTIES_INCLUDE) $(CXXFLAGS) $(CPPFLAGS)
OBJS  := $(LIBDIR)/util.o \
	$(LIBDIR)/ARPA2WFST.o \
	$(LIBDIR)/rnnlmlib.o \
	$(LIBDIR)/FstPathFinder.o \
	$(LIBDIR)/LatticePruner.o \
	$(LIBDIR)/M2MFstAligner.o \
	$(LIBDIR)/phonetisaurus-align.o \
	$(LIBDIR)/phonetisaurus-arpa2wfst.o \
	$(LIBDIR)/rnnlmlib.o

vpath %.cc $(LIBDIR)/
$(LIBDIR)/%.o: %.cc
	$(CC) $(EXTRA) $(CFLAGS) -I. -c $(<) -o $(@)

all: phonetisaurus-align phonetisaurus-arpa2wfst phonetisaurus-g2prnn rnnlm

#Phony stuff
.PHONY: phonetisaurus-align phonetisaurus-arpa2wfst phonetisaurus-g2prnn rnnlm
phonetisaurus-align: $(BINDIR)/phonetisaurus-align
phonetisaurus-arpa2wfst: $(BINDIR)/phonetisaurus-arpa2wfst
phonetisaurus-g2prnn: $(BINDIR)/phonetisaurus-g2prnn
phonetisaurus-g2p: $(BINDIR)/phonetisaurus-g2p
rnnlm: $(BINDIR)/rnnlm

#General stuff
$(BINDIR)/phonetisaurus-align: $(LIBDIR)/util.o $(LIBDIR)/LatticePruner.o \
	$(LIBDIR)/M2MFstAligner.o $(LIBDIR)/FstPathFinder.o
	$(CC) $(EXTRA) $(LDFLAGS) -I$(ROOT) $(LIBS) $(LIBDIR)/util.o $(LIBDIR)/LatticePruner.o \
	$(LIBDIR)/M2MFstAligner.o $(LIBDIR)/FstPathFinder.o bin/phonetisaurus-align.cc \
	-o $(BINDIR)/phonetisaurus-align $(LIBS)

$(BINDIR)/phonetisaurus-arpa2wfst: $(LIBDIR)/ARPA2WFST.o $(LIBDIR)/util.o
	$(CC) $(EXTRA) $(LDFLAGS) $(LIBS) $(LIBDIR)/ARPA2WFST.o $(LIBDIR)/util.o \
	-I$(ROOT) bin/phonetisaurus-arpa2wfst.cc \
	-o $(BINDIR)/phonetisaurus-arpa2wfst $(LIBS)

$(BINDIR)/phonetisaurus-g2prnn: $(LIBDIR)/rnnlmlib.o bin/phonetisaurus-g2prnn.cc \
	include/RnnLMDecoder.h include/LegacyRnnLMDecodable.h $(LIBDIR)/util.o
	$(CC) $(EXTRA) -O2 -lfst -lm -std=c++0x -I3rdparty/rnnlm -I3rdparty/utfcpp \
	-funroll-loops -I$(ROOT) -ffast-math $(LIBDIR)/util.o $(LIBDIR)/rnnlmlib.o \
	bin/phonetisaurus-g2prnn.cc -fopenmp -o bin/phonetisaurus-g2prnn -lfst -ldl -lm

#RNNLM library
bin/rnnlm: $(BINDIR)/rnnlm.cc $(LIBDIR)/rnnlmlib.o
	$(CC) $(EXTRA) -std=c++0x -fPIC -I. -funroll-loops -ffast-math -lm -w \
	$(LIBDIR)/rnnlmlib.o -o bin/rnnlm $(BINDIR)/rnnlm.cc

$(LIBDIR)/rnnlmlib.o: 3rdparty/rnnlm/rnnlmlib.cpp 3rdparty/rnnlm/rnnlmlib.h
	$(CC) $(EXTRA) -std=c++0x -fPIC -I. -lfst -lm -ldl \
	-funroll-loops -ffast-math -lm -w -c 3rdparty/rnnlm/rnnlmlib.cpp \
	-o $(LIBDIR)/rnnlmlib.o

#Installation
install: all
	install -c $(BINDIR)/phonetisaurus-align $(INSTALLBIN)/
	install -c $(BINDIR)/phonetisaurus-arpa2wfst $(INSTALLBIN)/
	install -c $(BINDIR)/phonetisaurus-g2prnn $(INSTALLBIN)/
	install -c $(BINDIR)/rnnlm $(INSTALLBIN)/

#Cleanup
clean: 
	$(RM) $(OUT) $(TMP)

