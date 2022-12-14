#Purpose: Creation of Cloudwatch Alarms for Target groups (UnhealthyHostCount >=2 and UnhealthyHostCount >=50% and HealthyHostCount <1 )

#Script WorkFlow
   #Cloudwatch EventBridge (Everyday at 4 PM) -> Lambda Function (lending-target-groups-alarm-creation) -> Iterate through All ELB and Check for "CW_MON = True" Tag -> Create cloudwatch alarms for UnhealthyHostCount       

#Python packages and modules used
import csv
import boto3
import os

#List of target groups for which alarm is created
tg_arn = []

#boto3 client
cloudwatch_client = boto3.client('cloudwatch', region_name = 'ap-south-1')
elb_client = boto3.client('elbv2', region_name = 'ap-south-1')
s3 = boto3.client('s3')

#Variable to store additional SNS Topic based on tag
TEAM_SNS_TOPIC = ""

#Dictionary with mapping of team and respective SNS Topic
switcher = {
        "risk": "arn:aws:sns:ap-south-1:340077773684:risk-alerts",
        "los": "arn:aws:sns:ap-south-1:340077773684:los-alerts",
        "lms": "arn:aws:sns:ap-south-1:340077773684:lms-alerts",
        "collection": "arn:aws:sns:ap-south-1:340077773684:collection-alerts"
    }

#Function to create cloudwatch alarm for HealthyHostCount < 1
def create_high_priority_alarm(tg_name, alb_name, alarm_name, flag):
    #flag variable to check if proper tagging is present in target group. If not present, use only Infra-Alerts SNS Topic
    if flag == 0:
        cloudwatch_client.put_metric_alarm(
            AlarmName=alarm_name,
            ComparisonOperator='GreaterThanOrEqualToThreshold',
            EvaluationPeriods=1,
            Metrics=[{'Id': 'unhealthy',
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
                                            'MetricName': 'UnHealthyHostCount',
                                            'Namespace': 'AWS/ApplicationELB'},
                                    'Period': 300,
                                    'Stat': 'Average'},
                                    'ReturnData': False},
                 {'Id': 'healthy',
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
                                            'MetricName': 'HealthyHostCount',
                                            'Namespace': 'AWS/ApplicationELB'},
                                    'Period': 300,
                                    'Stat': 'Average'},
                                    'ReturnData': False},
                 {'Expression': '100*(unhealthy/(unhealthy+healthy))',
                  'Id': 'e1',
                  'Label': 'UnHealthyHostPercentage-100',
                  'ReturnData': True}
            ],
            Threshold=100,
            ActionsEnabled=True,
            AlarmActions=[
                SNS_TOPIC,
                SNS_TOPIC_NOC,
                SNS_TOPIC_PD
            ],
            AlarmDescription='Alarm when UnHealthyHostCount >= 100% for more than 10 minutes',
        )
    #flag variable to check if proper tagging is present in target group. If present, use Infra-Alerts as well as team specific SNS Topic
    elif flag == 1:
        cloudwatch_client.put_metric_alarm(
            AlarmName=alarm_name,
            ComparisonOperator='GreaterThanOrEqualToThreshold',
            EvaluationPeriods=1,
            Metrics=[{'Id': 'unhealthy',
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
                                            'MetricName': 'UnHealthyHostCount',
                                            'Namespace': 'AWS/ApplicationELB'},
                                    'Period': 300,
                                    'Stat': 'Average'},
                                    'ReturnData': False},
                 {'Id': 'healthy',
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
                                            'MetricName': 'HealthyHostCount',
                                            'Namespace': 'AWS/ApplicationELB'},
                                    'Period': 300,
                                    'Stat': 'Average'},
                                    'ReturnData': False},
                 {'Expression': '100*(unhealthy/(unhealthy+healthy))',
                  'Id': 'e1',
                  'Label': 'UnHealthyHostPercentage-100',
                  'ReturnData': True}
            ],
            Threshold=100,
            ActionsEnabled=True,
            AlarmActions=[
                SNS_TOPIC,
                TEAM_SNS_TOPIC,
                SNS_TOPIC_NOC,
                SNS_TOPIC_PD
            ],
            AlarmDescription='Alarm when UnHealthyHostCount >= 100% for more than 10 minutes',
        )


#Function to create cloudwatch alarm for UnhealthyHostCount >=2
def create_alarm(tg_name, alb_name, alarm_name):
    cloudwatch_client.put_metric_alarm(
        AlarmName=alarm_name,
        ComparisonOperator='GreaterThanOrEqualToThreshold',
        EvaluationPeriods=2,
        MetricName='UnHealthyHostCount',
        Namespace='AWS/ApplicationELB',
        Period=300,
        Statistic='Minimum',
        Threshold=2,
        ActionsEnabled=True,
        AlarmActions=[
            SNS_TOPIC
        ],
        AlarmDescription='Alarm when UnHealthyHostCount >= 2 for more than 10 minutes',
        Dimensions=[
            {
              'Name': 'LoadBalancer',
              'Value': alb_name
            },
            {
              'Name': 'TargetGroup',
              'Value': tg_name
            }
        ]
    )

#Function to create cloudwatch alarm for UnhealthyHostCount >=50%
def create_alarm_exp(tg_name, alb_name, alarm_name, flag):
    #flag variable to check if proper tagging is present in target group. If not present, use only Infra-Alerts SNS Topic
    if flag == 0:
        cloudwatch_client.put_metric_alarm(
            AlarmName=alarm_name,
            ComparisonOperator='GreaterThanOrEqualToThreshold',
            EvaluationPeriods=1,
            Metrics=[{'Id': 'unhealthy',
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
                                            'MetricName': 'UnHealthyHostCount',
                                            'Namespace': 'AWS/ApplicationELB'},
                                    'Period': 300,
                                    'Stat': 'Average'},
                                    'ReturnData': False},
                 {'Id': 'healthy',
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
                                            'MetricName': 'HealthyHostCount',
                                            'Namespace': 'AWS/ApplicationELB'},
                                    'Period': 300,
                                    'Stat': 'Average'},
                                    'ReturnData': False},
                 {'Expression': '100*(unhealthy/(unhealthy+healthy))',
                  'Id': 'e1',
                  'Label': 'UnHealthyHostPercentage',
                  'ReturnData': True}
            ],
            Threshold=50,
            ActionsEnabled=True,
            AlarmActions=[
                SNS_TOPIC,
                SNS_TOPIC_NOC
            ],
            AlarmDescription='Alarm when UnHealthyHostCount >= 50% for more than 10 minutes',
        )
    #flag variable to check if proper tagging is present in target group. If present, use Infra-Alerts as well as team specific SNS Topic
    elif flag == 1:
        cloudwatch_client.put_metric_alarm(
            AlarmName=alarm_name,
            ComparisonOperator='GreaterThanOrEqualToThreshold',
            EvaluationPeriods=1,
            Metrics=[{'Id': 'unhealthy',
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
                                            'MetricName': 'UnHealthyHostCount',
                                            'Namespace': 'AWS/ApplicationELB'},
                                    'Period': 300,
                                    'Stat': 'Average'},
                                    'ReturnData': False},
                 {'Id': 'healthy',
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
                                            'MetricName': 'HealthyHostCount',
                                            'Namespace': 'AWS/ApplicationELB'},
                                    'Period': 300,
                                    'Stat': 'Average'},
                                    'ReturnData': False},
                 {'Expression': '100*(unhealthy/(unhealthy+healthy))',
                  'Id': 'e1',
                  'Label': 'UnHealthyHostPercentage',
                  'ReturnData': True}
            ],
            Threshold=50,
            ActionsEnabled=True,
            AlarmActions=[
                SNS_TOPIC,
                TEAM_SNS_TOPIC,
                SNS_TOPIC_NOC
            ],
            AlarmDescription='Alarm when UnHealthyHostCount >= 50% for more than 10 minutes',
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

#Function to delete existing alarm
# def delete_alarm(alarm_name):
#     cloudwatch_client.delete_alarms(
#         AlarmNames=[
#             alarm_name
#         ]
#     )

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

#Function to define alarm name and check if alarm already exists. If not call create function 
def check_alarm(tg):
    tg_name = tg.split(':')[5]
    alarm_name = "TargetGroup-" + tg.split('/')[1] + "-UnhealthyHostCount"
    alarm_name_exp = "TargetGroup-" + tg.split('/')[1] + "-UnhealthyHostCount-50%"
    high_priority_alarm_name = "TargetGroup-" + tg.split('/')[1] + "-UnhealthyHostCount-100%"
    alb_name=get_load_balancer(tg)
    if alb_name == 0:
        print(tg_name, 'has no Load Balancer attached to it')
    else:
        response_high = cloudwatch_client.describe_alarms(AlarmNames=[high_priority_alarm_name,])
        if response_high['MetricAlarms']:
            # delete_alarm(alarm_name)
            print(high_priority_alarm_name, 'aleady exists')
        else:
            tg_arn.append(tg)
            flag = describe_target_group(tg)
            create_high_priority_alarm(tg_name, alb_name, high_priority_alarm_name, flag)
        response = cloudwatch_client.describe_alarms(AlarmNames=[alarm_name,])
        if response['MetricAlarms']:
            # delete_alarm(alarm_name)
            print(alarm_name, 'aleady exists')
        else:
            tg_arn.append(tg)
            create_alarm(tg_name, alb_name, alarm_name)
        response_exp = cloudwatch_client.describe_alarms(AlarmNames=[alarm_name_exp,])
        if response_exp['MetricAlarms']:
            # delete_alarm(alarm_name_exp)
            print(alarm_name_exp, 'aleady exists')
        else:
            tg_arn.append(tg)
            flag = describe_target_group(tg)
            create_alarm_exp(tg_name, alb_name, alarm_name_exp, flag)

def check_mon_tag(tg_arn):
    response = elb_client.describe_tags(
        ResourceArns=[
            tg_arn
        ]
    )
    all_tags = response['TagDescriptions'][0]['Tags']
    mon = False
    for j in range(len(all_tags)):
        if 'CW_MON' in all_tags[j]['Key'] and all_tags[j]['Value'] in ('True'):
            mon = True
            break
    if mon == True:
        check_alarm(tg_arn)

def lambda_handler(event, context):
    global tg_arn, SNS_TOPIC, SNS_TOPIC_PD, SNS_TOPIC_NOC
    SNS_TOPIC = os.environ['SNS_TOPIC']
    SNS_TOPIC_PD = os.environ['SNS_TOPIC_PD']
    SNS_TOPIC_NOC = os.environ['SNS_TOPIC_NOC']
    response = elb_client.describe_target_groups()
    for tg in response['TargetGroups']:
        check_mon_tag(tg['TargetGroupArn'])
    tg_arn =  list(set(tg_arn))
    if not tg_arn:
        print('Alarms already exist for all the target groups with CW_MON tag')
    else:
        print('Alarms created for following Target Groups:')
        print(tg_arn)
