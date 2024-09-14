#!/bin/bash

# Set paths to your JSON files
USER_DATA_JSON="data/user_data.json"
DEPLOYED_JSON="data/deployed.json"  # Update this path
OUTPUT_DIR="data/jobyamls"            # Directory to save the YAML files

# Monitor the user_data.json file for changes
inotifywait -m -e modify "$USER_DATA_JSON" |
while read -r directory events filename; do
    echo "Detected changes in $USER_DATA_JSON"

    # Extract node names from user_data.json
    nodes=$(jq -r 'keys[]' "$USER_DATA_JSON")

    for node in $nodes; do
        # Check if the node exists in deployed.json
        if jq -e --arg NODE "$node" '.[$NODE]' "$DEPLOYED_JSON" > /dev/null; then
            echo "Node $node already exists in deployed.json. Skipping..."
        else
            echo "Node $node not found in deployed.json. Creating YAML file..."

            # Set the name and node variables
            NAME="ImageDeployOn$node"
            NODE="$node"

            # Create the YAML content
            YAML_FILE="$OUTPUT_DIR/$NAME.yaml"
            cat <<EOF > "$YAML_FILE"
name: $NAME
plugins:
  - name: image-sampler
    pluginSpec:
      image: registry.sagecontinuum.org/theone/imagesampler:0.3.0
      args:
        - -stream
        - bottom_camera
nodes:
  $NODE:
scienceRules:
  - "schedule(image-sampler): cronjob('image-sampler', '* * * * *')"
successCriteria:
  - WallClock(1d)
EOF

            echo "YAML file $NAME.yaml created for node $NODE."

            # Run sesctl create command
            CREATE_OUTPUT=$(sesctl create --file-path "$YAML_FILE")
            JOB_ID=$(echo "$CREATE_OUTPUT" | jq -r '.job_id')
            echo "Job created with ID: $JOB_ID"

            # Run sesctl submit command
            SUBMIT_OUTPUT=$(sesctl submit --job-id "$JOB_ID")
            echo "Job $JOB_ID submitted."

            # Update deployed.json with the new node and job_id
            jq --arg NODE "$NODE" --arg JOB_ID "$JOB_ID" '.[$NODE] = $JOB_ID' "$DEPLOYED_JSON" > "$DEPLOYED_JSON.tmp" && mv "$DEPLOYED_JSON.tmp" "$DEPLOYED_JSON"
            echo "Node $NODE with Job ID $JOB_ID added to deployed.json."
        fi
    done
done