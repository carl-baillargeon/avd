# cvx-2

## Table of Contents

- [Management](#management)
  - [Management Interfaces](#management-interfaces)
- [CVX](#cvx)
  - [CVX Device Configuration](#cvx-device-configuration)

## Management

### Management Interfaces

#### Management Interfaces Summary

##### IPv4

| Management Interface | Description | Type | VRF | IP Address | Gateway |
| -------------------- | ----------- | ---- | --- | ---------- | ------- |
| Management1 | oob_management | oob | MGMT | 10.73.255.122/24 | 10.73.255.2 |

##### IPv6

| Management Interface | Description | Type | VRF | IPv6 Address | IPv6 Gateway |
| -------------------- | ----------- | ---- | --- | ------------ | ------------ |
| Management1 | oob_management | oob | MGMT | - | - |

#### Management Interfaces Device Configuration

```eos
!
interface Management1
   description oob_management
   vrf MGMT
   ip address 10.73.255.122/24
```

## CVX

CVX is disabled

### CVX Device Configuration

```eos
!
cvx
   shutdown
   service mcs
      shutdown
   service vxlan
      shutdown
```
