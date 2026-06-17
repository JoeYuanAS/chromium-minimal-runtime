#pragma once

#include <string>
#include <vector>

struct FingerprintProfile {
    std::string name;
    std::string userAgent;
    std::string platform;
    std::vector<std::string> languages;
    std::string timezone;

    static FingerprintProfile LoadFromJson(const std::string& path);
};
