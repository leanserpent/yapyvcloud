from nose.tools import *
from yapyvcloud.yapyvcloud import *

def test_session():
    #session = Session('vcdsys')
    session = Session('vcdorg')

    org=Org()
    for vdc_record in org.get_orgvdc():
        vdc = OrgVdc(vdc_record['name'])
        for i in range(0,len(vdc.get_independent_disk())):
            vdc.del_independent_disk(i)

    session.disconnect()

