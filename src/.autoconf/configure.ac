#                                               -*- Autoconf -*-
# Process this file with autoconf to produce a configure script.
AC_PREREQ([2.69])
AC_INIT([phonetisaurus], [0.1], [joe@spitch.ch])
AC_CONFIG_MACRO_DIR([m4])

# Checks for programs.
AC_PROG_CXX
AX_CXX_COMPILE_STDCXX_11([], [mandatory])
#Python stuff not currently needed.  Will return.
#AX_PYTHON_DEVEL([>= '2.7'])
AC_PROG_CC
#AC_PROG_INSTALL
AC_PROG_LN_S
AC_PROG_RANLIB

# Checks for libraries.
AC_CHECK_LIB([c], [getgid],[AC_DEFINE([HAVE_GETGID],[1],[libc includes getgid])])
AC_CHECK_LIB([dl], [dlopen], [], [echo "dl library not found. Weird."; exit -1])
AC_CHECK_LIB([m], [cos], [], [echo "m library not found.  Please install m library before proceeding"; exit -1])
AC_CHECK_LIB([pthread], [pthread_mutex_init], [], [echo "pthreads not found.  Please install pthread library before proceeding"; exit -1])

# Checks for header files.
AC_CHECK_HEADERS([stddef.h stdlib.h string.h])

# Checks for typedefs, structures, and compiler characteristics.
AC_CHECK_HEADER_STDBOOL
AC_C_INLINE
AC_TYPE_SIZE_T
AC_TYPE_SSIZE_T
AC_CHECK_TYPES([ptrdiff_t])

# Checks for library functions.
AC_FUNC_STRTOD
AC_CHECK_FUNCS([memmove strchr strrchr strspn])

# Checks for optional paths
#Check for all the OpenFst stuff make sure all extensions
# AND the kaldi extensions patch were installed
default_openfst_libs=/usr/local/lib
AC_ARG_WITH([openfst-libs],
	[AS_HELP_STRING([--with-openfst-libs],
	[Location of the OpenFst shared libraries.])],
	[OPENFST_LDFLAGS="$withval"; \
	echo "Set user-defined OpenFst libs: $withval"],
	[OPENFST_LDFLAGS="$default_openfst_libs"; \
	with_openfst_libs="$default_openfst_libs"; \
	echo "Set default OpenFst libs: $default_openfst_libs"])
AC_SUBST([OPENFST_LDFLAGS])
#First check OpenFst is actually there
AS_IF([test ! -e "$with_openfst_libs""/libfst.so"],
	    [AC_MSG_ERROR([OpenFst libs not found: \
--with-openfst-libs=$with_openfst_libs \
 Did you specify --with-openfst-libs?])])
#Test all the extensions - tell the user how it *should* be compiled
#	    -a -e "$with_openfst_libs/fst/libfstpdtscript.so" \
AS_IF([test -e "$with_openfst_libs/fst/libfstconst.so" \
	    -a -e "$with_openfst_libs/fst/libfstfar.so" \
	    -a -e "$with_openfst_libs/fst/libfstngram.so" \
	    -a -e "$with_openfst_libs/fst/libfstlookahead.so" \
 	    -a -e "$with_openfst_libs/fst/libfstlinearscript.so"],
	    [AC_MSG_RESULT([Found all required OpenFst extensions.])],
	    [AC_MSG_ERROR([Can't find one or more extensions.  OpenFst should \
have been configured with the following flags: \
--enable-static --enable-shared --enable-far --enable-lookahead-fsts \
--enable-const-fsts --enable-pdt --enable-ngram-fsts --enable-linear-fsts])])

#Set the default install directories
default_install_bin=/usr/local/bin
AC_ARG_WITH([install-bin],
	[AS_HELP_STRING([--with-install-bin],
	[Install directory.])],
	[INSTALL_BIN="$withval"; \
	echo "Set user-defined install directory: $withval"],
	[INSTALL_BIN="$default_install_bin"; \
	with_install_bin="$default_install_bin"; \
	echo "Set default installation directory: $default_install_bin"])
AC_SUBST([INSTALL_BIN])

default_install_lib=/usr/local/lib
AC_ARG_WITH([install-lib],
	[AS_HELP_STRING([--with-install-lib],
	[Install directory.])],
	[INSTALL_LIB="$withval"; \
	echo "Set user-defined libraries install directory: $withval"],
	[INSTALL_LIB="$default_install_lib"; \
	with_install_lib="$default_install_lib"; \
	echo "Set default libraries installtion directory: $default_install_lib"])
AC_SUBST([INSTALL_LIB])

#Check the OpenFst headers, and then check that the patch was applied
default_openfst_includes=/usr/local/include
AC_ARG_WITH([openfst-includes],
	[AS_HELP_STRING([--with-openfst-includes],
	[Location of the OpenFst shared libraries.])],
	[OPENFST_CXXFLAGS="$withval"; \
	echo "Set user-defined OpenFst includes: $withval"],
	[OPENFST_CXXFLAGS="$default_openfst_includes"; \
	with_openfst_includes="$default_openfst_includes"; \
	echo "Set default OpenFst includes: $default_openfst_includes"])
AC_SUBST([OPENFST_CXXFLAGS])
AS_IF([test -e "$with_openfst_includes""/fst/minimize.h"],
	    [AC_MSG_RESULT([Found OpenFst headers.])],
	    [AC_MSG_ERROR([Couldn't find OpenFst headers in specified location.])])
#Check whether the OpenFst patch has been applied. Throw a warning if not
AS_IF([test -n "`grep 'CyclicMinimizer(const ExpandedFst<A>& fst):' \
	    $with_openfst_includes/fst/minimize.h`"],
	    [AC_MSG_RESULT([Found patched OpenFst header.  Everything looks OK.])],
	    [AC_MSG_WARN([OpenFst headers do not appear to be patched.  \
Did you apply the Kaldi OpenFst patch?  Might be problematic when using with Kaldi.])])


AC_CONFIG_FILES([Makefile:.autoconf/Makefile.in])
AC_OUTPUT

mv config.log .autoconf/config.log
mv config.status .autoconf/config.status
