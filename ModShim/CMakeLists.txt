cmake_minimum_required(VERSION 3.20)
project(F4RL_Shim VERSION 1.0.0 LANGUAGES CXX)

# Require C++20 for CommonLibF4
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Configure output directories
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)

# We are building an F4SE DLL Plugin
add_library(F4RL_Shim SHARED
    src/main.cpp
)

# Point to the raw F4SE source we extracted
set(F4SE_DIR "/mnt/data1/Apps/GamePlayer/f4se_source/f4se_0_06_23/src")

target_include_directories(F4RL_Shim PRIVATE 
    src
    ${F4SE_DIR}
    ${F4SE_DIR}/f4se
    ${F4SE_DIR}/f4se_common
    ${F4SE_DIR}/xbyak
)

# MinGW requires linking against standard Windows libraries.
target_link_libraries(F4RL_Shim PRIVATE 
    kernel32 
    user32 
)

# Statically link C++ runtime so Wine doesn't need libstdc++-6.dll / libgcc_s_seh-1.dll
target_link_options(F4RL_Shim PRIVATE -static-libgcc -static-libstdc++ -static)

# Strip binary for release
if(CMAKE_BUILD_TYPE STREQUAL "Release")
    set_target_properties(F4RL_Shim PROPERTIES LINK_FLAGS "-s")
endif()
