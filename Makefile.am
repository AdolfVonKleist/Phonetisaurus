AUTOMAKE_OPTIONS = subdir-objects
ACLOCAL_AMFLAGS = -I .autoconf/m4

bin_SCRIPTS =                          \
	src/bin/phonetisaurus_apply    \
	src/bin/phonetisaurus_train

bin_PROGRAMS =                     \
	phonetisaurus-align	   \
	phonetisaurus-arpa2wfst	   \
	phonetisaurus-g2pfst       \
	phonetisaurus-g2prnn       \
	rnnlm

AM_CPPFLAGS = -I$(top_srcdir)/src -DGIT_REVISION=\"$(GIT_REVISION)\" -std=c++0x -Wall -Wno-sign-compare -Wno-unused-local-typedefs

phonetisaurus_align_SOURCES = src/bin/phonetisaurus-align.cc src/include/PhonetisaurusRex.h src/lib/util.cc src/include/util.h src/lib/LatticePruner.cc src/include/LatticePruner.h src/lib/M2MFstAligner.cc src/include/M2MFstAligner.h
phonetisaurus_align_CXXFLAGS = $(OPENFST_CXXFLAGS) -I$(top_srcdir)/src/3rdparty/utfcpp
phonetisaurus_align_LDADD = $(OPENFST_LDFLAGS)

phonetisaurus_arpa2wfst_SOURCES = src/bin/phonetisaurus-arpa2wfst.cc src/include/ARPA2WFST.h src/lib/util.cc src/include/util.h
phonetisaurus_arpa2wfst_CXXFLAGS = $(OPENFST_CXXFLAGS) -I$(top_srcdir)/src/3rdparty/utfcpp
phonetisaurus_arpa2wfst_LDADD = $(OPENFST_LDFLAGS)

phonetisaurus_g2pfst_SOURCES = src/bin/phonetisaurus-g2pfst.cc src/include/PhonetisaurusScript.h src/include/PhonetisaurusRex.h src/lib/util.cc src/include/util.h
phonetisaurus_g2pfst_CXXFLAGS = $(OPENFST_CXXFLAGS) -I$(top_srcdir)/src/3rdparty/utfcpp -funroll-loops -ffast-math
phonetisaurus_g2pfst_LDADD = $(OPENFST_LDFLAGS)

phonetisaurus_g2prnn_SOURCES = src/bin/phonetisaurus-g2prnn.cc src/include/LegacyRnnLMHash.h src/include/LegacyRnnLMDecodable.h src/include/LegacyRnnLMReader.h src/include/RnnLMDecoder.h src/lib/util.cc src/include/util.h src/3rdparty/rnnlm/rnnlmlib.cpp src/3rdparty/rnnlm/rnnlmlib.h
phonetisaurus_g2prnn_CXXFLAGS = $(OPENFST_CXXFLAGS) -I$(top_srcdir)/src/3rdparty/utfcpp -I$(top_srcdir)/src/3rdparty/rnnlm -funroll-loops -ffast-math
phonetisaurus_g2prnn_LDADD = $(OPENFST_LDFLAGS)
if WANT_OPENMP
if OPENMP
  phonetisaurus_g2prnn_CXXFLAGS += $(OPENMP_CXXFLAGS)
  phonetisaurus_g2prnn_LDADD += $(OPENMP_LDFLAGS)
endif
endif

rnnlm_SOURCES = src/bin/rnnlm.cc src/3rdparty/rnnlm/rnnlmlib.cpp src/3rdparty/rnnlm/rnnlmlib.h
rnnlm_CXXFLAGS = $(OPENFST_CXXFLAGS) -I$(top_srcdir)/src/3rdparty/rnnlm -funroll-loops -ffast-math
rnnlm_LDADD = $(OPENFST_LDFLAGS)
