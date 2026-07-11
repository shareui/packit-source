cmake_minimum_required(VERSION 3.18)
project(libpackitdb LANGUAGES C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

set(CMAKE_BUILD_TYPE Release)
set(CMAKE_C_FLAGS_RELEASE "-O3")

add_library(packitdb SHARED
    libpackitdb.c
)

target_include_directories(packitdb PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})



target_compile_options(packitdb PRIVATE
    -O3
    -ffunction-sections
    -fdata-sections
    -fno-ident
    -fno-asynchronous-unwind-tables
    -fno-exceptions
    -fno-unwind-tables
    -Wno-unused-result
)

target_link_options(packitdb PRIVATE
    -Wl,--gc-sections
    -Wl,--strip-all
    -Wl,--build-id=none
    -Wl,-z,norelro
    -Wl,--hash-style=sysv
    -s
)

set_target_properties(packitdb PROPERTIES
    OUTPUT_NAME "packitdb"
    PREFIX "lib"
    SUFFIX ".so"
)
