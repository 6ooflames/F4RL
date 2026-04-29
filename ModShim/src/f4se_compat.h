#pragma once
// =============================================================================
// F4SE MinGW Compatibility Shim
// =============================================================================
// F4SE was built for MSVC and force-includes common/IPrefix.h (which pulls in
// ITypes.h, IErrors.h, etc.) to define UInt32, STATIC_ASSERT, __forceinline,
// and other MSVC-specific constructs.
//
// This header provides MinGW-compatible definitions for the subset of F4SE
// types and macros we actually use, so we can include PluginAPI.h and
// GameThreads.h without dragging in the entire MSVC-only common/ tree.
// =============================================================================

#include <cstdint>
#include <cstdlib>
#include <cstdio>
#include <cstring>
#include <string>

// --- Windows headers (MinGW provides these) ---
#include <windows.h>

// --- F4SE Base Type Aliases (from common/ITypes.h) ---
typedef unsigned char       UInt8;
typedef unsigned short      UInt16;
typedef unsigned long       UInt32;
typedef unsigned long long  UInt64;
typedef signed char         SInt8;
typedef signed short        SInt16;
typedef signed long         SInt32;
typedef signed long long    SInt64;
typedef float               Float32;
typedef double              Float64;

// --- STATIC_ASSERT (from common/IErrors.h) ---
// F4SE uses a pre-C++11 static assert pattern. We can just map to static_assert.
#define STATIC_ASSERT(expr) static_assert((expr), #expr)

// --- MSVC-specific keyword compat ---
#ifndef __forceinline
#define __forceinline __attribute__((always_inline)) inline
#endif

// Stub for MSVC __declspec(novtable) - not needed on MinGW but referenced
#ifndef __declspec
// MinGW supports __declspec, but just in case:
#endif

// --- F4SE Logging Stubs ---
// F4SE uses _MESSAGE etc. from IDebugLog.h. We stub them to OutputDebugString.
#ifndef _MESSAGE
#define _MESSAGE(fmt, ...) do { \
    char _msg_buf[1024]; \
    snprintf(_msg_buf, sizeof(_msg_buf), fmt, ##__VA_ARGS__); \
    OutputDebugStringA(_msg_buf); \
} while(0)
#endif

#ifndef _WARNING
#define _WARNING(fmt, ...) _MESSAGE("WARNING: " fmt, ##__VA_ARGS__)
#endif

#ifndef _ERROR
#define _ERROR(fmt, ...) _MESSAGE("ERROR: " fmt, ##__VA_ARGS__)
#endif

// --- Assertion stubs (from common/IErrors.h) ---
inline void _AssertionFailed(const char* file, unsigned long line, const char* desc) {
    char buf[1024];
    snprintf(buf, sizeof(buf), "ASSERTION FAILED: %s (%s:%lu)", desc, file, line);
    OutputDebugStringA(buf);
}

inline void _AssertionFailed_ErrCode(const char* file, unsigned long line, const char* desc, unsigned long long code) {
    char buf[1024];
    snprintf(buf, sizeof(buf), "ASSERTION FAILED: %s (code: %llu) (%s:%lu)", desc, code, file, line);
    OutputDebugStringA(buf);
}

inline void _AssertionFailed_ErrCode(const char* file, unsigned long line, const char* desc, const char* code) {
    char buf[1024];
    snprintf(buf, sizeof(buf), "ASSERTION FAILED: %s (code: %s) (%s:%lu)", desc, code, file, line);
    OutputDebugStringA(buf);
}

#define ASSERT(a)           do { if(!(a)) _AssertionFailed(__FILE__, __LINE__, #a); } while(0)
#define ASSERT_STR(a, b)    do { if(!(a)) _AssertionFailed(__FILE__, __LINE__, b); } while(0)

// --- Macro helpers used in Utilities.h ---
#define __MACRO_JOIN__(a, b)      __MACRO_JOIN_2__(a, b)
#define __MACRO_JOIN_2__(a, b)    __MACRO_JOIN_3__(a, b)
#define __MACRO_JOIN_3__(a, b)    a##b
#define __PREPRO_TOKEN_STR2__(a)  #a
#define __PREPRO_TOKEN_STR__(a)   __PREPRO_TOKEN_STR2__(a)

// --- FORCE_INLINE used in Utilities.h DEFINE_MEMBER_FN macros ---
#ifndef FORCE_INLINE
#define FORCE_INLINE __attribute__((always_inline)) inline
#endif
