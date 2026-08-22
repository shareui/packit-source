cmake_minimum_required(VERSION 3.18)
project(libpacklight LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

set(CMAKE_BUILD_TYPE Release)
set(CMAKE_CXX_FLAGS_RELEASE "-O3")

add_library(packlight SHARED
    packlight_api.cpp
    pl_java.cpp
    pl_json.cpp
    pl_kotlin.cpp
    pl_python.cpp
)

target_include_directories(packlight PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})



target_compile_options(packlight PRIVATE
    -O3
    -ffunction-sections
    -fdata-sections
    -fno-ident
    -fno-asynchronous-unwind-tables
    -fno-exceptions
    -fno-rtti
    -Wno-unused-result
)

target_link_options(packlight PRIVATE
    -Wl,--gc-sections
    -Wl,--strip-all
    -Wl,--build-id=none
    -Wl,-z,norelro
    -Wl,--hash-style=sysv
    -s
)

set_target_properties(packlight PROPERTIES
    OUTPUT_NAME "packlight"
    PREFIX "lib"
    SUFFIX ".so"
)
