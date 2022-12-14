import requests, datetime, smtplib, os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Query prometheus to get data for past days
def query_prometheus(query, day=None):
  if day != None:
    response = requests.get(PROMETHEUS + '/api/v1/query',
    params={
      'query': query,
      'time': day + time_utc}).json()
    domain_dict = {}
    for item in response['data']['result']:
      domain_dict[item['metric']['request_host']] = [int(item['value'][1]), item['metric']['destination_workload']]
    return domain_dict
  else:
    response = requests.get(PROMETHEUS + '/api/v1/query',
    params={
      'query': query
      }).json()
    return round(float(response['data']['result'][0]['value'][1]), 1)

# Substract previous two time points values to get the number of hits between these two time points
def process_day_data(day_dict, previous_day_dict):
  domain_day_dict = {}
  for k, v in day_dict.items():
    domain_day_dict[k] = abs(v[0] - previous_day_dict[k][0]) if previous_day_dict.get(k) != None else abs(v[0] - 0)
    domain_day_dict[k] = [domain_day_dict[k] , day_dict[k][1]]
  return domain_day_dict

# Check if the passed dict is empty
def check_empty_dict(dict_to_check):
  return bool(dict_to_check)

# Get the number of pods running for input destination workload
def get_number_of_pods(destination_workload):
  if destination_workload:
    final_query = query_num_pods % (destination_workload)
    return int(query_prometheus(final_query))
  else:
    return 0  

# Get the cpu requests for input destination workload
def get_cpu_requests(destination_workload):
  final_query = query_cpu_requests % (destination_workload)
  return int((query_prometheus(final_query))*1000)

# Get the memory requests for input destination workload
def get_memory_requests(destination_workload):
  final_query = query_memory_requests % (destination_workload)
  return int((query_prometheus(final_query))*1000)

# Prepare email body for the services which has 0 hits in last 2 days
def set_email_body_with_zero_hits_in_last_two_days(report_no_transaction_last_two_days_dict):
    message = '<table style="border: black 0.5px;"><caption style="text-align:left; "><font color = "blue">Service Environments with 0 hits in last 2 days*</caption>'
    message += '<tr><th class="yellowcell">Service DNS</th><th class="yellowcell">Request-hits T-1</th> <th class="yellowcell">Request-hits T-2</th><th class="yellowcell">Request-hits Weekly</th><th class="yellowcell">Replicacount</th><th class="yellowcell">CPU Requests(in milliCPU) per replica</th><th class="yellowcell">Memory Requests(in Mi) per replica</th></tr>'
    if not check_empty_dict(report_no_transaction_last_two_days_dict):
      message += '</table>'
      return message
    # Total value holders
    total_cpu_requests = 0
    total_memory_requests = 0
    # Add row for each entry in pods_usage_report dictionary
    for key, value in report_no_transaction_last_two_days_dict.items():
        table_row = '<tr>'
        if value[3] != 'unknown':
          num_of_pods = get_number_of_pods(value[3])
          cpu_requests = get_cpu_requests(value[3])
          memory_requests = get_memory_requests(value[3])
          total_cpu_requests +=  num_of_pods*cpu_requests
          total_memory_requests +=  num_of_pods*memory_requests
          if num_of_pods > 0:
            table_row += '<td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td>'.format(key, value[0], value[1], value[2], num_of_pods, cpu_requests, memory_requests)
        else:
          table_row += '<td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td>'.format(
                  key, value[0], value[1], value[2], 'NA', 'NA', 'NA')
        table_row += '</tr>'
        message += table_row
    # Create last row with total of cpu requests and memory requests
    last_row = '<tr><td colspan="5" ><b>Total</b></td><td>{}</td><td>{}</td></tr>'.format(total_cpu_requests, total_memory_requests)
    message += last_row
    # End table tag
    message += '</table>'
    return message

# Prepare email body for the services which has le 100 hits in last 1 week
def set_email_body_with_le_100_hits_in_last_one_week(report_no_transaction_last_week_dict):
    message = '<table style="border: black 0.5px;"><caption style="text-align:left; "><font color = "red">Service Environments with less than 100 hits in last 1  week*</caption>'
    message += '<tr><th class="redcell">Service DNS</th><th class="redcell">Request-hits T-1</th> <th class="redcell">Request-hits T-2</th><th class="redcell">Request-hits Weekly</th><th class="redcell">Replicacount</th><th class="redcell">CPU Requests(in milliCPU) per replica</th><th class="redcell">Memory Requests(in Mi) per replica</th></tr>'
    if not check_empty_dict(report_no_transaction_last_week_dict):
      message += '</table>'
      return message
    # Total value holders
    total_cpu_requests = 0
    total_memory_requests = 0
    # Add row for each entry in pods_usage_report dictionary
    for key, value in report_no_transaction_last_week_dict.items():
        table_row = '<tr>'
        if value[3] != 'unknown':
          num_of_pods = get_number_of_pods(value[3])
          cpu_requests = get_cpu_requests(value[3])
          memory_requests = get_memory_requests(value[3])
          total_cpu_requests +=  num_of_pods*cpu_requests
          total_memory_requests +=  num_of_pods*memory_requests
          if num_of_pods > 0:
            table_row += '<td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td>'.format(key, value[0], value[1], value[2], num_of_pods, cpu_requests, memory_requests)
        else:
          table_row += '<td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td>'.format(
                  key, value[0], value[1], value[2], 'NA', 'NA', 'NA')
        table_row += '</tr>'
        message += table_row
    # Create last row with total of cpu requests and memory requests
    last_row = '<tr><td colspan="5" ><b>Total</b></td><td>{}</td><td>{}</td></tr>'.format(total_cpu_requests, total_memory_requests)
    message += last_row
    # End table tag with body and html tag
    message += '</table>'
    return message

# Prepare email body for the services which are least used in last 1 week
def set_email_body_with_least_ten_used_in_last_one_week(report_least_ten_transaction_last_week_dict):
    message = '<table style="border: black 0.5px;"><caption style="text-align:left; "><font color = "green">Top 10 Service Environments with least usage in last 1  week*</caption>' 
    message += '<tr><th class="greencell">Service Name</th><th class="greencell">Request-hits T-1</th> <th class="greencell">Request-hits T-2</th><th class="greencell">Request-hits Weekly</th><th class="greencell">Replicacount</th><th class="greencell">CPU Requests(in milliCPU) per replica</th><th class="greencell">Memory Requests(in Mi) per replica</th></tr>'
    if not check_empty_dict(report_least_ten_transaction_last_week_dict):
      message += '</table>'
      return message
    # Total value holders
    total_cpu_requests = 0
    total_memory_requests = 0
    # Add row for each entry in pods_usage_report dictionary
    for key, value in report_least_ten_transaction_last_week_dict.items():
        table_row = '<tr>'
        if value[3] != 'unknown':
          num_of_pods = get_number_of_pods(value[3])
          cpu_requests = get_cpu_requests(value[3])
          memory_requests = get_memory_requests(value[3])
          total_cpu_requests +=  num_of_pods*cpu_requests
          total_memory_requests +=  num_of_pods*memory_requests
          if num_of_pods > 0:
            table_row += '<td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td>'.format(key, value[0], value[1], value[2], num_of_pods, cpu_requests, memory_requests)
        else:
          table_row += '<td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td>'.format(
                  key, value[0], value[1], value[2], 'NA', 'NA', 'NA')
        table_row += '</tr>'
        message += table_row
    # Create last row with total of cpu requests and memory requests
    last_row = '<tr><td colspan="5" ><b>Total</b></td><td>{}</td><td>{}</td></tr>'.format(total_cpu_requests, total_memory_requests)
    message += last_row
    # End table tag with body and html tag
    message += '</table>'
    return message

# Define send mail using formatted HTML Table
def send_email(toAddr, cc, subject, message):
    msg = MIMEMultipart(
        "alternative", None, [MIMEText(message, 'html')])
    msg["Subject"] = subject
    msg["From"] = source
    msg["To"] = toAddr
    msg["Cc"] = cc
    # Set recipients
    rcpt = [toAddr] + [cc]
    server = smtplib.SMTP(smtp_server, smtp_port)
    try:
        server.sendmail(source, rcpt, msg.as_string())
        print(f"Sending message to {toAddr} with cc to {cc}: \n {message}")
    except Exception as e:
        print(e)
    finally:
        server.quit()


# Mail variables
source = os.environ.get('source','lending.notification@paytm.com')
smtp_server = os.environ.get('smtp_server','postfix.lending.local')
smtp_port = os.environ.get('smtp_port','25')
destination =  os.environ.get('destination','ronak.khandelwal@paytm.com')
cc = os.environ.get('cc','')
subject = os.environ.get('subject','Unused Service Environments report')

# Time value variables
time_utc = os.environ.get('time_utc','T18:29:00.000Z')
yesterday = (datetime.datetime.today() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
day_before_yesterday = (datetime.datetime.today() - datetime.timedelta(days=2)).strftime('%Y-%m-%d')
two_day_before_yesterday = (datetime.datetime.today() - datetime.timedelta(days=3)).strftime('%Y-%m-%d')
week_before_yesterday = (datetime.datetime.today() - datetime.timedelta(days=8)).strftime('%Y-%m-%d')

# PROMETHEUS = 'https://thanos-query-stage-k8s.lending.paytm.com'
PROMETHEUS = os.environ.get('PROMETHEUS','http://10.167.1.38:9090')

query_num_requests = 'sort(sum(istio_requests_total{job="envoy-stats", request_operation!~"actuator.*|/", request_host!~"elk.*|thanos.*|apm-server-int.lending.paytm.com|es-stage.lending.paytm.com", request_host=~".*-.*.lending.paytm.com"}) by (request_host, destination_workload))'

query_num_pods = """sum(kube_pod_status_phase{ pod=~"%s.*", k8scluster="lending_staging_eks", phase="Running"})"""

query_cpu_requests = """avg(kube_pod_container_resource_requests_cpu_cores{ pod=~"%s.*", k8scluster="lending_staging_eks"})"""
query_memory_requests = """avg(kube_pod_container_resource_requests_memory_bytes{pod=~"%s.*", k8scluster="lending_staging_eks"}) / 1024 / 1024 / 1024"""

domain_yesterday_dict = query_prometheus(query_num_requests, yesterday)
domain_day_before_yesterday_dict = query_prometheus(query_num_requests, day_before_yesterday)
domain_two_day_before_yesterday_dict = query_prometheus(query_num_requests, two_day_before_yesterday)
domain_week_before_yesterday_dict = query_prometheus(query_num_requests, week_before_yesterday)

domain_previous_day_dict = process_day_data(domain_yesterday_dict, domain_day_before_yesterday_dict)
domain_previous_to_previous_day_dict = process_day_data(domain_day_before_yesterday_dict, domain_two_day_before_yesterday_dict)
domain_previous_week_dict = process_day_data(domain_yesterday_dict, domain_week_before_yesterday_dict)

report_dict_keys = list(set([*domain_yesterday_dict, *domain_day_before_yesterday_dict, *domain_two_day_before_yesterday_dict, *domain_week_before_yesterday_dict]))
report_dict = dict.fromkeys(report_dict_keys, None)

# Due to prometheus instability, there are cases when weekly = 0 but T-1 or T-2 != 0
# There is a tweak here for weekly value, if value is not present, have set it to sum of last 2 days.
for key in report_dict.keys():

  # Destination workload
  domain_destination_workload = domain_previous_day_dict[key][1] if domain_previous_day_dict.get(key) != None else ('')
  if not (domain_destination_workload and domain_destination_workload != 'unknown'):
    domain_destination_workload = domain_previous_to_previous_day_dict[key][1] if domain_previous_to_previous_day_dict.get(key) != None else ('')
  if not (domain_destination_workload and domain_destination_workload != 'unknown'):
    domain_destination_workload = domain_previous_week_dict[key][1] if domain_previous_week_dict.get(key) != None else ('')

  # Number of requests
  domain_previous_day_value = domain_previous_day_dict[key][0] if domain_previous_day_dict.get(key) != None else (0)
  domain_previous_to_previous_day_value = domain_previous_to_previous_day_dict[key][0] if domain_previous_to_previous_day_dict.get(key) != None else (0)
  domain_previous_week_value = domain_previous_week_dict[key][0] if domain_previous_week_dict.get(key) != None else (0)
  domain_yesterday_value = domain_yesterday_dict[key][0] if domain_yesterday_dict.get(key) != None else (0)
  domain_day_before_yesterday_value = domain_day_before_yesterday_dict[key][0] if domain_day_before_yesterday_dict.get(key) != None else (0)
  domain_two_day_before_yesterday_value = domain_two_day_before_yesterday_dict[key][0] if domain_two_day_before_yesterday_dict.get(key) != None else (0)

  if domain_previous_week_value > (domain_previous_day_value+domain_previous_to_previous_day_value):
    report_dict[key] = [domain_previous_day_value, domain_previous_to_previous_day_value, domain_previous_week_value, domain_destination_workload]
  elif domain_previous_day_value+domain_previous_to_previous_day_value > 0:
    report_dict[key] = [domain_previous_day_value, domain_previous_to_previous_day_value, domain_previous_day_value+domain_previous_to_previous_day_value, domain_destination_workload]
  elif domain_yesterday_value > 0:
    report_dict[key] = [domain_previous_day_value, domain_previous_to_previous_day_value, domain_yesterday_dict.get(key, 0), domain_destination_workload]
  elif domain_day_before_yesterday_value > 0:
    report_dict[key] = [domain_previous_day_value, domain_previous_to_previous_day_value, domain_day_before_yesterday_dict.get(key, 0), domain_destination_workload]
  elif domain_two_day_before_yesterday_value > 0:
    report_dict[key] = [domain_previous_day_value, domain_previous_to_previous_day_value, domain_two_day_before_yesterday_dict.get(key, 0), domain_destination_workload]
  else:
    report_dict[key] = [domain_previous_day_value, domain_previous_to_previous_day_value, domain_previous_week_value, domain_destination_workload]

# Get all keys for which there has been no transaction in last week
report_no_transaction_last_week_dict = {key: value for (key, value) in report_dict.items() if value[1][2] < 100 }
report_no_transaction_last_week_dict = dict(sorted(report_no_transaction_last_week_dict.items(), key=lambda x: x[1][2]))

# Remove entries for which there is a negative value coming for weekly figures
# This indicates data might have broken in prometheus
report_dict = dict(filter(lambda x: x[1][2] >= 0, report_dict.items()))

# Get all keys for least ten used in last week
report_least_ten_transaction_last_week_dict = dict(sorted(report_dict.items(), key=lambda x: x[1][2])[:10])

report_dict = dict(sorted(report_dict.items()))

# Get all keys for which there has been no transaction in last 2 days
report_no_transaction_last_two_days_dict = {key: value for (key, value) in report_dict.items() if value[0] + value[1] == 0 }
report_no_transaction_last_two_days_dict = dict(sorted(report_no_transaction_last_two_days_dict.items(), key=lambda x: x[1][2]))
   
# Generate HTML for mail
html = """
<html>
<head>
<style type="text/css" media="screen">
table, th, td {
  border: 1px solid black;
  border-collapse: collapse;
}
th.yellowcell{
 background-color: yellow;
 }
 th.redcell{
 background-color: brown;
 }
 th.greencell{
 background-color: green;
 }
</style>
</head>
<body>
%s
<br>
<br>
%s
<br>
%s
<br>
%s 
<br>
<br>
%s
<br>
%s
<br>
<br> 
</body></html>""" % (
  '* Tables are sorted on "Request-hits Weekly" column',
  set_email_body_with_zero_hits_in_last_two_days(report_no_transaction_last_two_days_dict), 
  set_email_body_with_le_100_hits_in_last_one_week(report_no_transaction_last_week_dict), 
  set_email_body_with_least_ten_used_in_last_one_week(report_least_ten_transaction_last_week_dict),
  'Scale down service environment: - https://jenkins.lending.paytm.com/job/Kubernetes/job/lending-distribution/job/Scale_Down_Service_Environment/',
  'Scale up service environment: - https://jenkins.lending.paytm.com/job/Kubernetes/job/lending-distribution/job/Scale_Up_Service_Environment/'
  )

# Send mail
send_email(destination, cc, subject, html)
