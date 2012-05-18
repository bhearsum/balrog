import mock
import simplejson as json

import flaskext.wtf.form

from auslib.web.base import app
from auslib.test.web.views.base import ViewTest, JSONTestMixin

class TestCSRFEndpoint(ViewTest, JSONTestMixin):
    def setUp(self):
        ViewTest.setUp(self)
        app.config['CSRF_ENABLED'] = True
        # Normally we'd just use mock.patch to do this, but it's not working
        # with this class for some reason....
        def g(self, x):
            return 111
        self.old_generate_csrf_token = flaskext.wtf.form.Form.generate_csrf_token
        flaskext.wtf.form.Form.generate_csrf_token = g

    def tearDown(self):
        flaskext.wtf.form.Form.generate_csrf_token = self.old_generate_csrf_token
        ViewTest.tearDown(self)

    def testCsrfGet(self):
        ret = self._get('/csrf_token')
        self.assertEquals(ret.status_code, 200)
        self.assertEquals(json.loads(ret.data), dict(csrf_token=111))
