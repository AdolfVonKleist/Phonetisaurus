AUTOMAKE_OPTIONS = subdir-objects
ACLOCAL_AMFLAGS = -I .autoconf/m4

bin_SCRIPTS =                          \
	src/bin/phonetisaurus_apply    \
	src/bin/phonetisaurus_train

bin_PROGRAMS =                         \
	bin/phonetisaurus-align	       \
	bin/phonetisaurus-arpa2wfst    \
	bin/phonetisaurus-g2pfst       \
	bin/phonetisaurus-g2prnn       \
	bin/rnnlm

AM_CPPFLAGS = -I$(top_srcdir)/src -DGIT_REVISION=\"$(GIT_REVISION)\" -std=c++0x -Wall -Wno-sign-compare -Wno-unused-local-typedefs

bin_phonetisaurus_align_SOURCES = src/bin/phonetisaurus-align.cc src/include/PhonetisaurusRex.h src/lib/util.cc src/include/util.h src/lib/LatticePruner.cc src/include/LatticePruner.h src/lib/M2MFstAligner.cc src/include/M2MFstAligner.h
bin_phonetisaurus_align_CXXFLAGS = $(OPENFST_CXXFLAGS) -I$(top_srcdir)/src/3rdparty/utfcpp
bin_phonetisaurus_align_LDADD = $(OPENFST_LDFLAGS)

bin_phonetisaurus_arpa2wfst_SOURCES = src/bin/phonetisaurus-arpa2wfst.cc src/include/ARPA2WFST.h src/lib/util.cc src/include/util.h
bin_phonetisaurus_arpa2wfst_CXXFLAGS = $(OPENFST_CXXFLAGS) -I$(top_srcdir)/src/3rdparty/utfcpp
bin_phonetisaurus_arpa2wfst_LDADD = $(OPENFST_LDFLAGS)

bin_phonetisaurus_g2pfst_SOURCES = src/bin/phonetisaurus-g2pfst.cc src/include/PhonetisaurusScript.h src/include/PhonetisaurusRex.h src/lib/util.cc src/include/util.h
bin_phonetisaurus_g2pfst_CXXFLAGS = $(OPENFST_CXXFLAGS) -I$(top_srcdir)/src/3rdparty/utfcpp -funroll-loops -ffast-math
bin_phonetisaurus_g2pfst_LDADD = $(OPENFST_LDFLAGS)

bin_phonetisaurus_g2prnn_SOURCES = src/bin/phonetisaurus-g2prnn.cc src/include/LegacyRnnLMHash.h src/include/LegacyRnnLMDecodable.h src/include/LegacyRnnLMReader.h src/include/RnnLMDecoder.h src/lib/util.cc src/include/util.h src/3rdparty/rnnlm/rnnlmlib.cpp src/3rdparty/rnnlm/rnnlmlib.h
bin_phonetisaurus_g2prnn_CXXFLAGS = $(OPENFST_CXXFLAGS) -I$(top_srcdir)/src/3rdparty/utfcpp -I$(top_srcdir)/src/3rdparty/rnnlm -funroll-loops -ffast-math
bin_phonetisaurus_g2prnn_LDADD = $(OPENFST_LDFLAGS)
if WANT_OPENMP
if OPENMP
  bin_phonetisaurus_g2prnn_CXXFLAGS += $(OPENMP_CXXFLAGS)
  bin_phonetisaurus_g2prnn_LDADD += $(OPENMP_LDFLAGS)
endif
endif

bin_rnnlm_SOURCES = src/bin/rnnlm.cc src/3rdparty/rnnlm/rnnlmlib.cpp src/3rdparty/rnnlm/rnnlmlib.h
bin_rnnlm_CXXFLAGS = $(OPENFST_CXXFLAGS) -I$(top_srcdir)/src/3rdparty/rnnlm -funroll-loops -ffast-math
bin_rnnlm_LDADD = $(OPENFST_LDFLAGS)

if WANT_PYTHON
if HAVE_PYTHON

python/Phonetisaurus-binding.cc: $(top_srcdir)/python/phonetisaurus-module.py
	mkdir -p python
	$(PYTHON) -B $(top_srcdir)/python/phonetisaurus-module.py > python/Phonetisaurus-binding.cc

CLEANFILES = python/Phonetisaurus-binding.cc

if HAVE_PYTHON_DEV
pyexec_LTLIBRARIES = Phonetisaurus.la
nodist_Phonetisaurus_la_SOURCES = python/Phonetisaurus-binding.cc src/lib/util.cc src/include/util.h
Phonetisaurus_la_CXXFLAGS = $(OPENFST_CXXFLAGS) $(PYTHON_CPPFLAGS) -I$(top_srcdir)/src/3rdparty/utfcpp -funroll-loops -ffast-math
Phonetisaurus_la_LIBADD = $(OPENFST_LDFLAGS) $(PYTHON_LIBS)
Phonetisaurus_la_LDFLAGS = -avoid-version -module
endif
endif
endif
