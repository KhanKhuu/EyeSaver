import paho.mqtt.client as mqtt
import time

client = mqtt.Client("poster")
client.connect("172.20.10.171", port=30300)
client.loop_start()
client.subscribe("eyes")

# Example 1: Starts with user looking at screen,
#            user looks for 21 'minutes' and then
#            takes a 1 minute break, then looks again
#            for 21 minutes.
# user looks at screen 11 minutes non-stop
#client.publish("eyes", "1") # user is looking
#time.sleep(21) # listener should alert user at 600 seconds
#client.publish("eyes", "0")
#time.sleep(1) # user takes a 20 second break
#client.publish("eyes", "1")
#time.sleep(24)

# Example 1: Starts with user looking at screen,
#            user looks for 11 'minutes' and then
#            takes a 6 second break, then looks again
#            for 12 second.
client.publish("eyes", "1") # user looks 2 seconds
time.sleep(2) 
client.publish("eyes", "0") # looks away 6 seconds
time.sleep(0.1)
client.publish("eyes", "1") # looks 5 seconds
time.sleep(5)
client.publish("eyes", "0") # looks away 12 seconds
time.sleep(0.2)
client.publish("eyes", "1") # looks 7 seconds
time.sleep(7)
client.publish("eyes", "0") # looks away 9 seconds
time.sleep(0.15)
client.publish("eyes", "1") # looks 6 seconds
time.sleep(6)
client.publish("eyes", "0") # looks away 2 seconds
time.sleep(2) 
client.publish("eyes", "1") # looks 19 seconds
time.sleep(19)
client.publish("eyes", "0") # look away 6 seconds
time.sleep(0.1)
client.publish("eyes", "1") # looks forever
time.sleep(10)
client.loop_stop

