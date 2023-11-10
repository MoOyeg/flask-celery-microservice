#/bin/bash
dnf module -y install python38
dnf install -y python3-pip
pip install -r ./flask-celery-microservice/flask-server-app/requirements.txt