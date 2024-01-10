# pylint: disable=invalid-name
'''
Version 1: Prototype
'''

from asyncio import get_event_loop, create_task, Lock as AsyncLock, sleep as AsyncSleep

from collections import OrderedDict
import json
from logging import getLogger, config
from os import getenv
import ssl
from requests.exceptions import HTTPError, ConnectionError,Timeout
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Body, Response, BackgroundTasks,status  # pylint: disable=import-error
from starlette.background import BackgroundTasks as StarletteBackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from os import path as ospath, pardir, mkdir
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from .config import settings
import string
import random
import requests
import aiohttp
import subprocess

# App Init and Global Variables
# ------------------------------------------------------------------------------------------------
# Logging
log_file_path = ospath.join(ospath.dirname(ospath.abspath(__file__)), 'logging.conf')
config.fileConfig(log_file_path, disable_existing_loggers=False)
logger = getLogger("logger_root")

# Global Variables
oc_error_count = settings.oc_error_count
looped_methods = []

class VirtualMachine():
    
    def __init__(self,name) -> None:
        self.name = name
        self.memory_metric = 0
        self.cpu_metric = 0
        self.running = False
        self.ready = False
        self.workernode = ""
        self.instance_ip = ""
        self.creation_timestamp = ""
        self.lastpollupdate = datetime.now()
        #TODO: Add Locking for each individual VM to allow individual non-blocking updates, for now will use VMPool Lock
        #self.updateLock = AsyncLock()
        
    def __str__(self) -> str:
        return "VirtualMachine: {} Memory: {} CPU: {} Running: {} Ready: {} Node: {} IP: {} CreationTimestamp: {} LastPollUpdate: {}".format(
            self.name,
            self.memory_metric,
            self.cpu_metric,
            self.running,
            self.ready,
            self.workernode,
            self.instance_ip,
            self.creation_timestamp,
            self.lastpollupdate)
        
    def __repr__(self) -> str:
        return "VirtualMachine: {} Memory: {} CPU: {} Running: {} Ready: {} Node: {} IP: {} CreationTimestamp: {} LastPollUpdate: {}".format(
            self.name,
            self.memory_metric,
            self.cpu_metric,
            self.running,
            self.ready,
            self.workernode,
            self.instance_ip,
            self.creation_timestamp,
            self.lastpollupdate)
    
    def __eq__(self, other):
        if isinstance(other, VirtualMachine):
            if self.creation_timestamp is not None and other.creation_timestamp is not None:
                return str(self) == str(other)
            return self.name == other.name
        return False
        
    def __json__(self) -> str:
        return json.dumps(self.__dict__,indent=4, sort_keys=True, default=str)

#Stack where we will store our VMs
class VMPool:
    _initalized = False
    _lock = AsyncLock()
    _vmstack = []
    _virtualmachine_max = settings.virtualmachine_max
    _virtualmachine_min = settings.virtualmachine_min
    _virtualmachine_expected_current = 0
    json_report = {}

    #TODO: Add Wrapper Method to Lock and Unlock the Class Lock with timeouts to help forestall locking issues
    # Wrapper Method should auto-release the lock after a timeout period

    @classmethod
    async def _push(cls,item: VirtualMachine) -> None:
        '''Push a VirtualMachine onto the stack'''
        if not cls._lock.locked():
            raise Exception("Class Lock not locked, Function should only be called from within the lock")       
   
        if item in cls._vmstack:
            logger.error("Error adding VM to Stack, VM already exists")
            return None
        else:
            cls._vmstack.append(item) 

    @classmethod
    async def _pop(cls,item: VirtualMachine) -> None:
        '''Push a VirtualMachine onto the stack'''
        if not cls._lock.locked():
            raise Exception("Class Lock not locked, Function should only be called from within the lock")

        try:
            cls._vmstack.remove(item)
        except Exception as e:
            logger.error("Error popping VM from Stack {}".format(e))
            pass  
    
    @classmethod
    async def _update_json_report(cls) -> None:
        '''Update the JSON Report'''
        if not cls._lock.locked():
            raise Exception("Class Lock not locked, Function should only be called from within the lock")
        
        cls.json_report = {}
        cls.json_report.update({"virtualmachine_max":cls._virtualmachine_max})
        cls.json_report.update({"virtualmachine_min":cls._virtualmachine_min})
        cls.json_report.update({"virtualmachine_expected_current":cls._virtualmachine_expected_current})
        cls.json_report.update({"virtualmachine_count":await cls._size()})
        cls.json_report.update({"virtualmachine_list":[]})
        try:
            for vm in cls._vmstack:
                cls.json_report["virtualmachine_list"].append(json.loads(vm.__json__()))
        except Exception as e:
            logger.error("Error updating JSON Report {}".format(e))
    
    @classmethod
    async def _peek(cls) -> VirtualMachine:
        '''Return the top item in the stack'''
        if not cls._lock.locked():
            raise Exception("Class Lock not locked, Function should only be called from within the lock")
        if len(cls._vmstack) > 0:
            return cls._vmstack[-1]
        return None
    
    @classmethod
    async def _is_empty(cls) -> bool:
        '''Check if the Stack is Empty'''
        if not cls._lock.locked():
            raise Exception("Class Lock not locked, Function should only be called from within the lock")
        return len(cls._vmstack) == 0

    @classmethod
    async def _vm_exists_return(cls,item: str) -> VirtualMachine:
        '''Check if VM is already in stack by Name'''
        if not cls._lock.locked():
            raise Exception("Class Lock not locked, Function should only be called from within the lock")
        for vm in cls._vmstack:
            if vm.name == item:
                return vm
        return None
    
    @classmethod
    async def _size(cls) -> int:
        """Return the size of the stack"""
        if not cls._lock.locked():
            raise Exception("Class Lock not locked, Function should only be called from within the lock")     
        return len(cls._vmstack)
       

  
    @classmethod
    async def _create_vms(cls,count:int) -> list:
        '''Create a new VM'''
        if not cls._lock.locked():
            raise Exception("Class Lock not locked, Function should only be called from within the lock")    
        
        logger.debug("Creating {} VMs".format(count))
        status_return_bool=[]
        
        for i in range(count):
            global oc_error_count
            retry_count = 0
            result = None
            
            environment = Environment(loader=FileSystemLoader(ospath.join(ospath.dirname(__file__),"templates")))
            template = environment.get_template("virtualmachinetemplate.yaml")
            machine_name = settings.virtualmachine_prefix + str(''.join(random.choices(string.ascii_lowercase + string.digits, k=6)))
            content = template.render(Name=machine_name
                                      ,ContainerDiskImage=settings.containerdiskimage
                                      ,Labels=settings.vmlist_label
                                      ,Namespace=settings.vm_namespace)

            while retry_count < oc_error_count and result is None:
                try:
                    result = subprocess.run(['oc','apply','-f', '-'],input=content,capture_output=True, text=True)
                except Exception as e:                
                    logger.error("Error could not run oc command {},Retry Count: {}".format(e,retry_count))
                retry_count += 1

            if result.returncode == 0:
                if "{} created".format(machine_name) in str(result.stderr):
                    logger.info("VirtualMachine {} Created Successfully on Cluster".format(machine_name))
                    created_vm = VirtualMachine(machine_name)
                    await cls._push(created_vm)
                    status_return_bool.append(True)
            else:
                logger.error("Error Creating VirtualMachine: {}".format(result.stderr))
                status_return_bool.append(False)
        return status_return_bool

    @classmethod
    async def _delete_vms(cls,count:int=None,vm:VirtualMachine=None) -> list:
        '''Remove a VM or VM's from the stack'''
        '''Send either a count for the number of VMs to delete or a VM object to delete'''

        if not cls._lock.locked():
            raise Exception("Class Lock not locked, Function should only be called from within the lock")
        status_return_bool=[]
        
        if count is not None:
            logger.debug("Deleting {} VMs".format(count))
            existing_machine_name = None

        if vm is not None and count is None:
            count = 1
            logger.debug("Deleting VM {}".format(vm.name))
            existing_machine = vm
            existing_machine_name = vm.name
        
        for i in range(count):
            global oc_error_count
            retry_count = 0
            result = None
                
            #If we are not given a VM to delete, lets pop one off the stack
            if existing_machine_name is None:
                existing_machine = await cls._peek() 
                existing_machine_name = existing_machine.name
                     
            while retry_count < oc_error_count and result is None:
                try:
                    result = subprocess.run(['oc','delete','virtualmachine',
                                             existing_machine_name,
                                             '-n',settings.vm_namespace,],capture_output=True, text=True)
                except Exception as e:                
                    logger.error("Error could not run oc command {},Retry Count: {}".format(e,retry_count))
                    retry_count += 1

            if result.returncode == 0:
                if "deleted" in str(result.stdout):
                    logger.info("VirtualMachine {} Deleted Successfully".format(existing_machine_name))
                    await cls._pop(existing_machine)
                    status_return_bool.append(True)                        
            if "NotFound" in str(result.stderr):
                logger.error("VirtualMachine does not seem to exist: {}".format(result.stderr))
                try:
                    await cls._pop(existing_machine)
                except:
                    logger.error("Error deleting VM {} from Stack".format(existing_machine_name))
                status_return_bool.append(False)
        
        return status_return_bool
        
    @classmethod
    async def _poll_existing_vm(cls) -> list:
        '''Poll the Cluster for Existing VMs'''
        '''Returns a list of VMs in the format of [name,running,ready,creationTimestamp]'''
        
        #Method should not to be called within a lock

        global oc_error_count  # pylint: disable=global-statement
        retry_count = 0
        result = None
        errored_out = False
        
        while retry_count < oc_error_count and result is None:
            try:
                result = subprocess.run(['oc','get','virtualmachines',
                                    '-l',settings.vmlist_label+'=true',
                                    '-n',settings.vm_namespace,
                                    '-o','jsonpath={range .items[*]}{@.metadata.name}{" "}{@.spec.running}{" "}{@.status.ready}{" "}{@.metadata.creationTimestamp}{" "}{end}',
                                    ],capture_output=True, text=True)
            except Exception as e:                
                logger.error("Error could not run oc command {},Retry Count: {}".format(e,retry_count))

            if result is None:
                logger.error("Error could not run oc command, unknown error,Retry Count: {}".format(retry_count))
                logger.error("Error From Cluster")

            if "error" in str(result.stderr):
                logger.error("Error could not run oc command, unknown error,Retry Count: {}".format(retry_count))
                logger.error("Error From Cluster: {}".format(result.stderr))
                result=None
                logger.info("Sleeping for {} seconds before retrying".format(settings.oc_error_sleep_timer)) 
                await AsyncSleep(settings.oc_error_sleep_timer)
            retry_count += 1
            if retry_count == oc_error_count:
                errored_out = True
                logger.error("Error polling existing VMs, exceeded max retry count")
                logger.error("Error: {}".format(result.stderr))
                return []

        if result.returncode == 0:
            if "No resources found" in str(result.stderr):
                logger.info("No Existing VMs Found")
                return []
            else:
                vm_list = result.stdout.strip().split(" ")
                logger.info("Found {} Existing VMs".format(int(len(vm_list)/4)))
                return vm_list
                  
    @classmethod
    async def update_vmpool(cls) -> None:
        '''Continuous Polling and Correlation of Our managed VMs'''
        while True:
            #Get the List/Count of Existing VMs on OpenShift
            try:
                existing_vm_list = await cls._poll_existing_vm()
            except Exception as e:
                logger.error("Error polling existing VMs {}".format(e))
                existing_vm_list = []           
            
            #Accounting for the fact that we are returning a list of 4 items per VM  
            existing_vm_list_size = len(existing_vm_list)
            if len(existing_vm_list) > 0:
                existing_vm_list_size = int(len(existing_vm_list)/4)
            
            async with cls._lock:
                logger.debug("update_vmpool lock acquired")
                #sync up our stack with the existing VMs
                vmpool_size = await cls._size()
                for i in range(int(existing_vm_list_size)):
                    vm_name = existing_vm_list[i*4]
                    vm_running = existing_vm_list[i*4+1]
                    vm_ready = existing_vm_list[i*4+2]
                    vm_creation_timestamp = existing_vm_list[i*4+3]
                    vm = await cls._vm_exists_return(vm_name)
                    if vm is not None:
                        vm.lastpollupdate = datetime.now()
                        vm.running = vm_running
                        vm.ready = vm_ready
                        vm.creation_timestamp = vm_creation_timestamp
                        logger.info("VM {} updated in VMPool Stack".format(vm_name))
                    else:
                        new_vm = VirtualMachine(vm_name)
                        new_vm.running = vm_running
                        new_vm.ready = vm_ready
                        new_vm.creation_timestamp = vm_creation_timestamp
                        try:
                            await cls._push(new_vm)
                        except Exception as e:
                            logger.error("Error adding VM {} to VMPool Stack {}".format(vm_name,e))
                        logger.info("Added VM {} to VMPool Stack".format(vm_name))
                
                #Check if we have unexpected VMs in our stack
                vmstack_copy = cls._vmstack.copy()
                for vm in vmstack_copy:
                    if vm.name not in existing_vm_list:
                        logger.info("VM {} not found in Cluster, removing from Stack".format(vm.name))
                        try:
                            await cls._delete_vms(None,vm)
                        except:
                            logger.error("Error deleting VM {}".format(vm.name))
                await cls._update_json_report()
            logger.debug("update_vmpool lock released")
                
            async with cls._lock:
                logger.debug("update_vmpool lock acquired")                      
                #Finally make sure we have the expected number of existing VMs
                vmpool_size = await cls._size()
                expected_current_vms = max(cls._virtualmachine_min,cls._virtualmachine_expected_current)
                if expected_current_vms > cls._virtualmachine_max:
                    expected_current_vms = cls._virtualmachine_max
                
                #Create VM's if we are too low
                if vmpool_size < expected_current_vms:                  
                    try:
                        await cls._create_vms(expected_current_vms - vmpool_size)
                    except Exception as e:
                        logger.error("Error creating VMs {}".format(e))
                        
                #Delete VM's if we are too high
                if vmpool_size > expected_current_vms:
                    try:
                        await cls._delete_vms(vmpool_size - expected_current_vms)
                    except Exception as e:
                        logger.error("Error deleting VMs {}".format(e))  

            logger.debug("update_vmpool lock released")
            await AsyncSleep(settings.vm_poll_timer)

    @classmethod
    async def get_vm_livemetrics(cls) -> None:
        '''Get the Live Metrics for each VM'''
        api_token = None
        #Get Token to use for API Calls
        logger.debug("Getting ServiceAccount Token")
        if settings.serviceaccount_token == "":
            try:
                with open(settings.serviceaccount_token_location, 'r') as file:
                    api_token = file.read().replace('\n', '')
            except Exception as e:
                logger.error("Cannot Read ServiceAccount Token: {}".format(e))
        else:
            api_token = settings.serviceaccount_token
            
        if api_token is None:
            logger.error("Cannot Get ServiceAccount Token for API Calls")
            return None
        
        while True:            
            async with aiohttp.ClientSession() as session:
                kwargs={}
                metrics=["kubevirt_vmi_memory_used_bytes","kubevirt_vmi_cpu_usage_seconds_total"]
                apiresponse={}
                for metric in metrics:
                    apiresponse.update({metric:None})
                    if not settings.thanos_ssl_verify:
                        logger.info("SSL Verification Disabled for Thanos API Calls")
                        kwargs['ssl'] = False
                    kwargs["timeout"]= aiohttp.ClientTimeout(total=60)
                    kwargs["params"] = {'query': metric, 'namespace': settings.vm_namespace}
                    kwargs["headers"] = {'Accept': 'application/json'
                                        ,'Authorization': "Bearer {}".format(api_token)}
                    try:
                        async with session.get(settings.thanos_url,**kwargs) as response:
                            apiresponse[metric] = await response.json()
                    except aiohttp.ClientConnectorError as e:
                        logger.error("Error connecting to Thanos {}".format(e))
                        if "CERTIFICATE_VERIFY_FAILED" in e:
                            logger.info("SSL Certificate Verification Failed, retrying with SSL Verification Disabled")
                            logger.info("To disable SSL Verification, set THANOS_SSL_VERIFY=False via envirtonment variable")
                            return None
                    except Exception as e:
                        logger.error("Error connecting to Thanos {}".format(e))
                        return None

                    if response is not None:
                        if response.status != 200:
                            try:
                                logger.error("Error connecting to Thanos, Error Code: {}".format(response.status))
                                logger.error("Error connecting to Thanos, Reason: {}".format(response.reason))
                            except:
                                logger.error("Error connecting to Thanos, Unknown Error")        
                            return None                   

                #TODO: Refactor to improve multiple loops
                async with cls._lock:
                    logger.debug("update_vmpool lock acquired")
                    vmlist=[vm.name for vm in cls._vmstack]
                    for metric in metrics:                         
                        for exposed_metric in apiresponse[metric]['data']['result']:
                            if exposed_metric['metric']['name'] in vmlist:
                                vm = await cls._vm_exists_return(exposed_metric['metric']['name'])
                                vm.workernode = exposed_metric['metric']['node']
                                vm.instance_ip = exposed_metric['metric']['instance']
                                if metric == "kubevirt_vmi_memory_used_bytes":
                                    vm.memory_metric = exposed_metric['value'][1]
                                    logger.debug("VM {} updated with Live Memory Metrics".format(vm.name))
                                if metric == "kubevirt_vmi_cpu_usage_seconds_total":
                                    vm.cpu_metric = exposed_metric['value'][1]
                                    logger.debug("VM {} updated with Live CPU Metrics".format(vm.name))
                                vm.lastpollupdate = datetime.now()
                    await cls._update_json_report()            
                logger.debug("update_vmpool lock released")
                              
            await AsyncSleep(settings.vm_poll_timer)

    @classmethod
    async def set_max_or_min_or_current(cls, max:int=None, min:int=None,current:int=None) -> str:
        '''Set the Max or Min VM Count'''
        async with cls._lock:           
            if max is not None and min is not None:
                if min > max:
                    return "error: minreplicacount cannot be greater than maxreplicacount"
                else:                
                    cls._virtualmachine_max = max
                    cls._virtualmachine_min = min
                    return "Max and Min VM Count Set"

            if max is not None:
                if max < cls._virtualmachine_min:
                    return "error: maxrequest:{} cannot be lower than present minreplicacount:{}".format(max,cls._virtualmachine_min)
                cls._virtualmachine_max = max
                return "Max VM Count Set to {}".format(max)
            
            if min is not None:
                if min > cls._virtualmachine_max:
                    return "error: minrequest:{} cannot be greater than present max vm's:{}".format(min,cls._virtualmachine_max)
                cls._virtualmachine_min = min
                if min > cls._virtualmachine_expected_current:
                    cls._virtualmachine_expected_current = min
                return "Min VM Count Set to {}".format(min)
            
            if current is not None:
                if current > cls._virtualmachine_max:
                    return "error: currentreplicacount cannot be greater than maxreplicacount"
                elif current < cls._virtualmachine_min:
                    return "error: currentreplicacount cannot be lower than minreplicacount"
                else:
                    cls._virtualmachine_expected_current = current
                    return "Current VM Count Set {}".format(current)
            await cls._update_json_report()   
        logger.debug("set_max_or_min_or_current lock released")

    @classmethod
    async def get_max_or_min_or_current(cls, max:bool=None, min:bool=None,current:bool=None) -> int:
        '''Get the Max or Min VM Count'''
        async with cls._lock:
            if max is not None:
                return cls._virtualmachine_max
            if min is not None:
                return cls._virtualmachine_min
            if current is not None:
                return cls._virtualmachine_expected_current
        logger.debug("get_max_or_min_or_current lock released")

    @classmethod
    async def autoscale_current(cls) -> None:
        '''Autoscale the Current VM Count'''
        scaling_logic = settings.auto_logic
        
        while True:
            logger.info("Running the Autoscaling process")
            if scaling_logic is not None:
                vmstack_copy = None
                async with cls._lock:
                    logger.debug("autoscale_current lock acquired")
                    vmstack_copy = cls._vmstack.copy()
                logger.debug("autoscale_current lock released")
                
                #TODO: Really need to Refactor logic here to improve multiple loops
                conditions_met = True
                for condition in scaling_logic:
                    metric = condition[0]
                    operator = condition[1]
                    value = condition[2]
                    vm_count = condition[3]
                    this_condition_met = False
                    
                    if metric == "memory_metric":
                        count_met = 0
                        for vm in vmstack_copy:
                            try:
                                vm.memory_metric = int(vm.memory_metric)
                                value = int(value)
                            except:
                                continue                                              
                            if operator == ">":                        
                                if vm.memory_metric > value:
                                    count_met += 1
                            if operator == "<":
                                if vm.memory_metric < value:
                                    count_met += 1
                            if operator == ">=":
                                if vm.memory_metric >= value:
                                    count_met += 1
                            if operator == "<=":
                                if vm.memory_metric <= value:
                                    count_met += 1
                    if metric == "cpu_metric":
                        for vm in vmstack_copy:
                            try:
                                vm.cpu_metric = int(vm.cpu_metric)
                                value = int(value)
                            except:
                                continue   
                            if operator == ">":
                                if vm.cpu_metric > value:
                                    count_met += 1
                            if operator == "<":
                                if vm.cpu_metric < value:
                                    count_met += 1
                            if operator == ">=":
                                if vm.cpu_metric >= value:
                                    count_met += 1
                            if operator == "<=":
                                if vm.cpu_metric <= value:
                                    count_met += 1

                    if count_met >= vm_count:
                        this_condition_met = True
                    
                    conditions_met = conditions_met and this_condition_met

                if conditions_met:
                    logger.info("Autoscaling Conditions, will review if we need to scale up")
                    current = await cls.get_max_or_min_or_current(current=True)
                    await cls.set_max_or_min_or_current(current=current+1)
                    if "error" not in returnval:
                        logger.info("Autoscaling Current VM Count to {}".format(current+1))
                else:
                    logger.info("Autoscaling Conditions, will review if we need to scale down")
                    current = await cls.get_max_or_min_or_current(current=True)
                    returnval = await cls.set_max_or_min_or_current(current=current-1)
                    if "error" not in returnval:
                        logger.info("Autoscaling Current VM Count to {}".format(current-1))
            await AsyncSleep(settings.vm_poll_timer)

# App Startup
# ------------------------------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    '''Startup Function'''
    logger.info("Starting up Custom OpenShift Virtualization AutoScaling Service")
    global instance_hostname  # pylint: disable=global-statement
    instance_hostname = getenv('HOSTNAME')
    logger.info("Instance Hostname: {}".format(instance_hostname))
    
    #At Startup, Set our expected VM count to our minimum
    response= await VMPool.set_max_or_min_or_current(None,None,current=settings.virtualmachine_min)
    if "error" in response:
        logger.error(response)     
    

    #Method to update the VMPool continously and create/delete VMs as needed
    logger.info("Starting Continous VMPool Update loop, will check VM status every {} seconds".format(settings.vm_poll_timer))
    looped_methods.append(create_task(VMPool.update_vmpool()))
    logger.info("Started Continous VMPool Update loop")

    #Method to get the Live Metrics for each VM continously
    logger.info("Starting Continous Live Metrics Receive loop, will get VM metrics every {} seconds".format(settings.vm_poll_timer))
    looped_methods.append(create_task(VMPool.get_vm_livemetrics()))
    logger.info("Started Continous Live Metrics Receive loop")
         
    #Method to Autoscale the Current VM Count
    logger.info("Starting Continous Autoscaling loop, will check VM metrics every {} seconds".format(settings.vm_poll_timer))
    looped_methods.append(create_task(VMPool.autoscale_current()))
    logger.info("Started Continous Autoscaling loop")        
         
    #Startup Complete
    startup_status = True
    logger.info("Startup Complete")
       
    #yield to allow the rest of the application to run
    yield
    
    #Shutdown Procedure
    logger.info("Shutdown Custom OpenShift Virtualization AutoScaling Service")
    
# Declare App as a FastApi Object
app = FastAPI(lifespan=lifespan)

# Instance Hostname is global
instance_hostname = ""

# App Routes
# ------------------------------------------------------------------------------------------------
@app.get("/")
async def root():
    '''Application'''
    logger.info("Root Url '/' was Called")
    return {"Application": "AutoScaling Service for OpenShift Virtualization"
            ,"Hostname": instance_hostname
            ,"Help": "Please see the README.md for more information"
            ,"Useful Urls": "/replica - Set the Min and Max VM Count with query parameters 'minreplicacount' and 'maxreplicacount'"
            ,"Present Status": VMPool.json_report}

@app.post('/replica')
async def scale(request: Request):
    '''Command helps to set the min and max'''
    if "maxreplicacount" in request.query_params and "minreplicacount" in request.query_params:
        try:
            max=int(request.query_params["maxreplicacount"])
            min=int(request.query_params["minreplicacount"])
            response= await VMPool.set_max_or_min_or_current(max,min,None)
            if "error" in response:
                logger.error(response)
                return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": response})
            else:
                return JSONResponse(status_code=status.HTTP_200_OK, content={"status": response})
        except:
            logger.error("Error getting maxreplicacount and minreplicacount via request")
        
    if "maxreplicacount" in request.query_params:
        try:
            max=int(request.query_params["maxreplicacount"])
            response= await VMPool.set_max_or_min_or_current(max,None,None)
            if "error" in response:
                logger.error(response)
                return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": response})
            else:
                return JSONResponse(status_code=status.HTTP_200_OK, content={"status": response})
        except:
            logger.error("Error getting maxreplicacount via request")

    if "minreplicacount" in request.query_params:
        try:
            min=int(request.query_params["minreplicacount"])
            response= await VMPool.set_max_or_min_or_current(None,min,None)
            if "error" in response:
                logger.error(response)
                return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": response})
            else:
                return JSONResponse(status_code=status.HTTP_200_OK, content={"status": response})
        except:
            logger.error("Error getting minreplicacount via request")

@app.get("/health")
async def health():
    '''Application Health URL'''
    logger.debug("Health Url '/health' was Called")
    return {"status": "OK"}

@app.get("/ready")
async def ready():
    '''Application Readiness URL'''
    global startup_status  # pylint: disable=global-statement
    
    logger.debug("Health Url '/ready' was Called")
    if startup_status:
        logger.debug("Application is Ready")
        return {"status": "OK"}
    else:
        logger.debug("Application is Not Ready")
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={"status": "Not Ready"})
