#include "logic/SolidAssets.h"

#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

namespace fs = std::filesystem;

namespace {
std::string pathUtf8(const fs::path& path) {
#if defined(_WIN32)
    const auto value = path.u8string();
    return std::string(reinterpret_cast<const char*>(value.data()), value.size());
#else
    return path.string();
#endif
}

struct Cleanup {
    fs::path path;
    ~Cleanup() {
        std::error_code ignored;
        fs::remove_all(path, ignored);
    }
};
}

int main() {
    try {
        const auto unique = std::to_string(std::chrono::steady_clock::now().time_since_epoch().count());
        const fs::path root = fs::temp_directory_path() / ("mwgc-unicode-path-test-" + unique);
        Cleanup cleanup{root};
        const fs::path data = root / fs::path(u8"Data \u2013 Moon");

        fs::create_directories(data / fs::path(u8"Necromancer\u2019s Moon"));
        fs::create_directories(data / fs::path(u8"Reign of Fire \u2013 OpenMW Edition"));
        fs::create_directories(data / fs::path(u8"Engineers Guild \u2014 Chapter 1"));
        fs::create_directories(data / "Meshes");

        const fs::path config = root / "openmw.cfg";
        std::ofstream output(config, std::ios::binary);
        output << "data=\"" << pathUtf8(data) << "\"\n";
        output.close();
        if (!output) throw std::runtime_error("Could not write Unicode OpenMW test configuration");

        std::vector<spdlog::sink_ptr> sinks;
        auto logger = std::make_shared<spdlog::logger>("unicode-path-regression", sinks.begin(), sinks.end());
        SolidAssets assets(config, logger);
        if (assets.get("f/missing.nif") != nullptr)
            throw std::runtime_error("A deliberately missing test model unexpectedly resolved");

        const auto configUtf8 = pathUtf8(assets.configurationPath());
        if (configUtf8.find("mwgc-unicode-path-test-") == std::string::npos)
            throw std::runtime_error("Configuration path was not preserved");

        std::cout << "Unicode OpenMW path regression passed\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Unicode OpenMW path regression failed: " << error.what() << '\n';
        return 1;
    }
}
