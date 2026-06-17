#include "automation_api.h"
#include "browser_runtime.h"
#include <iostream>

AutomationAPI::AutomationAPI(BrowserRuntime* runtime) : runtime_(runtime) {}

bool AutomationAPI::RunTaskFile(const std::string& yamlPath) {
    std::cout << "Run task: " << yamlPath << std::endl;
    return true;
}
