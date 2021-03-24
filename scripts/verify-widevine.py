url = "https://aus5.mozilla.org/update/3/Widevine/{version}/{buildid}/{build_target}/en-US/{channel}/{os_version}/default/default/update.xml"

# Only used for a couple of specific, hardcoded tests
old_buildid = 20170829220349
newer_buildid = 20200101010101

all_channels = ["nightly", "beta", "release", "esr"]
all_build_targets = {
    "Darwin_x86_64-gcc3-u-i386-x86_64": ["Darwin 15", "Darwin 16", "Darwin 17", "Darwin 18", "Darwin 19", "Darwin 20"],
    "Darwin_aarch64-gcc3": ["Darwin 15", "Darwin 16", "Darwin 17", "Darwin 18", "Darwin 19", "Darwin 20"],
    "Linux_x86-gcc3": ["default"],
    "Linux_x86_64-gcc3": ["default"],
    "WINNT_x86-msvc": ["Windows_NT 10", "Windows_NT 8", "Windows_NT 6"],
    "WINNT_x86_64-msvc-x64": ["Windows_NT 10", "Windows_NT 8"],
    "WINNT_aarch64-msvc-aarch64": ["Windows_NT 10", "Windows_NT 8", "Windows_NT 6"]
}

def parse_test_case(line, append_test):
    parts = line.split(",")
    version = parts[0].strip()
    channel = parts[1].strip()
    if channel == "*":
        channels = all_channels
    else:
        channels = [channel]
    build_target = parts[2].strip()
    if build_target == "*":
        build_targets = all_build_targets.keys()
    else:
        build_targets = [build_target]
    widevine_version = parts[3].strip()
    if widevine_version == "none":
        widevine_version = None

    for c in channels:
        if append_test:
            c += "test"
        buildids = [newer_buildid]
        if c.startswith("nightly") and version < "58.0":
            buildids.append(old_buildid)
        if not c.startswith("nightly") and version < "57.0":
            buildids.append(old_buildid)

        for buildid in buildids:
            for bt in build_targets:
                # behaviour is undefined and irrelevant for aarch64 darwin on older firefox versions
                if version < "80.0" and bt == "Darwin_aarch64-gcc3":
                    continue
                for os_version in all_build_targets[bt]:
                    yield url.format(version=version, buildid=buildid, build_target=bt, channel=c, os_version=os_version), widevine_version


def main(test_case_file, append_test):
    if append_test == "True":
        append_test = True
    else:
        append_test = False
    cases = {}
    with open(test_case_file) as f:
        while line := f.readline():
            for url, expected in parse_test_case(line, append_test):
                cases[url] = expected

        import requests
        for url, expected in cases.items():
            r = requests.get(url)
            content = r.content.decode("utf-8")
            if expected:
                if expected in content:
                    print(f"PASS: {url}")
                else:
                    print(f"FAIL: {url}")
                    print(f"Expected widevine version {expected}, got this response instead:")
                    print(content)
            else:
                if "gmp-widevinecdm" in content:
                    print(f"FAIL: {url}")
                    print("Should not have gotten a widevine version")
                else:
                    print(f"PASS: {url}")

import sys
main(sys.argv[1], sys.argv[2])
