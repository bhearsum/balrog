import mock
import simplejson as json

from auslib.global_state import dbo
from auslib.test.admin.views.base import ViewTest


class TestUsersAPI_JSON(ViewTest):

    def testUsers(self):
        ret = self._get('/users')
        self.assertEqual(ret.status_code, 200)
        data = json.loads(ret.data)
        data['users'] = set(data['users'])
        self.assertEqual(data, dict(users=set(['bill', 'billy', 'bob', 'ashanti', 'mary'])))


class TestPermissionsAPI_JSON(ViewTest):

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

    def testPermissionPutWithEmptyOptions(self):
        ret = self._put('/users/bob/permissions/admin', data=dict(options=""))
        self.assertStatusCode(ret, 201)
        self.assertEqual(ret.data, json.dumps(dict(new_data_version=1)), "Data: %s" % ret.data)
        query = dbo.permissions.t.select()
        query = query.where(dbo.permissions.username == 'bob')
        query = query.where(dbo.permissions.permission == 'admin')
        self.assertEqual(query.execute().fetchone(), ('admin', 'bob', None, 1))

    def testPermissionPutWithEmail(self):
        ret = self._put('/users/bob@bobsworld.com/permissions/admin')
        self.assertStatusCode(ret, 201)
        self.assertEqual(ret.data, json.dumps(dict(new_data_version=1)), "Data: %s" % ret.data)
        query = dbo.permissions.t.select()
        query = query.where(dbo.permissions.username == 'bob@bobsworld.com')
        query = query.where(dbo.permissions.permission == 'admin')
        self.assertEqual(query.execute().fetchone(), ('admin', 'bob@bobsworld.com', None, 1))

    # This test is meant to verify that the app properly unquotes URL parts
    # as part of routing, because it is required when running under uwsgi.
    # Unfortunately, Werkzeug's test Client will unquote URL parts before
    # the app sees them, so this test doesn't actually verify that case...
    def testPermissionPutWithQuotedEmail(self):
        ret = self._put('/users/bob%40bobsworld.com/permissions/admin')
        self.assertStatusCode(ret, 201)
        self.assertEqual(ret.data, json.dumps(dict(new_data_version=1)), "Data: %s" % ret.data)
        query = dbo.permissions.t.select()
        query = query.where(dbo.permissions.username == 'bob@bobsworld.com')
        query = query.where(dbo.permissions.permission == 'admin')
        self.assertEqual(query.execute().fetchone(), ('admin', 'bob@bobsworld.com', None, 1))

    def testPermissionsPostWithHttpRemoteUser(self):
        ret = self._httpRemoteUserPost('/users/bill/permissions/admin', username="bob", data=dict(options="", data_version=1))
        self.assertEqual(ret.status_code, 200, "Status Code: %d" % ret.status_code)
        self.assertEqual(json.loads(ret.data), dict(new_data_version=2))
        r = dbo.permissions.t.select().where(dbo.permissions.username == 'bill').execute().fetchall()
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0], ('admin', 'bill', None, 2))

    def testPermissionsPost(self):
        ret = self._post('/users/bill/permissions/admin', data=dict(options="", data_version=1))
        self.assertEqual(ret.status_code, 200, "Status Code: %d" % ret.status_code)
        self.assertEqual(json.loads(ret.data), dict(new_data_version=2))
        r = dbo.permissions.t.select().where(dbo.permissions.username == 'bill').execute().fetchall()
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0], ('admin', 'bill', None, 2))

    def testPermissionsPostMissing(self):
        ret = self._post("/users/bill/permissions/rule", data=dict(options="", data_version=1))
        self.assertStatusCode(ret, 404)

    def testPermissionsPostBadInput(self):
        ret = self._post("/users/bill/permissions/admin")
        self.assertStatusCode(ret, 400)

    def testPermissionsPostWithoutPermission(self):
        ret = self._post("/users/bob/permissions/rule", username="shane", data=dict(data_version=1, options=json.dumps(dict(actions=["create"]))))
        self.assertStatusCode(ret, 403)

    def testPermissionUrl(self):
        ret = self._put('/users/cathy/permissions/release')
        self.assertStatusCode(ret, 201)
        self.assertEqual(ret.data, json.dumps(dict(new_data_version=1)), "Data: %s" % ret.data)
        query = dbo.permissions.t.select()
        query = query.where(dbo.permissions.username == 'cathy')
        query = query.where(dbo.permissions.permission == 'release')
        self.assertEqual(query.execute().fetchone(), ('release', 'cathy', None, 1))

    def testPermissionPutWithOption(self):
        ret = self._put('/users/bob/permissions/release_locale', data=dict(options=json.dumps(dict(products=['fake']))))
        self.assertStatusCode(ret, 201)
        self.assertEqual(ret.data, json.dumps(dict(new_data_version=1)), "Data: %s" % ret.data)
        query = dbo.permissions.t.select()
        query = query.where(dbo.permissions.username == 'bob')
        query = query.where(dbo.permissions.permission == 'release_locale')
        self.assertEqual(query.execute().fetchone(), ('release_locale', 'bob', dict(products=['fake']), 1))

    def testPermissionModify(self):
        ret = self._put('/users/bob/permissions/release',
                        data=dict(options=json.dumps(dict(products=['different'])), data_version=1))
        self.assertStatusCode(ret, 200)
        self.assertEqual(json.loads(ret.data), dict(new_data_version=2))
        query = dbo.permissions.t.select()
        query = query.where(dbo.permissions.username == 'bob')
        query = query.where(dbo.permissions.permission == 'release')
        self.assertEqual(query.execute().fetchone(), ('release', 'bob', dict(products=['different']), 2))

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
        ret = self._put("/users/ashanti/permissions/rule", data=dict(options='{"products":'))
        self.assertStatusCode(ret, 400)

    def testPermissionPutWithoutPermission(self):
        ret = self._put('/users/bob/permissions/admin', username="joseph")
        self.assertStatusCode(ret, 403)

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

    def testPermissionDeleteWithoutPermission(self):
        ret = self._delete("/users/bob/permissions/permission", qs=dict(data_version=1), username="anna")
        self.assertStatusCode(ret, 403)


class TestPermissionsScheduledChanges(ViewTest):
    maxDiff = 10000

    def setUp(self):
        super(TestPermissionsScheduledChanges, self).setUp()
        dbo.permissions.scheduled_changes.t.insert().execute(
            sc_id=1, scheduled_by="bill", change_type="insert", data_version=1, base_permission="rule", base_username="janet",
            base_options={"products": ["foo"]},
        )
        dbo.permissions.scheduled_changes.history.t.insert().execute(change_id=1, changed_by="bill", timestamp=20, sc_id=1)
        dbo.permissions.scheduled_changes.history.t.insert().execute(
            change_id=2, changed_by="bill", timestamp=21, sc_id=1, scheduled_by="bill", change_type="insert", data_version=1,
            base_permission="rule", base_username="janet", base_options={"products": ["foo"]},
        )
        dbo.permissions.scheduled_changes.signoffs.t.insert().execute(sc_id=1, username="bill", role="releng")
        dbo.permissions.scheduled_changes.conditions.t.insert().execute(sc_id=1, when=10000000, data_version=1)
        dbo.permissions.scheduled_changes.conditions.history.t.insert().execute(change_id=1, changed_by="bill", timestamp=20, sc_id=1)
        dbo.permissions.scheduled_changes.conditions.history.t.insert().execute(
            change_id=2, changed_by="bill", timestamp=21, sc_id=1, when=10000000, data_version=1
        )

        dbo.permissions.scheduled_changes.t.insert().execute(
            sc_id=2, scheduled_by="bill", change_type="update", data_version=1, base_permission="release_locale", base_username="ashanti",
            base_options=None, base_data_version=1,
        )
        dbo.permissions.scheduled_changes.history.t.insert().execute(change_id=3, changed_by="bill", timestamp=40, sc_id=2)
        dbo.permissions.scheduled_changes.history.t.insert().execute(
            change_id=4, changed_by="bill", timestamp=41, sc_id=2, scheduled_by="bill", change_type="update", data_version=1,
            base_permission="release_locale", base_username="ashanti", base_options=None, base_data_version=1
        )
        dbo.permissions.scheduled_changes.conditions.t.insert().execute(sc_id=2, when=20000000, data_version=1)
        dbo.permissions.scheduled_changes.conditions.history.t.insert().execute(change_id=3, changed_by="bill", timestamp=40, sc_id=2)
        dbo.permissions.scheduled_changes.conditions.history.t.insert().execute(
            change_id=4, changed_by="bill", timestamp=41, sc_id=2, when=20000000, data_version=1
        )

        dbo.permissions.scheduled_changes.t.insert().execute(
            sc_id=3, scheduled_by="bill", change_type="insert", data_version=2, base_permission="permission", base_username="bob", complete=True
        )
        dbo.permissions.scheduled_changes.history.t.insert().execute(change_id=5, changed_by="bill", timestamp=60, sc_id=3)
        dbo.permissions.scheduled_changes.history.t.insert().execute(
            change_id=6, changed_by="bill", timestamp=61, sc_id=3, scheduled_by="bill", change_type="insert", data_version=1,
            base_permission="permission", base_username="bob", complete=False,
        )
        dbo.permissions.scheduled_changes.history.t.insert().execute(
            change_id=7, changed_by="bill", timestamp=100, sc_id=3, scheduled_by="bill", change_type="insert", data_version=2,
            base_permission="permission", base_username="bob", complete=True,
        )
        dbo.permissions.scheduled_changes.conditions.t.insert().execute(sc_id=3, when=30000000, data_version=2)
        dbo.permissions.scheduled_changes.conditions.history.t.insert().execute(change_id=5, changed_by="bill", timestamp=60, sc_id=3)
        dbo.permissions.scheduled_changes.conditions.history.t.insert().execute(
            change_id=6, changed_by="bill", timestamp=61, sc_id=3, when=30000000, data_version=1
        )
        dbo.permissions.scheduled_changes.conditions.history.t.insert().execute(
            change_id=7, changed_by="bill", timestamp=100, sc_id=3, when=30000000, data_version=2
        )

    def testGetScheduledChanges(self):
        ret = self._get("/scheduled_changes/permissions")
        expected = {
            "count": 2,
            "scheduled_changes": [
                {
                    "sc_id": 1, "when": 10000000, "scheduled_by": "bill", "change_type": "insert", "complete": False, "sc_data_version": 1,
                    "permission": "rule", "username": "janet", "options": {"products": ["foo"]}, "data_version": None,
                    "signoffs": {"bill": "releng"},
                },
                {
                    "sc_id": 2, "when": 20000000, "scheduled_by": "bill", "change_type": "update", "complete": False, "sc_data_version": 1,
                    "permission": "release_locale", "username": "ashanti", "options": None, "data_version": 1, "signoffs": {},
                },
            ],
        }
        self.assertEquals(json.loads(ret.data), expected)

    def testGetScheduledChangesWithCompleted(self):
        ret = self._get("/scheduled_changes/permissions", qs={"all": 1})
        expected = {
            "count": 3,
            "scheduled_changes": [
                {
                    "sc_id": 1, "when": 10000000, "scheduled_by": "bill", "change_type": "insert", "complete": False, "sc_data_version": 1,
                    "permission": "rule", "username": "janet", "options": {"products": ["foo"]}, "data_version": None,
                    "signoffs": {"bill": "releng"},
                },
                {
                    "sc_id": 2, "when": 20000000, "scheduled_by": "bill", "change_type": "update", "complete": False, "sc_data_version": 1,
                    "permission": "release_locale", "username": "ashanti", "options": None, "data_version": 1, "signoffs": {},
                },
                {
                    "sc_id": 3, "when": 30000000, "scheduled_by": "bill", "change_type": "insert", "complete": True, "sc_data_version": 2,
                    "permission": "permission", "username": "bob", "options": None, "data_version": None, "signoffs": {},
                },
            ],
        }
        self.assertEquals(json.loads(ret.data), expected)

    @mock.patch("time.time", mock.MagicMock(return_value=300))
    def testAddScheduledChangeExistingPermission(self):
        data = {
            "when": 400000000, "permission": "rule", "username": "bob", "options": None, "data_version": 1, "change_type": "update",
        }
        ret = self._post("/scheduled_changes/permissions", data=data)
        self.assertEquals(ret.status_code, 200, ret.data)
        self.assertEquals(json.loads(ret.data), {"sc_id": 4})
        r = dbo.permissions.scheduled_changes.t.select().where(dbo.permissions.scheduled_changes.sc_id == 4).execute().fetchall()
        self.assertEquals(len(r), 1)
        db_data = dict(r[0])
        expected = {
            "sc_id": 4, "scheduled_by": "bill", "change_type": "update", "complete": False, "data_version": 1,
            "base_permission": "rule", "base_username": "bob", "base_options": None, "base_data_version": 1,
        }
        self.assertEquals(db_data, expected)
        cond = dbo.permissions.scheduled_changes.conditions.t.select().where(dbo.permissions.scheduled_changes.conditions.sc_id == 4).execute().fetchall()
        self.assertEquals(len(cond), 1)
        cond_expected = {"sc_id": 4, "data_version": 1, "when": 400000000}
        self.assertEquals(dict(cond[0]), cond_expected)

    @mock.patch("time.time", mock.MagicMock(return_value=300))
    def testAddScheduledChangeNewPermission(self):
        data = {
            "when": 400000000, "permission": "release", "username": "jill", "options": '{"products": ["a"]}', "change_type": "insert",
        }
        ret = self._post("/scheduled_changes/permissions", data=data)
        self.assertEquals(ret.status_code, 200, ret.data)
        self.assertEquals(json.loads(ret.data), {"sc_id": 4})
        r = dbo.permissions.scheduled_changes.t.select().where(dbo.permissions.scheduled_changes.sc_id == 4).execute().fetchall()
        self.assertEquals(len(r), 1)
        db_data = dict(r[0])
        db_data["base_options"] = db_data["base_options"]
        expected = {
            "sc_id": 4, "scheduled_by": "bill", "change_type": "insert", "complete": False, "data_version": 1,
            "base_permission": "release", "base_username": "jill", "base_options": {"products": ["a"]}, "base_data_version": None,
        }
        self.assertEquals(db_data, expected)
        cond = dbo.permissions.scheduled_changes.conditions.t.select().where(dbo.permissions.scheduled_changes.conditions.sc_id == 4).execute().fetchall()
        self.assertEquals(len(cond), 1)
        cond_expected = {"sc_id": 4, "data_version": 1, "when": 400000000}
        self.assertEquals(dict(cond[0]), cond_expected)

    @mock.patch("time.time", mock.MagicMock(return_value=300))
    def testAddScheduledChangeDeletePermission(self):
        data = {
            "when": 400000000, "permission": "build", "username": "ashanti", "change_type": "delete", "data_version": 1,
        }
        ret = self._post("/scheduled_changes/permissions", data=data)
        self.assertEquals(ret.status_code, 200, ret.data)
        self.assertEquals(json.loads(ret.data), {"sc_id": 4})
        r = dbo.permissions.scheduled_changes.t.select().where(dbo.permissions.scheduled_changes.sc_id == 4).execute().fetchall()
        self.assertEquals(len(r), 1)
        db_data = dict(r[0])
        expected = {
            "sc_id": 4, "scheduled_by": "bill", "change_type": "delete", "complete": False, "data_version": 1,
            "base_permission": "build", "base_username": "ashanti", "base_options": None, "base_data_version": 1,
        }
        self.assertEquals(db_data, expected)
        cond = dbo.permissions.scheduled_changes.conditions.t.select().where(dbo.permissions.scheduled_changes.conditions.sc_id == 4).execute().fetchall()
        self.assertEquals(len(cond), 1)
        cond_expected = {"sc_id": 4, "data_version": 1, "when": 400000000}
        self.assertEquals(dict(cond[0]), cond_expected)

    @mock.patch("time.time", mock.MagicMock(return_value=300))
    def testUpdateScheduledChangeExistingPermission(self):
        data = {
            "options": '{"products": ["Thunderbird"]}', "data_version": 1, "sc_data_version": 1, "when": 200000000,
        }
        ret = self._post("/scheduled_changes/permissions/2", data=data)
        self.assertEquals(ret.status_code, 200, ret.data)
        self.assertEquals(json.loads(ret.data), {"new_data_version": 2})

        r = dbo.permissions.scheduled_changes.t.select().where(dbo.permissions.scheduled_changes.sc_id == 2).execute().fetchall()
        self.assertEquals(len(r), 1)
        db_data = dict(r[0])
        db_data["base_options"] = db_data["base_options"]
        expected = {
            "sc_id": 2, "complete": False, "data_version": 2, "scheduled_by": "bill", "change_type": "update", "base_permission": "release_locale",
            "base_username": "ashanti", "base_options": {"products": ["Thunderbird"]}, "base_data_version": 1,
        }
        self.assertEquals(db_data, expected)
        cond = dbo.permissions.scheduled_changes.conditions.t.select().where(dbo.permissions.scheduled_changes.conditions.sc_id == 2).execute().fetchall()
        self.assertEquals(len(cond), 1)
        cond_expected = {"sc_id": 2, "data_version": 2, "when": 200000000}
        self.assertEquals(dict(cond[0]), cond_expected)

    @mock.patch("time.time", mock.MagicMock(return_value=300))
    def testUpdateScheduledChangeNewPermission(self):
        data = {
            "options": '{"products": ["Firefox"]}', "sc_data_version": 1, "when": 450000000,
        }
        ret = self._post("/scheduled_changes/permissions/1", data=data)
        self.assertEquals(ret.status_code, 200, ret.data)
        self.assertEquals(json.loads(ret.data), {"new_data_version": 2})

        r = dbo.permissions.scheduled_changes.t.select().where(dbo.permissions.scheduled_changes.sc_id == 1).execute().fetchall()
        self.assertEquals(len(r), 1)
        db_data = dict(r[0])
        db_data["base_options"] = db_data["base_options"]
        expected = {
            "sc_id": 1, "complete": False, "data_version": 2, "scheduled_by": "bill", "change_type": "insert", "base_permission": "rule",
            "base_username": "janet", "base_options": {"products": ["Firefox"]}, "base_data_version": None,
        }
        self.assertEquals(db_data, expected)
        cond = dbo.permissions.scheduled_changes.conditions.t.select().where(dbo.permissions.scheduled_changes.conditions.sc_id == 1).execute().fetchall()
        self.assertEquals(len(cond), 1)
        cond_expected = {"sc_id": 1, "data_version": 2, "when": 450000000}
        self.assertEquals(dict(cond[0]), cond_expected)

    def testDeleteScheduledChange(self):
        ret = self._delete("/scheduled_changes/permissions/1", qs={"data_version": 1})
        self.assertEquals(ret.status_code, 200, ret.data)
        got = dbo.permissions.scheduled_changes.t.select().where(dbo.permissions.scheduled_changes.sc_id == 1).execute().fetchall()
        self.assertEquals(got, [])
        cond_got = dbo.permissions.scheduled_changes.conditions.t.select().where(dbo.permissions.scheduled_changes.conditions.sc_id == 1).execute().fetchall()
        self.assertEquals(cond_got, [])

    def testEnactScheduledChangeExistingPermission(self):
        ret = self._post("/scheduled_changes/permissions/2/enact")
        self.assertEquals(ret.status_code, 200, ret.data)

        r = dbo.permissions.scheduled_changes.t.select().where(dbo.permissions.scheduled_changes.sc_id == 2).execute().fetchall()
        self.assertEquals(len(r), 1)
        db_data = dict(r[0])
        expected = {
            "sc_id": 2, "complete": True, "data_version": 2, "scheduled_by": "bill", "change_type": "update", "base_permission": "release_locale",
            "base_username": "ashanti", "base_options": None, "base_data_version": 1,
        }
        self.assertEquals(db_data, expected)

        base_row = dbo.permissions.t.select().where(dbo.permissions.username == "ashanti")\
                                             .where(dbo.permissions.permission == "release_locale")\
                                             .execute().fetchall()[0]
        base_expected = {
            "permission": "release_locale", "username": "ashanti", "options": None, "data_version": 2
        }
        self.assertEquals(dict(base_row), base_expected)

    def testEnactScheduledChangeNewPermission(self):
        ret = self._post("/scheduled_changes/permissions/1/enact")
        self.assertEquals(ret.status_code, 200, ret.data)

        r = dbo.permissions.scheduled_changes.t.select().where(dbo.permissions.scheduled_changes.sc_id == 1).execute().fetchall()
        self.assertEquals(len(r), 1)
        db_data = dict(r[0])
        db_data["base_options"] = db_data["base_options"]
        expected = {
            "sc_id": 1, "complete": True, "data_version": 2, "scheduled_by": "bill", "change_type": "insert", "base_permission": "rule",
            "base_username": "janet", "base_options": {"products": ["foo"]}, "base_data_version": None,
        }
        self.assertEquals(db_data, expected)

        base_row = dict(dbo.permissions.t.select().where(dbo.permissions.username == "janet")
                                                  .where(dbo.permissions.permission == "rule")
                                                  .execute().fetchall()[0])
        base_expected = {
            "permission": "rule", "username": "janet", "options": {"products": ["foo"]}, "data_version": 1
        }
        self.assertEquals(dict(base_row), base_expected)

    def testGetScheduledChangeHistoryRevisions(self):
        ret = self._get("/scheduled_changes/permissions/3/revisions")
        self.assertEquals(ret.status_code, 200, ret.data)
        expected = {
            "count": 2,
            "revisions": [
                {
                    "change_id": 7, "changed_by": "bill", "timestamp": 100, "sc_id": 3, "scheduled_by": "bill", "change_type": "insert",
                    "data_version": None, "permission": "permission", "username": "bob", "options": None, "when": 30000000, "complete": True,
                    "sc_data_version": 2,
                },
                {
                    "change_id": 6, "changed_by": "bill", "timestamp": 61, "sc_id": 3, "scheduled_by": "bill", "change_type": "insert",
                    "data_version": None, "permission": "permission", "username": "bob", "options": None, "when": 30000000, "complete": False,
                    "sc_data_version": 1,
                },
            ],
        }
        self.assertEquals(json.loads(ret.data), expected)

    def testSignoffWithPermission(self):
        ret = self._post("/scheduled_changes/permissions/2/signoffs", data=dict(role="qa"), username="bill")
        self.assertEquals(ret.status_code, 200, ret.data)
        r = dbo.permissions.scheduled_changes.signoffs.t.select().where(dbo.permissions.scheduled_changes.signoffs.sc_id == 2).execute().fetchall()
        self.assertEquals(len(r), 1)
        db_data = dict(r[0])
        self.assertEquals(db_data, {"sc_id": 2, "username": "bill", "role": "qa"})

    def testSignoffWithoutPermission(self):
        ret = self._post("/scheduled_changes/permissions/2/signoffs", data=dict(role="relman"), username="bill")
        self.assertEquals(ret.status_code, 403, ret.data)

    def testRevokeSignoff(self):
        ret = self._delete("/scheduled_changes/permissions/1/signoffs", username="bill")
        self.assertEquals(ret.status_code, 200, ret.data)
        r = dbo.permissions.scheduled_changes.signoffs.t.select().where(dbo.permissions.scheduled_changes.signoffs.sc_id == 1).execute().fetchall()
        self.assertEquals(len(r), 0)


class TestUserRolesAPI_JSON(ViewTest):

    def testGetRoles(self):
        ret = self._get("/users/bill/roles")
        self.assertStatusCode(ret, 200)
        got = set(json.loads(ret.data)["roles"])
        self.assertEquals(got, set(["releng", "qa"]))

    def testGetRolesMissingUserReturnsEmptyList(self):
        ret = self.client.get("/users/dean/roles")
        self.assertStatusCode(ret, 200)

    def testGrantRole(self):
        ret = self._put("/users/ashanti/roles/dev")
        self.assertStatusCode(ret, 201)
        self.assertEquals(ret.data, json.dumps(dict(new_data_version=1)), ret.data)
        got = dbo.permissions.user_roles.t.select().where(dbo.permissions.user_roles.username == "ashanti").execute().fetchall()
        self.assertEquals(got, [("ashanti", "dev", 1)])

    def testGrantExistingRole(self):
        ret = self._put("/users/bill/roles/releng")
        self.assertStatusCode(ret, 200)
        self.assertEquals(ret.data, json.dumps(dict(new_data_version=1)), ret.data)
        got = dbo.permissions.user_roles.t.select().where(dbo.permissions.user_roles.username == "bill").execute().fetchall()
        self.assertEquals(got, [("bill", "qa", 1), ("bill", "releng", 1)])

    def testGrantRoleWithoutPermission(self):
        ret = self._put("/users/emily/roles/relman", username="rory", data=dict(data_version=1))
        self.assertStatusCode(ret, 403)

    def testRevokeRole(self):
        ret = self._delete("/users/bob/roles/relman", qs=dict(data_version=1))
        self.assertStatusCode(ret, 200)
        got = dbo.permissions.user_roles.t.select().where(dbo.permissions.user_roles.username == "bob").execute().fetchall()
        self.assertEquals(got, [])

    def testRevokeRoleWithoutPermission(self):
        ret = self._delete("/users/bob/roles/relman", username="lane", qs=dict(data_version=1))
        self.assertStatusCode(ret, 403)

    def testRevokeRoleBadDataVersion(self):
        ret = self._delete("/users/bob/roles/relman", qs=dict(data_version=3))
        self.assertStatusCode(ret, 400)
