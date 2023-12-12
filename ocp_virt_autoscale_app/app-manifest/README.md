# Custom AutoScaling Service

This app provides a cheap representation of a VMPool and Autoscaler.

App configuration can be found in [config file](./app/config.py).


Get Application Status
```bash
APP_ROUTE=$(oc get route custom-autoscale-app -n celery-workers -o jsonpath='{.spec.host}')
curl https://$APP_ROUTE
```

Set Minimum VM's, will take sometime before actualization(Default-30s)
```bash
curl -k -X POST "https://$APP_ROUTE/replica?minreplicacount=3"
```

```bash
curl -k -X POST "https://$APP_ROUTE/replica?maxreplicacount=8"
```

Test autoscale in App
- Install stress-ng in one of the VM's(sudo yum -y install stress-ng)
- Run a memory test inside VM(stress-ng --vm 1 --vm-bytes 75% -t 85)
- The app should continue to add VM's up to it's current max
- Delete the VM with the stress test, after a while app should go back to min.

More Documentation to be added