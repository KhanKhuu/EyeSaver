# EyeSaver
Eye strain preventer that won most technically advanced award in the IEEE Winter 2021 Quarterly Project at UC San Diego. It uses four neural nets and a binary classifier to track your gaze as you use a computer and alert you when you've been looking at a screen for too long so you can take a break.  

![eyesaver_demo_16s](https://user-images.githubusercontent.com/33473815/110299234-47297800-7faa-11eb-9573-823d2ac0fc57.gif)



Requires:  
* Hardware: 
  * OpenCV AIKit camera module  
* Infrastructure:
  * MQTT server running on port 30300 (can be reconfigured)  
* Python Libraries:  
  * cv2
  * depthai
  * paho-mqtt
  * pandas
  * sklearn

Steps to use:
1. `$ python3 calibrate_eyes_ON.py -c`. When ready, press enter and look around at your computer screen until the program finishes (about 15 seconds).
2. `$ python3 calibrate_eyes_OFF.py -c`. When ready, press enter and look around away from your computer screen until the program finishes (about 15 seconds).
3. `$ python3 train_model.py`. Train the ON/OFF screen binary classifier on the data you just generated.
4. `$ python3 eye-strain-alerter.py`. Start the alert system software. 
5. `$ python3 eye-monitor.py -c`. Start the camera stream that monitors your gaze using the binary classifier.
