# Integrating OpenNebula cloud resource with Moab cluster

Using the Elastic Computing feature of Moab, the aim is to burst out HPC cluster resources to the SURFSara HPC cloud, and OpenNebula-based IaaS cloud.

The burst-out is implemented in Moab as a QOS tigger that calls a user-provided script for provisioning dynamic pbs_mom nodes in the cloud.  We use the python-oca to manage dynamic VMs in the SURFSara HPC Cloud.

## Requirement on Torque/Moab server

- install the latest version of python-oca from github
- configure Moab with a QOS trigger
- provide a script for Moab to create and remove VMs from the cloud

### Install python-oca

```bash
$ git clone https://github.com/python-oca/python-oca.git
$ cd python-oca
$ python setup.py install
```

### Moab configuration

An example is provided below. Note the script and options in the `TRIGGER` entries. The first one is for creating new VMs, while the second is to remove VMs.  The action of creating VM is triggered when the `BACKLOGCOMPLETETIME` is larger than `500` seconds; and when the VM is called to shutdown when it has been idle for more than 120 seconds.

```bash
# Add qos elastic to all users
USERCFG[DEFAULT]        QLIST=elastic

# Enable scheduling on elastic nodes
SCHEDCFG[Moab]		FLAGS=enabledynamicnodes

# This trigger is used by Moab to sync its internal elastic usage records with RLM
SCHEDCFG[Moab]		TRIGGER=atype=exec,action="$TOOLSDIR/rlm/sync_moab_rlm.py -f /opt/rlm/adaptiveco.log",etype=standing,period=minute,offset=10

QOSCFG[DEFAULT]		ENABLEPROFILING=TRUE
NODECFG[DEFAULT]	ENABLEPROFILING=TRUE

# Send script the request geometry of the highest priority job in the backlog
QOSCFG[elastic]		REQUESTGEOMETRY=PRIORITYJOBSIZE

# Create an elastic node if the back log completion time exceeds 500 processor seconds
QOSCFG[elastic]		TRIGGER=EType=threshold,AType=exec,TType=elastic,Action="$TOOLSDIR/dccn/elastic-hpccloud-mom-trigger.py deploy --jobid $JOBID --user $USER --request-geometry $REQUESTGEOMETRY",Threshold=BACKLOGCOMPLETIONTIME>500,RearmTime=01:00

# Remove nodes if they are idle for 120 seconds
NODEIDLEPURGETIME		120

# Remove elastic nodes when the TTL expires
NODECFG[DEFAULT]		TRIGGER=EType=end,AType=exec,TType=elastic,Action="$TOOLDIR/dccn/elastic-hpccloud-mom-trigger.py shutdown --node-name $OID"
```

## The VM creat/delete script

An example script is [elastic-hpccloud-mom-trigger.py](https://github.com/Donders-Institute/hpccloud/blob/master/elastic-hpccloud-mom-trigger.py) in this repository.

This script assumes that one has manually created a basic template and working VM image (e.g. pbs_mom, trqauthd are preinstalled) in the OpenNebula system.  When deploying a new VM, the script crons the basic template, modifies the croned template (mainly for user/group provisioning), and initiates VMs from it. The croned template is then removed after required VMs are started.
