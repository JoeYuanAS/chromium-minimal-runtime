#include "browser_runtime.h"
#include "automation_api.h"

int main(int argc, char** argv) {
    BrowserRuntime runtime;
    runtime.Init("config/runtime.yaml");
    runtime.SetHeadless(true);
    runtime.Goto("https://example.com");
    runtime.Evaluate("document.title");
    runtime.Screenshot("output/example.png");
    runtime.Shutdown();
    return 0;
}
