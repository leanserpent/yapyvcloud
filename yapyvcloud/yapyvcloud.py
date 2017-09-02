import requests, sys, time, inspect, re, yaml, os, tarfile, netaddr, logging, logging.config
from random import randint
from datetime import datetime
from bs4 import builder, BeautifulSoup, Tag, NavigableString
from lxml import etree

LOG_CONFIG = {'version':1,
    'formatters':{
        'verbose':{
            'format':'%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        }
    },
    'handlers':{
        'console':{
            'class':'logging.StreamHandler',
            'formatter':'verbose',
            'level':logging.DEBUG
        },
        'file':{
            'class':'logging.FileHandler',
            'filename':os.path.expanduser('~') + '/yapyvcloud.log',
            'formatter':'verbose',
            'level':logging.DEBUG
        }
    },
    'root':{
        'handlers':('console', 'file'), 
        'level':'DEBUG'
    }
}
logging.config.dictConfig(LOG_CONFIG)
logger = logging.getLogger(__name__)

class IterableToFileAdapter(object):
    def __init__(self, iterable):
        self.iterator = iter(iterable)
        self.length = len(iterable)

    def read(self, size=-1):
        return next(self.iterator, b'')

    def __len__(self):
        return self.length

class ApiError(Exception):
    def __init__(self, *args):
        self.args = args

class ApiWarning(Exception):
    def __init__(self, *args):
        self.args = args

class Container(yaml.YAMLObject):

    conf_path = os.path.expanduser('~') + '/yapyvcloud_cred.yaml'
    session_file_path = os.path.expanduser('~') + '/yapyvcloud_token.yaml'
    api_url_prefix = None
    api_headers = None
    session_org_name = None

    chunk_size = 128*1024
    max_chunk_size = 1024*1024
    identity_provider_types = ['INTEGRATED','SAML']
    hardware_vers = ['vmx-7','vmx-8','vmx-9','vmx-10','vmx-11','vmx-12','vmx-13']
    allocation_models = [ 'AllocationVApp', 'AllocationPool', 'ReservationPool' ]
    edge_gateway_sizes = ['compact','large','x-large','quad-large']
    metadata_visibilities = ['PRIVATE','READONLY']
    metadata_value_types = ['MetadataStringValue','MetadataNumberValue','MetadataBooleanValue','MetadataDateTimeValue']
    access_levels = ['FullControl','Change','ReadOnly']
    disk_bus_sub_types = {'':5,'buslogic':6,'lsilogic':6,'lsilogicsas':6,'VirtualSCSI':6,'vmware.sata.ahci':20}
    fence_modes = ['bridged','natRouted','isolated']
    os_types = {'darwinGuest':'Apple Mac OS X 10.5 (32-bit)',
        'darwin64Guest':'Apple Mac OS X 10.5 (64-bit)',
        'darwin10Guest':'Apple Mac OS X 10.6 (32-bit)',
        'darwin10_64Guest':'Apple Mac OS X 10.6 (64-bit)',
        'darwin11Guest':'Apple Mac OS X 10.7 (32-bit)',
        'darwin11_64Guest':'Apple Mac OS X 10.7 (64-bit)',
        'asianux3Guest':'Asianux 3 (32-bit)',
        'asianux3_64Guest':'Asianux 3 (64-bit)',
        'asianux4Guest':'Asianux 4 (32-bit)',
        'asianux4_64Guest':'Asianux 4 (64-bit)',
        'centosGuest':'CentOS 4/5/6 (32-bit)',
        'centos64Guest':'CentOS 4/5/6 (64-bit)',
        'debian4Guest':'Debian GNU/Linux 4 (32-bit)',
        'debian4_64Guest':'Debian GNU/Linux 4 (64-bit)',
        'debian5Guest':'Debian GNU/Linux 5 (32-bit)',
        'debian5_64Guest':'Debian GNU/Linux 5 (64-bit)',
        'debian6Guest':'Debian GNU/Linux 6 (32-bit)',
        'debian6_64Guest':'Debian GNU/Linux 6 (64-bit)',
        'freebsdGuest':'FreeBSD (32-bit)',
        'freebsd64Guest':'FreeBSD (64-bit)',
        'os2Guest':'IBM OS/2',
        'dosGuest':'Microsoft MS-DOS',
        'winNetBusinessGuest':'Microsoft Small Business Server 2003',
        'win2000AdvServGuest':'Microsoft Windows 2000',
        'win2000ProGuest':'Microsoft Windows 2000 Professional',
        'win2000ServGuest':'Microsoft Windows 2000 Server',
        'win31Guest':'Microsoft Windows 3.1',
        'windows7Guest':'Microsoft Windows 7 (32-bit)',
        'windows7_64Guest':'Microsoft Windows 7 (64-bit)',
        'windows8Guest':'Microsoft Windows 8 (32-bit)',
        'windows8_64Guest':'Microsoft Windows 8 (64-bit)',
        'win95Guest':'Microsoft Windows 95',
        'win98Guest':'Microsoft Windows 98',
        'winNTGuest':'Microsoft Windows NT',
        'winNetEnterpriseGuest':'Microsoft Windows Server 2003 (32-bit)',
        'winNetEnterprise64Guest':'Microsoft Windows Server 2003 (64-bit)',
        'winNetDatacenterGuest':'Microsoft Windows Server 2003 Datacenter (32-bit)',
        'winNetDatacenter64Guest':'Microsoft Windows Server 2003 Datacenter (64-bit)',
        'winNetStandardGuest':'Microsoft Windows Server 2003 Standard (32-bit)',
        'winNetStandard64Guest':'Microsoft Windows Server 2003 Standard (64-bit)',
        'winNetWebGuest':'Microsoft Windows Server 2003 Web Edition (32-bit)',
        'winLonghornGuest':'Microsoft Windows Server 2008 (32-bit)',
        'winLonghorn64Guest':'Microsoft Windows Server 2008 (64-bit)',
        'windows7Server64Guest':'Microsoft Windows Server 2008 R2 (64-bit)',
        'windows8Server64Guest':'Microsoft Windows Server 2012 (64-bit)',
        'winVistaGuest':'Microsoft Windows Vista (32-bit)',
        'winVista64Guest':'Microsoft Windows Vista (64-bit)',
        'winXPProGuest':'Microsoft Windows XP Professional (32-bit)',
        'winXPPro64Guest':'Microsoft Windows XP Professional (64-bit)',
        'netware5Guest':'Novell NetWare 5.1',
        'netware6Guest':'Novell NetWare 6.x',
        'oesGuest':'Novell Open Enterprise Server',
        'oracleLinuxGuest':'Oracle Linux 4/5/6 (32-bit)',
        'oracleLinux64Guest':'Oracle Linux 4/5/6 (64-bit)',
        'solaris10Guest':'Oracle Solaris 10 (32-bit)',
        'solaris10_64Guest':'Oracle Solaris 10 (64-bit)',
        'solaris11_64Guest':'Oracle Solaris 11 (64-bit)',
        'otherGuest':'Other (32-bit)',
        'otherGuest64':'Other (64-bit)',
        'other24xLinuxGuest':'Other 2.4.x Linux (32-bit)',
        'other24xLinux64Guest':'Other 2.4.x Linux (64-bit)',
        'other26xLinuxGuest':'Other 2.6.x Linux (32-bit)',
        'other26xLinux64Guest':'Other 2.6.x Linux (64-bit)',
        'otherLinuxGuest':'Other Linux (32-bit)',
        'otherLinux64Guest':'Other Linux (64-bit)',
        'rhel2Guest':'Red Hat Enterprise Linux 2.1',
        'rhel3Guest':'Red Hat Enterprise Linux 3 (32-bit)',
        'rhel3_64Guest':'Red Hat Enterprise Linux 3 (64-bit)',
        'rhel4Guest':'Red Hat Enterprise Linux 4 (32-bit)',
        'rhel4_64Guest':'Red Hat Enterprise Linux 4 (64-bit)',
        'rhel5Guest':'Red Hat Enterprise Linux 5 (32-bit)',
        'rhel5_64Guest':'Red Hat Enterprise Linux 5 (64-bit)',
        'rhel6Guest':'Red Hat Enterprise Linux 6 (32-bit)',
        'rhel6_64Guest':'Red Hat Enterprise Linux 6 (64-bit)',
        'openServer5Guest':'SCO OpenServer 5',
        'openServer6Guest':'SCO OpenServer 6',
        'unixWare7Guest':'SCO UnixWare 7',
        'eComStationGuest':'Serenity Systems eComStation 1',
        'eComStation2Guest':'Serenity Systems eComStation 2',
        'solaris8Guest':'Sun Microsystems Solaris 8',
        'solaris9Guest':'Sun Microsystems Solaris 9',
        'sles10Guest':'SUSE Linux Enterprise 10 (32-bit)',
        'sles10_64Guest':'SUSE Linux Enterprise 10 (64-bit)',
        'sles11Guest':'SUSE Linux Enterprise 11 (32-bit)',
        'sles11_64Guest':'SUSE Linux Enterprise 11 (64-bit)',
        'slesGuest':'SUSE Linux Enterprise 8/9 (32-bit)',
        'sles64Guest':'SUSE Linux Enterprise 8/9 (64-bit)',
        'ubuntuGuest':'Ubuntu Linux (32-bit)',
        'ubuntu64Guest':'Ubuntu Linux (64-bit)',
        'vmkernelGuest':'VMware ESX 4.x',
        'vmkernel5Guest':'VMware ESXi 5.x'}
    ip_alloc_modes = ['DHCP','POOL','MANUAL']
    nic_types = ['vlance','flexible','e1000','e1000e','vmxnet','vmxnet2','vmxnet3']
    edge_gateway_nat_types = ['SNAT','DNAT']
    edge_gateway_dnat_protocols = ['TCP','UDP','tcpudp','icmp','any']
    undeploy_power_actions = ['default','powerOff','suspend','shutdown','force']
    firewall_protocols = [['Tcp'],['Udp'],['Tcp','Udp'],['Icmp'],['Any']]
    firewall_policies = ['allow','drop']
    vapp_nat_types = ['ipTranslation','portForwarding']
    vapp_port_forwarding_protocols = ['TCP','UDP','TCP_UDP']
    vapp_ip_translation_mapping_modes = ['automatic','manual']
    icmp_sub_types = ['address-mask-request',
        'address-mask-reply',
        'destination-unreachable',
        'echo-request',
        'echo-reply',
        'parameter-problem',
        'redirect',
        'router-advertisement',
        'router-solicitation',
        'source-quench',
        'time-exceeded',
        'timestamp-request',
        'timestamp-reply',
        'any']
    task_statuses = [None,'queued','preRunning','running','success','error','canceled','aborted']
    vdc_network_types = {'direct':'0','routed':'1','isolated':'2'}
    encryption_protocols = ['AES', 'AES256', 'TRIPLEDES']
    load_balancer_algorithms = ['IP_HASH', 'ROUND_ROBIN', 'URI', 'LEAST_CONN']
    load_balancer_protocols = {'HTTP':'80', 'HTTPS':'443', 'TCP':''}
    load_balancer_healthchecks = {'HTTP':'HTTP','HTTPS':'SSL','TCP':'TCP'}
    load_balancer_persistences = {'HTTP':'COOKIE','HTTPS':'SSL_SESSION_ID','TCP':None}
    load_balancer_cookie_modes = ['INSERT','PREFIX','APP']

    def __init__(self, name):
        self.name = name
        self.href = None
        self.sections = None

    def api_get(self, api_url, headers=None):
        try:
            headers = Container.api_headers if headers is None else headers
            r = requests.get(api_url, headers=headers)
            if r.status_code == requests.codes.ok:
                return r
            else:
                raise ApiError(self.name, r.status_code, r.content)
        except:
            raise

    def api_delete(self, api_url, caller, target_name=None, wait=True):
        try:
            target_name = '' if target_name == None else target_name
            r = requests.delete(api_url, headers = Container.api_headers)
            if r.status_code == requests.codes.accepted:
                task = BeautifulSoup(r.content,'xml').find('Task',attrs={'type':'application/vnd.vmware.vcloud.task+xml'})
                task_success = self.get_task_progress(task['href'],wait) if task != None else True
                if task_success:
                        logger.info("%s %s %s succeeded" % (self.name, caller, target_name))
                else:
                    logger.warning("%s %s %s failed" % (self.name, caller, target_name))
            elif r.status_code == requests.codes.no_content:
                logger.info("%s %s %s succeeded" % (self.name, caller, target_name))
            else:
                raise ApiError(self.name + ' ' + caller + ' ' + target_name, r.status_code, r.content)
            return r
        except:
            raise

    def api_post(self, api_url, expected_r_code, caller, auth=None, headers=None, wait=True):
        try:
            headers = Container.api_headers if headers is None else headers
            r = requests.post(api_url, auth=auth, headers=headers) # href
            if r.status_code == expected_r_code:
                task = BeautifulSoup(r.content,'xml').find('Task',attrs={'type':'application/vnd.vmware.vcloud.task+xml'})
                task_success = self.get_task_progress(task['href'],wait) if task != None else True
                if task_success:
                    logger.info("%s %s succeeded" % (self.name, caller))
                    return r
                else:
                    logger.info("%s %s failed" % (self.name, caller))
                    return None
            else:
                raise ApiError(self.name + ' ' + caller, r.status_code, r.content)
        except:
            raise

    def api_post_params(self, params_type, api_url, params, expected_r_code, caller, target_name, wait=True):
        try:
            api_headers = Container.api_headers.copy()
            api_headers['Content-Type'] = 'application/vnd.vmware.'+ params_type + '+xml'
            r = requests.post(api_url, headers = api_headers, data=params) # href
            if r.status_code == expected_r_code:
                task = BeautifulSoup(r.content,'xml').find('Task',attrs={'type':'application/vnd.vmware.vcloud.task+xml'})
                task_success = self.get_task_progress(task['href'],wait) if task != None else True
                if task_success:
                    logger.info("%s %s %s succeeded" % (self.name, caller, target_name))
                    return r
                else:
                    logger.info("%s %s %s failed" % (self.name, caller, target_name))
                    return None
            else:
                raise ApiError(self.name + ' ' + caller + ' ' + target_name, r.status_code, r.content)
                return None
        except:
            raise

    def api_put_params(self, params_type, api_url, params, expected_r_code, caller, target_name, wait=True):
        try:
            api_headers = Container.api_headers.copy()
            api_headers['Content-Type'] = 'application/vnd.vmware.'+ params_type + '+xml'
            r = requests.put(api_url, headers = api_headers, data=params) # href
            if r.status_code == expected_r_code:
                task = BeautifulSoup(r.content,'xml').find('Task',attrs={'type':'application/vnd.vmware.vcloud.task+xml'})
                task_success = self.get_task_progress(task['href'],wait) if task != None else True
                if task_success:
                    logger.info("%s %s %s succeeded" % (self.name, caller, target_name))
                    return r
                else:
                    logger.info("%s %s %s failed" % (self.name, caller, target_name))
                    return None
            else:
                raise ApiError(self.name + ' ' + caller + ' ' + target_name, r.status_code, r.content)
                return None
        except:
            raise

    def get_record(self, record_type, tag, record_filter=None, detailed=False, show=True):
        try:
            api_url = Container.api_url_prefix + '/query?type=' + record_type + '&format=records'
            api_url += '&filter=(' + record_filter + ')' if record_filter != None and record_filter != '' else ''
            records = []
            r = self.api_get(api_url)
            if r != None:
                records = BeautifulSoup(r.content,'xml').find_all(tag)
                page_size = int(BeautifulSoup(r.content,'xml').QueryResultRecords['pageSize'])            
                total = int(BeautifulSoup(r.content,'xml').QueryResultRecords['total'])
                for i in range(0, total/page_size):
                    next_page_href = BeautifulSoup(r.content,'xml').find('Link',attrs={'rel':'nextPage'})['href']
                    r = self.api_get(next_page_href)
                    records += BeautifulSoup(r.content,'xml').find_all(tag)
            if detailed:
                entities = []
                for record in records:
                    entities.append(self.get_entity(record['href']))
                records = entities
            if show:
                Container.show_records(record_type,records)
            return records
        except:
            raise

    def get_entity(self, entity_href):
        try:
            r = self.api_get(entity_href)
            return r.content if r != None else None
        except:
            raise

    def get_href(self, record_type, tag):
        try:
            links = self.get_record(record_type, tag, 'name==' + self.name,show=False)
            if len(links) == 0:
                logger.info("%s does not exist" % (self.name))
                return None
            elif len(links) > 1:
                logger.info("more than one %s found" % (self.name))
                return None
            else:
                return links[0]['href']
        except:
            raise

    def get_children(self, tag, content_type):
            # how to call in sub-class OrgVdc: super(OrgVdc, self).get_children('VdcStorageProfile', 'application/vnd.vmware.vcloud.vdcStorageProfile+xml')
            entity = self.get_entity(self.href)
            children = {}
            links = BeautifulSoup(entity,'xml').find_all(tag,attrs={'type':content_type})
            if len(links) == 0:
                return None
            else:
                for link in links:
                    link_attrs = dict(link.attrs)
                    children[link_attrs['name']]=link_attrs['href']
                return children

    def get_actions(self):
            entity = self.get_entity(self.href)
            actions = {}
            links = BeautifulSoup(entity,'xml').find_all('Link')
            if len(links) == 0:
                return None
            else:
                for link in links:
                    link_attrs = dict(link.attrs)
                    if 'action' in link_attrs['href']:
                        actions[link_attrs['href'].split('/')[-1]]=link_attrs['href']
                return actions

    def get_section(self, section, show=True):
        try:
            r = self.api_get(self.href + section)
            records = [r.content if r != None else None]
            if show:
                self.show_records(section, records)
            return records[0]
        except:
            raise

    def set_section(self, section, params):
            if str(section) not in self.sections:
                logger.info("%s not in %s" % (section, self.sections.keys()))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], section))
                return
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_put_params('vcloud.' + self.sections[section], self.href + section, params, requests.codes.accepted, inspect.stack()[0][3], section)

    def get_task_progress(self,task_href,show_progress=True,wait=True):
        try:
            while wait:
                r = self.api_get(task_href)
                if r != None:
                    task_status = BeautifulSoup(r.content,'xml').Task['status']
                    task_operation_name = BeautifulSoup(r.content,'xml').Task['operationName']
                    owner = BeautifulSoup(r.content,'xml').find('Owner')
                    task_owner = owner['name'] if owner.has_attr('name') else ''
                    progress = BeautifulSoup(r.content,'xml').Task.find('Progress')
                    if progress != None and show_progress:
                        logger.info("task %s %s progress: %s%%" % (task_operation_name, task_owner, progress.string))
                    if task_status != 'running' and task_status != 'queued':
                        if task_status != 'error':
                            logger.info("task %s %s completed successfully" % (task_operation_name, task_owner))
                            return True
                        else:
                            raise ApiError(task_operation_name + ' ' + task_owner, r.status_code, r.content)
                            return False
                        break
                else:
                    return False
                time.sleep(1)
            return True
        except:
            raise

    def set_task(self,task_href,status): 
            r = self.api_get(task_href)
            if r != None:
                params = BeautifulSoup(r.content,'xml')
                for tag in params.find_all(True):
                    tag.name = 'vcloud:' + tag.name
                params.find('vcloud:Task')['status'] = status
                params.find('vcloud:Task')['xmlns:vcloud'] = 'http://www.vmware.com/vcloud/v1.5'
                params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
                self.api_put_params('vcloud.task', task_href, params, requests.codes.ok, inspect.stack()[0][3], task_href)

    def del_task(self,task_href): 
            r = self.api_get(task_href)
            if r != None:
                task_owner = BeautifulSoup(r.content,'xml').find('Owner')['name']
                task_status = BeautifulSoup(r.content,'xml').Task['status']
                task_operation_name = BeautifulSoup(r.content,'xml').Task['operationName']
            else:
                return False
            r = requests.post(task_href + '/action/cancel', headers = Container.api_headers)
            if r.status_code == requests.codes.no_content:
                self.get_task_progress(task_href,True,False)
                logger.info("task %s %s cancelled" % (task_operation_name, task_owner))
                return True
            else:
                ApiError(task_operation_name + ' ' + task_owner, r.status_code, r.content)
                return False

    def start(self,power_on=True):
            params = BeautifulSoup('<?xml version="1.0" encoding=""?>','xml')
            params.append(Tag(builder=builder.TreeBuilder(),name='DeployVAppParams',attrs={'powerOn':str(power_on).lower(),
                'xmlns':'http://www.vmware.com/vcloud/v1.5'}))
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('vcloud.deployVAppParams', self.href + '/action/deploy', params, requests.codes.accepted, inspect.stack()[0][3], self.name)

    def stop(self,power_action='default'):
            if power_action not in Container.undeploy_power_actions:
                logger.info("%s not in %s" % (power_action,Container.undeploy_power_actions))
                return
            params = BeautifulSoup('<?xml version="1.0" encoding=""?>','xml')
            params.append(Tag(builder=builder.TreeBuilder(),name='UndeployVAppParams',attrs={'xmlns':'http://www.vmware.com/vcloud/v1.5'}))
            params.UndeployVAppParams.append(Tag(builder=builder.TreeBuilder(),name='UndeployPowerAction'))
            params.UndeployVAppParams.UndeployPowerAction.string = power_action
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('vcloud.undeployVAppParams', self.href + '/action/undeploy', params, requests.codes.accepted, inspect.stack()[0][3], self.name)

    def power_on(self):
            self.api_post(self.href + '/power/action/powerOn', requests.codes.accepted, inspect.stack()[0][3])

    def power_off(self):
            self.api_post(self.href + '/power/action/powerOff', requests.codes.accepted, inspect.stack()[0][3])

    def reset(self):
            self.api_post(self.href + '/power/action/reset', requests.codes.accepted, inspect.stack()[0][3])

    def suspend(self):
            self.api_post(self.href + '/power/action/suspend', requests.codes.accepted, inspect.stack()[0][3])

    def discard_suspend(self):
            self.api_post(self.href + '/action/discardSuspendedState', requests.codes.accepted, inspect.stack()[0][3])

    def shutdown(self):
            self.api_post(self.href + '/power/action/shutdown', requests.codes.accepted, inspect.stack()[0][3])

    def reboot(self):
            self.api_post(self.href + '/power/action/reboot', requests.codes.accepted, inspect.stack()[0][3])

    def get_owner(self):
            r = self.api_get(self.href + '/owner')
            return BeautifulSoup(r.content,'xml').Owner.User if r != None else None
            
    def set_owner(self,user_name):
            user_record = self.get_record('user', 'UserRecord', 'name==' + user_name, show=False)
            if len(user_record) == 0:
                logger.info("%s does not exist" % (user_name))
                return
            params = BeautifulSoup('<?xml version="1.0" encoding=""?>','xml')
            params.append(Tag(builder=builder.TreeBuilder(),name='Owner',attrs={'xmlns':'http://www.vmware.com/vcloud/v1.5'}))
            params.Owner.append(Tag(builder=builder.TreeBuilder(),name='User',attrs={'href':user_record[0]['href']}))
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_put_params('vcloud.owner', self.href + '/owner', params, requests.codes.ok, inspect.stack()[0][3], user_name)

    def get_metadata_entries(self):
        records = BeautifulSoup(self.get_section('/metadata',show=False),'xml').find_all('MetadataEntry')
        self.show_records('metadata_entry',records)
        return records

    def add_metadata_entry(self,key,value,value_type='MetadataStringValue',system_domain=False,visibility='READONLY'):
        if len(key) > 256:
            logger.info("%s is too long (>256)" % (key))
            return
        if value_type not in Container.metadata_value_types:
            logger.info("%s not in %s" % (value_type, Container.metadata_value_types))
            return
        if value_type == 'MetadataNumberValue' and not is_number(value):
            logger.info("%s is not a number" %s (value))
            return           
        elif value_type == 'MetadataBooleanValue' and not is_boolean(value):
            logger.info("%s is not a boolean" %s (value))
            return           
        elif value_type == 'MetadataDateTimeValue' and not is_datetime(value):
            logger.info("%s is not a datetime(YYYY-MM-DD HH:MM:SS)" %s (value))
            return
        if system_domain != None and not is_boolean(system_domain):
            logger.info("%s is not a boolean" %s (system_domain))
            return
        if visibility not in Container.metadata_visibilities:
            logger.info("%s not in %s" % (visibility, Container.metadata_visibility))
            return
        params = BeautifulSoup('<?xml version="1.0" encoding=""?>','xml')
        params.append(Tag(builder=builder.TreeBuilder(),name='Metadata',attrs={'xmlns':'http://www.vmware.com/vcloud/v1.5',
            'xmlns:xsi':'http://www.w3.org/2001/XMLSchema-instance'}))
        params.Metadata.append(Tag(builder=builder.TreeBuilder(),name='MetadataEntry'))
        if system_domain == True:
            params.Metadata.append(Tag(builder=builder.TreeBuilder(),name='Domain',attrs={'vsi:type':visibility}))
            params.Metadata.Domain.string = 'SYSTEM'
        params.Metadata.append(Tag(builder=builder.TreeBuilder(),name='Key'))
        params.Metadata.Key.string = str(key)
        params.Metadata.append(Tag(builder=builder.TreeBuilder(),name='TypedValue',attrs={'xsi:type':value_type}))
        params.Metadata.TypedValue.append(Tag(builder=builder.TreeBuilder(),name='Value'))
        params.Metadata.TypedValue.Value.string = str(value)
        params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
        self.api_post_params('vcloud.metadata', self.href + '/metadata', params, requests.codes.accepted, inspect.stack()[0][3], self.name)

    def del_metadata_entry(self,key):
        self.api_delete(self.href + '/metadata/' + key, inspect.stack()[0][3], self.name)

    def get_metadata_entry_value(self,key,system_domain=False):
        domain = 'SYSTEM/' if system_domain == True else ''
        records = BeautifulSoup(self.get_section('/metadata/' + domain + key,show=False),'xml').find_all('MetadataValue')
        self.show_records('metadata_value',records)
        return records[0]

    def set_metadata_entry_value(self,key,value,value_type='MetadataStringValue',system_domain=False):
        domain = 'SYSTEM/' if system_domain == True else ''
        params = BeautifulSoup('<?xml version="1.0" encoding=""?>','xml')
        params.append(Tag(builder=builder.TreeBuilder(),name='MetadataValue',attrs={'xmlns':'http://www.vmware.com/vcloud/v1.5',
            'xmlns:xsi':'http://www.w3.org/2001/XMLSchema-instance'}))
        params.MetadataValue.append(Tag(builder=builder.TreeBuilder(),name='TypedValue',attrs={'xsi:type':value_type})) 
        params.MetadataValue.TypedValue.append(Tag(builder=builder.TreeBuilder(),name='Value'))
        params.MetadataValue.TypedValue.Value.string = value
        params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
        self.api_put_params('vcloud.metadata.value', self.href + '/metadata/' + domain + key, params, requests.codes.accepted, inspect.stack()[0][3], self.name)

    @staticmethod
    def is_hostname(name):
            if len(name) > 255:
                return False
            if name[-1] == ".":
                name = name[:-1] # strip exactly one dot from the right, if present
            # contains at least one character and a maximum of 63 characters
            # consists only of allowed characters
            # doesn't begin or end with a hyphen.
            allowed = re.compile("(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)
            return name if all(allowed.match(x) for x in name.split(".")) else False

    @staticmethod
    def is_valid_name(name):
            """
            https://kb.vmware.com/selfservice/microsites/search.do?language=en_US&cmd=displayKC&externalId=2011305
            """
            if name == None:
                return True
            if len(name) > 128:
                return False
            allowed = re.compile("[A-Z\d.-_]+", re.IGNORECASE)
            return name if all(allowed.match(x) for x in list(name)) else False

    @staticmethod
    def is_valid_computer_name(name):
            if len(name) > 15:
                return False
            allowed = re.compile("[A-Z\d.-_]+", re.IGNORECASE)
            return name if all(allowed.match(x) for x in list(name)) else False

    @staticmethod
    def is_number(x):
        try:
            complex(x) # for int, long, float and complex
        except ValueError:
            return False
        return True
    
    @staticmethod
    def is_boolean(x):
        return True if type(x) == type(True) else False

    @staticmethod
    def is_datetime(x):
        try:
            datetime.datetime.strptime(x, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            return False
        return True

    @staticmethod
    def is_email(x):
        return True if re.match("[\w\.\-\+]*@[\w\.\-]*\.\w+", str(x)) else False

    @staticmethod
    def is_valid_password(x):
        if len(x) < 8 or len(x) > 16:
            logger.info("password length must be between 8 to 16")
            return False
        if not re.search(r'[A-Z]', x):
            logger.info("password must include upper case")
            return False
        if not re.search(r'[a-z]', x):
            logger.info("password must include lower case")
            return False
        if not re.search(r'[0-9]', x):
            logger.info("password must include digits")
            return False
        return True

    @staticmethod
    def convertYaml2Xml(in_yaml):
        try:
            inobj = []
            inobj.append(yaml.load(in_yaml))
            level = 0
            out = []
            Container.convertYaml2XmlAux(inobj, level, out)
            return "".join(out)
        except:
            raise

    @staticmethod
    def convertYaml2XmlAux(inobj, level, out):
        try:
            for obj in inobj:
                # get from yaml 
                name = None
                attributes = None
                text = None
                children = None
                name,data = obj.items()[0]
                if type(data) is list:
                    key,value = data[0].items()[0]
                    if key == 'attributes':
                        attributes = value
                        if len(data) > 1:
                            children = data[1:]
                    else:
                        children = data
                else:
                    text = data
                # convert to xml
                for idx in range(level):
                    out.append('    ')
                if name:
                    out.append('<%s' % name)
                if attributes:
                    for obj in attributes:
                        out.append(' %s="%s"' % (obj, attributes[obj]))
                if not (children or text):
                    out.append('/>\n')
                else:
                    if children:
                        out.append('>\n')
                    else:
                        out.append('>')
                    if text:
                        out.append(text)
                    if children:
                        Container.convertYaml2XmlAux(children, level + 1, out)
                        for idx in range(level):
                            out.append('    ')
                    out.append('</%s>\n' % name)
        except:
            raise

    @staticmethod
    def convertXml2Yaml(in_xml):
        try:
            # replace xmlns to suppress namespace on tag
            # parser recover=True to tolerate undeclared prefix
            root = etree.fromstring(str(in_xml).replace('xmlns','xmlnamespace'),etree.XMLParser(recover=True,ns_clean=True))
            # Convert the DOM tree into "YAML-able" data structures.
            out = Container.convertXml2YamlAux(root)
            # Ask YAML to dump the data structures to a string.
            return yaml.safe_dump(out,default_flow_style=False)
        except:
            raise

    @staticmethod
    def convertXml2YamlAux(obj):
        try:
            objDict = {}
            # Add the element name.
            nodeName = str(obj.tag)
            objDict[nodeName] = None
            children = []
            # Convert the attributes to first member of children
            if len(obj.attrib) > 0:
                children.append({'attributes':dict(obj.attrib)})
            # Convert the text.
            if obj.text != None:
                objDict[nodeName] = str(obj.text)
            # Convert the children
            for child in obj:
                obj = Container.convertXml2YamlAux(child)
                children.append(obj)
            if children:
                objDict[nodeName] = list(children)
            return objDict
        except:
            raise
    
    def isAllWhiteSpace(self,text):
            NonWhiteSpacePattern = re.compile('\S')
            if NonWhiteSpacePattern.search(text):
                return 0
            return 1

    @staticmethod
    def show_records(record_type,records):
        try:
            if records == None:
                return
            for i in range(len(records)):
                logger.info("%s[%d]:" % (record_type,i) + "\n" + Container.convertXml2Yaml(str(records[i])))
            logger.info("%d %s found" % (len(records),record_type))
        except:
            raise
 
    @staticmethod
    def handle_exception(exc):
        exc_type, exc_value, exc_tb = exc
        if 'ApiError' in str(exc_type):
            logger.exception('')
            #os._exit(1) # terminate without exception
        else:
            logger.exception('')

class UploadInChunks(Container):
    def __init__(self, file_path, offset, chunksize=1 << Container.max_chunk_size):
        self.file_path = file_path
        self.chunksize = chunksize
        self.totalsize = os.path.getsize(file_path)
        self.readsofar = offset

    def __iter__(self):
        with open(self.file_path, 'rb') as file:
            file.seek(self.readsofar)
            while True:
                data = file.read(self.chunksize)
                if not data:
                    sys.stderr.write("\n")
                    break
                self.readsofar += len(data)
                percent = self.readsofar * 1e2 / self.totalsize
                sys.stderr.write("\rupload {} {} progress:{percent:3.0f}%".format(self.file_path,self.readsofar,percent=percent))
                yield data

    def __len__(self):
        return self.totalsize

class Session(Container):
    
    def __init__(self, alias):
        try:
            logger.debug("get credential from config by alias then connect")
            with open(Container.conf_path, 'r') as conf_file:
                credentials = yaml.load(conf_file)['credentials']
            for credential in credentials:
                if credential['credential']['alias'] == alias:
                    break
            else:
                raise ValueError("%s does not exist" % (alias))
            self.hostname = credential['credential']['host']
            Container.api_url_prefix = "https://" + self.hostname + "/api" 
            self.org_name = credential['credential']['org']
            Container.session_org_name = self.org_name
            self.username = credential['credential']['user']
            self.password = credential['credential']['pass']
            Container.__init__(self, self.username + '@' + self.org_name + '@' + self.hostname)
            self.token = None
            self.href = self.connect()
        except:
            Container.handle_exception(sys.exc_info())

    def connect(self):
        try:
            logger.debug("set api_vesion to highest supported")
            api_url = Container.api_url_prefix + "/versions"
            r = self.api_get(api_url)
            tags = BeautifulSoup(r.content,'xml').SupportedVersions.find_all('Version')
            versions = []
            for tag in tags:
                versions.append(float(tag.string))
            Container.api_headers = {'Accept':'application/*+xml;version=' + str(max(versions)),'Accept-Encoding':'gzip'}

            logger.debug("try reuse existing session")
            open(Container.session_file_path, "a").close() # touch
            with open(Container.session_file_path,"r") as session_file:
                sessions = yaml.load(session_file)
                sessions = [] if sessions is None else sessions
            api_user = self.username + "@" + self.org_name
            for session in sessions:
                if session['session']['host'] == self.hostname and session['session']['user'] == api_user :
                    api_url = Container.api_url_prefix + "/session/"  
                    api_headers = Container.api_headers.copy()
                    api_headers.update({'x-vcloud-authorization':session['session']['token']})
                    r = requests.get(api_url, headers=api_headers)
                    if r.status_code == requests.codes.ok:
                        self.token = session['session']['token']
                        Container.api_headers.update({'x-vcloud-authorization':self.token})
                        logger.info("%s re%s succeeded" % (self.name, inspect.stack()[0][3]))
                        return BeautifulSoup(r.content,'xml').Session['href']
                    else:
                        sessions.remove(session)

            logger.debug("create new session")
            api_url = Container.api_url_prefix + "/sessions"  
            api_auth = requests.auth.HTTPBasicAuth(api_user,self.password)
            r = self.api_post(api_url, requests.codes.ok, inspect.stack()[0][3], auth=api_auth)
            self.token = r.headers.get('x-vcloud-authorization')
            Container.api_headers.update({'x-vcloud-authorization':self.token})
            sessions.append({'session':{'host':self.hostname,'user':api_user,'token':self.token}})
            with open(Container.session_file_path, "w") as session_file:
                session_file.write(yaml.safe_dump(sessions,default_flow_style=False))
            return BeautifulSoup(r.content,'xml').Session['href']
        except:
            Container.handle_exception(sys.exc_info())

    def disconnect(self):
        try:
            logger.debug("disconnect and delete session")
            r = self.api_delete(self.href, inspect.stack()[0][3])
            with open(Container.session_file_path, "r+") as session_file:
                sessions = yaml.load(session_file)
                sessions = [] if sessions is None else sessions
            for session in sessions:
                if session['session']['token'] == self.token:
                    sessions.remove(session)
            with open(Container.session_file_path, "w") as session_file:
                session_file.write(yaml.safe_dump(sessions,default_flow_style=False))
        except:
            Container.handle_exception(sys.exc_info())
 
class Org(Container):
    
    def __init__(self, name=None):
        if name == None:
           name = Container.session_org_name
        Container.__init__(self, name)
        self.href = self.get_href()
        self.admin_href = self.href.replace('/api','/api/admin')

    ### orgadmin,sysadmin ###

    def get_href(self):
        try:
            r = self.api_get(Container.api_url_prefix + '/org')
            return BeautifulSoup(r.content,'xml').find('Org')['href'] if r != None else None
        except:
            Container.handle_exception(sys.exc_info())

    def get_settings(self, show=True):
        try:
            r = self.api_get(self.admin_href + '/settings')
            records = [r.content] if r != None else []
            if show:
                self.show_records('OrgSettings',records)
            return records
        except:
            Container.handle_exception(sys.exc_info())

    def get_settings_ldap(self, show=True):
        try:
            r = self.api_get(self.admin_href + '/settings/ldap')
            records = [r.content] if r != None else []
            if show:
                self.show_records('OrgSettingsLdap',records)
            return records
        except:
            Container.handle_exception(sys.exc_info())

    def get_settings_federation(self, show=True):
        try:
            r = self.api_get(self.admin_href + '/settings/federation')
            records = [r.content] if r != None else []
            if show:
                self.show_records('OrgSettingsFederation',records)
            return records
        except:
            Container.handle_exception(sys.exc_info())

    def get_orgvdc(self,name=None,detailed=False,show=True):
        try:
            record_filter = 'name==' + name if name != None else ''
            return self.get_record('orgVdc', 'OrgVdcRecord', record_filter, detailed=detailed, show=show)
        except:
            Container.handle_exception(sys.exc_info())

    def get_network(self,name=None,detailed=False,show=True):
        try:
            record_filter = 'org==' + self.href
            record_filter += ';name==' +name if name != None else ''
            return self.get_record('orgNetwork', 'OrgNetworkRecord', record_filter, detailed=detailed, show=show)
        except:
            Container.handle_exception(sys.exc_info())

    def get_catalog(self,name=None,detailed=False,show=True):
        try:
            record_filter = 'name==' + name if name != None else ''
            return self.get_record('catalog', 'CatalogRecord', record_filter, detailed=detailed, show=show)
        except:
            Container.handle_exception(sys.exc_info())

    def add_catalog(self,catalog_name):
        try:
            catalog_record = self.get_record('catalog', 'CatalogRecord', 'name==' + catalog_name +';orgName==' + self.name, show=False)
            if len(catalog_record) > 0:
                logger.info("%s already exist in %s" % (catalog_name,self.name))
                return
            params = BeautifulSoup('<?xml version="1.0" encoding=""?>','xml')
            params.append(Tag(builder=builder.TreeBuilder(),name='vcloud:AdminCatalog',attrs={'name':catalog_name,
                'xmlns:vcloud':'http://www.vmware.com/vcloud/v1.5'}))
            params.find('vcloud:AdminCatalog').append(Tag(builder=builder.TreeBuilder(),name='vcloud:Description'))
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.catalog', self.admin_href + '/catalogs', params, requests.codes.created, inspect.stack()[0][3], catalog_name)
        except:
            Container.handle_exception(sys.exc_info())

    def del_catalog(self,catalog_name):
        try:
            catalog_record = self.get_record('catalog', 'CatalogRecord', 'name==' + catalog_name +';orgName==' + self.name, show=False)
            if len(catalog_record) == 0:
                logger.info("%s does not exist in %s" % (catalog_name,self.name))
                return
            self.api_delete(catalog_record[0]['href'].replace('/api','/api/admin'), inspect.stack()[0][3], catalog_name)
        except:
            Container.handle_exception(sys.exc_info())

    def get_right(self, name=None, detailed=False, show=True):
        try:
            record_filter = 'name==' + name if name != None else ''
            return self.get_record('right', 'RightRecord', record_filter, detailed=detailed, show=show)
        except:
            Container.handle_exception(sys.exc_info())

    def get_role(self, name=None, detailed=False, show=True):
        try:
            record_filter = 'name==' + name if name != None else ''
            return self.get_record('role', 'RoleRecord', record_filter, detailed=detailed, show=show)
        except:
            Container.handle_exception(sys.exc_info())

    def set_role(self,role_name,name=None,role_right_names=None):
        try:
            role_record = self.get_record('role', 'RoleRecord', 'name==' + role_name, show=False)
            if len(role_record) == 0:
                logger.info("%s does not exist in %s" % (role_name,self.name))
                return
            role_entity = self.get_entity(role_record[0]['href'])
            params = BeautifulSoup(role_entity,'xml')
            if name != None:
                params.Role['name'] = name
            if role_right_names != None:
                current_rights = []
                for current_right in params.Role.RightReferences.find_all('RightReference',recursive=False):
                    current_right.extract()
                for role_right_name in role_right_names:
                    right_record = self.get_record('right', 'RightRecord', 'name==' + role_right_name, show=False)
                    if len(right_record) == 0:
                        logger.info("%s does not exist in %s" % (role_right_name,self.name))
                        return
                    right = Tag(builder=builder.TreeBuilder(),name='RightReference',attrs={'href':right_record[0]['href'],
                        'name':right_record[0]['name']}) 
                    params.Role.RightReferences.append(right)
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_put_params('admin.role', role_record[0]['href'], params, requests.codes.ok, inspect.stack()[0][3], role_name)
        except:
            Container.handle_exception(sys.exc_info())

    def add_role(self,role_name,role_right_names):
        try:
            role_record = self.get_record('role', 'RoleRecord', 'name==' + role_name, show=False)
            if len(role_record) > 0:
                logger.info("%s already exist in %s" % (role_name,self.name))
                return
            params = BeautifulSoup('<?xml version="1.0" encoding=""?>','xml')
            params.append(Tag(builder=builder.TreeBuilder(),name='Role',attrs={'name':role_name,
                'xmlns':'http://www.vmware.com/vcloud/v1.5'}))
            params.Role.append(Tag(builder=builder.TreeBuilder(),name='Description'))
            if role_right_names != None:
                params.Role.append(Tag(builder=builder.TreeBuilder(),name='RightReferences'))
                for role_right_name in role_right_names:
                    right_record = self.get_record('right', 'RightRecord', 'name==' + role_right_name, show=False)
                    if len(right_record) == 0:
                        logger.info("%s does not exist in %s" % (role_right_name,self.name))
                        return
                    right = Tag(builder=builder.TreeBuilder(),name='RightReference',attrs={'href':right_record[0]['href'],
                        'name':right_record[0]['name']}) 
                    params.Role.RightReferences.append(right)
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.role', self.admin_href + '/roles', params, requests.codes.created, inspect.stack()[0][3], role_name)
        except:
            Container.handle_exception(sys.exc_info())
 
    def del_role(self,role_name):
        try:
            role_record = self.get_record('role', 'RoleRecord', 'name==' + role_name, show=False)
            if len(role_record) == 0:
                logger.info("%s does not exist in %s" % (role_name,self.name))
                return
            self.api_delete(role_record[0]['href'], inspect.stack()[0][3], role_name)
        except:
            Container.handle_exception(sys.exc_info())

    def get_user(self, name=None, detailed=True, show=True):
        try:
            record_filter = 'name==' + name if name != None else ''
            return self.get_record('user', 'UserRecord', record_filter, detailed=detailed, show=show)
        except:
            Container.handle_exception(sys.exc_info())

    def set_user(self,user_name,full_name=None,enable=None,email=None,role_name=None,password=None):
        try:
            user_record = self.get_record('user', 'UserRecord', 'name==' + user_name, show=False)
            if len(user_record) == 0:
                logger.info("%s does not exist in %s" % (user_name,self.name))
                return
            user_entity = self.get_entity(user_record[0]['href'])
            params = BeautifulSoup(user_entity,'xml')
            if enable != None:
                params.User.IsEnabled.string = str(enable).lower() 
            if full_name != None:
                params.User.FullName.string = full_name 
            if email != None:
                params.User.EmailAddress.string = email 
            if role_name != None:
                role_record = self.get_record('role', 'RoleRecord' , 'name==' + role_name, show=False)
                if len(role_record) == 0:
                    logger.info("%s does not exist in %s" % (role_name,self.name))
                    return
                params.User.Role['href'] = role_record[0]['href']
            if params.User.IsExternal.string == 'true' and password != None:
                logger.info("only local user password can be changed")
            if params.User.IsExternal.string == 'false' and password != None:
                params.User.Role.insert_after(Tag(builder=builder.TreeBuilder(),name='Password'))
                params.User.Password.string = password 
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_put_params('admin.user', user_record[0]['href'], params, requests.codes.ok, inspect.stack()[0][3], user_name)
        except:
            Container.handle_exception(sys.exc_info())

    def add_user(self,user_name,full_name=None,email=None,enable=True,provider_type=None,external=True,role_name=None,password=None):
        try:
            user_record = self.get_record('user', 'UserRecord', 'name==' + user_name, show=False)
            if len(user_record) > 0:
                logger.info("%s already exist in %s" % (user_name,self.name))
                return
            params = BeautifulSoup('<?xml version="1.0" encoding=""?>','xml')
            params.append(Tag(builder=builder.TreeBuilder(),name='User',attrs={'name':user_name,
                'xmlns':'http://www.vmware.com/vcloud/v1.5'}))
            if full_name != None:
                params.User.append(Tag(builder=builder.TreeBuilder(),name='FullName'))
                params.User.FullName.string = full_name
            if email != None:
                params.User.append(Tag(builder=builder.TreeBuilder(),name='EmailAddress'))
                params.User.EmailAddress.string = email
            if enable != None:
                params.User.append(Tag(builder=builder.TreeBuilder(),name='IsEnabled'))
                params.User.IsEnabled.string = str(enable).lower() 
            if provider_type != None:
                if provider_type.upper() not in self.identity_provider_types:
                    logger.info("%s not in %s" % (provider_type,self.identity_provider_types))
                    return
                params.User.append(Tag(builder=builder.TreeBuilder(),name='ProviderType'))
                params.User.ProviderType.string = provider_type.upper()
                external = None
            if external != None:
                params.User.append(Tag(builder=builder.TreeBuilder(),name='IsExternal'))
                params.User.IsExternal.string = str(external).lower() 
            if role_name != None:
                role_record = self.get_record('role', 'RoleRecord' , 'name==' + role_name, show=False)
                if len(role_record) == 0:
                    logger.info("%s does not exist in %s" % (role_name,self.name))
                    return
                params.User.append(Tag(builder=builder.TreeBuilder(),name='Role',attrs={'href':role_record[0]['href']}))
            else:
                logger.info("role_name must be specified")
                return
            if external and password != None:
                logger.info("only local user password can be specified")
            if not external and password != None:
                params.User.Role.insert_after(Tag(builder=builder.TreeBuilder(),name='Password'))
                params.User.Password.string = password 
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.user', self.admin_href + '/users', params, requests.codes.created, inspect.stack()[0][3], user_name)
        except:
            Container.handle_exception(sys.exc_info())
  
    def del_user(self,user_name):
        try:
            user_record = self.get_record('user', 'UserRecord', 'name==' + user_name, show=False)
            if len(user_record) == 0:
                logger.info("%s does not exist in %s" % (user_name,self.name))
                return
            self.api_delete(user_record[0]['href'], inspect.stack()[0][3], user_name)
        except:
            Container.handle_exception(sys.exc_info())
 
    def get_group(self, name=None, detailed=False, show=True):
        try:
            record_filter = 'name==' + name if name != None else ''
            return self.get_record('group', 'GroupRecord', record_filter, detailed=detailed, show=show)
        except:
            Container.handle_exception(sys.exc_info())

    def set_group(self,group_name,role_name=None):
        try:
            group_record = self.get_record('group', 'GroupRecord', 'name==' + group_name, show=False)
            if len(group_record) == 0:
                logger.info("%s does not exist in %s" % (group_name,self.name))
                return
            group_entity = self.get_entity(group_record[0]['href'])
            params = BeautifulSoup(group_entity,'xml')
            if role_name != None:
                role_record = self.get_record('role', 'RoleRecord' , 'name==' + role_name, show=False)
                if len(role_record) == 0:
                    logger.info("%s does not exist in %s" % (role_name,self.name))
                    return
                params.Group.Role['href'] = role_record[0]['href']
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_put_params('admin.group', group_record[0]['href'], params, requests.codes.ok, inspect.stack()[0][3], group_name)
        except:
            Container.handle_exception(sys.exc_info())

    def add_group(self,group_name,role_name=None,provider_type=None):
        try:
            group_record = self.get_record('group', 'GroupRecord', 'name==' + group_name, show=False)
            if len(group_record) > 0:
                logger.info("%s already exist in %s" % (group_name,self.name))
                return
            params = BeautifulSoup('<?xml version="1.0" encoding=""?>','xml')
            params.append(Tag(builder=builder.TreeBuilder(),name='Group',attrs={'name':group_name,
                'xmlns':'http://www.vmware.com/vcloud/v1.5'}))
            if provider_type != None:
                if provider_type.upper() not in self.identity_provider_types:
                    logger.info("%s not in %s" % (provider_type,self.identity_provider_types))
                    return
                params.Group.append(Tag(builder=builder.TreeBuilder(),name='ProviderType'))
                params.Group.ProviderType.string = provider_type.upper()
            if role_name != None:
                role_record = self.get_record('role', 'RoleRecord' , 'name==' + role_name, show=False)
                if len(role_record) == 0:
                    logger.info("%s does not exist in %s" % (role_name,self.name))
                    return
                params.Group.append(Tag(builder=builder.TreeBuilder(),name='Role',attrs={'href':role_record[0]['href']}))
            else:
                logger.info("role_name must be specified")
                return
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.group', self.admin_href + '/groups', params, requests.codes.created, inspect.stack()[0][3], group_name)
        except:
            Container.handle_exception(sys.exc_info())

    def del_group(self,group_name):
        try:
            group_record = self.get_record('group', 'GroupRecord', 'name==' + group_name, show=False)
            if len(group_record) == 0:
                logger.info("%s does not exist in %s" % (group_name,self.name))
                return
            self.api_delete(group_record[0]['href'], inspect.stack()[0][3], group_name)
        except:
            Container.handle_exception(sys.exc_info())

    def set_ownership(self,user_name):
        try:
            user_record = self.get_record('user', 'UserRecord', 'name==' + user_name, show=False)
            if len(user_record) == 0:
                logger.info("%s does not exist in %s" % (user_name,self.name))
                return
            self.api_post(user_record[0]['href'] + '/action/takeOwnership', requests.codes.no_content, inspect.stack()[0][3])
        except:
            Container.handle_exception(sys.exc_info())

    ### sysadmin only ### 

    def get_system_settings(self):
        try:
            records = [self.get_entity(Container.api_url_prefix + '/admin/extension/settings')]
            self.show_records('systemSettings',records)
            return records
        except:
            Container.handle_exception(sys.exc_info())

    def set_system_settings(self,allow_overlapping_extnet):
        try:
            system_settings = self.get_entity(Container.api_url_prefix + '/admin/extension/settings')
            params = BeautifulSoup(system_settings,'xml')
            params.find('SystemSettings').find('GeneralSettings').find('AllowOverlappingExtNets').string = str(allow_overlapping_extnet).lower()
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_put_params('admin.systemSettings', Container.api_url_prefix + '/admin/extension/settings', params, requests.codes.ok, inspect.stack()[0][3], self.name)
        except:
            Container.handle_exception(sys.exc_info())

    def get_org(self, name=None, detailed=False, show=True):
        try:
            record_filter = 'name==' + name if name != None else ''
            return self.get_record('organization', 'OrgRecord', record_filter, detailed=detailed, show=show)
        except:
            Container.handle_exception(sys.exc_info())

    def set_org(self,org_name,enable=True):
        try:
            org_record = self.get_record('organization', 'OrgRecord', 'name==' + org_name, show=False)
            if len(org_record) == 0:
                logger.info("%s does not exist in %s" % (org_name,self.name))
                return
            if enable:
                self.api_post(org_record[0]['href'].replace('/api','/api/admin') + '/action/enable', requests.codes.no_content, inspect.stack()[0][3])
            else:
                self.api_post(org_record[0]['href'].replace('/api','/api/admin') + '/action/disable', requests.codes.no_content, inspect.stack()[0][3])
        except:
            Container.handle_exception(sys.exc_info())

    def add_org(self,org_name,org_ldap_mode=None,custom_users_ou=None,enable=True):
        try:
            org_record = self.get_record('organization', 'OrgRecord', 'name==' + org_name, show=False)
            if len(org_record) > 0:
                logger.info("%s already exist in %s" % (org_name,self.name))
                return
            params = BeautifulSoup('<?xml version="1.0" encoding=""?>','xml')
            params.append(Tag(builder=builder.TreeBuilder(),name='AdminOrg',attrs={'name':org_name,
                'xmlns':'http://www.vmware.com/vcloud/v1.5'}))
            params.AdminOrg.append(Tag(builder=builder.TreeBuilder(),name='FullName'))
            params.AdminOrg.FullName.string = org_name
            params.AdminOrg.append(Tag(builder=builder.TreeBuilder(),name='IsEnabled'))
            params.AdminOrg.IsEnabled.string = str(enable).lower()
            params.AdminOrg.append(Tag(builder=builder.TreeBuilder(),name='Settings'))
            params.AdminOrg.Settings.append(Tag(builder=builder.TreeBuilder(),name='VAppLeaseSettings'))
            params.AdminOrg.Settings.VAppLeaseSettings.append(Tag(builder=builder.TreeBuilder(),name='DeploymentLeaseSeconds'))
            params.AdminOrg.Settings.VAppLeaseSettings.DeploymentLeaseSeconds.string = '0'
            params.AdminOrg.Settings.VAppLeaseSettings.append(Tag(builder=builder.TreeBuilder(),name='StorageLeaseSeconds'))
            params.AdminOrg.Settings.VAppLeaseSettings.StorageLeaseSeconds.string = '0'
            params.AdminOrg.Settings.VAppLeaseSettings.append(Tag(builder=builder.TreeBuilder(),name='PowerOffOnRuntimeLeaseExpiration'))
            params.AdminOrg.Settings.VAppLeaseSettings.PowerOffOnRuntimeLeaseExpiration.string = 'false'
            #params.AdminOrg.Settings.VAppLeaseSettings.append(Tag(builder=builder.TreeBuilder(),name='DeleteOnStorageLeaseExpiration'))
            #params.AdminOrg.Settings.VAppLeaseSettings.DeleteOnStorageLeaseExpiration.string = 'false'
            params.AdminOrg.Settings.append(Tag(builder=builder.TreeBuilder(),name='VAppTemplateLeaseSettings'))
            params.AdminOrg.Settings.VAppTemplateLeaseSettings.append(Tag(builder=builder.TreeBuilder(),name='StorageLeaseSeconds'))
            params.AdminOrg.Settings.VAppTemplateLeaseSettings.StorageLeaseSeconds.string = '0'
            #params.AdminOrg.Settings.VAppTemplateLeaseSettings.append(Tag(builder=builder.TreeBuilder(),name='DeleteOnStorageLeaseExpiration'))
            #params.AdminOrg.Settings.VAppTemplateLeaseSettings.DeleteOnStorageLeaseExpiration.string = 'false'
            if org_ldap_mode == 'SYSTEM' and custom_users_ou == None:
                logger.info("custom_users_ou must be specified for SYSTEM org_ldap_mode")
                return
            if org_ldap_mode == 'SYSTEM' and custom_users_ou != None:
                params.AdminOrg.Settings.append(Tag(builder=builder.TreeBuilder(),name='OrgLdapSettings'))
                params.AdminOrg.Settings.OrgLdapSettings.append(Tag(builder=builder.TreeBuilder(),name='OrgLdapMode'))
                params.AdminOrg.Settings.OrgLdapSettings.OrgLdapMode.string = org_ldap_mode
                params.AdminOrg.Settings.OrgLdapSettings.append(Tag(builder=builder.TreeBuilder(),name='CustomUsersOu'))
                params.AdminOrg.Settings.OrgLdapSettings.CustomUsersOu.string = custom_users_ou
            #params.AdminOrg.Settings.append(Tag(builder=builder.TreeBuilder(),name='OrgEmailSettings'))
            #params.AdminOrg.Settings.append(Tag(builder=builder.TreeBuilder(),name='OrgPasswordPolicySettings'))
            #params.AdminOrg.Settings.append(Tag(builder=builder.TreeBuilder(),name='OrgOperationLimitsSettings'))
            #params.AdminOrg.Settings.append(Tag(builder=builder.TreeBuilder(),name='OrgFederationSettings'))
            #params.AdminOrg.Settings.append(Tag(builder=builder.TreeBuilder(),name='OrgOAuthSettings'))
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            logger.debug(params)
            self.api_post_params('admin.organization', Container.api_url_prefix + '/admin/orgs', params, requests.codes.created, inspect.stack()[0][3], org_name)
        except:
            Container.handle_exception(sys.exc_info())

    def del_org(self,org_name):
        try:
            org_record = self.get_record('organization', 'OrgRecord', 'name==' + org_name, show=False)
            if len(org_record) == 0:
                logger.info("%s does not exist in %s" % (org_name,self.name))
                return
            self.api_delete(org_record[0]['href'].replace('/api','/api/admin'), inspect.stack()[0][3], org_name)
        except:
            Container.handle_exception(sys.exc_info())

    def get_cell(self, detailed=False, show=True):
        try:
            return self.get_record('cell', 'CellRecord', detailed=detailed, show=show)
        except:
            Container.handle_exception(sys.exc_info())

    def get_providervdc(self, name=None, detailed=False, show=True):
        try:
            record_filter = 'name==' + name if name != None else ''
            return self.get_record('providerVdc', 'VMWProviderVdcRecord', record_filter, detailed=detailed, show=show)
        except:
            Container.handle_exception(sys.exc_info())

    def add_providervdc(self,providervdc_name,vcenter_name,resource_pool_name,storage_profile_name,enable=True):
        try:
            providervdc_record = self.get_record('providerVdc', 'VMWProviderVdcRecord', 'name==' + providervdc_name, show=False)
            if len(providervdc_record) > 0:
                logger.info("%s already exist in %s" % (providervdc_name,self.name))
                return
            params = BeautifulSoup('<?xml version="1.0" encoding=""?>','xml')
            params.append(Tag(builder=builder.TreeBuilder(),name='VMWProviderVdcParams',attrs={'name':providervdc_name,
                'xmlns':'http://www.vmware.com/vcloud/extension/v1.5',
                'xmlns:vcloud':'http://www.vmware.com/vcloud/v1.5'}))
            params.VMWProviderVdcParams.append(Tag(builder=builder.TreeBuilder(),name='ResourcePoolRefs'))
            params.VMWProviderVdcParams.ResourcePoolRefs.append(Tag(builder=builder.TreeBuilder(),name='VimObjectRef'))
            vcenter=Vcenter(vcenter_name)
            params.VMWProviderVdcParams.ResourcePoolRefs.VimObjectRef.append(Tag(builder=builder.TreeBuilder(),name='VimServerRef',attrs={'href':vcenter.href}))
            resource_pool = vcenter.get_resource_pool(resource_pool_name, show=False)
            params.VMWProviderVdcParams.ResourcePoolRefs.VimObjectRef.append(Tag(builder=builder.TreeBuilder(),name='MoRef'))
            params.VMWProviderVdcParams.ResourcePoolRefs.VimObjectRef.MoRef.string = resource_pool.find('MoRef').string
            params.VMWProviderVdcParams.ResourcePoolRefs.VimObjectRef.append(Tag(builder=builder.TreeBuilder(),name='VimObjectType'))
            params.VMWProviderVdcParams.ResourcePoolRefs.VimObjectRef.VimObjectType.string = 'RESOURCE_POOL'
            params.VMWProviderVdcParams.append(Tag(builder=builder.TreeBuilder(),name='VimServer',attrs={'href':vcenter.href}))
            params.VMWProviderVdcParams.append(Tag(builder=builder.TreeBuilder(),name='IsEnabled'))
            params.VMWProviderVdcParams.IsEnabled.string=str(enable).lower()
            storage_profile = BeautifulSoup(vcenter.get_storage_profile(show=False),'xml').find('VMWStorageProfile',attrs={'name':storage_profile_name})
            if storage_profile == None:
                logger.info("%s does not exist" % (storage_profile_name))
            params.VMWProviderVdcParams.append(Tag(builder=builder.TreeBuilder(),name='StorageProfile'))
            params.VMWProviderVdcParams.StorageProfile.string = storage_profile_name
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.createProviderVdcParams', Container.api_url_prefix + '/admin/extension/providervdcsparams', params, requests.codes.created, inspect.stack()[0][3], providervdc_name)
        except:
            Container.handle_exception(sys.exc_info())

    def del_providervdc(self,providervdc_name):
        try:
            providervdc_record = self.get_record('providerVdc', 'VMWProviderVdcRecord', 'name==' + providervdc_name, show=False)
            if len(providervdc_record) == 0:
                logger.info("%s does not exist in %s" % (providervdc_name,self.name))
                return
            self.api_delete(providervdc_record[0]['href'].replace('/api/admin','/api/admin/extension'), inspect.stack()[0][3], providervdc_name)
        except:
            Container.handle_exception(sys.exc_info())

    def get_adminvdc(self,org_name=None,name=None,detailed=False,show=True):
        try:
            record_filter = 'orgName==' + org_name if org_name != None and org_name != 'system' else ''
            record_filter += ';name==' + name if name != None else ''
            return self.get_record('adminOrgVdc', 'AdminVdcRecord', record_filter, detailed=detailed, show=show)
        except:
            Container.handle_exception(sys.exc_info())

    def add_adminvdc(self,org_name,adminvdc_name,allocation_model,cpu_limit_ghz,memory_limit_gb,storage_limit_gb,storage_profile_name,memory_reserve_pc,cpu_reserve_pc,network_pool_name,providervdc_name,adopt_resource_pools=False,enable=True,enable_thin_provision=False,enable_fast_provision=False,allow_overcommit=False,vcpu_in_mhz=2000):
        try:
            if allocation_model not in self.allocation_models:
                logger.info("%s not in %s" % (allocation_model,self.allocation_models))
                return
            org = Org('org_name')
            orgvdc_record = self.get_record('adminOrgVdc', 'AdminVdcRecord', 'name==' + adminvdc_name + ';orgName==' + org.name, show=False)
            if len(orgvdc_record) > 0:
                logger.info("%s already exist in %s" % (adminvdc_name,org.name))
                return
            params = BeautifulSoup('<?xml version="1.0" encoding=""?>','xml')
            params.append(Tag(builder=builder.TreeBuilder(),name='CreateVdcParams',attrs={'name':adminvdc_name,
                'xmlns:vmext':'http://www.vmware.com/vcloud/extension/v1.5',
                'xmlns':'http://www.vmware.com/vcloud/v1.5'}))
            params.CreateVdcParams.append(Tag(builder=builder.TreeBuilder(),name='AllocationModel'))
            params.CreateVdcParams.AllocationModel.string = allocation_model
            params.CreateVdcParams.append(Tag(builder=builder.TreeBuilder(),name='ComputeCapacity'))
            params.CreateVdcParams.ComputeCapacity.append(Tag(builder=builder.TreeBuilder(),name='Cpu'))
            params.CreateVdcParams.ComputeCapacity.Cpu.append(Tag(builder=builder.TreeBuilder(),name='Units'))
            params.CreateVdcParams.ComputeCapacity.Cpu.Units.string = 'MHz'
            params.CreateVdcParams.ComputeCapacity.Cpu.append(Tag(builder=builder.TreeBuilder(),name='Allocated'))
            params.CreateVdcParams.ComputeCapacity.Cpu.Allocated.string = str(cpu_limit_ghz*1000) 
            params.CreateVdcParams.ComputeCapacity.Cpu.append(Tag(builder=builder.TreeBuilder(),name='Limit'))
            params.CreateVdcParams.ComputeCapacity.Cpu.Limit.string = str(cpu_limit_ghz*1000) 
            params.CreateVdcParams.ComputeCapacity.append(Tag(builder=builder.TreeBuilder(),name='Memory'))
            params.CreateVdcParams.ComputeCapacity.Memory.append(Tag(builder=builder.TreeBuilder(),name='Units'))
            params.CreateVdcParams.ComputeCapacity.Memory.Units.string = 'MB'
            params.CreateVdcParams.ComputeCapacity.Memory.append(Tag(builder=builder.TreeBuilder(),name='Allocated'))
            params.CreateVdcParams.ComputeCapacity.Memory.Allocated.string = str(cpu_limit_ghz*1000) 
            params.CreateVdcParams.ComputeCapacity.Memory.append(Tag(builder=builder.TreeBuilder(),name='Limit'))
            params.CreateVdcParams.ComputeCapacity.Memory.Limit.string = str(memory_limit_gb*1024) 
            params.CreateVdcParams.append(Tag(builder=builder.TreeBuilder(),name='NetworkQuota'))
            params.CreateVdcParams.NetworkQuota.string = '1024'
            params.CreateVdcParams.append(Tag(builder=builder.TreeBuilder(),name='IsEnabled'))
            params.CreateVdcParams.IsEnabled.string = str(enable).lower()
            params.CreateVdcParams.append(Tag(builder=builder.TreeBuilder(),name='VdcStorageProfile'))
            params.CreateVdcParams.VdcStorageProfile.append(Tag(builder=builder.TreeBuilder(),name='Enabled'))
            params.CreateVdcParams.VdcStorageProfile.Enabled.string = 'true'
            params.CreateVdcParams.VdcStorageProfile.append(Tag(builder=builder.TreeBuilder(),name='Units'))
            params.CreateVdcParams.VdcStorageProfile.Units.string = 'MB'
            params.CreateVdcParams.VdcStorageProfile.append(Tag(builder=builder.TreeBuilder(),name='Limit'))
            params.CreateVdcParams.VdcStorageProfile.Limit.string = str(storage_limit_gb*1024) 
            params.CreateVdcParams.VdcStorageProfile.append(Tag(builder=builder.TreeBuilder(),name='Default'))
            params.CreateVdcParams.VdcStorageProfile.Default.string = 'true'
            providervdc = ProviderVdc(providervdc_name)
            storage_profile_href = providervdc.get_storage_profile(storage_profile_name,show=False)[0]['href']
            params.CreateVdcParams.VdcStorageProfile.append(Tag(builder=builder.TreeBuilder(),name='ProviderVdcStorageProfile',attrs={'href':storage_profile_href}))
            if memory_reserve_pc > 1.0 or cpu_reserve_pc > 1.0:
                logger.info("Can't reserve higher than 1.0(100%)")
                return
            params.CreateVdcParams.append(Tag(builder=builder.TreeBuilder(),name='ResourceGuaranteedMemory'))
            params.CreateVdcParams.ResourceGuaranteedMemory.string = str(memory_reserve_pc)
            params.CreateVdcParams.append(Tag(builder=builder.TreeBuilder(),name='ResourceGuaranteedCpu'))
            params.CreateVdcParams.ResourceGuaranteedCpu.string = str(cpu_reserve_pc)
            params.CreateVdcParams.append(Tag(builder=builder.TreeBuilder(),name='VCpuInMhz'))
            params.CreateVdcParams.VCpuInMhz.string = str(vcpu_in_mhz) 
            params.CreateVdcParams.append(Tag(builder=builder.TreeBuilder(),name='IsThinProvision'))
            params.CreateVdcParams.IsThinProvision.string = str(enable_thin_provision).lower()
            network_pool_href = self.get_network_pool(network_pool_name,show=False)[0]['href']              
            params.CreateVdcParams.append(Tag(builder=builder.TreeBuilder(),name='NetworkPoolReference',attrs={'href':network_pool_href}))
            params.CreateVdcParams.append(Tag(builder=builder.TreeBuilder(),name='ProviderVdcReference',attrs={'href':providervdc.href}))
            if adopt_resource_pools:
                providervdc=ProviderVdc(providervdc_name)
                adoptable_resource_pools = providervdc.get_resource_pool(discover_adoptable=True, show=False)
                if len(adoptable_resource_pools) > 0:
                    params.CreateVdcParams.append(Tag(builder=builder.TreeBuilder(),name='ResourcePoolRefs'))
                    for adoptable_resource_pool in adoptable_resource_pools:
                            resource_pool_ref = Tag(builder=builder.TreeBuilder(),name='vmext:VimObjectRef')
                            resource_pool_ref.append(Tag(builder=builder.TreeBuilder(),name='vmext:VimServerRef',attrs={'href':adoptable_resource_pool.find('ResourcePoolVimObjectRef').find('VimServerRef')['href']}))
                            resource_pool_ref.append(Tag(builder=builder.TreeBuilder(),name='vmext:MoRef'))
                            resource_pool_ref.find('vmext:MoRef').string = adoptable_resource_pool.find('ResourcePoolVimObjectRef').find('MoRef').string
                            resource_pool_ref.append(Tag(builder=builder.TreeBuilder(),name='vmext:VimObjectType'))
                            resource_pool_ref.find('vmext:VimObjectType').string = 'RESOURCE_POOL'
                            params.CreateVdcParams.ResourcePoolRefs.append(resource_pool_ref)
            params.CreateVdcParams.append(Tag(builder=builder.TreeBuilder(),name='UsesFastProvisioning'))
            params.CreateVdcParams.UsesFastProvisioning.string = str(enable_fast_provision).lower()
            params.CreateVdcParams.append(Tag(builder=builder.TreeBuilder(),name='OverCommitAllowed'))
            params.CreateVdcParams.OverCommitAllowed.string = str(allow_overcommit).lower()
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.createVdcParams', org.href.replace('/api','/api/admin') + '/vdcsparams', params, requests.codes.created, inspect.stack()[0][3], adminvdc_name)
        except:
            Container.handle_exception(sys.exc_info())

    def set_adminvdc(self,adminvdc_name,enable=True):
        try:
            adminvdc_record = self.get_record('adminOrgVdc', 'AdminVdcRecord', 'name==' + adminvdc_name, show=False)
            if len(adminvdc_record) == 0:
                logger.info("%s does not exist in %s" % (adminvdc_name,self.name))
                return
            adminvdc_entity = self.get_entity(adminvdc_record[0]['href'])
            params = BeautifulSoup(adminvdc_entity,'xml')
            params.find('AdminVdc').find('IsEnabled').string = str(enable).lower()
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_put_params('admin.vdc', adminvdc_record[0]['href'], params, requests.codes.accepted, inspect.stack()[0][3], adminvdc_name)
        except:
            Container.handle_exception(sys.exc_info())

    def del_adminvdc(self,adminvdc_name):
        try:
            adminvdc_record = self.get_record('adminOrgVdc', 'AdminVdcRecord', 'name==' + adminvdc_name, show=False)
            if len(adminvdc_record) == 0:
                logger.info("%s does not exist in %s" % (adminvdc_name,self.name))
                return
            self.api_delete(adminvdc_record[0]['href'], inspect.stack()[0][3], adminvdc_name)
        except:
            Container.handle_exception(sys.exc_info())

    def get_edge_gateway(self, name=None, detailed=False, show=True):
        try:
            record_filter = 'name==' + name if name != None else ''
            return self.get_record('edgeGateway', 'EdgeGatewayRecord', record_filter, detailed=detailed, show=show)
        except:
            Container.handle_exception(sys.exc_info())

    def get_externalnet(self, name=None, detailed=False, show=True):
        try:
            record_filter = 'name==' + name if name != None else ''
            return self.get_record('externalNetwork', 'NetworkRecord', record_filter, detailed=detailed, show=show)
        except:
            Container.handle_exception(sys.exc_info())

    def set_externalnet(self,externalnet_name,name=None):
        try:
            externalnet_record = self.get_record('externalNetwork', 'NetworkRecord', 'name==' + externalnet_name, show=False)
            if len(externalnet_record) == 0:
                logger.info("%s does not exist in %s" % (externalnet_name,self.name))
                return
            externalnet_entity = self.get_entity(externalnet_record[0]['href'].replace('/api/network','/api/admin/extension/externalnet'))
            params = BeautifulSoup(externalnet_entity,'xml')
            if name != None:
                params.find('VMWExternalNetwork')['name'] = name
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_put_params('admin.vmwexternalnet', externalnet_record[0]['href'].replace('/api/network','/api/admin/extension/externalnet'), params, requests.codes.ok, inspect.stack()[0][3], externalnet_name)
        except:
            Container.handle_exception(sys.exc_info())

    def add_externalnet(self,externalnet_name,ipscope_gateway,ipscope_netmask,iprange_start,iprange_end,vcenter_name,portgroup_name,ipscope_dns1=None,ipscope_dns_suffix=None,):
        try:
            externalnet_record = self.get_record('externalNetwork', 'NetworkRecord', 'name==' + externalnet_name, show=False)
            if len(externalnet_record) > 0:
                logger.info("%s already exist in %s" % (externalnet_name,self.name))
                return
            params = BeautifulSoup('<?xml version="1.0" encoding=""?>','xml')
            params.append(Tag(builder=builder.TreeBuilder(),name='vmext:VMWExternalNetwork',attrs={'name':externalnet_name,
                'xmlns:vmext':'http://www.vmware.com/vcloud/extension/v1.5',
                'xmlns':'http://www.vmware.com/vcloud/v1.5'}))
            params.find('vmext:VMWExternalNetwork').append(Tag(builder=builder.TreeBuilder(),name='Description'))
            params.find('vmext:VMWExternalNetwork').append(Tag(builder=builder.TreeBuilder(),name='Configuration'))
            params.find('vmext:VMWExternalNetwork').Configuration.append(Tag(builder=builder.TreeBuilder(),name='IpScopes'))
            params.find('vmext:VMWExternalNetwork').Configuration.IpScopes.append(Tag(builder=builder.TreeBuilder(),name='IpScope'))
            params.find('vmext:VMWExternalNetwork').Configuration.IpScopes.IpScope.append(Tag(builder=builder.TreeBuilder(),name='IsInherited'))
            params.find('vmext:VMWExternalNetwork').Configuration.IpScopes.IpScope.IsInherited.string = 'false'
            params.find('vmext:VMWExternalNetwork').Configuration.IpScopes.IpScope.append(Tag(builder=builder.TreeBuilder(),name='Gateway'))
            params.find('vmext:VMWExternalNetwork').Configuration.IpScopes.IpScope.Gateway.string = ipscope_gateway 
            params.find('vmext:VMWExternalNetwork').Configuration.IpScopes.IpScope.append(Tag(builder=builder.TreeBuilder(),name='Netmask'))
            params.find('vmext:VMWExternalNetwork').Configuration.IpScopes.IpScope.Netmask.string = ipscope_netmask 
            if ipscope_dns1 != None:
                params.find('vmext:VMWExternalNetwork').Configuration.IpScopes.IpScope.append(Tag(builder=builder.TreeBuilder(),name='Dns1'))
                params.find('vmext:VMWExternalNetwork').Configuration.IpScopes.IpScope.Dns1.string = ipscope_dns1 
            if ipscope_dns_suffix != None:
                params.find('vmext:VMWExternalNetwork').Configuration.IpScopes.IpScope.append(Tag(builder=builder.TreeBuilder(),name='DnsSuffix'))
                params.find('vmext:VMWExternalNetwork').Configuration.IpScopes.IpScope.DnsSuffix.string = ipscope_dns_suffix 
            params.find('vmext:VMWExternalNetwork').Configuration.IpScopes.IpScope.append(Tag(builder=builder.TreeBuilder(),name='IpRanges'))
            params.find('vmext:VMWExternalNetwork').Configuration.IpScopes.IpScope.IpRanges.append(Tag(builder=builder.TreeBuilder(),name='IpRange'))
            params.find('vmext:VMWExternalNetwork').Configuration.IpScopes.IpScope.IpRanges.IpRange.append(Tag(builder=builder.TreeBuilder(),name='StartAddress'))
            params.find('vmext:VMWExternalNetwork').Configuration.IpScopes.IpScope.IpRanges.IpRange.StartAddress.string = iprange_start 
            params.find('vmext:VMWExternalNetwork').Configuration.IpScopes.IpScope.IpRanges.IpRange.append(Tag(builder=builder.TreeBuilder(),name='EndAddress'))
            params.find('vmext:VMWExternalNetwork').Configuration.IpScopes.IpScope.IpRanges.IpRange.EndAddress.string = iprange_end 
            params.find('vmext:VMWExternalNetwork').Configuration.append(Tag(builder=builder.TreeBuilder(),name='FenceMode'))
            params.find('vmext:VMWExternalNetwork').Configuration.FenceMode.string = 'isolated'
            params.find('vmext:VMWExternalNetwork').append(Tag(builder=builder.TreeBuilder(),name='vmext:VimPortGroupRef'))
            params.find('vmext:VMWExternalNetwork').find('vmext:VimPortGroupRef').append(Tag(builder=builder.TreeBuilder(),name='vmext:VimServerRef',attrs={'href':Vcenter(vcenter_name).href}))
            params.find('vmext:VMWExternalNetwork').find('vmext:VimPortGroupRef').append(Tag(builder=builder.TreeBuilder(),name='vmext:MoRef'))
            params.find('vmext:VMWExternalNetwork').find('vmext:VimPortGroupRef').find('vmext:MoRef').string = self.get_portgroup(portgroup_name,show=False)[0]['moref']
            params.find('vmext:VMWExternalNetwork').find('vmext:VimPortGroupRef').append(Tag(builder=builder.TreeBuilder(),name='vmext:VimObjectType'))
            # VimObjectType: HOST,VIRTUAL_MACHINE,VIRTUAL_APP,NETWORK,DV_PORTGROUP,DV_SWITCH,DATASTORE_CLUSTER
            params.find('vmext:VMWExternalNetwork').find('vmext:VimPortGroupRef').find('vmext:VimObjectType').string = 'DV_PORTGROUP'
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.vmwexternalnet', Container.api_url_prefix + '/admin/extension/externalnets', params, requests.codes.created, inspect.stack()[0][3], externalnet_name)
        except:
            Container.handle_exception(sys.exc_info())

    def del_externalnet(self,externalnet_name):
        try:
            externalnet_record = self.get_record('externalNetwork', 'NetworkRecord', 'name==' + externalnet_name, show=False)
            if len(externalnet_record) == 0:
                logger.info("%s does not exist in %s" % (externalnet_name,self.name))
                return
            self.api_delete(externalnet_record[0]['href'].replace('/api/network','/api/admin/extension/externalnet'), inspect.stack()[0][3], externalnet_name)
        except:
            Container.handle_exception(sys.exc_info())

    def get_network_pool(self, name=None, detailed=False, show=True):
        try:
            record_filter = 'name==' + name if name != None else ''
            return self.get_record('networkPool', 'NetworkPoolRecord', record_filter, detailed=detailed, show=show)
        except:
            Container.handle_exception(sys.exc_info())

    def get_vcenter(self, name=None, detailed=False, show=True):
        try:
            record_filter = 'name==' + name if name != None else ''
            return self.get_record('virtualCenter', 'VirtualCenterRecord', record_filter, detailed=detailed, show=show)
        except:
            Container.handle_exception(sys.exc_info())

    def add_vcenter(self,vcenter_name,vcenter_username,vcenter_password,vcenter_ip,vsm_name,vsm_ip,vsm_username,vsm_password,enable=True):
        try:
            vcenter_record = self.get_record('virtualCenter', 'VirtualCenterRecord', 'name==' + vcenter_name, show=False)
            if len(vcenter_record) > 0:
                logger.info("%s already exist in %s" % (vcenter_name,self.name))
                return
            params = BeautifulSoup('<?xml version="1.0" encoding=""?>','xml')
            params.append(Tag(builder=builder.TreeBuilder(),name='vmext:RegisterVimServerParams',attrs={'xmlns:vmext':'http://www.vmware.com/vcloud/extension/v1.5'}))
            params.find('vmext:RegisterVimServerParams').append(Tag(builder=builder.TreeBuilder(),name='vmext:VimServer',attrs={'name':vcenter_name}))            
            params.find('vmext:RegisterVimServerParams').find('vmext:VimServer').append(Tag(builder=builder.TreeBuilder(),name='vmext:Username'))
            params.find('vmext:RegisterVimServerParams').find('vmext:VimServer').find('vmext:Username').string=vcenter_username
            params.find('vmext:RegisterVimServerParams').find('vmext:VimServer').append(Tag(builder=builder.TreeBuilder(),name='vmext:Password'))
            params.find('vmext:RegisterVimServerParams').find('vmext:VimServer').find('vmext:Password').string=vcenter_password
            params.find('vmext:RegisterVimServerParams').find('vmext:VimServer').append(Tag(builder=builder.TreeBuilder(),name='vmext:Url'))
            params.find('vmext:RegisterVimServerParams').find('vmext:VimServer').find('vmext:Url').string='https://' + vcenter_ip + ':443' 
            params.find('vmext:RegisterVimServerParams').find('vmext:VimServer').append(Tag(builder=builder.TreeBuilder(),name='vmext:IsEnabled'))
            params.find('vmext:RegisterVimServerParams').find('vmext:VimServer').find('vmext:IsEnabled').string=str(enable).lower()
            params.find('vmext:RegisterVimServerParams').append(Tag(builder=builder.TreeBuilder(),name='vmext:ShieldManager',attrs={'name':vsm_name}))            
            params.find('vmext:RegisterVimServerParams').find('vmext:ShieldManager').append(Tag(builder=builder.TreeBuilder(),name='vmext:Username'))
            params.find('vmext:RegisterVimServerParams').find('vmext:ShieldManager').find('vmext:Username').string=vsm_username
            params.find('vmext:RegisterVimServerParams').find('vmext:ShieldManager').append(Tag(builder=builder.TreeBuilder(),name='vmext:Password'))
            params.find('vmext:RegisterVimServerParams').find('vmext:ShieldManager').find('vmext:Password').string=vsm_password
            params.find('vmext:RegisterVimServerParams').find('vmext:ShieldManager').append(Tag(builder=builder.TreeBuilder(),name='vmext:Url'))
            params.find('vmext:RegisterVimServerParams').find('vmext:ShieldManager').find('vmext:Url').string='https://' + vsm_ip + ':443' 
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.registerVimServerParams', Container.api_url_prefix + '/admin/extension/action/registervimserver', params, requests.codes.ok, inspect.stack()[0][3], vcenter_name)
        except:
            Container.handle_exception(sys.exc_info())

    def del_vcenter(self, vcenter_name):
        try:
            vcenter_record = self.get_record('virtualCenter', 'VirtualCenterRecord', 'name==' + vcenter_name, show=False)
            if len(vcenter_record) == 0:
                logger.info("%s does not exist in %s" % (vcenter_name,self.name))
                return
            self.api_post(vcenter_record[0]['href'] + '/action/unregister', requests.codes.accepted, inspect.stack()[0][3])
        except:
            Container.handle_exception(sys.exc_info())

    def get_resource_pool(self, name=None, detailed=False, show=True):
        try:
            record_filter = 'name==' + name if name != None else ''
            return self.get_record('resourcePool', 'ResourcePoolRecord', record_filter, detailed=detailed, show=show)
        except:
            Container.handle_exception(sys.exc_info())

    def get_host(self, name=None, detailed=False, show=True):
        try:
            record_filter = 'name==' + name if name != None else ''
            return self.get_record('host', 'HostRecord', record_filter, detailed=detailed, show=show)
        except:
            Container.handle_exception(sys.exc_info())

    def set_host(self,host_name,enable=True):
        try:
            host_record = self.get_record('host', 'HostRecord', 'name==' + host_name, show=False)
            if len(host_record) == 0:
                logger.info("%s does not exist in %s" % (host_name,self.name))
                return
            host_entity = self.get_entity(host_record[0]['href'])
            if enable:
                self.api_post(host_record[0]['href'] + '/action/enable', requests.codes.accepted, inspect.stack()[0][3])
            else:
                self.api_post(host_record[0]['href'] + '/action/disable', requests.codes.accepted, inspect.stack()[0][3])
        except:
            Container.handle_exception(sys.exc_info())

    def add_host(self, host_name, username, password):
        try:
            host_record = self.get_record('host', 'HostRecord', 'name==' + host_name, show=False)
            if len(host_record) == 0:
                logger.info("%s does not exist in %s" % (host_name,self.name))
                return
            params = BeautifulSoup('<?xml version="1.0" encoding=""?>','xml')
            params.append(Tag(builder=builder.TreeBuilder(),name='PrepareHostParams',attrs={'xmlns':'http://www.vmware.com/vcloud/extension/v1.5'}))
            params.PrepareHostParams.append(Tag(builder=builder.TreeBuilder(),name='Username'))
            params.PrepareHostParams.Username.string = username
            params.PrepareHostParams.append(Tag(builder=builder.TreeBuilder(),name='Password'))
            params.PrepareHostParams.Password.string = password
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.prepareHostParams', host_record[0]['href'] + '/action/prepare', params, requests.codes.accepted, inspect.stack()[0][3], host_name)
        except:
            Container.handle_exception(sys.exc_info())

    def del_host(self, host_name):
        try:
            host_record = self.get_record('host', 'HostRecord', 'name==' + host_name, show=False)
            if len(host_record) == 0:
                logger.info("%s does not exist in %s" % (host_name,self.name))
                return
            self.api_post(host_record[0]['href'] + '/action/unprepare', requests.codes.accepted, inspect.stack()[0][3])
        except:
            Container.handle_exception(sys.exc_info())

    def get_datastore(self, name=None, detailed=False, show=True):
        try:
            record_filter = 'name==' + name if name != None else ''
            return self.get_record('datastore', 'DatastoreRecord', record_filter, detailed=detailed, show=show)
        except:
            Container.handle_exception(sys.exc_info())

    def get_storage_profile(self, name=None, detailed=False, show=True):
        try:
            record_filter = 'name==' + name if name != None else ''
            return self.get_record('providerVdcStorageProfile', 'ProviderVdcStorageProfileRecord', record_filter, detailed=detailed, show=show)
        except:
            Container.handle_exception(sys.exc_info())

    def get_dvswitch(self, name=None, detailed=False, show=True):
        try:
            record_filter = 'name==' + name if name != None else ''
            return self.get_record('dvSwitch', 'DvSwitchRecord', record_filter, detailed=detailed, show=show)
        except:
            Container.handle_exception(sys.exc_info())

    def get_portgroup(self, name=None, detailed=False, show=True):
        try:
            record_filter = 'name==' + name if name != None else ''
            return self.get_record('portgroup', 'PortgroupRecord', record_filter, detailed=detailed, show=show)
        except:
            Container.handle_exception(sys.exc_info())

    def get_task(self, status=None, detailed=False, show=True):
        try:
            if status not in Container.task_statuses:
                logger.info("%s not in %s" % (status,Container.task_statuses))
                return
            record_filter = 'status==' + status if status != None else ''
            return self.get_record('task', 'TaskRecord', record_filter, detailed=detailed, show=show)
        except:
            Container.handle_exception(sys.exc_info())

    def get_event(self, detailed=False, show=True):
        try:
            return self.get_record('event', 'EventRecord', detailed=detailed, show=show)
        except:
            Container.handle_exception(sys.exc_info())

    def get_role_template(self, name=None, detailed=True, show=True):
        try:
            api_headers = Container.api_headers
            Container.api_headers['Accept'] = 'application/*+xml;version=9.0'
            role_templates = self.get_role(name, detailed, show)
            Container.api_headers = api_headers
            return role_templates
        except:
            Container.handle_exception(sys.exc_info())

    def set_role_template(self,role_name,name=None,role_right_names=None):
        try:
            api_headers = Container.api_headers
            Container.api_headers['Accept'] = 'application/*+xml;version=9.0'
            self.set_role(role_name,name,role_right_names)
            Container.api_headers = api_headers
        except:
            Container.handle_exception(sys.exc_info())

    def add_role_template(self,role_name,role_right_names):
        try:
            api_headers = Container.api_headers
            Container.api_headers['Accept'] = 'application/*+xml;version=9.0'
            self.add_role(role_name,role_right_names)
            Container.api_headers = api_headers
        except:
            Container.handle_exception(sys.exc_info())

    def del_role_template(self,role_name):
        try:
            api_headers = Container.api_headers
            Container.api_headers['Accept'] = 'application/*+xml;version=9.0'
            self.del_role(role_name)
            Container.api_headers = api_headers
        except:
            Container.handle_exception(sys.exc_info())

class Vcenter(Container):

    def __init__(self, name):
        Container.__init__(self, name)
        self.href = self.get_href()

    def get_href(self):
        try:
            return super(Vcenter, self).get_href('virtualCenter', 'VirtualCenterRecord')
        except:
            Container.handle_exception(sys.exc_info())

    def set_vcenter(self,name=None,enable=True):
        try:
            vcenter_entity = self.get_entity(self.href)
            params = BeautifulSoup(vcenter_entity,'xml')
            if name != None:
                params.find('VimServer')['name'] = name
            params.find('VimServer').find('IsEnabled').string = str(enable).lower()
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_put_params('admin.vmwvirtualcenter', self.href, params, requests.codes.accepted, inspect.stack()[0][3], vcenter_name)
        except:
            Container.handle_exception(sys.exc_info())

    def get_host(self, show=True):
        try:
            return self.get_section('/hostReferences', show)
        except:
            Container.handle_exception(sys.exc_info())

    def get_network(self, show=True):
        try:
            return self.get_section('/networks', show)
        except:
            Container.handle_exception(sys.exc_info())

    def get_resource_pool(self, name=None, show=True):
        try:
            if name != None:
                resource_pool = BeautifulSoup(self.get_section('/resourcePoolList', show=False),'xml').find('ResourcePool',attrs={'name':name})
                if resource_pool == None:
                    logger.info("%s does not exist" % (name))
                else:
                    if show:
                        self.show_records('ResourcePool',[resource_pool])
                    return resource_pool
            else:
                return BeautifulSoup(self.get_section('/resourcePoolList', show), 'xml')
        except:
            Container.handle_exception(sys.exc_info())

    def get_storage_profile(self, show=True):
        try:
            self.api_post(self.href + '/action/refreshStorageProfiles', requests.codes.accepted, inspect.stack()[0][3])
            return self.get_section('/storageProfiles', show)
        except:
            Container.handle_exception(sys.exc_info())

class ProviderVdc(Container):

    def __init__(self, name):
        Container.__init__(self, name)
        self.href = self.get_href()
        self.admin_href = self.href
        self.extension_href = self.href.replace('/api/admin','/api/admin/extension')

    def get_href(self):
        try:
            return super(ProviderVdc, self).get_href('providerVdc', 'VMWProviderVdcRecord')
        except:
            Container.handle_exception(sys.exc_info())

    def set_providervdc(self,name=None,hardware_ver=None,enable=True):
        try:
            if enable:
                self.api_post(self.extension_href + '/action/enable', requests.codes.no_content, inspect.stack()[0][3])
            else:
                self.api_post(self.extension_href + '/action/disable', requests.codes.no_content, inspect.stack()[0][3])
            providervdc_entity = self.get_entity(self.extension_href)
            params = BeautifulSoup(providervdc_entity,'xml')
            if name != None:
                params.find('VMWProviderVdc')['name'] = name
            if hardware_ver != None:
                if hardware_ver not in self.hardware_vers:
                    logger.info("%s not in %s, default to highest." % (hardware_ver, self.hardware_vers))
                    hardware_ver = sorted(self.hardware_vers, key=lambda x: int(x.replace('vmx-','')))[-1] # highest supported by vcd system
                params.find('VMWProviderVdc').find('HighestSupportedHardwareVersion').string = hardware_ver
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_put_params('admin.vmwprovidervdc', self.extension_href, params, requests.codes.ok, inspect.stack()[0][3], providervdc_name)
        except:
            Container.handle_exception(sys.exc_info())

    def get_storage_profile(self, name=None, available=None, detailed=False, show=True):
        try:
            if available != None:
                if available:
                    self.href = self.extension_href
                    availables = self.get_section('/availableStorageProfiles', show)
                    self.href = self.admin_href
                    return availables
            record_filter = 'providerVdc==' + self.href
            record_filter += ';name==' + name if name != None else ''
            return self.get_record('providerVdcStorageProfile', 'ProviderVdcStorageProfileRecord', record_filter, detailed=detailed, show=show)
        except:
            Container.handle_exception(sys.exc_info())

    def set_storage_profile(self, storage_profile_name, enable=None):
        try:
            storage_profile_record = self.get_record('providerVdcStorageProfile', 'ProviderVdcStorageProfileRecord', 'name==' + storage_profile_name + ';providerVdc==' + self.href, show=False)
            if len(storage_profile_record) == 0:
                logger.info("%s does not exist in %s" % (storage_profile_name, self.name))
                return
            params = BeautifulSoup(self.get_entity(storage_profile_record[0]['href'].replace('/api/admin','/api/admin/extension')),'xml')
            if enable != None:
                params.find('VMWProviderVdcStorageProfile').Enabled.string = str(enable).lower()
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_put_params('admin.vmwPvdcStorageProfile', storage_profile_record[0]['href'].replace('/api/admin','/api/admin/extension'), params, requests.codes.ok, inspect.stack()[0][3], storage_profile_name)
        except:
            Container.handle_exception(sys.exc_info())

    def add_storage_profile(self,storage_profile_name):
        try:
            storage_profile_record = self.get_record('providerVdcStorageProfile', 'ProviderVdcStorageProfileRecord', 'name==' + storage_profile_name + ';providerVdc==' + self.href,show=False)
            if len(storage_profile_record) > 0:
                logger.info("%s already exist in %s" % (storage_profile_name, self.name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], storage_profile_name))
                return
            availables = BeautifulSoup(self.get_storage_profile(available=True, show=False),'xml')
            if availables.find('VMWStorageProfile',attrs={'name':storage_profile_name}) == None:
                logger.info("%s not available to %s" % (storage_profile_name, self.name))
                return
            params = BeautifulSoup('<?xml version="1.0" encoding=""?>','xml')
            params = Tag(builder=builder.TreeBuilder(),name='UpdateProviderVdcStorageProfiles',attrs={'name':storage_profile_name,
                'xmlns':'http://www.vmware.com/vcloud/extension/v1.5',
                'xmlns:vcloud':'http://www.vmware.com/vcloud/v1.5'})
            params.append(Tag(builder=builder.TreeBuilder(),name='AddStorageProfile'))
            params.AddStorageProfile.string = storage_profile_name
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.updateProviderVdcStorageProfiles', self.extension_href + '/storageProfiles', params, requests.codes.accepted, inspect.stack()[0][3], storage_profile_name)
        except:
            Container.handle_exception(sys.exc_info())

    def del_storage_profile(self,storage_profile_name):
        try:
            storage_profile_record = self.get_record('providerVdcStorageProfile', 'ProviderVdcStorageProfileRecord', 'name==' + storage_profile_name + ';providerVdc==' + self.href,show=False)
            if len(storage_profile_record) == 0:
                logger.info("%s does not exist in %s" % (storage_profile_name, self.name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], storage_profile_name))
                return
            params = BeautifulSoup('<?xml version="1.0" encoding=""?>','xml')
            params = Tag(builder=builder.TreeBuilder(),name='UpdateProviderVdcStorageProfiles',attrs={'name':storage_profile_name,
                'xmlns':'http://www.vmware.com/vcloud/extension/v1.5',
                'xmlns:vcloud':'http://www.vmware.com/vcloud/v1.5'})
            params.append(Tag(builder=builder.TreeBuilder(),name='RemoveStorageProfile',attrs={'href':storage_profile_record[0]['href']}))
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.updateProviderVdcStorageProfiles', self.extension_href + '/storageProfiles', params, requests.codes.accepted, inspect.stack()[0][3], storage_profile_name)
        except:
            Container.handle_exception(sys.exc_info())

    def get_resource_pool(self, name=None, discover_adoptable=None, detailed=None, show=True):
        try:
            if discover_adoptable != None:
                if discover_adoptable:
                    adoptables = []
                    self.href = self.extension_href
                    discover_sources = BeautifulSoup(self.get_section('/discoverResourcePools', show=False),'xml').find('VMWDiscoveredResourcePools').find_all('VMWDiscoveredResourcePool',recursive=False)
                    for discover_source in discover_sources:
                        discover_source_moref = discover_source.find('ResourcePoolVimObjectRef').find('MoRef').string
                        valid_candidates = BeautifulSoup(self.get_section('/discoverResourcePools/' + discover_source_moref, show=False),'xml').find('VMWDiscoveredResourcePools').find_all('VMWDiscoveredResourcePool',recursive=False,attrs={'validCandidate':'true'})
                        adoptables.extend(valid_candidates)
                    self.href = self.admin_href
                    if show:
                        self.show_records('adoptable resource pool',adoptables)
                    return adoptables
            if detailed != None:
                if detailed:
                    self.href = self.extension_href
                    resource_pools = BeautifulSoup(self.get_section('/resourcePools', show=show),'xml')
                    self.href = self.admin_href
                    return resource_pools
            record_filter = 'providerVdc==' + self.href
            record_filter += ';name==' + name if name != None else ''
            return self.get_record('providerVdcResourcePoolRelation', 'ProviderVdcResourcePoolRelationRecord', record_filter, show=show)
        except:
            Container.handle_exception(sys.exc_info())

    def set_resource_pool(self,resource_pool_name,enable=True):
        try:
            resource_pool_record = self.get_record('providerVdcResourcePoolRelation', 'ProviderVdcResourcePoolRelationRecord', 'name==' + resource_pool_name + ';providerVdc==' + self.href, show=False)
            if len(resource_pool_record) == 0:
                logger.info("%s does not exist in %s" % (resource_pool_name, self.name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], resource_pool_name))
                return
            resource_pool_moref = resource_pool_record[0]['resourcePoolMoref']
            for resource_pool in self.get_resource_pool(detailed=True,show=False).find('VMWProviderVdcResourcePoolSet').find_all('VMWProviderVdcResourcePool', recursive=False):
                if resource_pool.find('ResourcePoolVimObjectRef').find('MoRef',text=resource_pool_moref) != None:
                    resource_pool_href = resource_pool.find('ResourcePoolRef')['href']
            if enable:
                self.api_post(resource_pool_href + '/action/enable', requests.codes.no_content, inspect.stack()[0][3])
            else:
                self.api_post(resource_pool_href + '/action/disable', requests.codes.no_content, inspect.stack()[0][3])
        except:
            Container.handle_exception(sys.exc_info())

    def add_resource_pool(self,resource_pool_name,vcenter_name): 
        try:
            resource_pool_record = self.get_record('providerVdcResourcePoolRelation', 'ProviderVdcResourcePoolRelationRecord', 'name==' + resource_pool_name + ';providerVdc==' + self.href, show=False)
            if len(resource_pool_record) > 0:
                logger.info("%s already exist in %s" % (resource_pool_name, self.name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], resource_pool_name))
                return
            params = BeautifulSoup('<?xml version="1.0" encoding=""?>','xml')
            params = Tag(builder=builder.TreeBuilder(),name='UpdateResourcePoolSetParams',attrs={'xmlns':'http://www.vmware.com/vcloud/extension/v1.5'})
            params.append(Tag(builder=builder.TreeBuilder(),name='AddItem'))
            vcenter = Vcenter(vcenter_name)
            params.AddItem.append(Tag(builder=builder.TreeBuilder(),name='VimServerRef',attrs={'href':vcenter.href}))
            resource_pool = vcenter.get_resource_pool(resource_pool_name, show=False)
            params.AddItem.append(Tag(builder=builder.TreeBuilder(),name='MoRef'))
            params.AddItem.MoRef.string = resource_pool.find('MoRef').string
            params.AddItem.append(Tag(builder=builder.TreeBuilder(),name='VimObjectType'))
            params.AddItem.VimObjectType.string = 'RESOURCE_POOL'
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.resourcePoolSetUpdateParams', self.extension_href + '/action/updateResourcePools', params, requests.codes.accepted, inspect.stack()[0][3], resource_pool_name)
        except:
            Container.handle_exception(sys.exc_info())

    def del_resource_pool(self,resource_pool_name):
        try:
            resource_pool_record = self.get_record('providerVdcResourcePoolRelation', 'ProviderVdcResourcePoolRelationRecord', 'name==' + resource_pool_name + ';providerVdc==' + self.href, show=False)
            if len(resource_pool_record) == 0:
                logger.info("%s does not exist in %s" % (resource_pool_name, self.name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], resource_pool_name))
                return
            params = BeautifulSoup('<?xml version="1.0" encoding=""?>','xml')
            params = Tag(builder=builder.TreeBuilder(),name='UpdateResourcePoolSetParams',attrs={'xmlns':'http://www.vmware.com/vcloud/extension/v1.5'})
            resource_pool_moref = resource_pool_record[0]['resourcePoolMoref']
            for resource_pool in self.get_resource_pool(detailed=True,show=False).find('VMWProviderVdcResourcePoolSet').find_all('VMWProviderVdcResourcePool', recursive=False):
                if resource_pool.find('ResourcePoolVimObjectRef').find('MoRef',text=resource_pool_moref) != None:
                    resource_pool_href = resource_pool.find('ResourcePoolRef')['href']
            params.append(Tag(builder=builder.TreeBuilder(),name='DeleteItem',attrs={'href':resource_pool_href}))
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.resourcePoolSetUpdateParams', self.extension_href + '/action/updateResourcePools', params, requests.codes.accepted, inspect.stack()[0][3], resource_pool_name)
        except:
            Container.handle_exception(sys.exc_info())

    def get_hostgroup(self, resource_pool_name, hostgroup_name=None, show=True):
        try:
            resource_pool_record = self.get_record('providerVdcResourcePoolRelation', 'ProviderVdcResourcePoolRelationRecord', 'name==' + resource_pool_name + ';providerVdc==' + self.href, show=False)
            if resource_pool_record != None:
                resource_pool_moref = resource_pool_record[0]['resourcePoolMoref']
            for resource_pool in self.get_resource_pool(detailed=True,show=False).find('VMWProviderVdcResourcePoolSet').find_all('VMWProviderVdcResourcePool', recursive=False):
                if resource_pool.find('ResourcePoolVimObjectRef').find('MoRef',text=resource_pool_moref) != None:
                    resource_pool_href = resource_pool.find('ResourcePoolRef')['href']
            if hostgroup_name == None:
                hostgroups = BeautifulSoup(self.get_entity(resource_pool_href + '/hostGroups'),'xml').find('VMWHostGroups').find_all('HostGroup', recursive=False)
            else:
                hostgroups = BeautifulSoup(self.get_entity(resource_pool_href + '/hostGroups'),'xml').find('VMWHostGroups').find('HostGroup', attrs={'name':hostgroup_name})
                if hostgroups != None:
                    hostgroups = [hostgroups]
            if show:
                self.show_records('hostgroup',hostgroups)
            return hostgroups
        except:
            Container.handle_exception(sys.exc_info())

    def get_vm(self, resource_pool_name, vm_name=None, show=True):
        try:
            resource_pool_record = self.get_record('providerVdcResourcePoolRelation', 'ProviderVdcResourcePoolRelationRecord', 'name==' + resource_pool_name + ';providerVdc==' + self.href, show=False)
            resource_pool_moref = resource_pool_record[0]['resourcePoolMoref']
            for resource_pool in self.get_resource_pool(detailed=True,show=False).find('VMWProviderVdcResourcePoolSet').find_all('VMWProviderVdcResourcePool', recursive=False):
                if resource_pool.find('ResourcePoolVimObjectRef').find('MoRef',text=resource_pool_moref) != None:
                    resource_pool_href = resource_pool.find('ResourcePoolRef')['href']
            if vm_name == None:
                resource_pool_vms = BeautifulSoup(self.get_entity(resource_pool_href + '/vmList'),'xml').find('QueryResultRecords').find_all('ResourcePoolVMRecord', recursive=False)
            else:
                resource_pool_vms = BeautifulSoup(self.get_entity(resource_pool_href + '/vmList'),'xml').find('QueryResultRecords').find('ResourcePoolVMRecord', attrs={'name':vm_name})
                if resource_pool_vms != None:
                    resource_pool_vms = [resource_pool_vms]
            if show:
                self.show_records('resource_pool_vm',resource_pool_vms)
            return resource_pool_vms
        except:
            Container.handle_exception(sys.exc_info())

    def get_vmgroup(self, resource_pool_name, vmgroup_name=None, show=True):
        try:
            resource_pool_record = self.get_record('providerVdcResourcePoolRelation', 'ProviderVdcResourcePoolRelationRecord', 'name==' + resource_pool_name + ';providerVdc==' + self.href, show=False)
            resource_pool_moref = resource_pool_record[0]['resourcePoolMoref']
            for resource_pool in self.get_resource_pool(detailed=True,show=False).find('VMWProviderVdcResourcePoolSet').find_all('VMWProviderVdcResourcePool', recursive=False):
                if resource_pool.find('ResourcePoolVimObjectRef').find('MoRef',text=resource_pool_moref) != None:
                    resource_pool_href = resource_pool.find('ResourcePoolRef')['href']
            if vmgroup_name == None:
                vmgroups = BeautifulSoup(self.get_entity(resource_pool_href + '/vmGroups'),'xml').find('VMWVmGroups').find_all('VmGroup', recursive=False)
            else:
                vmgroups = BeautifulSoup(self.get_entity(resource_pool_href + '/vmGroups'),'xml').find('VMWVmGroups').find('VmGroup', attrs={'name':vmgroup_name})
                if vmgroups != None:
                    vmgroups = [vmgroups]
            if show:
                self.show_records('vmgroup',vmgroups)
            return vmgroups
        except:
            Container.handle_exception(sys.exc_info())
 
    def add_vmgroup(self, resource_pool_name, vmgroup_name):
        try:
            resource_pool_record = self.get_record('providerVdcResourcePoolRelation', 'ProviderVdcResourcePoolRelationRecord', 'name==' + resource_pool_name + ';providerVdc==' + self.href, show=False)
            resource_pool_moref = resource_pool_record[0]['resourcePoolMoref']
            for resource_pool in self.get_resource_pool(detailed=True,show=False).find('VMWProviderVdcResourcePoolSet').find_all('VMWProviderVdcResourcePool', recursive=False):
                if resource_pool.find('ResourcePoolVimObjectRef').find('MoRef',text=resource_pool_moref) != None:
                    resource_pool_href = resource_pool.find('ResourcePoolRef')['href']
            vmgroup = BeautifulSoup(self.get_entity(resource_pool_href + '/vmGroups'),'xml').find('VMWVmGroups').find('VmGroup', attrs={'name':vmgroup_name})
            if vmgroup != None:
                logger.info("%s already exist in %s" % (vmgroup_name,resource_pool_name))
                return
            params = BeautifulSoup('<?xml version="1.0" encoding=""?>','xml')
            params.append(Tag(builder=builder.TreeBuilder(),name='VMWVmGroup',attrs={'name':vmgroup_name,
                'xmlns':'http://www.vmware.com/vcloud/extension/v1.5'}))
            params.VMWVmGroup.append(Tag(builder=builder.TreeBuilder(),name='vmCount'))
            params.VMWVmGroup.vmCount.string = '0'
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.vmwVmGroupType', resource_pool_href + '/vmGroups', params, requests.codes.accepted, inspect.stack()[0][3], vmgroup_name)
        except:
            Container.handle_exception(sys.exc_info())

    def del_vmgroup(self, resource_pool_name, vmgroup_name):
        try:
            resource_pool_record = self.get_record('providerVdcResourcePoolRelation', 'ProviderVdcResourcePoolRelationRecord', 'name==' + resource_pool_name + ';providerVdc==' + self.href, show=False)
            resource_pool_moref = resource_pool_record[0]['resourcePoolMoref']
            for resource_pool in self.get_resource_pool(detailed=True,show=False).find('VMWProviderVdcResourcePoolSet').find_all('VMWProviderVdcResourcePool', recursive=False):
                if resource_pool.find('ResourcePoolVimObjectRef').find('MoRef',text=resource_pool_moref) != None:
                    resource_pool_href = resource_pool.find('ResourcePoolRef')['href']
            vmgroup = BeautifulSoup(self.get_entity(resource_pool_href + '/vmGroups'),'xml').find('VMWVmGroups').find('VmGroup', attrs={'name':vmgroup_name})
            if vmgroup == None:
                logger.info("%s does not exist in %s" % (vmgroup_name,resource_pool_name))
                return
            self.api_delete(vmgroup['href'], inspect.stack()[0][3], vmgroup_name)
        except:
            Container.handle_exception(sys.exc_info())

    def get_vmgroup_vm(self, resource_pool_name, vmgroup_name, show=True):
        try:
            resource_pool_record = self.get_record('providerVdcResourcePoolRelation', 'ProviderVdcResourcePoolRelationRecord', 'name==' + resource_pool_name + ';providerVdc==' + self.href, show=False)
            resource_pool_moref = resource_pool_record[0]['resourcePoolMoref']
            for resource_pool in self.get_resource_pool(detailed=True,show=False).find('VMWProviderVdcResourcePoolSet').find_all('VMWProviderVdcResourcePool', recursive=False):
                if resource_pool.find('ResourcePoolVimObjectRef').find('MoRef',text=resource_pool_moref) != None:
                    resource_pool_href = resource_pool.find('ResourcePoolRef')['href']
            vmgroup = BeautifulSoup(self.get_entity(resource_pool_href + '/vmGroups'),'xml').find('VMWVmGroups').find('VmGroup', attrs={'name':vmgroup_name})
            if vmgroup == None:
                logger.info("%s does not exist in %s" % (vmgroup_name,resource_pool_name))
                return
            vmgroup_vms = BeautifulSoup(self.get_entity(vmgroup['href'] + '/vmsList'),'xml').find('QueryResultRecords').find_all('VmGroupVmsRecord', recursive=False)
            if show:
                self.show_records('vmgroup_vm',vmgroup_vms)
            return vmgroup_vms
        except:
            Container.handle_exception(sys.exc_info())

    def add_vmgroup_vm(self, resource_pool_name, vmgroup_name, vm_name):
        try:
            resource_pool_record = self.get_record('providerVdcResourcePoolRelation', 'ProviderVdcResourcePoolRelationRecord', 'name==' + resource_pool_name + ';providerVdc==' + self.href, show=False)
            resource_pool_moref = resource_pool_record[0]['resourcePoolMoref']
            for resource_pool in self.get_resource_pool(detailed=True,show=False).find('VMWProviderVdcResourcePoolSet').find_all('VMWProviderVdcResourcePool', recursive=False):
                if resource_pool.find('ResourcePoolVimObjectRef').find('MoRef',text=resource_pool_moref) != None:
                    resource_pool_href = resource_pool.find('ResourcePoolRef')['href']
            vmgroup = BeautifulSoup(self.get_entity(resource_pool_href + '/vmGroups'),'xml').find('VMWVmGroups').find('VmGroup', attrs={'name':vmgroup_name})
            if vmgroup == None:
                logger.info("%s does not exist in %s" % (vmgroup_name,resource_pool_name))
                return
            vmgroup_vm = BeautifulSoup(self.get_entity(vmgroup['href'] + '/vmsList'),'xml').find('QueryResultRecords').find('VmGroupVmsRecord', attrs={'vmName':vm_name})
            if vmgroup_vm != None:
                logger.info("%s already exist in %s" % (vm_name,vmgroup_name))
                return
            vm = self.get_vm(resource_pool_name, vm_name, show=False)
            if vm == None:
                logger.info("%s does not exist in %s" % (vm_name, resource_pool_name))
                return
            params = BeautifulSoup('<?xml version="1.0" encoding=""?>','xml')
            params.append(Tag(builder=builder.TreeBuilder(),name='Vms',attrs={'xmlns':'http://www.vmware.com/vcloud/v1.5'}))
            params.Vms.append(Tag(builder=builder.TreeBuilder(),name='VmReference',attrs={'href':vm['href'],'name':vm_name}))
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('vcloud.vms', vmgroup.find('Link', attrs={'rel':'up'})['href'] + '/action/addVms', params, requests.codes.accepted, inspect.stack()[0][3], vm_name)
        except:
            Container.handle_exception(sys.exc_info())

    def del_vmgroup_vm(self, resource_pool_name, vmgroup_name, vm_name):
        try:
            resource_pool_record = self.get_record('providerVdcResourcePoolRelation', 'ProviderVdcResourcePoolRelationRecord', 'name==' + resource_pool_name + ';providerVdc==' + self.href, show=False)
            resource_pool_moref = resource_pool_record[0]['resourcePoolMoref']
            for resource_pool in self.get_resource_pool(detailed=True,show=False).find('VMWProviderVdcResourcePoolSet').find_all('VMWProviderVdcResourcePool', recursive=False):
                if resource_pool.find('ResourcePoolVimObjectRef').find('MoRef',text=resource_pool_moref) != None:
                    resource_pool_href = resource_pool.find('ResourcePoolRef')['href']
            vmgroup = BeautifulSoup(self.get_entity(resource_pool_href + '/vmGroups'),'xml').find('VMWVmGroups').find('VmGroup', attrs={'name':vmgroup_name})
            if vmgroup == None:
                logger.info("%s does not exist in %s" % (vmgroup_name,resource_pool_name))
                return
            vmgroup_vm = BeautifulSoup(self.get_entity(vmgroup['href'] + '/vmsList'),'xml').find('QueryResultRecords').find('VmGroupVmsRecord', attrs={'vmName':vm_name})
            if vmgroup_vm == None:
                logger.info("%s does not exist in %s" % (vm_name,vmgroup_name))
                return
            vm = self.get_vm(resource_pool_name, vm_name, show=False)
            if vm == None:
                logger.info("%s does not exist in %s" % (vm_name, resource_pool_name))
                return
            params = BeautifulSoup('<?xml version="1.0" encoding=""?>','xml')
            params.append(Tag(builder=builder.TreeBuilder(),name='Vms',attrs={'xmlns':'http://www.vmware.com/vcloud/v1.5'}))
            params.Vms.append(Tag(builder=builder.TreeBuilder(),name='VmReference',attrs={'href':vm['href'],'name':vm_name}))
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('vcloud.vms', vmgroup.find('Link', attrs={'rel':'up'})['href'] + '/action/removeVms', params, requests.codes.accepted, inspect.stack()[0][3], vm_name)
        except:
            Container.handle_exception(sys.exc_info())

    def get_vm_host_affinity_rule(self, resource_pool_name, vm_host_affinity_rule_name=None, show=True):
        try:
            resource_pool_record = self.get_record('providerVdcResourcePoolRelation', 'ProviderVdcResourcePoolRelationRecord', 'name==' + resource_pool_name + ';providerVdc==' + self.href, show=False)
            resource_pool_moref = resource_pool_record[0]['resourcePoolMoref']
            for resource_pool in self.get_resource_pool(detailed=True,show=False).find('VMWProviderVdcResourcePoolSet').find_all('VMWProviderVdcResourcePool', recursive=False):
                if resource_pool.find('ResourcePoolVimObjectRef').find('MoRef',text=resource_pool_moref) != None:
                    resource_pool_href = resource_pool.find('ResourcePoolRef')['href']
            if vm_host_affinity_rule_name == None:
                vm_host_affinity_rules = BeautifulSoup(self.get_entity(resource_pool_href + '/rules'),'xml').find('VMWVmHostAffinityRules').find_all('VmHostAffinityRule', recursive=False)
            else:
                vm_host_affinity_rules = BeautifulSoup(self.get_entity(resource_pool_href + '/rules'),'xml').find('VMWVmHostAffinityRules').find('Name', text=vm_host_affinity_rule_name)
                if vm_host_affinity_rules != None:
                    vm_host_affinity_rules = [vm_host_affinity_rules.parent]
            if show:
                self.show_records('vm_host_affinity_rule',vm_host_affinity_rules)
            return vm_host_affinity_rules
        except:
            Container.handle_exception(sys.exc_info())

class OrgVdc(Container):
    
    def __init__(self, name):
        Container.__init__(self, name)
        self.href = self.get_href()
        self.admin_href = self.href.replace('/api', '/api/admin')

    def get_href(self):
        try:
            return super(OrgVdc, self).get_href('orgVdc', 'OrgVdcRecord')
        except:
            Container.handle_exception(sys.exc_info())
    
    def get_compute(self):
            vdc_entity = self.get_entity(self.href)
            compute = {}
            # cpu_mhz
            cpu_limit = int(BeautifulSoup(vdc_entity,'xml').Vdc.ComputeCapacity.Cpu.Limit.string)
            cpu_used = int(BeautifulSoup(vdc_entity,'xml').Vdc.ComputeCapacity.Cpu.Used.string)
            cpu_overhead = int(BeautifulSoup(vdc_entity,'xml').Vdc.ComputeCapacity.Cpu.Overhead.string)
            cpu_mhz = cpu_limit - cpu_used - cpu_overhead
            compute['cpu_mhz'] = cpu_mhz
            # memory_mb
            memory_limit = int(BeautifulSoup(vdc_entity,'xml').Vdc.ComputeCapacity.Memory.Limit.string)
            memory_used = int(BeautifulSoup(vdc_entity,'xml').Vdc.ComputeCapacity.Memory.Used.string)
            memory_overhead = int(BeautifulSoup(vdc_entity,'xml').Vdc.ComputeCapacity.Memory.Overhead.string)
            memory_mb = memory_limit - memory_used - memory_overhead
            compute['memory_mb'] = memory_mb
            return compute

    def get_storage_profile(self, name=None, detailed=False, show=True):
        try:
            record_filter = 'vdc==' + self.href
            record_filter += ';name==' + name if name != None else ''
            if Container.session_org_name.lower() == 'system':
                return self.get_record('adminOrgVdcStorageProfile', 'AdminOrgVdcStorageProfileRecord', record_filter, detailed=detailed, show=show)
            else:
                return self.get_record('orgVdcStorageProfile', 'OrgVdcStorageProfileRecord', record_filter, detailed=detailed, show=show)
        except:
            Container.handle_exception(sys.exc_info())

    def set_storage_profile(self, storage_profile_name, enable=None, default=None, limit_gb=None):
        try:
            storage_profile_record = self.get_record('adminOrgVdcStorageProfile', 'AdminOrgVdcStorageProfileRecord', 'name==' + storage_profile_name + ';vdc==' + self.href, show=False)
            if len(storage_profile_record) == 0:
                logger.info("%s does not exist in %s" % (storage_profile_name, self.name))
                return
            params = BeautifulSoup(self.get_entity(storage_profile_record[0]['href'].replace('/api','/api/admin')),'xml')
            if enable != None:
                params.AdminVdcStorageProfile.Enabled.string = str(enable).lower()
            if default != None:
                params.AdminVdcStorageProfile.Default.string = str(default).lower()
            if limit_gb != None:
                params.AdminVdcStorageProfile.Limit.string = str(limit_gb*1024) 
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_put_params('admin.vdcStorageProfile', storage_profile_record[0]['href'].replace('/api','/api/admin'), params, requests.codes.ok, inspect.stack()[0][3], storage_profile_name)
        except:
            Container.handle_exception(sys.exc_info())

    def get_network(self,name=None,link_type=None,shared=False,detailed=False, show=True):
        try:
            if link_type != None and link_type not in Container.vdc_network_types.keys():
                logger.info("%s not in %s" % (link_type, Container.vdc_network_types.keys()))
                return
            record_filter = 'vdc==' + self.href
            record_filter += ';name==' + name if name != None else ''
            record_filter += ';linkType==' + Container.vdc_network_types[link_type] if link_type != None else ''
            record_filter += ';isShared==' + str(shared).lower() if shared else ''
            return self.get_record('orgVdcNetwork', 'OrgVdcNetworkRecord', record_filter, detailed=detailed, show=show)
        except:
            Container.handle_exception(sys.exc_info())

    def set_network(self,network_name,name=None,shared=None):
            network_record = self.get_record('orgVdcNetwork', 'OrgVdcNetworkRecord', 'name==' + network_name + ';vdcName==' + self.name, show=False)
            if len(network_record) == 0:
                logger.info("%s does not exist in %s" % (network_name, self.name))
                return
            params = BeautifulSoup(self.get_entity(network_record[0]['href']),'xml')
            if name != None:
                params.OrgVdcNetwork['name'] = name 
            if shared != None:
                params.OrgVdcNetwork.IsShared.string = str(shared).lower() 
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_put_params('vcloud.orgVdcNetwork', network_record[0]['href'], params, requests.codes.accepted, inspect.stack()[0][3], network_name)

    def get_network_ip_in_use(self,network_name):
            network_record = self.get_record('orgVdcNetwork', 'OrgVdcNetworkRecord', 'name==' + network_name + ';vdcName==' + self.name, show=False)
            if len(network_record) == 0:
                logger.info("%s does not exist in %s" % (network_name, self.name))
                return
            r = self.api_get(network_record[0]['href'] + '/allocatedAddresses')
            return r.content if r != None else None

    def get_network_ipranges(self,network_name):
            network_record = self.get_record('orgVdcNetwork', 'OrgVdcNetworkRecord', 'name==' + network_name + ';vdcName==' + self.name, show=False)
            if len(network_record) == 0:
                logger.info("%s does not exist in %s" % (network_name, self.name))
                return
            records = BeautifulSoup(self.get_entity(network_record[0]['href']),'xml').find_all('IpRange')
            self.show_records('IpRange',records)
            return records

    def set_network_iprange(self,network_name,iprange_index,iprange_start=None,iprange_end=None):
            network_record = self.get_record('orgVdcNetwork', 'OrgVdcNetworkRecord', 'name==' + network_name + ';vdcName==' + self.name, show=False)
            if len(network_record) == 0:
                logger.info("%s does not exist in %s" % (network_name, self.name))
                return
            params = BeautifulSoup(self.get_entity(network_record[0]['href']),'xml')
            ipranges = params.find_all('IpRange')
            if iprange_index not in range(len(ipranges)):
                logger.info("%s does not exist in %s" % (iprange_index,network_name))
                return
            if iprange_start == None or iprange_end == None:
                logger.info("one of iprange_start or iprange_end must be specified")
                return
            if iprange_start != None:
                ipranges[iprange_index].StartAddress.string = iprange_start 
            if iprange_end != None:
                ipranges[iprange_index].EndAddress.string = iprange_end 
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_put_params('vcloud.orgVdcNetwork', network_record[0]['href'], params, requests.codes.accepted, inspect.stack()[0][3], network_name)

    def add_network_iprange(self,network_name,iprange_start,iprange_end):
            network_record = self.get_record('orgVdcNetwork', 'OrgVdcNetworkRecord', 'name==' + network_name + ';vdcName==' + self.name, show=False)
            if len(network_record) == 0:
                logger.info("%s does not exist in %s" % (network_name, self.name))
                return
            iprange = Tag(builder=builder.TreeBuilder(),name='IpRange')
            iprange.append(Tag(builder=builder.TreeBuilder(),name='StartAddress'))
            iprange.append(Tag(builder=builder.TreeBuilder(),name='EndAddress'))
            iprange.StartAddress.string = iprange_start 
            iprange.EndAddress.string = iprange_end 
            params = BeautifulSoup(self.get_entity(network_record[0]['href']),'xml')
            ipranges = params.find_all('IpRange')
            if len(ipranges) > 0:
                ipranges[-1].insert_after(iprange)
            else:
                params.append(iprange)
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_put_params('vcloud.orgVdcNetwork', network_record[0]['href'], params, requests.codes.accepted, inspect.stack()[0][3], network_name)

    def del_network_iprange(self,network_name,iprange_index):
            network_record = self.get_record('orgVdcNetwork', 'OrgVdcNetworkRecord', 'name==' + network_name + ';vdcName==' + self.name, show=False)
            if len(network_record) == 0:
                logger.info("%s does not exist in %s" % (network_name, self.name))
                return
            params = BeautifulSoup(self.get_entity(network_record[0]['href']),'xml')
            ipranges = params.find_all('IpRange')
            if iprange_index not in range(len(ipranges)):
                logger.info("%s does not exist in %s" % (iprange_index,network_name))
                return
            ipranges[iprange_index].extract()
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_put_params('vcloud.orgVdcNetwork', network_record[0]['href'], params, requests.codes.accepted, inspect.stack()[0][3], network_name)

    def add_network(self,network_name,fence_mode,ipscope_gateway,ipscope_netmask,ipscope_dns1=None,ipscope_dns_suffix=None,iprange_start=None,iprange_end=None,edge_gateway_name=None,shared=False):
        try:
            network_record = self.get_record('orgVdcNetwork', 'OrgVdcNetworkRecord', 'name==' + network_name + ';vdcName==' + self.name, show=False)
            if len(network_record) > 0:
                logger.info("%s already exist in %s" % (network_name, self.name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], network_name))
                return
            if fence_mode not in Container.fence_modes:
                logger.info("%s not in %s" % (fence_mode, Container.fence_modes))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], network_name))
                return
            if fence_mode == 'natRouted' and edge_gateway_name == None:
                logger.info("edge_gateway_name must be specified for fence_mode natRouted")
                return
            if fence_mode == 'natRouted':
                edge_gateway_record = self.get_record('edgeGateway', 'EdgeGatewayRecord', 'name==' + edge_gateway_name + ';vdc==' + self.href, show=False)
                if len(edge_gateway_record) == 0:
                    logger.info("%s does not exist in %s" % (edge_gateway_name, self.name))
                    return
            params = BeautifulSoup('<?xml version="1.0" encoding=""?>','xml')
            params = Tag(builder=builder.TreeBuilder(),name='OrgVdcNetwork',attrs={'name':network_name,'xmlns':'http://www.vmware.com/vcloud/v1.5'})
            params.append(Tag(builder=builder.TreeBuilder(),name='Description'))
            params.append(Tag(builder=builder.TreeBuilder(),name='Configuration'))
            params.Configuration.append(Tag(builder=builder.TreeBuilder(),name='IpScopes'))
            params.Configuration.IpScopes.append(Tag(builder=builder.TreeBuilder(),name='IpScope'))
            params.Configuration.IpScopes.IpScope.append(Tag(builder=builder.TreeBuilder(),name='IsInherited'))
            params.Configuration.IpScopes.IpScope.IsInherited.string = str(fence_mode == 'bridged').lower()
            params.Configuration.IpScopes.IpScope.append(Tag(builder=builder.TreeBuilder(),name='Gateway'))
            params.Configuration.IpScopes.IpScope.Gateway.string = ipscope_gateway 
            params.Configuration.IpScopes.IpScope.append(Tag(builder=builder.TreeBuilder(),name='Netmask'))
            params.Configuration.IpScopes.IpScope.Netmask.string = ipscope_netmask 
            if ipscope_dns1 != None:
                params.Configuration.IpScopes.IpScope.append(Tag(builder=builder.TreeBuilder(),name='Dns1'))
                params.Configuration.IpScopes.IpScope.Dns1.string = ipscope_dns1 
            if ipscope_dns_suffix != None:
                params.Configuration.IpScopes.IpScope.append(Tag(builder=builder.TreeBuilder(),name='DnsSuffix'))
                params.Configuration.IpScopes.IpScope.DnsSuffix.string = ipscope_dns_suffix 
            if iprange_start and iprange_end:
                params.Configuration.IpScopes.IpScope.append(Tag(builder=builder.TreeBuilder(),name='IpRanges'))
                params.Configuration.IpScopes.IpScope.IpRanges.append(Tag(builder=builder.TreeBuilder(),name='IpRange'))
                params.Configuration.IpScopes.IpScope.IpRanges.IpRange.append(Tag(builder=builder.TreeBuilder(),name='StartAddress'))
                params.Configuration.IpScopes.IpScope.IpRanges.IpRange.StartAddress.string = iprange_start 
                params.Configuration.IpScopes.IpScope.IpRanges.IpRange.append(Tag(builder=builder.TreeBuilder(),name='EndAddress'))
                params.Configuration.IpScopes.IpScope.IpRanges.IpRange.EndAddress.string = iprange_end 
            params.Configuration.append(Tag(builder=builder.TreeBuilder(),name='FenceMode'))
            params.Configuration.FenceMode.string = fence_mode
            if fence_mode == 'natRouted':
                params.append(Tag(builder=builder.TreeBuilder(),name='EdgeGateway',attrs={'href':edge_gateway_record[0]['href']}))
            params.append(Tag(builder=builder.TreeBuilder(),name='IsShared'))
            params.IsShared.string = str(shared).lower() 
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('vcloud.orgVdcNetwork', self.admin_href + '/networks', params, requests.codes.created, inspect.stack()[0][3], network_name)
        except:
            Container.handle_exception(sys.exc_info())

    def del_network(self,network_name):
            network_record = self.get_record('orgVdcNetwork', 'OrgVdcNetworkRecord', 'name==' + network_name + ';vdcName==' + self.name, show=False)
            if len(network_record) == 0:
                logger.info("%s does not exist in %s" % (network_name,self.name))
                return
            self.api_delete(network_record[0]['href'], inspect.stack()[0][3], network_name)

    def reset_network(self,network_name):
            network_record = self.get_record('orgVdcNetwork', 'OrgVdcNetworkRecord', 'name==' + network_name + ';vdcName==' + self.name, show=False)
            if len(network_record) == 0:
                logger.info("%s does not exist in %s" % (network_name,self.name))
                return
            self.api_post(network_record[0]['href'] + '/action/reset', requests.codes.accepted, inspect.stack()[0][3])

    def get_edge_gateway(self, name=None, detailed=False, show=True):
        try:
            record_filter = 'vdc==' + self.href
            record_filter += ';name==' + name if name != None else ''
            return self.get_record('edgeGateway', 'EdgeGatewayRecord', record_filter, detailed=detailed, show=show)
        except:
            Container.handle_exception(sys.exc_info())

    def add_edge_gateway(self,edge_gateway_name,externalnet_name,externalnet_gateway,externalnet_netmask,iprange_start,iprange_end,edge_gateway_size='compact',default_route=True,enable_ha=False):
        try:
            if edge_gateway_size not in self.edge_gateway_sizes:
                logger.info("%s not in %s" % (edge_gateway_size,self.edge_gateway_sizes))
                return
            edge_gateway_record = self.get_record('edgeGateway', 'EdgeGatewayRecord', 'name==' + edge_gateway_name + ';vdc==' + self.href,show=False)
            if len(edge_gateway_record) > 0:
                logger.info("%s already exist in %s" % (edge_gateway_name, self.name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], edge_gateway_name))
                return
            params = BeautifulSoup('<?xml version="1.0" encoding=""?>','xml')
            params = Tag(builder=builder.TreeBuilder(),name='EdgeGateway',attrs={'name':edge_gateway_name,'xmlns':'http://www.vmware.com/vcloud/v1.5'})
            params.append(Tag(builder=builder.TreeBuilder(),name='Description'))
            params.append(Tag(builder=builder.TreeBuilder(),name='Configuration'))
            params.Configuration.append(Tag(builder=builder.TreeBuilder(),name='GatewayBackingConfig'))
            params.Configuration.GatewayBackingConfig.string = edge_gateway_size
            params.Configuration.append(Tag(builder=builder.TreeBuilder(),name='GatewayInterfaces'))
            params.Configuration.GatewayInterfaces.append(Tag(builder=builder.TreeBuilder(),name='GatewayInterface'))
            externalnet_record = self.get_record('externalNetwork', 'NetworkRecord', 'name==' + externalnet_name, show=False)
            if len(externalnet_record) == 0:
                logger.info("%s does not exist" % (externalnet_name))
                return
            params.Configuration.GatewayInterfaces.GatewayInterface.append(Tag(builder=builder.TreeBuilder(),name='Network',attrs={'href':externalnet_record[0]['href']}))
            params.Configuration.GatewayInterfaces.GatewayInterface.append(Tag(builder=builder.TreeBuilder(),name='InterfaceType'))
            params.Configuration.GatewayInterfaces.GatewayInterface.InterfaceType.string = 'uplink'
            params.Configuration.GatewayInterfaces.GatewayInterface.append(Tag(builder=builder.TreeBuilder(),name='SubnetParticipation'))
            params.Configuration.GatewayInterfaces.GatewayInterface.SubnetParticipation.append(Tag(builder=builder.TreeBuilder(),name='Gateway'))
            params.Configuration.GatewayInterfaces.GatewayInterface.SubnetParticipation.Gateway.string = externalnet_gateway 
            params.Configuration.GatewayInterfaces.GatewayInterface.SubnetParticipation.append(Tag(builder=builder.TreeBuilder(),name='Netmask'))
            params.Configuration.GatewayInterfaces.GatewayInterface.SubnetParticipation.Netmask.string = externalnet_netmask 
            params.Configuration.GatewayInterfaces.GatewayInterface.SubnetParticipation.append(Tag(builder=builder.TreeBuilder(),name='IpRanges'))
            params.Configuration.GatewayInterfaces.GatewayInterface.SubnetParticipation.IpRanges.append(Tag(builder=builder.TreeBuilder(),name='IpRange'))
            params.Configuration.GatewayInterfaces.GatewayInterface.SubnetParticipation.IpRanges.IpRange.append(Tag(builder=builder.TreeBuilder(),name='StartAddress'))
            params.Configuration.GatewayInterfaces.GatewayInterface.SubnetParticipation.IpRanges.IpRange.StartAddress.string = iprange_start 
            params.Configuration.GatewayInterfaces.GatewayInterface.SubnetParticipation.IpRanges.IpRange.append(Tag(builder=builder.TreeBuilder(),name='EndAddress'))
            params.Configuration.GatewayInterfaces.GatewayInterface.SubnetParticipation.IpRanges.IpRange.EndAddress.string = iprange_end 
            params.Configuration.GatewayInterfaces.GatewayInterface.append(Tag(builder=builder.TreeBuilder(),name='UseForDefaultRoute'))
            params.Configuration.GatewayInterfaces.GatewayInterface.UseForDefaultRoute.string = str(default_route).lower()
            params.Configuration.append(Tag(builder=builder.TreeBuilder(),name='HaEnabled'))
            params.Configuration.HaEnabled.string = str(enable_ha).lower()
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.edgeGateway', self.admin_href + '/edgeGateways', params, requests.codes.created, inspect.stack()[0][3], edge_gateway_name)
        except:
            Container.handle_exception(sys.exc_info())

    def del_edge_gateway(self,edge_gateway_name):
        try:
            edge_gateway_record = self.get_record('edgeGateway', 'EdgeGatewayRecord', 'name==' + edge_gateway_name + ';vdc==' + self.href,show=False)
            if len(edge_gateway_record) == 0:
                logger.info("%s does not exist in %s" % (edge_gateway_name,self.name))
                return
            self.api_delete(edge_gateway_record[0]['href'], inspect.stack()[0][3], edge_gateway_name)
        except:
            Container.handle_exception(sys.exc_info())

    def get_vapp(self, name=None, detailed=False, show=True):
        try:
            record_filter = 'vdc==' + self.href
            record_filter += ';name==' + name if name != None else ''
            return self.get_record('vApp', 'VAppRecord', record_filter, detailed=detailed, show=show)
        except:
            Container.handle_exception(sys.exc_info())

    def get_vapp_template(self, name=None, detailed=False, show=True):
        try:
            record_filter = 'vdc==' + self.href
            record_filter += ';name==' + name if name != None else ''
            return self.get_record('vAppTemplate', 'VAppTemplateRecord', record_filter, detailed=detailed, show=show)
        except:
            Container.handle_exception(sys.exc_info())

    def add_vapp(self,vapp_name,vapp_template_name=None,source_vapp_name=None, source_vdc_name=None, source_delete=False):
            vapp_record = self.get_record('vApp', 'VAppRecord', 'vdcName==' + self.name + ';name==' + vapp_name, show=False)
            if len(vapp_record) > 0:
                logger.info("%s already exists" % (vapp_name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vapp_name))
                return
            # empty vapp
            if vapp_template_name == None and source_vapp_name == None:
                params = BeautifulSoup('<?xml version="1.0" encoding=""?>','xml')
                params.append(Tag(builder=builder.TreeBuilder(),name='ComposeVAppParams',attrs={'name':vapp_name,
                    'xmlns':'http://www.vmware.com/vcloud/v1.5',
                    'xmlns:ovf':'http://schemas.dmtf.org/ovf/envelope/1'}))
                params.ComposeVAppParams.append(Tag(builder=builder.TreeBuilder(),name='Description'))
                params.ComposeVAppParams.append(Tag(builder=builder.TreeBuilder(),name='InstantiationParams'))
                params.ComposeVAppParams.append(Tag(builder=builder.TreeBuilder(),name='AllEULAsAccepted'))
                params.ComposeVAppParams.AllEULAsAccepted.string = 'true'
                params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
                self.api_post_params('vcloud.ComposeVAppParams', self.href + '/action/composeVApp', params, requests.codes.created, inspect.stack()[0][3], vapp_name)
                return
            # vapp from template
            if vapp_template_name:
                vapp_template = self.get_vapp_template(vapp_template_name, detailed=False, show=False)
                if len(vapp_template) == 0:
                    logger.info("%s not in %s" % (vapp_template_name, self.name))
                    logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vapp_name))
                    return
                params = BeautifulSoup('<?xml version="1.0" encoding=""?>','xml')
                params.append(Tag(builder=builder.TreeBuilder(),name='InstantiateVAppTemplateParams',attrs={'name':vapp_name,
                    'xmlns':'http://www.vmware.com/vcloud/v1.5',
                    'xmlns:ovf':'http://schemas.dmtf.org/ovf/envelope/1'}))
                params.InstantiateVAppTemplateParams.append(Tag(builder=builder.TreeBuilder(),name='Description'))
                params.InstantiateVAppTemplateParams.append(Tag(builder=builder.TreeBuilder(),name='InstantiationParams'))
                params.InstantiateVAppTemplateParams.append(Tag(builder=builder.TreeBuilder(),name='Source',attrs={'href':vapp_template[0]['href'],
                    'name':vapp_template_name,
                    'type':'application/vnd.vmware.vcloud.vAppTemplate+xml'}))
                params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
                self.api_post_params('vcloud.instantiateVAppTemplateParams', self.href + '/action/instantiateVAppTemplate', params, requests.codes.created, inspect.stack()[0][3], vapp_name)
                return
            # clone vapp
            if source_vapp_name and not source_vdc_name:
                source_vdc_name = self.name
            if source_vapp_name and source_vdc_name:
                if len(self.get_record('orgVdc', 'OrgVdcRecord', 'name==' + source_vdc_name, show=False)) == 0:
                    logger.info("%s does not exist" % (source_vdc_name))
                    logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], source_vdc_name))
                    return
                source_vapp_record = self.get_record('vApp', 'VAppRecord', 'vdcName==' + source_vdc_name + ';name==' + source_vapp_name, show=False)
                if len(source_vapp_record) == 0:
                    logger.info("%s does not exist in %s" % (source_vapp_name, source_vdc_name))
                    logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], source_vapp_name))
                    return
                params = BeautifulSoup('<?xml version="1.0" encoding=""?>','xml')
                params.append(Tag(builder=builder.TreeBuilder(),name='CloneVAppParams',attrs={'name':vapp_name,
                    'xmlns':'http://www.vmware.com/vcloud/v1.5'}))
                params.CloneVAppParams.append(Tag(builder=builder.TreeBuilder(),name='Description'))
                params.CloneVAppParams.append(Tag(builder=builder.TreeBuilder(),name='Source',attrs={'href':source_vapp_record[0]['href'],
                    'name':source_vapp_record[0]['name'],
                    'type':'application/vnd.vmware.vcloud.cloneVAppParams+xml'}))
                params.CloneVAppParams.append(Tag(builder=builder.TreeBuilder(),name='IsSourceDelete'))
                params.CloneVAppParams.IsSourceDelete.string = str(source_delete).lower()
                params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
                self.api_post_params('vcloud.cloneVAppParams', self.href + '/action/cloneVApp', params, requests.codes.created, inspect.stack()[0][3], source_vapp_name)

    def del_vapp(self, vapp_name):
            vapp_record = self.get_record('vApp', 'VAppRecord', 'vdcName==' + self.name + ';name==' + vapp_name, show=False)
            if len(vapp_record) == 0:
                logger.info("%s does not exist in %s" % (vapp_name, self.name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vapp_name))
                return
            self.api_delete(vapp_record[0]['href'], inspect.stack()[0][3], vapp_name)

    def get_independent_disk(self, name=None, detailed=False, show=True):
        try:
            record_filter = 'vdc==' + self.href
            record_filter += ';name==' + name if name != None else ''
            return self.get_record('disk', 'DiskRecord', record_filter, detailed=detailed, show=show)
        except:
            Container.handle_exception(sys.exc_info())

    def set_independent_disk(self,disk_index,name=None,storage_profile_name=None):
        disks = self.get_record('disk', 'DiskRecord', 'vdcName==' + self.name, show=False)
        if disk_index not in range(len(disks)):
            logger.info("%s does not exist in %s" % (disk_index,self.name))
            return
        params = BeautifulSoup(self.get_entity(disks[disk_index]['href']),'xml')
        if name != None:
            params.Disk['name'] = name 
        if storage_profile_name != None:
            storage_profile_record = self.get_record('orgVdcStorageProfile','OrgVdcStorageProfileRecord','name==' + storage_profile_name + ';vdc==' + self.href, show=False)
            if len(storage_profile_record) == 0:
                logger.info("%s does not exist" % (storage_profile_name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], storage_profile_name))
                return
            params.Disk.StorageProfile['href'] = storage_profile_record[0]['href']
        params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
        self.api_put_params('vcloud.disk', disks[disk_index]['href'], params, requests.codes.accepted, inspect.stack()[0][3], self.name)

    def add_independent_disk(self,size_gb,name=None,bus_sub_type='lsilogic'):
        if name == None:
            name = self.name + '_' + str(size_gb) + 'GB' 
        if bus_sub_type not in Container.disk_bus_sub_types.keys():
            logger.info("%s not in %s" % (bus_sub_type, Container.disk_bus_sub_types.keys()))
            return
        params = BeautifulSoup('<?xml version="1.0" encoding=""?>','xml')
        params.append(Tag(builder=builder.TreeBuilder(),name='DiskCreateParams',attrs={'xmlns':'http://www.vmware.com/vcloud/v1.5'}))
        params.DiskCreateParams.append(Tag(builder=builder.TreeBuilder(),name='Disk',attrs={'name':name,
            'size':str(size_gb*1024*1024*1024),
            'busType':Container.disk_bus_sub_types[bus_sub_type],
            'busSubType':bus_sub_type}))
        params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
        self.api_post_params('vcloud.diskCreateParams', self.href + '/disk', params, requests.codes.created, inspect.stack()[0][3], self.name)

    def del_independent_disk(self,disk_index):
        disks = self.get_record('disk', 'DiskRecord', 'vdcName==' + self.name, show=False)
        if disk_index not in range(len(disks)):
            logger.info("%s does not exist in %s" % (disk_index,self.name))
            return
        self.api_delete(disks[disk_index]['href'], inspect.stack()[0][3], self.name)

class EdgeGateway(Container):

    def __init__(self, name, parent):
        Container.__init__(self, name)
        self.parent = parent
        self.href = self.get_href(parent)

    def get_href(self, parent):
            edge_gateway_record = self.get_record('edgeGateway', 'EdgeGatewayRecord', 'name==' + self.name + ';vdc==' + self.parent.href, show=False)
            if len(edge_gateway_record) == 0:
                logger.info("%s not in %s" % (self.name, self.parent.name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], self.parent.name))
                return None
            return edge_gateway_record[0]['href']

    def set_edge_gateway(self,name=None,enable_advanced=False):
        try:
            if enable_advanced:
                self.api_post(self.href + '/action/convertToAdvancedGateway', requests.codes.no_content, inspect.stack()[0][3])
            edge_gateway_entity = self.get_entity(self.href)
            params = BeautifulSoup(edge_gateway_entity,'xml')
            if name != None:
                params.EdgeGateway['name'] = name
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_put_params('admin.edgeGateway', self.href, params, requests.codes.accepted, inspect.stack()[0][3], self.name)
        except:
            Container.handle_exception(sys.exc_info())

    def get_interface(self): 
            records = BeautifulSoup(self.get_entity(self.href),'xml').find('GatewayInterfaces').find_all('GatewayInterface',recursive=False)
            self.show_records('interface',records)
            return records

    def add_interface(self,externalnet_name,externalnet_gateway,externalnet_netmask,iprange_start,iprange_end,default_route=False):
        try:
            params = BeautifulSoup(self.get_entity(self.href),'xml')
            interface = Tag(builder=builder.TreeBuilder(),name='GatewayInterface')
            externalnet_record = self.get_record('externalNetwork', 'NetworkRecord', 'name==' + externalnet_name, show=False)
            if len(externalnet_record) == 0:
                logger.info("%s does not exist" % (externalnet_name))
                return
            interface.append(Tag(builder=builder.TreeBuilder(),name='Network',attrs={'href':externalnet_record[0]['href']}))
            interface.append(Tag(builder=builder.TreeBuilder(),name='InterfaceType'))
            interface.InterfaceType.string = 'uplink'
            interface.append(Tag(builder=builder.TreeBuilder(),name='SubnetParticipation'))
            interface.SubnetParticipation.append(Tag(builder=builder.TreeBuilder(),name='Gateway'))
            interface.SubnetParticipation.Gateway.string = externalnet_gateway 
            interface.SubnetParticipation.append(Tag(builder=builder.TreeBuilder(),name='Netmask'))
            interface.SubnetParticipation.Netmask.string = externalnet_netmask 
            interface.SubnetParticipation.append(Tag(builder=builder.TreeBuilder(),name='IpRanges'))
            interface.SubnetParticipation.IpRanges.append(Tag(builder=builder.TreeBuilder(),name='IpRange'))
            interface.SubnetParticipation.IpRanges.IpRange.append(Tag(builder=builder.TreeBuilder(),name='StartAddress'))
            interface.SubnetParticipation.IpRanges.IpRange.StartAddress.string = iprange_start 
            interface.SubnetParticipation.IpRanges.IpRange.append(Tag(builder=builder.TreeBuilder(),name='EndAddress'))
            interface.SubnetParticipation.IpRanges.IpRange.EndAddress.string = iprange_end 
            interface.append(Tag(builder=builder.TreeBuilder(),name='UseForDefaultRoute'))
            interface.UseForDefaultRoute.string = str(default_route).lower()
            params.GatewayInterfaces.append(interface)            
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_put_params('admin.edgeGateway', self.href, params, requests.codes.accepted, inspect.stack()[0][3], self.name)
        except:
            Container.handle_exception(sys.exc_info())
    
    def get_dhcp(self): 
            return Container.convertXml2Yaml(str(BeautifulSoup(self.get_entity(self.href),'xml').find('GatewayDhcpService')))

    def set_dhcp(self, enable): 
            params = BeautifulSoup(self.get_entity(self.href),'xml').find('EdgeGatewayServiceConfiguration')
            if params.find('GatewayDhcpService') == None:
                params.append(Tag(builder=builder.TreeBuilder(),name='GatewayDhcpService'))
                params.GatewayDhcpService.append(Tag(builder=builder.TreeBuilder(),name='IsEnabled'))
            params.GatewayDhcpService.IsEnabled.string = str(enable).lower() 
            params['xmlns'] = 'http://www.vmware.com/vcloud/v1.5'
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.edgeGatewayServiceConfiguration', self.href + '/action/configureServices', params, requests.codes.accepted, inspect.stack()[0][3], self.name)

    def get_dhcp_pools(self): 
            records = BeautifulSoup(self.get_entity(self.href),'xml').find('EdgeGatewayServiceConfiguration').find('GatewayDhcpService').find_all('Pool',recursive=False)
            self.show_records('pool',records)
            return records

    def set_dhcp_pool(self,pool_index,enable=None,network_name=None,default_lease_time=None,max_lease_time=None,iprange_start=None,iprange_end=None): 
            params = BeautifulSoup(self.get_entity(self.href),'xml').find('EdgeGatewayServiceConfiguration')
            pools = params.find('GatewayDhcpService').find_all('Pool',recursive=False)
            if pool_index not in range(len(pools)):
                logger.info("%s does not exist in %s" % (pool_index,self.name))
                return
            if enable != None:
                pools[pool_index].IsEnabled.string = str(enable).lower()
            if network_name != None:
                network_record = self.get_record('orgVdcNetwork', 'OrgVdcNetworkRecord', 'name==' + network_name + ';vdcName==' + self.name, show=False)
                if len(network_record) == 0:
                    logger.info("%s does not exist in %s" % (network_name, self.name))
                    return
                pools[pool_index].Network['href'] = network_record[0]['href']
            if default_lease_time != None:
                pools[pool_index].DefaultLeaseTime.string = str(default_lease_time) 
            if max_lease_time != None:
                pools[pool_index].MaxLeaseTime.string = str(max_lease_time) 
            if iprange_start != None:
                pools[pool_index].LowIpAddress.string = iprange_start 
            if iprange_end != None:
                pools[pool_index].HighIpAddress.string = iprange_end 
            params['xmlns'] = 'http://www.vmware.com/vcloud/v1.5'
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.edgeGatewayServiceConfiguration', self.href + '/action/configureServices', params, requests.codes.accepted, inspect.stack()[0][3], self.name)

    def add_dhcp_pool(self,enable=True,network_name=None,default_lease_time=3600,max_lease_time=7200,iprange_start=None,iprange_end=None): 
            params = BeautifulSoup(self.get_entity(self.href),'xml').find('EdgeGatewayServiceConfiguration')
            if network_name == None:
                logger.info("network_name must be specified")
                return
            if iprange_start == None or iprange_end == None:
                logger.info("iprange_start/iprange_end must be specified")
                return
            network_record = self.get_record('orgVdcNetwork', 'OrgVdcNetworkRecord', 'name==' + network_name + ';vdcName==' + self.name, show=False)
            if len(network_record) == 0:
                logger.info("%s does not exist in %s" % (network_name, self.name))
                return
            pool = Tag(builder=builder.TreeBuilder(),name='Pool')
            pool.append(Tag(builder=builder.TreeBuilder(),name='IsEnabled'))
            pool.IsEnabled.string = str(enable).lower() 
            pool.append(Tag(builder=builder.TreeBuilder(),name='Network',attrs={'href':network_record[0]['href']}))
            pool.append(Tag(builder=builder.TreeBuilder(),name='DefaultLeaseTime'))
            pool.DefaultLeaseTime.string = str(default_lease_time) 
            pool.append(Tag(builder=builder.TreeBuilder(),name='MaxLeaseTime'))
            pool.MaxLeaseTime.string = str(max_lease_time) 
            pool.append(Tag(builder=builder.TreeBuilder(),name='LowIpAddress'))
            pool.append(Tag(builder=builder.TreeBuilder(),name='HighIpAddress'))
            pool.LowIpAddress.string = iprange_start 
            pool.HighIpAddress.string = iprange_end 
            params.GatewayDhcpService.append(pool)
            params['xmlns'] = 'http://www.vmware.com/vcloud/v1.5'
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.edgeGatewayServiceConfiguration', self.href + '/action/configureServices', params, requests.codes.accepted, inspect.stack()[0][3], self.name)

    def del_dhcp_pool(self,pool_index): 
            params = BeautifulSoup(self.get_entity(self.href),'xml').find('EdgeGatewayServiceConfiguration')
            pools = params.find('GatewayDhcpService').find_all('Pool',recursive=False)
            if pool_index not in range(len(pools)):
                logger.info("%s does not exist in %s" % (pool_index,self.name))
                return
            pools[pool_index].extract()
            params['xmlns'] = 'http://www.vmware.com/vcloud/v1.5'
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.edgeGatewayServiceConfiguration', self.href + '/action/configureServices', params, requests.codes.accepted, inspect.stack()[0][3], self.name)

    def get_firewall(self): 
            return Container.convertXml2Yaml(str(BeautifulSoup(self.get_entity(self.href),'xml').find('FirewallService')))

    def set_firewall(self,enable=None,default_action=None,log_default_action=None): 
            params = BeautifulSoup(self.get_entity(self.href),'xml').find('EdgeGatewayServiceConfiguration')
            if enable != None:
                params.FirewallService.IsEnabled.string = str(enable).lower() 
            if default_action != None:
                params.FirewallService.DefaultAction.string = default_action 
            if log_default_action != None:
                params.FirewallService.LogDefaultAction.string = str(log_default_action).lower() 
            params['xmlns'] = 'http://www.vmware.com/vcloud/v1.5'
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.edgeGatewayServiceConfiguration', self.href + '/action/configureServices', params, requests.codes.accepted, inspect.stack()[0][3], self.name)

    def get_firewall_rules(self): 
            records = BeautifulSoup(self.get_entity(self.href),'xml').find('EdgeGatewayServiceConfiguration').find('FirewallService').find_all('FirewallRule',recursive=False)
            self.show_records('rule',records)
            return records

    def set_firewall_rule(self,rule_index,enable=None,rule_name=None,action=None,protocols=None,dest_port=None,dest_ip=None,source_port=None,source_ip=None,log=None): 
            params = BeautifulSoup(self.get_entity(self.href),'xml').find('EdgeGatewayServiceConfiguration')
            rules = params.find('FirewallService').find_all('FirewallRule',recursive=False)
            if rule_index not in range(len(rules)):
                logger.info("%s does not exist in %s" % (rule_index,self.name))
                return
            if enable != None:
                rules[rule_index].IsEnabled.string = str(enable).lower()
            if rule_name != None:
                rules[rule_index].Description.string = rule_name
            if action != None:
                rules[rule_index].Policy.string = action
            if protocols != None:
                if protocols not in Container.firewall_protocols:
                        logger.info("%s not in %s" % (protocols,Container.firewall_protocols))
                        return
                rules[rule_index].Protocols.clear()
                for protocol in protocols:
                    rules[rule_index].Protocols.append(Tag(builder=builder.TreeBuilder(),name=protocol))
                    rules[rule_index].Protocols.find(protocol).string = 'true'
            rules[rule_index].Port.string = '-1'
            if dest_port != None:
                rules[rule_index].DestinationPortRange.string = dest_port 
            if dest_ip != None:
                rules[rule_index].DestinationIp.string = dest_ip 
            rules[rule_index].SourcePort.string = '-1'
            if source_port != None:
                rules[rule_index].SourcePortRange.string = source_port 
            if source_ip != None:
                rules[rule_index].SourceIp.string = source_ip 
            rules[rule_index].EnableLogging.string = str(log).lower()
            params['xmlns'] = 'http://www.vmware.com/vcloud/v1.5'
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.edgeGatewayServiceConfiguration', self.href + '/action/configureServices', params, requests.codes.accepted, inspect.stack()[0][3], self.name)

    def add_firewall_rule(self,rule_index,enable=True,rule_name='',action='allow',protocols=['Tcp'],dest_port=None,dest_ip=None,source_port=None,source_ip=None,log=True): 
            params = BeautifulSoup(self.get_entity(self.href),'xml').find('EdgeGatewayServiceConfiguration')
            rule = Tag(builder=builder.TreeBuilder(),name='FirewallRule')
            rule.append(Tag(builder=builder.TreeBuilder(),name='IsEnabled'))
            rule.IsEnabled.string = str(enable).lower() 
            rule.append(Tag(builder=builder.TreeBuilder(),name='Description'))
            rule.Description.string = rule_name
            rule.append(Tag(builder=builder.TreeBuilder(),name='Policy'))
            if action not in Container.firewall_policies:
                logger.info("%s not in %s" % (action,Container.firewall_policies))
                return
            else:
                rule.Policy.string = action
            rule.append(Tag(builder=builder.TreeBuilder(),name='Protocols'))
            if protocols:
                if protocols not in Container.firewall_protocols:
                        logger.info("%s not in %s" % (protocols,Container.firewall_protocols))
                        return
                for protocol in protocols:
                    rule.Protocols.append(Tag(builder=builder.TreeBuilder(),name=protocol))
                    rule.Protocols.find(protocol).string = 'true'
            rule.append(Tag(builder=builder.TreeBuilder(),name='Port'))
            rule.Port.string = '-1'
            if dest_port:
                rule.append(Tag(builder=builder.TreeBuilder(),name='DestinationPortRange'))
                rule.DestinationPortRange.string = dest_port 
            else:
                logger.info("dest_port must be specified")
                return
            if dest_ip:
                rule.append(Tag(builder=builder.TreeBuilder(),name='DestinationIp'))
                rule.DestinationIp.string = dest_ip 
            else:
                logger.info("dest_ip must be specified")
                return
            rule.append(Tag(builder=builder.TreeBuilder(),name='SourcePort'))
            rule.SourcePort.string = '-1'
            if source_port:
                rule.append(Tag(builder=builder.TreeBuilder(),name='SourcePortRange'))
                rule.SourcePortRange.string = source_port 
            else:
                logger.info("source_port must be specified")
                return
            if source_ip:
                rule.append(Tag(builder=builder.TreeBuilder(),name='SourceIp'))
                rule.SourceIp.string = source_ip 
            else:
                logger.info("source_ip must be specified")
                return
            rule.append(Tag(builder=builder.TreeBuilder(),name='EnableLogging'))
            rule.EnableLogging.string = str(log).lower() 
            rules = params.find('FirewallService').find_all('FirewallRule',recursive=False)
            if len(rules) == 0: 
                params.find('FirewallService').append(rule)
            elif rule_index < len(rules):
                rules[rule_index].insert_before(rule)
            elif rule_index >= len(rules):
                rules[-1].insert_after(rule)
            params['xmlns'] = 'http://www.vmware.com/vcloud/v1.5'
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.edgeGatewayServiceConfiguration', self.href + '/action/configureServices', params, requests.codes.accepted, inspect.stack()[0][3], self.name)

    def del_firewall_rule(self,rule_index): 
            params = BeautifulSoup(self.get_entity(self.href),'xml').find('EdgeGatewayServiceConfiguration')
            rules = params.find('FirewallService').find_all('FirewallRule',recursive=False)
            if rule_index not in range(len(rules)):
                logger.info("%s does not exist in %s" % (rule_index,self.name))
                return
            rules[rule_index].extract()
            params['xmlns'] = 'http://www.vmware.com/vcloud/v1.5'
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.edgeGatewayServiceConfiguration', self.href + '/action/configureServices', params, requests.codes.accepted, inspect.stack()[0][3], self.name)

    def get_nat(self): 
            return Container.convertXml2Yaml(str(BeautifulSoup(self.get_entity(self.href),'xml').find('NatService')))

    def set_nat(self, enable): 
            params = BeautifulSoup(self.get_entity(self.href),'xml').find('EdgeGatewayServiceConfiguration')
            if params.find('NatService') == None:
                params.append(Tag(builder=builder.TreeBuilder(),name='NatService'))
                params.NatService.append(Tag(builder=builder.TreeBuilder(),name='IsEnabled'))
                params.NatService.IsEnabled.string = str(enable).lower() 
            params['xmlns'] = 'http://www.vmware.com/vcloud/v1.5'
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.edgeGatewayServiceConfiguration', self.href + '/action/configureServices', params, requests.codes.accepted, inspect.stack()[0][3], self.name)

    def get_nat_rules(self): 
            records = BeautifulSoup(self.get_entity(self.href),'xml').find('EdgeGatewayServiceConfiguration').find('NatService').find_all('NatRule',recursive=False)
            self.show_records('rule',records)
            return rules

    def set_nat_rule(self,rule_index,enable=None,network_name=None,original_ip=None,original_port=None,translated_ip=None,translated_port=None,protocol=None,icmp_sub_type=None): 
            params = BeautifulSoup(self.get_entity(self.href),'xml').find('EdgeGatewayServiceConfiguration')
            rules = params.find('NatService').find_all('NatRule',recursive=False)
            if rule_index not in range(len(rules)):
                logger.info("%s does not exist in %s" % (rule_index,self.name))
                return
            if enable != None:
                rules[rule_index].IsEnabled.string = str(enable).lower() 
            if network_name != None:
                network_record = self.get_record('orgVdcNetwork', 'OrgVdcNetworkRecord', 'name==' + network_name + ';vdcName==' + self.name, show=False)
                if len(network_record) == 0:
                    logger.info("%s does not exist in %s" % (network_name, self.name))
                    return
                rules[rule_index].GatewayNatRule.Interface['href'] = network_record[0]['href']
            if original_ip != None:
                rules[rule_index].GatewayNatRule.OriginalIp.string = original_ip 
            if translated_ip != None:
                rules[rule_index].GatewayNatRule.TranslatedIp.string = translated_ip 
            nat_type = rules[rule_index].RuleType.string
            if nat_type == 'DNAT':
                if protocol == 'icmp' and icmp_sub_type == None:
                    logger.info("icmp_sub_type must be specified for protocol icmp")
                    return                   
                if protocol == 'icmp' and icmp_sub_type not in Container.icmp_sub_types:
                    logger.info("%s not in %s" % (icmp_sub_type,Container.icmp_sub_types))
                    return
                if protocol == 'icmp' and icmp_sub_type:
                    rules[rule_index].GatewayNatRule.IcmpSubType.string = icmp_sub_type
                    original_port = 'any'
                    translated_port = 'any'
                if original_port != None:
                    rules[rule_index].GatewayNatRule.OriginalPort.string = original_port 
                if translated_port != None:
                    rules[rule_index].GatewayNatRule.TranslatedPort.string = translated_port 
            if protocol != None and protocol not in Container.edge_gateway_dnat_protocols:
                logger.info("%s not in %s" % (protocol,Container.edge_gateway_dnat_protocols))
                return
            if protocol != None:
                rules[rule_index].Protocol.string = protocol 
            params['xmlns'] = 'http://www.vmware.com/vcloud/v1.5'
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.edgeGatewayServiceConfiguration', self.href + '/action/configureServices', params, requests.codes.accepted, inspect.stack()[0][3], self.name)

    def add_nat_rule(self,nat_type,network_name,original_ip,translated_ip,enable=None,original_port=None,translated_port=None,protocol=None,icmp_sub_type=None): 
            params = BeautifulSoup(self.get_entity(self.href),'xml').find('EdgeGatewayServiceConfiguration')
            rule = Tag(builder=builder.TreeBuilder(),name='NatRule')
            if nat_type not in Container.edge_gateway_nat_types:
                logger.info("%s not in %s" % (nat_type,Container.edge_gateway_nat_types))
                return                       
            rule.append(Tag(builder=builder.TreeBuilder(),name='RuleType'))
            rule.RuleType.string = nat_type
            rule.append(Tag(builder=builder.TreeBuilder(),name='IsEnabled'))
            rule.IsEnabled.string = str(enable).lower() if enable != None else 'true'
            network_record = self.get_record('orgVdcNetwork', 'OrgVdcNetworkRecord', 'name==' + network_name + ';vdcName==' + self.name, show=False)
            if len(network_record) == 0:
                logger.info("%s does not exist in %s" % (network_name, self.name))
                return
            rule.append(Tag(builder=builder.TreeBuilder(),name='GatewayNatRule'))
            rule.GatewayNatRule.append(Tag(builder=builder.TreeBuilder(),name='Interface',attrs={'href':network_record[0]['href']}))
            rule.GatewayNatRule.append(Tag(builder=builder.TreeBuilder(),name='OriginalIp'))
            if nat_type == 'DNAT' and (original_port == None or translated_port == None):
                logger.info("original_port/translated_port must be specified for DNAT rule")
                return
            if protocol == 'icmp' and icmp_sub_type == None:
                logger.info("icmp_sub_type must be specified for protocol icmp")
                return                   
            if protocol == 'icmp' and icmp_sub_type not in Container.icmp_sub_types:
                logger.info("%s not in %s" % (icmp_sub_type,Container.icmp_sub_types))
                return
            if protocol == 'icmp' and icmp_sub_type:
                original_port = 'any'
                translated_port = 'any'
            rule.GatewayNatRule.OriginalIp.string = original_ip 
            if nat_type == 'DNAT':
                rule.GatewayNatRule.append(Tag(builder=builder.TreeBuilder(),name='OriginalPort'))
                rule.GatewayNatRule.OriginalPort.string = original_port 
            rule.GatewayNatRule.append(Tag(builder=builder.TreeBuilder(),name='TranslatedIp'))
            rule.GatewayNatRule.TranslatedIp.string = translated_ip 
            if nat_type == 'DNAT':
                rule.GatewayNatRule.append(Tag(builder=builder.TreeBuilder(),name='TranslatedPort'))
                rule.GatewayNatRule.TranslatedPort.string = translated_port 
                if protocol != None and protocol not in Container.edge_gateway_dnat_protocols:
                    logger.info("%s not in %s" % (protocol,Container.edge_gateway_dnat_protocols))
                    return
                rule.GatewayNatRule.append(Tag(builder=builder.TreeBuilder(),name='Protocol'))
                rule.GatewayNatRule.Protocol.string = protocol if protocol != None else 'TCP'
                if protocol == 'icmp' and icmp_sub_type:
                    rule.GatewayNatRule.append(Tag(builder=builder.TreeBuilder(),name='IcmpSubType'))
                    rule.GatewayNatRule.IcmpSubType.string = icmp_sub_type
            params.NatService.append(rule)
            params['xmlns'] = 'http://www.vmware.com/vcloud/v1.5'
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.edgeGatewayServiceConfiguration', self.href + '/action/configureServices', params, requests.codes.accepted, inspect.stack()[0][3], self.name)

    def del_nat_rule(self,rule_index): 
            params = BeautifulSoup(self.get_entity(self.href),'xml').find('EdgeGatewayServiceConfiguration')
            rules = params.find('NatService').find_all('NatRule',recursive=False)
            if rule_index not in range(len(rules)):
                logger.info("%s does not exist in %s" % (rule_index,self.name))
                return
            rules[rule_index].extract()
            params['xmlns'] = 'http://www.vmware.com/vcloud/v1.5'
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.edgeGatewayServiceConfiguration', self.href + '/action/configureServices', params, requests.codes.accepted, inspect.stack()[0][3], self.name)

    def get_static_routing(self): 
            return Container.convertXml2Yaml(str(BeautifulSoup(self.get_entity(self.href),'xml').find('StaticRoutingService')))

    def set_static_routing(self, enable): 
            params = BeautifulSoup(self.get_entity(self.href),'xml').find('EdgeGatewayServiceConfiguration')
            if params.find('StaticRoutingService') == None:
                params.append(Tag(builder=builder.TreeBuilder(),name='StaticRoutingService'))
                params.StaticRoutingService.append(Tag(builder=builder.TreeBuilder(),name='IsEnabled'))
            params.StaticRoutingService.IsEnabled.string = str(enable).lower() 
            params['xmlns'] = 'http://www.vmware.com/vcloud/v1.5'
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.edgeGatewayServiceConfiguration', self.href + '/action/configureServices', params, requests.codes.accepted, inspect.stack()[0][3], self.name)

    def get_static_routes(self): 
            records = BeautifulSoup(self.get_entity(self.href),'xml').find('EdgeGatewayServiceConfiguration').find('StaticRoutingService').find_all('StaticRoute',recursive=False)
            self.show_records('route',records)
            return records

    def set_static_route(self,route_index,name=None,subnet=None,next_hop_ip=None): 
            params = BeautifulSoup(self.get_entity(self.href),'xml').find('EdgeGatewayServiceConfiguration')
            routes = params.find('StaticRoutingService').find_all('StaticRoute',recursive=False)
            if route_index not in range(len(routes)):
                logger.info("%s does not exist in %s" % (route_index,self.name))
                return
            if name != None:
                routes[route_index].Name.string = name
            if subnet != None:
                routes[route_index].Network.string = subnet 
            if next_hop_ip != None:
                routes[route_index].NextHopIp.string = next_hop_ip 
            params['xmlns'] = 'http://www.vmware.com/vcloud/v1.5'
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.edgeGatewayServiceConfiguration', self.href + '/action/configureServices', params, requests.codes.accepted, inspect.stack()[0][3], self.name)

    def add_static_route(self,network_name,subnet,next_hop_ip,name=None): 
            network_record = self.get_record('orgVdcNetwork', 'OrgVdcNetworkRecord', 'name==' + network_name + ';vdcName==' + self.name, show=False)
            if len(network_record) == 0:
                logger.info("%s does not exist in %s" % (network_name, self.name))
                return
            params = BeautifulSoup(self.get_entity(self.href),'xml').find('EdgeGatewayServiceConfiguration')
            route = Tag(builder=builder.TreeBuilder(),name='StaticRoute')
            route.append(Tag(builder=builder.TreeBuilder(),name='Name'))
            route.Name.string = name if name != None else subnet
            route.append(Tag(builder=builder.TreeBuilder(),name='Network'))
            route.Network.string = subnet 
            route.append(Tag(builder=builder.TreeBuilder(),name='NextHopIp'))
            route.NextHopIp.string = next_hop_ip 
            route.append(Tag(builder=builder.TreeBuilder(),name='GatewayInterface',attrs={'href':network_record[0]['href']}))
            params.StaticRoutingService.append(route)
            params['xmlns'] = 'http://www.vmware.com/vcloud/v1.5'
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.edgeGatewayServiceConfiguration', self.href + '/action/configureServices', params, requests.codes.accepted, inspect.stack()[0][3], self.name)

    def del_static_route(self,route_index): 
            params = BeautifulSoup(self.get_entity(self.href),'xml').find('EdgeGatewayServiceConfiguration')
            routes = params.find('StaticRoutingService').find_all('StaticRoute',recursive=False)
            if route_index not in range(len(routes)):
                logger.info("%s does not exist in %s" % (route_index,self.name))
                return
            routes[route_index].extract()
            params['xmlns'] = 'http://www.vmware.com/vcloud/v1.5'
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.edgeGatewayServiceConfiguration', self.href + '/action/configureServices', params, requests.codes.accepted, inspect.stack()[0][3], self.name)
    
    def get_ipsec_vpn(self): 
            return Container.convertXml2Yaml(str(BeautifulSoup(self.get_entity(self.href),'xml').find('GatewayIpsecVpnService')))

    def set_ipsec_vpn(self, enable): 
            params = BeautifulSoup(self.get_entity(self.href),'xml').find('EdgeGatewayServiceConfiguration')
            if params.find('GatewayIpsecVpnService') == None:
                params.append(Tag(builder=builder.TreeBuilder(),name='GatewayIpsecVpnService'))
                params.GatewayIpsecVpnService.append(Tag(builder=builder.TreeBuilder(),name='IsEnabled'))
            params.GatewayIpsecVpnService.IsEnabled.string = str(enable).lower() 
            params['xmlns'] = 'http://www.vmware.com/vcloud/v1.5'
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.edgeGatewayServiceConfiguration', self.href + '/action/configureServices', params, requests.codes.accepted, inspect.stack()[0][3], self.name)

    def get_ipsec_vpn_endpoints(self): 
            records = BeautifulSoup(self.get_entity(self.href),'xml').find('EdgeGatewayServiceConfiguration').find('GatewayIpsecVpnService').find_all('Endpoint',recursive=False)
            self.show_records('endpoint',records)
            return records

    def set_ipsec_vpn_endpoint(self,endpoint_index,public_ip=None):
            params = BeautifulSoup(self.get_entity(self.href),'xml').find('EdgeGatewayServiceConfiguration')
            endpoints = params.find('GatewayIpsecVpnService').find_all('Endpoint',recursive=False)
            if endpoint_index not in range(len(endpoints)):
                logger.info("%s does not exist in %s" % (endpoint_index,self.name))
                return
            if public_ip != None:
                endpoints[endpoint_index].PublicIp.string = public_ip 
            params['xmlns'] = 'http://www.vmware.com/vcloud/v1.5'
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.edgeGatewayServiceConfiguration', self.href + '/action/configureServices', params, requests.codes.accepted, inspect.stack()[0][3], self.name)

    def get_ipsec_vpn_tunnels(self): 
            records = BeautifulSoup(self.get_entity(self.href),'xml').find('EdgeGatewayServiceConfiguration').find('GatewayIpsecVpnService').find_all('Endpoint',recursive=False)
            self.show_records('tunnel',records)
            return records

    def set_ipsec_vpn_tunnel(self,tunnel_index,name=None,peer_public_ip=None,peer_private_ip=None,peer_networks=[],local_public_ip=None,local_network_names=[],secret=None,encryption=None,enable=None): 
            params = BeautifulSoup(self.get_entity(self.href),'xml').find('EdgeGatewayServiceConfiguration')
            tunnels = params.find('GatewayIpsecVpnService').find_all('Endpoint',recursive=False)
            if tunnel_index not in range(len(tunnels)):
                logger.info("%s does not exist in %s" % (tunnel_index,self.name))
                return
            if name != None:
                tunnels[tunnel_index].Name.string = name
            if peer_public_ip != None:
                tunnels[tunnel_index].PeerIpAddress.string = peer_public_ip 
            if peer_public_ip != None and peer_private_ip == None:
                peer_private_ip = peer_public_ip
            if peer_private_ip != None:
                tunnels[tunnel_index].IpsecVpnThirdPartyPeer.PeerId.string = peer_private_ip 
                tunnels[tunnel_index].PeerId.string = peer_private_ip 
            if len(peer_networks) > 0:
                for subnet in tunnels[tunnel_index].find_all('PeerSubnet',recursive=False):
                    subnet.extract()
                for peer_network in peer_networks:
                    peer_network = netaddr.IPNetwork(peer_network) 
                    tunnels[tunnel_index].find_all('LocalSubnet',recursive=False)[-1].insert_after(Tag(builder=builder.TreeBuilder(),name='PeerSubnet'))
                    tunnels[tunnel_index].PeerSubnet.append(Tag(builder=builder.TreeBuilder(),name='Name'))
                    tunnels[tunnel_index].PeerSubnet.Name.string = str(peer_network)
                    tunnels[tunnel_index].PeerSubnet.append(Tag(builder=builder.TreeBuilder(),name='Gateway'))
                    tunnels[tunnel_index].PeerSubnet.Gateway.string = str(peer_network.network)
                    tunnels[tunnel_index].PeerSubnet.append(Tag(builder=builder.TreeBuilder(),name='Netmask'))
                    tunnels[tunnel_index].PeerSubnet.Netmask.string = str(peer_network.netmask)
            if local_public_ip != None:
                tunnels[tunnel_index].LocalIpAddress.string = local_public_ip 
                endpoint_network_href = BeautifulSoup(self.get_entity(self.href),'xml').find('Endpoint').find('PublicIp',text=local_public_ip).parent.Network['href']
                endpoint_interface = BeautifulSoup(self.get_entity(self.href),'xml').find('GatewayInterfaces').find('Network',attrs={'href':endpoint_network_href}).parent
                local_private_ip = endpoint_interface.SubnetParticipation.IpAddress.string
                tunnels[tunnel_index].LocalId.string = local_private_ip 
            if len(local_network_names) > 0:
                for subnet in tunnels[tunnel_index].find_all('LocalSubnet',recursive=False):
                    subnet.extract()
                for local_network_name in local_network_names: 
                    network_interface = BeautifulSoup(self.get_entity(self.href),'xml').find('GatewayInterfaces').find('Name',text=local_network_name).parent
                    tunnels[tunnel_index].LocalId.insert_after(Tag(builder=builder.TreeBuilder(),name='LocalSubnet'))
                    tunnels[tunnel_index].LocalSubnet.append(Tag(builder=builder.TreeBuilder(),name='Name'))
                    tunnels[tunnel_index].LocalSubnet.Name.string = local_network_name
                    tunnels[tunnel_index].LocalSubnet.append(Tag(builder=builder.TreeBuilder(),name='Gateway'))
                    tunnels[tunnel_index].LocalSubnet.Gateway.string = network_interface.SubnetParticipation.IpAddress.string
                    tunnels[tunnel_index].LocalSubnet.append(Tag(builder=builder.TreeBuilder(),name='Netmask'))
                    tunnels[tunnel_index].LocalSubnet.Netmask.string = network_interface.SubnetParticipation.Netmask.string
            if secret != None:
                tunnels[tunnel_index].SharedSecret.string = secret 
            if encryption != None and encryption not in Container.encryption_protocols:
                logger.info("%s not in %s" % (encryption, Container.encryption_protocols))
                return
            if encryption != None:
                tunnels[tunnel_index].EncryptionProtocol.string = encryption
            if enable != None:
                tunnels[tunnel_index].IsEnabled.string = str(enable).lower() 
            params['xmlns'] = 'http://www.vmware.com/vcloud/v1.5'
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.edgeGatewayServiceConfiguration', self.href + '/action/configureServices', params, requests.codes.accepted, inspect.stack()[0][3], self.name)

    def add_ipsec_vpn_tunnel(self,name,peer_public_ip,peer_networks,local_public_ip,local_network_names,secret,encryption,peer_private_ip=None,enable=True): 
            params = BeautifulSoup(self.get_entity(self.href),'xml').find('EdgeGatewayServiceConfiguration')
            tunnel = Tag(builder=builder.TreeBuilder(),name='Tunnel')
            tunnel.append(Tag(builder=builder.TreeBuilder(),name='Name'))
            tunnel.Name.string = name
            tunnel.append(Tag(builder=builder.TreeBuilder(),name='Description'))
            tunnel.append(Tag(builder=builder.TreeBuilder(),name='IpsecVpnThirdPartyPeer'))
            tunnel.IpsecVpnThirdPartyPeer.append(Tag(builder=builder.TreeBuilder(),name='PeerId'))
            if peer_private_ip == None:
                peer_private_ip = peer_public_ip
            tunnel.IpsecVpnThirdPartyPeer.PeerId.string = peer_private_ip
            tunnel.append(Tag(builder=builder.TreeBuilder(),name='PeerIpAddress'))
            tunnel.PeerIpAddress.string = peer_public_ip 
            tunnel.append(Tag(builder=builder.TreeBuilder(),name='PeerId'))
            # if direct, previous tag will be set
            tunnel.PeerIpAddress.next_sibling.string = peer_private_ip 
            endpoint_network_href = BeautifulSoup(self.get_entity(self.href),'xml').find('Endpoint').find('PublicIp',text=local_public_ip).parent.Network['href']
            endpoint_interface = BeautifulSoup(self.get_entity(self.href),'xml').find('GatewayInterfaces').find('Network',attrs={'href':endpoint_network_href}).parent
            local_private_ip = endpoint_interface.SubnetParticipation.IpAddress.string
            tunnel.append(Tag(builder=builder.TreeBuilder(),name='LocalIpAddress'))
            tunnel.LocalIpAddress.string = local_private_ip 
            tunnel.append(Tag(builder=builder.TreeBuilder(),name='LocalId'))
            tunnel.LocalId.string = local_public_ip 
            if len(local_network_names) == 0: 
                logger.info("local_network_name must be specified")
                return
            for local_network_name in local_network_names: 
                network_interface = BeautifulSoup(self.get_entity(self.href),'xml').find('GatewayInterfaces').find('Name',text=local_network_name).parent
                tunnel.LocalId.insert_after(Tag(builder=builder.TreeBuilder(),name='LocalSubnet'))
                tunnel.LocalSubnet.append(Tag(builder=builder.TreeBuilder(),name='Name'))
                tunnel.LocalSubnet.Name.string = local_network_name
                tunnel.LocalSubnet.append(Tag(builder=builder.TreeBuilder(),name='Gateway'))
                tunnel.LocalSubnet.Gateway.string = network_interface.SubnetParticipation.IpAddress.string
                tunnel.LocalSubnet.append(Tag(builder=builder.TreeBuilder(),name='Netmask'))
                tunnel.LocalSubnet.Netmask.string = network_interface.SubnetParticipation.Netmask.string
            if len(peer_networks) == 0: 
                logger.info("peer_network must be specified")
                return
            for peer_network in peer_networks:
                peer_network = netaddr.IPNetwork(peer_network) 
                tunnel.find_all('LocalSubnet',recursive=False)[-1].insert_after(Tag(builder=builder.TreeBuilder(),name='PeerSubnet'))
                tunnel.PeerSubnet.append(Tag(builder=builder.TreeBuilder(),name='Name'))
                tunnel.PeerSubnet.Name.string = str(peer_network)
                tunnel.PeerSubnet.append(Tag(builder=builder.TreeBuilder(),name='Gateway'))
                tunnel.PeerSubnet.Gateway.string = str(peer_network.network)
                tunnel.PeerSubnet.append(Tag(builder=builder.TreeBuilder(),name='Netmask'))
                tunnel.PeerSubnet.Netmask.string = str(peer_network.netmask)
            tunnel.append(Tag(builder=builder.TreeBuilder(),name='SharedSecret'))
            tunnel.SharedSecret.string = secret 
            tunnel.append(Tag(builder=builder.TreeBuilder(),name='SharedSecretEncrypted'))
            tunnel.SharedSecretEncrypted.string = 'false'
            if encryption not in Container.encryption_protocols:
                logger.info("%s not in %s" % (encryption, Container.encryption_protocols))
                return
            tunnel.append(Tag(builder=builder.TreeBuilder(),name='EncryptionProtocol'))
            tunnel.EncryptionProtocol.string = encryption
            tunnel.append(Tag(builder=builder.TreeBuilder(),name='Mtu'))
            tunnel.Mtu.string = '1500'
            tunnel.append(Tag(builder=builder.TreeBuilder(),name='IsEnabled'))
            tunnel.IsEnabled.string = str(enable).lower() 
            tunnel.append(Tag(builder=builder.TreeBuilder(),name='IsOperational'))
            tunnel.IsOperational.string = 'false'
            params.GatewayIpsecVpnService.append(tunnel)
            params['xmlns'] = 'http://www.vmware.com/vcloud/v1.5'
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.edgeGatewayServiceConfiguration', self.href + '/action/configureServices', params, requests.codes.accepted, inspect.stack()[0][3], self.name)

    def del_ipsec_vpn_tunnel(self,tunnel_index): 
            params = BeautifulSoup(self.get_entity(self.href),'xml').find('EdgeGatewayServiceConfiguration')
            tunnels = params.find('GatewayIpsecVpnService').find_all('Endpoint',recursive=False)
            if tunnel_index not in range(len(tunnels)):
                logger.info("%s does not exist in %s" % (tunnel_index,self.name))
                return
            tunnels[tunnel_index].extract()
            params['xmlns'] = 'http://www.vmware.com/vcloud/v1.5'
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.edgeGatewayServiceConfiguration', self.href + '/action/configureServices', params, requests.codes.accepted, inspect.stack()[0][3], self.name)

    def get_load_balancer(self): 
            return Container.convertXml2Yaml(str(BeautifulSoup(self.get_entity(self.href),'xml').find('LoadBalancerService')))

    def set_load_balancer(self, enable): 
            params = BeautifulSoup(self.get_entity(self.href),'xml').find('EdgeGatewayServiceConfiguration')
            if params.find('LoadBalancerService') == None:
                params.append(Tag(builder=builder.TreeBuilder(),name='LoadBalancerService'))
                params.LoadBalancerService.append(Tag(builder=builder.TreeBuilder(),name='IsEnabled'))
            params.LoadBalancerService.IsEnabled.string = str(enable).lower() 
            params['xmlns'] = 'http://www.vmware.com/vcloud/v1.5'
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.edgeGatewayServiceConfiguration', self.href + '/action/configureServices', params, requests.codes.accepted, inspect.stack()[0][3], self.name)

    def get_load_balancer_pools(self): 
            records = BeautifulSoup(self.get_entity(self.href),'xml').find('EdgeGatewayServiceConfiguration').find('LoadBalancerService').find_all('Pool',recursive=False)
            self.show_records('pool',records)
            return records

    def set_load_balancer_pool(self,pool_index,name=None,protocol=None,algorithm=None,port=None): 
            params = BeautifulSoup(self.get_entity(self.href),'xml').find('EdgeGatewayServiceConfiguration')
            pools = params.find('LoadBalancerService').find_all('Pool',recursive=False)
            if pool_index not in range(len(pools)):
                logger.info("%s does not exist in %s" % (pool_index,self.name))
                return
            old_name = pools[pool_index].Name.string
            if name != None:
                pools[pool_index].Name.string = name
                pool_refs = params.find('LoadBalancerService').find_all('Pool',text=old_name)
                for pool_ref in pool_refs:
                    pool_ref.string = name
            if protocol != 'HTTP' and algorithm == 'URI':
                logger.info("algorithm URI only available to protocol HTTP")
                return
            if protocol != None:
                if protocol not in Container.load_balancer_protocols.keys():
                    logger.info("%s not in %s" % (protocol, Container.load_balancer_protocols.keys()))
                    return
                pools[pool_index].ServicePort.Protocol.string = protocol
            if algorithm != None:
                if algorithm not in Container.load_balancer_algorithms:
                    logger.info("%s not in %s" % (algorithm, Container.load_balancer_algorithms))
                    return
                pools[pool_index].ServicePort.Algorithm.string = algorithm
            if protocol == 'TCP' and port == None:
                logger.info("port must be specified")
                return
            if port != None:
                pools[pool_index].ServicePort.Port.string = port 
            params['xmlns'] = 'http://www.vmware.com/vcloud/v1.5'
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.edgeGatewayServiceConfiguration', self.href + '/action/configureServices', params, requests.codes.accepted, inspect.stack()[0][3], self.name)

    def add_load_balancer_pool(self,name,member_ip,protocol='HTTP',algorithm='ROUND_ROBIN',http_uri='/',port=None,weight=None): 
            params = BeautifulSoup(self.get_entity(self.href),'xml').find('EdgeGatewayServiceConfiguration')
            pool = Tag(builder=builder.TreeBuilder(),name='Pool')
            pool.append(Tag(builder=builder.TreeBuilder(),name='Name'))
            pool.Name.string = name
            pool.append(Tag(builder=builder.TreeBuilder(),name='ServicePort'))
            pool.ServicePort.append(Tag(builder=builder.TreeBuilder(),name='IsEnabled'))
            pool.ServicePort.IsEnabled.string = 'true'
            if protocol not in Container.load_balancer_protocols.keys():
                logger.info("%s not in %s" % (protocol, Container.load_balancer_protocols.keys()))
                return
            pool.ServicePort.append(Tag(builder=builder.TreeBuilder(),name='Protocol'))
            pool.ServicePort.Protocol.string = protocol
            if algorithm not in Container.load_balancer_algorithms:
                logger.info("%s not in %s" % (algorithm, Container.load_balancer_algorithms))
                return
            if protocol != 'HTTP' and algorithm == 'URI':
                logger.info("algorithm URI only available to protocol HTTP")
                return
            pool.ServicePort.append(Tag(builder=builder.TreeBuilder(),name='Algorithm'))
            pool.ServicePort.Algorithm.string = algorithm
            if protocol == 'TCP' and port == None:
                logger.info("port must be specified")
                return
            pool.ServicePort.append(Tag(builder=builder.TreeBuilder(),name='Port'))
            pool.ServicePort.Port.string = port if port != None else Container.load_balancer_protocols[protocol] 
            pool.ServicePort.append(Tag(builder=builder.TreeBuilder(),name='HealthCheckPort'))
            pool.ServicePort.HealthCheckPort.string = pool.ServicePort.Port.string
            pool.ServicePort.append(Tag(builder=builder.TreeBuilder(),name='HealthCheck'))
            pool.ServicePort.HealthCheck.append(Tag(builder=builder.TreeBuilder(),name='Mode'))
            pool.ServicePort.HealthCheck.Mode.string = Container.load_balancer_healthchecks[protocol]
            if protocol == 'HTTP':
                pool.ServicePort.HealthCheck.append(Tag(builder=builder.TreeBuilder(),name='Uri'))
                pool.ServicePort.HealthCheck.Uri.string = http_uri 
            pool.ServicePort.HealthCheck.append(Tag(builder=builder.TreeBuilder(),name='HealthThreshold'))
            pool.ServicePort.HealthCheck.HealthThreshold.string = '2'
            pool.ServicePort.HealthCheck.append(Tag(builder=builder.TreeBuilder(),name='UnhealthThreshold'))
            pool.ServicePort.HealthCheck.UnhealthThreshold.string = '3'
            pool.ServicePort.HealthCheck.append(Tag(builder=builder.TreeBuilder(),name='Interval'))
            pool.ServicePort.HealthCheck.Interval.string = '5'
            pool.ServicePort.HealthCheck.append(Tag(builder=builder.TreeBuilder(),name='Timeout'))
            pool.ServicePort.HealthCheck.Timeout.string = '15'
            pool.append(Tag(builder=builder.TreeBuilder(),name='Member'))
            pool.Member.append(Tag(builder=builder.TreeBuilder(),name='IpAddress'))
            pool.Member.IpAddress.string = member_ip 
            pool.Member.append(Tag(builder=builder.TreeBuilder(),name='Weight'))
            pool.Member.Weight.string = weight if weight != None else '1' 
            pools = params.LoadBalancerService.find_all('Pool',recursive=False)
            if len(pools) > 0:
                pools[-1].insert_after(pool)
            else:
                params.LoadBalancerService.append(pool)               
            params['xmlns'] = 'http://www.vmware.com/vcloud/v1.5'
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.edgeGatewayServiceConfiguration', self.href + '/action/configureServices', params, requests.codes.accepted, inspect.stack()[0][3], self.name)

    def del_load_balancer_pool(self,pool_index): 
            params = BeautifulSoup(self.get_entity(self.href),'xml').find('EdgeGatewayServiceConfiguration')
            pools = params.find('LoadBalancerService').find_all('Pool',recursive=False)
            if pool_index not in range(len(pools)):
                logger.info("%s does not exist in %s" % (pool_index,self.name))
                return
            pools[pool_index].extract()
            params['xmlns'] = 'http://www.vmware.com/vcloud/v1.5'
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.edgeGatewayServiceConfiguration', self.href + '/action/configureServices', params, requests.codes.accepted, inspect.stack()[0][3], self.name)

    def get_load_balancer_pool_members(self,pool_index): 
            pools = BeautifulSoup(self.get_entity(self.href),'xml').find('EdgeGatewayServiceConfiguration').find('LoadBalancerService').find_all('Pool',recursive=False)
            if pool_index not in range(len(pools)):
                logger.info("%s does not exist in %s" % (pool_index,self.name))
                return
            records = pools[pool_index].find_all('Member')
            self.show_records('member',records)
            return records

    def set_load_balancer_pool_member(self,pool_index,member_index,member_ip=None,weight=None): 
            params = BeautifulSoup(self.get_entity(self.href),'xml').find('EdgeGatewayServiceConfiguration')
            pools = params.find('LoadBalancerService').find_all('Pool',recursive=False)
            if pool_index not in range(len(pools)):
                logger.info("%s does not exist in %s" % (pool_index,self.name))
                return
            members = pools[pool_index].find_all('Member')
            if member_index not in range(len(members)):
                logger.info("%s does not exist in %s" % (members_index,self.name))
                return
            if member_ip != None:
                members[member_index].IpAddress.string = member_ip 
            if weight != None:
                members[member_index].Weight.string = weight 
            params['xmlns'] = 'http://www.vmware.com/vcloud/v1.5'
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.edgeGatewayServiceConfiguration', self.href + '/action/configureServices', params, requests.codes.accepted, inspect.stack()[0][3], self.name)

    def add_load_balancer_pool_member(self,pool_index,member_ip,weight=None): 
            params = BeautifulSoup(self.get_entity(self.href),'xml').find('EdgeGatewayServiceConfiguration')
            pools = params.find('LoadBalancerService').find_all('Pool',recursive=False)
            if pool_index not in range(len(pools)):
                logger.info("%s does not exist in %s" % (pool_index,self.name))
                return
            member = Tag(builder=builder.TreeBuilder(),name='Member')
            member.append(Tag(builder=builder.TreeBuilder(),name='IpAddress'))
            member.IpAddress.string = member_ip 
            member.append(Tag(builder=builder.TreeBuilder(),name='Weight'))
            member.Weight.string = weight if weight != None else '1' 
            pools[pool_index].find_all('Member')[-1].insert_after(member)
            params['xmlns'] = 'http://www.vmware.com/vcloud/v1.5'
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.edgeGatewayServiceConfiguration', self.href + '/action/configureServices', params, requests.codes.accepted, inspect.stack()[0][3], self.name)

    def del_load_balancer_pool_member(self,pool_index,member_index): 
            params = BeautifulSoup(self.get_entity(self.href),'xml').find('EdgeGatewayServiceConfiguration')
            pools = params.find('LoadBalancerService').find_all('Pool',recursive=False)
            if pool_index not in range(len(pools)):
                logger.info("%s does not exist in %s" % (pool_index,self.name))
                return
            members = pools[pool_index].find_all('Member')
            if member_index not in range(len(members)):
                logger.info("%s does not exist in %s" % (members_index,self.name))
                return
            members[member_index].extract()
            params['xmlns'] = 'http://www.vmware.com/vcloud/v1.5'
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.edgeGatewayServiceConfiguration', self.href + '/action/configureServices', params, requests.codes.accepted, inspect.stack()[0][3], self.name)

    def get_load_balancer_virtual_servers(self): 
            records = BeautifulSoup(self.get_entity(self.href),'xml').find('EdgeGatewayServiceConfiguration').find('LoadBalancerService').find_all('VirtualServer',recursive=False)
            self.show_records('vserver',records)
            return records

    def set_load_balancer_virtual_server(self,vserver_index,enable=None,name=None,interface_name=None,vip=None,protocol=None,port=None,persistence=None,cookie_name=None,cookie_mode=None,logging=None,pool_name=None): 
            params = BeautifulSoup(self.get_entity(self.href),'xml').find('EdgeGatewayServiceConfiguration')
            vservers = params.find('LoadBalancerService').find_all('VirtualServer',recursive=False)
            if vserver_index not in range(len(vservers)):
                logger.info("%s does not exist in %s" % (vserver_index,self.name))
                return
            if enable != None:
                vservers[vserver_index].IsEnabled.string = str(enable).lower() 
            if name != None:
                vservers[vserver_index].Name.string = name 
            if interface_name != None:
                interface_href = BeautifulSoup(self.get_entity(self.href),'xml').find('GatewayInterfaces').find('Network',attrs={'name':interface_name})['href'] 
                vservers[vserver_index].Interface['href']=interface_href
            if vip != None:
                vservers[vserver_index].IpAddress.string = vip 
            if protocol != None:
                if protocol not in Container.load_balancer_protocols.keys():
                    logger.info("%s not in %s" % (protocol, Container.load_balancer_protocols.keys()))
                    return
                vservers[vserver_index].ServiceProfile.Protocol.string = protocol
            if port != None:
                vservers[vserver_index].ServiceProfile.Port.string = port 
            if persistence != None:
                if persistence != Container.load_balancer_persistences[protocol]:
                    logger.info("%s only supports %s" % (protocol, Container.load_balancer_persistences[protocol]))
                    return
                vservers[vserver_index].ServiceProfile.Persistence.Method.string = persistence
                if persistence == 'COOKIE':
                    if cookie_name != None:
                        vservers[vserver_index].ServiceProfile.Persistence.CookieName.string = cookie_name 
                    if cookie_mode != None:
                        if cookie_mode not in Container.load_balancer_cookie_modes:
                            logger.info("%s not in %s" % (cookie_mode, Container.load_balancer_cookie_modes))
                            return
                        vservers[vserver_index].ServiceProfile.Persistence.CookieMode.string = cookie_mode 
            if logging != None:
                vservers[vserver_index].Logging.string = str(logging).lower() 
            if pool_name != None:
                if params.find('LoadBalancerService').find('Name',text=pool_name).find_parent('Pool') == None:
                    logger.info("%s does not exist" % (pool_name))
                    return
                vservers[vserver_index].Pool.string = pool_name
            params['xmlns'] = 'http://www.vmware.com/vcloud/v1.5'
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.edgeGatewayServiceConfiguration', self.href + '/action/configureServices', params, requests.codes.accepted, inspect.stack()[0][3], self.name)

    def add_load_balancer_virtual_server(self,name,interface_name,vip,protocol,port,pool_name,persistence=None,cookie_name=None,cookie_mode=None): 
            params = BeautifulSoup(self.get_entity(self.href),'xml').find('EdgeGatewayServiceConfiguration')
            vserver = Tag(builder=builder.TreeBuilder(),name='VirtualServer')
            vserver.append(Tag(builder=builder.TreeBuilder(),name='IsEnabled'))
            vserver.IsEnabled.string = 'true'
            vserver.append(Tag(builder=builder.TreeBuilder(),name='Name'))
            vserver.Name.string = name
            interface_href = BeautifulSoup(self.get_entity(self.href),'xml').find('GatewayInterfaces').find('Network',attrs={'name':interface_name})['href'] 
            vserver.append(Tag(builder=builder.TreeBuilder(),name='Interface',attrs={'href':interface_href}))
            vserver.append(Tag(builder=builder.TreeBuilder(),name='IpAddress'))
            vserver.IpAddress.string = vip 
            vserver.append(Tag(builder=builder.TreeBuilder(),name='ServiceProfile'))
            vserver.ServiceProfile.append(Tag(builder=builder.TreeBuilder(),name='IsEnabled'))
            vserver.ServiceProfile.IsEnabled.string = 'true'
            if protocol not in Container.load_balancer_protocols.keys():
                logger.info("%s not in %s" % (protocol, Container.load_balancer_protocols.keys()))
                return
            vserver.ServiceProfile.append(Tag(builder=builder.TreeBuilder(),name='Protocol'))
            vserver.ServiceProfile.Protocol.string = protocol
            vserver.ServiceProfile.append(Tag(builder=builder.TreeBuilder(),name='Port'))
            vserver.ServiceProfile.Port.string = port if port != None else Container.load_balancer_protocols[protocol] 
            if persistence != None and persistence != Container.load_balancer_persistences[protocol]:
                logger.info("%s only supports %s" % (protocol, Container.load_balancer_persistences[protocol]))
                return
            if persistence != None:
                vserver.ServiceProfile.append(Tag(builder=builder.TreeBuilder(),name='Persistence'))
                vserver.ServiceProfile.Persistence.append(Tag(builder=builder.TreeBuilder(),name='Method'))
                vserver.ServiceProfile.Persistence.Method.string = persistence
                if persistence == 'COOKIE':
                    if cookie_name == None:
                        cookie_name = name 
                    if cookie_mode == None:
                        cookie_mode = 'INSERT'                   
                    if cookie_mode not in Container.load_balancer_cookie_modes:
                        logger.info("%s not in %s" % (cookie_mode, Container.load_balancer_cookie_modes))
                        return
                    vserver.ServiceProfile.Persistence.append(Tag(builder=builder.TreeBuilder(),name='CookieName'))
                    vserver.ServiceProfile.Persistence.CookieName.string = cookie_name
                    vserver.ServiceProfile.Persistence.append(Tag(builder=builder.TreeBuilder(),name='CookieMode'))
                    vserver.ServiceProfile.Persistence.CookieMode.string = cookie_mode
            vserver.append(Tag(builder=builder.TreeBuilder(),name='Logging'))
            vserver.Logging.string = 'true'
            if params.find('LoadBalancerService').find('Name',text=pool_name).find_parent('Pool') == None:
                logger.info("%s does not exist" % (pool_name))
                return
            vserver.append(Tag(builder=builder.TreeBuilder(),name='Pool'))
            vserver.Pool.string = pool_name
            vservers = params.LoadBalancerService.find_all('VirtualServer',recursive=False)
            if len(vservers) > 0:
                vservers[-1].insert_after(vserver)
            else:
                params.LoadBalancerService.append(vserver)               
            params['xmlns'] = 'http://www.vmware.com/vcloud/v1.5'
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.edgeGatewayServiceConfiguration', self.href + '/action/configureServices', params, requests.codes.accepted, inspect.stack()[0][3], self.name)

    def del_load_balancer_virtual_server(self,vserver_index): 
            params = BeautifulSoup(self.get_entity(self.href),'xml').find('EdgeGatewayServiceConfiguration')
            vservers = params.find('LoadBalancerService').find_all('VirtualServer',recursive=False)
            if vserver_index not in range(len(vservers)):
                logger.info("%s does not exist in %s" % (vserver_index,self.name))
                return
            vservers[vserver_index].extract()
            params['xmlns'] = 'http://www.vmware.com/vcloud/v1.5'
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('admin.edgeGatewayServiceConfiguration', self.href + '/action/configureServices', params, requests.codes.accepted, inspect.stack()[0][3], self.name)

    def reapply_services(self):
            self.api_post(self.href + '/action/reapplyServices', requests.codes.accepted, inspect.stack()[0][3])

    def redeploy(self):
            self.api_post(self.href + '/action/redeploy', requests.codes.accepted, inspect.stack()[0][3])

    def sync_syslog_setting(self):
            self.api_post(self.href + '/action/syncSyslogServerSettings', requests.codes.accepted, inspect.stack()[0][3])

class Vapp(Container):
    
    def __init__(self, name):
        Container.__init__(self, name)
        self.href = self.get_href()
        self.sections = {'':'vApp',
            '/action/controlAccess':'controlAccess',
            '/startupSection':'startupSection',
            '/networkConfigSection':'networkConfigSection',
            '/leaseSettingsSection':'leaseSettingsSection'}

    def get_href(self):
            return super(Vapp, self).get_href('vApp', 'VAppRecord')

    def set_vapp(self, name):
        params = BeautifulSoup(self.get_entity(self.href),'xml')
        params.VApp['name'] = name
        params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
        self.api_put_params('vcloud.vApp', self.href, params, requests.codes.accepted, inspect.stack()[0][3], name)

    def get_lease_settings(self, show=True):
        return self.get_section('/leaseSettingsSection',show)
 
    def set_lease_settings(self,deployment_lease_days,storage_lease_days):
            params = BeautifulSoup(self.get_section('/leaseSettingsSection', show=False),'xml')
            params.DeploymentLeaseInSeconds.string = str(int(deployment_lease_days)*38400) 
            params.StorageLeaseInSeconds.string= str(int(storage_lease_days)*38400) 
            self.set_section('/leaseSettingsSection',params)
 
    def get_control_access(self, show=True):
        return self.get_section('/controlAccess', show)
        
    def set_control_access_everyone(self,shared_to_everyone=True,access_level='ReadOnly'):
            if access_level not in Container.access_levels:
                logger.info("%s not in %s" % (access_level,Container.access_levels))
                return
            params = BeautifulSoup('<?xml version="1.0" encoding=""?>','xml')
            params.append(Tag(builder=builder.TreeBuilder(),name='ControlAccessParams',attrs={'xmlns':'http://www.vmware.com/vcloud/v1.5'}))
            params.ControlAccessParams.append(Tag(builder=builder.TreeBuilder(),name='IsSharedToEveryone'))
            params.ControlAccessParams.IsSharedToEveryone.string = str(shared_to_everyone).lower() 
            params.ControlAccessParams.append(Tag(builder=builder.TreeBuilder(),name='EveryoneAccessLevel'))
            params.ControlAccessParams.EveryoneAccessLevel.string = access_level
            self.set_section('/action/controlAccess',params)

    def get_control_access_subjects(self):
        records = BeautifulSoup(self.get_control_access()[0],'xml').find_all('AccessSetting')
        self.show_records('accessSetting',records)
        return records

    def add_control_access_subject(self,subject_type,subject_name,access_level):
        if subject_type == 'user':
            record_type = 'UserRecord'
        elif subject_type == 'group':
            record_type = 'GroupRecord'
        else:
            logger.info("%s not in user,group" % (subject_type))
            return
        subject_record = self.get_record(subject_type, record_type, 'name==' + subject_name, show=False)
        if len(subject_record) == 0:
            logger.info("%s does not exist" % (subject_name))
            return
        if access_level not in Container.access_levels:
            logger.info("%s not in %s" % (access_level,Container.access_levels))
            return
        access = Tag(builder=builder.TreeBuilder(),name='AccessSetting')
        access.append(Tag(builder=builder.TreeBuilder(),name='Subject',attrs={'href':subject_record[0]['href']}))
        access.append(Tag(builder=builder.TreeBuilder(),name='AccessLevel'))
        access.AccessLevel.string = access_level
        params = BeautifulSoup(self.get_section('/controlAccess', show=False),'xml')
        if params.find('AccessSettings') == None:
            params.ControlAccessParams.append(Tag(builder=builder.TreeBuilder(),name='AccessSettings'))
        params.find('AccessSettings').append(access)
        params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
        self.api_post_params('vcloud.controlAccess', self.href + '/action/controlAccess', params, requests.codes.ok, inspect.stack()[0][3], self.name)

    def del_control_access_subject(self,access_index):
        params = BeautifulSoup(self.get_control_access()[0],'xml')
        accesses = params.find_all('AccessSetting')
        if access_index not in range(len(accesses)):
            logger.info("%s does not exist in %s" % (access_index, self.name))
            return
        if len(accesses) == 1:
            params.find('AccessSettings').extract()
        else:
            accesses[access_index].extract()
        params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
        self.api_post_params('vcloud.controlAccess', self.href + '/action/controlAccess', params, requests.codes.ok, inspect.stack()[0][3], self.name)

    def get_startup_section(self, show=True):
        self.get_section('/startupSection', show)

    def set_startup_section(self,vm_index,order=None,start_action=None,start_delay=None,stop_action=None,stop_delay=None):
            params = BeautifulSoup(self.get_section('/startupSection', show=False),'xml')
            vms = params.find_all('Item')
            if vm_index not in range(len(vms)):
                logger.info("%s does not exist in %s" % (vm_index, self.name))
                return
            if order != None:
                vms[vm_index]['ovf:order'] = str(order) 
            if start_action != None:
                vms[vm_index]['ovf:startAction'] = start_action 
            if start_delay != None:
                vms[vm_index]['ovf:startDelay'] = str(start_delay) 
            if stop_action != None:
                vms[vm_index]['ovf:stopAction'] = stop_action 
            if stop_delay != None:
                vms[vm_index]['ovf:stopDelay'] = str(stop_delay) 
            self.set_section('/startupSection',params)

    def get_network(self, name=None, detailed=False, show=True):
        try:
            record_filter = 'vApp==' + self.href
            record_filter += ';name==' + name if name != None else ''
            return self.get_record('vAppNetwork', 'VAppNetworkRecord', record_filter, detailed=detailed, show=show)
        except:
            Container.handle_exception(sys.exc_info())

    def set_network(self,vapp_network_name,name):
            vapp_network_record = self.get_record('vAppNetwork', 'VAppNetworkRecord', 'name==' + vapp_network_name + ';vApp==' + self.href, show=False)
            if  len(vapp_network_record) == 0:
                logger.info("%s does not exist in %s" % (vapp_network_name, self.name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vapp_network_name))
                return
            params = BeautifulSoup(self.get_section('/networkConfigSection', show=False),'xml')
            nc = params.find('NetworkConfig',attrs={'networkName':vapp_network_name})
            nc['networkName'] = name 
            self.set_section('/networkConfigSection',params)

    def get_network_ip_in_use(self,vapp_network_name):
            vapp_network_record = self.get_record('vAppNetwork', 'VAppNetworkRecord', 'name==' + vapp_network_name + ';vApp==' + self.href, show=False)
            if  len(vapp_network_record) == 0:
                logger.info("%s does not exist in %s" % (vapp_network_name, self.name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vapp_network_name))
                return
            r = self.api_get(vapp_network_record[0]['href'] + '/allocatedAddresses')
            return r.content if r != None else None

    def get_network_ipranges(self,vapp_network_name):
            vapp_network_record = self.get_record('vAppNetwork', 'VAppNetworkRecord', 'name==' + vapp_network_name + ';vApp==' + self.href, show=False)
            if  len(vapp_network_record) == 0:
                logger.info("%s does not exist in %s" % (vapp_network_name, self.name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vapp_network_name))
                return
            records = BeautifulSoup(self.get_entity(vapp_network_record[0]['href']),'xml').find_all('IpRange')
            self.show_records('IpRange',records)
            return records

    def set_network_iprange(self,vapp_network_name,iprange_index,iprange_start=None,iprange_end=None):
            vapp_network_record = self.get_record('vAppNetwork', 'VAppNetworkRecord', 'name==' + vapp_network_name + ';vApp==' + self.href, show=False)
            if  len(vapp_network_record) == 0:
                logger.info("%s does not exist in %s" % (vapp_network_name, self.name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vapp_network_name))
                return
            params = BeautifulSoup(self.get_section('/networkConfigSection', show=False),'xml')
            nc = params.find('NetworkConfig',attrs={'networkName':vapp_network_name})
            ipranges = nc.find_all('IpRange')
            if iprange_index not in range(len(ipranges)):
                logger.info("%s does not exist in %s" % (iprange_index,network_name))
                return
            if iprange_start == None or iprange_end == None:
                logger.info("one of iprange_start or iprange_end must be specified")
                return
            if iprange_start != None:
                ipranges[iprange_index].StartAddress.string = iprange_start 
            if iprange_end != None:
                ipranges[iprange_index].EndAddress.string = iprange_end 
            self.set_section('/networkConfigSection',params)

    def add_network_iprange(self,vapp_network_name,iprange_start,iprange_end):
            vapp_network_record = self.get_record('vAppNetwork', 'VAppNetworkRecord', 'name==' + vapp_network_name + ';vApp==' + self.href, show=False)
            if  len(vapp_network_record) == 0:
                logger.info("%s does not exist in %s" % (vapp_network_name, self.name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vapp_network_name))
                return
            iprange = Tag(builder=builder.TreeBuilder(),name='IpRange')
            iprange.append(Tag(builder=builder.TreeBuilder(),name='StartAddress'))
            iprange.append(Tag(builder=builder.TreeBuilder(),name='EndAddress'))
            iprange.StartAddress.string = iprange_start 
            iprange.EndAddress.string = iprange_end 
            params = BeautifulSoup(self.get_section('/networkConfigSection', show=False),'xml')
            nc = params.find('NetworkConfig',attrs={'networkName':vapp_network_name})
            ipranges = nc.find_all('IpRange')
            ipranges[-1].insert_after(iprange)
            self.set_section('/networkConfigSection',params)

    def del_network_iprange(self,vapp_network_name,iprange_index):
            vapp_network_record = self.get_record('vAppNetwork', 'VAppNetworkRecord', 'name==' + vapp_network_name + ';vApp==' + self.href, show=False)
            if  len(vapp_network_record) == 0:
                logger.info("%s does not exist in %s" % (vapp_network_name, self.name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vapp_network_name))
                return
            params = BeautifulSoup(self.get_section('/networkConfigSection', show=False),'xml')
            nc = params.find('NetworkConfig',attrs={'networkName':vapp_network_name})
            ipranges = nc.find_all('IpRange')
            if iprange_index not in range(len(ipranges)):
                logger.info("%s does not exist in %s" % (iprange_index,vapp_network_name))
                return
            ipranges[iprange_index].extract()
            self.set_section('/networkConfigSection',params)

    def add_network(self,vapp_network_name,fence_mode,ipscope_gateway,ipscope_netmask,iprange_start=None,iprange_end=None,vdc_network_name=None):
            vapp_network_record = self.get_record('vAppNetwork', 'VAppNetworkRecord', 'name==' + vapp_network_name + ';vApp==' + self.href, show=False)
            if  len(vapp_network_record) > 0:
                logger.info("%s salerady exist" % (vapp_network_name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vapp_network_name))
                return
            if fence_mode not in Container.fence_modes:
                logger.info("%s not in %s" % (fence_mode, Container.fence_modes))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vapp_network_name))
                return
            if fence_mode != 'isolated' and not vdc_network_name:
                logger.info("vdc_network_name needed for %s" % (fence_mode))
                return
            if vdc_network_name:
                vapp_record = self.get_record('vApp', 'VAppRecord', 'href==' + self.href, show=False)
                vdc_network_record = self.get_record('orgVdcNetwork', 'OrgVdcNetworkRecord', 'name==' + vdc_network_name + ';vdc==' + vapp_record[0]['vdc'], show=False)
                if len(vdc_network_record) == 0:
                    logger.info("%s does not exist" % (vdc_network_name))
                    return
                vdc_network_href = vdc_network_record[0]['href']
            params = BeautifulSoup(self.get_section('/networkConfigSection', show=False),'xml')
            nc = Tag(builder=builder.TreeBuilder(),name='NetworkConfig',attrs={'networkName':vapp_network_name})
            nc.append(Tag(builder=builder.TreeBuilder(),name='Description'))
            nc.append(Tag(builder=builder.TreeBuilder(),name='Configuration'))
            nc.Configuration.append(Tag(builder=builder.TreeBuilder(),name='IpScopes'))
            nc.Configuration.IpScopes.append(Tag(builder=builder.TreeBuilder(),name='IpScope'))
            nc.Configuration.IpScopes.IpScope.append(Tag(builder=builder.TreeBuilder(),name='IsInherited'))
            nc.Configuration.IpScopes.IpScope.IsInherited.string = str(fence_mode == 'bridged').lower()
            nc.Configuration.IpScopes.IpScope.append(Tag(builder=builder.TreeBuilder(),name='Gateway'))
            nc.Configuration.IpScopes.IpScope.Gateway.string = ipscope_gateway 
            nc.Configuration.IpScopes.IpScope.append(Tag(builder=builder.TreeBuilder(),name='Netmask'))
            nc.Configuration.IpScopes.IpScope.Netmask.string = ipscope_netmask 
            nc.Configuration.IpScopes.IpScope.append(Tag(builder=builder.TreeBuilder(),name='IsEnabled'))
            nc.Configuration.IpScopes.IpScope.IsEnabled.string = 'true'
            if iprange_start and iprange_end:
                nc.Configuration.IpScopes.IpScope.append(Tag(builder=builder.TreeBuilder(),name='IpRanges'))
                nc.Configuration.IpScopes.IpScope.IpRanges.append(Tag(builder=builder.TreeBuilder(),name='IpRange'))
                nc.Configuration.IpScopes.IpScope.IpRanges.IpRange.append(Tag(builder=builder.TreeBuilder(),name='StartAddress'))
                nc.Configuration.IpScopes.IpScope.IpRanges.IpRange.StartAddress.string = iprange_start 
                nc.Configuration.IpScopes.IpScope.IpRanges.IpRange.append(Tag(builder=builder.TreeBuilder(),name='EndAddress'))
                nc.Configuration.IpScopes.IpScope.IpRanges.IpRange.EndAddress.string = iprange_end 
            if fence_mode != 'isolated':
                nc.Configuration.append(Tag(builder=builder.TreeBuilder(),name='ParentNetwork',attrs={
                    'href':vdc_network_href,
                    'name':vdc_network_name}))
            nc.Configuration.append(Tag(builder=builder.TreeBuilder(),name='FenceMode'))
            nc.Configuration.FenceMode.string = fence_mode
            nc.Configuration.append(Tag(builder=builder.TreeBuilder(),name='RetainNetInfoAcrossDeployments'))
            nc.Configuration.RetainNetInfoAcrossDeployments.string = 'false'
            params.NetworkConfigSection.append(nc)
            self.set_section('/networkConfigSection',params)

    def clone_network(self, vapp, vapp_network_name):
            nc = BeautifulSoup(vapp.get_section('/networkConfigSection', show=False),'xml').find('NetworkConfig',attrs={'networkName':vapp_network_name})
            if len(nc) == 0:
                logger.info("%s does not exist in %s" % (vapp_network_name, vapp.name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vapp.name + '.' + vapp_network_name))
                return
            params = BeautifulSoup(self.get_section('/networkConfigSection', show=False),'xml')
            params.NetworkConfigSection.append(nc)
            self.set_section('/networkConfigSection',params)

    def del_network(self, vapp_network_name):
            vapp_network_record = self.get_record('vAppNetwork', 'VAppNetworkRecord', 'name==' + vapp_network_name + ';vApp==' + self.href, show=False)
            if  len(vapp_network_record) == 0:
                logger.info("%s does not exist in %s" % (vapp_network_name, self.name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vapp_network_name))
                return
            params = BeautifulSoup(self.get_section('/networkConfigSection', show=False),'xml')
            params.find('NetworkConfig',attrs={'networkName':vapp_network_name}).decompose()
            self.set_section('/networkConfigSection',params)

    def get_network_dhcp(self, vapp_network_name):
            params = BeautifulSoup(self.get_section('/networkConfigSection', show=False),'xml')
            nc = params.find('NetworkConfig',attrs={'networkName':vapp_network_name})
            if len(nc) == 0:
                logger.info("%s does not exist in %s" % (vapp_network_name, self.name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vapp_network_name))
                return
            if nc.Configuration.find('Features'):
                return nc.Configuration.Features.find('DhcpService')
            else:
                return None

    def set_network_dhcp(self, vapp_network_name,enable=True,default_lease_time=3600,max_lease_time=7200,iprange_start=None,iprange_end=None):
            params = BeautifulSoup(self.get_section('/networkConfigSection', show=False),'xml')
            nc = params.find('NetworkConfig',attrs={'networkName':vapp_network_name})
            if len(nc) == 0:
                logger.info("%s does not exist in %s" % (vapp_network_name, self.name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vapp_network_name))
                return
            if nc.Configuration.FenceMode == 'bridged':
                logger.info("dhcp only available under isolated or natRouted network")
                return
            if nc.Configuration.find('Features') == None:
                nc.Configuration.append(Tag(builder=builder.TreeBuilder(),name='Features'))
            if nc.Configuration.Features.find('DhcpService') == None:
                nc.Configuration.Features.append(Tag(builder=builder.TreeBuilder(),name='DhcpService'))
                nc.Configuration.Features.DhcpService.append(Tag(builder=builder.TreeBuilder(),name='IsEnabled'))
                nc.Configuration.Features.DhcpService.append(Tag(builder=builder.TreeBuilder(),name='DefaultLeaseTime'))
                nc.Configuration.Features.DhcpService.append(Tag(builder=builder.TreeBuilder(),name='MaxLeaseTime'))
                nc.Configuration.Features.DhcpService.append(Tag(builder=builder.TreeBuilder(),name='IpRange'))
                nc.Configuration.Features.DhcpService.IpRange.append(Tag(builder=builder.TreeBuilder(),name='StartAddress'))
                nc.Configuration.Features.DhcpService.IpRange.append(Tag(builder=builder.TreeBuilder(),name='EndAddress'))
            nc.Configuration.Features.DhcpService.IsEnabled.string = str(enable).lower()
            nc.Configuration.Features.DhcpService.DefaultLeaseTime.string = str(default_lease_time)
            nc.Configuration.Features.DhcpService.MaxLeaseTime.string = str(max_lease_time)
            if iprange_start:
                nc.Configuration.Features.DhcpService.IpRange.StartAddress.string = iprange_start 
            if iprange_end:
                nc.Configuration.Features.DhcpService.IpRange.EndAddress.string = iprange_end 
            self.set_section('/networkConfigSection',params)

    def get_network_firewall(self, vapp_network_name):
            params = BeautifulSoup(self.get_section('/networkConfigSection', show=False),'xml')
            nc = params.find('NetworkConfig',attrs={'networkName':vapp_network_name})
            if len(nc) == 0:
                logger.info("%s does not exist in %s" % (vapp_network_name, self.name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vapp_network_name))
                return
            if nc.Configuration.FenceMode.string != 'natRouted':
                logger.info("firewall only available under natRouted network")
                return
            return nc.Configuration.Features.FirewallService

    def set_network_firewall(self, vapp_network_name,enable=None,default_action=None,log_default_action=None):
            params = BeautifulSoup(self.get_section('/networkConfigSection', show=False),'xml')
            nc = params.find('NetworkConfig',attrs={'networkName':vapp_network_name})
            if len(nc) == 0:
                logger.info("%s does not exist in %s" % (vapp_network_name, self.name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vapp_network_name))
                return
            if nc.Configuration.FenceMode.string != 'natRouted':
                logger.info("firewall only available under natRouted network")
                return
            if enable != None:
                nc.Configuration.Features.FirewallService.IsEnabled.string = str(enable).lower() 
            if default_action != None:
                nc.Configuration.Features.FirewallService.DefaultAction.string = default_action 
            if log_default_action != None:
                nc.Configuration.Features.FirewallService.LogDefaultAction.string = str(log_default_action).lower() 
            self.set_section('/networkConfigSection',params)

    def get_network_firewall_rules(self, vapp_network_name):
            params = BeautifulSoup(self.get_section('/networkConfigSection', show=False),'xml')
            nc = params.find('NetworkConfig',attrs={'networkName':vapp_network_name})
            if len(nc) == 0:
                logger.info("%s does not exist in %s" % (vapp_network_name, self.name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vapp_network_name))
                return
            if nc.Configuration.FenceMode.string != 'natRouted':
                logger.info("firewall only available under natRouted network")
                return
            records = nc.Configuration.Features.FirewallService.find_all('FirewallRule',recursive=False)
            self.show_records('rule',records)
            return records
    
    def set_network_firewall_rule(self,vapp_network_name,rule_index,enable=None,rule_name=None,action=None,protocols=None,dest_port=None,dest_ip=None,source_port=None,source_ip=None,log=None):
            params = BeautifulSoup(self.get_section('/networkConfigSection', show=False),'xml')
            nc = params.find('NetworkConfig',attrs={'networkName':vapp_network_name})
            if len(nc) == 0:
                logger.info("%s does not exist in %s" % (vapp_network_name, self.name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vapp_network_name))
                return
            if nc.Configuration.FenceMode.string != 'natRouted':
                logger.info("firewall only available under natRouted network")
                return
            rules = nc.Configuration.Features.FirewallService.find_all('FirewallRule',recursive=False)
            if rule_index not in range(len(rules)):
                logger.info("%s does not exist in %s" % (rule_index,vapp_network_name))
                return
            if enable != None:
                rules[rule_index].IsEnabled.string = str(enable).lower()
            rules[rule_index].MatchOnTranslate.string = 'false'
            if rule_name != None:
                rules[rule_index].Description.string = rule_name
            if action != None:
                rules[rule_index].Policy.string = action
            if protocols != None:
                if protocols not in Container.firewall_protocols:
                        logger.info("%s not in %s" % (protocols,Container.firewall_protocols))
                        return
                rules[rule_index].Protocols.clear()
                for protocol in protocols:
                    rules[rule_index].Protocols.append(Tag(builder=builder.TreeBuilder(),name=protocol))
                    rules[rule_index].Protocols.find(protocol).string = 'true'
            rules[rule_index].Port.string = '-1'
            if dest_port != None:
                rules[rule_index].DestinationPortRange.string = dest_port 
            if dest_ip != None:
                rules[rule_index].DestinationIp.string = dest_ip 
            rules[rule_index].SourcePort.string = '-1'
            if source_port != None:
                rules[rule_index].SourcePortRange.string = source_port 
            if source_ip != None:
                rules[rule_index].SourceIp.string = source_ip 
            rules[rule_index].EnableLogging.string = str(log).lower()
            self.set_section('/networkConfigSection',params)

    def add_network_firewall_rule(self,vapp_network_name,rule_index,enable=True,rule_name='',action='allow',protocols=['Tcp'],dest_port=None,dest_ip=None,source_port=None,source_ip=None,log=True):
            params = BeautifulSoup(self.get_section('/networkConfigSection', show=False),'xml')
            nc = params.find('NetworkConfig',attrs={'networkName':vapp_network_name})
            if len(nc) == 0:
                logger.info("%s does not exist in %s" % (vapp_network_name, self.name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vapp_network_name))
                return
            if nc.Configuration.FenceMode.string != 'natRouted':
                logger.info("firewall only available under natRouted network")
                return
            rule = Tag(builder=builder.TreeBuilder(),name='FirewallRule')
            rule.append(Tag(builder=builder.TreeBuilder(),name='IsEnabled'))
            rule.IsEnabled.string = str(enable).lower() 
            rule.append(Tag(builder=builder.TreeBuilder(),name='MatchOnTranslate'))
            rule.MatchOnTranslate.string = 'false'
            rule.append(Tag(builder=builder.TreeBuilder(),name='Description'))
            rule.Description.string = rule_name
            rule.append(Tag(builder=builder.TreeBuilder(),name='Policy'))
            if action not in Container.firewall_policies:
                logger.info("%s not in %s" % (action,Container.firewall_policies))
                return
            else:
                rule.Policy.string = action
            rule.append(Tag(builder=builder.TreeBuilder(),name='Protocols'))
            if protocols:
                if protocols not in Container.firewall_protocols:
                        logger.info("%s not in %s" % (protocols,Container.firewall_protocols))
                        return
                for protocol in protocols:
                    rule.Protocols.append(Tag(builder=builder.TreeBuilder(),name=protocol))
                    rule.Protocols.find(protocol).string = 'true'
            rule.append(Tag(builder=builder.TreeBuilder(),name='Port'))
            rule.Port.string = '-1'
            if dest_port:
                rule.append(Tag(builder=builder.TreeBuilder(),name='DestinationPortRange'))
                rule.DestinationPortRange.string = dest_port 
            else:
                logger.info("dest_port must be specified")
                return
            if dest_ip:
                rule.append(Tag(builder=builder.TreeBuilder(),name='DestinationIp'))
                rule.DestinationIp.string = dest_ip 
            else:
                logger.info("dest_ip must be specified")
                return
            rule.append(Tag(builder=builder.TreeBuilder(),name='SourcePort'))
            rule.SourcePort.string = '-1'
            if source_port:
                rule.append(Tag(builder=builder.TreeBuilder(),name='SourcePortRange'))
                rule.SourcePortRange.string = source_port 
            else:
                logger.info("source_port must be specified")
                return
            if source_ip:
                rule.append(Tag(builder=builder.TreeBuilder(),name='SourceIp'))
                rule.SourceIp.string = source_ip 
            else:
                logger.info("source_ip must be specified")
                return
            rule.append(Tag(builder=builder.TreeBuilder(),name='EnableLogging'))
            rule.EnableLogging.string = str(log).lower() 
            rules = nc.Configuration.Features.FirewallService.find_all('FirewallRule',recursive=False)
            if rule_index < len(rules):
                rules[rule_index].insert_before(rule)
            else:
                rules[-1].insert_after(rule)
            self.set_section('/networkConfigSection',params)

    def del_network_firewall_rule(self,vapp_network_name,rule_index):
            params = BeautifulSoup(self.get_section('/networkConfigSection', show=False),'xml')
            nc = params.find('NetworkConfig',attrs={'networkName':vapp_network_name})
            if len(nc) == 0:
                logger.info("%s does not exist in %s" % (vapp_network_name, self.name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vapp_network_name))
                return
            if nc.Configuration.FenceMode.string != 'natRouted':
                logger.info("firewall only available under natRouted network")
                return
            rules = nc.Configuration.Features.FirewallService.find_all('FirewallRule',recursive=False)
            if rule_index not in range(len(rules)):
                logger.info("%s does not exist in %s" % (rule_index,vapp_network_name))
                return
            rules[rule_index].extract()
            self.set_section('/networkConfigSection',params)

    def get_network_nat(self, vapp_network_name):
            params = BeautifulSoup(self.get_section('/networkConfigSection', show=False),'xml')
            nc = params.find('NetworkConfig',attrs={'networkName':vapp_network_name})
            if len(nc) == 0:
                logger.info("%s does not exist in %s" % (vapp_network_name, self.name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vapp_network_name))
                return
            if nc.Configuration.FenceMode.string != 'natRouted':
                logger.info("nat only available under natRouted network")
                return
            return nc.Configuration.Features.NatService

    def set_network_nat(self, vapp_network_name,enable=None,nat_type=None):
            params = BeautifulSoup(self.get_section('/networkConfigSection', show=False),'xml')
            nc = params.find('NetworkConfig',attrs={'networkName':vapp_network_name})
            if len(nc) == 0:
                logger.info("%s does not exist in %s" % (vapp_network_name, self.name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vapp_network_name))
                return
            if nc.Configuration.FenceMode.string != 'natRouted':
                logger.info("nat only available under natRouted network")
                return
            if nc.Configuration.Features.NatService == None:
                nc.Configuration.Features.append(Tag(builder=builder.TreeBuilder(),name='NatService'))
                nc.Configuration.Features.NatService.append(Tag(builder=builder.TreeBuilder(),name='IsEnabled'))
                nc.Configuration.Features.NatService.append(Tag(builder=builder.TreeBuilder(),name='NatType'))
                nc.Configuration.Features.NatService.append(Tag(builder=builder.TreeBuilder(),name='Policy'))
            if enable != None:
                nc.Configuration.Features.NatService.IsEnabled.string = str(enable).lower() 
            if nat_type != None:
                nc.Configuration.Features.NatService.NatType.string = nat_type 
            if nat_type == 'ipTranslation':
                nc.Configuration.Features.NatService.Policy.string = 'allowTrafficIn'
            if nat_type == 'portForwarding':
                nc.Configuration.Features.NatService.Policy.string = 'allowTraffic'
            self.set_section('/networkConfigSection',params)

    def get_network_nat_rules(self, vapp_network_name):
            params = BeautifulSoup(self.get_section('/networkConfigSection', show=False),'xml')
            nc = params.find('NetworkConfig',attrs={'networkName':vapp_network_name})
            if len(nc) == 0:
                logger.info("%s does not exist in %s" % (vapp_network_name, self.name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vapp_network_name))
                return
            if nc.Configuration.FenceMode.string != 'natRouted':
                logger.info("nat only available under natRouted network")
                return
            records = nc.Configuration.Features.NatService.find_all('NatRule',recursive=False)
            self.show_records('rule',records)
            return records

    def set_network_nat_rule(self,vapp_network_name,rule_index,mapping_mode=None,external_ip=None,external_port=None,internal_port=None,protocol=None):
            params = BeautifulSoup(self.get_section('/networkConfigSection', show=False),'xml')
            nc = params.find('NetworkConfig',attrs={'networkName':vapp_network_name})
            if len(nc) == 0:
                logger.info("%s does not exist in %s" % (vapp_network_name, self.name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vapp_network_name))
                return
            if nc.Configuration.FenceMode.string != 'natRouted':
                logger.info("nat only available under natRouted network")
                return
            rules = nc.Configuration.Features.NatService.find_all('NatRule',recursive=False)
            if rule_index not in range(len(rules)):
                logger.info("%s does not exist in %s" % (rule_index,vapp_network_name))
                return
            nat_type = nc.Configuration.Features.NatService.NatType.string
            if nat_type == 'ipTranslation':
                if mapping_mode != None:
                    rules[rule_index].MappingMode.string = mapping_mode
                if mapping_mode == 'manual' and external_ip == None:
                    logger.info("external_ip must be specified for manual mapping in ip_translation rule")
                    return
                if mapping_mode == 'manual' and external_ip != None:
                    rules[rule_index].ExternalIpAddress.string = external_ip
            if nat_type == 'portForwarding':
                if external_ip == None or external_port == None or internal_port == None or protocol == None:
                    logger.info("external_ip,external_port,internal_port,protocol must be specified in port_forwarding rule" )
                    return
                if protocol not in Container.vapp_port_forwarding_protocols:
                    logger.info("%s not in %s" % (protocol,Container.vapp_port_forwarding_protocols))
                    return
                rules[rule_index].ExternalIpAddress.string = external_ip 
                rules[rule_index].ExternalPort.string = external_port 
                rules[rule_index].InternalPort.string = internal_port 
                rules[rule_index].Protocol.string = protocol
            self.set_section('/networkConfigSection',params)

    def add_network_nat_rule(self,vapp_network_name,vm_name,nic_index,mapping_mode=None,external_ip=None,external_port=None,internal_port=None,protocol=None):
            vm_record = self.get_record('vm', 'VMRecord', 'name==' + vm_name + ';container==' + self.href, show=False)
            vm_entity = self.get_entity(vm_record[0]['href'])
            vapp_scoped_vm_id = BeautifulSoup(vm_entity,'xml').Vm.VAppScopedLocalId.string
            if len(vm_record) == 0:
                logger.info("%s does not exist in %s" % (vm_name, self.name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vm_name))
                return
            params = BeautifulSoup(self.get_section('/networkConfigSection', show=False),'xml')
            nc = params.find('NetworkConfig',attrs={'networkName':vapp_network_name})
            if len(nc) == 0:
                logger.info("%s does not exist in %s" % (vapp_network_name, self.name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vapp_network_name))
                return
            if nc.Configuration.FenceMode.string != 'natRouted':
                logger.info("nat only available under natRouted network")
                return
            rule = Tag(builder=builder.TreeBuilder(),name='NatRule')
            rule.append(Tag(builder=builder.TreeBuilder(),name='Id'))
            rule.Id.string = str(randint(65537,131072))
            nat_type = nc.Configuration.Features.NatService.NatType.string
            if nat_type == 'ipTranslation':
                if mapping_mode == None:
                    logger.info("mapping_mode must be specified in ip_translation rule" )
                    return
                rule.append(Tag(builder=builder.TreeBuilder(),name='OneToOneVmRule'))
                rule.OneToOneVmRule.append(Tag(builder=builder.TreeBuilder(),name='MappingMode'))
                if mapping_mode not in Container.vapp_ip_translation_mapping_modes:
                    logger.info("%s not in %s" % (mapping_mode,Container.vapp_ip_translation_mapping_modes))
                    return
                rule.OneToOneVmRule.MappingMode.string = mapping_mode
                rule.OneToOneVmRule.append(Tag(builder=builder.TreeBuilder(),name='ExternalIpAddress'))
                if mapping_mode == 'manual' and external_ip == None:
                    logger.info("external_ip must be specified for manual mapping in ip_translation rule")
                    return
                if mapping_mode == 'manual' and external_ip != None:
                    rule.OneToOneVmRule.ExternalIpAddress.string = external_ip 
                rule.OneToOneVmRule.append(Tag(builder=builder.TreeBuilder(),name='VAppScopedVmId'))
                rule.OneToOneVmRule.VAppScopedVmId.string = vapp_scoped_vm_id
                rule.OneToOneVmRule.append(Tag(builder=builder.TreeBuilder(),name='VmNicId'))
                rule.OneToOneVmRule.VmNicId.string = str(nic_index)
            if nat_type == 'portForwarding':
                if external_ip == None or external_port == None or internal_port == None or protocol == None:
                    logger.info("external_ip,external_port,internal_port,protocol must be specified in port_forwarding rule" )
                    return
                rule = Tag(builder=builder.TreeBuilder(),name='NatRule')
                rule.append(Tag(builder=builder.TreeBuilder(),name='Id'))
                rule.Id.string = str(randint(65537,131072))
                rule.append(Tag(builder=builder.TreeBuilder(),name='VmRule'))
                rule.VmRule.append(Tag(builder=builder.TreeBuilder(),name='ExternalIpAddress'))
                rule.VmRule.ExternalIpAddress.string = external_ip 
                rule.VmRule.append(Tag(builder=builder.TreeBuilder(),name='ExternalPort'))
                rule.VmRule.ExternalPort.string = str(external_port) 
                rule.VmRule.append(Tag(builder=builder.TreeBuilder(),name='VAppScopedVmId'))
                rule.VmRule.VAppScopedVmId.string = vapp_scoped_vm_id
                rule.VmRule.append(Tag(builder=builder.TreeBuilder(),name='VmNicId'))
                rule.VmRule.VmNicId.string = str(nic_index) 
                rule.VmRule.append(Tag(builder=builder.TreeBuilder(),name='InternalPort'))
                rule.VmRule.InternalPort.string = str(internal_port) 
                rule.VmRule.append(Tag(builder=builder.TreeBuilder(),name='Protocol'))
                rule.VmRule.Protocol.string = protocol
                if protocol not in Container.vapp_port_forwarding_protocols:
                    logger.info("%s not in %s" % (protocol,Container.vapp_port_forwarding_protocols))
                    return
                rule.append(Tag(builder=builder.TreeBuilder(),name='VmRule'))
                rule.VmRule.append(Tag(builder=builder.TreeBuilder(),name='ExternalIpAddress'))
                rule.VmRule.ExternalIpAddress.string = external_ip 
                rule.VmRule.append(Tag(builder=builder.TreeBuilder(),name='ExternalPort'))
                rule.VmRule.ExternalPort.string = str(external_port) 
                rule.VmRule.append(Tag(builder=builder.TreeBuilder(),name='VAppScopedVmId'))
                rule.VmRule.VAppScopedVmId.string = vapp_scoped_vm_id
                rule.VmRule.append(Tag(builder=builder.TreeBuilder(),name='VmNicId'))
                rule.VmRule.VmNicId.string = str(nic_index) 
                rule.VmRule.append(Tag(builder=builder.TreeBuilder(),name='InternalPort'))
                rule.VmRule.InternalPort.string = str(internal_port) 
                rule.VmRule.append(Tag(builder=builder.TreeBuilder(),name='Protocol'))
                rule.VmRule.Protocol.string = protocol
            nc.Configuration.Features.NatService.append(rule)
            self.set_section('/networkConfigSection',params)

    def del_network_nat_rule(self,vapp_network_name,rule_index):
            params = BeautifulSoup(self.get_section('/networkConfigSection', show=False),'xml')
            nc = params.find('NetworkConfig',attrs={'networkName':vapp_network_name})
            if len(nc) == 0:
                logger.info("%s does not exist in %s" % (vapp_network_name, self.name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vapp_network_name))
                return
            if nc.Configuration.FenceMode.string != 'natRouted':
                logger.info("nat only available under natRouted network")
                return
            rules = nc.Configuration.Features.NatService.find_all('NatRule',recursive=False)
            if rule_index not in range(len(rules)):
                logger.info("%s does not exist in %s" % (rule_index,vapp_network_name))
                return
            rules[rule_index].extract()
            self.set_section('/networkConfigSection',params)
    
    def get_network_static_routing(self, vapp_network_name):
            params = BeautifulSoup(self.get_section('/networkConfigSection', show=False),'xml')
            nc = params.find('NetworkConfig',attrs={'networkName':vapp_network_name})
            if len(nc) == 0:
                logger.info("%s does not exist in %s" % (vapp_network_name, self.name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vapp_network_name))
                return
            if nc.Configuration.FenceMode.string != 'natRouted':
                logger.info("static routing only available under natRouted network")
                return
            return nc.Configuration.Features.StaticRoutingService

    def set_network_static_routing(self, vapp_network_name,enable=None):
            params = BeautifulSoup(self.get_section('/networkConfigSection', show=False),'xml')
            nc = params.find('NetworkConfig',attrs={'networkName':vapp_network_name})
            if len(nc) == 0:
                logger.info("%s does not exist in %s" % (vapp_network_name, self.name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vapp_network_name))
                return
            if nc.Configuration.FenceMode.string != 'natRouted':
                logger.info("static routing only available under natRouted network")
                return
            if nc.Configuration.Features.StaticRoutingService == None:
                nc.Configuration.Features.append(Tag(builder=builder.TreeBuilder(),name='StaticRoutingService'))
                nc.Configuration.Features.StaticRoutingService.append(Tag(builder=builder.TreeBuilder(),name='IsEnabled'))
            if enable != None:
                nc.Configuration.Features.StaticRoutingService.IsEnabled.string = str(enable).lower() 
            self.set_section('/networkConfigSection',params)

    def get_network_static_routes(self, vapp_network_name):
            params = BeautifulSoup(self.get_section('/networkConfigSection', show=False),'xml')
            nc = params.find('NetworkConfig',attrs={'networkName':vapp_network_name})
            if len(nc) == 0:
                logger.info("%s does not exist in %s" % (vapp_network_name, self.name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vapp_network_name))
                return
            if nc.Configuration.FenceMode.string != 'natRouted':
                logger.info("static routing only available under natRouted network")
                return
            records = nc.Configuration.Features.StaticRoutingService.find_all('StaticRoute',recursive=False)
            self.show_records('route',records)
            return records

    def set_network_static_route(self,vapp_network_name,route_index,subnet=None,next_hop_ip=None):
            params = BeautifulSoup(self.get_section('/networkConfigSection', show=False),'xml')
            nc = params.find('NetworkConfig',attrs={'networkName':vapp_network_name})
            if len(nc) == 0:
                logger.info("%s does not exist in %s" % (vapp_network_name, self.name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vapp_network_name))
                return
            if nc.Configuration.FenceMode.string != 'natRouted':
                logger.info("static routing only available under natRouted network")
                return
            routes = nc.Configuration.Features.StaticRoutingService.find_all('StaticRoute',recursive=False)
            if route_index not in range(len(routes)):
                logger.info("%s does not exist in %s" % (route_index,vapp_network_name))
                return
            if subnet != None:
                routes[route_index].Name.string = subnet 
                routes[route_index].Network.string = subnet
            if next_hop_ip !=None:
                routes[route_index].NextHopIp.string = next_hop_ip 
            self.set_section('/networkConfigSection',params)

    def add_network_static_route(self,vapp_network_name,subnet=None,next_hop_ip=None):
            params = BeautifulSoup(self.get_section('/networkConfigSection', show=False),'xml')
            nc = params.find('NetworkConfig',attrs={'networkName':vapp_network_name})
            if len(nc) == 0:
                logger.info("%s does not exist in %s" % (vapp_network_name, self.name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vapp_network_name))
                return
            if nc.Configuration.FenceMode.string != 'natRouted':
                logger.info("static routing only available under natRouted network")
                return
            if subnet == None or next_hop_ip == None:
                logger.info("subnet,next_hop_ip must be specified in static route" )
                return
            route = Tag(builder=builder.TreeBuilder(),name='StaticRoute')
            route.append(Tag(builder=builder.TreeBuilder(),name='Name'))
            route.Name.string = subnet 
            route.append(Tag(builder=builder.TreeBuilder(),name='Network'))
            route.Network.string = subnet
            route.append(Tag(builder=builder.TreeBuilder(),name='NextHopIp'))
            route.NextHopIp.string = next_hop_ip 
            route.append(Tag(builder=builder.TreeBuilder(),name='Interface'))
            route.Interface.string = 'External'
            nc.Configuration.Features.StaticRoutingService.append(route)
            self.set_section('/networkConfigSection',params)

    def del_network_static_route(self,vapp_network_name,route_index):
            params = BeautifulSoup(self.get_section('/networkConfigSection', show=False),'xml')
            nc = params.find('NetworkConfig',attrs={'networkName':vapp_network_name})
            if len(nc) == 0:
                logger.info("%s does not exist in %s" % (vapp_network_name, self.name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vapp_network_name))
                return
            if nc.Configuration.FenceMode.string != 'natRouted':
                logger.info("static routing only available under natRouted network")
                return
            routes = nc.Configuration.Features.StaticRoutingService.find_all('StaticRoute',recursive=False)
            if route_index not in range(len(routes)):
                logger.info("%s does not exist in %s" % (route_index,vapp_network_name))
                return
            routes[route_index].extract()
            self.set_section('/networkConfigSection',params)

    def reset_network(self,vapp_network_name):
            vapp_network_record = self.get_record('vAppNetwork', 'VAppNetworkRecord', 'name==' + vapp_network_name + ';vApp==' + self.href, show=False)
            if  len(vapp_network_record) == 0:
                logger.info("%s does not exist in %s" % (vapp_network_name, self.name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vapp_network_name))
                return
            self.api_post(vapp_network_record[0]['href'].replace('/api','/api/admin') + '/action/reset', requests.codes.accepted, inspect.stack()[0][3])

    def sync_network_syslog_setting(self,vapp_network_name):
            vapp_network_record = self.get_record('vAppNetwork', 'VAppNetworkRecord', 'name==' + vapp_network_name + ';vApp==' + self.href, show=False)
            if  len(vapp_network_record) == 0:
                logger.info("%s does not exist in %s" % (vapp_network_name, self.name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vapp_network_name))
                return
            self.api_post(vapp_network_record[0]['href'].replace('/api','/api/admin') + '/action/syncSyslogServerSettings', requests.codes.accepted, inspect.stack()[0][3])

    def get_vm(self,name=None,detailed=False,show=True):
        try:
            record_filter = 'container==' + self.href
            record_filter += ';name==' +name if name != None else ''
            return self.get_record('vm','VMRecord', record_filter, detailed=detailed, show=show)
        except:
            Container.handle_exception(sys.exc_info())

    def add_vm(self, vm, source_delete=False, wait=True):
            vm_record = self.get_record('vm', 'VMRecord', 'href==' + vm.href, show=False)
            if not vm_record[0]['status'] == 'POWERED_OFF':
                logger.info("%s must be powered off" % (vm.name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vm.name))
                return
            params = BeautifulSoup('<?xml version="1.0" encoding=""?>','xml')
            params.append(Tag(builder=builder.TreeBuilder(),name='RecomposeVAppParams',attrs={'name':self.name,
                'xmlns':'http://www.vmware.com/vcloud/v1.5',
                'xmlns:ovf':'http://schemas.dmtf.org/ovf/envelope/1'}))
            params.RecomposeVAppParams.append(Tag(builder=builder.TreeBuilder(),name='Description'))
            # source vm
            params.RecomposeVAppParams.append(Tag(builder=builder.TreeBuilder(),name='SourcedItem',attrs={'sourceDelete':str(source_delete).lower()}))
            params.RecomposeVAppParams.SourcedItem.append(Tag(builder=builder.TreeBuilder(),name='Source',attrs={'href':vm.href}))
            vm_networks = BeautifulSoup(vm.get_section('/networkConnectionSection', show=False),'xml').find_all('NetworkConnection')
            for vm_network in vm_networks:
                # only clone networks if source is vapp
                if vm_record[0]['isVAppTemplate'] == 'false':
                    self.clone_network(vm.parent, vm_network['network'])
                    params.RecomposeVAppParams.SourcedItem.append(Tag(builder=builder.TreeBuilder(),name='NetworkAssignment',attrs={
                        'innerNetwork':vm_network['network'],
                        'containerNetwork':vm_network['network']}))
                if vm_record[0]['isVAppTemplate'] == 'true':
                    params.RecomposeVAppParams.SourcedItem.append(Tag(builder=builder.TreeBuilder(),name='NetworkAssignment',attrs={
                        'innerNetwork':vm_network['network'],
                        'containerNetwork':'none'}))
            # eula
            params.RecomposeVAppParams.append(Tag(builder=builder.TreeBuilder(),name='AllEULAsAccepted'))
            params.RecomposeVAppParams.AllEULAsAccepted.string = 'true'
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('vcloud.recomposeVAppParams', self.href + '/action/recomposeVApp', params, requests.codes.accepted, inspect.stack()[0][3], vm.name, wait)

    def del_vm(self, vm_name, wait=True):
            vm_record = self.get_record('vm', 'VMRecord', 'name==' + vm_name + ';container==' + self.href, show=False)
            if len(vm_record) == 0:
                logger.info("%s does not exist in %s" % (vm_name, self.name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vm_name))
                return
            if not vm_record[0]['status'] == 'POWERED_OFF':
                logger.info("%s must be powered off" % (vm_name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vm_name))
                return
            params = BeautifulSoup('<?xml version="1.0" encoding=""?>','xml')
            params.append(Tag(builder=builder.TreeBuilder(),name='RecomposeVAppParams',attrs={'name':self.name,
                'xmlns':'http://www.vmware.com/vcloud/v1.5',
                'xmlns:ovf':'http://schemas.dmtf.org/ovf/envelope/1'}))
            # delete vm
            params.RecomposeVAppParams.append(Tag(builder=builder.TreeBuilder(),name='DeleteItem',attrs={'href':vm_record[0]['href']}))
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('vcloud.recomposeVAppParams', self.href + 'recomposeVApp', params, requests.codes.accepted, inspect.stack()[0][3], vm_name)

    def get_snapshots(self, show=True):
        return self.get_section('/snapshotSection', show=False)

    def add_snapshot(self,name=None):
        if name == None:
            name = datetime.now().isoformat()
        params = BeautifulSoup('<?xml version="1.0" encoding=""?>','xml')
        params.append(Tag(builder=builder.TreeBuilder(),name='CreateSnapshotParams',attrs={'xmlns':'http://www.vmware.com/vcloud/v1.5',
            'name':name})) 
        params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
        self.api_post_params('vcloud.createSnapshotParams', self.href + '/action/createSnapshot', params, requests.codes.accepted, inspect.stack()[0][3], self.name)

    def del_snapshot(self):
        self.api_post(self.href + '/action/removeAllSnapshots', requests.codes.accepted, inspect.stack()[0][3])

    def revert_snapshot(self):
        self.api_post(self.href + '/action/revertToCurrentSnapshot', requests.codes.accepted, inspect.stack()[0][3])

class Catalog(Container):

    def __init__(self, name, parent):
        Container.__init__(self, name)
        self.href = self.get_href()
        self.admin_href = self.href.replace('/api','/api/admin')
        self.parent = parent
        self.sections = {'/action/controlAccess':'controlAccess'}

    def get_href(self):
        return super(Catalog, self).get_href('catalog', 'CatalogRecord')

    def set_catalog(self, name):
        params = BeautifulSoup(self.get_entity(self.admin_href),'xml')
        params.AdminCatalog['name'] = name
        params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
        self.api_put_params('admin.catalog', self.admin_href, params, requests.codes.ok, inspect.stack()[0][3], name)

    def set_storage_profile(self,vdc_name,storage_profile_name):
        storage_profile_record = self.get_record('orgVdcStorageProfile', 'OrgVdcStorageProfileRecord', 'vdcName==' + vdc_name + ';name==' + storage_profile_name, show=False)
        params = BeautifulSoup(self.get_entity(self.admin_href),'xml')
        if params.AdminCatalog.CatalogStorageProfiles.find('VdcStorageProfile') == None:
            params.AdminCatalog.CatalogStorageProfiles.append(Tag(builder=builder.TreeBuilder(),name='VdcStorageProfile',attrs={'href':storage_profile_record[0]['href']}))
        else:
            params.AdminCatalog.CatalogStorageProfiles.VdcStorageProfile['href'] = storage_profile_record[0]['href']
        params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
        self.api_put_params('admin.catalog', self.admin_href, params, requests.codes.ok, inspect.stack()[0][3], self.name)

    def sync(self):
        self.api_post(self.href + '/action/sync', requests.codes.accepted, inspect.stack()[0][3])

    def get_control_access(self):
        r = self.api_get(self.href.replace('/api','/api' + self.parent.href.replace(Container.api_url_prefix,'')) + '/controlAccess')
        records = [r.content if r != None else None]
        self.show_records('controlAccess', records)
        return records

    def set_control_access_everyone(self,shared_to_everyone=True,access_level='ReadOnly'):
        if access_level not in Container.access_levels:
            logger.info("%s not in %s" % (access_level,Container.access_levels))
            return
        params = BeautifulSoup('<?xml version="1.0" encoding=""?>','xml')
        params.append(Tag(builder=builder.TreeBuilder(),name='ControlAccessParams',attrs={'xmlns':'http://www.vmware.com/vcloud/v1.5'}))
        params.ControlAccessParams.append(Tag(builder=builder.TreeBuilder(),name='IsSharedToEveryone'))
        params.ControlAccessParams.IsSharedToEveryone.string = str(shared_to_everyone).lower() 
        params.ControlAccessParams.append(Tag(builder=builder.TreeBuilder(),name='EveryoneAccessLevel'))
        params.ControlAccessParams.EveryoneAccessLevel.string = access_level
        params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
        self.api_post_params('vcloud.controlAccess', self.href.replace('/api','/api' + self.parent.href.replace(Container.api_url_prefix,'')) + '/action/controlAccess', params, requests.codes.ok, inspect.stack()[0][3], self.name)

    def get_control_access_subjects(self):
        records = BeautifulSoup(self.get_control_access()[0],'xml').find_all('AccessSetting')
        self.show_records('accessSetting',records)
        return records

    def add_control_access_subject(self,subject_type,subject_name,access_level):
        if subject_type == 'user':
            record_type = 'UserRecord'
        elif subject_type == 'group':
            record_type = 'GroupRecord'
        else:
            logger.info("%s not in user,group" % (subject_type))
            return
        subject_record = self.get_record(subject_type, record_type, 'name==' + subject_name, show=False)
        if len(subject_record) == 0:
            logger.info("%s does not exist" % (subject_name))
            return
        if access_level not in Container.access_levels:
            logger.info("%s not in %s" % (access_level,Container.access_levels))
            return
        access = Tag(builder=builder.TreeBuilder(),name='AccessSetting')
        access.append(Tag(builder=builder.TreeBuilder(),name='Subject',attrs={'href':subject_record[0]['href']}))
        access.append(Tag(builder=builder.TreeBuilder(),name='AccessLevel'))
        access.AccessLevel.string = access_level
        params = BeautifulSoup(self.get_control_access()[0],'xml')
        if params.find('AccessSettings') == None:
            params.ControlAccessParams.append(Tag(builder=builder.TreeBuilder(),name='AccessSettings'))
        params.find('AccessSettings').append(access)
        params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
        self.api_post_params('vcloud.controlAccess', self.href.replace('/api','/api' + self.parent.href.replace(Container.api_url_prefix,'')) + '/action/controlAccess', params, requests.codes.ok, inspect.stack()[0][3], self.name)

    def del_control_access_subject(self,access_index):
        params = BeautifulSoup(self.get_control_access()[0],'xml')
        accesses = params.find_all('AccessSetting')
        if access_index not in range(len(accesses)):
            logger.info("%s does not exist in %s" % (access_index, self.name))
            return
        if len(accesses) == 1:
            params.find('AccessSettings').extract()
        else:
            accesses[access_index].extract()
        params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
        self.api_post_params('vcloud.controlAccess', self.href.replace('/api','/api' + self.parent.href.replace(Container.api_url_prefix,'')) + '/action/controlAccess', params, requests.codes.ok, inspect.stack()[0][3], self.name)

    def get_catalog_item(self,name=None,detailed=False,show=True):
        try:
            record_filter = 'catalogName==' + self.name
            record_filter += ';name==' +name if name != None else ''
            return self.get_record('catalogItem', 'CatalogItemRecord', record_filter, detailed=detailed, show=show)
        except:
            Container.handle_exception(sys.exc_info())

    def sync_catalog_item(self,catalog_item_index):
        catalog_items = self.get_record('catalogItem', 'CatalogItemRecord', 'catalogName==' + self.name, show=False)
        if catalog_item_index not in range(len(catalog_items)):
            logger.info("%s does not exist in %s" % (catalog_item_index,catalog_items[catalog_item_index]))
            return
        self.api_post(catalog_items[catalog_item_index]['href'] + '/action/sync', requests.codes.accepted, inspect.stack()[0][3])

    def get_vapp_template(self,name=None,detailed=False,show=True):
        try:
            record_filter = 'catalogName==' + self.name
            record_filter += ';name==' +name if name != None else ''
            return self.get_record('vAppTemplate', 'VAppTemplateRecord', record_filter, detailed=detailed, show=show)
        except:
            Container.handle_exception(sys.exc_info())

    def add_vapp_template(self, vdc_name, file_path=None, dummy_hardware_ver='vmx-10', vapp_name=None, source_catalog_name=None, source_vapp_template_name=None, source_delete=False):
        vdc_record = self.get_record('orgVdc', 'OrgVdcRecord', 'name==' + vdc_name, show=False)
        if len(vdc_record) == 0:
            logger.info("%s does not exist" % (vdc_name))
            logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vdc_name))
            return
        if file_path == None and vapp_name == None and source_vapp_template_name == None:
            logger.info("either file_path or vapp_name or source_vapp_template_name needed")
            return
        if file_path: 
            if file_path == 'dummy':
                ovf_content = BeautifulSoup('<?xml version="1.0" encoding=""?>','xml')
                envelope = Tag(builder=builder.TreeBuilder(),name='ovf:Envelope',attrs={'xmlns:ovf':'http://schemas.dmtf.org/ovf/envelope/1',
                    'xmlns:rasd':'http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_ResourceAllocationSettingData',
                    'xmlns:vcloud':'http://www.vmware.com/vcloud/v1.5',
                    'xmlns:vmw':'http://www.vmware.com/schema/ovf',
                    'xmlns:vssd':'http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_VirtualSystemSettingData'})
                ovf_content.append(envelope)
                envelope.append(Tag(builder=builder.TreeBuilder(),name='ovf:References'))

                collection = Tag(builder=builder.TreeBuilder(),name='ovf:VirtualSystemCollection',attrs={'ovf:id':'dummy'})
                envelope.append(collection)        
                collection.append(Tag(builder=builder.TreeBuilder(),name='ovf:Info'))
                tag = Tag(builder=builder.TreeBuilder(),name='ovf:Name')
                collection.append(tag)
                tag.string = 'dummy'

                vs = Tag(builder=builder.TreeBuilder(),name='ovf:VirtualSystem',attrs={'ovf:id':'dummy'})
                collection.append(vs)
                vs.append(Tag(builder=builder.TreeBuilder(),name='ovf:Info'))
                tag = Tag(builder=builder.TreeBuilder(),name='ovf:Name')
                tag.string = 'dummy'
                vs.append(tag)

                vhw = Tag(builder=builder.TreeBuilder(),name='ovf:VirtualHardwareSection')
                vs.append(vhw)
                vhw.append(Tag(builder=builder.TreeBuilder(),name='ovf:Info'))

                sys = Tag(builder=builder.TreeBuilder(),name='ovf:System')
                vhw.append(sys)
                sys.append(Tag(builder=builder.TreeBuilder(),name='vssd:ElementName'))
                sys.append(Tag(builder=builder.TreeBuilder(),name='vssd:InstanceID'))
                sys.append(Tag(builder=builder.TreeBuilder(),name='vssd:VirtualSystemIdentifier'))
                tag = Tag(builder=builder.TreeBuilder(),name='vssd:VirtualSystemType')
                tag.string = dummy_hardware_ver
                sys.append(tag)

                item = Tag(builder=builder.TreeBuilder(),name='ovf:Item')
                vhw.append(item)
                tag = Tag(builder=builder.TreeBuilder(),name='rasd:Address')
                tag.string = '0'
                item.append(tag)
                item.append(Tag(builder=builder.TreeBuilder(),name='rasd:Description'))
                tag = Tag(builder=builder.TreeBuilder(),name='rasd:ElementName')
                tag.string = 'IDE Controller 0'
                item.append(tag)
                tag = Tag(builder=builder.TreeBuilder(),name='rasd:InstanceID')
                tag.string = '1'
                item.append(tag)
                tag = Tag(builder=builder.TreeBuilder(),name='rasd:ResourceType')
                tag.string = '5'
                item.append(tag)

                item = Tag(builder=builder.TreeBuilder(),name='ovf:Item')
                vhw.append(item)
                tag = Tag(builder=builder.TreeBuilder(),name='rasd:AddressOnParent')
                tag.string = '0'
                item.append(tag)
                tag = Tag(builder=builder.TreeBuilder(),name='rasd:AutomaticAllocation')
                tag.string = 'false'
                item.append(tag)
                item.append(Tag(builder=builder.TreeBuilder(),name='rasd:Description'))
                tag = Tag(builder=builder.TreeBuilder(),name='rasd:ElementName')
                tag.string = 'Floppy Drive 1'
                item.append(tag)
                item.append(Tag(builder=builder.TreeBuilder(),name='rasd:HostResource'))
                tag = Tag(builder=builder.TreeBuilder(),name='rasd:InstanceID')
                tag.string = '8000'
                item.append(tag)
                tag = Tag(builder=builder.TreeBuilder(),name='rasd:ResourceType')
                tag.string = '14'
                item.append(tag)

                item = Tag(builder=builder.TreeBuilder(),name='ovf:Item')
                vhw.append(item)
                tag = Tag(builder=builder.TreeBuilder(),name='rasd:AddressOnParent')
                tag.string = '0'
                item.append(tag)
                tag = Tag(builder=builder.TreeBuilder(),name='rasd:AutomaticAllocation')
                tag.string = 'false'
                item.append(tag)
                item.append(Tag(builder=builder.TreeBuilder(),name='rasd:Description'))
                tag = Tag(builder=builder.TreeBuilder(),name='rasd:ElementName')
                tag.string = 'CD/DVD Drive 1'
                item.append(tag)
                item.append(Tag(builder=builder.TreeBuilder(),name='rasd:HostResource'))
                tag = Tag(builder=builder.TreeBuilder(),name='rasd:InstanceID')
                tag.string = '3000'
                item.append(tag)
                tag = Tag(builder=builder.TreeBuilder(),name='rasd:ResourceType')
                tag.string = '15'
                item.append(tag)

                item = Tag(builder=builder.TreeBuilder(),name='ovf:Item')
                vhw.append(item)
                tag = Tag(builder=builder.TreeBuilder(),name='rasd:AllocationUnits')
                tag.string = 'hertz * 10^6'
                item.append(tag)
                item.append(Tag(builder=builder.TreeBuilder(),name='rasd:Description'))
                tag = Tag(builder=builder.TreeBuilder(),name='rasd:ElementName')
                tag.string = '1 virtual CPU(s)'
                item.append(tag)
                tag = Tag(builder=builder.TreeBuilder(),name='rasd:InstanceID')
                tag.string = '2'
                item.append(tag)
                tag = Tag(builder=builder.TreeBuilder(),name='rasd:Reservation')
                tag.string = '0'
                item.append(tag)
                tag = Tag(builder=builder.TreeBuilder(),name='rasd:ResourceType')
                tag.string = '3'
                item.append(tag)
                tag = Tag(builder=builder.TreeBuilder(),name='rasd:VirtualQuantity')
                tag.string = '1'
                item.append(tag)
                item.append(Tag(builder=builder.TreeBuilder(),name='rasd:Weight'))
                tag = Tag(builder=builder.TreeBuilder(),name='vmw:CoresPerSocket',attrs={'ovf:required':'false'})
                tag.string = '1'
                item.append(tag)

                item = Tag(builder=builder.TreeBuilder(),name='ovf:Item')
                vhw.append(item)
                tag = Tag(builder=builder.TreeBuilder(),name='rasd:AllocationUnits')
                tag.string = 'byte * 2^20'
                item.append(tag)
                item.append(Tag(builder=builder.TreeBuilder(),name='rasd:Description'))
                tag = Tag(builder=builder.TreeBuilder(),name='rasd:ElementName')
                tag.string = '4 MB of memory'
                item.append(tag)
                tag = Tag(builder=builder.TreeBuilder(),name='rasd:InstanceID')
                tag.string = '3'
                item.append(tag)
                tag = Tag(builder=builder.TreeBuilder(),name='rasd:Reservation')
                tag.string = '0'
                item.append(tag)
                tag = Tag(builder=builder.TreeBuilder(),name='rasd:ResourceType')
                tag.string = '4'
                item.append(tag)
                tag = Tag(builder=builder.TreeBuilder(),name='rasd:VirtualQuantity')
                tag.string = '4'
                item.append(tag)
                item.append(Tag(builder=builder.TreeBuilder(),name='rasd:Weight'))
                ovf_content = etree.tostring(etree.fromstring(str(ovf_content)),pretty_print=True)
                with open('/tmp/dummy.ovf', "wb") as file:
                    file.write(ovf_content)
                self.upload_ovf('/tmp/dummy.ovf', vdc_name)
            elif not os.path.isfile(file_path):
                logger.info("%s does not exist" % (file_path))
                return
            elif file_path.endswith('.ova'):
                tar = tarfile.open(file_path)
                members = tar.getnames()
                tar.extractall('/tmp')
                tar.close()
                for member in members:
                    if member.endswith('.ovf'):
                        ovf_path = '/tmp/' + member
                    if member.endswith('.000000000'):
                        vmdk_name = member[:-10]
                        os.rename('/tmp/' + member, '/tmp/' + vmdk_name)
                self.upload_ovf(ovf_path, vdc_name)
            elif file_path.endswith('.ovf'):
                self.upload_ovf(file_path, vdc_name)
            else:
                logger.info("%s must be ovf or ova" % (file_path))
                return
        if vapp_name:
            vapp_record = self.get_record('vApp', 'VAppRecord', 'vdcName==' + vdc_name + ';name==' + vapp_name, show=False)
            if len(vapp_record) == 0:
                logger.info("%s does not exist" % (vapp_name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vapp_name))
                return
            params = BeautifulSoup('<?xml version="1.0" encoding=""?>','xml')
            params.append(Tag(builder=builder.TreeBuilder(),name='CaptureVAppParams',attrs={'xmlns':'http://www.vmware.com/vcloud/v1.5',
                'name':vapp_name}))
            params.CaptureVAppParams.append(Tag(builder=builder.TreeBuilder(),name='Description'))
            params.CaptureVAppParams.append(Tag(builder=builder.TreeBuilder(),name='Source',attrs={
                'href':vapp_record[0]['href'],
                'name':vapp_record[0]['name'],
                'type':'application/vnd.vmware.vcloud.vApp+xml'}))
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('vcloud.captureVAppParams', self.href + '/action/captureVApp', params, requests.codes.accepted, inspect.stack()[0][3], vapp_name)
            return
        if source_vapp_template_name and source_catalog_name:
            source_catalog_record = self.get_record('catalog', 'CatalogRecord', 'name==' + source_catalog_name, show=False)
            if len(source_catalog_name) == 0:
                logger.info("%s does not exist" % (source_catalog_name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], source_catalog_name))
                return
            source_vapp_template_record = self.get_record('vAppTemplate', 'VAppTemplateRecord', 'catalogName==' + source_catalog_name + ';name==' + source_vapp_template_name, show=False)
            if len(source_vapp_template_record) == 0:
                logger.info("%s does not exist in %s" % (source_vapp_template_name, source_catalog_name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], source_vapp_template_name))
                return
            params = BeautifulSoup('<?xml version="1.0" encoding=""?>','xml')
            params.append(Tag(builder=builder.TreeBuilder(),name='CloneVAppTemplateParams',attrs={'xmlns':'http://www.vmware.com/vcloud/v1.5',
                'name':source_vapp_template_record[0]['name']}))
            params.CloneVAppTemplateParams.append(Tag(builder=builder.TreeBuilder(),name='Source',attrs={'href':source_vapp_template_record[0]['href']}))
            params.CloneVAppTemplateParams.append(Tag(builder=builder.TreeBuilder(),name='IsSourceDelete'))
            params.CloneVAppTemplateParams.IsSourceDelete.string = str(source_delete).lower()
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('vcloud.cloneVAppTemplateParams', vdc_record[0]['href'] + '/action/cloneVAppTemplate', params, requests.codes.created, inspect.stack()[0][3], source_vapp_template_name)
        else:
            logger.info("both source_vapp_template_name and source_catalog_name needed")
            return
        
    def upload_ovf(self, ovf_path, vdc_name):
        if len(self.get_record('orgVdc', 'OrgVdcRecord', 'name==' + vdc_name, show=False)) == 0:
            logger.info("%s does not exist" % (vdc_name))
            logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vdc_name))
            return
        if not os.path.isfile(ovf_path):
            logger.info("%s does not exist" % (ovf_path))
            logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], ovf_path))
            return
        if not ovf_path.endswith('.ovf'):
            logger.info("invalid %s" % (ovf_path))
            logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], ovf_path))
            return
        ovf_content = open(ovf_path,'r').read()
        ovf_dirname = os.path.dirname(ovf_path)
        ovf_size = len(ovf_content)
        if BeautifulSoup(ovf_content,'xml').find('Envelope').find('VirtualSystemCollection'):
            ovf_name = BeautifulSoup(ovf_content,'xml').find('Envelope').find('VirtualSystemCollection')['ovf:id']
        elif BeautifulSoup(ovf_content,'xml').find('Envelope').find('VirtualSystem'):
            ovf_name = BeautifulSoup(ovf_content,'xml').find('Envelope').find('VirtualSystem')['ovf:id']
        else:
            logger.info("invalid %s" % (ovf_path))
            return
        ovf_record = self.get_record('vAppTemplate', 'VAppTemplateRecord', 'catalogName==' + self.name + ';name==' + ovf_name, show=False)
        ovf_href = None
        if len(ovf_record) > 0:
            if ovf_record[0]['status'] == 'RESOLVED':
                logger.info("%s alerady exists in %s" % (ovf_name, self.name))
                return
            elif ovf_record[0]['taskStatus'] == 'error':
                self.del_vapp_template(ovf_name)
            elif ovf_record[0]['taskStatus'] == 'running' or ovf_record[0]['taskStatus'] == 'queued':
                ovf_href = ovf_record[0]['href']
        if ovf_href == None:
            params = BeautifulSoup('<?xml version="1.0" encoding=""?>','xml')
            params.append(Tag(builder=builder.TreeBuilder(),name='UploadVAppTemplateParams',attrs={'xmlns:ovf':'http://schemas.dmtf.org/ovf/envelope/1',
                'xmlns':'http://www.vmware.com/vcloud/v1.5',
                'name':ovf_name}))
            params.find('UploadVAppTemplateParams').append(Tag(builder=builder.TreeBuilder(),name='Description'))
            # catalog storage set to *any
            storage_profile_record = self.get_record('orgVdcStorageProfile', 'OrgVdcStorageProfileRecord', 'vdcName==' + vdc_name + ';isDefaultStorageProfile==true', show=False)
            params.find('UploadVAppTemplateParams').append(Tag(builder=builder.TreeBuilder(),name='VdcStorageProfile',attrs={
                'href':storage_profile_record[0]['href'],
                'name':storage_profile_record[0]['name'],
                'type':'application/vnd.vmware.vcloud.vdcStorageProfile+xml'}))
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            r = self.api_post_params('vcloud.uploadVAppTemplateParams', self.href + '/action/upload', params, requests.codes.created, inspect.stack()[0][3], ovf_name)
            if r == None:
                return
            ovf_href = BeautifulSoup(r.content,'xml').CatalogItem.Entity['href']
        # initiate ovf upload
        ovf_entity = self.get_entity(ovf_href)
        transfer_files = BeautifulSoup(ovf_entity,'xml').Files.find_all('File')
        if len(transfer_files) == 1:
            transfer_file_href = transfer_files[0].Link['href']
            transfer_offset = int(transfer_files[0]['bytesTransferred'])
            api_headers = Container.api_headers.copy()
            api_headers['Content-lenght'] = ovf_size
            api_headers['Content-type'] = 'text/xml'
            api_headers['Content-Range'] = 'bytes ' + str(transfer_offset) + '-' + str(ovf_size) + '/' + str(ovf_size)
            try:
                it = UploadInChunks(ovf_path, transfer_offset, Container.chunk_size)
                r = requests.put(transfer_file_href, headers = api_headers, data=IterableToFileAdapter(it))
                if not r.status_code == requests.codes.ok:
                    raise ApiError(inspect.stack()[0][3] + ' ' + ovf_name, r.status_code, r.content)
                    return
            except requests.exceptions.ConnectionError as e:
                pass
            # check ovf upload status
            ovf_entity = self.get_entity(ovf_href)
            transfer_offset = int(BeautifulSoup(ovf_entity,'xml').Files.File['bytesTransferred'])
            if transfer_offset == ovf_size:
                logger.info("upload %s succeeded" % (ovf_name))
            else:
                logger.info("upload %s failed" % (ovf_name))
                return
        # wait for ovf import
        while True:
            ovf_entity = self.get_entity(ovf_href)
            if BeautifulSoup(ovf_entity,'xml').VAppTemplate['ovfDescriptorUploaded'] == 'true':
                break
        # upload vmdks
        vmdk_files = BeautifulSoup(ovf_entity,'xml').Files.find_all('File')
        for vmdk_file in vmdk_files:
            if 'descriptor.ovf' in vmdk_file.Link['href']:
                continue
            else:
                vmdk_path = ovf_dirname + '/' + vmdk_file.Link['href'].split('/')[-1]
                vmdk_size = os.path.getsize(vmdk_path)
                transfer_offset = int(vmdk_file['bytesTransferred'])
                if not os.path.isfile(vmdk_path):
                    logger.info("%s does not exist" % (vmdk_path))
                    return
                if transfer_offset == vmdk_size:
                    logger.info("%s already uploaded" % (vmdk_path))
                    continue
                # upload vmdk
                api_headers = {}
                api_headers['Content-lenght'] = vmdk_size
                api_headers['Content-Range'] = 'bytes ' + str(transfer_offset) + '-' + str(vmdk_size) + '/' + str(vmdk_size)
                try:
                    it = UploadInChunks(vmdk_path, transfer_offset, Container.chunk_size)
                    r = requests.put(vmdk_file.Link['href'], headers = api_headers, data=IterableToFileAdapter(it))
                    if not r.status_code == requests.codes.ok:
                        raise ApiError(inspect.stack()[0][3] + ' ' + ovf_name, r.status_code, r.content)
                        return
                except requests.exceptions.ConnectionError as e:
                    pass
                # check vmdk upload status
                ovf_entity = self.get_entity(ovf_href)
                vmdk_link = BeautifulSoup(ovf_entity,'xml').find('Link',attrs={'href':vmdk_file.Link['href']})
                transfer_offset = int(vmdk_link.parent['bytesTransferred'])
                if transfer_offset == vmdk_size:
                    logger.info("upload %s succeeded" % (vmdk_path))
                else:
                    logger.info("upload %s failed" % (vmdk_path))
                    return
        transfer_task_href = BeautifulSoup(ovf_entity,'xml').Tasks.Task['href']
        self.get_task_progress(transfer_task_href)

    def del_vapp_template(self, vapp_template_name, wait=True):
        vapp_template_record = self.get_record('vAppTemplate', 'VAppTemplateRecord', 'catalogName==' + self.name + ';name==' + vapp_template_name, show=False)
        if len(vapp_template_record) == 0:
            logger.info("%s does not exist in %s" % (vapp_template_name, self.name))
            logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vapp_template_name))
            return
        self.api_delete(vapp_template_record[0]['href'], inspect.stack()[0][3], vapp_template_name)

    def download_ovf(self, ovf_source, download_dirname):
        if not os.path.isdir(download_dirname):
            logger.info("%s does not exist" % (download_dirname))
            return
        self.api_post(ovf_source.href + '/action/enableDownload', requests.codes.accepted, inspect.stack()[0][3])
        # ovf
        ovf_source_entity = self.get_entity(ovf_source.href)
        ovf_href = BeautifulSoup(ovf_source_entity,'xml').find('Link',attrs={'rel':'download:default'})['href']
        ovf_name = ovf_href.split('/')[-1]
        ovf_path = download_dirname + '/' + ovf_name
        transfer_url = ovf_href.replace(ovf_name,'')
        with open(ovf_path, 'wb') as file:
            logger.info("downloading %s" % (ovf_name))
            r = requests.get(ovf_href, stream=True)
            file.write(r.content)
        # vmdk
        vmdk_files = BeautifulSoup(r.content,'xml').find_all('File')
        for vmdk_file in vmdk_files:
            vmdk_name = vmdk_file['ovf:href']
            vmdk_href = transfer_url + vmdk_name
            vmdk_path = download_dirname + '/' + vmdk_name
            with open(vmdk_path, 'wb') as file:
                logger.info("downloading %s" % (vmdk_name))
                r = requests.get(vmdk_href, stream=True)
                length = r.headers.get('content-length')
                if length is None:
                    file.write(r.content)
                else:
                    dl = 0
                    length = int(length)
                    for chunk in r.iter_content(Container.chunk_size):
                        dl += len(chunk)
                        file.write(chunk)
                        done = int(50 * dl / length)
                        sys.stdout.write("\r[%s%s]" % ('=' * done, ' ' * (50-done)))    
                        sys.stdout.flush()
                    print

    def get_media(self,name=None,detailed=False,show=True):
        try:
            record_filter = 'catalogName==' + self.name
            record_filter += ';name==' +name if name != None else ''
            return self.get_record('media', 'MediaRecord', record_filter, detailed=detailed, show=show)
        except:
            Container.handle_exception(sys.exc_info())

    def add_media(self, vdc_name, media_path=None, source_catalog_name=None, source_media_name=None, source_delete=False):
        vdc_record = self.get_record('orgVdc', 'OrgVdcRecord', 'name==' + vdc_name, show=False)
        if len(vdc_record) == 0:
            logger.info("%s does not exist" % (vdc_name))
            logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], vdc_name))
            return
        if media_path == None and source_media_name == None:
            logger.info("either media_path or source_media_name needed")
            return
        # upload
        if media_path:
            if not os.path.isfile(media_path):
                logger.info("%s does not exist" % (media_path))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], media_path))
                return
            media_name = os.path.basename(media_path)
            media_size = os.path.getsize(media_path)
            media_record = self.get_record('media', 'MediaRecord', 'catalogName==' + self.name + ';name==' + media_name, show=False)
            media_href = None
            if len(media_record) > 0:
                if media_record[0]['status'] == 'RESOLVED':
                    logger.info("%s alerady exists in %s" % (media_name, self.name))
                    return
                elif media_record[0]['status'] == 'FAILED_CREATION':
                    self.del_media(media_name)
                elif media_record[0]['status'] == 'UNKNOWN' and (media_record[0]['taskStatus'] == 'running' or media_record[0]['taskStatus'] == 'queued'):
                    media_href = media_record[0]['href']
            if media_href == None:
                params = BeautifulSoup('<?xml version="1.0" encoding=""?>','xml')
                params.append(Tag(builder=builder.TreeBuilder(),name='vcloud:Media',attrs={'xmlns:vcloud':'http://www.vmware.com/vcloud/v1.5',
                    'name':media_name,
                    'imageType':'iso',
                    'operationKey':'operationKey',
                    'size':media_size}))
                params.find('vcloud:Media').append(Tag(builder=builder.TreeBuilder(),name='vcloud:Description'))
                # catalog storage set to *any
                storage_profile_record = self.get_record('orgVdcStorageProfile', 'OrgVdcStorageProfileRecord', 'vdcName==' + vdc_name + ';isDefaultStorageProfile==true', show=False)[0]
                params.find('vcloud:Media').append(Tag(builder=builder.TreeBuilder(),name='vcloud:VdcStorageProfile',attrs={
                    'href':storage_profile_record[0]['href'],
                    'name':storage_profile_record[0]['name'],
                    'type':'application/vnd.vmware.vcloud.vdcStorageProfile+xml'}))
                params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
                r = self.api_post_params('vcloud.media', self.href + '/action/upload', params, requests.codes.created, inspect.stack()[0][3], media_name)
                if r == None:
                    return
                media_href = BeautifulSoup(r.content,'xml').CatalogItem.Entity['href']
            media_entity = self.get_entity(media_href)
            transfer_file_href = BeautifulSoup(media_entity,'xml').Files.File.Link['href']
            transfer_task_href = BeautifulSoup(media_entity,'xml').Tasks.Task['href']
            transfer_offset = int(BeautifulSoup(media_entity,'xml').Files.File['bytesTransferred'])

            api_headers = Container.api_headers.copy()
            api_headers['Content-lenght'] = media_size
            api_headers['Content-Range'] = 'bytes ' + str(transfer_offset) + '-' + str(media_size) + '/' + str(media_size)
            try:
                it = UploadInChunks(media_path, transfer_offset, Container.chunk_size)
                r = requests.put(transfer_file_href, headers = api_headers, data=IterableToFileAdapter(it))
                if not r.status_code == requests.codes.ok:
                    raise ApiError(inspect.stack()[0][3] + ' ' + media_name, r.status_code, r.content)
                    return
            except requests.exceptions.ConnectionError as e:
                pass
            media_entity = self.get_entity(media_href)
            transfer_offset = int(BeautifulSoup(media_entity,'xml').Files.File['bytesTransferred'])
            if transfer_offset == media_size:
                logger.info("upload %s succeeded" % (media_name))
            else:
                logger.info("upload %s failed" % (media_name))
                return
            self.get_task_progress(transfer_task_href)
            return
        if source_media_name and source_catalog_name:
            source_catalog_record = self.get_record('catalog', 'CatalogRecord', 'name==' + source_catalog_name, show=False)
            if len(source_catalog_name) == 0:
                logger.info("%s does not exist" % (source_catalog_name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], source_catalog_name))
                return
            source_media_record = self.get_record('media', 'MediaRecord', 'catalogName==' + source_catalog_name + ';name==' + source_media_name, show=False)
            if len(source_media_record) == 0:
                logger.info("%s does not exist in %s" % (source_media_name, source_catalog_name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], source_media_name))
                return
            params = BeautifulSoup('<?xml version="1.0" encoding=""?>','xml')
            params.append(Tag(builder=builder.TreeBuilder(),name='CloneMediaParams',attrs={'xmlns':'http://www.vmware.com/vcloud/v1.5',
                'name':source_media_record[0]['name']}))
            params.CloneMediaParams.append(Tag(builder=builder.TreeBuilder(),name='Source',attrs={'href':source_media_record[0]['href']}))
            params.CloneMediaParams.append(Tag(builder=builder.TreeBuilder(),name='IsSourceDelete'))
            params.CloneMediaParams.IsSourceDelete.string = str(source_delete).lower()
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('vcloud.cloneMediaParams', vdc_record[0]['href'] + '/action/cloneMedia', params, requests.codes.created, inspect.stack()[0][3], source_media_name)
        else:
            logger.info("both source_media_name and source_catalog_name needed")
            return

    def del_media(self, media_name, wait=True):
        media_record = self.get_record('media', 'MediaRecord', 'catalogName==' + self.name + ';name==' + media_name, show=False)
        if len(media_record) == 0:
            logger.info("%s does not exist in %s" % (media_name, self.name))
            logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], media_name))
            return
        self.api_delete(media_record[0]['href'], inspect.stack()[0][3], media_name)

    def download_media(self, media, download_dirname):
        if not os.path.isdir(download_dirname):
            logger.info("%s does not exist" % (download_dirname))
            return
        self.api_post(media.href + '/action/enableDownload', requests.codes.accepted, inspect.stack()[0][3])
        media_entity = self.get_entity(media.href)
        media_href = BeautifulSoup(media_entity,'xml').find('Link',attrs={'rel':'download:default'})['href']
        media_path = download_dirname + '/' + media.name
        with open(media_path, 'wb') as file:
            logger.info("downloading %s" % (media.name))
            r = requests.get(media_href, stream=True)
            length = r.headers.get('content-length')
            if length is None:
                file.write(r.content)
            else:
                dl = 0
                length = int(length)
                for chunk in r.iter_content(Container.chunk_size):
                    dl += len(chunk)
                    file.write(chunk)
                    done = int(50 * dl / length)
                    sys.stdout.write("\r[%s%s]" % ('=' * done, ' ' * (50-done)))    
                    sys.stdout.flush()
                print

class VappTemplate(Container):

    def __init__(self, name, parent):
        Container.__init__(self, name)
        self.parent = parent
        self.href = self.get_href(parent)

    def get_href(self, parent):
        vapp_template_record = self.get_record('vAppTemplate' , 'VAppTemplateRecord', 'name==' + self.name + ';catalogName==' + parent.name, show=False)
        if len(vapp_template_record) == 0:
            logger.info("%s not in %s" % (self.name, self.parent.name))
            logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], self.parent.name))
            return None
        return vapp_template_record[0]['href']

    def set_vapp_template(self, name):
        params = BeautifulSoup(self.get_entity(self.href),'xml')
        params.VAppTemplate['name'] = name
        params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
        self.api_put_params('vcloud.vAppTemplate', self.href, params, requests.codes.accepted, inspect.stack()[0][3], name)

    def get_vm(self,name=None,detailed=False,show=True):
        try:
            record_filter = 'container==' + self.href
            record_filter += ';name==' +name if name != None else ''
            return self.get_record('vm', 'VMecord', record_filter, detailed=detailed, show=show)
        except:
            Container.handle_exception(sys.exc_info())

class Media(Container):
    
    def __init__(self, name, parent):
        Container.__init__(self, name)
        self.parent = parent
        self.href = self.get_href(parent)

    def get_href(self, parent):
        media_record = self.get_record('media' , 'MediaRecord', 'name==' + self.name + ';catalogName==' + parent.name, show=False)
        if len(media_record) == 0:
            logger.info("%s not in %s" % (self.name, self.parent.name))
            logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], self.parent.name))
            return None
        return media_record[0]['href']

    def set_media(self, name):
        params = BeautifulSoup(self.get_entity(self.href),'xml')
        params.Media['name'] = name
        params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
        self.api_put_params('vcloud.media', self.href, params, requests.codes.accepted, inspect.stack()[0][3], name)

class Vm(Container):

    def __init__(self, name, parent):
        Container.__init__(self, name)
        self.parent = parent
        self.href = self.get_href(parent)
        self.sections = {'':'vm',
            '/operatingSystemSection':'operatingSystemSection',
            '/networkConnectionSection':'networkConnectionSection',
            '/guestCustomizationSection':'guestCustomizationSection',
            '/operatingSystemSection':'operatingSystemSection',
            '/productSections':'productSections',
            '/vmCapabilities':'vmCapabilitiesSection',
            '/virtualHardwareSection/cpu':'rasdItem',
            '/virtualHardwareSection/memory':'rasdItem',
            '/virtualHardwareSection/disks':'rasdItemsList',
            '/virtualHardwareSection/networkCards':'rasdItemsList'}

    def get_href(self, parent):
            vm_record = self.get_record('vm' , 'VMRecord', 'name==' + self.name + ';container==' + self.parent.href, show=False)
            if len(vm_record) == 0:
                logger.info("%s not in %s" % (self.name, self.parent.name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], self.parent.name))
                return None
            return vm_record[0]['href']

    def set_vm(self, name):
            params = BeautifulSoup(self.get_entity(self.href),'xml')
            params.Vm['name'] = name
            self.set_section('', params)
            self.name = name

    def get_storage_profile(self):
            records = BeautifulSoup(self.get_entity(self.href),'xml').find_all('StorageProfile')
            self.show_records('storageProfile',records)
            return records

    def set_storage_profile(self, storage_profile_name):
            vm_record = self.get_record('vm' , 'VMRecord', 'name==' + self.name + ';href==' + self.href, show=False)[0]
            storage_profile_record = self.get_record('orgVdcStorageProfile','OrgVdcStorageProfileRecord','name==' + storage_profile_name + ';vdc==' + vm_record['vdc'], show=False)
            if len(storage_profile_record) == 0:
                logger.info("%s does not exist" % (storage_profile_name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], storage_profile_name))
                return
            vm_entity = self.get_entity(self.href)
            params = BeautifulSoup(vm_entity,'xml')
            params.Vm.StorageProfile['name'] = storage_profile_record[0]['name']
            params.Vm.StorageProfile['href'] = storage_profile_record[0]['href']
            self.set_section('', params)

    def get_guest_customization(self, show=True):
            return self.get_section('/guestCustomizationSection', show=False)

    def set_guest_customization(self,enable_customization=None,change_sid=None,join_domain=False,use_org_settings=None,domain_name=None,domain_user=None,domain_password=None,admin_password_enable=None,admin_password_auto=None,admin_password=None,reset_password_required=None,customization_script=None,computer_name=None):
            if not enable_customization in [True, False]:
                logger.info("invalid input %s" % (str(enable_customization)))
                logger.info("%s %s failed" % (self.name, inspect.stack()[0][3]))
                return
            params = BeautifulSoup(self.get_section('/guestCustomizationSection', show=False),'xml')
            if enable_customization != None:
                params.GuestCustomizationSection.Enabled.string = str(enable_customization).lower() 
            if change_sid != None:
                params.GuestCustomizationSection.ChangeSid.string = str(change_sid).lower() 
            if join_domain != None:
                params.GuestCustomizationSection.JoinDomainEnabled.string = str(join_domain).lower() 
            if use_org_settings != None:
                params.GuestCustomizationSection.UseOrgSettings.string = str(use_org_settings).lower() 
            if domain_name != None:
                params.GuestCustomizationSection.DomainName.string = domain_name 
            if domain_user != None:
                params.GuestCustomizationSection.DomainUserName.string = domain_user 
            if domain_password != None:
                params.GuestCustomizationSection.DomainUserPassword.string = domain_password 
            if admin_password_enable != None:
                params.GuestCustomizationSection.AdminPasswordEnabled.string = str(admin_password_enable).lower() 
            if admin_password_auto != None:
                params.GuestCustomizationSection.AdminPasswordAuto.string = str(admin_password_auto).lower() 
            if admin_password != None:
                if params.GuestCustomizationSection.find('AdminPassword') == None:
                    params.GuestCustomizationSection.AdminPasswordAuto.insert_after(Tag(builder=builder.TreeBuilder(),name='AdminPassword'))
                params.GuestCustomizationSection.AdminPassword.string = admin_password 
            if reset_password_required != None:
                params.GuestCustomizationSection.ResetPasswordRequired.string = str(reset_password_required).lower() 
            if customization_script != None:
                params.GuestCustomizationSection.CustomizationScript.string = customization_script 
            if computer_name != None:
                params.GuestCustomizationSection.ComputerName.string = computer_name 
            self.set_section('/guestCustomizationSection',params)                   

    def get_operating_system(self, show=True):
            return self.get_section('/operatingSystemSection', show)

    def set_operating_system(self, os_type):
            os_type = str(os_type).lower()
            if os_type not in Container.os_types:
                logger.info("%s not in %s" % (os_type, Container.os_types.keys()))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], os_type))
                return
            params = BeautifulSoup(self.get_section('/operatingSystemSection', show=False),'xml')
            params.OperatingSystemSection['vmw:osType'] = os_type
            self.set_section('/operatingSystemSection',params)                   

    def get_vm_capabilities(self, show=True):
            return self.get_section('/vmCapabilities', show)

    def set_vm_capabilities(self):
            params = BeautifulSoup(sefl.get_section('/vmCapabilities', show=False),'xml')
            params.VmCapabilities.MemoryHotAddEnabled.string = 'true'
            params.VmCapabilities.CpuHotAddEnabled.string = 'true'
            self.set_section('/vmCapabilities',params)                   

    def get_custom_properties(self, show=True):
            self.get_section('/productSections', show=False)
 
    def add_custom_property(self,property_key,property_value):
            params = BeautifulSoup(self.get_section('/productSections', show=False),'xml')
            params.ProductSectionList['xmlns:ovf'] = 'http://schemas.dmtf.org/ovf/envelope/1'
            if params.ProductSectionList.find('ProductSection') == None:
                params.ProductSectionList.append(Tag(builder=builder.TreeBuilder(),name='ovf:ProductSection'))
                params.ProductSectionList.find('ovf:ProductSection').append(Tag(builder=builder.TreeBuilder(),name='ovf:Info'))
            params.ProductSectionList.find('ProductSection').append(Tag(builder=builder.TreeBuilder(),name='ovf:Property',attrs={'ovf:type':'string',
                'ovf:key':property_key,
                'ovf:value':property_value}))
            self.set_section('/productSections',params)

    def del_custom_property(self,property_index):
            params = BeautifulSoup(self.get_section('/productSections', show=False),'xml')
            params.ProductSectionList['xmlns:ovf'] = 'http://schemas.dmtf.org/ovf/envelope/1'
            properties = params.find_all('Property')
            if property_index not in range(len(properties)):
                logger.info("%s does not exist in %s" % (property_index,self.name))
                return
            properties[property_index].extract()
            self.set_section('/productSections',params)

    def get_vmtools(self, show=True):
        self.get_section('/runtimeInfoSection', show)

    def install_vmtools(self):
        self.api_post(self.href + '/action/installVMwareTools', requests.codes.accepted, inspect.stack()[0][3])

    def consolidate_snapshot(self):
        self.api_post(self.href + '/action/consolidate', requests.codes.accepted, inspect.stack()[0][3])

    def upgrade_hardware(self):
        self.api_post(self.href + '/action/upgradeHardwareVersion', requests.codes.accepted, inspect.stack()[0][3])

    def get_cpu(self, show=True):
        self.get_section('/virtualHardwareSection/cpu', show)

    def set_cpu(self,num_cpu,core_socket):
            if not str(num_cpu).isdigit() or not str(core_socket).isdigit():
                logger.info("invalid input %s or %s" % (num_cpu,core_socket))
                logger.info("%s %s failed" % (self.name, inspect.stack()[0][3]))
                return
            if not int(num_cpu) % int(core_socket) == 0:
                logger.info("%s not divisible by %s" % (num_cpu,core_socket))
                logger.info("%s %s failed" % (self.name, inspect.stack()[0][3]))
                return
            params = BeautifulSoup(self.get_section('/virtualHardwareSection/cpu', show=False),'xml')
            params.Item.find('VirtualQuantity').string = str(num_cpu)
            params.Item.find('CoresPerSocket').string = str(core_socket)
            self.set_section('/virtualHardwareSection/cpu', params)
    
    def get_memory(self, show=True):
        self.get_section('/virtualHardwareSection/memory', show)

    def set_memory(self,memory_size_mb):
            if not str(memory_size_mb).isdigit():
                logger.info("invalid input %s" % (memory_size_mb))
                logger.info("%s %s failed" % (self.name, inspect.stack()[0][3]))
                return
            params = BeautifulSoup(self.get_section('/virtualHardwareSection/memory', show=False),'xml')
            params.Item.find('VirtualQuantity').string = str(memory_size_mb)
            self.set_section('/virtualHardwareSection/memory', params)

    def get_disks(self, show=True):
        self.get_section('/virtualHardwareSection/disks', show)

    def set_disk(self,disk_index,disk_size_mb,storage_profile_name=None):
            if not str(disk_size_mb).isdigit():
                logger.info("invalid input %s" % (disk_size_mb))
                logger.info("%s %s failed" % (self.name, inspect.stack()[0][3]))
                return
            vm_record = self.get_record('vm' , 'VMRecord', 'name==' + self.name + ';href==' + self.href, show=False)[0]
            sp_name = storage_profile_name if storage_profile_name != None else vm_record['storageProfileName']
            storage_profile_record = self.get_record('orgVdcStorageProfile','OrgVdcStorageProfileRecord','name==' + sp_name + ';vdc==' + vm_record['vdc'], show=False)
            storage_available_mb = int(storage_profile_record[0]['storageLimitMB']) - int(storage_profile_record[0]['storageUsedMB'])
            if disk_size_mb > storage_available_mb:
                logger.info("%s requested but only %s left" % (disk_size_mb, storage_available_mb))
                return
            params = BeautifulSoup(self.get_section('/virtualHardwareSection/disks', show=False),'xml')
            for host_resource in params.RasdItemsList.find_all('HostResource'):
                host_resource['xmlns:vcloud'] = 'http://www.vmware.com/vcloud/v1.5'
                host_resource['vcloud:capacity'] = host_resource['capacity']
            params.RasdItemsList.find('AddressOnParent',text=str(disk_index)).parent.HostResource['vcloud:capacity'] = str(disk_size_mb)
            if storage_profile_name != vm_record['storageProfileName']:
               params.RasdItemsList.find('AddressOnParent',text=str(disk_index)).parent.HostResource['vcloud:storageProfileOverrideVmDefault'] = 'true' 
               params.RasdItemsList.find('AddressOnParent',text=str(disk_index)).parent.HostResource['vcloud:storageProfileHref'] = storage_profile_record[0]['href']
            self.set_section('/virtualHardwareSection/disks', params)

    def add_disk(self,disk_size_mb,bus_sub_type=None):
            if not str(disk_size_mb).isdigit():
                logger.info("invalid input %s" % (disk_size_mb))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], str(disk_size_mb)))
                return

            if bus_sub_type != None and bus_sub_type not in Container.disk_bus_sub_types.keys():
                logger.info("%s not in %s" % (bus_sub_type, Container.disk_bus_sub_types.keys()))
                return
            vm_record = self.get_record('vm' , 'VMRecord', 'name==' + self.name + ';href==' + self.href, show=False)[0]
            storage_profile_record = self.get_record('orgVdcStorageProfile','OrgVdcStorageProfileRecord','name==' + vm_record['storageProfileName'] + ';vdc==' + vm_record['vdc'], show=False)
            storage_available_mb = int(storage_profile_record[0]['storageLimitMB']) - int(storage_profile_record[0]['storageUsedMB'])
            if disk_size_mb > storage_available_mb:
                logger.info("%s requested but only %s left" % (disk_size_mb, storage_available_mb))
                return
            params = BeautifulSoup(self.get_section('/virtualHardwareSection/disks', show=False),'xml')
            for host_resource in params.RasdItemsList.find_all('HostResource'):
                host_resource['xmlns:vcloud'] = 'http://www.vmware.com/vcloud/v1.5'
                host_resource['vcloud:capacity'] = host_resource['capacity']
                host_resource['vcloud:busSubType'] = host_resource['busSubType']
                host_resource['vcloud:busType'] = host_resource['busType']
            item = Tag(builder=builder.TreeBuilder(),name='Item')
            tag = Tag(builder=builder.TreeBuilder(),name='rasd:AddressOnParent')
            tag.string = str(len(params.RasdItemsList.find_all('HostResource')))
            item.append(tag)
            item.append(Tag(builder=builder.TreeBuilder(),name='rasd:Description'))
            item.append(Tag(builder=builder.TreeBuilder(),name='rasd:ElementName'))
            tag = Tag(builder=builder.TreeBuilder(),name='rasd:HostResource')
            tag['xmlns:vcloud'] = 'http://www.vmware.com/vcloud/v1.5'
            tag['vcloud:capacity'] = str(disk_size_mb)
            if bus_sub_type != None:
                tag['vcloud:busSubType'] = bus_sub_type
                tag['vcloud:busType'] = Container.disk_bus_sub_types[bus_sub_type]
            else:
                tag['vcloud:busSubType'] = params.RasdItemsList.find_all('HostResource')[-1]['busSubType']
                tag['vcloud:busType'] = params.RasdItemsList.find_all('HostResource')[-1]['busType']
            item.append(tag)
            item.append(Tag(builder=builder.TreeBuilder(),name='rasd:InstanceID'))
            tag = Tag(builder=builder.TreeBuilder(),name='rasd:Parent')
            tag.string = params.RasdItemsList.find_all('Parent')[-1].string
            item.append(tag)
            tag = Tag(builder=builder.TreeBuilder(),name='rasd:ResourceType')
            tag.string = '17'
            item.append(tag)
            params.RasdItemsList.append(item)
            params.RasdItemsList['xmlns:rasd'] = 'http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_ResourceAllocationSettingData'
            self.set_section('/virtualHardwareSection/disks', params)

    def get_nics(self):
            records = BeautifulSoup(self.get_section('/networkConnectionSection', show=False),'xml').find_all('NetworkConnection')
            self.show_records('nic',records)
            return records

    def set_nic(self, nic_index, connected=False, primary_nic=False, vapp_network_name=None, ip_alloc_mode=None, ip_address=None, mac_address=None):
            if vapp_network_name != None and vapp_network_name != 'none':
                vapp_network_record = self.get_record('vAppNetwork', 'VAppNetworkRecord', 'name==' + vapp_network_name + ';vAppName==' + self.parent.name, show=False)
                if  len(vapp_network_record) == 0:
                    logger.info("%s does not exist" % (vapp_network_name))
                    return
            if not ip_alloc_mode == None:
                ip_alloc_mode = str(ip_alloc_mode).upper()
                if ip_alloc_mode not in Container.ip_alloc_modes:
                    logger.info("%s not in %s" % (ip_alloc_mode, Container.ip_alloc_modes))
                    return
            params = BeautifulSoup(self.get_section('/networkConnectionSection', show=False),'xml')
            nic = params.find('NetworkConnectionIndex',text=str(nic_index))
            if nic == None:
                logger.info("nic %s does not exist" % (nic_index))
                return
            if connected == True:
                nic.parent.IsConnected.string = 'true'
            elif connected == False:
                nic.parent.IsConnected.string = 'false'
            if primary_nic:
                nic.parent.parent.PrimaryNetworkConnectionIndex.string = str(nic_index)
            if vapp_network_name:
                nic.parent['network'] = vapp_network_name
            if ip_alloc_mode:
                nic.parent.IpAddressAllocationMode.string = ip_alloc_mode
            if ip_alloc_mode == 'MANUAL' and ip_address == None:
                logger.info("ip_address must be specified")
                return
            if ip_alloc_mode == 'MANUAL' and ip_address:
                if nic.parent.find('IpAddress') == None:
                    nic.parent.insert(2,Tag(builder=builder.TreeBuilder(),name='IpAddress'))
                nic.parent.IpAddress.string = ip_address 
            if mac_address:
                nic.parent.MACAddress.string = mac_address 
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.set_section('/networkConnectionSection', params)

    def add_nic(self,nic_type,vapp_network_name,ip_alloc_mode):
            nic_type = str(nic_type).lower()
            if nic_type not in Container.nic_types:
                logger.info("%s not in %s, default to e1000" % (nic_type, Container.nic_types))
                nic_type = 'E1000'
            vapp_network_record = self.get_record('vAppNetwork', 'VAppNetworkRecord', 'name==' + vapp_network_name + ';vAppName==' + self.parent.name, show=False)
            if  len(vapp_network_record) == 0:
                logger.info("%s does not exist, default to none" % (vapp_network_name))
                vapp_network_name = 'none'
            ip_alloc_mode = str(ip_alloc_mode).upper()
            if ip_alloc_mode not in Container.ip_alloc_modes:
                logger.info("%s not in %s, default to DHCP" % (ip_alloc_mode, Container.ip_alloc_modes))
                ip_alloc_mode = 'DHCP'
            params = BeautifulSoup(self.get_section('/virtualHardwareSection/networkCards', show=False),'xml')
            for connection in params.RasdItemsList.find_all('Connection'):
                connection['xmlns:vcloud'] = 'http://www.vmware.com/vcloud/v1.5'
                connection['vcloud:ipAddressingMode'] = connection['ipAddressingMode']
                connection['vcloud:primaryNetworkConnection'] = connection['primaryNetworkConnection']
            # only one new nic will be primary
            nics = params.RasdItemsList.find_all('AddressOnParent')
            if len(nics) > 0:
                i=0
                for nic in nics:
                    nics[i] = int(nic.string)
                    if nic.parent.find('Connection')['vcloud:primaryNetworkConnection'] == 'true':
                        primary_index = int(nic.string)
                    i=i+1
                missing = list(set(range(nics[len(nics)-1])[0:]) - set(nics))
                if len(missing) > 0:
                    nic_index = min(missing)
                else:
                    nic_index = len(nics)
            else:
                nic_index = 0
                primary_index = 0

            item = Tag(builder=builder.TreeBuilder(),name='Item')
            item.append(Tag(builder=builder.TreeBuilder(),name='rasd:Address'))
            tag = Tag(builder=builder.TreeBuilder(),name='rasd:AddressOnParent')
            tag.string = str(nic_index)
            item.append(tag)
            tag = Tag(builder=builder.TreeBuilder(),name='rasd:AutomaticAllocation')
            tag.string = 'true'
            item.append(tag)
            tag = Tag(builder=builder.TreeBuilder(),name='rasd:Connection')
            tag.string = vapp_network_name
            tag['xmlns:vcloud'] = 'http://www.vmware.com/vcloud/v1.5'
            tag['vcloud:ipAddressingMode'] = ip_alloc_mode
            if nic_index == 0 and primary_index == 0:
                tag['vcloud:primaryNetworkConnection']= 'true'
            else:
                tag['vcloud:primaryNetworkConnection']= 'false'
            item.append(tag)
            item.append(Tag(builder=builder.TreeBuilder(),name='rasd:Description'))
            item.append(Tag(builder=builder.TreeBuilder(),name='rasd:ElementName'))
            item.append(Tag(builder=builder.TreeBuilder(),name='rasd:InstanceID'))
            tag = Tag(builder=builder.TreeBuilder(),name='rasd:ResourceSubType')
            tag.string = nic_type 
            item.append(tag)
            tag = Tag(builder=builder.TreeBuilder(),name='rasd:ResourceType')
            tag.string = '10'
            item.append(tag)
            params.RasdItemsList.append(item)
            params.RasdItemsList['xmlns:rasd'] = 'http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_ResourceAllocationSettingData'
            self.set_section('/virtualHardwareSection/networkCards', params)

    def del_nic(self,nic_index):
            params = BeautifulSoup(self.get_section('/virtualHardwareSection/networkCards', show=False),'xml')
            if params.RasdItemsList.find('AddressOnParent',text=str(nic_index)) == None:
                logger.info("nic %s does not exist" % (str(nic_index)))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], str(nic_index)))
                return
            # restore namespaced attrs ripped by bs4
            for connection in params.RasdItemsList.find_all('Connection'):
                connection['xmlns:vcloud'] = 'http://www.vmware.com/vcloud/v1.5'
                connection['vcloud:ipAddressingMode'] = connection['ipAddressingMode']
                connection['vcloud:primaryNetworkConnection'] = connection['primaryNetworkConnection']
            # if removed is primary, set remaining lowest nic as primary
            if params.RasdItemsList.find('AddressOnParent',text=str(nic_index)).parent.find('Connection')['vcloud:primaryNetworkConnection'] == 'true':
                params.RasdItemsList.find('AddressOnParent',text=str(nic_index)).parent.decompose()
                nics = params.RasdItemsList.find_all('AddressOnParent')
                if len(nics) > 0:
                    i=0
                    for nic in nics:
                        nics[i] = int(nic.string)
                        i=i+1
                    primary_index = min(nics)
                    params.RasdItemsList.find('AddressOnParent',text=str(primary_index)).parent.find('Connection')['vcloud:primaryNetworkConnection'] = 'true'
            else:
                params.RasdItemsList.find('AddressOnParent',text=str(nic_index)).parent.decompose()
            self.set_section('/virtualHardwareSection/networkCards', params)

    def get_media(self):
            media = BeautifulSoup(self.get_entity(self.href),'xml').find('ResourceSubType',text='vmware.cdrom.iso')
            return media.parent.find('HostResource').string if media.has_attr('parent') else None

    def insert_media(self, media_name):
            # media must in vm vdc
            vm_record = self.get_record('vm' , 'VMRecord', 'name==' + self.name + ';href==' + self.href, show=False)[0]
            media_record = self.get_record('media' , 'MediaRecord', 'name==' + media_name + ';vdc==' + vm_record['vdc'], show=False)
            if len(media_record) == 0:
                logger.info("%s does not exist" % (media_name))
                logger.info("%s %s %s failed" % (self.name, inspect.stack()[0][3], media_name))
                return
            params = BeautifulSoup('<?xml version="1.0" encoding=""?>','xml')
            params.append(Tag(builder=builder.TreeBuilder(),name='ns6:MediaInsertOrEjectParams',attrs={'xmlns:ns6':'http://www.vmware.com/vcloud/v1.5'}))
            params.find('ns6:MediaInsertOrEjectParams').append(Tag(builder=builder.TreeBuilder(),name='ns6:Media',attrs={'type':'application/vnd.vmware.vcloud.media+xml',
                'name':media_name,
                'href':media_record[0]['href']}))
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('vcloud.mediaInsertOrEjectParams', self.href + '/media/action/insertMedia', params, requests.codes.accepted, inspect.stack()[0][3], media_name)

    def eject_media(self):
            vm_entity = self.get_entity(self.href)
            media = BeautifulSoup(vm_entity,'xml').find('ResourceSubType',text='vmware.cdrom.iso')
            if media == None:
                logger.info("%s has no media inserted" % (self.name))
                logger.info("%s %s failed" % (self.name, inspect.stack()[0][3]))
                return
            else:
                media_name = media.parent.find('HostResource').string
            # media must in vm vdc
            vm_record = self.get_record('vm' , 'VMRecord', 'name==' + self.name + ';href==' + self.href, show=False)[0]
            media_record = self.get_record('media' , 'MediaRecord', 'name==' + media_name + ';vdc==' + vm_record['vdc'], show=False)
            params = BeautifulSoup('<?xml version="1.0" encoding=""?>','xml')
            params.append(Tag(builder=builder.TreeBuilder(),name='ns6:MediaInsertOrEjectParams',attrs={'xmlns:ns6':'http://www.vmware.com/vcloud/v1.5'}))
            params.find('ns6:MediaInsertOrEjectParams').append(Tag(builder=builder.TreeBuilder(),name='ns6:Media',attrs={'type':'application/vnd.vmware.vcloud.media+xml',
                'name':media_name,
                'href':media_record[0]['href']}))
            params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
            self.api_post_params('vcloud.mediaInsertOrEjectParams', self.href + '/media/action/ejectMedia', params, requests.codes.accepted, inspect.stack()[0][3], media_name)

    def get_independent_disk(self,detailed=False,show=True):
        try:
            record_filter = 'vm==' + self.href
            return self.get_record('vmDiskRelation' , 'VmDiskRelationRecord', record_filter, detailed=detailed, show=show)
        except:
            Container.handle_exception(sys.exc_info())

    def attach_independent_disk(self,vdc_disk_index):
        vm_record = self.get_record('vm' , 'VMRecord', 'name==' + self.name + ';href==' + self.href, show=False)[0]
        vdc_disks = self.get_record('disk', 'DiskRecord', 'vdc==' + vm_record['vdc'], show=False)
        if vdc_disk_index not in range(len(vdc_disks)):
            logger.info("%s does not exist in %s" % (vdc_disk_index,vm_record['vdcName']))
            return
        params = BeautifulSoup('<?xml version="1.0" encoding=""?>','xml')
        params.append(Tag(builder=builder.TreeBuilder(),name='DiskAttachOrDetachParams',attrs={'xmlns':'http://www.vmware.com/vcloud/v1.5'}))
        params.DiskAttachOrDetachParams.append(Tag(builder=builder.TreeBuilder(),name='Disk',attrs={'href':vdc_disks[vdc_disk_index]['href']}))
        params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
        self.api_post_params('vcloud.diskAttachOrDetachParams', self.href + '/disk/action/attach', params, requests.codes.accepted, inspect.stack()[0][3], self.name)

    def detach_independent_disk(self,vm_disk_index):
        vm_disks = self.get_record('vmDiskRelation' , 'VmDiskRelationRecord', 'vm==' + self.href, show=False)
        if vm_disk_index not in range(len(vm_disks)):
            logger.info("%s does not exist in %s" % (vm_disk_index,self.name))
            return
        params = BeautifulSoup('<?xml version="1.0" encoding=""?>','xml')
        params.append(Tag(builder=builder.TreeBuilder(),name='DiskAttachOrDetachParams',attrs={'xmlns':'http://www.vmware.com/vcloud/v1.5'}))
        params.DiskAttachOrDetachParams.append(Tag(builder=builder.TreeBuilder(),name='Disk',attrs={'href':vm_disks[vm_disk_index]['disk']}))
        params = etree.tostring(etree.fromstring(str(params)),pretty_print=True)
        self.api_post_params('vcloud.diskAttachOrDetachParams', self.href + '/disk/action/detach', params, requests.codes.accepted, inspect.stack()[0][3], self.name)

    def get_storage_compliance(self):
        self.api_post(self.href + '/action/checkCompliance', requests.codes.accepted, inspect.stack()[0][3])
        self.get_section('/complianceResult', show=True)

    def get_wmks(self):
        r = self.api_post(self.href + '/screen/action/acquireMksTicket', requests.codes.ok, inspect.stack()[0][3])
        if r == None:
            logger.info("%s has to be powered on" % (self.name))
            return
        mks_ticket = BeautifulSoup(r.content,'xml').MksTicket
        return {'url':'wss://' + mks_ticket.Host.string + '/' + mks_ticket.Port.string + ';' + mks_ticket.Ticket.string,
            'vmx':mks_ticket.Vmx.string}

