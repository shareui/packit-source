cmake_minimum_required(VERSION 3.18)
project(libachiv LANGUAGES C)

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

# strip all symbols and metadata
set(CMAKE_BUILD_TYPE Release)
set(CMAKE_C_FLAGS_RELEASE "-O3")

add_library(achiv SHARED
    achievG.c
)

target_include_directories(achiv PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})



target_compile_options(achiv PRIVATE
    -O3
    -ffunction-sections
    -fdata-sections
    -fno-ident
    -fno-asynchronous-unwind-tables
    -fno-exceptions
    -fno-unwind-tables
    -Wno-unused-result
)

target_link_options(achiv PRIVATE
    -Wl,--gc-sections            # drop unused sections
    -Wl,--strip-all              # strip all symbols
    -Wl,--build-id=none          # no build-id note
    -Wl,-z,norelro               # no RELRO segment
    -Wl,--hash-style=sysv        # minimal hash table style
    -s                           # redundant with --strip-all
)

set_target_properties(achiv PROPERTIES
    OUTPUT_NAME "achiv"
    PREFIX "lib"
    SUFFIX ".so"
)
