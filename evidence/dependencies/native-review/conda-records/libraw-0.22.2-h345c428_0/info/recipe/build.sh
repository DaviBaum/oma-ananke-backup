#!/bin/bash

cd libraw

autoreconf --install

if [ `uname` == Darwin ]; then
	USE_OPENMP=no
else
	USE_OPENMP=yes
fi;

./configure --prefix="${PREFIX}" --enable-openmp=$USE_OPENMP

make -j${CPU_COUNT}
make install
