Sigma3 Touchscreen + MQTT Runbook
=========================================================

Terminal 1 - MQTT Broker
------------------------
mosquitto -v


Terminal 2 - Touchscreen Bridge (WiFi MQTT bridge)
---------------------------------------------------
cd /Users/.../.../Sigma3Castelao-main/software/touchescreen
export MQTT_HOST=127.0.0.1
export MQTT_PORT=1883
export SECTION_ID=12345
export SEAT_ID=section1,row1,col1
python3 main_touchscreen.py


Terminal 3 - GUI
----------------
cd /Users/.../.../Sigma3Castelao-main/software/touchescreen
export MQTT_HOST=127.0.0.1
export MQTT_PORT=1883
export SEAT_ID=section1,row1,col1
python3 qt_gui.py


Terminal 4 - Monitor MQTT topics (optional but recommended)
------------------------------------------------------------
mosquitto_sub -h 127.0.0.1 -p 1883 -v \
  -t 'stadium/seat/section1,row1,col1/cmd' \
  -t 'stadium/seat/section1,row1,col1/ack' \
  -t 'stadium/seat/section1,row1,col1/telemetry' \
  -t 'stadium/section/12345/telemetry' \
  -t 'stadium/broadcast/replay'


Replay Publish Commands (simulate backend server response)
==========================================================

Goal replay
-----------
mosquitto_pub -h 127.0.0.1 -p 1883 \
  -t 'stadium/broadcast/replay' \
  -m '{"ts":1771932000.0,"clip":"goal","url":"/Users/.../.../Sigma3Castelao-main/software/touchescreen/goal.mp4","expires_at":2771932300,"seat_id":"section1,row1,col1"}'


Highlight replay
----------------
mosquitto_pub -h 127.0.0.1 -p 1883 \
  -t 'stadium/broadcast/replay' \
  -m '{"ts":1771932005.0,"clip":"highlight","url":"/Users/.../.../Sigma3Castelao-main/software/touchescreen/highlight.mp4","expires_at":2771932305,"seat_id":"section1,row1,col1"}'


Moment replay
-------------
mosquitto_pub -h 127.0.0.1 -p 1883 \
  -t 'stadium/broadcast/replay' \
  -m '{"ts":1771932010.0,"clip":"moment","url":"/Users/.../.../Sigma3Castelao-main/software/touchescreen/moment.mp4","expires_at":2771932310,"seat_id":"section1,row1,col1"}'



