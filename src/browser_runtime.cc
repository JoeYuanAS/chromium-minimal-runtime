#include "browser_runtime.h"
#include <iostream>

bool BrowserRuntime::Init(const std::string& runtimeConfigPath) {
    std::cout << "Init Chromium Minimal Runtime with config: " << runtimeConfigPath << std::endl;
    return true;
}

bool BrowserRuntime::SetHeadless(bool headless) {
    headless_ = headless;
    return true;
}

bool BrowserRuntime::Goto(const std::string& url) {
    std::cout << "Goto: " << url << std::endl;
    return true;
}

std::string BrowserRuntime::Evaluate(const std::string& js) {
    std::cout << "Evaluate: " << js << std::endl;
    return "{}";
}

std::string BrowserRuntime::DumpDom() {
    return "<html></html>";
}

bool BrowserRuntime::Screenshot(const std::string& path) {
    std::cout << "Screenshot: " << path << std::endl;
    return true;
}

void BrowserRuntime::Shutdown() {
    std::cout << "Shutdown" << std::endl;
}
