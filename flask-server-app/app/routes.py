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

    try:
        minreplica = request.args.get('minreplicacount')
        maxreplica = request.args.get('maxreplicacount')
        scaledobject = request.args.get('scaledobject')
        if scaledobject is None:
            scaledobject = "pod-scaledobject"
    except Exception as e:
        return jsonify({"status":"Could not obtain arguments from request"})

    if scaledobject.lower != "pod-scaledobject" or scaledobject.lower != "vm-scaledobject":
        return jsonify({"status":"Scaled object must be either %s or %s".format("pod-scaledobject","vm-scaledobject")})
    
    
        
        try:
            minreplica = int(minreplica)
            maxreplica = int(maxreplica)
            cmd = '''oc patch scalpatch scaledobject cpu-scaledobject --type=merge -p '{"spec":{"%s":2}}'''.format(minreplica)
            
            
            
            process = subprocess.Popen(['echo', 'More output'],
                     stdout=subprocess.PIPE, 
                     stderr=subprocess.PIPE)
            

