#                                               -*- Autoconf -*-
# Process this file with autoconf to produce a configure script.
AC_PREREQ([2.69])
AC_INIT([phonetisaurus], [0.8.1], [phonetisaurus@gmail.com])
AC_CONFIG_MACRO_DIR([.autoconf/m4])
AC_CONFIG_AUX_DIR([.autoconf])
AC_CONFIG_SRCDIR(configure.ac)

GIT_REVISION=`git describe --abbrev=6 --dirty --always --tags 2>/dev/null || echo package`
AC_SUBST([GIT_REVISION])

AM_INIT_AUTOMAKE([foreign -Wall])
AM_MAINTAINER_MODE

AM_PROG_AR
LT_INIT

AC_ARG_ENABLE(python,
        AS_HELP_STRING([--enable-python], [Compile with Python support]),
        [case "${enableval}" in
          yes) enable_python=true ;;
          no) enable_python=false ;;
          *) AC_MSG_ERROR(bad value ${enableval} for --enable-python) ;;
        esac], [enable_python=false])
AM_CONDITIONAL(WANT_PYTHON, test x"$enable_python" = xtrue)

AS_IF([test x"$enable_python" = xtrue], [
AM_PATH_PYTHON([2.7],, [:])
])
AM_CONDITIONAL([HAVE_PYTHON], [test "$PYTHON" != :])
AC_SUBST([PYTHON])
if test x"$PYTHON" != x && test "$PYTHON" != ":"; then
   PYTHON_CPPFLAGS=
   PYTHON_LIBS=
   AX_PYTHON_DEVEL([>= '$PYTHON_VERSION'])
fi
AM_CONDITIONAL([HAVE_PYTHON_DEV], [test x"$PYTHON" != x && test "$PYTHON" != :])
AC_SUBST([PYTHON_CPPFLAGS])
AC_SUBST([PYTHON_LIBS])

AC_LANG(C++)
# Checks for programs.
AC_PROG_CXX
AX_CXX_COMPILE_STDCXX_11([], [mandatory])
#Python stuff not currently needed.  Will return.
#AX_PYTHON_DEVEL([>= '2.7'])
AC_PROG_CC
AC_PROG_CPP
#AC_PROG_INSTALL
AC_PROG_LN_S

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
AC_CHECK_MATH_FUNC(exp10)

AC_ARG_WITH([openfst-includes],
	[AS_HELP_STRING([--with-openfst-includes],
	[Location of the OpenFst headers.])],
	[user_openfst_headers_path="$withval"],
	[])
AC_ARG_WITH([openfst-libs],
	[AS_HELP_STRING([--with-openfst-libs],
	[Location of the OpenFst shared libraries.])],
	[user_openfst_libs_path="$withval"],
	[])

saved_cppflags="${CPPFLAGS}"
if [[ "$user_openfst_headers_path" != "" ]]; then
      CPPFLAGS="-I$user_openfst_headers_path"
      AC_CHECK_HEADERS([fst/fst.h], [openfst_headers_found=1], [openfst_headers_found=0], [])
      if [[ $openfst_headers_found -eq 1 ]]; then
         OPENFST_CXXFLAGS="$CPPFLAGS"
      fi
else
   CPPFLAGS=""
   AC_CHECK_HEADERS([fst/fst.h], [openfst_headers_found=1], [openfst_headers_found=0], [])
   if [[ $openfst_headers_found -eq 1 ]]; then
      OPENFST_CXXFLAGS="$CPPFLAGS"
   else
      CPPFLAGS="-I/usr/local/include"
      AC_CHECK_HEADERS([fst/fst.h], [openfst_headers_found=1], [openfst_headers_found=0], [])
      if [[ $openfst_headers_found -eq 1 ]]; then
         OPENFST_CXXFLAGS="$CPPFLAGS"
      fi
   fi
fi
CPPFLAGS="${saved_cppflags}"

AC_MSG_CHECKING([for openfst libraries])
CHECK_LIBRARIES="-lfst -lfstfar -lfstngram"
saved_ldflags="${LDFLAGS}"
saved_cppflags="${CPPFLAGS}"
CPPFLAGS="${OPENFST_CXXFLAGS}"
if test x"$user_openfst_libs_path" != x; then
   LDFLAGS="-L$user_openfst_libs_path ${CHECK_LIBRARIES}"
   AC_LINK_IFELSE([AC_LANG_PROGRAM([#include <fst/fst.h>], [std::unique_ptr<fst::FstHeader> ifst(fst::FstHeader());])],
       [have_openfst=true],                                           
       [have_openfst=false])
   if test x"$have_openfst" = xtrue; then
      OPENFST_LDFLAGS="$LDFLAGS"
      AC_MSG_RESULT([$OPENFST_LDFLAGS])
   fi
else
   LDFLAGS="${CHECK_LIBRARIES}"
   AC_LINK_IFELSE([AC_LANG_PROGRAM([#include <fst/fst.h>], [std::unique_ptr<fst::FstHeader> ifst(fst::FstHeader());])],
       [have_openfst=true],                                           
       [have_openfst=false])
   if test x"$have_openfst" = xtrue; then
      OPENFST_LDFLAGS="$LDFLAGS"
      AC_MSG_RESULT([$OPENFST_LDFLAGS])
   else
      LDFLAGS="-L/usr/local/lib ${CHECK_LIBRARIES}"
      AC_LINK_IFELSE([AC_LANG_PROGRAM([#include <fst/fst.h>], [std::unique_ptr<fst::FstHeader> ifst(fst::FstHeader());])],
          [have_openfst=1],                                           
          [have_openfst=0])
      if test x"$have_openfst" = xtrue; then
         OPENFST_LDFLAGS="$LDFLAGS"
         AC_MSG_RESULT([$OPENFST_LDFLAGS])
      else
         AC_MSG_RESULT([no])
      fi
   fi
fi
LDFLAGS="${saved_ldflags}"
CPPFLAGS="${saved_cppflags}"

if test x"$have_openfst" != xtrue; then
   AC_MSG_ERROR([Can't find OpenFST or one or more of its extensions. Use --with-openfst-includes and --with-openfst-libs to specify where you have installed OpenFst. OpenFst should have been configured with the following flags: --enable-static --enable-shared --enable-far --enable-ngram-fsts])
fi
AC_SUBST([OPENFST_CXXFLAGS])
AC_SUBST([OPENFST_LDFLAGS])
AM_CONDITIONAL(OPENFST, [test x"$have_openfst" = xtrue])

AX_OPENMP([AC_DEFINE(HAVE_OPENMP,1,[Define if OpenMP is enabled])] [have_openmp=true])
AM_CONDITIONAL(OPENMP, [test x"$have_openmp" = xtrue])
AC_SUBST([OPENMP_CXXFLAGS])
AC_SUBST([OPENMP_LDFLAGS])
AC_ARG_ENABLE(openmp,
        AS_HELP_STRING([--enable-openmp], [Compile with OpenMP support]),
        [case "${enableval}" in
          yes) enable_openmp=true ;;
          no) enable_openmp=false ;;
          *) AC_MSG_ERROR(bad value ${enableval} for --enable-openmp) ;;
        esac], [enable_openmp=false])
AM_CONDITIONAL(WANT_OPENMP, test x"$enable_openmp" = xtrue)

saved_cppflags="${CPPFLAGS}"
CPPFLAGS=
AC_CHECK_HEADERS([utf8.h], [utfcpp_headers_found=1], [utfcpp_headers_found=0], [])
if [[ $utfcpp_headers_found -eq 1 ]]; then
    UTFCPP_CXXFLAGS="$CPPFLAGS"
else
    UTFCPP_CXXFLAGS="-I \${top_srcdir}/src/3rdparty/utfcpp"
fi
CPPFLAGS="${saved_cppflags}"
AC_SUBST([UTFCPP_CXXFLAGS])
AM_CONDITIONAL(UTFCPP, [test x"$utfcpp_headers_found" = x1])


AC_CONFIG_FILES([Makefile])
AC_OUTPUT
