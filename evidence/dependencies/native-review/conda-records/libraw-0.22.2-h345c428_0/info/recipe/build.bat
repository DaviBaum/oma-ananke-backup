setlocal EnableDelayedExpansion

:: Copy CMake files to the source directory
copy cmake\CMakeLists.txt libraw
mkdir libraw\cmake
mkdir libraw\cmake\data
mkdir libraw\cmake\modules
copy cmake\cmake\*.cmake.in libraw\cmake
copy cmake\cmake\data\*.cmake libraw\cmake\data
copy cmake\cmake\modules\*.cmake libraw\cmake\modules

cd libraw
dir
mkdir build
cd build

:: Configure using the CMakeFiles
cmake -G "Ninja" ^
      -DCMAKE_PREFIX_PATH="%LIBRARY_PREFIX%" ^
      -DCMAKE_INSTALL_PREFIX:PATH="%LIBRARY_PREFIX%" ^
      -DCMAKE_BUILD_TYPE:STRING=Release ^
      ..
if errorlevel 1 exit 1
cmake --build . --config Release --target install
if errorlevel 1 exit 1
