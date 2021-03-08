# EyeSaver
Eye strain preventer that won most technically advanced award in the IEEE Winter 2021 Quarterly Project at UC San Diego. It uses four neural nets and a binary classifier to track your gaze as you use a computer and alert you when you've been looking at a screen for too long so you can take a break.  

![eyesaver_demo_25s](https://user-images.githubusercontent.com/33473815/110295363-e009c480-7fa5-11eb-8d10-b41efed0d50b.gif)


Requires:  
* Hardware: 
  * OpenCV AIKit camera module  
* Infrastructure:
  * MQTT server running on port 30300 (can be reconfigured)  
* Python Libraries:  
  * depthai
  * opencv
  * paho-mqtt  
