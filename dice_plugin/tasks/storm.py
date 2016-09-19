# -*- coding: utf-8 -*-

# Copyright (C) 2016 XLAB d.o.o.
#
# This file is part of dice-plugin.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy of
# the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, * WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. * See the
# License for the specific language governing permissions and * limitations
# under the License.
#
# Author:
#     Tadej Borovšak <tadej.borovsak@xlab.si>

import os
import yaml
import requests
import tempfile
import subprocess

from dice_plugin import utils
from cloudify.decorators import operation
from cloudify.exceptions import NonRecoverableError


def _get_topology_id(url, name):
    topologies = requests.get(url).json()["topologies"]
    for top in topologies:
        if top["name"] == name:
            return top["id"]
    return None


def _write_tmp_configuration(config):
    handle = tempfile.NamedTemporaryFile(suffix=".yaml", delete=False)
    handle.write(yaml.dump(config))
    handle.close()
    return handle.name


@operation
def submit_topology(ctx, jar, name, klass, args):
    ctx.logger.info("Obtaining topology jar '{}'".format(jar))
    local_jar = utils.obtain_resource(ctx, jar)
    ctx.logger.info("Topology jar stored as '{}'".format(local_jar))

    ctx.logger.info("Preparing topology configuration")
    cfg = ctx.node.properties["configuration"].copy()
    cfg.update(ctx.instance.runtime_properties.get("configuration", {}))
    cfg_file = _write_tmp_configuration(cfg)
    ctx.logger.info("Configuration stored in '{}'".format(cfg_file))

    ctx.logger.info("Submitting '{}' as '{}'".format(local_jar, name))
    subprocess.call([
        "storm", "--config", cfg_file, "jar", local_jar, klass, name
    ] + args)
    os.unlink(cfg_file)

    ctx.logger.info("Retrieving topology id for '{}'".format(name))
    nimbus_ip = ctx.instance.host_ip
    url = "http://{}:8080/api/v1/topology/summary".format(nimbus_ip)
    topology_id = _get_topology_id(url, name)
    ctx.logger.info("Topology id for '{}' is '{}'".format(name, topology_id))

    if topology_id is None:
        msg = "Topology '{}' failed to start properly".format(name)
        raise NonRecoverableError(msg)
    ctx.instance.runtime_properties["topology_id"] = topology_id


@operation
def kill_topology(ctx, name):
    ctx.logger.info("Killing topology '{}'".format(name))
    subprocess.call(["storm", "kill", name])