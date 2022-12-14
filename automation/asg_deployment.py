# -*- coding: utf-8 -*-
""" deploy.py: Script to Deploy Performance testing """

__author__ = "Ashish Yadav"
__version__ = "0.0.1"
__maintainer__ = "Ashish yadav"
__email__ = "ashish6.yadav@paytm.com"
__status__ = "Production"

import boto3
import argparse
import paramiko
import time
import logging, coloredlogs
import sys

FORMATTER = logging.Formatter("%(asctime)s — %(levelname)s — %(message)s")
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(FORMATTER)
logger = logging.getLogger('Performance testing Deployment')
logger.setLevel(logging.DEBUG)
logger.addHandler(console_handler)
logger.propagate = False
coloredlogs.install(fmt='%(asctime)s - %(levelname)s - %(message)s', logger=logger)

class DoDeployment:
    def __init__(self, ip_addr, build, env):
        try:
            self.ip = ip_addr
            self.ssh = paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.password = None
            self.bucket = "paytm-lending-infra"
            self.prefix = "artifacts/lending-lms-performance/{env}".format(env=env)
            self.build = "{build}".format(build=build)
            self.service = 'lmsapp.service'
            if self.password is None:
                print
                'Making paramiko ssh object'
                self.ssh.connect(
                    hostname=ip_addr,
                    username='ops',
                    key_filename='/jenkins/.ssh/ops',  # TODO: Change to jenkins KEY once on prod
                    timeout=10)
            else:
                self.ssh.connect(
                    hostname=ip_addr,
                    username='ops',
                    key_filename='',
                    timeout=10
                )
        except paramiko.AuthenticationException:
            logger.error("Authentication failed, please verify your credentials")
            exit(1)
        except paramiko.SSHException as sshException:
            logger.error("Could not establish SSH connection: %s" % sshException)
            exit(1)
        except Exception as e:
            logger.error("Exception in connecting to the server")
            logger.error("PYTHON SAYS: {0}".format(e))
            exit(1)

    # def test_connection(self):
    #     stdin, stdout, stderr = self.ssh.exec_command("curl -I -X GET  http://localhost:30000/v3/user/profile -H 'Postman-Token: 508923b2-4c0c-4332-b855-c146899a0ea6' -H 'X-USER-ID: 19419231' -H 'X-USER-SSOTOKEN: 4767a9b4-d559-4bd1-b425-48a61b057900' -H 'cache-control: no-cache' -H 'session_token: 4767a9b4-d559-4bd1-b425-48a61b057900' -H 'sso_token: 4767a9b4-d559-4bd1-b425-48a61b057900'")
    #     print stdout.readlines()
    #     logger.debug(stdout.readlines())

    def download_object_from_s3(self):
        logger.info("Downloading build from S3")
        logger.debug("aws s3 cp s3://{bucket}/{prefix}/{build} /tmp/{build}".format(
            bucket=self.bucket,
            prefix=self.prefix,
            build=self.build
        ))
        stdin, stdout, stderr = self.ssh.exec_command("aws s3 cp s3://{bucket}/{prefix}/{build} /tmp/{build}".format(
            bucket=self.bucket,
            prefix=self.prefix,
            build=self.build
        ))
        #print(stdin.readlines())
        #print(stdout.readlines())
        #print(stderr.readlines())
        exit_status = stdout.channel.recv_exit_status()
        if exit_status == 0:
            logger.info("File Downloaded")
        else:
            logger.error("error: {0}".format(stderr.readlines()))
            exit(1)

    def perform_deployment(self):
        logger.debug("sudo systemctl stop {service} && sudo yum localinstall /tmp/{build} -y".format(service=self.service,
                                                                                  build=self.build))
        stdin, stdout, stderr = self.ssh.exec_command(
            "sudo systemctl stop {service} && sudo yum localinstall /tmp/{build} -y".format(service=self.service,
                                                                                build=self.build))
        logger.info(stdout.readlines())
        install_status = stdout.channel.recv_exit_status()
        if install_status == 0:
            stdin, stdout, stderr = self.ssh.exec_command(
                "sudo systemctl daemon-reload; sudo systemctl start {service}".format(service=self.service)
            )
            start_status = stdout.channel.recv_exit_status()
            if start_status == 0:
                logger.info("{service} installation done".format(service=self.service))
                stdin, stdout, stderr = self.ssh.exec_command("curl localhost:80/lms/actuator/health")
                print stdout.readlines()
            else:
                logger.error("Failed to start {service}, after installing {build}".format(service=self.service,
                                                                                   build=self.build))
                # TODO Implement rollback strategy
                exit(1)
        else:
            logger.error("Failed to install {build} on {ip}".format(build=self.build, ip=self.ip))
            exit(1)
        logger.info("Deployment Completed")

def get_allowed_instances(asg,region):
    session = boto3.Session()
    client_asg = session.client('autoscaling',region_name=region)
    client_instance = session.client('ec2',region_name=region)
    response_asg = client_asg.describe_auto_scaling_groups(AutoScalingGroupNames=[asg])
    instance_list = [ x['InstanceId'] for x in response_asg['AutoScalingGroups'][0]['Instances'] ]
    ip_list = []
    try:
        response_instance = client_instance.describe_instances(InstanceIds=instance_list)
        ip_list += [ x['Instances'][0]['PrivateIpAddress'] for x in response_instance['Reservations'] ]
    except:
        print("No Instances are present in an ASG")
    server_count = len(ip_list)
    logger.info("Servers Present in ASG {count}".format(count=server_count))
    return ip_list


def main():
    allowed_instances = get_allowed_instances('lending-lms-performance-testing','ap-south-1')
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", help="Build file to be installed on servers")
    parser.add_argument("--env", help="Environment in which deploying")
    print(allowed_instances)
    args = parser.parse_args()

    #print(args.build,args.env)

    #if args.server in allowed_instances:
    for server in allowed_instances:
        DoDeployment(ip_addr=server,
                     build=args.build,env=args.env).download_object_from_s3()
        DoDeployment(ip_addr=server,
                     build=args.build,env=args.env).perform_deployment()
        logger.info("Deployment completed")


if __name__ == '__main__':
    #DoDeployment('10.165.1.18','test').test_connection()
    main()
