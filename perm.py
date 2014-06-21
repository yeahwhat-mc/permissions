#!/usr/bin/env python

import yaml
import os.path
import collections
import copy
from pprint import pprint

configpath = "config.yml"
groupspath = "groups/"
worldspath = "worlds/"
outputpath = "final/"

def merge_worlds(world, update):
    groups = world["groups"]
    for group, prop in update["groups"].items():
        if group not in groups:
            groups[group] = fixgroup(copy.deepcopy(prop))

    for group, prop in update["groups"].items():
        newgroup = groups[group]
        if "default" in prop:
            newgroup["default"] = prop["default"]
        if "info" in prop:
            if "info" in newgroup:
                for key, val in prop["info"].items():
                    newgroup["info"][key] = val
            else:
                newgroup["info"] = copy.copy(prop["info"])
        if "permissions" in prop:
            addnodes(newgroup["permissions"], prop["permissions"])
        if "inheritance" in prop:
            addnodes(newgroup["inheritance"], prop["inheritance"])
    return groups

def fixgroup(group):
    if "permissions" not in group:
        group["permissions"] = list()
    if "inheritance" not in group:
        group["inheritance"] = list()
    if "default" not in group:
        group["default"] = False
    return group
                    
def addnodes(nodeset, nodes):
    for node in nodes:
        if node.startswith("-"):
            if node[1:] in nodeset:
                nodeset.remove(node[1:])
            elif node not in nodeset:
                nodeset.append(node)
        else:
            if "-"+node in nodeset:
                nodeset.remove("-"+node)
            elif node not in nodeset:
                nodeset.append(node)
    return nodeset

f = open(configpath, "r")
config = yaml.load(f)
f.close()

cworlds = config["worlds"]
cgroups = config["groups"]
worldorder = []
for world, prop in cworlds.items():
    if "inheritances" not in prop or not prop["inheritances"]:
        worldorder.append(world)

newworlds = True
while newworlds:
    remaining = set(world for world in cworlds if world not in worldorder)
    newworlds = set()
    for world in remaining:
        if all(inherit in worldorder for inherit in cworlds[world]["inheritances"]):
            newworlds.add(world)
            worldorder.append(world)

if remaining:
    print("ERROR: Could not resolve inheritances for", remaining)
    exit()

globalgroups = {}
for filename in os.listdir(groupspath):
    filepath = os.path.join(groupspath, filename)
    f = open(filepath, "r")
    filegroups = yaml.load(f)
    f.close()
    for group, nodes in filegroups.items():
        if "permissions" not in nodes:
            print("ERROR: No permissions section not in group", group)
            exit()
        globalgroups[group] = nodes
        globalgroups[group]["permissions"].sort()

customworlds = {}
for filename in os.listdir(worldspath):
    filepath = os.path.join(worldspath, filename)
    worldname = os.path.splitext(filename)[0]
    f = open(filepath, "r")
    worlddata = yaml.load(f)
    f.close()
    customworlds[worldname] = worlddata

worldperms = {}
for world in worldorder:
    worldconfig = cworlds[world]
    worlddata = {}
    if not "groups" in worlddata:
        worlddata["groups"] = {}
    if "inheritances" in worldconfig:
        for inheritworld in worldconfig["inheritances"]:
            merge_worlds(worlddata, worldperms[inheritworld])
    for group in worlddata["groups"]:
        fixgroup(worlddata["groups"][group])
    if world in customworlds:
        for group in customworlds[world]["groups"]:
            if group not in worlddata["groups"]:
                worlddata["groups"][group] = fixgroup({})
    if "suffixes" in worldconfig:
        suffixes = worldconfig["suffixes"]
        for pgroup in globalgroups:
            pgroupparts = pgroup.split("_")
            if len(pgroupparts) < 2:
                print("WARNING: Group", pgroup, "has an invalid name and will be ignored")
                continue
            elif (len(pgroupparts) == 2 and "" in suffixes or 
                len(pgroupparts) >= 3 and pgroupparts[2] in suffixes):
                    for group in (group for group in worlddata["groups"] if group in cgroups):
                        if pgroupparts[1] in cgroups[group] and pgroup not in worlddata["groups"][group]["inheritance"]:
                            worlddata["groups"][group]["inheritance"].append(pgroup)
    if world in customworlds:
        merge_worlds(worlddata, customworlds[world])

    worldperms[world] = worlddata

f = open(os.path.join(outputpath, "globalgroups.yml"), "w")
yaml.dump({"groups": globalgroups}, f, default_flow_style=False)
f.close()

for world in cworlds:
    if "folder" not in cworlds[world]:
        folder = world
    elif cworlds[world]["folder"] == '':
        continue
    else:
        folder = cworlds[world]["folder"]
    
    worlddir = os.path.join(outputpath, folder)
    if not os.path.exists(worlddir):
        os.makedirs(worlddir)
    f = open(os.path.join(worlddir, "groups.yml"), "w")
    yaml.dump(worldperms[world], f, default_flow_style=False)
    f.close()
