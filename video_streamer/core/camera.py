import time
import logging
import struct
import sys
import os
import io
import multiprocessing
import multiprocessing.queues
import requests
import redis
import json
import base64
from datetime import datetime
import cv2
import numpy as np

from typing import Union, IO, Tuple

from PIL import Image

try:
    from PyTango import DeviceProxy
except ImportError:
    logging.warning("PyTango not available.")


class Camera:
    def __init__(self, device_uri: str, sleep_time: int, debug: bool = False, redis: str = None, redis_channel: str = None):
        self._device_uri = device_uri
        self._sleep_time = sleep_time
        self._debug = debug
        self._width = -1
        self._height = -1
        self._output = None
        self._redis = redis
        self._redis_channel = redis_channel

    def _poll_once(self) -> None:
        pass

    def _write_data(self, data: bytearray):
        if isinstance(self._output, multiprocessing.queues.Queue):
            self._output.put(data)
        else:
            self._output.write(data)

    def poll_image(self, output: Union[IO, multiprocessing.queues.Queue]) -> None:
        self._output = output
        if self._redis:
            host, port = self._redis.split(':')
            self._redis_client = redis.StrictRedis(host=host, port=port)

        while True:
            try:
                self._poll_once()
            except KeyboardInterrupt:
                sys.exit(0)
            except BrokenPipeError:
                sys.exit(0)
            except Exception:
                logging.exception("")
            finally:
                pass

    @property
    def size(self) -> Tuple[float, float]:
        return (self._width, self._height)

    def get_jpeg(self, data, size=(0, 0)) -> bytearray:
        jpeg_data = io.BytesIO()
        image = Image.frombytes("RGB", self.size, data, "raw")

        if size[0]:
            image = image.resize(size)

        image.save(jpeg_data, format="JPEG")
        jpeg_data = jpeg_data.getvalue()

        return jpeg_data


class MJPEGCamera(Camera):
    def __init__(self, device_uri: str, sleep_time: int, debug: bool = False, redis: str = None, redis_channel: str = None):
        super().__init__(device_uri, sleep_time, debug, redis, redis_channel)

    def poll_image(self, output: Union[IO, multiprocessing.queues.Queue]) -> None:
        # auth=("user", "password")
        r = requests.get(self._device_uri, stream=True)

        buffer = bytes()
        while True:
            try:
                if r.status_code == 200:
                    for chunk in r.iter_content(chunk_size=1024):
                        buffer += chunk

                else:
                    print("Received unexpected status code {}".format(r.status_code))
            except requests.exceptions.StreamConsumedError:
                output.put(buffer)
                r = requests.get(self._device_uri, stream=True)
                buffer = bytes()

    def get_jpeg(self, data, size=None) -> bytearray:
        return data


class LimaCamera(Camera):
    def __init__(self, device_uri: str, sleep_time: int, debug: bool = False, redis: str = None, redis_channel: str = None):
        super().__init__(device_uri, sleep_time, debug, redis, redis_channel)

        self._lima_tango_device = self._connect(self._device_uri)
        _, self._width, self._height, _ = self._get_image()
        self._sleep_time = sleep_time
        self._last_frame_number = -1

    def _connect(self, device_uri: str) -> DeviceProxy:
        try:
            logging.info("Connecting to %s", device_uri)
            lima_tango_device = DeviceProxy(device_uri)
            lima_tango_device.ping()
        except Exception:
            logging.exception("")
            logging.info("Could not connect to %s, retrying ...", device_uri)
            sys.exit(-1)
        else:
            return lima_tango_device

    def _get_image(self) -> Tuple[bytearray, float, float, int]:
        img_data = self._lima_tango_device.video_last_image

        hfmt = ">IHHqiiHHHH"
        hsize = struct.calcsize(hfmt)
        _, _, img_mode, frame_number, width, height, _, _, _, _ = struct.unpack(
            hfmt, img_data[1][:hsize]
        )

        raw_data = img_data[1][hsize:]

        return raw_data, width, height, frame_number

    def _poll_once(self) -> None:
        frame_number = self._lima_tango_device.video_last_image_counter

        if self._last_frame_number != frame_number:
            raw_data, width, height, frame_number = self._get_image()
            self._raw_data = raw_data

            self._write_data(self._raw_data)
            self._last_frame_number = frame_number

            if self._redis:
                frame_dict = {
                    "data": base64.b64encode(self._raw_data).decode('utf-8'),
                    "size": (width, height),
                    "time": datetime.now().strftime("%H:%M:%S.%f"),
                    "frame_number": self._last_frame_number,
                }
                self._redis_client.publish(self._redis_channel, json.dumps(frame_dict))

        time.sleep(self._sleep_time / 2)


class RedisCamera(Camera):
    def __init__(self, device_uri: str, sleep_time: int, debug: bool = False, out_redis: str = None, out_redis_channel: str = None, in_redis_channel: str = 'frames'):
        super().__init__(device_uri, sleep_time, debug, out_redis, out_redis_channel)
        # for this camera in_redis_... is for the input and redis_... as usual for output
        self._in_redis_client = self._connect(self._device_uri)
        self._last_frame_number = -1
        self._in_redis_channel = in_redis_channel
        self._set_size()

    def _set_size(self):
        # the size is send via redis, hence we get the information from there
        pubsub = self._in_redis_client.pubsub()
        pubsub.subscribe(self._in_redis_channel)
        while True:
            message = pubsub.get_message()
            if message and message["type"] == "message":
                frame = json.loads(message["data"])
                self._width = frame["size"][1]
                self._height = frame["size"][0]
                break

    def _connect(self, device_uri: str):
        host, port = device_uri.replace('redis://', '').split(':')
        port = port.split('/')[0]
        return redis.StrictRedis(host=host, port=port)

    def poll_image(self, output: Union[IO, multiprocessing.queues.Queue]) -> None:
        pubsub = self._in_redis_client.pubsub()
        pubsub.subscribe(self._in_redis_channel)
        self._output = output
        for message in pubsub.listen():
            if message["type"] == "message":
                frame = json.loads(message["data"])
                self._last_frame_number += 1
                if self._redis:
                    frame_dict = {
                        "data": frame["data"],
                        "size": frame["size"],
                        "time": datetime.now().strftime("%H:%M:%S.%f"),
                        "frame_number": self._last_frame_number
                    }
                    self._redis_client.publish(self._redis_channel, json.dumps(frame_dict))
                raw_image_data = base64.b64decode(frame["data"])
                # ffmpeg needs an rgb encoded image, since we cannot be sure if the image was in rgb or 
                # bgr(common for cv2 image manipulation) we need these transformations
                image_array = np.frombuffer(raw_image_data, dtype=np.uint8)
                frame = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                self._write_data(rgb_frame.tobytes())

class TestCamera(Camera):
    def __init__(self, device_uri: str, sleep_time: int, debug: bool = False, redis: str = None, redis_channel: str = None):
        super().__init__(device_uri, sleep_time, debug, redis, redis_channel)
        self._sleep_time = 0.05
        testimg_fpath = os.path.join(os.path.dirname(__file__), "fakeimg.jpg")
        self._im = Image.open(testimg_fpath, "r")

        self._raw_data = self._im.convert("RGB").tobytes()
        self._width, self._height = self._im.size
        self._last_frame_number = -1

    def _poll_once(self) -> None:
        self._write_data(self._raw_data)
        
        self._last_frame_number += 1
        if self._redis:
            frame_dict = {
                "data": base64.b64encode(self._raw_data).decode('utf-8'),
                "size": self._im.size,
                "time": datetime.now().strftime("%H:%M:%S.%f"),
                "frame_number": self._last_frame_number,
            }
            self._redis_client.publish(self._redis_channel, json.dumps(frame_dict))
        
        time.sleep(self._sleep_time)

class VideoTestCamera(Camera):
    def __init__(self, device_uri: str, sleep_time: int, debug: bool = False, redis: str = None, redis_channel: str = None):
        super().__init__(device_uri, sleep_time, debug, redis, redis_channel)
        self._sleep_time = 0.04
        # for your testvideo, please use an uncompressed video or mjpeg codec, 
        # otherwise, opencv might have issues with reading the frames.
        self._testvideo_fpath = os.path.join(os.path.dirname(__file__), "./test_video.avi")
        self._current = 0
        self._video_capture = cv2.VideoCapture(self._testvideo_fpath)
        self._set_video_dimensions()
        self._last_frame_number = -1

    def _poll_once(self) -> None:
        if not self._video_capture.isOpened():
            print("Video capture is not opened.")
            return
        
        ret, frame = self._video_capture.read()
        if not ret:
            # End of video, loop back to the beginning
            self._video_capture.release()
            self._video_capture = cv2.VideoCapture(self._testvideo_fpath)
            ret, frame = self._video_capture.read()
            if not ret:
                print("Failed to restart video capture.")
                return
            
        frame_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        size = frame_pil.size        
        frame_bytes = frame_pil.tobytes()
        self._write_data(bytearray(frame_bytes))
        self._last_frame_number += 1
        if self._redis:
            frame_dict = {
                "data": base64.b64encode(frame_bytes).decode('utf-8'),
                "size": size,
                "time": datetime.now().strftime("%H:%M:%S.%f"),
                "frame_number": self._last_frame_number,
            }
            self._redis_client.publish(self._redis_channel, json.dumps(frame_dict))
        
        time.sleep(self._sleep_time)

    def _set_video_dimensions(self):
        if not self._video_capture.isOpened():
            print("Video capture is not opened.")
            return
        self._width = int(self._video_capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        self._height = int(self._video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT))