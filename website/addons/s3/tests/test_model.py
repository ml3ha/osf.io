import mock
import unittest
from nose.tools import *

from tests.base import DbTestCase
from tests.factories import UserFactory, ProjectFactory

from website.addons.base import AddonError
from website.addons.s3 import settings as s3_settings
from website.addons.s3.model import AddonS3NodeSettings, AddonS3UserSettings

class TestCallbacks(DbTestCase):

    def setUp(self):

        super(TestCallbacks, self).setUp()

        self.project = ProjectFactory.build()
        self.non_authenticator = UserFactory()
        self.project.add_contributor(
            contributor=self.non_authenticator,
            user=self.project.creator,
        )
        self.project.save()

        self.project.add_addon('s3')
        self.project.creator.add_addon('s3')
        self.node_settings = self.project.get_addon('s3')
        self.user_settings = self.project.creator.get_addon('s3')
        self.user_settings.user_has_auth = 1
        self.node_settings.user_settings = self.user_settings
        self.node_settings.user = 'Queen'
        self.node_settings.s3_bucket = 'Sheer-Heart-Attack'
        self.node_settings.save()

    def test_something(self):
        assert_equals(1,1)

    def test_node_settings_empty_bucket(self):
        s3 = AddonS3NodeSettings()
        assert_equals(s3.to_json(self.project.creator)['has_bucket'], 0)

    def test_node_settings_full_bucket(self):
        s3 = AddonS3NodeSettings()
        s3.s3_bucket = 'bucket'
        assert_equals(s3.to_json(self.project.creator)['has_bucket'], 1)

    def test_node_settings_user_auth(self):
        s3 = AddonS3NodeSettings()
        assert_equals(s3.to_json(self.project.creator)['user_has_auth'], 1)

    def test_node_settings_moar_use(self):
        assert_equals(self.node_settings.to_json(self.project.creator)['user_has_auth'],1)
