yapyvcloud = yet another pyvcloud, an alternative python wrapper to VMware's python SDK for vCloud Director

tests/yapyvcloud_tests.py for usage example.

The wrapper assumes yapyvcloud_cred.yaml under user home (~/):
```
credentials:
- credential:
   alias: vcdorg
   host: vcloud.example.com
   org: org_name
   user: org_admin
   pass: org_admin_password
- credential:
    alias: vcdsys
    host: vcloud.example.com
    org: system
    user: sys_admin
    pass: sys_admin_password
```
