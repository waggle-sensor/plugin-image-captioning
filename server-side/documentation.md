# Slack Bot Server Communications and the Code Underneath

The folder is compromised of four section: 
1. **Python Files**
    - userToServer.py
        - takes in Slack messaging, outputs data to user_data.json
    - serverToUser.py
        - takes in cloud data and json data, outputs data to Slack
2. **Bash Scripts**
    - inotify-install.sh
        - runs a script that installs a feature that can listen to changes in json files
    - makejobs.sh
        - used to deploy the plugin through sesctl and make a yaml file. It also logs the node in relation to the job#  
3. **json Files**
    - sageinfo.json
        - lots of information about the nodes
    - user_data.json
        - contains all of the information about the slack user and what they need. It is formatted in the following way:
            - node
                - description
                    - channel 
                        - user
        - any of these can be added to, so for example, if there were two users looking for the same information in one channel, there would be two users inside of the channel field. 
4. **Docker files**
    - dockerfile 
    - docker-compose.yml
        - I am using docker-compose so that there can be multiple programs running and working together with a shared docker volume.
--------------------------------------------------------------------
## How to Run:
### Slack-Side
```
#To ask for an image from the bot, say something like

@Sage Search take a photo on W023

# To ask for a feature of an image, say something like

@Sage Search tell me when there are trees on W058

#Be sure to stick @Sage Search at the front, otherwise it will not work properly
```
```
#First go to the directory of the docker-compose file and run
sudo docker-compose up -d

# While the container is running, you can see the logs with

sudo docker-compose logs

#To look inside the container run:
sudo docker ps  
#this gets the container ID, then do: 
sudo docker exec -it CONT_ID /bin/bash


## When you are ready to bring the containers down, run:
sudo docker-compose down

#I also like to make sure the volume is down with 
sudo docker-compose down -v
#Although it should go down automatically
```
--------------------------------------------------------------------
## What does the Workflow Look Like? (simple edition)
#### Workflow for just an image being sent back

1. The user sends a message in Slack such as "@Sage Search, send me an image from W023"
2. **userToServer.py**, understanding the Slack API for the Waggle Workspace, hears the user request. It looks kind of like:
```
{'token': '', 'team_id': '', 'api_app_id': '', 'event': {'user': '', 'type': 'app_mention', 'ts': '', 'client_msg_id': '', 'text': '<@ID> send me an image from W023', 'team': '', 'blocks': [{'type': 'rich_text', 'block_id': 'uPlwB', 'elements': [{'type': 'rich_text_section', 'elements': [{'type': 'user', 'user_id': ''}, {'type': 'text', 'text': ' send me an image from W023'}]}]}], 'channel': '', 'event_ts': ''}, 'type': 'event_callback', 'event_id': '', 'event_time': , 'authorizations': [{'enterprise_id': None, 'team_id': '', 'user_id': '', 'is_bot': True, 'is_enterprise_install': False}], 'is_ext_shared_channel': False, 'event_context': ''}
```
- Yikes that is a lot! 
 - also all of the secret information is redacted just in case :)

 3. The slack json chunk is parsed out to get the userID, channelID, and text

 4. Ollama is running on a seperate container on the server (on localhost:11433). It is using Gemma2. I promt it as follows:
    - botReply = runOllama(f"Please only reply with what the user wants to use, what the user is searching for (if they are searching for anything) and where the user wants to use the plugin. Reply specifically with what the user wants to use, what the user is searching for, and where the user is looking for it all on new lines. If the user asked: Tell me when you see a car in Chicago. Print plugin-image-capturing, then on a new line, print car, then on a newline print Chicago. If the user asks: Capture an image on W026. Print plugin-image-sampler, then, on a newline, print null, then on a newline, print W026. If the user asks: Let me know when there is a dog on the street in W0B5. print plugin-image-capturing, then on a newline, print dog, then on a newline, print W0B5. If the user says something where you do not know the location. Explain what went wrong. Perform like that. If you don't understand what the user is saying, or you believe that the plugin is not plugin-image-capturing or plugin-image-sampler, say why. This is very important if you think there is no location to instead say your reasoning on why the request cannon be fulfilled.  Now go ahead with this one: {message_text}")
        - It is not a great prompt, but it seems to work. 
5. With this prompt, Ollama gives the plugin the user wants, word that the user is looking for and the location they are looking for it at.
    - For image-sampler, the word is "null" since the person is just looking to capture an image
    - If Ollama doesn't understand the prompt, it will explain why
6. The location is checked by **sageinfo.json**. If it is a node, nothing happens, but if it is a location, an list of nodes in that location is made and returned. 
    - Ex. If the location was IL. The function would return all of the nodes in Illinois as a list. 
6. **user_data.json** is added to with the node, description, channel_ID, and user_ID. It looks something like this: 

```
{
    "plugin-image-captioner": {
        "W0B3": {
            "yellow": {
                "C07DJHV3E2F": [
                    "<@U076B5NUDR9>"
                    ]
            }
        }
    }
}
```
**Remember: These steps were done with userToServer.py, slack API, Ollama, sageinfo.json, and user_data.json**

---------
8. **makejobs.sh** has been listening for a change in user_data.json this whole time with the command 
```
inotifywait -m -e modify "$USER_DATA_JSON" 
```
 9. Now that the file is changed, **makejobs.sh** gets further activated. It checks for which node is new on the list and creates a YAML file with the name PLUGIN{NODE} where {NODE} is the node that has been put inside of the user_data.json file and PLUGIN is the name of the plugin (all one word). 

 10. The yaml is added to the folder jobyamls inside of the data directory. 
 11. The script then runs
 ```
 sesctl create --file-path YAML_FILE
 ```
 12.  As this happens, it listens for the return of what job ID is associated with the job. It then adds the node and the respective job_ID to **deployed.json**
        - For example {"W023": "2348"}

**This is the last we hear from makejobs.sh**

13. **serverToUser.py** has kept checking every 60 seconds if there is any new data on the specified nodes

14. When new photos come in from the cloud, the code checks if the data has a job associated with it. Then, it checks which user wanted data from that node. The program then downloads the image and sends it to the user. 

15. The request is then deleted from **user_data.json** and the job is removed using sesctl, in addition, the job information is deleted from **deployed.json**
    - This only happens if there is one user who requested something from that node. If there are two users and one hasn't gotten an image yet, only the first user is deleted and nothing else changes about the job or the json file. 

Congrats! In 15 steps you have learned the workflow of this process.

## What does the Workflow Look Like? (demo edition)

For the demo, the only thing that is allowed to be deployed is plugin-image-sampler. This is due to the speed at which it captures (good for demoing)

The job for plugin-image-captioner is fixed to a specific job ID so that there is less deployment wait time  

## To Do List 
#### In no particular order

- [ ] Set up a listener for data being generated by the jobs on the Sage Nodes so that 60 second calls do not have to happen (see step 13)
- [X] Use Gemma2 to check the user description with the image description (easy to implement but may take some prompt engineering for it to produce the right results)
- [O] Make the code more abstract so that other plugins can use this format. Right now the code is not friendly. 
    - getting there! 
- [ ] Add a safe and secure way for users to give their Sage Token so they can get images from the nodes they have access to 
    - Right now everything is under my account
    - When users are allowed to deploy on their own, this also means the jobs will not be under one account. This may cause a problem in the future since sesctl may be allowed only to delete jobs under the correct token. 
- [ ] Store the Slack API tokens in a safe way
    - Yikes
- [ ] Take this off of slack and put it on the website
    - Huge 
- [O] Get the capture-and-describe plugin to deploy in under 10 minutes
    - The workaround is having a job already deployed





