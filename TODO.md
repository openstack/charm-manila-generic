TODO
====

 * Add roles to the manila charm: api, scheduler, data, process, (all)
 * Add a manila-backend-plugin interface
 * Split the generic configuration into manila-generic-backend charm
 * Add unit tests
 * Add amulet tests
 * Put the manual testing bits into charm-openstack-testing so that the bundles
   are available

## Add roles:

It's necessary for the manila charm to be able to install itself as one of a
number of roles:

 1. The manila-api: this provides the API to the rest of OpenStack.  Until this
    is HA aware, only ONE manila-api can be provisioned.  Also, it may not make
    sense to provision more than one manila-api server per OpenStack
    installation.
 2. The manila-scheduler: TODO
 3. The manila-data process: TODO
 4. The manila-share process: TODO


## Split the generic backend configuration out into a separate charm + interface

It's necessary to have the ability to configure a share backend independently
of the main charm.  This means that plugin charms will be used to configure
each backend.

Essentially, a plugin needs to be able to configure:

 - it's section in the manila.conf along with any network plugin's that it
     needs (assuming that it's a share that manages it's own share-instance).
 - ensure that the relevant bits are restarted.

It's not clear whether, for example, the api bit needs to know if the backend
is a generic backend, rather than something else.

Anyway, to start with:

 - charm-manila : the main charm that can be deployed as multiple roles
 - interface-manila-backend-plugin : the interface for plugging in the generic
   backend (and other interfaces)
 - charm-manila-generic-backend : the plugin for configuring the generic backend.

The backend needs to provide a piece of the manila.conf configuration file with
the bits necessary to configure the backend.  This is mostly for the share,
rather than the api level.  However, the issue is that parts of this file
actually need informatation from the principal charm (i.e. the manila service
user and password).  And only the API charm should register with keystone
(particularly when the HA stuff is done with a floating VIP).

So, to solve that particular problem, we need to 'half' do the template, OR
provide the keystone 'manila' user credentials across the interface.  And I
prefer the latter!
