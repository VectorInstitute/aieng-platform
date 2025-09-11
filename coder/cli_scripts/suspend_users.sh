#!/bin/bash

# Log in to coder
coder login https://agent-bootcamp.vectorinstitute.ai

# Get a list of all usernames and store it in an array
mapfile -t users < <(coder users list -c username | grep -v "USERNAME")

# Iterate of the list of users
for user in "${users[@]}"; do
    role=$(coder users show $user | grep "Roles:" | awk '{ print $2 }')
    # If role is not "Owner", suspend the user
    if [ "$role" != "Owner" ]; then
        # The <<< "" simulates the Enter button to confirm user suspension
        coder users suspend $user <<< ""
        echo "Suspended user: $user"
    else
        echo "Skipped owner: $user"
    fi
done

