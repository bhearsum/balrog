import simplejson as json
from urlparse import urlparse

import logging
log = logging.getLogger(__name__)

from auslib.log import cef_event, CEF_ALERT

# TODO: move me
def isSpecialURL(url, specialForceHosts):
    if not specialForceHosts:
        return False
    for s in specialForceHosts:
        if url.startswith(s):
            return True
    return False

# TODO: move me
def containsForbiddenDomain(url, whitelistedDomains):
    domain = urlparse(url)[1]
    if domain not in whitelistedDomains:
        cef_event("Forbidden domain", CEF_ALERT, domain=domain)
        return True
    return False

def isValidBlob(format_, blob, topLevel=True):
    """Decides whether or not 'blob' is valid based on the format provided.
       Validation follows these rules:
       1) If there's no format at all, the blob is valid.
       2) If the format contains a '*' key, all key names are accepted.
       3) If the format doesn't contain a '*' key, all keys in the blob must
          also be present in the format.
       3) If the value for the key is None, all values for that key are valid.
       4) If the value for the key is a dictionary, validate it.
    """
    # If there's no format at all, we assume the blob is valid.
    if not format_:
        return True
    # If the blob isn't a dictionary-like or list-like object, it's not valid!
    if not isinstance(blob, (dict,list)):
        return False
    # If the blob format has a schema_version then that's a mandatory int
    if topLevel and 'schema_version' in format_:
        if 'schema_version' not in blob or not isinstance(blob['schema_version'], int):
            log.debug("blob is not valid because schema_version is not defined, or non-integer")
            return False
    # check the blob against the format
    if isinstance(blob, dict):
        for key in blob.keys():
            # A '*' key in the format means that all key names in the blob are accepted.
            if '*' in format_:
                # But we still need to validate the sub-blob, if it exists.
                if format_['*'] and not isValidBlob(format_['*'], blob[key], topLevel=False):
                    log.debug("blob is not valid because of key '%s'" % key)
                    return False
            # If there's no '*' key, we need to make sure the key name is valid
            # and the sub-blob is valid, if it exists.
            elif key not in format_ or not isValidBlob(format_[key], blob[key], topLevel=False):
                log.debug("blob is not valid because of key '%s'" % key)
                return False
    else:
        # Empty lists are not allowed. These can be represented by leaving out the key entirely.
        if len(blob) == 0:
            return False
        for subBlob in blob:
            # Other than the empty list check above, we can hand off the rest
            # of the validation to another isValidBlob call!
            if not isValidBlob(format_[0], subBlob, topLevel=False):
                return False
    return True

def createBlob(data):
    """Takes a string form of a blob (eg from DB or API) and converts into an
    actual blob, taking care to notice the schema"""
    data = json.loads(data)
    try:
        if data['schema_version'] == 1:
            return ReleaseBlobV1(**data)
        elif data['schema_version'] == 2:
            return ReleaseBlobV2(**data)
        elif data['schema_version'] == 3:
            return ReleaseBlobV3(**data)
        else:
            raise ValueError("schema_version is unknown")
    except KeyError:
        raise ValueError("schema_version is not set")

class Blob(dict):
    """See isValidBlob for details on how format is used to validate blobs."""
    format_ = {}

    def __init__(self, *args, **kwargs):
        self.log = logging.getLogger(self.__class__.__name__)
        dict.__init__(self, *args, **kwargs)

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

    def isValid(self):
        """Decides whether or not this blob is valid based."""
        self.log.debug('Validating blob %s' % self)
        return isValidBlob(self.format_, self)

    def loadJSON(self, data):
        """Replaces this blob's contents with parsed contents of the json
           string provided."""
        self.clear()
        self.update(json.loads(data))

    def getJSON(self):
        """Returns a JSON formatted version of this blob."""
        return json.dumps(self)

    def getFallbackChannel(self, channel):
        return channel.split('-cck-')[0]

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

    def getUrl(self, updateQuery, patch, specialForceHosts, ftpFilename=None, bouncerProduct=None):
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
                    url = self['fileUrls'][self.getFallbackChannel(updateQuery['channel'])]
                except KeyError:
                    self.log.debug("Couldn't find fileUrl for")
                    raise

            url = url.replace('%LOCALE%', updateQuery['locale'])
            url = url.replace('%OS_FTP%', platformData['OS_FTP'])
            url = url.replace('%FILENAME%', ftpFilename)
            url = url.replace('%PRODUCT%', bouncerProduct)
            url = url.replace('%OS_BOUNCER%', platformData['OS_BOUNCER'])
        # pass on forcing for special hosts (eg download.m.o for mozilla metrics)
        if updateQuery['force'] and isSpecialURL(url, specialForceHosts):
            if '?' in url:
                url += '&force=1'
            else:
                url += '?force=1'

        return url

class ReleaseBlobV1(Blob):
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

    def createSnippets(self, db, updateQuery, update_type, whitelistedDomains, specialForceHosts):
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
                fromRelease = db.releases.getReleaseBlob(name=patch["from"])
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

    def createXML(self, db, updateQuery, update_type, whitelistedDomains, specialForceHosts):
        buildTarget = updateQuery["buildTarget"]
        locale = updateQuery["locale"]

        platformData = self.getPlatformData(buildTarget)
        localeData = platformData["locales"][locale]
        appv = self.getAppv(buildTarget, locale)
        extv = self.getExtv(buildTarget, locale)
        buildid = self.getBuildID(buildTarget, locale)

        updateLine = '    <update type="%s" version="%s" extensionVersion="%s" buildID="%s"' % \
            (update_type, appv, extv, buildid)
        if "detailsUrl" in self:
            details = self["detailsUrl"].replace("%LOCALE%", updateQuery["locale"])
            updateLine += ' detailsURL="%s"' % details
        if "licenseUrl" in self:
            license = self["licenseUrl"].replace("%LOCALE%", updateQuery["locale"])
            updateLine += ' licenseURL="%s"' % license
        updateLine += ">"

        patches = []
        forbidden = False
        for patchKey in ("partial", "complete"):
            patch = localeData.get(patchKey)
            if not patch:
                continue

            try:    
                fromRelease = db.releases.getReleaseBlob(name=patch["from"])
            except KeyError:
                fromRelease = None
            ftpFilename = self.get("ftpFilenames", {}).get(patchKey)
            bouncerProduct = self.get("bouncerProducts", {}).get(patchKey)

            if patch["from"] != "*" and fromRelease and not fromRelease.matchesUpdateQuery(updateQuery):
                continue

            url = self.getUrl(updateQuery, patch, specialForceHosts, ftpFilename, bouncerProduct)
            if containsForbiddenDomain(url, whitelistedDomains):
                forbidden = True
                break
            patches.append('        <patch type="%s" URL="%s" hashFunction="%s" hashValue="%s" size="%s"/>' % \
                (patchKey, url, self["hashFunction"], patch["hashValue"], patch["filesize"]))

        xml = ['<?xml version="1.0"?>']
        xml.append('<updates>')
        if not forbidden:
            xml.append(updateLine)
            xml.extend(patches)
            xml.append('    </update>')
        xml.append('</updates>')
        return xml

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


class ReleaseBlobV2(Blob, NewStyleVersionsMixin):
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

    def createSnippets(self, db, updateQuery, update_type, whitelistedDomains, specialForceHosts):
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
                fromRelease = db.releases.getReleaseBlob(name=patch["from"])
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

    def createXML(self, db, updateQuery, update_type, whitelistedDomains, specialForceHosts):
        # add tests before writing this
        xml = ['<?xml version="1.0"?>']
        xml.append('<updates>')
        xml.append('</updates>')
        return xml

class ReleaseBlobV3(Blob, NewStyleVersionsMixin):
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

    def createSnippets(self, db, updateQuery, update_type, whitelistedDomains, specialForceHosts):
        # does this even need to be implemented?
        return {}

    def createXML(self, db, updateQuery, update_type, whitelistedDomains, specialForceHosts):
        buildTarget = updateQuery["buildTarget"]
        locale = updateQuery["locale"]

        platformData = self.getPlatformData(buildTarget)
        localeData = platformData["locales"][locale]
        displayVersion = self.getDisplayVersion(buildTarget, locale)
        appVersion = self.getAppVersion(buildTarget, locale)
        platformVersion = self.getPlatformVersion(buildTarget, locale)
        buildid = self.getBuildID(buildTarget, locale)

        updateLine = '    <update type="%s" displayVersion="%s" appVersion="%s" platformVersion="%s" buildID="%s"' % \
            (update_type, displayVersion, appVersion, platformVersion, buildid)
        if "detailsUrl" in self:
            details = self["detailsUrl"].replace("%LOCALE%", updateQuery["locale"])
            updateLine += ' detailsURL="%s"' % details
        if "licenseUrl" in self:
            license = self["licenseUrl"].replace("%LOCALE%", updateQuery["locale"])
            updateLine += ' licenseURL="%s"' % license
        if "isOSUpdate" in self and self["isOSUpdate"]:
            updateLine += ' isOSUpdate="true"'
        updateLine += ">"

        patches = []
        forbidden = False
        for patchKey in ("partials", "completes"):
            for patch in localeData.get(patchKey):
                if not patch:
                    continue

                try:    
                    fromRelease = db.releases.getReleaseBlob(name=patch["from"])
                except KeyError:
                    fromRelease = None
                ftpFilename = self.get("ftpFilenames", {}).get(patchKey, {}).get(patch["from"])
                bouncerProduct = self.get("bouncerProducts", {}).get(patchKey, {}).get(patch["from"])

                if patch["from"] != "*" and fromRelease and not fromRelease.matchesUpdateQuery(updateQuery):
                    continue

                url = self.getUrl(updateQuery, patch, specialForceHosts, ftpFilename, bouncerProduct)
                if containsForbiddenDomain(url, whitelistedDomains):
                    forbidden = True
                    break
                patches.append('        <patch type="%s" URL="%s" hashFunction="%s" hashValue="%s" size="%s"/>' % \
                    # OMG HACK
                    (patchKey[:-1], url, self["hashFunction"], patch["hashValue"], patch["filesize"]))
                break

        xml = ['<?xml version="1.0"?>']
        xml.append('<updates>')
        if not forbidden:
            xml.append(updateLine)
            xml.extend(patches)
            xml.append('    </update>')
        xml.append('</updates>')
        return xml
