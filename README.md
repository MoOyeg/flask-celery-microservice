# flask-celery-microservice

Contains code samples for [Scaling Celery workers with RabbitMQ on Kubernetes](https://learnk8s.io/scaling-celery-rabbitmq-kubernetes)


oc apply -k ./flask-server-deploy

oc apply -k ./rabbitmq

oc apply -k ./postgresql

oc apply -k ./celery-workers

oc apply -k ./locust

oc apply -k ./keda-operator


oc apply -k ./keda


oc create sa/thanos -n celerty-workers
SA_TOKEN=$(oc describe sa/thanos -n celery-workers | grep -i Tokens | awk '{print $2}')


Clean up
oc delete -k ./keda-operator

oc delete -k ./locust

oc delete -k ./locust

oc delete -k ./celery-workers

oc delete -k ./postgresql

oc delete -k ./rabbitmq

oc delete -k ./flask-server-deploy








