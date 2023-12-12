from pydantic_settings import BaseSettings
import os
from dotenv import load_dotenv  # pylint: disable=import-error


basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Settings(BaseSettings):
    """Application Settings """
    #VM Template
    #File is under templates/vm-template.yaml
    
    #Label we will apply to every VM so we can identify them
    vmlist_label:str = os.environ.get('LABEL_VMLIST') or 'custom_vmlist_test'
    
    #VM Namespace
    vm_namespace:str = os.environ.get('VM_NAMESPACE') or 'celery-workers'  
    
    
    oc_error_count:int = int(os.environ.get('OC_ERROR_COUNT') or 3) 
    oc_error_sleep_timer:int = int(os.environ.get('OC_ERROR_RETRY_TIMER') or 5)
    
    vm_poll_timer:int = int(os.environ.get('VM_POLL_TIMER') or 30)
    virtualmachine_max:int = int(os.environ.get('VIRTUALMACHINE_MAX') or 5)
    virtualmachine_min:int = int(os.environ.get('VIRTUALMACHINE_MIN') or 2)
    virtualmachine_prefix:str = os.environ.get('VIRTUALMACHINE_PREFIX') or 'celery-worker-vm-'
    containerdiskimage:str = os.environ.get('CONTAINER_DISK_IMAGE') or 'quay.io/mooyeg/containerdisk-celery:v1.0'
    #thanos_url:str = os.environ.get('THANOS_URL') or 'https://thanos-querier.thanos.svc.cluster.local:9092/api/v1/query'
    thanos_url:str = os.environ.get('THANOS_URL') or 'https://localhost:9092/api/v1/query'
    thanos_ssl_verify:bool = bool(os.environ.get('THANOS_SSL_VERIFY') or False)
    
    #Location of ServiceAccountFile with access to Thanos
    serviceaccount_token_location:str = os.environ.get('SERVICEACCOUNT_TOKEN_LOCATION') or '/var/run/secrets/kubernetes.io/serviceaccount/token'
    
    #Location of ServiceAccountToken with access to Thanos, will be used even if SERVICEACCOUNT_TOKEN_LOCATION is set
    serviceaccount_token:str = os.environ.get('SERVICEACCOUNT_TOKEN') or ''

    #Autoscale Logic
    #Metric used by autoscaling logic (needs improvement)
    #auto_logic(list of conditions) will be used to determine if we need to scale up or down
    #conditions --> [metric,operator,value,vm_count,]
    #metric: memory_metric, cpu_metric
    #operator: >, <, >=, <=
    #value: int, for memory_metric it is in bytes
    #vm_count: int, number of VM's that need to be above/below value
    #Conditions are "AND" together, so all conditions need to be met for autoscaling to happen
    
    auto_logic:list = [["memory_metric",">","200000000",1],]


settings = Settings()