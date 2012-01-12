import mock
import simplejson as json

from sqlalchemy import select

from auslib.web.base import db
from auslib.test.web.views.base import ViewTest, JSONTestMixin

class TestReleasesAPI_JSON(ViewTest, JSONTestMixin):
    def testLocalePut(self):
        details = json.dumps(dict(complete=dict(filesize=435)))
        ret = self._put('/releases/a/builds/p/l', data=dict(details=details, product='a', version='a'))
        self.assertStatusCode(ret, 201)
        ret = select([db.releases.data]).where(db.releases.name=='a').execute().fetchone()[0]
        self.assertEqual(json.loads(ret), json.loads("""
{
    "name": "a",
    "platforms": {
        "p": {
            "locales": {
                "l": {
                    "complete": {
                        "filesize": 435
                    }
                }
            }
        }
    }
}
"""))

    def testLocalePutAppend(self):
        details = json.dumps(dict(partial=dict(fileUrl='abc')))
        ret = self._put('/releases/d/builds/p/g', data=dict(details=details, product='d', version='d'))
        self.assertStatusCode(ret, 201)
        ret = select([db.releases.data]).where(db.releases.name=='d').execute().fetchone()[0]
        self.assertEqual(json.loads(ret), json.loads("""
{
    "name": "d",
    "platforms": {
        "p": {
            "locales": {
                "d": {
                    "complete": {
                        "filesize": 1234
                    }
                },
                "g": {
                    "partial": {
                        "fileUrl": "abc"
                    }
                }
            }
        }
    }
}
"""))

    def testLocalePutWithCopy(self):
        details = json.dumps(dict(partial=dict(filesize=123)))
        data = dict(details=details, product='a', version='a', copyTo=json.dumps(['ab']))
        ret = self._put('/releases/a/builds/p/l', data=data)
        self.assertStatusCode(ret, 201)
        ret = select([db.releases.data]).where(db.releases.name=='a').execute().fetchone()[0]
        self.assertEqual(json.loads(ret), json.loads("""
{
    "name": "a",
    "platforms": {
        "p": {
            "locales": {
                "l": {
                    "partial": {
                        "filesize": 123
                    }
                }
            }
        }
    }
}
"""))
        ret = select([db.releases.data]).where(db.releases.name=='ab').execute().fetchone()[0]
        self.assertEqual(json.loads(ret), json.loads("""
{
    "name": "ab",
    "platforms": {
        "p": {
            "locales": {
                "l": {
                    "partial": {
                        "filesize": 123
                    }
                }
            }
        }
    }
}
"""))

    def testLocalePutChangeVersion(self):
        ret = self._put('/releases/a/builds/p/l', data=dict(details="{}", product='a', version='b'))
        self.assertStatusCode(ret, 201)
        ret = select([db.releases.data]).where(db.releases.name=='a').execute().fetchone()[0]
        self.assertEqual(json.loads(ret), json.loads("""
{
    "name": "a",
    "platforms": {
        "p": {
            "locales": {
                "l": {
                }
            }
        }
    }
}
"""))
        newVersion = select([db.releases.version]).where(db.releases.name=='a').execute().fetchone()[0]
        self.assertEqual(newVersion, 'b')

    def testLocalePutRetry(self):
        # In order to test the retry logic we need to mock out the method used
        # to grab the current data_version. The first time through, it needs
        # to return the wrong one to trigger the retry logic. The second time
        # through it needs to return the correct one, to make sure retrying
        # results in success still.
        with mock.patch('auslib.web.base.db.releases.getReleases') as r:
            results = [[dict(data_version=1, product='a', version='a')], [dict(data_version=431, product='a', version='a')]]
            def se(*args, **kwargs):
                print results
                return results.pop()
            r.side_effect = se
            details = json.dumps(dict(complete=dict(filesize=435)))
            ret = self._put('/releases/a/builds/p/l', data=dict(details=details, product='a', version='a'))
            self.assertStatusCode(ret, 201)
            self.assertEqual(r.call_count, 2)
            ret = select([db.releases.data]).where(db.releases.name=='a').execute().fetchone()[0]
            self.assertEqual(json.loads(ret), json.loads("""
{
    "name": "a",
    "platforms": {
        "p": {
            "locales": {
                "l": {
                    "complete": {
                        "filesize": 435
                    }
                }
            }
        }
    }
}
"""))

    def testLocalePutBadJSON(self):
        ret = self._put('/releases/a/builds/p/l', data=dict(details='a', product='a', version='a'))
        self.assertStatusCode(ret, 400)

    def testLocaleGet(self):
        ret = self._get('/releases/d/builds/p/d')
        self.assertStatusCode(ret, 200)
        self.assertEqual(json.loads(ret.data), dict(complete=dict(filesize=1234)))

    def testLocalePutNotAllowed(self):
        ret = self.client.put('/releases/d/builds/p/d', data=dict(product='a'))
        self.assertStatusCode(ret, 401)

    def testLocalePutCantChangeProduct(self):
        details = json.dumps(dict(complete=dict(filesize=435)))
        ret = self._put('/releases/a/builds/p/l', data=dict(details=details, product='b', version='a'))
        self.assertStatusCode(ret, 400)

    def testLocaleRevertsPartialUpdate(self):
        details = json.dumps(dict(complete=dict(filesize=1)))
        with mock.patch('auslib.web.base.db.releases.addLocaleToRelease') as r:
            r.side_effect = Exception("Fail")
            ret = self._put('/releases/a/builds/p/l', data=dict(details=details, product='a', version='c'))
            self.assertStatusCode(ret, 500)
            ret = db.releases.t.select().where(db.releases.name=='a').execute().fetchone()
            self.assertEqual(ret['product'], 'a')
            self.assertEqual(ret['version'], 'a')
            self.assertEqual(json.loads(ret['data']), dict(name='a'))
