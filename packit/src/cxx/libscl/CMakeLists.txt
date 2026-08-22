cmake_minimum_required(VERSION 3.18)
project(libscl LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)
set(CMAKE_CXX_EXTENSIONS OFF)

set(CMAKE_BUILD_TYPE Release)
set(CMAKE_C_FLAGS_RELEASE "-O3")
set(CMAKE_CXX_FLAGS_RELEASE "-O3")

file(GLOB_RECURSE SCL_SOURCES "src/*.c" "src/*.cpp")

add_library(scl SHARED
    ${SCL_SOURCES}
)

target_include_directories(scl PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
target_include_directories(scl PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/include)



target_compile_options(scl PRIVATE
    -O3
    -ffunction-sections
    -fdata-sections
    -fno-ident
    -fno-asynchronous-unwind-tables
    -Wno-unused-result
)

target_link_options(scl PRIVATE
    -Wl,--gc-sections
    -Wl,--strip-all
    -Wl,--build-id=none
    -Wl,-z,norelro
    -Wl,--hash-style=sysv
    -s
)

set_target_properties(scl PROPERTIES
    OUTPUT_NAME "scl"
    PREFIX "lib"
    SUFFIX ".so"
)
