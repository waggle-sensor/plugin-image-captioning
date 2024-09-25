#!/bin/bash

# Set paths to your JSON files
USER_DATA_JSON="data/user_data.json"
DEPLOYED_JSON="data/deployed.json"  # Update this path
OUTPUT_DIR="data/jobyamls"          # Directory to save the YAML files

# Monitor the user_data.json file for changes
inotifywait -m -e modify "$USER_DATA_JSON" |
while read -r directory events filename; do
    echo "Detected changes in $USER_DATA_JSON"

    # Extract plugin names from user_data.json
    plugins=$(jq -r 'keys[]' "$USER_DATA_JSON")

    for plugin in $plugins; do
        # Make the name shorter than the plugin (after the last slash and before the colon, removing any special characters)
        base=$(echo "$plugin" | sed -E 's|.*/([^:]+):.*|\1|')
        name=$(echo "$base" | sed 's/-//g')

        # Only proceed if the plugin matches the specified plugin
        if [[ "$plugin" == "registry.sagecontinuum.org/theone/imagesampler:0.3.0" ]]; then

            # Extract the node keys for the current plugin
            nodes=$(jq -r --arg plugin "$plugin" '.[$plugin] | keys[]' "$USER_DATA_JSON")
            
            for node in $nodes; do
                # Check if the node exists in deployed.json
                if jq -e --arg NAME "$name$node" '.[$NAME]' "$DEPLOYED_JSON" > /dev/null; then
                    echo "Name $name$node already exists in deployed.json. Skipping..."
                else
                    echo "Name $name$node not found in deployed.json. Creating YAML file..."

                    # Set the name and node variables
                    NAME="$name$node"
                    NODE="$node"

                    # Create the YAML content
                    YAML_FILE="$OUTPUT_DIR/$NAME.yaml"

                    cat <<EOF > "$YAML_FILE"

name: $NAME
plugins:
  - name: image-sampler
    pluginSpec:
      image: $plugin
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
                    echo "sesctl submit --job-id "$JOB_ID""
                    SUBMIT_OUTPUT=$(sesctl submit --job-id "$JOB_ID")
                    echo "Job $JOB_ID submitted."

                    # Update deployed.json with the new node and job_id
                    jq --arg NAME "$name$NODE" --arg JOB_ID "$JOB_ID" '.[$NAME] = $JOB_ID' "$DEPLOYED_JSON" > "$DEPLOYED_JSON.tmp" && mv "$DEPLOYED_JSON.tmp" "$DEPLOYED_JSON"
                    echo "$name$NODE with Job ID $JOB_ID added to deployed.json."
                fi
            done
        else
            # If the plugin is not the desired one, just print "Checking Plugin Data"
            echo "Checking Plugin Data"
        fi
    done
done
