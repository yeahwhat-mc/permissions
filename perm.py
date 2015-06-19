#!/usr/bin/env python

import copy
import os
import os.path
import yaml

CONFIGPATH = "config.yml"
PLUGINSPATH = "plugins"
WORLDSPATH = "worlds"
OUTPUTPATH = "final"
SEPERATOR = "_"

def update_groups(groups, update):
    """Updates groups with new nodes from another dict of groups"""
    for groupname, nodes in update.items():
        # If the new group isn't in the old groups, just copy it and skip 
        # everything else
        if groupname not in groups:
            groups[groupname] = fixgroup(copy.deepcopy(nodes))
            continue

        group = groups[groupname]
        if "default" in nodes:
            group["default"] = nodes["default"]
        if "info" in nodes:
            if "info" in group:
                group["info"].update(nodes["info"])
            else:
                group["info"] = copy.copy(nodes["info"])
        if "permissions" in nodes:
            addnodes(group["permissions"], nodes["permissions"])
        if "inheritance" in nodes:
            addnodes(group["inheritance"], nodes["inheritance"])

        groups[groupname] = group
    return groups


def fixgroup(group):
    """Adds missing values to a group to prevent key errors"""
    if "permissions" not in group:
        group["permissions"] = list()
    if "inheritance" not in group:
        group["inheritance"] = list()
    if "default" not in group:
        group["default"] = False
    return group


def addnodes(nodeset, nodes):
    """Merges a list of permission nodes and checks the prefixes"""
    for node in nodes:
        if node in nodeset:
            continue
        elif node.startswith("-"):
            # Check for a positive node with the same name and remove it
            if node[1:] in nodeset:
                nodeset.remove(node[1:])
            # Only add a negative node, if a positive one hasn't been 
            # removed and it doesn't already exist
            elif node not in nodeset:
                nodeset.append(node)
        else:
            # Same as above with the sign inverted
            if "-"+node in nodeset:
                nodeset.remove("-"+node)
            elif node not in nodeset:
                nodeset.append(node)
    return nodeset


with open(CONFIGPATH, "r") as configfile:
    config = yaml.load(configfile)

worldconfigs = config["worlds"]
groupconfigs = config["groups"]
remaining = set(worldconfigs)
worldorder = []

globalgroups = {}
customworlds = {}
worldperms = {}

# Find all the worlds without inheritances and add them to worldorder
for world, nodes in worldconfigs.items():
    if "inheritance" not in nodes or not nodes["inheritance"]:
        worldorder.append(world)
        remaining.remove(world)

while remaining:
    newworlds = set()
    for world in remaining:
        # Check if all inheritances are satisfied
        if all(inheritance in worldorder for inheritance in 
                worldconfigs[world]["inheritance"]):
            newworlds.add(world)
    
    # We have remaining worlds and can't resolve the inheritances
    if not newworlds:
        raise RuntimeError("Could not resolve inheritances for " + 
            str(remaining))

    worldorder += newworlds
    for world in newworlds:
        remaining.remove(world)


# Load the global groups
for filename in os.listdir(PLUGINSPATH):
    filepath = os.path.join(PLUGINSPATH, filename)
    with open(filepath, "r") as pluginfile:
        plugingroups = yaml.load(pluginfile)

    for group, nodes in plugingroups.items():
        if group in globalgroups:
            print("WARNING: Group " + group + " in file " + filename + 
                " already defined, ignoring it")
            continue
        if "permissions" not in nodes:
            print("WARNING: No permissions section in group " + group + 
                ", ignoring it")
            continue
        
        globalgroups[group] = nodes
        globalgroups[group]["permissions"].sort()

# Load custom world permissions
for filename in os.listdir(WORLDSPATH):
    filepath = os.path.join(WORLDSPATH, filename)
    worldname = os.path.splitext(filename)[0]
    with open(filepath, "r") as worldfile:
        worlddata = yaml.load(worldfile)

    customworlds[worldname] = worlddata

# Generate world permissions
for world in worldorder:
    worldconfig = worldconfigs[world]
    groups = {}
    
    # Merge inheritances
    if "inheritance" in worldconfig:
        for inheritworld in worldconfig["inheritance"]:
            update_groups(groups, worldperms[inheritworld]["groups"])
    
    # Merge custom world nodes
    if world in customworlds:
        update_groups(groups, customworlds[world]["groups"])

    # Add the matching global groups
    if "suffixes" in worldconfig:
        suffixes = worldconfig["suffixes"]
        for globgroup in globalgroups:
            groupparts = globgroup.split(SEPERATOR)
            # Global group names have to be in the format
            # <plugin>_<group>_[world]
            if not 2 <= len(groupparts) <= 3:
                print("WARNING: Group" + globgroup + "has an invalid name and "
                    "will be ignored")
                continue

            plugin = groupparts[0]
            groupsuffix = groupparts[1]
            if len(groupparts) == 2:
                worldsuffix = ""
            elif len(groupparts) == 3:
                worldsuffix = groupparts[2]

            # The group has the wrong world suffix
            if worldsuffix not in suffixes:
                continue
            
            for group in groups:
                # Current group doesn't have any suffixes
                if group not in groupconfigs:
                    continue
                # The global group is already added
                if globgroup in groups[group]["inheritance"]:
                    continue
                
                if groupsuffix in groupconfigs[group]:
                    groups[group]["inheritance"].append(globgroup)

    for group, nodes in groups.items():
        nodes["permissions"].sort()
        nodes["inheritance"].sort()

    worldperms[world] = {"groups": groups}

# Make sure the output directory exists
if not os.path.exists(OUTPUTPATH):
    os.makedirs(OUTPUTPATH)

with open(os.path.join(OUTPUTPATH, "globalgroups.yml"), "w") as globalsfile:
    yaml.dump({"groups": globalgroups}, globalsfile, default_flow_style=False)

for world in worldconfigs:
    # World doesn't have a custom folder name
    if "folder" not in worldconfigs[world]:
        folder = world
    # World is virtual and doesn't get saved
    elif worldconfigs[world]["folder"] == '':
        continue
    else:
        folder = worldconfigs[world]["folder"]
    
    worlddir = os.path.join(OUTPUTPATH, folder)
    # Make sure the world directry exists
    if not os.path.exists(worlddir):
        os.makedirs(worlddir)
    
    with open(os.path.join(worlddir, "groups.yml"), "w") as worldfile:
        yaml.dump(worldperms[world], worldfile, default_flow_style=False)
