set -ex

mkdir -p build
pushd build

cmake ${CMAKE_ARGS}                          \
    -DOJPH_BUILD_EXECUTABLES=ON              \
    -G "Ninja"                               \
    ..

cmake --build . --config Release

cmake --build . --config Release --target install
