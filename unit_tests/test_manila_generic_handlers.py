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

import reactive.manila_generic_handlers as handlers

import charms_openstack.test_utils as test_utils


class TestRegisteredHooks(test_utils.TestRegisteredHooks):

    def test_hooks(self):
        defaults = [
            'charm.installed',
            'update-status']
        hook_set = {
            'when': {
                'send_config': ('manila-plugin.changed', ),
                'update_config': ('manila-plugin.available',
                                  'config.changed', ),
            },
            'when_not': {
                'send_config': ('config.changed', 'update-status'),
                'update_config': ('update-status', ),
            },
        }
        # test that the hooks were registered via the
        # reactive.barbican_handlers
        self.registered_hooks_test_helper(handlers, hook_set, defaults)


class TestHandlerFunctions(test_utils.PatchHelper):

    def _patch_provide_charm_instance(self):
        manila_generic_charm = mock.MagicMock()
        self.patch('charms_openstack.charm.provide_charm_instance',
                   name='provide_charm_instance',
                   new=mock.MagicMock())
        self.provide_charm_instance().__enter__.return_value = \
            manila_generic_charm
        self.provide_charm_instance().__exit__.return_value = None
        return manila_generic_charm

    def test_send_config(self):
        generic = self._patch_provide_charm_instance()

        class FakeManilaPlugin(object):

            name = None
            configuration_data = None
            authentication_data = 'auth data'

            _clear_changed = 0

            def clear_changed(self):
                self._clear_changed += 1

        generic.get_config_for_principal.return_value = "some data"
        manila_plugin = FakeManilaPlugin()
        handlers.send_config(manila_plugin)

        # test for expecations
        self.assertEqual(manila_plugin.name,
                         generic.options.share_backend_name)
        self.assertEqual(manila_plugin.configuration_data, "some data")
        generic.get_config_for_principal.assert_called_once_with('auth data')
        generic.assess_status.assert_called_once_with()
        generic.maybe_write_ssh_keys.assert_called_once_with()
        self.assertEqual(manila_plugin._clear_changed, 1)
