cmake_minimum_required(VERSION 3.18)
project(libexport LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# strip all symbols and metadata
set(CMAKE_BUILD_TYPE Release)
set(CMAKE_CXX_FLAGS_RELEASE "-O2")

add_library(export SHARED
    crypto.cpp
    exportbin.cpp
    exportbin_api.cpp
)

target_include_directories(export PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})

# hide symbols only in internal units, not in the API
set_source_files_properties(crypto.cpp exportbin.cpp PROPERTIES
    COMPILE_OPTIONS "-fvisibility=hidden;-fvisibility-inlines-hidden"
)

target_compile_options(export PRIVATE
    -O2
    -ffunction-sections
    -fdata-sections
    -fno-ident
    -fno-asynchronous-unwind-tables
    -fno-exceptions
    -fno-rtti
    -Wno-unused-result
)

target_link_options(export PRIVATE
    -Wl,--gc-sections            # drop unused sections
    -Wl,--strip-all              # strip all symbols
    -Wl,--build-id=none          # no build-id note
    -Wl,-z,norelro               # no RELRO segment (reduces metadata)
    -Wl,--hash-style=sysv        # minimal hash table style
    -s                           # redundant with --strip-all, belt and braces
)

# reproducible timestamps
set_target_properties(export PROPERTIES
    OUTPUT_NAME "export"
    PREFIX "lib"
    SUFFIX ".so"
)
