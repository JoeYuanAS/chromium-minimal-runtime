#pragma once

#include <string>

class BrowserRuntime {
public:
    bool Init(const std::string& runtimeConfigPath);
    bool SetHeadless(bool headless);
    bool Goto(const std::string& url);
    std::string Evaluate(const std::string& js);
    std::string DumpDom();
    bool Screenshot(const std::string& path);
    void Shutdown();

private:
    bool headless_ = true;
};
