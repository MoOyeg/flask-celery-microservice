# flask-celery-microservice

Contains code samples for [Scaling Celery workers with RabbitMQ on Kubernetes](https://learnk8s.io/scaling-celery-rabbitmq-kubernetes)

Build and Deploy our Flask Serve Application Image
Note: Pod image will fail until build is complete 

    ```bash
    oc apply -k ./flask-server-deploy
    ```

#Enable User Workload Monitoring
```bash
oc apply -k ./rabbitmq
oc start-build buildconfig/rabbitmq -n rabbitmq
```

```bash
oc apply -k ./postgresql
```

```bash
oc apply -k ./celery-workers
```

```bash
oc apply -k ./locust
```

```bash
oc apply -k ./keda-operator
```

oc create serviceaccount thanos -n celery-workers
export SA_TOKEN=$(oc describe sa/thanos -n celery-workers | grep -i Tokens | awk '{print $2}')
oc kustomize ./keda | envsubst | oc apply -f -


## Creating Celery VM's
You can build the VM image or use the pre-built image:


### Build VM Image  
- To build the image we need a StorageClass that supports filesystems, export the name of the storageclass:

    ```bash
    export STORAGECLASS_NAME=ocs-storagecluster-cephfs
    ```

- Export the Registry of the output image e.g.

    ```bash
    export OUTPUT_IMAGE=quay.io/mooyeg/containerdisk-celery:latest
    ```

- [Create a secret with credentials for your registry](https://docs.openshift.com/container-platform/4.10/openshift_images/managing_images/using-image-pull-secrets.html#images-allow-pods-to-reference-images-from-secure-registries_using-image-pull-secrets)

- Create the necessary manifests to build your image

   ```bash
   oc kustomize ./celery-vm-workers/build-image/ | envsubst | oc apply -f -   
   ```

- Link your registry pull-secret with your serviceaccount 

    ```bash
    oc secrets link pipelines-sa-userid-1000 quay-pull-secret -n celery-workers --for=pull,mount    
    ```


## Clean up

### Clean Up VM Build
    ```bash
    oc kustomize ./celery-vm-workers/build-image/ | envsubst | oc delete -f - 
    ```


oc delete -k ./keda
oc delete -k ./keda-operator

oc delete -k ./locust

oc delete -k ./celery-workers

oc delete -k ./postgresql

oc delete -k ./rabbitmq

oc delete -k ./flask-server-deploy








