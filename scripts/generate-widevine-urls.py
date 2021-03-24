url = "https://aus5.mozilla.org/update/3/Widevine/{version}/{buildid}/{build_target}/en-US/{channel}/{os_version}/default/default/update.xml"

# Only used for a couple of specific, hardcoded tests
old_buildid = 20170829220349
newer_buildid = 20200101010101


import json
import sys

config = json.load(open(sys.argv[1]))

for channel, channel_config in config["channels"].items():
    min_version = channel_config["min_version"]
    max_version = channel_config["max_version"]
    point_releases = channel_config.get("point_releases")

    all_versions = []
    current_version = min_version
    while current_version <= max_version:
        all_versions.append(current_version)
        if point_releases:
            v = current_version[:4]
            for i in range(1, point_releases+1):
                all_versions.append(v + "." + str(i))
        current_version = str(int(current_version[:2]) + 1) + current_version[2:]

    for v in all_versions:
        buildids = [newer_buildid]
        if channel == "nightly" and v < "58.0a1":
            buildids.append(old_buildid)
        if channel != "nightly" and v < "57.0":
            buildids.append(old_buildid)

        for buildid in buildids:
            for build_target, os_versions in config["build_targets"].items():
                for os_version in os_versions:
                    print(url.format(
                        version=v,
                        buildid=buildid,
                        build_target=build_target,
                        channel=channel,
                        os_version=os_version,
                    ))
