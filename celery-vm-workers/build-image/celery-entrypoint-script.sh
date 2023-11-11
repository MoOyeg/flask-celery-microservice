#!/bin/bash
# This script is run on first boot of the VM
mkdir /tmp/celery
#TODO add logic to determine correct drive rather than using /dev/vdc
#Till then VM must mount the correct drive to /dev/vdc
mount /dev/vdc /tmp/celery
export CELERY_BROKER_URL=$(cat /tmp/celery/CELERY_BROKER_URL)
export CELERY_RESULT_BACKEND=$(cat /tmp/celery/CELERY_RESULT_BACKEND)
export SECRET_KEY=$(cat /tmp/celery/SECRET_KEY) 
python -m celery worker -l info