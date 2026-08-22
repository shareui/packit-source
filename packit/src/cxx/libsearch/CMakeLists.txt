cmake_minimum_required(VERSION 3.18)
project(libsearch LANGUAGES C)

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

set(CMAKE_BUILD_TYPE Release)
set(CMAKE_C_FLAGS_RELEASE "-O3")

add_library(search SHARED
    search.c
)

target_include_directories(search PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})



target_compile_options(search PRIVATE
    -O3
    -ffunction-sections
    -fdata-sections
    -fno-ident
    -fno-asynchronous-unwind-tables
    -fno-exceptions
    -fno-unwind-tables
    -Wno-unused-result
)

target_link_options(search PRIVATE
    -Wl,--gc-sections
    -Wl,--strip-all
    -Wl,--build-id=none
    -Wl,-z,norelro
    -Wl,--hash-style=sysv
    -s
)

set_target_properties(search PROPERTIES
    OUTPUT_NAME "search"
    PREFIX "lib"
    SUFFIX ".so"
)
