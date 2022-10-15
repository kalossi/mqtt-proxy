#MQTT SQL Proxy:
#reads database, parses messages, publishes message to right topic for reading
#
#!/usr/bin/env python3
# -*-coding: utf-8-*-

# Notes:
# 1) check 0 ids

import pymysql as mysql
import paho.mqtt.client as mqtt
import argparse
import ashp
retain = False

# first level of looping: starts to handle each module connected to a certain controller with changed values individually. one serial at a time.
def handle_controller(serial):
    print("controller: "+str(serial))
    sql = "SELECT settings_id, module_id, sarjanumero, arvo, muuttunut FROM module_settings WHERE sarjanumero = %s AND muuttunut = 1" % (serial)
    cur.execute(sql)
    changed_mod = cur.fetchall()

    # branching if settings_id = 0
    device_num = 0
    for mod in changed_mod:
        if mod[0] == 0 and mod[1] == 0:
            continue
        elif mod[1] == 0:
            device_num += 1
            handle_price(mod)
        else:
            device_num += 1
            handle_device(mod)
    print("total number of handled device settings: "+str(device_num)+"\n")

    # going through profile settings
    sql2 = "SELECT id, sarjanumero, kohdistuu_id, profiili_id, alkaa, loppuu, arvo_nimi_id, arvo, muuttunut FROM rules WHERE sarjanumero = %s AND muuttunut = 1" % (serial)
    cur.execute(sql2)
    changed_prof = cur.fetchall()
    print("rules for the current controllers are: "+str(changed_prof)+"\n")
    for prof in changed_prof:
        handle_rule(serial, prof[2], prof[3], prof[6], prof[7])

    print("total number of handled rules: "+str(len(changed_prof))+"\n")

    # send profiles
    sql  = "SELECT id, milloin, alkaa, loppuu, viikonpaivat FROM profiles WHERE id > 0 AND sarjanumero = %s AND muuttunut = 1" % (serial)
    cur.execute(sql)
    profiles= cur.fetchall()
    for profile in profiles:
        handle_profile(serial, profile[0], profile[1], profile[2], profile[3], profile[4])

    # check away status and send mqtt messages accordingly
    sql  = "SELECT arvo FROM module_settings WHERE module_id = 0 AND settings_id = 0 AND sarjanumero = %s" % (serial)
    cur.execute(sql)
    away_status = cur.fetchone()
    sql  = "SELECT alkaa, loppuu FROM profiles WHERE id = -2 AND sarjanumero = %s" % (serial)
    cur.execute(sql)
    temp_away = cur.fetchone()

    if temp_away == None:
        temp_away = (None, None)

    if away_status != None and away_status[0] > 0:
        client.publish(MQTT_PREFIX+"controllers/"+str(serial)+"/profiles/away/enabled", payload=1, qos=1, retain=retain)
        client.publish(MQTT_PREFIX+"controllers/"+str(serial)+"/profiles/away/begin", payload=None, qos=1, retain=retain)
        client.publish(MQTT_PREFIX+"controllers/"+str(serial)+"/profiles/away/end", payload=None, qos=1, retain=retain)
        print("away status set: permanent")
    elif temp_away[0] != None or temp_away[1] != None:
        client.publish(MQTT_PREFIX+"controllers/"+str(serial)+"/profiles/away/enabled", payload=1, qos=1, retain=retain)
        client.publish(MQTT_PREFIX+"controllers/"+str(serial)+"/profiles/away/begin", payload=temp_away[0].isoformat(), qos=1, retain=retain)
        client.publish(MQTT_PREFIX+"controllers/"+str(serial)+"/profiles/away/end", payload=temp_away[1].isoformat(), qos=1, retain=retain)
        print("away status set: temporary")
    else:
        client.publish(MQTT_PREFIX+"controllers/"+str(serial)+"/profiles/away/enabled", payload=0, qos=1, retain=retain)
        client.publish(MQTT_PREFIX+"controllers/"+str(serial)+"/profiles/away/begin", payload=None, qos=1, retain=retain)
        client.publish(MQTT_PREFIX+"controllers/"+str(serial)+"/profiles/away/end", payload=None, qos=1, retain=retain)
        print("away status set: present")

    # send module information values
    sql = "SELECT id, tunniste, varmennuskoodi, muuttunut FROM module_information WHERE sarjanumero = %s AND (muuttunut = 1 OR muuttunut = 2)" % (serial)
    cur.execute(sql)
    information = cur.fetchall()
    for info in information:
        check_mod_info(serial, info[0], info[1], info[2], info[3])

    cur.execute("UPDATE module_information SET muuttunut = 0 WHERE sarjanumero = %s AND muuttunut = 1" % (serial))
    cur.execute("UPDATE module_settings SET muuttunut = 0 WHERE sarjanumero = %s AND muuttunut = 1" % (serial))
    conn.commit()

# handle single profile
def handle_profile(serial, id, enabled, begin, end, weekdays_str):
    # convert weird weekday string to ISO 8601
    to_iso_days = { 'ma': '1', 'ti': '2', 'ke': '3', 'to': '4', 'pe': '5', 'la': '6', 'su': '7' }
    old_days = weekdays_str.lstrip('_').split('&')
    days = []
    for d in old_days:
        if d in to_iso_days:
            days.append(to_iso_days[d])
    # convert enabled to comprehensible format
    if enabled == 2:
        enabled = 1
    else:
        enabled = 0
    # send messages
    client.publish(MQTT_PREFIX+"controllers/%s/profiles/%s" % (serial, id), payload='1', qos=1, retain=retain)
    client.publish(MQTT_PREFIX+"controllers/%s/profiles/%s/enabled" % (serial, id), payload=enabled, qos=1, retain=retain)
    client.publish(MQTT_PREFIX+"controllers/%s/profiles/%s/period/time/begin" % (serial, id), payload=begin.strftime('%H:%M'), qos=1, retain=retain)
    client.publish(MQTT_PREFIX+"controllers/%s/profiles/%s/period/time/end" % (serial, id), payload=end.strftime('%H:%M'), qos=1, retain=retain)
    client.publish(MQTT_PREFIX+"controllers/%s/profiles/%s/weekdays" % (serial, id), payload=','.join(days), qos=1, retain=retain)

# second level of looping: parses and sends out MQTT message conserning rules to right topic equaling to settings in DB
def handle_rule(serial, mod_id, profile, rule_type, value):
    if profile < 1:
        return False
    print("topic id is: "+str(type))
    topics = {"53" : "fan", "54" : "swing/vertical", "55" : "mode", "59" : "on", "60" : "swing/horizontal"}

    print("parsing rule topic path:")
    cur.execute("""SELECT tunniste, tyyppi FROM module_information WHERE id = %s""" % (mod_id))
    dev_id, dev_type = cur.fetchone()

    if dev_type == 7 or dev_type == 6:
        topic = MQTT_PREFIX+"controllers/"+str(serial)+"/devices/"+str(dev_id)+"/rules/"+str(profile)+"switch/on"
        client.publish(topic, payload=value, qos=1, retain=retain)
        print("message concerning rules sent to topic: "+topic+"\n")

    elif dev_type == 2 or dev_type == 4 or dev_type == 5:
        topic = MQTT_PREFIX+"controllers/"+str(serial)+"/devices/"+str(dev_id)+"/rules/"+str(profile)+"/temperature"
        client.publish(topic, payload=value, qos=1, retain = retain)
        print("message concerning rules sent to topic: "+topic+"\n")

    else:
        return False

    #after each module zero the changed value so the data is read only once and on controllers with validated serial
    confirm = "UPDATE rules SET muuttunut = 0 WHERE kohdistuu_id = %s AND sarjanumero = %s" % (mod_id, serial)
    cur.execute(confirm)
    conn.commit()

    #OLD VERSION BEGINS
    # # special cases concerning module type. tyyppi column in DB.
    # if topic_id == 50:
    #     if m_type == 7 or m_type == 6:
    #         topic = "controllers/"+str(module[1])+"/devices/"+str(module[2])+"/rules/"+str(module[3])+"switch/on/"
    #         client.publish(topic, payload=str(module[7]), qos=1, retain=True)
    #         print("message concerning rules sent to topic: "+topic+"\n")

    # if topic_id in topics.keys():

    #     print("parsing rule topic path from: "+str(module))
    #     sql = "SELECT tyyppi FROM module_information WHERE id = %s" % (module[2])
    #     cur.execute(sql)
    #     mod_info = cur.fetchone()
    #     m_type = mod_info[0]
    #     print("the module type is: "+str(m_type))

    #     # special cases concerning module type. tyyppi collumn in DB.
    #     if topic_id == 50:
    #         if m_type == 7 or m_type == 6:
    #             topic = MQTT_PREFIX+"controllers/"+str(module[1])+"/devices/"+str(module[2])+"/rules/"+str(module[3])+"switch/on/"
    #             client.publish(topic, payload=str(module[7]), qos=1, retain = retain)
    #             print("message concerning rules sent to topic: "+topic+"\n")

    #         elif m_type == 2 or m_type == 4 or m_type == 5:
    #             topic = MQTT_PREFIX+"controllers/"+str(module[1])+"/devices/"+str(module[2])+"/rules/"+str(module[3])+"/temperature/"
    #             client.publish(topic, payload=str(module[7]), qos=1, retain = retain)
    #             print("message concerning rules sent to topic: "+topic+"\n")

    #         else:
    #             return False

    #     else:
    #         topic = MQTT_PREFIX+"controllers/"+str(module[1])+"/devices/"+str(module[2])+"/rules/"+str(module[3])+"/type4/"+str(topics[str(topic_id)])
    #         client.publish(topic, payload=str(module[7]), qos=1, retain = retain)
    #         print("message concerning rules sent to topic: "+topic+"\n")

    #     # after each module zero the changed value so the data is read only once and on controllers with validated serial
    #     confirm = "UPDATE rules SET muuttunut = 0 WHERE kohdistuu_id = %s AND sarjanumero = %s" % (module[2], module[1])
    #     cur.execute(confirm)
    #     conn.commit()

    # else:
    #     return False
    #OLD VERSION ENDS

# second level of looping: handles the MQTT message conserning price to right topic equaling to settings_id in DB
def handle_price(pric):
    topic_id = str(pric[0])
    topics =    {"1" : "tariff", "2" : "price/primary", "4" : "price/margin", "5" : "price/period/time/begin",
                "6" : "price/period/time/end", "7" : "price/period/date/begin", "8" : "price/period/date/end", "30" : "price/max_effect"}

    if topic_id in topics.keys():

        if topic_id != 0:
            print("parsing price topic path from: "+str(pric))
            topic = MQTT_PREFIX+"controllers/"+str(pric[2])+"/electricity/"+str(topics[str(topic_id)])
            client.publish(topic, payload=str(pric[3]), qos=1, retain = retain)
            print("message concerning price sent to topic: "+topic+"\n")
        else:
            return False

        # after each module zero the changed value so the data is read only once and on controllers with validated serial
        confirm = "UPDATE module_settings SET muuttunut = 0 WHERE module_id = %s AND sarjanumero = %s" % (pric[1], pric[2])
        cur.execute(confirm)
        conn.commit()

    else:
        return False

# second level of looping: handles the MQTT message conserning device to right topic equaling to settings_id in DB
def handle_device(dev):
    topic_id = str(dev[0])
    topics =    {"0" : "away/", "1" : "power/", "2" : "manufacturer/", "9" : "temperature/safety/", "10" : "temperature/advance/", "15" : "temperature/freeze_limit/on/",
                "16" : "temperature/freeze_limit/when/", "51" : "temperature/floor_sensor/mode/", "52" : "switch/safety/", "211" : "temperature/warning/min/",
                "212" : "temperature/warning/max/", "213" : "humidity/warning/min/", "214" : "humidity/warning/max/"}

    if topic_id in topics.keys():

        print("parsing device topic path from: "+str(dev))
        topic = MQTT_PREFIX+"controllers/"+str(dev[2])+"/devices/"+str(dev[1])+"/"+str(topics[str(topic_id)])
        client.publish(topic, payload=str(dev[3]), qos=1, retain = retain)
        print("message concerning device sent to topic: "+topic+"\n")

        # after each module zero the changed value so the data is read only once and on controllers with validated serial
        confirm = "UPDATE module_settings SET muuttunut = 0 WHERE module_id = %s AND sarjanumero = %s" % (dev[1], dev[2])
        cur.execute(confirm)
        conn.commit()

    else:
        return False

def check_mod_info(serial, id, device_id, verification_code, changed):
    if changed == 1:
        # new device
        client.publish(str(MQTT_PREFIX)+"controllers/"+str(serial)+"/devices/"+str(device_id), payload="1", qos=1, retain=retain)
        client.publish(str(MQTT_PREFIX)+"controllers/"+str(serial)+"/devices/"+str(device_id)+"/verification_code", payload=str(verification_code), qos=1, retain=retain)
    elif changed == 2:
        # delete device
        client.publish(str(MQTT_PREFIX)+"controllers/"+str(serial)+"/devices/"+str(device_id), payload=None, qos=1, retain=retain)
        cur.execute("DELETE FROM module_history WHERE sarjanumero = %s AND module_id = %s" % (serial, id))
        cur.execute("DELETE FROM module_settings WHERE sarjanumero = %s AND module_id = %s" % (serial, id))
        cur.execute("DELETE FROM module_values WHERE sarjanumero = %s AND module_id = %s" % (serial, id))
        cur.execute("DELETE FROM rules WHERE sarjanumero = %s AND kohdistuu_id = %s" % (serial, id))
        cur.execute("DELETE FROM module_information WHERE sarjanumero = %s AND id = %s" % (serial, id))
        conn.commit()

    print("message concerning device sent to topic: "+MQTT_PREFIX+"controllers/"+str(serial)+"/devices/"+str(device_id)+"/verification_code -m \n"+verification_code)

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Listens to mqtt topic and changes module values in db accordingly", prog="listen.py", usage="proxy for listening mqtt topics to add values in sql")

    parser.add_argument("--mqtt-broker", help="MQTT broker host", default="localhost", type=str)
    parser.add_argument("--mqtt-port", help="MQTT broker host", default="1883", type=str)
    parser.add_argument("--mqtt-prefix", help="MQTT topic prefix", default="", type=str)
    parser.add_argument("--mqtt-user", help="MQTT username", default="", type=str)
    parser.add_argument("--mqtt-pass", help="MQTT password", default="", type=str)
    parser.add_argument("--mqtt-retain", help="If mqtt message needs to be retained (default=True)", default=True, type=bool)
    parser.add_argument("--mysql-host", help="MySQL server address", default="localhost", type=str)
    parser.add_argument("--mysql-port", help="MySQL server port", default="3306", type=str)
    parser.add_argument("--mysql-db", help="MySQL database to use", required=True, type=str) #mandatory!
    parser.add_argument("--mysql-user", help="MySQL username", default="", type=str)
    parser.add_argument("--mysql-pass", help="MySQL password", default="", type=str)

    args = parser.parse_args()
    print("connecting to mqtt broker with following settings:\n")
    mqtt_broker = str(args.mqtt_broker)
    mqtt_port = int(args.mqtt_port)
    MQTT_PREFIX = str(args.mqtt_prefix)
    mqtt_user = str(args.mqtt_user)
    mqtt_pass = str(args.mqtt_pass)
    MQTT_TOPIC=str(MQTT_PREFIX)+"controllers/#"
    retain = args.mqtt_retain
    print("MQTT broker: "+mqtt_broker)
    print("MQTT port: "+str(mqtt_port))
    print("MQTT topic: "+MQTT_TOPIC)
    print("MQTT user: "+mqtt_user)
    print("MQTT Message retain: "+str(retain)+"\n")

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
    client.connect(mqtt_broker, mqtt_port, 60)
    # mandatory loop for MQTT
    client.loop_start()

    # checking the version number. Only newer devices are included
    cur = conn.cursor()
    print("checking version >= 3.0 controllers modules...")
    sql = "SELECT sarjanumero, versio FROM system_update"
    cur.execute(sql)
    controllers = cur.fetchall()
    cont_num = 0
    for data in controllers:
        try:
            if float(data[1]) < 3:
                continue
        except ValueError:
            if data[1] != "rewrite":
                continue

        cont_num += 1
        handle_controller(data[0])
        print("total number of controllers handled: "+str(cont_num)+"\n")

    # end of mandatory MQTT loop
    client.loop_stop()
    cur.close()
    conn.close()