# Copyright 2016 Canonical Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import absolute_import
from __future__ import print_function

import mock

import charm.openstack.manila_generic as manila_generic

import charms_openstack.test_utils as test_utils


class Helper(test_utils.PatchHelper):

    def setUp(self):
        super().setUp()
        self.patch_release(manila_generic.ManilaGenericCharm.release)


class TestManilaGenericCharmConfigProperties(Helper):

    def test_computed_use_password(self):
        config = mock.MagicMock()
        # test no passowrd or driver_auth_type configured
        config.driver_service_instance_password = None
        config.driver_auth_type = None
        self.assertFalse(manila_generic.computed_use_password(config))
        # test with the password but no auth type configured.
        config.driver_service_instance_password = 'hello'
        self.assertFalse(manila_generic.computed_use_password(config))
        # test with a driver password, and a configured string, but not
        # password or both.
        config.driver_auth_type = 'goodbye'
        self.assertFalse(manila_generic.computed_use_password(config))
        # test with 'password'
        config.driver_auth_type = 'Password'
        self.assertTrue(manila_generic.computed_use_password(config))
        # test with 'BOTH'
        config.driver_auth_type = 'BOTH'
        self.assertTrue(manila_generic.computed_use_password(config))
        # now test without the password again.
        config.driver_service_instance_password = None
        self.assertFalse(manila_generic.computed_use_password(config))

    def test_computed_use_ssh(self):
        config = mock.MagicMock()
        # test that not being configured returns false.
        config.driver_auth_type = None
        self.assertFalse(manila_generic.computed_use_ssh(config))
        # check that being either ssh or 'both' in upper/lower gives true
        config.driver_auth_type = 'Ssh'
        self.assertTrue(manila_generic.computed_use_ssh(config))
        config.driver_auth_type = 'BOTH'
        self.assertTrue(manila_generic.computed_use_ssh(config))
        config.driver_auth_type = 'both'
        self.assertTrue(manila_generic.computed_use_ssh(config))

    def test_computed_define_ssh(self):
        config = mock.MagicMock()
        config.driver_service_ssh_key = None
        config.driver_service_ssh_key_public = None
        # test that function only returns true if both config items are set
        self.assertFalse(manila_generic.computed_define_ssh(config))
        config.driver_service_ssh_key = "ssh key"
        config.driver_service_ssh_key_public = None
        self.assertFalse(manila_generic.computed_define_ssh(config))
        config.driver_service_ssh_key = None
        config.driver_service_ssh_key_public = "ssh public key"
        self.assertFalse(manila_generic.computed_define_ssh(config))
        config.driver_service_ssh_key = "ssh key"
        config.driver_service_ssh_key_public = "ssh public key"
        self.assertTrue(manila_generic.computed_define_ssh(config))

    def test_computed_debug_level(self):
        config = mock.MagicMock()
        config.debug = False
        config.verbose = False
        self.assertEqual(manila_generic.computed_debug_level(config), "NONE")
        config.verbose = True
        self.assertEqual(manila_generic.computed_debug_level(config), "NONE")
        config.debug = True
        config.verbose = False
        self.assertEqual(
            manila_generic.computed_debug_level(config), "WARNING")
        config.verbose = True
        self.assertEqual(manila_generic.computed_debug_level(config), "DEBUG")


class TestManilaGenericCharm(Helper):

    def _patch_config_and_charm(self, config):
        self.patch('charmhelpers.core.hookenv.config', name='config')

        def cf(key=None):
            if key is not None:
                return config[key]
            return config

        self.config.side_effect = cf

    def test_custom_assess_status_check(self):
        config = {
            'driver-handles-share-servers': False,
            'driver-service-image-name': '',
            'driver-service-instance-user': '',
            'driver-service-instance-flavor-id': '',
            'driver-service-instance-password': '',
            'driver-keypair-name': '',
        }
        self._patch_config_and_charm(config)
        c = manila_generic.ManilaGenericCharm()
        self.assertEqual(c.custom_assess_status_check(), (None, None))
        config['driver-handles-share-servers'] = True
        c = manila_generic.ManilaGenericCharm()
        self.assertEqual(c.custom_assess_status_check(),
                         ('blocked', "Missing 'driver-service-image-name'"))
        config['driver-service-image-name'] = 'image-name'
        c = manila_generic.ManilaGenericCharm()
        self.assertEqual(c.custom_assess_status_check(),
                         ('blocked', "Missing 'driver-service-instance-user'"))
        config['driver-service-instance-user'] = 'manila'
        c = manila_generic.ManilaGenericCharm()
        self.assertEqual(
            c.custom_assess_status_check(),
            ('blocked', "Missing 'driver-service-instance-flavor-id'"))
        config['driver-service-instance-flavor-id'] = '100'
        c = manila_generic.ManilaGenericCharm()
        self.assertEqual(
            c.custom_assess_status_check(),
            ('blocked',
             "Need at least one of instance password or keypair name"))
        config['driver-service-instance-password'] = 'password'
        c = manila_generic.ManilaGenericCharm()
        self.assertEqual(c.custom_assess_status_check(), (None, None))
        config['driver-service-instance-password'] = ''
        config['driver-keypair-name'] = 'keyname'
        c = manila_generic.ManilaGenericCharm()
        self.assertEqual(c.custom_assess_status_check(), (None, None))
        config['driver-service-instance-password'] = 'password'
        config['driver-keypair-name'] = 'keyname'
        c = manila_generic.ManilaGenericCharm()
        self.assertEqual(c.custom_assess_status_check(), (None, None))

    def test_get_config_for_principal(self):
        # note that this indirectly tests 'process_lines' as well.
        c = manila_generic.ManilaGenericCharm()
        self.assertEqual(
            c.get_config_for_principal(None),
            {'complete': False, 'reason': 'No authentication data'})
        # we want to handle share servers to True to check for misconfig
        config = {
            'driver-handles-share-servers': True,
            'driver-service-image-name': '',
            'driver-service-instance-user': '',
            'driver-service-instance-flavor-id': '',
            'driver-service-instance-password': '',
            'driver-keypair-name': '',
            'share-backend-name': '',
            'driver-auth-type': '',
            'driver-connect-share-server-to-tenant-network': False,
        }
        self._patch_config_and_charm(config)
        c = manila_generic.ManilaGenericCharm()
        state, message = c.custom_assess_status_check()
        auth_data = {
            'username': 'user',
            'password': 'pass',
            'project_domain_id': 'pd1',
            'project_name': 'p1',
            'user_domain_id': 'ud1',
            'auth_uri': 'uri1',
            'auth_url': 'url1',
            'auth_type': 'type1',
        }
        self.maxDiff = None
        self.assertEqual(
            c.get_config_for_principal(auth_data),
            {'complete': False, 'reason': message})
        # now set up the config to be okay to generate the sections
        config['driver-handles-share-servers'] = True
        config['driver-service-image-name'] = 'manila'
        config['driver-service-instance-user'] = 'manila-user'
        config['driver-service-instance-flavor-id'] = '103'
        config['driver-service-instance-password'] = 'password'
        config['driver-keypair-name'] = 'my-keyname'
        # test that we've set the backend name
        c = manila_generic.ManilaGenericCharm()
        self.assertEqual(
            c.get_config_for_principal(auth_data),
            {'complete': False, 'reason':
             'Problem: share-backend-name is not set'})
        # now test that we actually generate some config data
        config['share-backend-name'] = 'test-backend'
        # simplify the output for the next test
        config['driver-handles-share-servers'] = False
        c = manila_generic.ManilaGenericCharm()
        lines = c.get_config_for_principal(auth_data)
        # verify that "# No generic password section" is in the lines
        conf = manila_generic.MANILA_CONF
        self.assertIn(conf, lines)
        self.assertIn('[test-backend]', lines[conf])
        section = lines[conf]['[test-backend]']
        self.assertIn('share_driver = '
                      'manila.share.drivers.generic.GenericShareDriver',
                      section)
        self.assertIn('driver_handles_share_servers = False', section)
        self.assertIn('share_backend_name = test-backend', section)

        # Now verify that when we switch the driver handles shares on that the
        # sections all appear
        config['driver-handles-share-servers'] = True
        c = manila_generic.ManilaGenericCharm()
        lines = c.get_config_for_principal(auth_data)
        self.assertIn(conf, lines)
        self.assertIn('[test-backend]', lines[conf])
        self.assertIn('[nova]', lines[conf])
        self.assertIn('[neutron]', lines[conf])
        self.assertIn('[cinder]', lines[conf])
        # check each of the nova, neutron and cinder sections (which are all
        # identical)
        auth_lines = ['# Only needed for the generic drivers as of Mitaka',
                      'username = user',
                      'password = pass',
                      'project_domain_id = pd1',
                      'project_name = p1',
                      'user_domain_id = ud1',
                      'auth_uri = uri1',
                      'auth_url = url1',
                      'auth_type = type1']

        for s in ('[nova]', '[neutron]', '[cinder]'):
            section = lines[conf][s]
            self._verify_section_contains(section, auth_lines)

        # now check the [test-backend] section
        section = lines[conf]['[test-backend]']
        self.assertIn('share_driver = '
                      'manila.share.drivers.generic.GenericShareDriver',
                      section)
        self.assertIn('driver_handles_share_servers = True', section)
        self.assertIn('share_backend_name = test-backend', section)
        self.assertIn('service_instance_flavor_id = 103', section)
        self._verify_section_contains(
            section,
            ['service_instance_user = manila-user',
             'service_image_name = manila',
             'connect_share_server_to_tenant_network = False'])
        self._verify_section_contains(
            section,
            ['# No generic password section',
             '# No ssh section', ])

        # Now switch on the password section
        config['driver-auth-type'] = 'password'
        c = manila_generic.ManilaGenericCharm()
        lines = c.get_config_for_principal(auth_data)
        section = lines[conf]['[test-backend]']
        self.assertNotIn('# No generic password section', section)
        self.assertIn('service_instance_password = password', section)

        # Now switch on the SSH section
        config['driver_service_ssh_key'] = 'ssh-key'
        config['driver-service-ssh-key-public'] = 'ssh-key-public'
        config['driver-auth-type'] = 'ssh'
        c = manila_generic.ManilaGenericCharm()
        lines = c.get_config_for_principal(auth_data)
        section = lines[conf]['[test-backend]']
        self.assertNotIn('# No ssh section', section)
        self.assertIn('# No generic password section', section)
        # test for ssh lines
        self._verify_section_contains(
            section,
            ['path_to_private_key = {}'
             .format(manila_generic.MANILA_SSH_KEY_PATH),
             'path_to_public_key = {}'
             .format(manila_generic.MANILA_SSH_KEY_PATH_PUBLIC),
             'manila_service_keypair_name = my-keyname', ])

        # Enable the connect_share_to_tenant_network and both password and ssh
        config['driver-auth-type'] = 'both'
        config['driver-connect-share-server-to-tenant-network'] = True
        c = manila_generic.ManilaGenericCharm()
        lines = c.get_config_for_principal(auth_data)
        section = lines[conf]['[test-backend]']
        self.assertNotIn('# No ssh section', section)
        self.assertNotIn('# No generic password section', section)
        self.assertIn('service_instance_password = password', section)
        # test for ssh lines
        self._verify_section_contains(
            section,
            ['path_to_private_key = {}'
             .format(manila_generic.MANILA_SSH_KEY_PATH),
             'path_to_public_key = {}'
             .format(manila_generic.MANILA_SSH_KEY_PATH_PUBLIC),
             'manila_service_keypair_name = my-keyname', ])
        self.assertIn('connect_share_server_to_tenant_network = True', section)

    def _verify_section_contains(self, section, lines):
        index = section.index(lines[0])
        for i, line in enumerate(lines):
            self.assertEqual(section[index + i], line)

    def test_maybe_write_ssh_keys(self):
        config = {
            'driver-keypair-name': '',
            'driver-auth-type': '',
            'driver-service-ssh-key': '',
            'driver-service-ssh-key-public': ''
        }
        self._patch_config_and_charm(config)
        c = manila_generic.ManilaGenericCharm()
        # The 'maybe_write_ssh_keys' should attempt to delete two files
        self.patch_object(manila_generic.os, 'remove')
        c.maybe_write_ssh_keys()
        self.assertEqual(self.remove.call_count, 2)
        print(self.remove.call_args_list)
        self.assertEqual(self.remove.call_args_list, [
                         mock.call(manila_generic.MANILA_SSH_KEY_PATH),
                         mock.call(manila_generic.MANILA_SSH_KEY_PATH_PUBLIC)])
        # now configure it up and check the writes happen
        config['driver-keypair-name'] = 'mykeypair'
        config['driver-auth-type'] = 'both'
        config['driver-service-ssh-key'] = 'this is my key'
        config['driver-service-ssh-key-public'] = 'my public key'
        c = manila_generic.ManilaGenericCharm()
        self.patch_object(manila_generic, 'write_file')
        c.maybe_write_ssh_keys()
        self.assertEqual(self.write_file.call_count, 2)
        self.write_file.assert_has_calls(
            [mock.call('this is my key', manila_generic.MANILA_SSH_KEY_PATH),
             mock.call('my public key',
                       manila_generic.MANILA_SSH_KEY_PATH_PUBLIC,
                       0o644)])


class TestAuxilaryFunctions(Helper):

    def test_write_file(self):
        f = mock.MagicMock()
        self.patch_object(manila_generic.os, 'fdopen', return_value=f)
        self.patch_object(manila_generic.os, 'open', return_value='opener')
        text = """
            This
            One"""
        # strip the first new line off when passing the test string through
        # this is to test dedenting strings
        manila_generic.write_file(text[1:], 'file1')
        self.open.assert_called_once_with(
            'file1',
            manila_generic.os.O_WRONLY | manila_generic.os.O_CREAT,
            0o600)
        self.fdopen.assert_called_once_with('opener', 'w')
        f.__enter__().write.assert_called_once_with("This\nOne")

    def test_write_file_private(self):
        f = mock.MagicMock()
        self.patch_object(manila_generic.os, 'fdopen', return_value=f)
        self.patch_object(manila_generic.os, 'open', return_value='opener')
        text = """
            This
            Two"""
        # strip the first new line off when passing the test string through
        # this is to test dedenting strings
        manila_generic.write_file(text[1:], 'file1', chown=0o644)
        self.open.assert_called_once_with(
            'file1',
            manila_generic.os.O_WRONLY | manila_generic.os.O_CREAT,
            0o644)
        self.fdopen.assert_called_once_with('opener', 'w')
        f.__enter__().write.assert_called_once_with("This\nTwo")
