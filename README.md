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

oc create sa/thanos -n celerty-workers
SA_TOKEN=$(oc describe sa/thanos -n celery-workers | grep -i Tokens | awk '{print $2}')


oc apply -k ./keda


oc create serviceaccount thanos -n celery-workers
export SA_TOKEN=$(oc describe sa/thanos -n celery-workers | grep -i Tokens | awk '{print $2}')
oc kustomize ./keda | envsubst


Clean up
oc delete -k ./keda

oc delete -k ./keda-operator

oc delete -k ./locust

oc delete -k ./celery-workers

oc delete -k ./postgresql

oc delete -k ./rabbitmq

oc delete -k ./flask-server-deploy








