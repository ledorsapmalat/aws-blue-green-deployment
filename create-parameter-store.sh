#!/bin/bash

if [ $# -lt 3 ]
  then
    echo "*********************************************************"
    echo "* ERROR: Specify Parameter Store to create.             *"
    echo "* USAGE: create-parameter-store <KEY> <VALUE> <REGION>  *"
    echo "*********************************************************"
    exit 1
fi

aws --profile $1 ssm put-parameter --name $2 --type String --value $3 --region $4 --overwrite
