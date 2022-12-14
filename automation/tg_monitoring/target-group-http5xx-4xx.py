import yaml
import boto3
import git
from git import Repo
from git import Git
import os
from os import walk
from fnmatch import fnmatch

cloudwatch_client = boto3.client('cloudwatch', region_name = 'ap-south-1')
elb_client = boto3.client('elbv2', region_name = 'ap-south-1')

#List of target groups for which alarm is created
tg_names = []

#List of files with rules config
file_paths = []

#Variable to store additional SNS Topic based on tag
TEAM_SNS_TOPIC = ""

#Dictionary with mapping of team and respective SNS Topic
switcher = {
        "risk": "arn:aws:sns:ap-south-1:340077773684:risk-alerts",
        "los": "arn:aws:sns:ap-south-1:340077773684:los-alerts",
        "lms": "arn:aws:sns:ap-south-1:340077773684:lms-alerts",
        "collection": "arn:aws:sns:ap-south-1:340077773684:collection-alerts"
    }

#Function to create cloudwatch alarm for 5XX
def create_5XX_alarm(tg_name, alb_name, alarm_name, flag, working_5xx_absolute, working_5xx_percent, working_5xx_from, working_5xx_to, non_working_5xx_absolute, non_working_5xx_percent, non_working_5xx_from, non_working_5xx_to):
    #flag variable to check if proper tagging is present in target group. If not present, use only Infra-Alerts SNS Topic
    alarm_description = "Alarm when HTTPCode_Target_5XX breaches threshold for 4 out of 5 datapoints within 5 minutes"
    expression = "IF((http5xx > (requestcount * {}) && http5xx > {} && HOUR(http5xx) >= {} && HOUR(http5xx) < {}) || (http5xx > (requestcount * {}) && http5xx > {} && ((HOUR(http5xx) >= {} && HOUR(http5xx) <= 23) || (HOUR(http5xx) >= 0 && HOUR(http5xx) < {}))), http5xx, 0)".format(working_5xx_percent, working_5xx_absolute, working_5xx_from, working_5xx_to, non_working_5xx_percent, non_working_5xx_absolute, non_working_5xx_from, non_working_5xx_to)
    if flag == 0:
        cloudwatch_client.put_metric_alarm(
            AlarmName=alarm_name,
            ComparisonOperator='GreaterThanThreshold',
            EvaluationPeriods=5,
            DatapointsToAlarm=4,
            Metrics=[{'Id': 'http5xx',
                  'MetricStat': {'Metric': {'Dimensions': [
                                                {
                                                  'Name': 'LoadBalancer',
                                                  'Value': alb_name
                                                },
                                                {
                                                  'Name': 'TargetGroup',
                                                  'Value': tg_name
                                                }
                                            ],
                                            'MetricName': 'HTTPCode_Target_5XX_Count',
                                            'Namespace': 'AWS/ApplicationELB'},
                                    'Period': 60,
                                    'Stat': 'Sum'},
                                    'ReturnData': False},
                 {'Id': 'requestcount',
                  'MetricStat': {'Metric': {'Dimensions': [
                                                {
                                                  'Name': 'LoadBalancer',
                                                  'Value': alb_name
                                                },
                                                {
                                                  'Name': 'TargetGroup',
                                                  'Value': tg_name
                                                }
                                            ],
                                            'MetricName': 'RequestCount',
                                            'Namespace': 'AWS/ApplicationELB'},
                                    'Period': 60,
                                    'Stat': 'Sum'},
                                    'ReturnData': False},
                 {'Expression': expression,
                  'Id': 'e1',
                  'Label': 'HTTPCode_Target_5XX_major',
                  'ReturnData': True}
            ],
            Threshold=0,
            TreatMissingData='notBreaching',
            ActionsEnabled=True,
            AlarmActions=[
                SNS_TOPIC_NOC,
                SNS_TOPIC_PD,
                SNS_TOPIC_MAZOR
            ],
            OKActions=[
                SNS_TOPIC_NOC,
                SNS_TOPIC_PD
            ],
            AlarmDescription = alarm_description
        )
    #flag variable to check if proper tagging is present in target group. If present, use Infra-Alerts as well as team specific SNS Topic
    elif flag == 1:
        cloudwatch_client.put_metric_alarm(
            AlarmName=alarm_name,
            ComparisonOperator='GreaterThanThreshold',
            EvaluationPeriods=5,
            DatapointsToAlarm=4,
            Metrics=[{'Id': 'http5xx',
                  'MetricStat': {'Metric': {'Dimensions': [
                                                {
                                                  'Name': 'LoadBalancer',
                                                  'Value': alb_name
                                                },
                                                {
                                                  'Name': 'TargetGroup',
                                                  'Value': tg_name
                                                }
                                            ],
                                            'MetricName': 'HTTPCode_Target_5XX_Count',
                                            'Namespace': 'AWS/ApplicationELB'},
                                    'Period': 60,
                                    'Stat': 'Sum'},
                                    'ReturnData': False},
                 {'Id': 'requestcount',
                  'MetricStat': {'Metric': {'Dimensions': [
                                                {
                                                  'Name': 'LoadBalancer',
                                                  'Value': alb_name
                                                },
                                                {
                                                  'Name': 'TargetGroup',
                                                  'Value': tg_name
                                                }
                                            ],
                                            'MetricName': 'RequestCount',
                                            'Namespace': 'AWS/ApplicationELB'},
                                    'Period': 60,
                                    'Stat': 'Sum'},
                                    'ReturnData': False},
                 {'Expression': expression,
                  'Id': 'e1',
                  'Label': 'HTTPCode_Target_5XX_major',
                  'ReturnData': True}
            ],
            Threshold=0,
            TreatMissingData='notBreaching',
            ActionsEnabled=True,
            AlarmActions=[
                TEAM_SNS_TOPIC,
                SNS_TOPIC_NOC,
                SNS_TOPIC_PD,
                SNS_TOPIC_MAZOR
            ],
            OKActions=[
                SNS_TOPIC_NOC,
                SNS_TOPIC_PD
            ],
            AlarmDescription = alarm_description
        )
#Function to create cloudwatch alarm for 4XX > 20%
def create_4XX_alarm(tg_name, alb_name, alarm_name, flag, working_4xx_absolute, working_4xx_percent, working_4xx_from, working_4xx_to, non_working_4xx_absolute, non_working_4xx_percent, non_working_4xx_from, non_working_4xx_to):
    alarm_description = "Alarm when HTTPCode_Target_4XX breaches threshold for 4 out of 5 datapoints within 5 minutes"
    expression = "IF((http4xx > (requestcount * {}) && http4xx > {} && HOUR(http4xx) >= {} && HOUR(http4xx) < {}) || (http4xx > (requestcount * {}) && http4xx > {} && ((HOUR(http4xx) >= {} && HOUR(http4xx) <= 23) || (HOUR(http4xx) >= 0 && HOUR(http4xx) < {}))), http4xx, 0)".format(working_4xx_percent, working_4xx_absolute, working_4xx_from, working_4xx_to, non_working_4xx_percent, non_working_4xx_absolute, non_working_4xx_from, non_working_4xx_to)
    #flag variable to check if proper tagging is present in target group. If not present, use only Infra-Alerts SNS Topic
    if flag == 0:
        cloudwatch_client.put_metric_alarm(
            AlarmName=alarm_name,
            ComparisonOperator='GreaterThanThreshold',
            EvaluationPeriods=5,
            DatapointsToAlarm=4,
            Metrics=[{'Id': 'http4xx',
                  'MetricStat': {'Metric': {'Dimensions': [
                                                {
                                                  'Name': 'LoadBalancer',
                                                  'Value': alb_name
                                                },
                                                {
                                                  'Name': 'TargetGroup',
                                                  'Value': tg_name
                                                }
                                            ],
                                            'MetricName': 'HTTPCode_Target_4XX_Count',
                                            'Namespace': 'AWS/ApplicationELB'},
                                    'Period': 60,
                                    'Stat': 'Sum'},
                                    'ReturnData': False},
                 {'Id': 'requestcount',
                  'MetricStat': {'Metric': {'Dimensions': [
                                                {
                                                  'Name': 'LoadBalancer',
                                                  'Value': alb_name
                                                },
                                                {
                                                  'Name': 'TargetGroup',
                                                  'Value': tg_name
                                                }
                                            ],
                                            'MetricName': 'RequestCount',
                                            'Namespace': 'AWS/ApplicationELB'},
                                    'Period': 60,
                                    'Stat': 'Sum'},
                                    'ReturnData': False},
                 {'Expression': expression,
                  'Id': 'e1',
                  'Label': 'HTTPCode_Target_4XX_major',
                  'ReturnData': True}
            ],
            Threshold=0,
            TreatMissingData='notBreaching',
            ActionsEnabled=True,
            AlarmActions=[
                SNS_TOPIC_NOC,
                SNS_TOPIC_PD,
                SNS_TOPIC_MAZOR
            ],
            OKActions=[
                SNS_TOPIC_NOC,
                SNS_TOPIC_PD
            ],
            AlarmDescription = alarm_description
        )
    #flag variable to check if proper tagging is present in target group. If present, use Infra-Alerts as well as team specific SNS Topic
    elif flag == 1:
        cloudwatch_client.put_metric_alarm(
            AlarmName=alarm_name,
            ComparisonOperator='GreaterThanThreshold',
            EvaluationPeriods=5,
            DatapointsToAlarm=4,
            Metrics=[{'Id': 'http4xx',
                  'MetricStat': {'Metric': {'Dimensions': [
                                                {
                                                  'Name': 'LoadBalancer',
                                                  'Value': alb_name
                                                },
                                                {
                                                  'Name': 'TargetGroup',
                                                  'Value': tg_name
                                                }
                                            ],
                                            'MetricName': 'HTTPCode_Target_4XX_Count',
                                            'Namespace': 'AWS/ApplicationELB'},
                                    'Period': 60,
                                    'Stat': 'Sum'},
                                    'ReturnData': False},
                 {'Id': 'requestcount',
                  'MetricStat': {'Metric': {'Dimensions': [
                                                {
                                                  'Name': 'LoadBalancer',
                                                  'Value': alb_name
                                                },
                                                {
                                                  'Name': 'TargetGroup',
                                                  'Value': tg_name
                                                }
                                            ],
                                            'MetricName': 'RequestCount',
                                            'Namespace': 'AWS/ApplicationELB'},
                                    'Period': 60,
                                    'Stat': 'Sum'},
                                    'ReturnData': False},
                 {'Expression': expression,
                  'Id': 'e1',
                  'Label': 'HTTPCode_Target_4XX_major',
                  'ReturnData': True}
            ],
            Threshold=0,
            TreatMissingData='notBreaching',
            ActionsEnabled=True,
            AlarmActions=[
                TEAM_SNS_TOPIC,
                SNS_TOPIC_NOC,
                SNS_TOPIC_PD,
                SNS_TOPIC_MAZOR
            ],
            OKActions=[
                SNS_TOPIC_NOC,
                SNS_TOPIC_PD
            ],
            AlarmDescription = alarm_description
        )


#Function to extract load balancer arn
def get_load_balancer(tg):
    response = elb_client.describe_target_groups(
        TargetGroupArns=[
            tg,
        ]
    )
    if not response['TargetGroups'][0].get('LoadBalancerArns'):
        return(0)
    else:
        return(response['TargetGroups'][0].get('LoadBalancerArns')[0].split('/', 1)[1])

#Function to check if proper tagging is present on Target Group
def describe_target_group(tg):
    global TEAM_SNS_TOPIC
    response = elb_client.describe_tags(
        ResourceArns=[
            tg,
        ]
    )
    all_tags = response['TagDescriptions'][0]['Tags']
    if not all_tags:
        return(0)
    else:
        for j in range(len(all_tags)):
            flag = 0
            if 'Alarm_Team' in all_tags[j]['Key']:
                if all_tags[j]['Value'] in switcher:
                    flag = 1
                    TEAM_SNS_TOPIC = switcher.get(all_tags[j]['Value'])
                    break
        return(flag)

#Function to populate list of file names with .yaml pattern
def list_files(dir_path, pattern):
    for (path, subdirs, files) in walk(dir_path):
        for name in files:
            if fnmatch(name, pattern):
                complete_path = str(os.path.join(path, name))
                file_paths.append(complete_path)

def lambda_handler(event, context):
    global tg_names, SNS_TOPIC_PD, SNS_TOPIC_NOC, SNS_TOPIC_MAZOR
    SNS_TOPIC_PD = os.environ['SNS_TOPIC_PD']
    SNS_TOPIC_NOC = os.environ['SNS_TOPIC_NOC']
    SNS_TOPIC_MAZOR = os.environ['SNS_TOPIC_MAZOR']
    ssm = boto3.client('ssm', region_name='ap-south-1')
    parameter = ssm.get_parameter(Name='git-private-key')
    private_key = parameter['Parameter']['Value']
    with open('/tmp/git-private-key', 'w') as outfile:
        outfile.write(private_key)
    os.chmod('/tmp/git-private-key', 0o600)
    git_ssh_identity_file = '/tmp/git-private-key'
    git_ssh_cmd = 'ssh -i %s -o StrictHostKeyChecking=no' % git_ssh_identity_file
    repo_url = 'git@bitbucket.org:paytmteam/lending-automation-scripts.git'
    repo_name = '/tmp/lending-automation-scripts'
    repo = Repo.clone_from(repo_url, os.path.join(os.getcwd(), repo_name),env=dict(GIT_SSH_COMMAND=git_ssh_cmd))
    repo.git.checkout('tg-alarms')
    list_files('/tmp/lending-automation-scripts/tg-alarms', '*.yaml')
    for file_name in file_paths:
        with open(file_name) as file:
            try:
                rulesConfig = yaml.safe_load(file)   
                for tg in rulesConfig:
                    tg_name = tg.get('tg_name')
                    for rule in tg.get('rules'):
                        if rule.get('alert') == 'http5xx':
                            working_5xx_absolute = rule.get('working_hours').get('absolute_value')
                            working_5xx_percent = rule.get('working_hours').get('percentage')
                            working_5xx_from = rule.get('working_hours').get('from') - 5
                            working_5xx_to = rule.get('working_hours').get('to') - 5
                            non_working_5xx_absolute = rule.get('non_working_hours').get('absolute_value')
                            non_working_5xx_percent = rule.get('non_working_hours').get('percentage')
                            non_working_5xx_from = rule.get('non_working_hours').get('from') - 5
                            non_working_5xx_to = rule.get('non_working_hours').get('to') - 5
                        elif rule.get('alert') == 'http4xx':
                            working_4xx_absolute = rule.get('working_hours').get('absolute_value')
                            working_4xx_percent = rule.get('working_hours').get('percentage')
                            working_4xx_from = rule.get('working_hours').get('from') - 5
                            working_4xx_to = rule.get('working_hours').get('to') - 5
                            non_working_4xx_absolute = rule.get('non_working_hours').get('absolute_value')
                            non_working_4xx_percent = rule.get('non_working_hours').get('percentage')
                            non_working_4xx_from = rule.get('non_working_hours').get('from') - 5
                            non_working_4xx_to = rule.get('non_working_hours').get('to') - 5
                    response = elb_client.describe_target_groups(Names=[tg_name])
                    tg_arn = response['TargetGroups'][0]['TargetGroupArn']
                    http_5xx_alarm_name = "TargetGroup-" + tg_name + "-HTTPCode_Target_5XX"
                    http_4xx_alarm_name = "TargetGroup-" + tg_name + "-HTTPCode_Target_4XX"
                    alb_name=get_load_balancer(tg_arn)
                    if alb_name == 0:
                        print(tg_name, 'has no Load Balancer attached to it')
                    else:
                        tg_names.append(tg_name)
                        flag = describe_target_group(tg_arn)
                        create_5XX_alarm(tg_name, alb_name, http_5xx_alarm_name, flag, working_5xx_absolute, working_5xx_percent/100, working_5xx_from, working_5xx_to, non_working_5xx_absolute, non_working_5xx_percent/100, non_working_5xx_from, non_working_5xx_to)
                        create_4XX_alarm(tg_name, alb_name, http_4xx_alarm_name, flag, working_4xx_absolute, working_4xx_percent/100, working_4xx_from, working_4xx_to, non_working_4xx_absolute, non_working_4xx_percent/100, non_working_4xx_from, non_working_4xx_to)         
            except yaml.YAMLError as exc:
                print(exc)
    print('Alarms created/updated for following Target Groups:')
    print(tg_names)
