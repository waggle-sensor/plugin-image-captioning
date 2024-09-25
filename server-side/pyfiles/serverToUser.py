import os
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import requests
import sage_data_client 
from PIL import Image 
import io 
import json
import time
import subprocess

USER_DATA = '/app/data/user_data.json' 
DEPLOYED_PATH = '/app/data/deployed.json'
SAGE_USERNAME = os.environ["SAGE_USERNAME"]
SAGE_USERTOKEN = os.environ["SAGE_USERTOKEN"]


app = App(token=os.environ["SLACK_BOT_TOKEN"])


#used for demo
JOB_ID = "image-captioner-2426"
#######

'''
This code has two primary activities: listening for new data, and sending data for the user

Slack listens by never terminating. 
getData() runs by requesting data when it can. 

Because of Slack, the script never actually finishes. So I can't have the script run, stop, and run again. 

Since the code never ends, and I need some code to run multiple times while the code never ends,
the only way to get around that is to have one massive function for everything
and then run it every 60 seconds

In another version, it may be nice to handle those two activities in seperate code (good design philosophy?),
but it is much easier to do it in one

my vision is "slack.py" that just does the listening and talking. 
and then a few backend scripts that handle the other things

These problems *should* solve themselves when we migrate to the website 



'''
OLLAMA_SERVER = "http://localhost:11433/api/generate"
#This is how Gemma2 is accessed
def runOllama(prompt):

    # Define the data payload as a dictionary
    #the model we have is gemma2
    #Use the prompt as the thing to ask the LLM
    payload = {
        "model": "gemma2:latest",
        "prompt": prompt
    }

    # Send the POST request to the server
    response = requests.post(OLLAMA_SERVER, json=payload)

    # Check if the request was successful
    #and gets the text
    if response.status_code == 200:
        print("Running Gemma2")

        #The text is generated word by word so each word has to be captured and stored
        response_text = []
        lines = response.text.strip().split('\n')
        for i, line in enumerate(lines):
            json_response = json.loads(line)
            if 'response' in json_response:
                response_text.append(json_response['response'])
    #join the entire response into one string for usability
        botReply = (''.join(response_text))
        return botReply
    else:
        botReply = ("ERROR: Could not connect to server")

def main():
    #Get the JSON file if it exists. Otherwise make something that would be JSONable 
    with open(USER_DATA, 'r') as f:
        try:
            user_data = json.load(f)
        except Exception as e:
            user_data = {}

    #takes in img url, login session, and where the img should be stored
    #basically downloads one image at a time and names it tmp.jpg so that Slack can send it
    #Someone please let me know if I can do this without downloading the image. Seems unneeded
    #TODO do this without having to download the image. Is unneeded

    def process_file_from_url(url):
        try:
            with requests.Session() as session:
                #get username and usertoken for verification
                session.auth = (SAGE_USERNAME, SAGE_USERTOKEN)
                response = session.get(url.strip())
                response.raise_for_status()  # Raise HTTP error for issues
                # Create an in-memory file-like object
                file_content = io.BytesIO(response.content)
                print(f'Successfully downloaded and opened file from {url}')
                file_content.seek(0)  # Reset file pointer to the start (I don't really understand this)
                
                try:
                    #for debugging
                    print(file_content)

                    #lame name but fine
                    #TODO make this name match the name on the SAGE website. (very low priority)
                    filename= "tmp.jpg"

                    # Open and process the image with Pillow
                    image = Image.open(file_content)
                    
                    # Get the directory where the script is located
                    script_dir = os.path.dirname(os.path.abspath(__file__))
                    
                    # Define the path where the image will be saved
                    file_path = os.path.join(script_dir, filename)
                    
                    # Save the image to the specified path
                    image.save(file_path)
                    return file_path
                

                except IOError:
                    print("The downloaded file is not a valid.")
                
                #if it ends up just being a file but not an image, still return it
                #shouldn't be needed but you never know.
                return file_content  # Return the in-memory file object


        except requests.exceptions.RequestException as e:
            print(f'Failed to download {url}: {e}')
            return None

    #sage data client stuff.
    #Gets all of the info from the plugin that is needed
    #We are abstracting! the variable "plugin" has replaced a hard-coded plugin :)
        #UPDATE: now there is less abstraction for the demo. I don't think this is coded well. 
    def getData(plugin):
        if(plugin == "plugin-image-captioning:0.1.0"):
            df = sage_data_client.query(
            start="-1h", 
            filter={
                "plugin": f"{plugin}",
                "job": f"{JOB_ID}"
                }
            )
        else: 
            df = sage_data_client.query(
                start="-1h", 
                filter={
                    "plugin": f"{plugin}",
                    }
                )
        return df
    



    #image is open image
    #des is the description generated by Florence-2
    #user_description is what the user is looking for (ex. smoke)
    #channel ID is used to find the right place to send the message on SLACK
        #it will be the same place the user sent the request. Wherever that is. See userToServer.py to get more info
        #TODO send the user this information in their private slack channel regardless of where they send the initial message (lowish priority)
    #user_ID is the ID of the user who sent the message. User IDs look like "<@APOKF3POI>" (something along those lines)
    def sendToSlack(image, des, user_description, channel_ID, user_ID, botTalk):

        channel = channel_ID

        #files_upload_v2 sends the image
        app.client.files_upload_v2(
                    channels=channel,
                    file=image,
                )
  
        #chat_postMessage sends the description along with the other strings

        #checks if there is a user_description (image-sampler will not have this)
        if(user_description):
            app.client.chat_postMessage(
                channel=channel,
                text=f"{user_ID}\nFound a match for {user_description}\n{botTalk}\n{des}",
                )
        else:
            app.client.chat_postMessage(
                channel=channel,
                text=f"{user_ID}\nCaptured an image",
                )

        #Descriptions are sent faster than images. This makes it hard to know what description goes to what image
        #5 seconds is enough time to send each pair and have them together in the app
        #TODO Instead of time.sleep, have a listener that allows program continuation after the image is verfified to be in the app
        time.sleep(5)

    #this is only used if the the matching image timestamp is not above or below the description timestamp. 
    def find_upload_by_timestamp(timestamp, exclude_index):
        # Filter the DataFrame for matching rows
        matches = imgs_and_des[(imgs_and_des['timestamp'] == timestamp) & (imgs_and_des['name'] == 'upload')]
        
        # Check if exclude_index exists in the filtered DataFrame and drop it if present
        if exclude_index in matches.index:
            matches = matches.drop(index=exclude_index)
        
        # Return the value if matches are found, else return None
        return matches['value'].iloc[0] if not matches.empty else None

    def delete_job_entry(job_id, file_path=DEPLOYED_PATH):
        try: 
            # Load the deployed.json file
            with open(file_path, 'r') as f:
                deployed_data = json.load(f)

            to_delete = None
            
            # Search for the job_id in deployed_data
            for key, value in deployed_data.items():
                if value == job_id:
                    to_delete = key
                    break
            
            if to_delete:
                # Remove the job using sesctl and delete the associated YAML file
                subprocess.run(['sesctl', 'rm', '--force', job_id], check=True)
                yaml_file_path = f'data/jobyamls/{to_delete}.yaml'
                subprocess.run(['rm', yaml_file_path], check=True)
                
                # Remove the entry from the deployed.json data
                del deployed_data[to_delete]
                print(f"Deleted entry: '{to_delete}' with Job ID: '{job_id}'")

                # Save the updated deployed.json data
                with open(file_path, 'w') as f:
                    json.dump(deployed_data, f, indent=4)
            
            else:
                print(f"No entry found for Job ID: {job_id}")

        except subprocess.CalledProcessError as e:
            print(f"Error while running subprocess: {e}")
        
        except Exception as e:
            print(f"An error occurred: {e}")

#removes user information from JSON file after the image and description is sent
    def delete_user_id(plugin, meta_vsn, user_description, channel_id, user_id, file_path=USER_DATA):
        # Step 1: Load the JSON data
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        # Step 2: Navigate through the structure and remove the user_id
        if plugin in data: 
            if meta_vsn in data[plugin]:
                if user_description in data[plugin][meta_vsn]:
                    if channel_id in data[plugin][meta_vsn][user_description]:
                        user_list = data[plugin][meta_vsn][user_description][channel_id]

                        if user_id in user_list:
                            user_list.remove(user_id)
                            print(f"Removed user ID: {user_id}")

                        # Step 3: Check if the channel_id has any users left
                        if not user_list:
                            del data[plugin][meta_vsn][user_description][channel_id]
                            print(f"Deleted empty channel ID: {channel_id}")

                        # Step 4: Check if the user_description has any channel_ids left
                        if not data[plugin][meta_vsn][user_description]:
                            del data[plugin][meta_vsn][user_description]
                            print(f"Deleted empty user description: {user_description}")

                        # Step 5: Check if the meta_vsn has any user_descriptions left
                        if not data[plugin][meta_vsn]:
                            del data[plugin][meta_vsn]
                            print(f"Deleted empty meta.vsn: {meta_vsn}")
                        
                        if not data[plugin]:
                            del data[plugin]
                            print(f"Deleted empty meta.vsn: {plugin}")

        # Step 6: Save the updated JSON data back to the file
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=5)

    #selects the time and img link for further processing
    #I told chatGPT to make the code with as few lines as possible. It does make it a little hard to read
    #Basically checks if the new plugin data matches with any user request. If it does, data is sent to the user
    try:  
        with open(USER_DATA, 'r') as f:
            data = json.load(f)
        with open(DEPLOYED_PATH, 'r') as f:
            deployed_data = json.load(f)
        if data:
            #if there is data, look at the plugins
            for plugin in data.keys():
                df = getData(plugin)
                #if the plugin is this, make sure it has the required columns
                if(plugin == "registry.sagecontinuum.org/theone/imagesampler:0.3.0"):
                    required_columns = ["name", "meta.vsn", "value", "meta.job"]
                    missing_columns = [col for col in required_columns if col not in df.columns]
                    if not missing_columns:
                        imgs_and_des = df[required_columns].dropna()
                        
                        # Process the DataFrame
                        #take the data and check each part individually
                        #for image upload, the name is upload. 
                        for i, row in imgs_and_des.iterrows():
                            if row['name'] == 'upload' and str(row['meta.job']).split("-")[-1] in deployed_data.values():
                            
                            #get the node (ex. W023)
                                meta_vsn = row['meta.vsn']


                                job = str(row['meta.job']).split("-")[-1] #just gets job ID

                                

                                #if the node is found in a request continue 
                                if plugin in user_data:
                                    if meta_vsn in user_data[plugin]:
                                        for user_description, channels in user_data[plugin][meta_vsn].items():
                                            des = ""
                                            upload_value = imgs_and_des['value'][i]
                                            print(i)
                                            for channel_ID, user_IDs in channels.items():
                                                for user_ID in user_IDs:
                                                    print(f"Channel ID: {channel_ID}, User ID: {user_ID}, Upload Value: {upload_value}")
                                                    image = process_file_from_url(upload_value)
                                                    sendToSlack(image, des, user_description==False, channel_ID, user_ID, botTalk="")
                                                    delete_user_id(plugin, meta_vsn, user_description, channel_ID, user_ID)   
                                                    delete_job_entry(job)
                                                    #I apologize for bad coding practices
                                                    break
                                                break
                                            break
                                        break
                                                    
                            else:
                                print(f"Missing columns: {missing_columns}")
                if (plugin == "registry.sagecontinuum.org/yonghokim/plugin-image-captioning:0.1.0"):
                    required_columns = ["timestamp", "name", "value", "meta.vsn", "meta.job"]
                    missing_columns = [col for col in required_columns if col not in df.columns]

                    if not missing_columns:
                        imgs_and_des = df[required_columns]
                            
                        # Process the DataFrame
                        #take the data and check each part individually
                        for i, row in imgs_and_des[imgs_and_des['name'] == 'env.image.description'].iterrows():
                            #get the node (ex. W023)
                            meta_vsn = row['meta.vsn']
                            #if the node is found in a request continue 
                            if plugin in user_data:
                                if meta_vsn in user_data[plugin]:
                                    #check all of the user descriptions. Then channels are the next iteration so keep that just in case
                                    for user_description, channels in user_data[plugin][meta_vsn].items():
                                        #if something in the user description is in the image description, continue
                                        #TODO use a better search method than just "in"
                                        bot_reply = runOllama(f"The user is looking for {user_description} a possible match for the search is {row['value']} is this a good match for the user? Reply with your reasoning along with a newline and then yes or a newline and then no")
                                        answer = bot_reply.split()[-1]
                                        print(answer)
                                        botTalk = ' '.join(bot_reply.split()[:-1]) if len(bot_reply.split()) > 1 else ''
                                        if answer == "yes":
                                            print("I am repeating since user_des in row value")
                                            #call the image description "des"
                                            des = row['value']
                                            #By this point we know an image has what the user wants. Now we have to find that image
                                            #First look one above and one below the description by timestamp.
                                            #The timestamps should match so this will be easy to find. If it is not above or below, check everything else
                                            upload_value = (
                                                imgs_and_des.iloc[i-1]['value'] if i > 0 and imgs_and_des.iloc[i-1]['timestamp'] == row['timestamp'] and imgs_and_des.iloc[i-1]['name'] == 'upload'
                                                else imgs_and_des.iloc[i+1]['value'] if i < len(imgs_and_des) - 1 and imgs_and_des.iloc[i+1]['timestamp'] == row['timestamp'] and imgs_and_des.iloc[i+1]['name'] == 'upload'
                                                #this "else" function *can* return "None" which then just stops the process
                                                else find_upload_by_timestamp(row['timestamp'], i)
                                                
                                            )
                                            #if the image is found, open it and send it!
                                            if upload_value:
                                                for channel_ID, user_IDs in channels.items():
                                                    for user_ID in user_IDs:
                                                        print(f"Timestamp: {row['timestamp']}, Channel ID: {channel_ID}, User ID: {user_ID}, Upload Value: {upload_value}")
                                                        image = process_file_from_url(upload_value)
                                                        sendToSlack(image, des, user_description, channel_ID, user_ID, botTalk)
                                                        delete_user_id(plugin, meta_vsn, user_description, channel_ID, user_ID)   
                                                        return
                    else:
                        print(f"Missing columns: {missing_columns}")  


    #say if anything goes wrong 
    except Exception as e:
        print("ERROR ", e)

while True:
    main()
    time.sleep(60)

if __name__ == "__main__":
    # Get the app token from the environment variable
    #see README if needed
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()




#TODO have the user queries be deleted after a certain amount of time if not found