# flask-celery-vm-microservice

This repo acts as a proof of concept for showcasing:
- Autoscaling VirtualMachines and Pods with the [Custom Metrics Autoscaler - KEDA](https://docs.openshift.com/container-platform/4.13/nodes/cma/nodes-cma-autoscaling-custom.html) on OpenShift.
- Simulating manual scaling with the application being auto-scaled controlling the min and max replica count as desired.
- Working with mixed Pod and VM autoscaling.

 A lot of the code used here was from the the excellent work done here - [Scaling Celery workers with RabbitMQ on Kubernetes](https://learnk8s.io/scaling-celery-rabbitmq-kubernetes). I have updated it to:
 - Python version 3.9
 - Rewritten specifically for OpenShift Usage.
 - Added support for [VirtualMachines - OpenShift Virtualization](https://docs.openshift.com/container-platform/4.13/virt/about-virt.html)


## Architecture
![Architecture Diagram](./images/KEDA-VM.png)
TODO: Autoscaling via RabbitMQ queue length( Blue Color) not yet complete. Cluster metrics autoscaling on OCP does not yet support amqp but does support prometheus.

## Prerequsites
- Tested on OpenShift 4.13
- To build images Openshift registry must be available
- To use VM's - OpenShift Virtualization must be installed
- We need OCP Pipelines to build VM image
- To use the Tekton Virt customize task to build VM's we "seem" to need file based storage class.
- Enable user workload monitoring for scaling based on RabbitMQ queue length.

## Deployment Steps
- Build and Deploy our Flask Serve Application Image
Note: Pod image will fail until build is complete 

    ```bash
    oc apply -k ./flask-server-deploy
    ```
- Build and deploy our RabbitMQ image and Pod.  

    ```bash
    oc apply -k ./rabbitmq
    oc start-build buildconfig/rabbitmq -n rabbitmq
    ```

- Deploy DB for Application
    ```bash
    oc apply -k ./postgresql
    ```

- Deploy Celery Pod Workers
    ```bash
    oc apply -k ./celery-workers
    ```

- Deploy Locust load testing utility
    ```bash
    oc apply -k ./locust
    ```

- You can install the Custom Metrics Autoscaler via console or create here.
    ```bash
    oc apply -k ./keda-operator
    ```

### Creating Celery VM's.
You can build the VM image or use the pre-built image. 

- Deploy with the pre-built image  
  ```bash
  oc apply -k ./celery-vm-workers/deploy
  ```

- Build VM Image(Optional).
    To build the image we need a StorageClass that supports filesystems, export the name of the storageclass:

    ```bash
    export STORAGECLASS_NAME=ocs-storagecluster-cephfs
    ```

    Export the Registry of the output image e.g.

    ```bash
    export OUTPUT_IMAGE=quay.io/mooyeg/containerdisk-celery:latest
    ```

    [Create a secret with credentials for your registry](https://docs.openshift.com/container-platform/4.10/openshift_images/managing_images/using-image-pull-secrets.html#images-allow-pods-to-reference-images-from-secure-registries_using-image-pull-secrets)

    Create the necessary manifests to build your image

    ```bash
    oc kustomize ./celery-vm-workers/build-image/ | envsubst | oc apply -f -   
    ```

    Link your registry pull-secret with your serviceaccount 

    ```bash
    oc secrets link pipelines-sa-userid-1000 quay-pull-secret -n celery-workers --for=pull,mount    
    ```

### Simulate Application Manual Scaling 
To simulate the application use-case where the application might want to be able to pre-scale or use it's own logic to control scaling. 

- Set the VM's max replicas to 6

```bash
curl -X POST -i 'http://$(oc get route flask-server -n flask-backend -o jsonpath='{.spec.host}')/replica?maxreplicacount=6&scaledobject=vm-scaledobject'
```

- Set the Pod's min replicas to 2
```bash
curl -X POST -i 'http://$(oc get route flask-server -n flask-backend -o jsonpath='{.spec.host}')/replica?minreplicacount=2&scaledobject=pod-scaledobject'
```

### Enable Autoscaling via RabbitMQ Queue Length(TODO)
oc create serviceaccount thanos -n celery-workers
export SA_TOKEN=$(oc describe sa/thanos -n celery-workers | grep -i Tokens | awk '{print $2}')
oc kustomize ./keda | envsubst | oc apply -f -


## Clean up

### Clean Up VM Build
    ```bash
    oc kustomize ./celery-vm-workers/build-image/ | envsubst | oc delete -f - 
    ```

### All Clean Up
oc delete -k ./keda
oc delete -k ./keda-operator
oc delete -k ./locust
oc delete -k ./celery-workers
oc delete -k ./postgresql
oc delete -k ./rabbitmq
oc delete -k ./flask-server-deploy








