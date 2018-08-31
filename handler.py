import json
import boto3
import os

class BlueGreenSwitcher(object):
    def __init__(self, prod_elb_name, temp_elb_name, prod_asg, new_asg):
        self.status_success = False
        self.ssm = boto3.client('ssm')
        self.asg = boto3.client('autoscaling')
        self.elb = boto3.client('elb')
        ##########
        ## Variables holding current state values
        ##########
        self.prod_elb = prod_elb_name
        self.new_elb = temp_elb_name
        self.prod_asg = prod_asg
        self.new_asg = new_asg
        self.old_instances = None
        self.new_instances = None
        ## Variables Holding Rollback values
        self.rollback_prod_asg = prod_asg
        self.rollback_new_asg = new_asg

    # in our definition 1 LB => 1 ASG
    def asg_get_loadbalancers(self, elb_name, asg, NextToken = None):
        lrsp = None
        if NextToken:
            lrsp = self.asg.describe_load_balancers(AutoScalingGroupName=asg, NextToken=NextToken)
        else:
            lrsp = self.asg.describe_load_balancers(AutoScalingGroupName=asg)

        for l in lrsp['LoadBalancers']:
            if l['LoadBalancerName'] == elb_name:
                yield l['LoadBalancerName']

        if 'NextToken' in lrsp:
            for l in asg_get_loadbalancers(asg, NextToken = lrsp['NextToken']):
                yield l

    def asg_get_instances(self, asg, NextToken = None):
        irsp = None
        if NextToken:
            irsp = self.asg.describe_auto_scaling_instances(NextToken=NextToken)
        else:
            irsp = self.asg.describe_auto_scaling_instances()

        for i in irsp['AutoScalingInstances']:
            if i['AutoScalingGroupName'] == asg:
                yield {"InstanceId": i['InstanceId']}

        if 'NextToken' in irsp:
            for i in as_get_instances(asg, NextToken = irsp['NextToken']):
                yield i


    def register(self, elb_name, asg_name, instances):
        self.asg.attach_load_balancers(
            AutoScalingGroupName=asg_name,
            LoadBalancerNames=[
                elb_name
            ]
        )
        ec2s = []

        self.elb.register_instances_with_load_balancer(
            LoadBalancerName=elb_name,
                Instances=instances
        )

    def deregister(self, elb_name, asg_name, instances):
        self.asg.detach_load_balancers(
            AutoScalingGroupName=asg_name,
            LoadBalancerNames=[
                elb_name
            ]
        )
        ec2s = []

        self.elb.deregister_instances_from_load_balancer(
            LoadBalancerName=elb_name,
                Instances=instances
        )

    def update_state(self, current_state, prod_asg, new_asg):
        new_state = 'green'
        if current_state == 'green':
            new_state = 'blue'

        self.ssm.put_parameter(
            Name=os.environ['current_state_parameter'],
            Value=new_state,
            Type='String',
            Overwrite=True
        )

        self.ssm.put_parameter(
            Name=os.environ['prod_asg_parameter'],
            Value=new_asg,
            Type='String',
            Overwrite=True
        )

        self.ssm.put_parameter(
            Name=os.environ['temp_asg_parameter'],
            Value=prod_asg,
            Type='String',
            Overwrite=True
        )

    def get_status(self):
        return self.status_success

    def process(self, current_state):
        try:
            self.old_instances = list(self.asg_get_instances(self.prod_asg))
            self.new_instances = list(self.asg_get_instances(self.new_asg))
            print("OLD: {0}".format(self.old_instances))
            print("NEW: {0}".format(self.new_instances))
            self.deregister(self.prod_elb,self.prod_asg,self.old_instances)
            self.deregister(self.new_elb,self.new_asg,self.new_instances)
            self.register(self.new_elb,self.prod_asg,self.old_instances)
            self.register(self.prod_elb,self.new_asg,self.new_instances)
            self.update_state(current_state, self.prod_asg, self.new_asg)
            self.status_success = True
        except Exception as e:
            self.status_success = False
            print(e)

ssm = boto3.client('ssm')

def get_keyvalue(key):
	resp = ssm.get_parameter(
		Name=key,
		WithDecryption=True
	)
	return resp['Parameter']['Value']

def switcher():
    current_state = get_keyvalue(os.environ['current_state_parameter'])
    prod_elb = get_keyvalue(os.environ['prod_elb_parameter'])
    temp_elb = get_keyvalue(os.environ['temp_elb_parameter'])
    prod_asg = get_keyvalue(os.environ['prod_asg_parameter'])
    new_asg = get_keyvalue(os.environ['temp_asg_parameter'])

    print("*********** BEFORE *******************")
    print(" PROD_ELB : {0}".format(prod_elb))
    print(" PROD_ASG : {0}".format(prod_asg))
    print(" TEMP_ELB : {0}".format(temp_elb))
    print(" TEMP_ASG : {0}".format(new_asg))
    print(" STATE    : {0}".format(current_state))
    print("*************************************")

    switcher = None
    switcher = BlueGreenSwitcher(prod_elb, temp_elb, prod_asg, new_asg)
    switcher.process(current_state)

    current_state = get_keyvalue(os.environ['current_state_parameter'])
    prod_elb = get_keyvalue(os.environ['prod_elb_parameter'])
    temp_elb = get_keyvalue(os.environ['temp_elb_parameter'])
    prod_asg = get_keyvalue(os.environ['prod_asg_parameter'])
    new_asg = get_keyvalue(os.environ['temp_asg_parameter'])

    print("*********** AFTER *******************")
    print(" PROD_ELB : {0}".format(prod_elb))
    print(" PROD_ASG : {0}".format(prod_asg))
    print(" TEMP_ELB : {0}".format(temp_elb))
    print(" TEMP_ASG : {0}".format(new_asg))
    print(" STATE    : {0}".format(current_state))
    print("*************************************")

    return switcher.get_status()

def switch(event, context):
    if switcher():
        return "Deployment Switch is Successful!"
    else:
        return "Deployment Switch is Unsuccessful! Issuing a Rollback ...."


if __name__ == "__main__":
    if switcher():
        print("Deployment Switch is Successful!")
    else:
        print("Deployment Switch is Unsuccessful! Issuing a Rollback ....")
