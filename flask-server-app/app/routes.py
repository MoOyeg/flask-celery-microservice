from app.app import app
from flask import request, render_template, jsonify
from celery.result import AsyncResult
from app.tasks import *
import os
import subprocess

@app.route('/')
def default():
    return "Welcome to Report Service"

@app.route('/health')
def health():
    return jsonify({"state":"healthy"})

@app.route('/report', methods=['POST'])
def generate_report():
    async_result = report.delay()
    return jsonify({"report_id":async_result.id})


@app.route('/report/<report_id>')
def get_report(report_id):
    res = AsyncResult(report_id,app=celery)
    return jsonify({"id":res.id,"result":res.result})


@app.route('/replica', methods=['POST'])
def scale():
    '''Command helps to scale  the KEDA Scaled Object using oc binary'''
    '''Simulates the idea that the application can choose when to manually scale it's own resources based on some logic'''

    try:
        minreplicacount = request.args.get('minreplicacount')
        maxreplicacount = request.args.get('maxreplicacount')
        scaledobject = request.args.get('scaledobject')
        if scaledobject is None:
            scaledobject = "pod-scaledobject"
    except Exception as e:
        return jsonify({"status":"Error","msg":"Could not obtain arguments from request"})

    if scaledobject.lower() != "pod-scaledobject" and scaledobject.lower() != "vm-scaledobject":
        return jsonify({"status":"Error","msg": "Scaled object argument(scaledobject) must be either pod-scaledobject or vm-scaledobject"})
        
    try:
        if minreplicacount is None and maxreplicacount is None:
            return jsonify({"status":"Either minreplicacount or maxreplicacount must be provided"})
        elif minreplicacount is not None and maxreplicacount is not None:
            minreplicacount = int(minreplicacount)
            maxreplicacount = int(maxreplicacount)
            patch="{\"spec\": {\"minReplicaCount\": " + str(minreplicacount) + ",\"maxReplicaCount\": " + str(maxreplicacount) + "} }"
        elif minreplicacount is not None:
            minreplicacount = int(minreplicacount)
            patch="{\"spec\": {\"minReplicaCount\": " + str(minreplicacount) + "} }"
        elif maxreplicacount is not None:
            maxreplicacount = int(maxreplicacount)
            patch="{\"spec\": {\"maxReplicaCount\": " + str(maxreplicacount) + "} }"              
    except:
        return jsonify({"status":"Could not scale the object"})
              
    
    try:
        result = subprocess.run(['oc', 'patch','scaledobject',scaledobject,
                             '--type','merge','-p',
                            patch],capture_output=True, text=True)
    except:
        return jsonify({"status":"Error","msg":"Could not scale the object"})
    
    if result.stderr != '' or result.returncode != 0:
        return jsonify({"status":"Error","msg":"Could not scale the object","stdout":result.stdout,"stderr":result.stderr})
    else:
        return jsonify({"status":"Success","msg":"Scale Command was Successful","stdout":result.stdout})


            

