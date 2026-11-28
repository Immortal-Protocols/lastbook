cmake_minimum_required(VERSION 3.22)
project(lastbook_llm C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(OPT_FLAGS "-O3 -DNDEBUG -march=armv8.2-a+dotprod+fp16")
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} ${OPT_FLAGS}")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${OPT_FLAGS}")
set(CMAKE_C_FLAGS_DEBUG "${OPT_FLAGS}" CACHE STRING "" FORCE)
set(CMAKE_CXX_FLAGS_DEBUG "${OPT_FLAGS}" CACHE STRING "" FORCE)
set(CMAKE_C_FLAGS_RELEASE "${OPT_FLAGS}" CACHE STRING "" FORCE)
set(CMAKE_CXX_FLAGS_RELEASE "${OPT_FLAGS}" CACHE STRING "" FORCE)
add_compile_options(-O3 -DNDEBUG -march=armv8.2-a+dotprod+fp16)

set(ANDROID_ROOT "${CMAKE_CURRENT_LIST_DIR}/../../../../..")
set(IPAD_ROOT "${ANDROID_ROOT}/ipad")
set(LLAMA_SRC "${IPAD_ROOT}/build/deps/llama.cpp")
set(BRIDGE "${IPAD_ROOT}/llm/lastbook_llm_bridge.cpp")
set(BRIDGE_INC "${IPAD_ROOT}/llm/include")

if(NOT EXISTS "${LLAMA_SRC}/CMakeLists.txt")
  message(FATAL_ERROR "llama.cpp source missing at ${LLAMA_SRC}; run mobile/ipad/scripts/prepare_dependencies.sh")
endif()

set(BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_COMMON OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_APP OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_TOOLS OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_SERVER OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_MTMD OFF CACHE BOOL "" FORCE)
set(LLAMA_CURL OFF CACHE BOOL "" FORCE)
set(LLAMA_OPENSSL OFF CACHE BOOL "" FORCE)
set(GGML_RPC OFF CACHE BOOL "" FORCE)
set(GGML_METAL OFF CACHE BOOL "" FORCE)
set(GGML_OPENMP OFF CACHE BOOL "" FORCE)
set(GGML_NATIVE OFF CACHE BOOL "" FORCE)
set(GGML_CCACHE OFF CACHE BOOL "" FORCE)
set(GGML_BACKEND_DL OFF CACHE BOOL "" FORCE)

# The app is a debug build, but llama.cpp must run at full speed on a phone.
set(CMAKE_C_FLAGS_DEBUG "-O3 -g")
set(CMAKE_CXX_FLAGS_DEBUG "-O3 -g")

add_subdirectory("${LLAMA_SRC}" llama.cpp)

add_library(lastbook_llm SHARED
    llm_jni.cpp
    "${BRIDGE}"
    "${LLAMA_SRC}/common/fit.cpp"
    "${LLAMA_SRC}/common/log.cpp"
    "${LLAMA_SRC}/common/json.cpp"
    "${ANDROID_ROOT}/../packaging/llm/fit_unused_win.cpp"
)

target_include_directories(lastbook_llm PRIVATE
    "${BRIDGE_INC}"
    "${LLAMA_SRC}/include"
    "${LLAMA_SRC}/ggml/include"
    "${LLAMA_SRC}/common"
    "${LLAMA_SRC}/vendor"
    "${LLAMA_SRC}/src"
)

target_link_libraries(lastbook_llm PRIVATE llama)
target_link_libraries(lastbook_llm PRIVATE android log)
