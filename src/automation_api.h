#pragma once

#include <string>

class BrowserRuntime;

class AutomationAPI {
public:
    explicit AutomationAPI(BrowserRuntime* runtime);
    bool RunTaskFile(const std::string& yamlPath);

private:
    BrowserRuntime* runtime_ = nullptr;
};
