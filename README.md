# mqtt-sql-proxy
Proxy between MQTT and SQL

1. Install Mosquitto MQTT Publish/Subscribe package on running server:
```
sudo apt install mosquitto
```

2. Install mysql database libraries for the machine running the code:
```
sudo apt install python3-pymysql
```

3. Install Paho MQTT libraries for Python3 (Ubuntu 18.04):

```
sudo apt install python3-paho-mqtt
```

You send MQTT messages from server through command line typing:
```
mosquitto_pub -h <ip> -p <port> -q <qos-level> -t <wanted topic path> -m <message> -r
```
Subscriping to a topic:
```
mosquitto_sub -h <hostname> -p <port> -v -t <topic>
```
Removing all the mqtt messages in all topics:
```
sudo service mosquitto stop
sudo rm /var/lib/mosquitto/mosquitto.db
sudo service mosquitto start
```
