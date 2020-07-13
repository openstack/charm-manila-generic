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

# this is just for the reactive handlers and calls into the charm.

import charms.reactive
import charms_openstack.charm

# This charm's library contains all of the handler code associated with
# manila -- we need to import it to get the definitions for the charm.
import charm.openstack.manila_generic  # noqa


# Use the charms.openstack defaults for common states and hooks
charms_openstack.charm.use_defaults(
    'charm.installed',
    'update-status')


@charms.reactive.when('manila-plugin.changed')
@charms.reactive.when_not('config.changed',
                          'update-status')
def send_config(manila_plugin):
    """Send the configuration over to the prinicpal charm"""
    with charms_openstack.charm.provide_charm_instance() as generic_charm:
        # set the name of the backend using the configuration option
        manila_plugin.name = generic_charm.options.share_backend_name
        # Set the configuration data for the principal charm.
        manila_plugin.configuration_data = (
            generic_charm.get_config_for_principal(
                manila_plugin.authentication_data))
        generic_charm.maybe_write_ssh_keys()
        generic_charm.assess_status()
        manila_plugin.clear_changed()


@charms.reactive.when('manila-plugin.available',
                      'config.changed')
@charms.reactive.when_not('update-status')
def update_config(manila_plugin):
    send_config(manila_plugin)
