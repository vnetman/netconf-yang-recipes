#!/usr/bin/env python3

'''iosxe_netconf_example.py

Program to configure a Cisco IOS-XE switch using netconf (via the ncclient
module. Creates a VLAN, includes it in the trunked VLANs list of a trunk
interface, creates an SVI, assigns the SVI an IP address, and finally includes
the newly-created network in the OSPF router.'''

import sys
import logging
import re
import xmltodict
from ncclient import manager

#---

def main():
    ''' Main program logic.
    '''

    # The device to operate on
    device = {}
    device['host'] = '192.0.2.1'   # Change this
    device['netconf_port'] = 830   # Typically 830
    device['user'] = 'user_name'   # Change this  
    device['password'] = '$ecret'  # Change this

    # The settings to apply
    settings = {}
    settings['vlan_id'] = '164'
    settings['vlan_name'] = 'Vendor VLAN Brown'
    settings['interface'] = 'Gi1/0/13'
    settings['ip_address'] = '10.3.164.1'
    settings['ip_network'] = '10.3.164.0'
    settings['ip_subnet'] = '255.255.255.0'
    settings['ip_ospf_router'] = '38'
    settings['ip_ospf_mask'] = '0.0.0.255'
    settings['ospf_area'] = '0'

    # Prepare the steps that will be executed once we connect to the device
    step_list = []

    # 1
    step_descr = 'create vlan {} ("{}")'.format(settings['vlan_id'],
                                                settings['vlan_name'])
    step_action = lambda: xml_create_vlan(settings['vlan_id'],
                                          settings['vlan_name'])
    step_list.append((step_descr, step_action,))

    # 2
    step_descr = 'create trunk interface {}'.format(settings['interface'])
    step_action = lambda: xml_mark_interface_as_switchport_trunk(
        settings['interface'])
    step_list.append((step_descr, step_action,))

    # 3
    step_descr = 'add vlan {} to trunk interface {}'.format(
        settings['vlan_id'], settings['interface'])
    step_action = lambda: xml_add_vlan_to_trunk_interface(
        settings['interface'], settings['vlan_id'])
    step_list.append((step_descr, step_action,))

    # 4
    svi_descr = 'Internet gateway for {}'.format(settings['vlan_name'])
    step_descr = 'create svi {}'.format(settings['vlan_id'])
    step_action = lambda: xml_svi_create(settings['vlan_id'], svi_descr)
    step_list.append((step_descr, step_action,))

    # 5
    svi_name = 'Vlan{}'.format(settings['vlan_id'])
    step_descr = 'assign IP address {} {} to svi {}'.format(
        settings['ip_address'], settings['ip_subnet'], settings['vlan_id'])
    step_action = lambda: xml_interface_ip(svi_name, settings['ip_address'],
                                           settings['ip_subnet'])
    step_list.append((step_descr, step_action,))

    # 6
    step_descr = 'add subnet {} to OSPF router {}'.format(
        settings['ip_network'], settings['ip_ospf_router'])
    step_action = lambda: xml_add_ipv4_net_to_ospf_router(
        settings['ip_ospf_router'], settings['ip_network'],
        settings['ip_ospf_mask'], settings['ospf_area'])
    step_list.append((step_descr, step_action,))

    # Connect to the device
    with manager.connect(host=device['host'], port=device['netconf_port'],
                         username=device['user'], password=device['password'],
                         hostkey_verify=False, allow_agent=False,
                         look_for_keys=False) as m:
        print('Connected to device')

        print('Attempting to lock running config...', end='')
        with m.locked('running'):
            print('succeeded.')
            # Execute the previously prepared steps
            step_num = 0
            for (step, func) in step_list:
                step_num += 1
                if send_config_to_device(m, func()):
                    print('Step {}: {}: success'.format(step_num, step),
                          file=sys.stdout)
                else:
                    print('Step {}: {}: failed, aborting'.format(step_num,
                                                                 step),
                          file=sys.stderr)
                    break
        print('Unlocked running config')
#---

def xml_create_vlan(vlan_id, vlan_name):
    '''Generate the Netconf XML config snippet for creating a new VLAN.
    '''

    xml_snippet = '''
    <config xmlns:xc="urn:ietf:params:xml:ns:netconf:base:1.0"
            xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
     <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
      <vlan>
       <vlan-list xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-vlan">
        <id>{vlan_id}</id>
        <name>{vlan_name}</name>
       </vlan-list>
      </vlan>
     </native>
    </config>'''.format(vlan_id=vlan_id, vlan_name=vlan_name)

    return xml_snippet
#---

def xml_delete_vlan(vlan_id):
    '''Generate the Netconf XML config snippet for deleting a VLAN.
    '''

    xml_snippet = '''
    <config xmlns:xc="urn:ietf:params:xml:ns:netconf:base:1.0"
            xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
     <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
      <vlan>
       <vlan-list xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-vlan"
                  operation="delete">
        <id>{vlan_id}</id>
       </vlan-list>
      </vlan>
     </native>
    </config>'''.format(vlan_id=vlan_id)

    return xml_snippet
#---

def xml_create_classmap(cm_name, cm_description):
    '''Generate the Netconf XML config snippet for creating a classmap
    (e.g. for configuring QoS). Will create an empty, "match-any" classmap.
    '''

    xml_snippet = '''
    <config xmlns:xc="urn:ietf:params:xml:ns:netconf:base:1.0"
            xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
     <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
      <policy>
       <class-map xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-policy">
        <name>{cm_name}</name>
        <prematch>match-any</prematch>
        <description>{cm_description}</description>
       </class-map>
      </policy>
     </native>
    </config>'''.format(cm_name=cm_name, cm_description=cm_description)

    return xml_snippet
#---

def xml_add_ipv4_net_to_ospf_router(router_id, network_ip, network_mask,
                                    area):
    '''Generate the Netconf XML config snippet for adding an IPv4 subnet
    to an OSPF router instance.
    '''

    xml_snippet = '''
    <config xmlns:xc="urn:ietf:params:xml:ns:netconf:base:1.0"
            xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
     <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
      <router>
       <ospf xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-ospf">
        <id>{router_id}</id>
        <network>
         <ip>{network_ip}</ip>
         <mask>{network_mask}</mask>
         <area>{area}</area>
        </network>
       </ospf>
      </router>
     </native>
    </config>'''.format(router_id=router_id, network_ip=network_ip,
                        network_mask=network_mask, area=area)

    return xml_snippet
#---

def xml_delete_ospf_router(router_id):
    '''Generate the Netconf XML config snippet for deleting an OSPF router
    instance.
    '''

    xml_snippet = '''
    <config xmlns:xc="urn:ietf:params:xml:ns:netconf:base:1.0"
            xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
     <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
      <router>
       <ospf xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-ospf"
             operation="delete">
        <id>{router_id}</id>
       </ospf>
      </router>
     </native>
    </config>'''.format(router_id=router_id)

    return xml_snippet
#---

def get_xml_if_name_for(interface_name):
    '''The Yang models for interfaces specify that an interface name like
    "Gi1/0/13" must be specified in the XML  with an outer tag of
    <GigabitEthernet> and an inner name value of "1/0/13".

    This helper function takes human-friendly strings like "Gi1/0/13" and
    "Vlan19", and returns tuples of the form ('GigabitEthernet', '1/0/13')
    and ('Vlan', '19') respectively, which allows caller functions to
    construct the XML properly.
    '''

    known_ifnames = [
        'FastEthernet',
        'GigabitEthernet',
        'FiveGigabitEthernet',
        'Port-channel',
        'TenGigabitEthernet',
        'TwentyFiveGigE',
        'FortyGigabitEthernet',
        'TwoGigabitEthernet',
        'HundredGigE',
        'Vlan',]

    re_if = re.compile(r'^([^\d]+)(\d[\d\/.]+)$')
    match_obj = re_if.search(interface_name)

    assert match_obj, ('{} does not conform to expected interface '
                       'name format').format(interface_name)

    this_ifname = match_obj.group(1)
    this_iflocation = match_obj.group(2)
    xml_ifname = None
    for known_name in known_ifnames:
        if re.match(this_ifname, known_name, re.I):
            xml_ifname = known_name
            break

    assert xml_ifname, ('Unable to determine XML interface name for "{}" '
                        '(derived from "{}")').format(this_ifname,
                                                      interface_name)

    return (xml_ifname, this_iflocation,)
#---

def xml_mark_interface_as_switchport_trunk(interface_name):
    '''Generate the Netconf XML config snippet for marking an interface as
    a layer 2 trunk instance.
    '''

    (xml_ifname, this_iflocation) = get_xml_if_name_for(interface_name)

    xml_snippet = '''
    <config xmlns:xc="urn:ietf:params:xml:ns:netconf:base:1.0"
            xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
     <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
      <interface>
       <{xml_ifname}>
        <name>{this_iflocation}</name>
         <switchport>
          <mode xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-switch">
           <trunk></trunk>
          </mode>
        </switchport>
       </{xml_ifname}>
      </interface>
     </native>
    </config>'''.format(xml_ifname=xml_ifname, this_iflocation=this_iflocation)

    return xml_snippet
#---

def xml_add_vlan_to_trunk_interface(interface_name, vlan_list):
    '''Generate the Netconf XML config snippet for including the specified
    list of VLANs in the VLANs that the specified trunk interface is
    carrying.
    This is a "safe" method in that it will only ADD the specified vlan list
    to the current list of trunked VLANs, i.e. it will NOT REPLACE the current
    list.
    '''

    (xml_ifname, this_iflocation) = get_xml_if_name_for(interface_name)

    xml_snippet = '''
    <config xmlns:xc="urn:ietf:params:xml:ns:netconf:base:1.0"
            xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
     <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
      <interface>
       <{xml_ifname}>
        <name>{this_iflocation}</name>
        <switchport>
         <trunk xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-switch">
          <allowed>
           <vlan><add>{vlan_list}</add></vlan>
          </allowed>
         </trunk>
        </switchport>
       </{xml_ifname}>
      </interface>
     </native>
    </config>'''.format(xml_ifname=xml_ifname, this_iflocation=this_iflocation,
                        vlan_list=vlan_list)

    return xml_snippet
#---

def xml_svi_create(vlan_id, description):
    '''Generate the Netconf XML config snippet for creating an SVI.
    '''

    xml_snippet = '''
    <config xmlns:xc="urn:ietf:params:xml:ns:netconf:base:1.0"
            xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
     <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
      <interface>
       <Vlan>
        <name>{vlan_id}</name>
        <description>{description}</description>
        <shutdown operation="remove"></shutdown>
       </Vlan>
      </interface>
     </native>
    </config>'''.format(vlan_id=vlan_id, description=description)

    return xml_snippet
#---

def xml_interface_ip(interface_name, ip_address, ip_subnet):
    '''Generate the Netconf XML config snippet for assigning an
    IPv4 address to an interface. The address is added as the primary
    IP address.
    '''

    (xml_ifname, this_iflocation) = get_xml_if_name_for(interface_name)

    xml_snippet = '''
    <config xmlns:xc="urn:ietf:params:xml:ns:netconf:base:1.0"
            xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
     <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
      <interface>
       <{xml_ifname}>
        <name>{this_iflocation}</name>
        <ip>
         <address>
          <primary>
           <address>{ip_address}</address>
           <mask>{ip_subnet}</mask>
          </primary>
         </address>
        </ip>
       </{xml_ifname}>
      </interface>
     </native>
    </config>'''.format(xml_ifname=xml_ifname, this_iflocation=this_iflocation,
                        ip_address=ip_address, ip_subnet=ip_subnet)

    return xml_snippet
#---

def send_config_to_device(ncclient_manager, config_xml):
    '''Given an XML config snippet, ask the ncclient manager to apply it
    on the device.
    '''

    try:
        reply = ncclient_manager.edit_config(target='running',
                                             config=config_xml)
    except Exception as e:
        print(str(e), file=sys.stderr)
        return False

    netconf_reply_data = xmltodict.parse(reply.xml)["rpc-reply"]
    assert 'ok' in netconf_reply_data

    return True
#---

if __name__ == '__main__':
    logging.basicConfig(level=logging.CRITICAL,
                        format='%(asctime)s %(levelname)s: %(message)s',
                        stream=sys.stdout)
    sys.exit(main())
