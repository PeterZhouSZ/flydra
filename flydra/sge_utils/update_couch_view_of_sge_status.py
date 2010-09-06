import sys, os
from couchdb.client import Server
import couchdb.http
import subprocess
import states, util # flydra.sge_utils
import pytz, datetime
from xml.etree import ElementTree

COUCHDB_STATUS_DOC_ID = 'sge_status'

def update_couch_view_of_sge_status(couch_url, db_name):
    couch_server = Server(couch_url)
    db = couch_server[db_name]

    # get original CouchDB document
    try:
        doc = db[COUCHDB_STATUS_DOC_ID]
    except couchdb.http.ResourceNotFound:
        doc = {'_id':COUCHDB_STATUS_DOC_ID}

    doc['update_time'] =  pytz.utc.localize( datetime.datetime.utcnow() ).isoformat()

    # get and parse qstat output (see http://jeetworks.org/node/29 for inspiration)
    qstat_cmd = "qstat -xml"

    qstat_proc = subprocess.Popen(qstat_cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=os.environ)
    stdout, stderr = qstat_proc.communicate()

    root = ElementTree.fromstring(stdout)
    queue_info = root.find('queue_info')
    assert queue_info is not None
    jobs = []

    for job_list in queue_info:
        job = {}
        job['id'] = job_list.find("JB_job_number").text
        job['name'] = job_list.find("JB_name").text
        job['owner'] = job_list.find("JB_owner").text
        job['state'] = job_list.find("state").text
#         job['cpu'] = job_list.find("cpu_usage").text
#         job['mem'] = job_list.find("mem_usage").text
#         job['io'] = job_list.find("io_usage").text
        qn = job_list.find("queue_name").text
        job['queue'], node = qn.split("@")
        job['node'] = node[:-6]
        job['node_index'] = int(node[10:-6])
        job['slots'] = job_list.find("slots").text
        stime = datetime.datetime.strptime(job_list.find("JAT_start_time").text, "%Y-%m-%dT%H:%M:%S")
        job["submitted"] = stime.strftime("%Y-%m-%d %H:%M:%S")

        jobs.append(job)

    doc['jobs']=jobs
    doc['uptime']=float(open('/proc/uptime',mode='r').read().strip().split()[0])
    doc['status']='running'

    db.update( [doc] )

def main():
    couch_url = sys.argv[1]
    db_name = sys.argv[2]
    update_couch_view_of_sge_status(couch_url, db_name)

if __name__=='__main__':
    main()
