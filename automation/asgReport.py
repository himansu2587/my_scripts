import boto3
import datetime
import logging
from elasticsearch import Elasticsearch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
EXCLUDED_RECORD_TYPES = {"Tax", "Refund", "Private Rate Card Discount", "Enterprise Discount Program Discount", "Credit"}

# AWS IAM Role
AWS_ROLE_ARN = "arn:aws:iam::{}:role/describe-ec2-role"
AWS_ROLE_SESSION_NAME = "{}-describe-ec2-role"

# Elasticsearch settings
ELASTICSEARCH_HOST = 'kyb-central-prod-es-elk-nlb-int-8be50214bbd7092c.elb.ap-south-1.amazonaws.com'
ELASTICSEARCH_PORT = 80
ELASTICSEARCH_SCHEME = 'http'

elasticsearch_client = Elasticsearch([
    {
        'host': ELASTICSEARCH_HOST,
        'port': ELASTICSEARCH_PORT,
        'scheme': ELASTICSEARCH_SCHEME
    }
])

# Dictionary of AWS account IDs and corresponding names
AWS_ACCOUNT_DICT = {
    "901553615594": "Merchant Dashboards",
    "182401677120": "OE",
    "495419344110": "Incentive",
    "761904723706": "KYB",
    "389881277731": "Merchant-Business",
    "745098155683": "Merchant-PT-Automation",
    "654654497161": "Merchant-Ppsl"
}

def getTagAsg(asg_name, session, target_tag_key="techteam"):
    client = session.client('autoscaling',region_name='ap-south-1')
    response = client.describe_tags(
        Filters=[
            {
                'Name': 'auto-scaling-group',
                'Values': [asg_name]
            },
            {
                'Name': 'key',
                'Values': [target_tag_key]
            }
        ],
        MaxRecords=100
    )
    if response['Tags']:
        return response['Tags'][0]['Value']
    return "no-tag"


def assume_role(account_id, resource='sts'):
    logger.info("Assuming AWS IAM Role Arn")
    client = boto3.client(resource,region_name='ap-south-1')
    assumed_client = client.assume_role(
        RoleArn=AWS_ROLE_ARN.format(account_id),
        RoleSessionName=AWS_ROLE_SESSION_NAME.format(account_id),
    )
    session = boto3.Session(
        aws_access_key_id=assumed_client["Credentials"]["AccessKeyId"],
        aws_secret_access_key=assumed_client["Credentials"]["SecretAccessKey"],
        aws_session_token=assumed_client["Credentials"]["SessionToken"]
    )
    return session

def get_asg_cost(session, start_date, end_date):
    client = session.client('ce',region_name='ap-south-1')
    response = client.get_cost_and_usage(
        TimePeriod={
            'Start': start_date,
            'End': end_date,
        },
        Granularity='DAILY',
        Metrics=['AmortizedCost'],
        Filter={
            'And': [
                {
                    'Not': {
                        'Dimensions': {
                            'Key': 'RECORD_TYPE',
                            'Values': list(EXCLUDED_RECORD_TYPES)
                        }
                    }
                },
                {
                    'Dimensions': {
                        'Key': 'SERVICE',
                        'Values': ['Amazon Elastic Compute Cloud - Compute']
                    }
                }
            ]
        },
        GroupBy=[
            {
                'Type': 'TAG',
                'Key': 'aws:autoscaling:groupName'
            },
        ]
    )
    return response

def push_to_elasticsearch(data, startDate):
    index_name = f'asg-cost-{str(startDate)}'
    if not elasticsearch_client.indices.exists(index=index_name):
        logger.info(f"Creating Index Name {index_name}")
        elasticsearch_client.indices.create(index=index_name)
        logger.info(f"Created index {index_name}")
    elasticsearch_client.index(index=index_name, body=data)
    logger.info(str(data) + "Data Pushed !")




def process_account(session_assumed, account_id, start_date_str, end_date_str, account_name):
    logger.info(f"Processing Account: {account_name} ({account_id})")

    response = get_asg_cost(session_assumed, start_date_str, end_date_str)
    
    for result in response['ResultsByTime']:
        for group in result['Groups']:
            asg_name = group['Keys'][0].split('$')[-1]  # Remove prefix
            if asg_name == '':
                continue
            cost = float(group['Metrics']['AmortizedCost']['Amount'])  # Use correct key for cost
            techteam = getTagAsg(asg_name=asg_name, session=session_assumed)
            doc = {
                'Date': start_date_str,
                'StartDate': start_date_str,
                'EndDate': end_date_str,
                'AccountName': account_name,
                'AccountID': account_id,
                'ASGName': asg_name,
                'techteam': techteam,
                'Cost': cost
            }
            # logger.info(doc)
            push_to_elasticsearch(doc,start_date_str)


def main():
    start_date = datetime.date.today() - datetime.timedelta(days=2)
    end_date = datetime.date.today() - datetime.timedelta(days=1)
    
    current_date = start_date
    while current_date < end_date:
        # Define START_DATE and END_DATE for each day
        startDate = current_date.strftime('%Y-%m-%d')
        endDate = (current_date + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        
        logger.info("Generating data from {} to {} date".format(startDate,endDate))
        for account_id, account_name in AWS_ACCOUNT_DICT.items():
            session = assume_role(account_id=account_id)
            logger.info(f"Session Created for AccountId {account_id}")
            process_account(session, account_id, startDate, endDate, account_name)
        
        # Increment current date
        current_date += datetime.timedelta(days=1)

if __name__ == "__main__":
    main()
