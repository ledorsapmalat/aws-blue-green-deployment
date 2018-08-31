#!/bin/bash
# Sample Calls

# Initial

# Blue
./create-parameter-store.sh etender-staging /prod/prod_elb blue-green-elb-dev1 ap-southeast-2
./create-parameter-store.sh etender-staging /prod/prod_asg replatform-dev-dev1-web-asg ap-southeast-2

# Green
./create-parameter-store.sh etender-staging /prod/temp_elb blue-green-temp-elb-green ap-southeast-2
./create-parameter-store.sh etender-staging /prod/temp_asg replatform-dev-green-web-asg ap-southeast-2

# current
./create-parameter-store.sh etender-staging /prod/deployment/current_state blue ap-southeast-2
