import amulet

from keystoneclient import session as keystone_session
from keystoneclient.auth import identity as keystone_identity
import keystoneclient.exceptions
from keystoneclient.v2_0 import client as keystone_v2_0_client
from keystoneclient.v3 import client as keystone_v3_client
from manilaclient.v1 import client as manila_client

from charmhelpers.contrib.openstack.amulet.deployment import (
    OpenStackAmuletDeployment
)

from charmhelpers.contrib.openstack.amulet.utils import (
    OpenStackAmuletUtils,
    DEBUG,
)

# Use DEBUG to turn on debug logging
u = OpenStackAmuletUtils(DEBUG)


class ManilaGenericBasicDeployment(OpenStackAmuletDeployment):
    """Amulet tests on a basic Manila Generic deployment.

    Note that these tests don't attempt to do a functional test on Manila,
    merely to demonstrate that the relations work and that they transfer the
    correct information across them. It verifies that the configuration goes
    across to the manila main charm.

    A functional test will be performed by a mojo or tempest test.
    """

    def __init__(self, series, openstack=None, source=None, stable=True,
                 keystone_version='2'):
        """Deploy the entire test environment.
        """
        super(ManilaGenericBasicDeployment, self).__init__(
            series, openstack, source, stable)
        self._keystone_version = keystone_version
        self._add_services()
        self._add_relations()
        self._configure_services()
        self._deploy()

        u.log.info('Waiting on extended status checks...')
        exclude_services = ['mysql', ]
        self._auto_wait_for_status(exclude_services=exclude_services)

        self._initialize_tests()

    def _add_services(self):
        """Add services

           Add the services that we're testing, where manila is local,
           and the rest of the service are from lp branches that are
           compatible with the local charm (e.g. stable or next).
           """
        this_service = {'name': 'manila-generic'}
        other_services = [
            {'name': 'mysql',
             'location': 'cs:percona-cluster',
             'constraints': {'mem': '3072M'}},
            {'name': 'rabbitmq-server'},
            {'name': 'keystone'},
            {'name': 'manila'}
        ]
        super(ManilaGenericBasicDeployment, self)._add_services(
            this_service, other_services)

    def _add_relations(self):
        """Add all of the relations for the services."""
        relations = {
            'manila:shared-db': 'mysql:shared-db',
            'manila:amqp': 'rabbitmq-server:amqp',
            'manila:identity-service': 'keystone:identity-service',
            'manila:manila-plugin': 'manila-generic:manila-plugin',
            'keystone:shared-db': 'mysql:shared-db',
        }
        super(ManilaGenericBasicDeployment, self)._add_relations(relations)

    def _configure_services(self):
        """Configure all of the services."""
        keystone_config = {
            'admin-password': 'openstack',
            'admin-token': 'ubuntutesting',
        }
        manila_config = {
            'default-share-backend': 'generic',
        }
        manila_generic_config = {
            'driver-handles-share-servers': False,
        }
        configs = {
            'keystone': keystone_config,
            'manila': manila_config,
            'manila-generic': manila_generic_config,
        }
        super(ManilaGenericBasicDeployment, self)._configure_services(configs)

    def _initialize_tests(self):
        """Perform final initialization before tests get run."""
        # Access the sentries for inspecting service units
        self.manila_sentry = self.d.sentry['manila'][0]
        self.manila_generic_sentry = self.d.sentry['manila-generic'][0]
        self.mysql_sentry = self.d.sentry['mysql'][0]
        self.keystone_sentry = self.d.sentry['keystone'][0]
        self.rabbitmq_sentry = self.d.sentry['rabbitmq-server'][0]
        u.log.debug('openstack release val: {}'.format(
            self._get_openstack_release()))
        u.log.debug('openstack release str: {}'.format(
            self._get_openstack_release_string()))

        keystone_ip = self.keystone_sentry.relation(
            'shared-db', 'mysql:shared-db')['private-address']

        # We need to auth either to v2.0 or v3 keystone
        if self._keystone_version == '2':
            ep = ("http://{}:35357/v2.0"
                  .format(keystone_ip.strip().decode('utf-8')))
            auth = keystone_identity.v2.Password(
                username='admin',
                password='openstack',
                tenant_name='admin',
                auth_url=ep)
            keystone_client_lib = keystone_v2_0_client
        elif self._keystone_version == '3':
            ep = ("http://{}:35357/v3"
                  .format(keystone_ip.strip().decode('utf-8')))
            auth = keystone_identity.v3.Password(
                user_domain_name='admin_domain',
                username='admin',
                password='openstack',
                domain_name='admin_domain',
                auth_url=ep)
            keystone_client_lib = keystone_v3_client
        else:
            raise RuntimeError("keystone version must be '2' or '3'")

        sess = keystone_session.Session(auth=auth)
        self.keystone = keystone_client_lib.Client(session=sess)
        # The service_catalog is missing from V3 keystone client when auth is
        # done with session (via authenticate_keystone_admin()
        # See https://bugs.launchpad.net/python-keystoneclient/+bug/1508374
        # using session construct client will miss service_catalog property
        # workaround bug # 1508374 by forcing a pre-auth and therefore, getting
        # the service-catalog --
        # see https://bugs.launchpad.net/python-keystoneclient/+bug/1547331
        self.keystone.auth_ref = auth.get_access(sess)

    def test_205_manila_to_manila_generic(self):
        """Verify that the manila to manila-generic config is working"""
        u.log.debug('Checking the manila:manila-generic relation data...')
        manila = self.manila_sentry
        relation = ['manila-plugin', 'manila-generic:manila-plugin']
        expected = {
            'private-address': u.valid_ip,
            '_authentication_data': u.not_null,
        }
        ret = u.validate_relation_data(manila, relation, expected)
        if ret:
            message = u.relation_error('manila manila_generic', ret)
            amulet.raise_status(amulet.FAIL, msg=message)
        u.log.debug('OK')

    def test_206_manila_generic_to_manila(self):
        """Verify that the manila-generic to manila config is working"""
        u.log.debug('Checking the manila-generic:manila relation data...')
        manila_generic = self.manila_generic_sentry
        relation = ['manila-plugin', 'manila:manila-plugin']
        expected = {
            'private-address': u.valid_ip,
            '_configuration_data': u.not_null,
            '_name': 'generic'
        }
        ret = u.validate_relation_data(manila_generic, relation, expected)
        if ret:
            message = u.relation_error('manila manila_generic', ret)
            amulet.raise_status(amulet.FAIL, msg=message)
        u.log.debug('OK')

    @staticmethod
    def _find_or_create(items, key, create):
        """Find or create the thing in the items

        :param items: the items to search using the key
        :param key: a function that key(item) -> boolean if found.
        :param create: a function to call if the key() never was true.
        :returns: the item that was either found or created.
        """
        for i in items:
            if key(i):
                return i
        return create()

    def test_400_api_connection(self):
        """Simple api calls to check service is up and responding"""
        u.log.debug('Checking api functionality...')

        # This handles both keystone v2 and v3.
        # For keystone v2 we need a user:
        #  - 'demo' user
        #  - has a project 'demo'
        #  - in the 'demo' project
        #  - with an 'admin' role
        # For keystone v3 we need a user:
        #  - 'default' domain
        #  - 'demo' user
        #  - 'demo' project
        #  - 'admin' role -- to be able to delete.

        # manila requires a user with creator or admin role on the project
        # when creating a secret (which this test does).  Therefore, we create
        # a demo user, demo project, and then get a demo manila client and do
        # the secret.  ensure that the default domain is created.

        if self._keystone_version == '2':
            # find or create the 'demo' tenant (project)
            tenant = self._find_or_create(
                items=self.keystone.tenants.list(),
                key=lambda t: t.name == 'demo',
                create=lambda: self.keystone.tenants.create(
                    tenant_name="demo",
                    description="Demo for testing manila",
                    enabled=True))
            # find or create the demo user
            demo_user = self._find_or_create(
                items=self.keystone.users.list(),
                key=lambda u: u.name == 'demo',
                create=lambda: self.keystone.users.create(
                    name='demo',
                    password='pass',
                    tenant_id=tenant.id))
            # find the admin role
            # already be created - if not, then this will fail later.
            admin_role = self._find_or_create(
                items=self.keystone.roles.list(),
                key=lambda r: r.name.lower() == 'admin',
                create=lambda: None)
            # grant the role if it isn't already created.
            # now grant the creator role to the demo user.
            self._find_or_create(
                items=self.keystone.roles.roles_for_user(
                    demo_user, tenant=tenant),
                key=lambda r: r.name.lower() == admin_role.name.lower(),
                create=lambda: self.keystone.roles.add_user_role(
                    demo_user, admin_role, tenant=tenant))
            # now we can finally get the manila client and create the secret
            keystone_ep = self.keystone.service_catalog.url_for(
                service_type='identity', endpoint_type='publicURL')
            auth = keystone_identity.v2.Password(
                username=demo_user.name,
                password='pass',
                tenant_name=tenant.name,
                auth_url=keystone_ep)

        else:
            # find or create the 'default' domain
            domain = self._find_or_create(
                items=self.keystone.domains.list(),
                key=lambda u: u.name == 'default',
                create=lambda: self.keystone.domains.create(
                    "default",
                    description="domain for manila testing",
                    enabled=True))
            # find or create the 'demo' user
            demo_user = self._find_or_create(
                items=self.keystone.users.list(domain=domain.id),
                key=lambda u: u.name == 'demo',
                create=lambda: self.keystone.users.create(
                    'demo',
                    domain=domain.id,
                    description="Demo user for manila tests",
                    enabled=True,
                    email="demo@example.com",
                    password="pass"))
            # find or create the 'demo' project
            demo_project = self._find_or_create(
                items=self.keystone.projects.list(domain=domain.id),
                key=lambda x: x.name == 'demo',
                create=lambda: self.keystone.projects.create(
                    'demo',
                    domain=domain.id,
                    description='manila testing project',
                    enabled=True))
            # create the role for the user - needs to be admin so that the
            # secret can be deleted - note there is only one admin role, and it
            # should already be created - if not, then this will fail later.
            admin_role = self._find_or_create(
                items=self.keystone.roles.list(),
                key=lambda r: r.name.lower() == 'admin',
                create=lambda: None)
            # now grant the creator role to the demo user.
            try:
                self.keystone.roles.check(
                    role=admin_role,
                    user=demo_user,
                    project=demo_project)
            except keystoneclient.exceptions.NotFound:
                # create it if it isn't found
                self.keystone.roles.grant(
                    role=admin_role,
                    user=demo_user,
                    project=demo_project)
            # now we can finally get the manila client and create the secret
            keystone_ep = self.keystone.service_catalog.url_for(
                service_type='identity', endpoint_type='publicURL')
            auth = keystone_identity.v3.Password(
                user_domain_name=domain.name,
                username=demo_user.name,
                password='pass',
                project_domain_name=domain.name,
                project_name=demo_project.name,
                auth_url=keystone_ep)

        # Now we carry on with common v2 and v3 code
        sess = keystone_session.Session(auth=auth)
        # Authenticate admin with manila endpoint
        manila_ep = self.keystone.service_catalog.url_for(
            service_type='share', endpoint_type='publicURL')
        manila = manila_client.Client(session=sess,
                                      endpoint=manila_ep)
        # now just try a list the shares
        manila.shares.list()
        u.log.debug('OK')
