Extract Foreman smart parameters to hiera
=========================================

Small utility to extract smart parameters from Foreman and create a hiera
hierarchy with matching values.

I've used this successfully to migrate a Puppet setup that used to store
module parameters in Foreman to a hiera based setup.

For simple module usage, see the end of this document.


Proposed migration strategy
===========================

The process I used was this:


Run `foreman2hiera`
-------------------

First: run `foreman2hiera` with correct parameters in order to create
hiera config and data directory.

    foreman2hiera -u username -p password -a https://foreman.server/api

This should create the hiera config (`hiera.yaml` and the `hieradata`
directory).


Correct the hierarchy
---------------------

`foreman2hiera` will warn you if it finds more than one override order. In
that case it won't know which order to use for `hiera.yaml`.

Since I had multiple override orders, I needed to find a hierarchy that
facilitated all use cases. Example:

Override order 1:
* fqdn
* hostgroup
* osfamily
* domain

Override order 2:
* fqdn
* hostgroup
* osfamily
* os
* domain

The case over is simple. Even though `foreman2hiera` has chosen the first order
for `hiera.yaml`, based on the most used override order, it's easy to add
another level in the hierarchy. The files for overrides based on `osfamily`
have already been created in `hieradata`, but they are not referenced by
`hiera.yaml`.


Account for nested hostgroups.
------------------------------

Foreman allows you to have nested hostgroups, and lets you inherit smart
parameters from the parent hostgroups. `foreman2hiera` will create files
for all nesting levels, so if you have hostgroups BASE/GROUP1 and
BASE/GROUP2, you will get the files `hieradata/hostgroups/BASE.yaml`,
`hieradata/hostgroups/BASE/GROUP1.yaml` and
`hieradata/hostgroups/BASE/GROUP2.yaml`.

In my case, the parent hostgroups represented physical locations, so I
added a global parameter, `location`, to the parent hostgroup, and added a
hierarchy level to hiera with `path: "location/%{::location}.yaml"`. Then
I moved the parent files from `hieradata/hostgroups/BASE.yaml` to
`hieradata/locations/BASE.yaml`


Test lookups, possibly tweak merge strategies
---------------------------------------------

When I was confident that all values were in the correct place, I synced
the hiera config (`hiera.yaml` and `hieradata`) to the environment folders
on the puppetmasters. When Foreman is used as an ENC, and overrides are
enabled in Foreman, these will override values from Hiera, so this can be
done safely.

Then I did some tests with `puppet lookup` to make sure values were
showing as expected. By using `--explain` you can see where in the
hierarchy the value is coming from and what merge strategy hiera is
taking.

    sudo /opt/puppetlabs/bin/puppet lookup \
        --environment test \
        --node hostname.of.node puppetclass::parameter \
        --explain

You can also experiment with different merge strategies by appending
`--merge strategy` like so:

    sudo /opt/puppetlabs/bin/puppet lookup \
        --environment test \
        --node hostname.of.node puppetclass::parameter \
        --merge deep \
        --explain

    sudo /opt/puppetlabs/bin/puppet lookup \
        --environment test \
        --node hostname.of.node puppetclass::parameter \
        --merge unique \
        --explain

`foreman2hiera` will use `hash` merging for all parameters which are using
"merge overrides". Sometimes you might want to switch to the `unique` or
`deep` merge strategies. In that case, you'll find all the
`lookup_options` configured by `foreman2hiera` in `hieradata/common.yaml`,
so change it there.

When the values looked correct for a handful of different representative
hosts, I disabled the override in Foreman and ran the puppet agent on them
to make sure all was as expected.

While doing the migration, I used `remaining_smartparams` to keep track of
my progress in disabling Foreman overrides.


Example usage of the module
===========================

The module can also be used by your own Python scripts.

    from smartparamextract import SmartParamExtractor
    extractor = SmartParamExtractor(('username', 'password'),
                                    'http://foreman.domain.tld/api')
    
    overridden = extractor.fetch_overridden_params()     # Takes a while
    
    all_params = list(extractor.fetch_all_param_info())  # Takes even longer
    override_orders = set(p['override_value_order'] for p in all_params)
