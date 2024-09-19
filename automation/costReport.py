import boto3
import sys
import datetime
import logging
from elasticsearch import Elasticsearch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
AWS_ACCOUNT_DICT = {
    "901553615594": "Merchant Dashboards",
    "182401677120": "OE",
    "495419344110": "Incentive",
    "761904723706": "KYB",
    "389881277731": "Merchant-Business",
    "745098155683": "Merchant-PT-Automation",
    "654654497161": "Merchant-Ppsl",
    "465354398947": "aws-aml-uat-admin",
    "532041146482": "aws-ppsl-nonprod-admin",
    "562921704166": "aws-ups-562921704166-admin",
    "647564693872": "aws-aml-prod-admin",
    "730335596554": "aws-ppsl-aml-prod-admin",
    "752518464574": "aws-ups-752518464574-admin",
    "975049937880": "aws-mgv-sclp-admin",
    "992382517474": "aws-ppsl-central-tools-admin",
    "064619502227": "aws-CentralToolsPlatform-admin",
    "054736913503": "aws-scp-mgv-admin",
    "290310562512": "aws-bpay-ocl-admin",
    "841860372390": "Hdfc-Issuer-Prod",
    "997924011427": "ATS/STS",
    "798411736697": "RAPS-Prod",
    "492902601864": "Ncmc-acq-nonprod",
    "176839215860": "Omni-card-prod",
    "116631508635": "Fastag-nonprod",
    "135329050410": "citybus",
    "239103975135": "QR",
    "789596305652": "Mutual-Fund",
    "419830208690": "AAAS-Prod",
    "718893572916": "AAAS-Nonprod"
}

TAG_NAME = 'techteam'
ELASTICSEARCH_HOST = 'kyb-central-prod-es-elk-nlb-int-8be50214bbd7092c.elb.ap-south-1.amazonaws.com'
ELASTICSEARCH_PORT = 80
ELASTICSEARCH_SCHEME = 'http'

# AWS IAM Role
AWS_ROLE_ARN = "arn:aws:iam::{}:role/describe-ec2-role"
AWS_ROLE_SESSION_NAME = "{}-describe-ec2-role"

# Filter values
RECORD_TYPE_VALUES = ["Tax", "Refund", "Private Rate Card Discount", "Enterprise Discount Program Discount", "Credit"]

# Initialize Elasticsearch client
elasticsearch_client = Elasticsearch([
    {
        'host': ELASTICSEARCH_HOST,
        'port': ELASTICSEARCH_PORT,
        'scheme': ELASTICSEARCH_SCHEME
    }
])

def get_tags(session, tag_name):
    try:
        client = session.client('resourcegroupstaggingapi', region_name="ap-south-1")
        response = client.get_tag_values(Key=tag_name)
        return response['TagValues']
    except Exception as e:
        logger.error(f"Exception - {e}")
        raise e

def get_cost(session, start_date, end_date, filter):
    client = session.client('ce',region_name="ap-south-1")
    response = client.get_cost_and_usage(
        TimePeriod={
            'Start': start_date,
            'End': end_date,
        },
        Granularity='DAILY',
        Metrics=['AmortizedCost'],
        Filter=filter,
        GroupBy=[
            {
                'Type': 'DIMENSION',
                'Key': 'SERVICE'
            },
        ]
    )
    return response

def push_data_to_elasticsearch(data,startDate):
    # startDate = startDate.strftime('%Y-%m-%d')
    index_name = f'cost-report-{str(startDate)}'
    if not elasticsearch_client.indices.exists(index=index_name):
        logger.info(f"Creating Index Name {index_name}")
        elasticsearch_client.indices.create(index=index_name)
        logger.info(f"Created index {index_name}")
    elasticsearch_client.index(index=index_name, body=data)
    logger.info(str(data) + "Data Pushed !")

def assume_role(account_id, resource='sts'):
    logger.info("Assuming AWS IAM Role Arn")
    client = boto3.client(resource,region_name="ap-south-1")
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

def process_account(session, account_id, startDate, endDate, account_name):
    logger.info(f"Processing AccountId {account_id}")
    tag_values = get_tags(session, TAG_NAME)
    
    total_cost = 0
    total_filter = {
        'Not': {"Dimensions": {"Key": "RECORD_TYPE", "Values": RECORD_TYPE_VALUES}}
    }
    total_account_cost_response = get_cost(session, startDate, endDate, total_filter)
    no_tag_cost = {'date': [startDate, endDate]}
    for cost in total_account_cost_response["ResultsByTime"][0]['Groups']:
        no_tag_cost[cost['Keys'][0]] = float(cost['Metrics']['AmortizedCost']['Amount'])
    
    for techteam in tag_values:
        filter = {
            "And": [
                {'Not': {"Dimensions": {"Key": "RECORD_TYPE", "Values": RECORD_TYPE_VALUES}}}, 
                {'Tags': {'Key': TAG_NAME, 'Values': [techteam]}}
            ]
        }
        
        cost_response = get_cost(session, startDate, endDate, filter)
        
        for metrics in cost_response["ResultsByTime"]:
            start_date_obj = datetime.datetime.strptime(metrics['TimePeriod']['Start'], '%Y-%m-%d').date()
            end_date_obj = datetime.datetime.strptime(metrics['TimePeriod']['End'], '%Y-%m-%d').date()
            data = {
                'AccountId': account_id,
                'AccountName': AWS_ACCOUNT_DICT[account_id],
                'Date': start_date_obj,
                'startDate': start_date_obj,
                'endDate': end_date_obj,
                'techteam': techteam,
                'Service': '',
                'AmortizedCost': float(0),
            }
            for service in metrics['Groups']:
                data['Service'] = service['Keys'][0]
                data['AmortizedCost'] = float(service['Metrics']['AmortizedCost']['Amount'])
                no_tag_cost[service['Keys'][0]] -= float(service['Metrics']['AmortizedCost']['Amount'])
                total_cost += data['AmortizedCost']
                #logger.info(data)
                push_data_to_elasticsearch(data, startDate)
                
    for item in no_tag_cost.keys():
        if item != 'date':
            data = {
                'AccountId': account_id,
                'AccountName': AWS_ACCOUNT_DICT[account_id],
                'Date': datetime.datetime.strptime(no_tag_cost['date'][0], '%Y-%m-%d').date(),
                'startDate': datetime.datetime.strptime(no_tag_cost['date'][0], '%Y-%m-%d').date(),
                'endDate': datetime.datetime.strptime(no_tag_cost['date'][1], '%Y-%m-%d').date(),
                'techteam': "no-tag",
                'Service': item,
                'AmortizedCost': no_tag_cost[item],
            }
            #logger.info(data)
            push_data_to_elasticsearch(data, startDate)

def main():
    # Define start and end dates
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
