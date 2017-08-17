#!/usr/bin/env python

from datetime import datetime, timedelta
from argparse import ArgumentParser
from threading import Thread
import xml.etree.ElementTree as xml
import re 
import pwd 
import grp 
import socket
import oca

class OneClient():
    """A simple OpenNebula API test class"""

    ONE_ENDPOINT = 'https://api.hpccloud.surfsara.nl/RPC2'
    ONE_USER = 'dccn-hongl'        # replace this with your HPC Cloud UI username
    ONE_PASSWORD = 'o^SYYLp3'      # replace this with your HPC Cloud UI password

    def __init__(self):
        self.client = oca.Client(self.ONE_USER + ':' + self.ONE_PASSWORD, self.ONE_ENDPOINT)

    def ask_version(self):
        return self.client.version()

    def getListOfVmTemplates(self):
        pool = oca.VmTemplatePool(self.client)
        pool.info()
        return pool

    def getVmTemplateByName(self, templateName):
        pool = oca.VmTemplatePool(self.client)
        pool.info()
        return pool.get_by_name(templateName)

    def deleteVmTemplateByName(self, templateName):
        self.getVmTemplateByName(templateName).delete()

    def cloneVmTemplate(self, templateName, newTemplateName):
        t = self.getVmTemplateByName(templateName)
        t.clone(name=newTemplateName)
        return self.getVmTemplateByName(newTemplateName)

    def getListOfVMs(self):
        pool = oca.VirtualMachinePool(self.client)
        pool.info()
        return pool

    def getVmByName(self, vmName):
        pool = oca.VirtualMachinePool(self.client)
        pool.info()
        return pool.get_by_name(vmName)

    def startVmByTemplate(self, vmName, vmTemplateName):
        vmt = self.getVmTemplateByName(vmTemplateName)
        print vmt.info()
        vmt.instantiate(vmName)
        vm = self.getVmByName(vmName)
        while vm.str_lcm_state != 'RUNNING':
            vm.info()
            print("%s:%s:%s" % (vm.id, vm.str_state, vm.str_lcm_state))
        return vm

    def stopVmByName(self, vmName):
        pool = oca.VirtualMachinePool(self.client)
        pool.info()
        vm = pool.get_by_name(vmName)
        vm.shutdown()
        while vm.str_state != 'DONE':
            vm.info()
            print("%s:%s:%s" % (vm.id, vm.str_state, vm.str_lcm_state))
        return vm

    def stopVmById(self, vmId):
        pool = oca.VirtualMachinePool(self.client)
        pool.info()
        vm = pool.get_by_id(vmId)
        vm.shutdown()
        while vm.str_state != 'DONE':
            vm.info()
            print("%s:%s:%s" % (vm.id, vm.str_state, vm.str_lcm_state))
        return vm

    def stopVmByIp(self, vmIp):
        pool = oca.VirtualMachinePool(self.client)
        pool.info()

        vms = filter( lambda x:x.template.nics[0].ip == vmIp, list(pool) )

        if not vms:
            return None
        else:
            vm = vms[0]
            vm.shutdown()
            while vm.str_state != 'DONE':
                vm.info()
                print("%s:%s:%s" % (vm.id, vm.str_state, vm.str_lcm_state))
            return vm

class VmStarter(Thread):

    def __init__(self, jobid, ncore, memGB, ttl, name_vmt, name_vm):
        Thread.__init__(self)
        self.jobid = jobid 
        self.ncore = ncore 
        self.memGB = memGB 
        self.n_vm  = name_vm
        self.n_vmt = name_vmt

        # resolve walltime string into timedelta object with 1 hour extra overhead/buffer
        data = ttl.split(':')
        reversed(data)
        td_args = {}
        td_keys = ['seconds','minutes','hours','days']
        for i in xrange(len(data)):
            td_args[ td_keys[i] ] = int(data[i]) 
        self.ttl = timedelta( **td_args ) + timedelta(hours=1)

    def run(self):
        oc = OneClient()

        ## start VM from template
        vm = oc.startVmByTemplate(self.n_vm, self.n_vmt)

        ip = vm.template.nics[0].ip
        ttl_s = datetime.strftime(datetime.utcnow() + self.ttl, '%Y-%m-%dT%H:%M:%SZ')

        print('%s: vm %s started, ip: %s' % (vm.id, vm.name, ip))


        # TODO: execute system call to add dynamic node to Torque resource manager
        qmgr_cmd = 'create node %s.vm.surfsara.nl np=%d,TTL=%s,requestid=%s' % (ip, self.ncore, ttl_s, self.jobid)
        print(qmgr_cmd)

class VmStopper(Thread):

    def __init__(self, nameOrId):
        Thread.__init__(self)
        self.nameOrId = nameOrId 

    def run(self):
        oc = OneClient()
        vm = None
        if re.match('^[0-9]+$', self.nameOrId):
            vm = oc.stopVmById(int(self.nameOrId))
        else: 
            try:
                socket.inet_aton(self.nameOrId)
                vm = oc.stopVmByIp(self.nameOrId)
            except socket.error:
                vm = oc.stopVmByName(self.nameOrId)

        print('%s: vm %s stopped' % (vm.id, vm.name))

def prepareTemplate(base, jobid, ncore, memGB, udata, gdata):
    ''' create/register new template for job, and return the registered template name'''

    oc = OneClient()

    ## clone template for this current VM 
    vmt_name = 't_job' + str(jobid)
    t = oc.cloneVmTemplate(base, vmt_name)

    r = xml.fromstring(t.template.xml)
    c = r.find('CONTEXT')
    i = c.getchildren().index(c.find('START_SCRIPT'))

    # list of user attributes and values for the current user 
    uinfo = {'TRQ_UID'   : str(udata.pw_uid),
             'TRQ_UNAME' : udata.pw_name,
             'TRQ_UHOME' : udata.pw_dir,
             'TRQ_GID'   : str(gdata.gr_gid),
             'TRQ_GNAME' : gdata.gr_name}

    # update template with current user's information 
    for k,v in uinfo.iteritems():
        i+=1
        # remove existing user information from template
        for e in c.findall(k):
            c.remove(e)

        # add current user information from template
        e = xml.Element(k)
        e.text = v
        c.insert(i,e)

    t.update(xml.tostring(r))

    return vmt_name

def deployVMs(args):
    request = args.request

    jobid = args.jobid
    user = args.user

    # get user's system information
    udata = None
    gdata = None
    try:
        udata = pwd.getpwnam(user)
        gdata = grp.getgrgid(udata.pw_gid)
    except KeyError:
        pass

    # ISSUE: there is no memory and core information in the $REQUESTGEOMETRY of Moab?
    memGB = 8
    ncore = 1

    # determin VM's TTL from the walltime information from the $REQUESTGEOMETRY of Moab?
    walltime = request.split('@')[-1]

    # determine number of nodes from the $REQUESTGEOMETRY of Moab, or 1 node
    nnode = 1
    try:
        nnode = int(request.split('@')[0])
    except ValueError:
        pass

    # prepare template 
    vmt_name = prepareTemplate('torque-mom.%dC%dG' % (ncore, memGB),
                               jobid, ncore, memGB, udata, gdata)

    # start nodes, each has 1 core and 8 GB memory
    threads = []
    for i in xrange(nnode):
        vm_name = 'trq-j%s-n%d' % (str(jobid), i+1)
        t = VmStarter(jobid, ncore, memGB, walltime, vmt_name, vm_name)
        threads.append(t)
        t.start()

    # remove the VM template when all starting threads are finished
    for t in threads:
        t.join()

    print('removing template %s' % vmt_name)
    oc = OneClient()
    oc.deleteVmTemplateByName(vmt_name)

def shutdownVMs(args):
    for n in args.name:
        t = VmStopper(n)
        t.start()

def listObjs(args):
    oc = OneClient()
    if args.target == 'vm':
        for p in oc.getListOfVMs():
            print('%s: %s' % (p.id, p.name))

    elif args.target == 'template':
        for p in oc.getListOfVmTemplates():

            r = xml.fromstring(p.template.xml)
            c = r.find('CONTEXT')
            for k in ['TRQ_UID', 'TRQ_UNAME', 'TRQ_UHOME', 'TRQ_GID', 'TRQ_GNAME']:
                for e in c.findall(k):
                    c.remove(e)

            print('%s: %s, %s' % (p.id, p.name, xml.tostring(r)))

if __name__ == '__main__':

    parser = ArgumentParser(description='deploy/shutdown VMs on SURFSara HPC cloud, using predefined templates', version="0.1")
    subparser = parser.add_subparsers()

    # arguments for deploy
    deploy = subparser.add_parser('deploy')

    deploy.add_argument('-j','--jobid',
                      action   = 'store',
                      dest     = 'jobid',
                      type     = int,
                      required = True,
                      help     = 'the torque/moab job id')

    deploy.add_argument('-u','--user',
                      action   = 'store',
                      dest     = 'user',
                      type     = str,
                      required = True,
                      help     = 'the torque/moab job user name')

    deploy.add_argument('-r','--request-geometry',
                      action  = 'store',
                      dest    = 'request',
                      type    = str,
                      default = '1@12:00:00',
                      help    = 'the job request geometry')

    deploy.set_defaults(func=deployVMs)

    # arguments for shutdown 
    shutdown = subparser.add_parser('shutdown')

    shutdown.add_argument('-n', '--node-name',
                          action   = 'store',
                          dest     = 'name',
                          required = True,
                          type     = str,
                          nargs    = '*',
                          help     = 'the name of VMs')

    shutdown.set_defaults(func=shutdownVMs)

    # arguments for shutdown 
    listo = subparser.add_parser('list')

    listo.add_argument('-t','--target',
                      action  = 'store',
                      dest    = 'target',
                      type    = str,
                      choices = ['vm','template'],
                      default = 'vm',
                      help    = 'list objects in the targeting pool')

    listo.set_defaults(func=listObjs)

    ##  
    cmd = parser.parse_args()
    cmd.func(cmd)
