#include "fingerprint_profile.h"
#include <iostream>

FingerprintProfile FingerprintProfile::LoadFromJson(const std::string& path) {
    std::cout << "Load fingerprint profile: " << path << std::endl;
    FingerprintProfile profile;
    profile.name = "default";
    return profile;
}
