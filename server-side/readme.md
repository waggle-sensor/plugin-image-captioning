##How to run this code:

IF not built
```
sudo docker build -t slackbot2 .
```


THEN when built
```
sudo docker-compose up -d
```

This should give you user to server and server to user code.

Try on "botcomms" and ask 
"@Sage Search find me x on y" (but replace x and y with something like "car" and "W023")

To end the program run 

```
sudo docker-compose down
```