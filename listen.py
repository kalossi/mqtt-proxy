#!/usr/bin/env python3
# -*-coding: utf-8-*-

# MQTT-SQL Proxy:
# listens to messages in mqtt topics and adds message data to right database

import sys
import pymysql as mysql
import paho.mqtt.client as mqtt
import argparse

# The callback for when the client receives a CONNACK response from the server.
def on_connect(mosq, obj, rc, x):
    client.subscribe(MQTT_TOPIC, 0)

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    # This is the Master Call for saving MQTT Data into DB
    # For details of "sensor_Data_Handler" function please refer "publish.py"
    topic = msg.topic
    print("MQTT Data Received...")
    print("Message: "+str(msg.topic)+" -m "+str(msg.payload))
    data = msg.payload
    if type(data) == bytes:
        #check if topic is too short
        if len(topic.split("/")) < 3:
            print("Topic path is invalid!")
            return False
        #valid topic
        elif len(topic.split("/")) >= 3:
            path = topic.replace(MQTT_PREFIX+"controllers/", "")

            print("cleaned topic: "+path)
            parse_topic(path, data)

    else:
        print("unacceptable message data type!")
        return False

#parses the necessary information from topics long form and saves them. returns those values in list
def parse_topic(top, data):
    data = data.decode()
    print(str(top.split("/")))
    serial = top.split("/")[0]
    idx_1 = top.split("/")[1]
    # controller version
    if idx_1 == "version":
        topic = top.split("/", 2)
        add_to_sys_update(serial, data)  #branching to sys update
    # update last connected time
    elif idx_1 == "connected":
        sql = """INSERT INTO connection_watchdog_and_profile
                 (id, sarjanumero, yhteystarkastelu, voimassa_oleva_profiili, muuttunut)
                 VALUES ('1', '%s', NOW(), '0', '0')
                 ON DUPLICATE KEY UPDATE yhteystarkastelu = NOW()""" % (serial)
        conn.cursor().execute(sql)
        conn.commit();
    # set all settings etc to changed when controller is rebooted so publish.py will send them
    elif idx_1 == "restart":
        cur = conn.cursor()
        cur.execute("UPDATE module_information SET muuttunut = 1 WHERE sarjanumero = %s AND muuttunut = 0" % (serial))
        cur.execute("UPDATE module_settings SET muuttunut = 1 WHERE sarjanumero = %s AND muuttunut = 0" % (serial))
        cur.execute("UPDATE profiles SET muuttunut = 1 WHERE sarjanumero = %s AND muuttunut = 0" % (serial))
        cur.execute("UPDATE rules SET muuttunut = 1 WHERE sarjanumero = %s AND muuttunut = 0" % (serial))
        cur.execute("UPDATE stock_prices SET changed = 1 WHERE controller = %s AND changed = 0" % (serial))
        conn.commit()
    # electricity settings
    elif idx_1 == "electricity":
        value = top.split("/",2)[2]
        topics = { "power/current": "152", "price/current": "151" }

        if value in topics.keys():
            nimi_id = topics[value]
            add_to_mod_val(serial, "0", data, nimi_id)  #branching to module_values
    # devices
    elif idx_1 == "devices":
        parts = top.split("/", 3)
        if len(parts) < 4:
            return
        value = parts[3]
        topics = {
            "connected": "0",
            "temperature/current": "1",
            "humidity/current": "3",
            "temperature/floor_sensor/current": "4",
            "errors": "49",
            "temperature/target": "50",
            "temperature/safety": "52",
        }
        module = parts[2]

        if value in topics.keys():
            nimi_id = topics[value]
            add_to_mod_val(serial, module, data, nimi_id)  #branching to module_values

        elif value == "type":
            sql = """UPDATE module_information SET tyyppi = %s WHERE sarjanumero = %s AND tunniste = %s""" % (data, serial, module)
            print(sql)
            conn.cursor().execute(sql)
            conn.commit()


def add_to_sys_update(serial, data):
    try:
        sql = "insert into system_update (sarjanumero, versio, muuttunut) values ('%s', '%s', '1') on duplicate key update versio = '%s'" % (serial, data, data)
        conn.cursor().execute(sql)
        conn.commit()
    except:
        print("connection from invalid controller, serial: %s" % (serial))

#add nimi_id, sarjanumero, arvo, muuttunut
def add_to_mod_val(serial, module, data, nimi_id):
    cur = conn.cursor()
    sql = """insert into module_values (nimi_id, module_id, sarjanumero, arvo, muuttunut)
             select "%s", id, sarjanumero, "%s", "1" from module_information where sarjanumero = %s and tunniste = %s 
             on duplicate key update arvo = %s""" % (nimi_id, data, serial, module, data)
    print(sql)
    cur.execute(sql)
    conn.commit()

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Listens to mqtt topic and changes module values in db accordingly", prog="listen.py", usage="proxy for listening mqtt topics to add values in sql")

    parser.add_argument("--mqtt-broker", help="MQTT broker host", default="localhost", type=str)
    parser.add_argument("--mqtt-port", help="MQTT broker host", default="1883", type=str)
    parser.add_argument("--mqtt-prefix", help="MQTT topic prefix", default="", type=str)
    parser.add_argument("--mqtt-user", help="MQTT username", default="", type=str)
    parser.add_argument("--mqtt-pass", help="MQTT password", default="", type=str)
    parser.add_argument("--mysql-host", help="MySQL server address", default="localhost", type=str)
    parser.add_argument("--mysql-port", help="MySQL server port", default="3306", type=str)
    parser.add_argument("--mysql-db", help="MySQL database to use", required=True, type=str) #mandatory!
    parser.add_argument("--mysql-user", help="MySQL username", default="", type=str)
    parser.add_argument("--mysql-pass", help="MySQL password", default="", type=str)

    args = parser.parse_args()
    print("connecting to mqtt broker with following settings:\n")
    MQTT_BROKER = str(args.mqtt_broker)
    MQTT_PORT = int(args.mqtt_port)
    MQTT_PREFIX = str(args.mqtt_prefix)
    MQTT_USER = str(args.mqtt_user)
    MQTT_PASS = str(args.mqtt_pass)
    MQTT_TOPIC=str(MQTT_PREFIX)+"controllers/#"
    print("MQTT broker: "+MQTT_BROKER)
    print("MQTT port: "+str(MQTT_PORT))
    print("MQTT topic: "+MQTT_TOPIC)
    print("MQTT user: "+MQTT_USER)

    print("connecting to database with following settings:\n")
    db_adress = str(args.mysql_host)
    db_user = str(args.mysql_user)
    db_password = str(args.mysql_pass)
    db_name = str(args.mysql_db)
    db_port = int(args.mysql_port)
    print("server: "+db_adress)
    print("port: "+str(db_port))
    print("user: "+db_user)
    print("db: "+db_name+"\n")

    conn = mysql.connect(   host=db_adress,    # your host, usually localhost
                        user=db_user,         # your username
                        passwd=db_password,  # your password
                        db=db_name)        # name of the data base

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(MQTT_BROKER, MQTT_PORT)

    # Blocking call that processes network traffic, dispatches callbacks and
    # handles reconnecting.
    # Other loop*() functions are available that give a threaded interface and a
    # manual interface.
    client.loop_forever()