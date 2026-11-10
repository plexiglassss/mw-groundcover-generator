from __future__ import annotations

from pathlib import Path
import re
import sys

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("mwgc-src")
solid_path = root / "src" / "logic" / "SolidAssets.cpp"
cmake_path = root / "CMakeLists.txt"
solid = solid_path.read_text(encoding="utf-8")
original = solid


def replace_once(old: str, new: str, label: str) -> None:
    global solid
    count = solid.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one {label} occurrence, found {count}")
    solid = solid.replace(old, new, 1)

replace_once(
    "#include <stdexcept>\n#include <utility>",
    "#include <stdexcept>\n#include <string_view>\n#include <utility>",
    "string_view include insertion",
)

replace_once(
    '''std::string trim(const std::string& s) {
    const auto first = s.find_first_not_of(" \\t\\r\\n");
    if (first == std::string::npos) return {};
    return s.substr(first, s.find_last_not_of(" \\t\\r\\n") - first + 1);
}

// Resource names are relative to a data directory, never filesystem paths.
''',
    '''std::string trim(const std::string& s) {
    const auto first = s.find_first_not_of(" \\t\\r\\n");
    if (first == std::string::npos) return {};
    return s.substr(first, s.find_last_not_of(" \\t\\r\\n") - first + 1);
}

// OpenMW configuration files and resource names are UTF-8. On Windows,
// std::filesystem::path::string() converts through the active ANSI code page
// and throws for characters such as curly apostrophes and en/em dashes.
// Keep every path boundary explicitly UTF-8 instead.
std::string pathUtf8(const fs::path& path) {
#if defined(_WIN32)
    const auto value = path.u8string();
    return std::string(reinterpret_cast<const char*>(value.data()), value.size());
#else
    return path.string();
#endif
}

fs::path pathFromUtf8(std::string_view value) {
#if defined(_WIN32)
    const auto* first = reinterpret_cast<const char8_t*>(value.data());
    return fs::path(std::u8string(first, first + value.size()));
#else
    return fs::path(value);
#endif
}

// Resource names are relative to a data directory, never filesystem paths.
''',
    "UTF-8 path helpers",
)

replace_once("    fs::path path(text);", "    fs::path path = pathFromUtf8(text);", "UTF-8 config path parse")

replacements = {
    ' + path.string()': ' + pathUtf8(path)',
    ' + impl->configuration.string()': ' + pathUtf8(impl->configuration)',
    'impl->configuration.string(), impl->data.size()': 'pathUtf8(impl->configuration), impl->data.size()',
    'impl->providers[key] = path->string();': 'impl->providers[key] = pathUtf8(*path);',
    'impl->providers[key] = entry.archive.string() + "::" + *normalized;': 'impl->providers[key] = pathUtf8(entry.archive) + "::" + *normalized;',
    'impl->loaded, impl->failed, impl->configuration.string());': 'impl->loaded, impl->failed, pathUtf8(impl->configuration));',
}
for old, new in replacements.items():
    count = solid.count(old)
    if count == 0:
        raise RuntimeError(f"Missing expected path conversion fragment: {old}")
    solid = solid.replace(old, new)

replace_once(
    '''        if (fs::is_directory(path, error)) {
            for (const auto& entry : fs::directory_iterator(path)) {
                if (index.size() > 1000000) throw std::runtime_error("Resource directory exceeds entry limit: " + pathUtf8(path));
                const auto key = lower(entry.path().filename().string());
                if (!index.emplace(key, entry.path()).second)
                    throw std::runtime_error("Ambiguous resource filenames differing only by case in " + pathUtf8(path));
            }
        } else if (error) throw fs::filesystem_error("Could not inspect resource directory", path, error);
''',
    '''        if (fs::is_directory(path, error)) {
            auto iterator = fs::directory_iterator(path, error);
            if (error) {
                throw std::runtime_error("Could not enumerate resource directory: " + pathUtf8(path)
                    + ": " + error.message());
            }
            for (const auto& entry : iterator) {
                if (index.size() > 1000000)
                    throw std::runtime_error("Resource directory exceeds entry limit: " + pathUtf8(path));
                const auto key = lower(pathUtf8(entry.path().filename()));
                if (!index.emplace(key, entry.path()).second)
                    throw std::runtime_error("Ambiguous resource filenames differing only by case in " + pathUtf8(path));
            }
        } else if (error) {
            throw std::runtime_error("Could not inspect resource directory: " + pathUtf8(path)
                + ": " + error.message());
        }
''',
    "Unicode-safe directory enumeration",
)

replace_once(
    '''        } else {
            if (error && error != std::errc::no_such_file_or_directory)
                throw fs::filesystem_error("Could not inspect OpenMW data directory", path, error);
            if (impl->logger) impl->logger->warn("Solid clearance: missing data directory skipped: {}", path.string());
        }
''',
    '''        } else {
            if (error && error != std::errc::no_such_file_or_directory)
                throw std::runtime_error("Could not inspect OpenMW data directory: " + pathUtf8(path)
                    + ": " + error.message());
            if (impl->logger) impl->logger->warn("Solid clearance: missing data directory skipped: {}", pathUtf8(path));
        }
''',
    "Unicode-safe data-directory error",
)

remaining = [
    line for line in solid.splitlines()
    if '.string()' in line and 'return path.string();' not in line and 'std::string()' not in line
]
if remaining:
    raise RuntimeError("Narrow filesystem conversions remain:\n" + "\n".join(remaining))

if solid == original:
    raise RuntimeError("SolidAssets.cpp was not changed")
solid_path.write_text(solid, encoding="utf-8", newline="\n")

cmake = cmake_path.read_text(encoding="utf-8")
updated, count = re.subn(r"project\(MW_GROUNDCOVER_GENERATOR VERSION 0\.6\.10\)",
                         "project(MW_GROUNDCOVER_GENERATOR VERSION 0.6.11)", cmake, count=1)
if count != 1:
    raise RuntimeError(f"Expected one 0.6.10 project version, found {count}")
cmake_path.write_text(updated, encoding="utf-8", newline="\n")
print("Applied UTF-8 filesystem path fix and versioned source as 0.6.11")
