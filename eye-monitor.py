import argparse
import pickle
import queue
import threading
from pathlib import Path
from sklearn.linear_model import SGDClassifier
from sklearn.preprocessing import MinMaxScaler
import paho.mqtt.client as mqtt
import cv2
import depthai
import numpy as np
from imutils.video import FPS
from math import cos, sin, floor


parser = argparse.ArgumentParser()
parser.add_argument('-nd', '--no-debug', action="store_true", help="Prevent debug output")
parser.add_argument('-cam', '--camera', action="store_true", help="Use DepthAI 4K RGB camera for inference (conflicts with -vid)")
parser.add_argument('-vid', '--video', type=str, help="Path to video file to be used for inference (conflicts with -cam)")
args = parser.parse_args()

debug = not args.no_debug
camera = not args.video

if args.camera and args.video:
    raise ValueError("Incorrect command line parameters! \"-cam\" cannot be used with \"-vid\"!")
elif args.camera is False and args.video is None:
    raise ValueError("Missing inference source! Either use \"-cam\" to run on DepthAI camera or \"-vid <path>\" to run on video file")


def draw_3d_axis(image, head_pose, origin, size=50):
    roll = head_pose[0] * np.pi / 180
    pitch = head_pose[1] * np.pi / 180
    yaw = -(head_pose[2] * np.pi / 180)

    # X axis (red)
    x1 = size * (cos(yaw) * cos(roll)) + origin[0]
    y1 = size * (cos(pitch) * sin(roll) + cos(roll) * sin(pitch) * sin(yaw)) + origin[1]
    cv2.line(image, (origin[0], origin[1]), (int(x1), int(y1)), (0, 0, 255), 3)

    # Y axis (green)
    x2 = size * (-cos(yaw) * sin(roll)) + origin[0]
    y2 = size * (-cos(pitch) * cos(roll) - sin(pitch) * sin(yaw) * sin(roll)) + origin[1]
    cv2.line(image, (origin[0], origin[1]), (int(x2), int(y2)), (0, 255, 0), 3)

    # Z axis (blue)
    x3 = size * (-sin(yaw)) + origin[0]
    y3 = size * (cos(yaw) * sin(pitch)) + origin[1]
    cv2.line(image, (origin[0], origin[1]), (int(x3), int(y3)), (255, 0, 0), 2)

    return image


def frame_norm(frame, bbox):
    norm_vals = np.full(len(bbox), frame.shape[0])
    norm_vals[::2] = frame.shape[1]
    return (np.clip(np.array(bbox), 0, 1) * norm_vals).astype(int)


def to_planar(arr: np.ndarray, shape: tuple) -> list:
    return [val for channel in cv2.resize(arr, shape).transpose(2, 0, 1) for y_col in channel for val in y_col]


def to_tensor_result(packet):
    return {
        tensor.name: np.array(packet.getLayerFp16(tensor.name)).reshape(tensor.dims)
        for tensor in packet.getRaw().tensors
    }


def padded_point(point, padding, frame_shape=None):
    if frame_shape is None:
        return [
            point[0] - padding,
            point[1] - padding,
            point[0] + padding,
            point[1] + padding
        ]
    else:
        def norm(val, dim):
            return max(0, min(val, dim))
        if np.any(point - padding > frame_shape[:2]) or np.any(point + padding < 0):
            print(f"Unable to create padded box for point {point} with padding {padding} and frame shape {frame_shape[:2]}")
            return None

        return [
            norm(point[0] - padding, frame_shape[0]),
            norm(point[1] - padding, frame_shape[1]),
            norm(point[0] + padding, frame_shape[0]),
            norm(point[1] + padding, frame_shape[1])
        ]


def create_pipeline():
    print("Creating pipeline...")
    pipeline = depthai.Pipeline()

    if camera:
        print("Creating Color Camera...")
        cam = pipeline.createColorCamera()
        cam.setPreviewSize(300, 300)
        cam.setResolution(depthai.ColorCameraProperties.SensorResolution.THE_1080_P)
        cam.setInterleaved(False)
        cam.setBoardSocket(depthai.CameraBoardSocket.RGB)

        cam_xout = pipeline.createXLinkOut()
        cam_xout.setStreamName("cam_out")
        cam.preview.link(cam_xout.input)


    # NeuralNetwork
    print("Creating Face Detection Neural Network...")
    face_nn = pipeline.createNeuralNetwork()
    face_nn.setBlobPath(str(Path("models/face-detection-retail-0004/face-detection-retail-0004.blob").resolve().absolute()))

    if camera:
        cam.preview.link(face_nn.input)
    else:
        face_in = pipeline.createXLinkIn()
        face_in.setStreamName("face_in")
        face_in.out.link(face_nn.input)

    face_nn_xout = pipeline.createXLinkOut()
    face_nn_xout.setStreamName("face_nn")
    face_nn.out.link(face_nn_xout.input)
    
    # NeuralNetwork
    print("Creating Landmarks Detection Neural Network...")
    land_nn = pipeline.createNeuralNetwork()
    land_nn.setBlobPath(
        str(Path("models/landmarks-regression-retail-0009/landmarks-regression-retail-0009.blob").resolve().absolute())
    )
    land_nn_xin = pipeline.createXLinkIn()
    land_nn_xin.setStreamName("landmark_in")
    land_nn_xin.out.link(land_nn.input)
    land_nn_xout = pipeline.createXLinkOut()
    land_nn_xout.setStreamName("landmark_nn")
    land_nn.out.link(land_nn_xout.input)

    # NeuralNetwork
    print("Creating Head Pose Neural Network...")
    pose_nn = pipeline.createNeuralNetwork()
    pose_nn.setBlobPath(
        str(Path("models/head-pose-estimation-adas-0001/head-pose-estimation-adas-0001.blob").resolve().absolute())
    )
    pose_nn_xin = pipeline.createXLinkIn()
    pose_nn_xin.setStreamName("pose_in")
    pose_nn_xin.out.link(pose_nn.input)
    pose_nn_xout = pipeline.createXLinkOut()
    pose_nn_xout.setStreamName("pose_nn")
    pose_nn.out.link(pose_nn_xout.input)

    # NeuralNetwork
    print("Creating Gaze Estimation Neural Network...")
    gaze_nn = pipeline.createNeuralNetwork()
    gaze_nn.setBlobPath(
        str(Path("models/gaze-estimation-adas-0002/gaze-estimation-adas-0002.blob").resolve().absolute())
    )
    gaze_nn_xin = pipeline.createXLinkIn()
    gaze_nn_xin.setStreamName("gaze_in")
    gaze_nn_xin.out.link(gaze_nn.input)
    gaze_nn_xout = pipeline.createXLinkOut()
    gaze_nn_xout.setStreamName("gaze_nn")
    gaze_nn.out.link(gaze_nn_xout.input)

    return pipeline


class Main:
    def __init__(self, device):
        self.device = device
        print("Starting pipeline...")
        self.device.startPipeline()
        if camera:
            self.cam_out = self.device.getOutputQueue("cam_out")
        else:
            self.face_in = self.device.getInputQueue("face_in")

        if not camera:
            self.cap = cv2.VideoCapture(str(Path(args.video).resolve().absolute()))

        self.frame = None
        self.face_box_q = queue.Queue()
        self.bboxes = []
        self.left_bbox = None
        self.right_bbox = None
        self.nose = None
        self.pose = None
        self.gaze = None

        self.running = True
        self.fps = FPS()
        self.fps.start()

    def face_thread(self):
        face_nn = self.device.getOutputQueue("face_nn")
        landmark_in = self.device.getInputQueue("landmark_in")
        pose_in = self.device.getInputQueue("pose_in")

        while self.running:
            if self.frame is None:
                continue
            try:
                bboxes = np.array(face_nn.get().getFirstLayerFp16())
            except RuntimeError as ex:
                continue
            bboxes = bboxes.reshape((bboxes.size // 7, 7))
            self.bboxes = bboxes[bboxes[:, 2] > 0.7][:, 3:7]

            for raw_bbox in self.bboxes:
                bbox = frame_norm(self.frame, raw_bbox)
                det_frame = self.frame[bbox[1]:bbox[3], bbox[0]:bbox[2]]

                land_data = depthai.NNData()
                land_data.setLayer("0", to_planar(det_frame, (48, 48)))
                landmark_in.send(land_data)

                pose_data = depthai.NNData()
                pose_data.setLayer("data", to_planar(det_frame, (60, 60)))
                pose_in.send(pose_data)

                self.face_box_q.put(bbox)

    def land_pose_thread(self):
        landmark_nn = self.device.getOutputQueue(name="landmark_nn", maxSize=1, blocking=False)
        pose_nn = self.device.getOutputQueue(name="pose_nn", maxSize=1, blocking=False)
        gaze_in = self.device.getInputQueue("gaze_in")

        while self.running:
            try:
                land_in = landmark_nn.get().getFirstLayerFp16()
            except RuntimeError as ex:
                continue

            try:
                face_bbox = self.face_box_q.get(block=True, timeout=100)
            except queue.Empty:
                continue

            self.face_box_q.task_done()
            left = face_bbox[0]
            top = face_bbox[1]
            

            face_frame = self.frame[face_bbox[1]:face_bbox[3], face_bbox[0]:face_bbox[2]]
            land_data = frame_norm(face_frame, land_in)
            land_data[::2] += left
            land_data[1::2] += top
            left_bbox = padded_point(land_data[:2], padding=30, frame_shape=self.frame.shape)
            if left_bbox is None:
                print("Point for left eye is corrupted, skipping nn result...")
                continue
            self.left_bbox = left_bbox
            right_bbox = padded_point(land_data[2:4], padding=30, frame_shape=self.frame.shape)
            if right_bbox is None:
                print("Point for right eye is corrupted, skipping nn result...")
                continue
            self.right_bbox = right_bbox
            self.nose = land_data[4:6]
            left_img = self.frame[self.left_bbox[1]:self.left_bbox[3], self.left_bbox[0]:self.left_bbox[2]]
            right_img = self.frame[self.right_bbox[1]:self.right_bbox[3], self.right_bbox[0]:self.right_bbox[2]]

            try:
                self.pose = [val[0][0] for val in to_tensor_result(pose_nn.get()).values()]
            except RuntimeError as ex:
                continue

            gaze_data = depthai.NNData()
            gaze_data.setLayer("left_eye_image", to_planar(left_img, (60, 60)))
            gaze_data.setLayer("right_eye_image", to_planar(right_img, (60, 60)))
            gaze_data.setLayer("head_pose_angles", self.pose)
            gaze_in.send(gaze_data)

    def gaze_thread(self):
        gaze_nn = self.device.getOutputQueue("gaze_nn")
        while self.running:
            try:
                self.gaze = np.array(gaze_nn.get().getFirstLayerFp16())
            except RuntimeError as ex:
                continue

    def should_run(self):
        return True if camera else self.cap.isOpened()

    def get_frame(self, retries=0):
        if camera:
            return True, np.array(self.cam_out.get().getData()).reshape((3, 300, 300)).transpose(1, 2, 0).astype(np.uint8)
        else:
            read_correctly, new_frame = self.cap.read()
            if not read_correctly or new_frame is None:
                if retries < 5:
                    return self.get_frame(retries+1)
                else:
                    print("Source closed, terminating...")
                    return False, None
            else:
                return read_correctly, new_frame

    
    def run(self):

        self.threads = [
            threading.Thread(target=self.face_thread),
            threading.Thread(target=self.land_pose_thread),
            threading.Thread(target=self.gaze_thread)
        ]
        for thread in self.threads:
            thread.start()


        ## TODO: 
        ## 1) load look-detector model (import pickle, import sklearn.models...
        ## 2) make predictions from data
        ## 3) setup MQTT client
        ## 4) track state
        ## 5) send message when state changes

        look_detector = pickle.load(open('models/looking-at-screen-detector/looking-at-screen-detector.blob', 'rb'))
        #print(look_detector.predict(np.array([0.333333, 0.333333, 0.333333]).reshape(1,-1)))
        normalizer = pickle.load(open('models/looking-at-screen-detector/normalizer.blob', 'rb'))

        streamsize = 50

        datastream = np.zeros(streamsize)
        idx = 0
        
        look_state = False

        client = mqtt.Client("look-detector")
        client.connect("172.20.10.171", port=30300)
        client.loop_start()
        client.subscribe("eyes")

        while self.should_run():
            read_correctly, new_frame = self.get_frame()
            
            if not read_correctly:
                break

            self.fps.update()
            self.frame = new_frame
            self.debug_frame = self.frame.copy()

            if not camera:
                nn_data = depthai.NNData()
                nn_data.setLayer("data", to_planar(self.frame, (300, 300)))
                self.face_in.send(nn_data)

            if debug:  # face

                ### face bounding box drawings $$
                #for raw_bbox in self.bboxes:
                    #bbox = frame_norm(self.frame, raw_bbox)
                    #cv2.rectangle(self.debug_frame, (bbox[0], bbox[1]), (bbox[2], bbox[3]), (10, 245, 10), 2)
                
                ### eye bounding box drawings ### 
                #if self.left_bbox is not None:
                    #cv2.rectangle(self.debug_frame, (self.left_bbox[0], self.left_bbox[1]), (self.left_bbox[2], self.left_bbox[3]), (245, 10, 10), 2)
                #if self.right_bbox is not None:
                    #cv2.rectangle(self.debug_frame, (self.right_bbox[0], self.right_bbox[1]), (self.right_bbox[2], self.right_bbox[3]), (245, 10, 10), 2)

                ### dot on nose showing origin of 3-d plane representing head tilt
                #if self.nose is not None:
                    #cv2.circle(self.debug_frame, (self.nose[0], self.nose[1]), 2, (0, 255, 0), thickness=5, lineType=8, shift=0)

                ### nose 3-d axis showing head pose
                #if self.pose is not None and self.nose is not None:
                    #draw_3d_axis(self.debug_frame, self.pose, self.nose)

                if self.gaze is not None and self.left_bbox is not None and self.right_bbox is not None:
                    re_x = (self.right_bbox[0] + self.right_bbox[2]) // 2
                    re_y = (self.right_bbox[1] + self.right_bbox[3]) // 2
                    le_x = (self.left_bbox[0] + self.left_bbox[2]) // 2
                    le_y = (self.left_bbox[1] + self.left_bbox[3]) // 2

                    x, y = (self.gaze * 100).astype(int)[:2]
                    cv2.arrowedLine(self.debug_frame, (le_x, le_y), (le_x + x, le_y - y), (255, 0, 255), 3)
                    cv2.arrowedLine(self.debug_frame, (re_x, re_y), (re_x + x, re_y - y), (255, 0, 255), 3)

                ############# Here's the gaze data #################

                #print(type(self.gaze))

                
                if self.gaze is not None:
                    datapoint = np.array(self.gaze).reshape(1,-1)
                    datapoint = normalizer.transform(datapoint)
                    #print(datapoint)

                    prediction = look_detector.predict(datapoint)
                    
                    datastream[idx] = prediction
                    idx = (idx + 1) % streamsize 
                    mode = floor(datastream.sum() / (streamsize / 2 + 1))
                    if (mode == 0):
                        if look_state is True:
                            client.publish("eyes", "0")
                            look_state = False
                    else:
                        if look_state is False:
                            client.publish("eyes", "1")
                            look_state = True

                else:
                    print('user not there')

                if camera:
                    cv2.imshow("Camera view", self.debug_frame)
                else:
                    aspect_ratio = self.frame.shape[1] / self.frame.shape[0]
                    cv2.imshow("Video view", cv2.resize(self.debug_frame, (int(900),  int(900 / aspect_ratio))))
                if cv2.waitKey(1) == ord('q'):
                    cv2.destroyAllWindows()
                    break

        self.fps.stop()
        print("FPS: {:.2f}".format(self.fps.fps()))
        if not camera:
            self.cap.release()
        cv2.destroyAllWindows()
        for i in range(1, 5):  # https://stackoverflow.com/a/25794701/5494277
            cv2.waitKey(1)
        self.running = False


with depthai.Device(create_pipeline()) as device:
    app = Main(device)
    app.run()

for thread in app.threads:
    thread.join()
