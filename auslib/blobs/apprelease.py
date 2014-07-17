from auslib import dbo
from auslib.AUS import containsForbiddenDomain, getFallbackChannel
from auslib.blobs.base import Blob
from auslib.util.versions import MozillaVersion


class ReleaseBlobBase(Blob):
    def matchesUpdateQuery(self, updateQuery):
        self.log.debug("Trying to match update query to %s" % self["name"])
        buildTarget = updateQuery["buildTarget"]
        buildID = updateQuery["buildID"]
        locale = updateQuery["locale"]

        if buildTarget in self["platforms"]:
            try:
                releaseBuildID = self.getBuildID(buildTarget, locale)
            # Platform doesn't exist in release, clearly it's not a match!
            except KeyError:
                return False
            self.log.debug("releasePlat buildID is: %s", releaseBuildID)
            if buildID == releaseBuildID:
                self.log.debug("Query matched!")
                return True

    def getResolvedPlatform(self, platform):
        return self['platforms'][platform].get('alias', platform)

    def getPlatformData(self, platform):
        platform = self.getResolvedPlatform(platform)
        return self['platforms'][platform]

    def getLocaleOrTopLevelParam(self, platform, locale, param):
        try:
            platform = self.getResolvedPlatform(platform)
            return self['platforms'][platform]['locales'][locale][param]
        except KeyError:
            try:
                return self[param]
            except KeyError:
                return None

    def getBuildID(self, platform, locale):
        platform = self.getResolvedPlatform(platform)
        if locale not in self['platforms'][platform]['locales']:
            raise KeyError("No such locale '%s' in platform '%s'" % (locale, platform))
        try:
            return self['platforms'][platform]['locales'][locale]['buildID']
        except KeyError:
            return self['platforms'][platform]['buildID']

    def getUrl(self, updateQuery, patch, specialForceHosts, ftpFilename, bouncerProduct):
        platformData = self.getPlatformData(updateQuery["buildTarget"])
        if 'fileUrl' in patch:
            url = patch['fileUrl']
        else:
            # When we're using a fallback channel it's unlikely
            # we'll have a fileUrl specifically for it, but we
            # should try nonetheless. Non-fallback cases shouldn't
            # be hitting any exceptions here.
            try:
                url = self['fileUrls'][updateQuery['channel']]
            except KeyError:
                try:
                    url = self['fileUrls'][getFallbackChannel(updateQuery['channel'])]
                except KeyError:
                    self.log.debug("Couldn't find fileUrl for")
                    raise

            url = url.replace('%LOCALE%', updateQuery['locale'])
            url = url.replace('%OS_FTP%', platformData['OS_FTP'])
            url = url.replace('%FILENAME%', ftpFilename)
            url = url.replace('%PRODUCT%', bouncerProduct)
            url = url.replace('%OS_BOUNCER%', platformData['OS_BOUNCER'])
        # pass on forcing for special hosts (eg download.m.o for mozilla metrics)
        if updateQuery['force']:
            url = self.processSpecialForceHosts(url, specialForceHosts)

        return url

    def getSpecificPatchXML(self, patchKey, patchType, patch, updateQuery, whitelistedDomains, specialForceHosts):
        try:
            fromRelease = dbo.releases.getReleaseBlob(name=patch["from"])
        except KeyError:
            fromRelease = None

        ftpFilename = self.getFtpFilename(patchKey, patch["from"])
        bouncerProduct = self.getBouncerProduct(patchKey, patch["from"])

        if patch["from"] != "*" and fromRelease and not fromRelease.matchesUpdateQuery(updateQuery):
            return None

        url = self.getUrl(updateQuery, patch, specialForceHosts, ftpFilename, bouncerProduct)
        # TODO: should be raising a bigger alarm here, or aborting
        # the update entirely? Right now, another patch type could still
        # return an update. Eg, the partial could contain a forbidden domain
        # but the complete could still return an update from an accepted one.
        if containsForbiddenDomain(url, whitelistedDomains):
            return None

        return '        <patch type="%s" URL="%s" hashFunction="%s" hashValue="%s" size="%s"/>' % \
            (patchType, url, self["hashFunction"], patch["hashValue"], patch["filesize"])

    def createXML(self, updateQuery, update_type, whitelistedDomains, specialForceHosts):
        buildTarget = updateQuery["buildTarget"]
        locale = updateQuery["locale"]
        localeData = self.getPlatformData(buildTarget)["locales"][locale]

        updateLine = self.getUpdateLineXML(buildTarget, locale, update_type)
        patches = self.getPatchesXML(localeData, updateQuery, whitelistedDomains, specialForceHosts)

        xml = ['<?xml version="1.0"?>']
        xml.append('<updates>')
        if patches:
            xml.append(updateLine)
            xml.extend(patches)
            xml.append('    </update>')
        xml.append('</updates>')
        return xml

    def shouldServeUpdate(self, updateQuery):
        buildTarget = updateQuery['buildTarget']
        locale = updateQuery['locale']
        releaseVersion = self.getApplicationVersion(buildTarget, locale)
        if not releaseVersion:
            self.log.debug("Matching rule has no extv, will not serve update.")
            return False
        releaseVersion = MozillaVersion(releaseVersion)
        queryVersion = MozillaVersion(updateQuery['version'])
        if queryVersion > releaseVersion:
            self.log.debug("Matching rule has older version than request, will not serve update.")
            return False
        elif releaseVersion == queryVersion:
            if updateQuery['buildID'] >= self.getBuildID(updateQuery['buildTarget'], updateQuery['locale']):
                self.log.debug("Matching rule has older buildid than request, will not serve update.")
                return False

        return True


class SingleUpdateXMLMixin(object):
    def getFtpFilename(self, patchKey, from_):
        return self.get("ftpFilenames", {}).get(patchKey, "")

    def getBouncerProduct(self, patchKey, from_):
        return self.get("bouncerProducts", {}).get(patchKey, "")

    def getPatchesXML(self, localeData, updateQuery, whitelistedDomains, specialForceHosts):
        patches = []
        for patchKey in ("partial", "complete"):
            patch = localeData.get(patchKey)
            if not patch:
                continue

            xml = self.getSpecificPatchXML(patchKey, patchKey, patch, updateQuery, whitelistedDomains, specialForceHosts)
            if xml:
                patches.append(xml)

        return patches


class ReleaseBlobV1(ReleaseBlobBase, SingleUpdateXMLMixin):
    format_ = {
        'name': None,
        'schema_version': None,
        'extv': None,
        'appv': None,
        'fileUrls': {
            '*': None
        },
        'ftpFilenames': {
            '*': None
        },
        'bouncerProducts': {
            '*': None
        },
        'hashFunction': None,
        'detailsUrl': None,
        'licenseUrl': None,
        'fakePartials': None,
        'platforms': {
            '*': {
                'alias': None,
                'buildID': None,
                'OS_BOUNCER': None,
                'OS_FTP': None,
                'locales': {
                    '*': {
                        'buildID': None,
                        'extv': None,
                        'appv': None,
                        'partial': {
                            'filesize': None,
                            'from': None,
                            'hashValue': None,
                            'fileUrl': None
                        },
                        'complete': {
                            'filesize': None,
                            'from': None,
                            'hashValue': None,
                            'fileUrl': None
                        }
                    }
                }
            }
        }
    }

    def __init__(self, **kwargs):
        # ensure schema_version is set if we init ReleaseBlobV1 directly
        Blob.__init__(self, **kwargs)
        if 'schema_version' not in self.keys():
            self['schema_version'] = 1

    def getAppv(self, platform, locale):
        return self.getLocaleOrTopLevelParam(platform, locale, 'appv')

    def getExtv(self, platform, locale):
        return self.getLocaleOrTopLevelParam(platform, locale, 'extv')

    def getApplicationVersion(self, platform, locale):
        """ We used extv as the application version for v1 schema, while appv
        may have been a pretty version for users to see"""
        return self.getExtv(platform, locale)

    def createSnippets(self, updateQuery, update_type, whitelistedDomains, specialForceHosts):
        snippets = {}
        buildTarget = updateQuery["buildTarget"]
        locale = updateQuery["locale"]
        platformData = self.getPlatformData(buildTarget)
        localeData = platformData["locales"][locale]
        for patchKey in ("partial", "complete"):
            patch = localeData.get(patchKey)
            if not patch:
                continue

            try:
                fromRelease = dbo.releases.getReleaseBlob(name=patch["from"])
            except KeyError:
                fromRelease = None
            ftpFilename = self.get("ftpFilenames", {}).get(patchKey)
            bouncerProduct = self.get("bouncerProducts", {}).get(patchKey)

            if patch["from"] != "*" and fromRelease and not fromRelease.matchesUpdateQuery(updateQuery):
                continue

            url = self.getUrl(updateQuery, patch, specialForceHosts, ftpFilename, bouncerProduct)
            if containsForbiddenDomain(url, whitelistedDomains):
                break

            snippet = [
                "version=1",
                "type=%s" % patchKey,
                "url=%s" % url,
                "hashFunction=%s" % self["hashFunction"],
                "hashValue=%s" % patch["hashValue"],
                "size=%s" % patch["filesize"],
                "build=%s" % self.getBuildID(buildTarget, locale),
                "appv=%s" % self.getAppv(buildTarget, locale),
                "extv=%s" % self.getExtv(buildTarget, locale),
            ]
            if "detailsUrl" in self:
                details = self["detailsUrl"].replace("%LOCALE%", updateQuery["locale"])
                snippet.append("detailsUrl=%s" % details)
            if "licenseUrl" in self:
                license = self["licenseUrl"].replace("%LOCALE%", updateQuery["locale"])
                snippet.append("licenseUrl=%s" % license)
            if update_type == "major":
                snippet.append("updateType=major")
            snippets[patchKey] = "\n".join(snippet) + "\n"

        if self.get("fakePartials") and "complete" in snippets and "partial" not in snippets:
            partial = snippets["complete"]
            partial = partial.replace("type=complete", "type=partial")
            snippets["partial"] = partial

        for s in snippets.keys():
            self.log.debug('%s\n%s' % (s, snippets[s].rstrip()))
        return snippets

    def getUpdateLineXML(self, buildTarget, locale, update_type):
        appv = self.getAppv(buildTarget, locale)
        extv = self.getExtv(buildTarget, locale)
        buildid = self.getBuildID(buildTarget, locale)

        updateLine = '    <update type="%s" version="%s" extensionVersion="%s" buildID="%s"' % \
            (update_type, appv, extv, buildid)
        if "detailsUrl" in self:
            details = self["detailsUrl"].replace("%LOCALE%", locale)
            updateLine += ' detailsURL="%s"' % details
        if "licenseUrl" in self:
            license = self["licenseUrl"].replace("%LOCALE%", locale)
            updateLine += ' licenseURL="%s"' % license
        updateLine += ">"

        return updateLine


class NewStyleVersionsMixin(object):
    def getAppVersion(self, platform, locale):
        return self.getLocaleOrTopLevelParam(platform, locale, 'appVersion')

    def getDisplayVersion(self, platform, locale):
        return self.getLocaleOrTopLevelParam(platform, locale, 'displayVersion')

    def getPlatformVersion(self, platform, locale):
        return self.getLocaleOrTopLevelParam(platform, locale, 'platformVersion')

    def getApplicationVersion(self, platform, locale):
        """ For v2 schema, appVersion really is the app version """
        return self.getAppVersion(platform, locale)

    def getUpdateLineXML(self, buildTarget, locale, update_type):
        displayVersion = self.getDisplayVersion(buildTarget, locale)
        appVersion = self.getAppVersion(buildTarget, locale)
        platformVersion = self.getPlatformVersion(buildTarget, locale)
        buildid = self.getBuildID(buildTarget, locale)
        localeData = self.getPlatformData(buildTarget)["locales"][locale]

        updateLine = '    <update type="%s" displayVersion="%s" appVersion="%s" platformVersion="%s" buildID="%s"' % \
            (update_type, displayVersion, appVersion, platformVersion, buildid)
        if "detailsUrl" in self:
            details = self["detailsUrl"].replace("%LOCALE%", locale)
            updateLine += ' detailsURL="%s"' % details
        if "licenseUrl" in self:
            license = self["licenseUrl"].replace("%LOCALE%", locale)
            updateLine += ' licenseURL="%s"' % license
        if localeData.get("isOSUpdate"):
            updateLine += ' isOSUpdate="true"'
        for attr in self.optional_:
            if attr in self:
                updateLine += ' %s="%s"' % (attr, self[attr])
        updateLine += ">"

        return updateLine


class ReleaseBlobV2(ReleaseBlobBase, NewStyleVersionsMixin, SingleUpdateXMLMixin):
    """ Changes from ReleaseBlobV1:
         * appv, extv become appVersion, platformVersion, displayVersion
        Added:
         * actions, billboardURL, openURL, notificationURL,
           alertURL, showPrompt, showSurvey, showNeverForVersion, isOSUpdate
    """
    format_ = {
        'name': None,
        'schema_version': None,
        'appVersion': None,
        'displayVersion': None,
        'platformVersion': None,
        'fileUrls': {
            '*': None
        },
        'ftpFilenames': {
            '*': None
        },
        'bouncerProducts': {
            '*': None
        },
        'hashFunction': None,
        'detailsUrl': None,
        'licenseUrl': None,
        'actions': None,
        'billboardURL': None,
        'openURL': None,
        'notificationURL': None,
        'alertURL': None,
        'showPrompt': None,
        'showNeverForVersion': None,
        'showSurvey': None,
        'platforms': {
            '*': {
                'alias': None,
                'buildID': None,
                'OS_BOUNCER': None,
                'OS_FTP': None,
                'locales': {
                    '*': {
                        'isOSUpdate': None,
                        'buildID': None,
                        'appVersion': None,
                        'displayVersion': None,
                        'platformVersion': None,
                        'partial': {
                            'filesize': None,
                            'from': None,
                            'hashValue': None,
                            'fileUrl': None
                        },
                        'complete': {
                            'filesize': None,
                            'from': None,
                            'hashValue': None,
                            'fileUrl': None
                        }
                    }
                }
            }
        }
    }
    # for the benefit of createXML and createSnippetv2
    optional_ = ('billboardURL', 'showPrompt', 'showNeverForVersion',
                 'showSurvey', 'actions', 'openURL', 'notificationURL',
                 'alertURL')

    def __init__(self, **kwargs):
        # ensure schema_version is set if we init ReleaseBlobV2 directly
        Blob.__init__(self, **kwargs)
        if 'schema_version' not in self.keys():
            self['schema_version'] = 2

    def createSnippets(self, updateQuery, update_type, whitelistedDomains, specialForceHosts):
        snippets = {}
        buildTarget = updateQuery["buildTarget"]
        locale = updateQuery["locale"]
        platformData = self.getPlatformData(buildTarget)
        localeData = platformData["locales"][locale]
        for patchKey in ("partial", "complete"):
            patch = localeData.get(patchKey)
            if not patch:
                continue

            try:
                fromRelease = dbo.releases.getReleaseBlob(name=patch["from"])
            except KeyError:
                fromRelease = None
            ftpFilename = self.get("ftpFilenames", {}).get(patchKey)
            bouncerProduct = self.get("bouncerProducts", {}).get(patchKey)

            if patch["from"] != "*" and fromRelease and not fromRelease.matchesUpdateQuery(updateQuery):
                continue

            url = self.getUrl(updateQuery, patch, specialForceHosts, ftpFilename, bouncerProduct)
            if containsForbiddenDomain(url, whitelistedDomains):
                break

            snippet = [
                "version=2",
                "type=%s" % patchKey,
                "url=%s" % url,
                "hashFunction=%s" % self["hashFunction"],
                "hashValue=%s" % patch["hashValue"],
                "size=%s" % patch["filesize"],
                "build=%s" % self.getBuildID(buildTarget, locale),
                "displayVersion=%s" % self.getDisplayVersion(buildTarget, locale),
                "appVersion=%s" % self.getAppVersion(buildTarget, locale),
                "platformVersion=%s" % self.getPlatformVersion(buildTarget, locale),
            ]
            if "detailsUrl" in self:
                details = self["detailsUrl"].replace("%LOCALE%", updateQuery["locale"])
                snippet.append("detailsUrl=%s" % details)
            if "licenseUrl" in self:
                license = self["licenseUrl"].replace("%LOCALE%", updateQuery["locale"])
                snippet.append("licenseUrl=%s" % license)
            if update_type == "major":
                snippet.append("updateType=major")
            for attr in self.optional_:
                if attr in self:
                    snippet.append("%s=%s" % (attr, self[attr]))
            snippets[patchKey] = "\n".join(snippet) + "\n"

        for s in snippets.keys():
            self.log.debug('%s\n%s' % (s, snippets[s].rstrip()))
        return snippets


class MultipleUpdatesXMLMixin(object):
    def getFtpFilename(self, patchKey, from_):
        return self.get("ftpFilenames", {}).get(patchKey, {}).get(from_, "")

    def getBouncerProduct(self, patchKey, from_):
        return self.get("bouncerProducts", {}).get(patchKey, {}).get(from_, "")

    def getPatchesXML(self, localeData, updateQuery, whitelistedDomains, specialForceHosts):
        patches = []
        for patchKey, patchType in (("partials", "partial"), ("completes", "complete")):
            for patch in localeData.get(patchKey):
                xml = self.getSpecificPatchXML(patchKey, patchType, patch, updateQuery, whitelistedDomains, specialForceHosts)
                if xml:
                    patches.append(xml)
                    break

        return patches


class ReleaseBlobV3(ReleaseBlobBase, NewStyleVersionsMixin, MultipleUpdatesXMLMixin):
    """ Changes from ReleaseBlobV2:
         * support multiple partials
           * remove "partial" and "complete" from locale level
           * add "partials" and "completes" to locale level, ftpFilenames, and bouncerProducts
    """
    format_ = {
        'name': None,
        'schema_version': None,
        'appVersion': None,
        'displayVersion': None,
        'platformVersion': None,
        'fileUrls': {
            '*': None
        },
        'ftpFilenames': {
            'partials': {
                '*': None
            },
            'completes': {
                '*': None
            }
        },
        'bouncerProducts': {
            'partials': {
                '*': None
            },
            'completes': {
                '*': None
            }
        },
        'hashFunction': None,
        'detailsUrl': None,
        'licenseUrl': None,
        'actions': None,
        'billboardURL': None,
        'openURL': None,
        'notificationURL': None,
        'alertURL': None,
        'showPrompt': None,
        'showNeverForVersion': None,
        'showSurvey': None,
        'platforms': {
            '*': {
                'alias': None,
                'buildID': None,
                'OS_BOUNCER': None,
                'OS_FTP': None,
                'locales': {
                    '*': {
                        'isOSUpdate': None,
                        'buildID': None,
                        'appVersion': None,
                        'displayVersion': None,
                        'platformVersion': None,
                        # Using lists instead of dicts for multiple updates
                        # gives us a way to reduce load a bit. As this is
                        # iterated over, each "from" release is looked up
                        # in the database. If the "from" releases that we
                        # we expect to be the most common are earlier in the
                        # list, we can avoid looking up every single entry.
                        # The server doesn't know anything about which order is
                        # best, so we assume the client will make the right
                        # decision about this.
                        'partials': [
                            {
                                'filesize': None,
                                'from': None,
                                'hashValue': None,
                                'fileUrl': None
                            }
                        ],
                        'completes': [
                            {
                                'filesize': None,
                                'from': None,
                                'hashValue': None,
                                'fileUrl': None
                            }
                        ]
                    }
                }
            }
        }
    }
    # for the benefit of createXML and createSnippetv2
    optional_ = ('billboardURL', 'showPrompt', 'showNeverForVersion',
                 'showSurvey', 'actions', 'openURL', 'notificationURL',
                 'alertURL')

    def __init__(self, **kwargs):
        # ensure schema_version is set if we init ReleaseBlobV3 directly
        Blob.__init__(self, **kwargs)
        if 'schema_version' not in self.keys():
            self['schema_version'] = 3

    def createSnippets(self, updateQuery, update_type, whitelistedDomains, specialForceHosts):
        # We have no tests that require this, probably not worthwhile to implement.
        return {}
