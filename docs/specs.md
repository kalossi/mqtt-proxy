*May 2018*
# Specification for Kotivo MQTT-SQL-proxy

Kotivo MQTT-SQL-proxy will be used to relay information between MQTT broker and
current Kotivo SQL database. This is done in two directions.
1. Changed values from database are sent to MQTT broker
2. Certain messages from MQTT broker are written into database

This should be done by two different programs, referring to the previous list:
1. Executed by cron at some interval
2. Running in the background as daemon

Lets call these programs from now on as follows:
1. publisher
2. listener

## Command line arguments
Both programs take the same arguments.
```
Usage:
 <program> [options]

Options:
  -h, --help                 display this help and exit
  --mqtt-host=<address>      MQTT broker host, default localhost
  --mqtt-port=<port>         MQTT broker host, default 1883
  --mqtt-prefix=<prefix>     MQTT topic prefix, default to no prefix
  --mqtt-user=<username>     MQTT username, default to no username
  --mqtt-pass=<password>     MQTT password, default to no password
  --mysql-host=<address>     MySQL server address, default localhost
  --mysql-port=<port>        MySQL server port, default 3306
  --mysql-db=<name>          MySQL database to use, required, no default
  --mysql-user=<username>    MySQL username, default to no username
  --mysql-pass=<password>    MySQL password, default to no password
```

## publisher


## listener
Must listen to topics described later under ***[prefix/]controllers/{controller_id}*** and write incoming messages
from those topics to database.

* *controller_id* must match to field *sarjanumero* in all tables
* *device_id* correlates to field *tunniste* in table *module_information*
* Table *module_values* needs *module_id* which must be resolved from *module_information* based on *sarjanumero* and *tunniste*

### topics
| topic                                                 | database table     | field written | key fields                            |
| ----------------------------------------------------- | ------------------ | ------------- | ------------------------------------- |
| /version                                              | system_update      | version       | sarjanumero                           |
| /electricity/power/current                            | module_values      | arvo          | sarjanumero, module_id=0, nimi_id=152 |
| /electricity/price/current                            | module_values      | arvo          | sarjanumero, module_id=0, nimi_id=151 |
| /devices/{device_id}/type                             | module_information | tyyppi        | sarjanumero, tunniste                 |
| /devices/{device_id}/version                          | module_information | NOT DONE      | sarjanumero, tunniste                 |
| /devices/{device_id}/connected                        | module_values      | arvo          | sarjanumero, module_id, nimi_id=0     |
| /devices/{device_id}/temperature/current              | module_values      | arvo          | sarjanumero, module_id, nimi_id=1     |
| /devices/{device_id}/temperature/floor_sensor/current | module_values      | arvo          | sarjanumero, module_id, nimi_id=4     |
| /devices/{device_id}/temperature/heating              | module_values      | arvo          | sarjanumero, module_id, nimi_id=2     |
| /devices/{device_id}/temperature/target               | module_values      | arvo          | sarjanumero, module_id, nimi_id=50    |
| /devices/{device_id}/humidity/current                 | module_values      | arvo          | sarjanumero, module_id, nimi_id=3     |
| /devices/{device_id}/switch/on                        | module_values      | arvo          | sarjanumero, module_id, nimi_id=2     |

### Examples
Message to topic (dev prefixed) **my_dev_prefix/controllers/123/devices/321/type** with payload **77** would write to table
**module_information** with following SQL clause:
```sql
UPDATE module_information SET tyyppi = 77 WHERE sarjanumero = 123 AND tunniste = 321
```

Message to topic (no prefix) **controllers/123/devices/321/temperature/current** with payload **21.85** would write to table
**module_values** with following SQL clause:
```sql
INSERT INTO module_values (sarjanumero, module_id, nimi_id, arvo)
  SELECT 123, id, 1, 21.85
  FROM module_information
  WHERE sarjanumero = 123 AND tunniste = 321
  ON DUPLICATE KEY UPDATE arvo = 21.85
```
