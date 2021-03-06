import paho.mqtt.client as mqtt
import signal
import subprocess
import time

# global init state
init = False



class Timer:
    start_time = 0
    total_pause_time = 0
    pause_start = 0
    paused = False
    running = False

    def reset(self):
        self.total_pause_time = 0
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
user_on_break = False # user was alerted and started looking away

# global time tracking variable
timer = Timer()

# global constants
MAX_SCREEN_TIME = 20
LOOK_AWAY_TIME = 15

#global process for music
#music_process = None

### This happens each time the user starts looking or looks away
def message_received(client, userdata, message):
    global user_on_break
    global timer
    global init

    if init is False:
        init = True

    if (str(message.payload.decode("utf-8")) == "1"): # user started looking
        print('looking at screen')
        if user_on_break:
            # user ended break too soon
            print('Resetting break timer. Try looking away for the full ' + 
                   str(LOOK_AWAY_TIME) + ' seconds.')
            timer.stop()
            timer.reset()
        else: # user started looking again while not on break
            if timer.paused: # user looked away briefly and is now looking back
                timer.unpause()
            else: # user is coming off of break
                timer.reset()
                timer.start()

    else: # user looked away
        print('looking away from screen')
        if user_on_break:
            # user restarted break
            timer.reset()
            timer.start()
        else:
            # user looks aways without it being time for a break
            timer.pause()

client = mqtt.Client("listener")
client.connect("172.20.10.171", port=30300)
client.on_message=message_received
client.loop_start()
client.subscribe("eyes")

play_ding_cmd = "omxplayer -o local ding.m4a"
#play_break_music_cmd = "omxplayer -o local controlla.m4a"

def main():

    global init
    global user_on_break
    global timer
    global LOOK_AWAY_TIME
    global MAX_SCREEN_TIME
    #global music_process

    while init is False:
        time.sleep(1)
    
    ### This is happening over and over again forever
    while(True):
        if user_on_break:
            if timer.time() >= LOOK_AWAY_TIME:
                print('Break is over! Get back to work.')
                user_on_break = False
                process = subprocess.Popen(play_ding_cmd.split(), stdout=subprocess.PIPE)
                output, error = process.communicate()
                timer.stop()
                timer.reset()
        else:
            if timer.time() >= MAX_SCREEN_TIME:
                print('You have been looking at the screen for ' +
                      str(MAX_SCREEN_TIME) + ' minutes. Try looking ' +
                      'at something far away for ' + str(LOOK_AWAY_TIME) +
                      'minutes.')
                process = subprocess.Popen(play_ding_cmd.split(), stdout=subprocess.PIPE)
                timer.stop()
                timer.reset()
                user_on_break = True
                

if __name__ == "__main__":
    main()

