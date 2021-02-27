import paho.mqtt.client as mqtt
import time



class Timer:
    start_time = 0
    total_pause_time = 0
    pause_start = 0
    paused = False
    running = False

    def reset(self):
        self.start_time = time.time()

    def start(self):
        self.total_pause_time = 0
        self.start_time = time.time()
        self.running = True

    def stop(self):
        self.running = False

    def time(self):
        return (time.time() - self.start_time) - self.total_pause_time

    def pause(self):
        if self.paused is False:
            self.pause_start = time.time()
            self.paused = True

    def unpause(self):
        if (self.paused is True):
            self.total_pause_time += (time.time() - self.pause_start)
            self.paused = False
            
    def current_pause_time(self):
        if (self.paused):
            return time.time() - self.pause_start
        else:
            return 0

# global state variable
user_on_break = False
user_is_looking = False
alerted = False
counting_look_time = False

# global time tracking variables
look_timer = Timer()
break_timer = Timer()

# global constants
MAX_SCREEN_TIME = 20
LOOK_AWAY_TIME = 0.333

### This happens only when the user_is_looking state changes
def message_received(client, userdata, message):

    global look_timer
    global break_timer

    if (str(message.payload.decode("utf-8")) == "1"): #went from not looking to looking
        if look_timer.running == False:
            look_timer.start()
        else:
            look_timer.unpause()

        if break_timer.running:
            break_timer.reset()
            print("Resetting break timer. Try not to look at the screen for 20 seconds.")
    else: 
        if look_timer.running:
            print("looked away")
            look_timer.pause()
        else:
            break_timer.start()

client = mqtt.Client("listener")
client.connect("172.20.10.171", port=30300)
client.on_message=message_received
client.loop_start()
client.subscribe("eyes")

def main():

    global alerted
    global look_timer
    global break_timer
    global LOOK_AWAY_TIME
    global MAX_SCREEN_TIME

    ### This is happening over and over again forever
    while(True):

        if (look_timer.running and look_timer.current_pause_time() >= LOOK_AWAY_TIME):
            look_timer.reset()

        if (look_timer.running and look_timer.time() >= MAX_SCREEN_TIME):
                print("Go on break")
                look_timer.stop()
                look_timer.reset()
        if (break_timer.running and break_timer.time() >= LOOK_AWAY_TIME):
            print("Break time over")
            break_timer.stop()
            break_timer.reset()


if __name__ == "__main__":
    main()

