import simplejson as json

from auslib.global_state import dbo
from auslib.test.admin.views.base import ViewTest, JSONTestMixin


class TestPermissionsAPI_JSON(ViewTest, JSONTestMixin):

    def testUsers(self):
        ret = self._get('/users')
        self.assertEqual(ret.status_code, 200)
        data = json.loads(ret.data)
        data['users'] = set(data['users'])
        self.assertEqual(data, dict(users=set(['bill', 'bob', 'ashanti', 'mary'])))

    def testPermissionsCollection(self):
        ret = self._get('/users/bill/permissions')
        self.assertEqual(ret.status_code, 200)
        self.assertEqual(json.loads(ret.data), dict(admin=dict(options=None, data_version=1)))

    def testPermissionGet(self):
        ret = self._get('/users/bill/permissions/admin')
        self.assertEqual(ret.status_code, 200)
        self.assertEqual(json.loads(ret.data), dict(options=None, data_version=1))

    def testPermissionGetMissing(self):
        ret = self.client.get("/users/bill/permissions/rule")
        self.assertEqual(ret.status_code, 404)

    def testPermissionPut(self):
        ret = self._put('/users/bob/permissions/admin')
        self.assertStatusCode(ret, 201)
        self.assertEqual(ret.data, json.dumps(dict(new_data_version=1)), "Data: %s" % ret.data)
        query = dbo.permissions.t.select()
        query = query.where(dbo.permissions.username == 'bob')
        query = query.where(dbo.permissions.permission == 'admin')
        self.assertEqual(query.execute().fetchone(), ('admin', 'bob', None, 1))

    def testPermissionsPost(self):
        ret = self._post('/users/bill/permissions/admin', data=dict(options="", data_version=1))
        self.assertEqual(ret.status_code, 200, "Status Code: %d" % ret.status_code)
        self.assertEqual(ret.data, json.dumps(dict(new_data_version=2)), "Data: %s" % ret.data)
        r = dbo.permissions.t.select().where(dbo.permissions.username == 'bill').execute().fetchall()
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0], ('admin', 'bill', None, 2))

    def testPermissionsPostMissing(self):
        ret = self._post("/users/bill/permissions/rule", data=dict(options="", data_version=1))
        self.assertStatusCode(ret, 404)

    def testPermissionsPostBadInput(self):
        ret = self._post("/users/bill/permissions/admin")
        self.assertStatusCode(ret, 400)

    def testPermissionUrl(self):
        ret = self._put('/users/cathy/permissions/release')
        self.assertStatusCode(ret, 201)
        self.assertEqual(ret.data, json.dumps(dict(new_data_version=1)), "Data: %s" % ret.data)
        query = dbo.permissions.t.select()
        query = query.where(dbo.permissions.username == 'cathy')
        query = query.where(dbo.permissions.permission == 'release')
        self.assertEqual(query.execute().fetchone(), ('release', 'cathy', None, 1))

    def testPermissionPutWithOption(self):
        ret = self._put('/users/bob/permissions/build', data=dict(options=json.dumps(dict(products=['fake']))))
        self.assertStatusCode(ret, 201)
        self.assertEqual(ret.data, json.dumps(dict(new_data_version=1)), "Data: %s" % ret.data)
        query = dbo.permissions.t.select()
        query = query.where(dbo.permissions.username == 'bob')
        query = query.where(dbo.permissions.permission == 'build')
        self.assertEqual(query.execute().fetchone(), ('build', 'bob', json.dumps(dict(products=['fake'])), 1))

    def testPermissionModify(self):
        ret = self._put('/users/bob/permissions/release',
                        data=dict(options=json.dumps(dict(products=['different'])), data_version=1))
        self.assertStatusCode(ret, 200)
        self.assertEqual(ret.data, json.dumps(dict(new_data_version=2)), "Data: %s" % ret.data)
        query = dbo.permissions.t.select()
        query = query.where(dbo.permissions.username == 'bob')
        query = query.where(dbo.permissions.permission == 'release')
        self.assertEqual(query.execute().fetchone(), ('release', 'bob', json.dumps(dict(products=['different'])), 2))

    def testPermissionModifyWithoutDataVersion(self):
        ret = self._put("/users/bob/permissions/release",
                        data=dict(options=json.dumps(dict(products=["different"]))))
        self.assertStatusCode(ret, 400)

    def testPermissionPutBadPermission(self):
        ret = self._put('/users/bob/permissions/fake')
        self.assertStatusCode(ret, 400)

    def testPermissionPutBadOption(self):
        ret = self._put('/users/bob/permissions/admin', data=dict(options=json.dumps(dict(foo=2))))
        self.assertStatusCode(ret, 400)

    # Discovered in https://bugzilla.mozilla.org/show_bug.cgi?id=1237264
    def testPermissionPutBadJSON(self):
        ret = self._put("/users/bob/permissions/rule", data=dict(options='{"products":'))
        self.assertStatusCode(ret, 400)

    def testPermissionDelete(self):
        ret = self._delete('/users/bob/permissions/permission', qs=dict(data_version=1))
        self.assertStatusCode(ret, 200)
        query = dbo.permissions.t.select()
        query = query.where(dbo.permissions.username == 'bob')
        query = query.where(dbo.permissions.permission == 'permission')
        self.assertEqual(query.execute().fetchone(), None)

    def testPermissionDeleteMissing(self):
        ret = self._delete("/users/bill/permissions/release")
        self.assertStatusCode(ret, 404)

    def testPermissionDeleteBadInput(self):
        ret = self._delete("/users/bill/permissions/admin")
        self.assertStatusCode(ret, 400)
