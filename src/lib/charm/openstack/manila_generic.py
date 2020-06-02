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
# The manila handlers class

# bare functions are provided to the reactive handlers to perform the functions
# needed on the class.

import os
import textwrap

import charmhelpers.contrib.openstack.templating as os_templating
import charmhelpers.core.hookenv as hookenv
import charmhelpers.core.templating
import charms_openstack.charm
import charms_openstack.adapters
import charms.reactive.relations as relations

# There are no additional packages to install.
PACKAGES = []
MANILA_DIR = '/etc/manila/'
MANILA_CONF = MANILA_DIR + "manila.conf"

MANILA_SSH_KEY_PATH = '/etc/manila/ssh_image_key'
MANILA_SSH_KEY_PATH_PUBLIC = '/etc/manila/ssh_image_key.pub'

# select the default release function and ssl feature
charms_openstack.charm.use_defaults('charm.default-select-release')


###
# Compute some options to help with template rendering
@charms_openstack.adapters.config_property
def computed_use_password(config):
    """Return True if the generic driver should use a password rather than an
    ssh key.
    :returns: boolean
    """
    return (bool(config.driver_service_instance_password) &
            ((config.driver_auth_type or '').lower()
             in ('password', 'both')))


@charms_openstack.adapters.config_property
def computed_use_ssh(config):
    """Return True if the generic driver should use a password rather than an
    ssh key.
    :returns: boolean
    """
    return ((config.driver_auth_type or '').lower() in ('ssh', 'both'))


@charms_openstack.adapters.config_property
def computed_define_ssh(config):
    """Return True if the generic driver should define the SSH keys
    :returns: boolean
    """
    return (bool(config.driver_service_ssh_key) &
            bool(config.driver_service_ssh_key_public))


@charms_openstack.adapters.config_property
def computed_debug_level(config):
    """Return NONE, INFO, WARNING, DEBUG depending on the settings of
    options.debug and options.level
    :returns: string, NONE, WARNING, DEBUG
    """
    if not config.debug:
        return "NONE"
    if config.verbose:
        return "DEBUG"
    return "WARNING"


# Work-around charms.openstack non ability to expose a property on the
# charms.reactive relation to the adapter.  it would work if it was a function,
# but sadly not for a property.
@charms_openstack.adapters.adapter_property('manila-plugin')
def authentication_data(manila_plugin):
    """Return the authentication dictionary for use in the manila.conf template

        The authentication data format is:
        {
            'username': <value>
            'password': <value>
            'project_domain_id': <value>
            'project_name': <value>
            'user_domain_id': <value>
            'auth_uri': <value>
            'auth_url': <value>
            'auth_type': <value>  # 'password', typically
        }

    :param manila_plugin: the charms.reactive relation instance.
    :returns: dict described above
    """
    return manila_plugin.relation.authentication_data


###
# Implementation of the Manila Charm classes

class ManilaGenericCharm(charms_openstack.charm.OpenStackCharm):
    """Generic backend driver configuration charm.  This configures a nominally
    named "generic" section along with nova, cinder and neutron sections to
    enable the generic NFS driver in the front end.
    """

    release = 'mitaka'
    name = 'manila-generic'
    packages = PACKAGES
    release_pkg = 'manila-common'
    version_package = 'manila-api'  # need this for versioning the app
    api_ports = {}
    service_type = None

    default_service = None  # There is no service for this charm.
    services = []

    required_relations = ['manila-plugin', ]

    restart_map = {}

    # This is the command to sync the database
    sync_cmd = []

    # TODO: remove this when the charms.openstack fix lands
    adapters_class = charms_openstack.adapters.OpenStackRelationAdapters

    def custom_assess_status_check(self):
        """Validate that the driver configuration is at least complete, and
        that it was valid when it used (either at configuration time or config
        changed time)

        :returns (status: string, message: string): the status, and message if
            there is a problem. Or (None, None) if there are no issues.
        """
        options = self.options
        if not options.driver_handles_share_servers:
            # Nothing to check if the driver doesn't handle share servers
            # directly.
            return None, None
        if not options.driver_service_image_name:
            return 'blocked', "Missing 'driver-service-image-name'"
        if not options.driver_service_instance_user:
            return 'blocked', "Missing 'driver-service-instance-user'"
        if not options.driver_service_instance_flavor_id:
            return ('blocked',
                    "Missing 'driver-service-instance-flavor-id'")
        # Need at least one of the password or the keypair
        if not(bool(options.driver_service_instance_password) or
                bool(options.driver_keypair_name)):
            return ('blocked',
                    "Need at least one of instance password or keypair name")
        return None, None

    def get_config_for_principal(self, auth_data):
        """Assuming that the configuration data is valid, return the
        configuration data for the principal charm.

        The format of the complete returned data is:
        {
            "<config file>: <string>
        }

        If the configuration is not complete, or we don't have auth data from
        the principal charm, then we return and emtpy dictionary {}

        :param auth_data: the raw dictionary received from the principal charm
        :returns: structure described above.
        """
        # If there is no auth_data yet, then we can't write our config.
        if not auth_data:
            return {}
        # If the state from the assess_status is not None then we're blocked,
        # so don't send any config to the principal.
        state, message = self.custom_assess_status_check()
        if state:
            return {}
        options = self.options  # tiny optimisation for less typing.

        # If there is no backend name, then we can't send the data yet as the
        # manila-charm won't know what to do with it.
        if not options.share_backend_name:
            return {}

        # We have the auth data & the config is reasonably sensible.
        # We can try and render the config file segment.
        # TODO this is horrible, and we should have something in
        # charms.openstack to do this, but we need a c.r relation to be able to
        # add it to the adapters_instance
        manila_plugin = relations.endpoint_from_flag('manila-plugin.available')
        self.adapters_instance.add_relation(manila_plugin)
        rendered_configs = charmhelpers.core.templating.render(
            source=os.path.basename(MANILA_CONF),
            template_loader=os_templating.get_loader(
                'templates/', self.release),
            target=None,
            context=self.adapters_instance)

        return {
            MANILA_CONF: rendered_configs
        }

    def maybe_write_ssh_keys(self):
        """Maybe write the ssh keys from the options to the key files where
        manila will be able to find them.  The function only writes them if the
        configuration is to use the SSH config.  If they are not to be written
        and they exist then they are deleted.
        """
        if (self.options.computed_use_ssh and
                self.options.computed_define_ssh):
            write_file(self.options.driver_service_ssh_key,
                       MANILA_SSH_KEY_PATH)
            write_file(self.options.driver_service_ssh_key_public,
                       MANILA_SSH_KEY_PATH_PUBLIC, 0o644)
        else:
            for f in (MANILA_SSH_KEY_PATH, MANILA_SSH_KEY_PATH_PUBLIC):
                try:
                    os.remove(f)
                except OSError:
                    pass


def write_file(contents, file, chown=0o600):
    """Write the contents to the file.

    :param contents: the contents to write.  This will be dedented, and striped
        to ensure that it is just a set of lines.
    :param file: the file to write
    :param chown: the ownership for the file.
    :raises OSError: If the file couldn't be written.
    :returns None:
    """
    try:
        with os.fdopen(os.open(file,
                               os.O_WRONLY | os.O_CREAT,
                               chown), 'w') as f:
            f.write(textwrap.dedent(contents))
    except OSError as e:
        hookenv.log("Couldn't write file: {}".format(str(e)))
