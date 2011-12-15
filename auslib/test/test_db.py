import mock
import simplejson as json
from tempfile import NamedTemporaryFile
import unittest

from sqlalchemy import create_engine, MetaData, Table, Column, Integer, select
from sqlalchemy.engine.reflection import Inspector

from auslib.db import AUSDatabase, AUSTable, AlreadySetupError, PermissionDeniedError, \
  AUSTransaction, TransactionError, OutdatedDataError
from auslib.blob import ReleaseBlobV1

class MemoryDatabaseMixin(object):
    """Use this when writing tests that don't require multiple connections to
       the database."""
    def setUp(self):
        self.dburi = 'sqlite:///:memory:'

class NamedFileDatabaseMixin(object):
    """Use this when writing tests that *do* require multiple connections to
       the database. SQLite memory database don't support multiple connections
       to the same database. When you try to use them, you get weird behaviour
       like the second "connection" seeing the state of an in-progress
       transaction in the first. See the following links for more detail:
        http://www.sqlalchemy.org/docs/dialects/sqlite.html#threading-pooling-behavior
        http://www.sqlalchemy.org/trac/wiki/FAQ#IamusingmultipleconnectionswithaSQLitedatabasetypicallytotesttransactionoperationandmytestprogramisnotworking
       """
    def setUp(self):
        self.dburi = 'sqlite:///%s' % NamedTemporaryFile().name

class TestAUSTransaction(unittest.TestCase, MemoryDatabaseMixin):
    def setUp(self):
        MemoryDatabaseMixin.setUp(self)
        self.engine = create_engine(self.dburi)
        self.metadata = MetaData(self.engine)
        self.table = Table('test', self.metadata, Column('id', Integer, primary_key=True),
                                             Column('foo', Integer))
        self.metadata.create_all()
        self.table.insert().execute(id=1, foo=33)
        self.table.insert().execute(id=2, foo=22)
        self.table.insert().execute(id=3, foo=11)

    def testTransaction(self):
        trans = AUSTransaction(self.metadata.bind.connect())
        trans.execute(self.table.insert(values=dict(id=4, foo=55)))
        trans.execute(self.table.update(values=dict(foo=66)).where(self.table.c.id==1))
        trans.commit()
        ret = self.table.select().execute().fetchall()
        self.assertEquals(ret, [(1, 66), (2, 22), (3, 11), (4, 55)])

    def testTransactionRaisesOnError(self):
        trans = AUSTransaction(self.metadata.bind.connect())
        self.assertRaises(TransactionError, trans.execute, "UPDATE test SET foo=123 WHERE fake=1")

    def testRollback(self):
        trans = AUSTransaction(self.metadata.bind.connect())
        trans.execute(self.table.update(values=dict(foo=66)).where(self.table.c.id==1))
        trans.rollback()
        ret = self.table.select().execute().fetchall()
        self.assertEquals(ret, [(1, 33), (2, 22), (3, 11)])

class TestAUSTransactionRequiresRealFile(unittest.TestCase, NamedFileDatabaseMixin):
    def setUp(self):
        NamedFileDatabaseMixin.setUp(self)
        self.engine = create_engine(self.dburi)
        self.metadata = MetaData(self.engine)
        self.table = Table('test', self.metadata, Column('id', Integer, primary_key=True),
                                             Column('foo', Integer))
        self.metadata.create_all()
        self.table.insert().execute(id=1, foo=33)
        self.table.insert().execute(id=2, foo=22)
        self.table.insert().execute(id=3, foo=11)

    def testTransactionNotChangedUntilCommit(self):
        trans = AUSTransaction(self.metadata.bind.connect())
        trans.execute(self.table.update(values=dict(foo=66)).where(self.table.c.id==1))
        # This select() runs in a different connection, so no changes should
        # be visible to it yet
        ret = self.table.select().execute().fetchall()
        self.assertEquals(ret, [(1, 33), (2, 22), (3, 11)])
        trans.commit()
        ret = self.table.select().execute().fetchall()
        self.assertEquals(ret, [(1, 66), (2, 22), (3, 11)])

class TestTableMixin(object):
    def setUp(self):
        self.engine = create_engine(self.dburi)
        self.metadata = MetaData(self.engine)
        class TestTable(AUSTable):
            def __init__(self, metadata):
                self.table = Table('test', metadata, Column('id', Integer, primary_key=True),
                                                     Column('foo', Integer))
                AUSTable.__init__(self)
        self.test = TestTable(self.metadata)
        self.metadata.create_all()
        self.test.t.insert().execute(id=1, foo=33, data_version=1)
        self.test.t.insert().execute(id=2, foo=22, data_version=1)
        self.test.t.insert().execute(id=3, foo=11, data_version=2)

class TestAUSTable(unittest.TestCase, TestTableMixin, MemoryDatabaseMixin):
    def setUp(self):
        MemoryDatabaseMixin.setUp(self)
        TestTableMixin.setUp(self)

    def testColumnMirroring(self):
        self.assertTrue(self.test.id in self.test.table.get_children())
        self.assertTrue(self.test.foo in self.test.table.get_children())

    def testSelect(self):
        expected = [dict(id=1, foo=33, data_version=1),
                    dict(id=2, foo=22, data_version=1),
                    dict(id=3, foo=11, data_version=2)]
        self.assertEquals(self.test.select(), expected)

    def testSelectWithColumns(self):
        expected = [dict(id=1), dict(id=2), dict(id=3)]
        self.assertEquals(self.test.select(columns=[self.test.id]), expected)

    def testSelectWithWhere(self):
        expected = [dict(id=2, foo=22, data_version=1),
                    dict(id=3, foo=11, data_version=2)]
        self.assertEquals(self.test.select(where=[self.test.id >= 2]), expected)

    def testSelectWithOrder(self):
        expected = [dict(id=3, foo=11, data_version=2),
                    dict(id=2, foo=22, data_version=1),
                    dict(id=1, foo=33, data_version=1)]
        self.assertEquals(self.test.select(order_by=[self.test.foo]), expected)

    def testSelectWithLimit(self):
        self.assertEquals(self.test.select(limit=1), [dict(id=1, foo=33, data_version=1)])

    def testSelectCanModifyResult(self):
        ret = self.test.select()[0]
        # If we can't write to this, an Exception will be raised and the test will fail
        ret['foo'] = 3245

    def testInsert(self):
        self.test.insert(changed_by='bob', id=4, foo=0)
        ret = self.test.t.select().execute().fetchall()
        self.assertEquals(len(ret), 4)
        self.assertEquals(ret[-1], (4, 0, 1))

    def testDelete(self):
        ret = self.test.delete(changed_by='bill', where=[self.test.id==1, self.test.foo==33],
            old_data_version=1)
        self.assertEquals(ret.rowcount, 1)
        self.assertEquals(len(self.test.t.select().execute().fetchall()), 2)

    def testDeleteFailsOnVersionMismatch(self):
        self.assertRaises(OutdatedDataError, self.test.delete, changed_by='bill',
            where=[self.test.id==3], old_data_version=1)

    def testUpdate(self):
        ret = self.test.update(changed_by='bob', where=[self.test.id==1], what=dict(foo=123),
            old_data_version=1)
        self.assertEquals(ret.rowcount, 1)
        self.assertEquals(self.test.t.select(self.test.id==1).execute().fetchone(), (1, 123, 2))

    def testUpdateFailsOnVersionMismatch(self):
        self.assertRaises(OutdatedDataError, self.test.update, changed_by='bill',
            where=[self.test.id==3], what=dict(foo=99), old_data_version=1)

    def testWherePkMatches(self):
        expected = self.test.id==1
        res = self.test.wherePkMatches(dict(id=1))
        self.assertEquals(len(res), 1)
        self.assertTrue(self.test.wherePkMatches(dict(id=1))[0].compare(expected))

class TestAUSTableRequiresRealFile(unittest.TestCase, TestTableMixin, NamedFileDatabaseMixin):
    def setUp(self):
        NamedFileDatabaseMixin.setUp(self)
        TestTableMixin.setUp(self)

# TODO: Find some way of testing this with SQLite, or testing it with some other backend.
# Because it's impossible to have multiple simultaneous transaction with sqlite, you
# can't test the behaviour of concurrent transactions with it.
#    def testUpdateCollidingUpdateFails(self):
#        trans1 = AUSTransaction(self.test.getEngine().connect())
#        trans2 = AUSTransaction(self.test.getEngine().connect())
#        ret1 = self.test._prepareUpdate(trans1, where=[self.test.id==3], what=dict(foo=99), changed_by='bob')
#        ret2 = self.test._prepareUpdate(trans2, where=[self.test.id==3], what=dict(foo=66), changed_by='bob')
#        trans1.commit()
#        self.assertEquals(ret1.rowcount, 1)
#        self.assertEquals(self.test.t.select(self.test.id==3).execute().fetchone(), (1, 99, 2))
#        self.assertRaises(TransactionError, trans2.commit)

class TestHistoryTable(unittest.TestCase, TestTableMixin, MemoryDatabaseMixin):
    def setUp(self):
        MemoryDatabaseMixin.setUp(self)
        TestTableMixin.setUp(self)

    def testHasHistoryTable(self):
        self.assertTrue(self.test.history)

    def testHistoryTableHasAllColumns(self):
        columns = [c.name for c in self.test.history.t.get_children()]
        self.assertTrue('change_id' in columns)
        self.assertTrue('id' in columns)
        self.assertTrue('foo' in columns)
        self.assertTrue('changed_by' in columns)
        self.assertTrue('timestamp' in columns)

    def testHistoryUponInsert(self):
        with mock.patch('time.time') as t:
            t.return_value = 1.0
            self.test.insert(changed_by='george', id=4, foo=0)
            ret = self.test.history.t.select().execute().fetchall()
            self.assertEquals(ret, [(1, 'george', 999, 4, None, None),
                                    (2, 'george', 1000, 4, 0, 1)])

    def testHistoryUponDelete(self):
        with mock.patch('time.time') as t:
            t.return_value = 1.0
            self.test.delete(changed_by='bobby', where=[self.test.id==1],
                old_data_version=1)
            ret = self.test.history.t.select().execute().fetchone()
            self.assertEquals(ret, (1, 'bobby', 1000, 1, None, None))

    def testHistoryUponUpdate(self):
        with mock.patch('time.time') as t:
            t.return_value = 1.0
            self.test.update(changed_by='heather', where=[self.test.id==2], what=dict(foo=99),
                old_data_version=1)
            ret = self.test.history.t.select().execute().fetchone()
            self.assertEquals(ret, (1, 'heather', 1000, 2, 99, 2))

    def testHistoryTimestampMaintainsPrecision(self):
        with mock.patch('time.time') as t:
            t.return_value = 1234567890.123456
            self.test.insert(changed_by='bob', id=4)
            ret = select([self.test.history.timestamp]).where(self.test.history.id==4).execute().fetchone()[0]
            # Insert decrements the timestamp
            self.assertEquals(ret, 1234567890122)

class RulesTestMixin(object):
    def _stripNullColumns(self, rules):
        # We know a bunch of columns are going to be empty...easier to strip them out
        # than to be super verbose (also should let this test continue to work even
        # if the schema changes).
        for rule in rules:
            for key in rule.keys():
                if rule[key] == None:
                    del rule[key]
        return rules

class TestRulesSimple(unittest.TestCase, RulesTestMixin, MemoryDatabaseMixin):
    def setUp(self):
        MemoryDatabaseMixin.setUp(self)
        self.db = AUSDatabase(self.dburi)
        self.db.createTables()
        self.paths = self.db.rules
        self.paths.t.insert().execute(id=1, priority=100, version='3.5', buildTarget='d', throttle=100, mapping='c', update_type='z', data_version=1)
        self.paths.t.insert().execute(id=2, priority=100, version='3.3', buildTarget='d', throttle=100, mapping='b', update_type='z', data_version=1)
        self.paths.t.insert().execute(id=3, priority=100, version='3.5', buildTarget='a', throttle=100, mapping='a', update_type='z', data_version=1)
        self.paths.t.insert().execute(id=4, priority=80, buildTarget='d', throttle=100, mapping='a', update_type='z', data_version=1)
        self.paths.t.insert().execute(id=5, priority=80, buildTarget='d', version='3.3', throttle=0, mapping='c', update_type='z', data_version=1)

    def testGetOrderedRules(self):
        rules = self._stripNullColumns(self.paths.getOrderedRules())
        expected = [
            dict(rule_id=4, priority=80, throttle=100, buildTarget='d', mapping='a', update_type='z', data_version=1),
            dict(rule_id=5, priority=80, throttle=0, version='3.3', buildTarget='d', mapping='c', update_type='z', data_version=1),
            dict(rule_id=2, priority=100, throttle=100, version='3.3', buildTarget='d', mapping='b', update_type='z', data_version=1),
            dict(rule_id=3, priority=100, throttle=100, version='3.5', buildTarget='a', mapping='a', update_type='z', data_version=1),
            dict(rule_id=1, priority=100, throttle=100, version='3.5', buildTarget='d', mapping='c', update_type='z', data_version=1),
        ]
        self.assertEquals(rules, expected)

    def testGetRulesMatchingQuery(self):
        rules = self.paths.getRulesMatchingQuery(
            dict(name='', product='', version='3.5', channel='',
                 buildTarget='a', buildID='', locale='', osVersion='',
                 distribution='', distVersion='', headerArchitecture=''
            ),
            fallbackChannel=''
        )
        rules = self._stripNullColumns(rules)
        expected = [dict(rule_id=3, priority=100, throttle=100, version='3.5', buildTarget='a', mapping='a', update_type='z', data_version=1)]
        self.assertEquals(rules, expected)

    def testGetRulesMatchingQueryWithNullColumn(self):
        rules = self.paths.getRulesMatchingQuery(
            dict(name='', product='', version='3.5', channel='',
                 buildTarget='d', buildID='', locale='', osVersion='',
                 distribution='', distVersion='', headerArchitecture=''
            ),
            fallbackChannel=''
        )
        rules = self._stripNullColumns(rules)
        expected = [
            dict(rule_id=1, priority=100, throttle=100, version='3.5', buildTarget='d', mapping='c', update_type='z', data_version=1),
            dict(rule_id=4, priority=80, throttle=100, buildTarget='d', mapping='a', update_type='z', data_version=1),
        ]
        self.assertEquals(rules, expected)

    def testGetRulesMatchingQueryDontReturnThrottled(self):
        rules = self.paths.getRulesMatchingQuery(
            dict(name='', product='', version='3.3', channel='',
                 buildTarget='d', buildID='', locale='', osVersion='',
                 distribution='', distVersion='', headerArchitecture=''
            ),
            fallbackChannel=''
        )
        rules = self._stripNullColumns(rules)
        expected = [
            dict(rule_id=2, priority=100, throttle=100, version='3.3', buildTarget='d', mapping='b', update_type='z', data_version=1),
            dict(rule_id=4, priority=80, throttle=100, buildTarget='d', mapping='a', update_type='z', data_version=1),
        ]
        self.assertEquals(rules, expected)

class TestRulesSpecial(unittest.TestCase, RulesTestMixin, MemoryDatabaseMixin):
    def setUp(self):
        MemoryDatabaseMixin.setUp(self)
        self.db = AUSDatabase(self.dburi)
        self.db.createTables()
        self.rules = self.db.rules
        self.rules.t.insert().execute(id=1, priority=100, version='4.0*', throttle=100, update_type='z', data_version=1)
        self.rules.t.insert().execute(id=2, priority=100, channel='release*', throttle=100, update_type='z', data_version=1)

    def testGetRulesMatchingQueryVersionGlobbing(self):
        expected = [dict(rule_id=1, priority=100, throttle=100, version='4.0*', update_type='z', data_version=1)]
        rules = self.rules.getRulesMatchingQuery(
            dict(name='', product='', version='4.0', channel='',
                 buildTarget='', buildID='', locale='', osVersion='',
                 distribution='', distVersion='', headerArchitecture=''
            ),
            fallbackChannel=''
        )
        rules = self._stripNullColumns(rules)
        self.assertEquals(rules, expected)
        rules = self.rules.getRulesMatchingQuery(
            dict(name='', product='', version='4.0b2', channel='',
                 buildTarget='', buildID='', locale='', osVersion='',
                 distribution='', distVersion='', headerArchitecture=''
            ),
            fallbackChannel=''
        )
        rules = self._stripNullColumns(rules)
        self.assertEquals(rules, expected)
        rules = self.rules.getRulesMatchingQuery(
            dict(name='', product='', version='4.0.1', channel='',
                 buildTarget='', buildID='', locale='', osVersion='',
                 distribution='', distVersion='', headerArchitecture=''
            ),
            fallbackChannel=''
        )
        rules = self._stripNullColumns(rules)
        self.assertEquals(rules, expected)

    def testGetRulesMatchingQueryChannelGlobbing(self):
        expected = [dict(rule_id=2, priority=100, throttle=100, channel='release*', update_type='z', data_version=1)]
        rules = self.rules.getRulesMatchingQuery(
            dict(name='', product='', version='', channel='releasetest',
                 buildTarget='', buildID='', locale='', osVersion='', distribution='',
                 distVersion='', headerArchitecture=''
            ),
            fallbackChannel='releasetest'
        )
        rules = self._stripNullColumns(rules)
        self.assertEquals(rules, expected)
        rules = self.rules.getRulesMatchingQuery(
            dict(name='', product='', version='', channel='releasetest-cck-blah',
                 buildTarget='', buildID='', locale='', osVersion='',
                 distribution='', distVersion='', headerArchitecture=''
            ),
            fallbackChannel='releasetest'
        )
        rules = self._stripNullColumns(rules)
        self.assertEquals(rules, expected)

class TestReleases(unittest.TestCase, MemoryDatabaseMixin):
    def setUp(self):
        MemoryDatabaseMixin.setUp(self)
        self.db = AUSDatabase(self.dburi)
        self.db.createTables()
        self.releases = self.db.releases
        self.releases.t.insert().execute(name='a', product='a', version='a', data=json.dumps(dict(name=1)), data_version=1)
        self.releases.t.insert().execute(name='ab', product='a', version='a', data=json.dumps(dict(name=1)), data_version=1)
        self.releases.t.insert().execute(name='b', product='b', version='b', data=json.dumps(dict(name=2)), data_version=1)
        self.releases.t.insert().execute(name='c', product='c', version='c', data=json.dumps(dict(name=3)), data_version=1)

    def testGetReleases(self):
        self.assertEquals(len(self.releases.getReleases()), 4)

    def testGetReleasesWithLimit(self):
        self.assertEquals(len(self.releases.getReleases(limit=1)), 1)

    def testGetReleasesWithWhere(self):
        expected = [dict(product='b', version='b', name='b', data=dict(name=2), data_version=1)]
        self.assertEquals(self.releases.getReleases(name='b'), expected)

    def testGetReleaseBlob(self):
        expected = dict(name=3)
        self.assertEquals(self.releases.getReleaseBlob(name='c'), expected)

    def testGetReleaseBlobNonExistentRelease(self):
        self.assertRaises(KeyError, self.releases.getReleaseBlob, name='z')

    def testAddRelease(self):
        blob = ReleaseBlobV1(name=4)
        self.releases.addRelease(name='d', product='d', version='d', blob=blob, changed_by='bill')
        expected = [('d', 'd', 'd', json.dumps(dict(name=4)), 1)]
        self.assertEquals(self.releases.t.select().where(self.releases.name=='d').execute().fetchall(), expected)

    def testAddReleaseAlreadyExists(self):
        blob = ReleaseBlobV1(name=1)
        self.assertRaises(TransactionError, self.releases.addRelease, name='a', product='a', version='a', blob=blob, changed_by='bill')

    def testUpdateRelease(self):
        self.releases.updateRelease(name='b', product='z', version='y', changed_by='bill', old_data_version=1)
        expected = [('b', 'z', 'y', json.dumps(dict(name=2)), 2)]
        self.assertEquals(self.releases.t.select().where(self.releases.name=='b').execute().fetchall(), expected)

class TestReleasesSchema1(unittest.TestCase, MemoryDatabaseMixin):
    """Tests for the Releases class that depend on version 1 of the blob schema."""
    def setUp(self):
        MemoryDatabaseMixin.setUp(self)
        self.db = AUSDatabase(self.dburi)
        self.db.createTables()
        self.releases = self.db.releases
        self.releases.t.insert().execute(name='a', product='a', version='a', data_version=1, data="""
{
    "name": "a",
    "platforms": {
        "p": {
            "locales": {
                "l": {
                    "complete": {
                        "filesize": "1234"
                    }
                }
            }
        }
    }
}
""")
        self.releases.t.insert().execute(name='b', product='b', version='b', data_version=1, data="""
{
    "name": "b"
}
""")

    def testAddLocaleToRelease(self):
        blob = dict(complete=dict(hashValue='abc'))
        self.releases.addLocaleToRelease(name='a', platform='p', locale='c', blob=blob, old_data_version=1, changed_by='bill')
        ret = json.loads(select([self.releases.data]).where(self.releases.name=='a').execute().fetchone()[0])
        expected = json.loads("""
{
    "name": "a",
    "platforms": {
        "p": {
            "locales": {
                "c": {
                    "complete": {
                        "hashValue": "abc"
                    }
                },
                "l": {
                    "complete": {
                        "filesize": "1234"
                    }
                }
            }
        }
    }
}
""")
        self.assertEqual(ret, expected)

    def testAddLocaleToReleaseOverride(self):
        blob = dict(complete=dict(hashValue=789))
        self.releases.addLocaleToRelease(name='a', platform='p', locale='l', blob=blob, old_data_version=1, changed_by='bill')
        ret = json.loads(select([self.releases.data]).where(self.releases.name=='a').execute().fetchone()[0])
        expected = json.loads("""
{
    "name": "a",
    "platforms": {
        "p": {
            "locales": {
                "l": {
                    "complete": {
                        "hashValue": 789
                    }
                }
            }
        }
    }
}
""")
        self.assertEqual(ret, expected)

    def testAddLocaleToReleasePlatformsDoesntExist(self):
        blob = dict(complete=dict(filesize=432))
        self.releases.addLocaleToRelease(name='b', platform='q', locale='l', blob=blob, old_data_version=1, changed_by='bill')
        ret = json.loads(select([self.releases.data]).where(self.releases.name=='b').execute().fetchone()[0])
        expected = json.loads("""
{
    "name": "b",
    "platforms": {
        "q": {
            "locales": {
                "l": {
                    "complete": {
                        "filesize": 432
                    }
                }
            }
        }
    }
}
""")
        self.assertEqual(ret, expected)

class TestPermissions(unittest.TestCase, MemoryDatabaseMixin):
    def setUp(self):
        MemoryDatabaseMixin.setUp(self)
        self.db = AUSDatabase(self.dburi)
        self.db.createTables()
        self.permissions = self.db.permissions
        self.permissions.t.insert().execute(permission='admin', username='bill', data_version=1)
        self.permissions.t.insert().execute(permission='/users/:id/permissions/:permission', username='bob', data_version=1)
        self.permissions.t.insert().execute(permission='/releases/:name', username='bob', options=json.dumps(dict(product='fake')), data_version=1)
        self.permissions.t.insert().execute(permission='/rules', username='cathy', data_version=1)
        self.permissions.t.insert().execute(permission='/rules/:id', username='bob', options=json.dumps(dict(method='POST')), data_version=1)

    def testGrantPermissions(self):
        query = self.permissions.t.select().where(self.permissions.username=='jess')
        self.assertEquals(len(query.execute().fetchall()), 0)
        self.permissions.grantPermission('bob', 'jess', '/rules/:id')
        self.assertEquals(query.execute().fetchall(), [('/rules/:id', 'jess', None, 1)])

    def testGrantPermissionsWithOptions(self):
        self.permissions.grantPermission('bob', 'cathy', '/releases/:name', options=dict(product='SeaMonkey'))
        query = self.permissions.t.select().where(self.permissions.username=='cathy')
        query = query.where(self.permissions.permission=='/releases/:name')
        self.assertEquals(query.execute().fetchall(), [('/releases/:name', 'cathy', json.dumps(dict(product='SeaMonkey')), 1)])

    def testGrantPermissionsNotAllowed(self):
        self.assertRaises(PermissionDeniedError, self.permissions.grantPermission,
            'cathy', 'bob', '/rules/:id'
        )

    def testGrantPermissionsUnknownPermission(self):
        self.assertRaises(ValueError, self.permissions.grantPermission,
            'bob', 'bud', 'bad'
        )

    def testGrantPermissionsUnknownOption(self):
        self.assertRaises(ValueError, self.permissions.grantPermission,
            'bob', 'bud', '/rules/:id', dict(foo=1)
        )
    def testRevokePermission(self):
        self.permissions.revokePermission(changed_by='bill', username='bob', permission='/releases/:name',
            old_data_version=1)
        query = self.permissions.t.select().where(self.permissions.username=='bob')
        query = query.where(self.permissions.permission=='/releases/:name')
        self.assertEquals(len(query.execute().fetchall()), 0)

    def testCanEditUsers(self):
        self.assertTrue(self.permissions.canEditUsers('bill'))
        self.assertTrue(self.permissions.canEditUsers('bob'))

    def testCanEditUsersFalse(self):
        self.assertFalse(self.permissions.canEditUsers('cathy'))

    def testGetAllUsers(self):
        self.assertEquals(self.permissions.getAllUsers(), ['bill', 'bob', 'cathy'])

    def testGetUserPermissions(self):
        expected = {'/users/:id/permissions/:permission': dict(options=None, data_version=1),
                    '/releases/:name': dict(options=dict(product='fake'), data_version=1),
                    '/rules/:id': dict(options=dict(method='POST'), data_version=1)}
        self.assertEquals(self.permissions.getUserPermissions('bob'), expected)

    def testGetOptions(self):
        expected = dict(product='fake')
        self.assertEquals(self.permissions.getOptions('bob', '/releases/:name'), expected)

    def testGetOptionsPermissionDoesntExist(self):
        self.assertRaises(ValueError, self.permissions.getOptions, 'fake', 'fake')

    def testGetOptionsNoOptions(self):
        self.assertEquals(self.permissions.getOptions('cathy', '/rules'), {})

    def testHasUrlPermission(self):
        self.assertTrue(self.permissions.hasUrlPermission('cathy', '/rules', 'PUT', dict(product='fake')))

    def testHasUrlPermissionWithOption(self):
        self.assertTrue(self.permissions.hasUrlPermission('bob', '/rules/:id', 'POST', dict(product='fake')))

    def testHasUrlPermissionNotAllowed(self):
        self.assertFalse(self.permissions.hasUrlPermission('cathy', '/rules/:id', 'DELETE', dict(product='fake')))

    def testHasUrlPermissionNotAllowedWithOption(self):
        self.assertFalse(self.permissions.hasUrlPermission('bob', '/rules/:id', 'DELETE', dict(product='fake')))

    def testHasUrlPermissionWithProduct(self):
        self.assertTrue(self.permissions.hasUrlPermission('bob', '/releases/:name', 'DELETE', dict(product='fake')))

class TestDB(unittest.TestCase):
    def testCreateTables(self):
        db = AUSDatabase()
        db.setDburi('sqlite:///:memory:')
        db.createTables()
        insp = Inspector.from_engine(db.engine)
        self.assertNotEqual(insp.get_table_names(), [])

    def testSetDburiAlreadySetup(self):
        db = AUSDatabase('sqlite:///:memory:')
        self.assertRaises(AlreadySetupError, db.setDburi, 'sqlite:///:memory:')

    def testReset(self):
        db = AUSDatabase('sqlite:///:memory:')
        db.reset()
        # If we can set the dburi again, reset worked!
        db.setDburi('sqlite:///:memory:')
        db.createTables()
        insp = Inspector.from_engine(db.engine)
        self.assertNotEqual(insp.get_table_names(), [])
