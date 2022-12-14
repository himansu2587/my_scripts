#!/bin/bash

#find out the private ip from instance id
private_ip=$(aws ec2 describe-instances \
	--instance-ids $instance_id \
	--query 'Reservations[0].Instances[0].NetworkInterfaces[0].PrivateIpAddress' \
	--output text \
	--region ap-south-1)
tg_list=()
echo "Instance id: $instance_id"
echo "Private ip: $private_ip"

#store all target group ARNS in the account
tg_arns=$(aws elbv2 describe-target-groups --region ap-south-1 --query TargetGroups[*].TargetGroupArn --output text)
#Loop through all target groups
for tg_arn in $tg_arns
do
	#find out all the attached targets in the target group
	targets=$(aws elbv2 describe-target-health --target-group-arn ${tg_arn}  --query 'TargetHealthDescriptions[*].Target.Id' --output text)
	#Loop through all the targets attached to the target group and match them with the provided instrance id and private ip
	for target in $targets
	do
		if [ "$instance_id" == "$target" ]
		then
			tg_list+=($tg_arn)
		elif [ "$private_ip" == "$target" ]
		then
			tg_list+=($tg_arn)
		fi
	done
done
echo "List of target groups containing this instance as target:"
printf '%s\n' "${tg_list[@]}"
