cmake_minimum_required(VERSION 3.20)
project(chromium_minimal_runtime_shell)

set(CMAKE_CXX_STANDARD 17)

# 注意：这个 CMake 只用于演示本项目自己的抽象层。
# 真正接入 Chromium 时，需要放入 Chromium GN 构建系统，而不是用 CMake 直接链接 Chromium。

add_executable(chromium_minimal_runtime_shell
    src/app_main.cc
    src/browser_runtime.cc
    src/fingerprint_profile.cc
    src/automation_api.cc
)

target_include_directories(chromium_minimal_runtime_shell PRIVATE src)
