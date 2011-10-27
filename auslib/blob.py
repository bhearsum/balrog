import simplejson as json

import logging
log = logging.getLogger(__name__)

CURRENT_SCHEMA_VERSION=1

def isValidBlob(format, blob):
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
    if not format:
        return True
    # If the blob isn't a dictionary-like object, it's not valid!
    if not hasattr(blob, 'keys') or not callable(blob.keys):
        return False
    for key in blob.keys():
        # A '*' key in the format means that all key names in the blob are accepted.
        if '*' in format:
            # But we still need to validate the sub-blob, if it exists.
            if format['*'] and not isValidBlob(format['*'], blob[key]):
                log.debug("blob is not valid because of key '%s'" % key)
                return False
        # If there's no '*' key, we need to make sure the key name is valid
        # and the sub-blob is valid, if it exists.
        elif key not in format or not isValidBlob(format[key], blob[key]):
            log.debug("blob is not valid because of key '%s'" % key)
            return False
    return True

class Blob(dict):
    """See isValidBlob for details on how format is used to validate blobs."""
    format = {}

    def isValid(self):
        """Decides whether or not this blob is valid based."""
        return isValidBlob(self.format, self)

    def loadJSON(self, data):
        """Replaces this blob's contents with parsed contents of the json
           string provided."""
        self.clear()
        self.update(json.loads(data))

    def getJSON(self):
        """Returns a JSON formatted version of this blob."""
        return json.dumps(self)

class ReleaseBlobV1(Blob):
    format = {
        'name': None,
        'schema_version': None,
        'detailsUrl': None,
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
        'fakePartials': None,
        'extv': None,
        'appv': None,
        'platforms': {
            '*': {
                'alias': None,
                'buildID': None,
                'OS_BOUNCER': None,
                'OS_FTP': None,
                'locales': {
                    '*': {
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

