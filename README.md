# netconf-yang-recipes
Recipes for configuring Cisco IOS-XE devices using NETCONF/YANG

This repository contains a few Python programs that use the [ncclient library](https://github.com/ncclient/ncclient) to push configuration out to Cisco IOS-XE devices.

## 1. Installation

* Use Python3
* `pip install xmltodict` (prefereably use a virtualenv set up for Python3)
* `pip install ncclient` (preferably use a virtualenv set up for Python3)
* Edit the device details in the Python script (IP address, NETCONF port, username and password)
* Run by calling `python3 <script name>` For example, `python3 add_new_vlan.py`

## 2. Brief descriptions of programs

### 2.1 add_new_vlan.py

This program executes the typical steps that are needed to be carried out on a typical distribution switch when a new VLAN is to be added on a trunk going to an access switch, and a new IPv4 subnet needs to be provisioned for this new VLAN.

The steps executed are:

1. Creates the new VLAN at the global level on the switch (we're assuming VTP mode is transparent)
2. Marks an interface as a trunk
3. Includes the newly created VLAN in the list of VLANs carried by the above trunk
4. Creates a VLAN interface (SVI) for the new VLAN
5. Assigns a primary IPv4 address to the SVI
6. Includes the just-created subnet in an OSPF router process
