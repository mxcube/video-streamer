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

from requests.auth import HTTPBasicAuth, HTTPDigestAuth
from video_streamer.core.config import AuthenticationConfiguration

class Camera:
    def __init__(self, device_uri: str, sleep_time: float, debug: bool = False, redis: str = None, redis_channel: str = None):
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
            self._redis_client = redis.StrictRedis(host=host, port=int(port))

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
    def size(self) -> Tuple[int, int]:
        return (self._width, self._height)

    def get_jpeg(self, data, size=(0, 0), v_flip=False) -> bytearray:
        jpeg_data = io.BytesIO()
        image = Image.frombytes("RGB", self.size, data, "raw")

        if size[0]:
            image = image.resize(size)

        if v_flip:
            image = image.transpose(Image.FLIP_TOP_BOTTOM)

        image.save(jpeg_data, format="JPEG")
        jpeg_data = jpeg_data.getvalue()

        return bytearray(jpeg_data)
    
    def _image_to_rgb24(self, image: bytes) -> bytearray:
        """
        Convert binary image data into raw RGB24-encoded byte array
        Supported image types include JPEG, PNG, BMP, TIFF, GIF, ...
        """
        image_array = np.frombuffer(image, dtype=np.uint8)
        frame = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return bytearray(rgb_frame.tobytes())


class MJPEGCamera(Camera):
    def __init__(self, device_uri: str, sleep_time: float, auth_config: AuthenticationConfiguration, debug: bool = False, redis: str = None, redis_channel: str = None):
        super().__init__(device_uri, sleep_time, debug, redis, redis_channel)
        self._authentication=self._createAuthenticationHeader(auth_config)
        self._set_size()

    def _set_size(self) -> None:
        buffer = bytearray()
        # To set the size, extract the first image from the MJPEG stream
        try:
            response = requests.get(self._device_uri, stream=True, verify=False, auth=self._authentication)
            if response.status_code == 200:
                boundary = self._extract_boundary(response.headers)
                if not boundary:
                    logging.error("Boundary not found in Content-Type header.")
                    return

                for chunk in response.iter_content(chunk_size=8192):
                    buffer.extend(chunk)

                    while True:
                        frame, buffer = self._extract_frame(buffer, boundary)
                        if frame is None:
                            break
                        image = Image.open(io.BytesIO(frame))
                        self._width, self._height = image.size
                        return
            else:
                logging.error(f"Received unexpected status code {response.status_code}")
                return
        except requests.RequestException as e:
            logging.exception(f"Exception occured during stream request")
            return

    def _createAuthenticationHeader(self, auth_config:AuthenticationConfiguration) -> Union[None, HTTPBasicAuth, HTTPDigestAuth]:
        type = auth_config.type
        if type == "Basic":
            return HTTPBasicAuth(username=auth_config.username, password=auth_config.password)
        elif type == "Digest":
            return HTTPDigestAuth(username=auth_config.username, password=auth_config.password)
        elif type:
            logging.warning("Unknown authentication Type {type}")
        return None

    def _extract_boundary(self, headers):
        """
        Extract the boundary marker from the Content-Type header.
        """
        content_type = headers.get("Content-Type", "")
        if "boundary=" in content_type:
            return content_type.split("boundary=")[-1]
        return None

    def _extract_frame(self, buffer: bytearray, boundary: str):
        """
        Extract a single JPEG frame from the buffer if a complete frame exists.
        Returns a tuple of (frame_data, remaining_buffer).
        """
        boundary_bytes = f"--{boundary}".encode()
        start_index = buffer.find(boundary_bytes)
        if start_index == -1:
            return None, buffer  # Boundary not found

        # Find the next boundary after the current one
        next_index = buffer.find(boundary_bytes, start_index + len(boundary_bytes))
        if next_index == -1:
            return None, buffer  # Complete frame not yet available

        # Extract the data between boundaries
        frame_section = buffer[start_index + len(boundary_bytes):next_index]

        # Separate headers and JPEG data
        header_end = frame_section.find(b"\r\n\r\n")  # End of headers
        if header_end == -1:
            return None, buffer  # Headers not fully received

        # Extract the JPEG data
        frame_data = frame_section[header_end + 4:]  # Skip past the headers
        remaining_buffer = buffer[next_index:]  # Data after the next boundary
        return frame_data.strip(), remaining_buffer  # Strip any extra whitespace

    def poll_image(self, output: Union[IO, multiprocessing.queues.Queue]) -> None:
        buffer = bytearray()
        self._output = output

        while True:
            try:
                response = requests.get(self._device_uri, stream=True, verify=False, auth=self._authentication)
                if response.status_code == 200:
                    boundary = self._extract_boundary(response.headers)
                    if not boundary:
                        logging.error("Boundary not found in Content-Type header.")
                        break

                    for chunk in response.iter_content(chunk_size=8192):
                        buffer.extend(chunk)

                        while True:
                            frame, buffer = self._extract_frame(buffer, boundary)
                            if frame is None:
                                break
                            self._write_data(self._image_to_rgb24(bytes(frame)))
                else:
                    logging.error(f"Received unexpected status code {response.status_code}")
                    break
            except requests.RequestException as e:
                logging.exception(f"Exception occured during stream request")
                break


class LimaCamera(Camera):

    # Image modes in LImA. Supporting only Y8 and RGB24 for now.
    IMAGE_MODE_Y8 = 0
    IMAGE_MODE_RGB24 = 6

    def __init__(self, device_uri: str, sleep_time: float, debug: bool = False, redis: str = None, redis_channel: str = None):
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
        
    def _convert_to_rgb24(self, raw_image: bytearray, image_mode: int, width: int, height: int) -> bytearray:
        """Converts image's byte representation to RGB24 format, which is used by ffmpeg streaming process.

        Args:
            raw_image: image as bytes
            image_mode: LImA image mode
            width: width of image
            height: height of image
        Raises:
            NotImplementedError: unsupported image mode
        Returns:
            image as bytes in RGB24 format
        """
        if image_mode == self.IMAGE_MODE_Y8:
            raw_image = raw_image[:width * height]
            gray_img = Image.frombytes("L", (width, height), raw_image)
            rgb_img = gray_img.convert("RGB")
            return rgb_img.tobytes()
        elif image_mode == self.IMAGE_MODE_RGB24:
            # In RGB24 mode, we expect width*height*3 bytes.
            expected_bytes = width * height * 3
            return raw_image[:expected_bytes]
        else:
            logging.error(f"Unsupported image mode: {image_mode}")
            raise NotImplementedError(f"Conversion for image mode {image_mode} not implemented.")

    def _get_image(self) -> Tuple[bytearray, int, int, int]:
        """Gets a single image from the Tango device.
        
        Returns:
            raw_data: image as bytes
            width: width of image
            height: height of image
            frame_number: frame number of the image
        """
        img_data = self._lima_tango_device.video_last_image

        # Header format for `video_last_image` attribute in LImA.
        hfmt = ">IHHqiiHHHH"
        hsize = struct.calcsize(hfmt)
        header_fields = struct.unpack(hfmt, img_data[1][:hsize])
        (
            _magic_number,
            _version, 
            image_mode, 
            frame_number, 
            width, 
            height, 
            _endianness, 
            _header_size, 
            _padding, 
            _padding2
        ) = header_fields

        raw_data = self._convert_to_rgb24(
            raw_image=img_data[1][hsize:],
            image_mode=image_mode,
            width=width,
            height=height
            )
        
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
    def __init__(self, device_uri: str, sleep_time: float, debug: bool = False, out_redis: str = None, out_redis_channel: str = None, in_redis_channel: str = 'frames'):
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
                self._write_data(self._image_to_rgb24(raw_image_data))

class TestCamera(Camera):
    def __init__(self, device_uri: str, sleep_time: float, debug: bool = False, redis: str = None, redis_channel: str = None):
        super().__init__(device_uri, sleep_time, debug, redis, redis_channel)
        self._sleep_time = 0.05
        testimg_fpath = os.path.join(os.path.dirname(__file__), "fakeimg.jpg")
        self._im = Image.open(testimg_fpath, "r")

        self._raw_data = self._im.convert("RGB").tobytes()
        self._width, self._height = self._im.size
        self._last_frame_number = -1

    def _poll_once(self) -> None:
        self._write_data(bytearray(self._raw_data))
        
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
    def __init__(self, device_uri: str, sleep_time: float, debug: bool = False, redis: str = None, redis_channel: str = None):
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
            logging.error("Video capture is not opened.")
            return
        
        ret, frame = self._video_capture.read()
        if not ret:
            # End of video, loop back to the beginning
            self._video_capture.release()
            self._video_capture = cv2.VideoCapture(self._testvideo_fpath)
            ret, frame = self._video_capture.read()
            if not ret:
                logging.error("Failed to restart video capture.")
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
            logging.error("Video capture is not opened.")
            return
        self._width = int(self._video_capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        self._height = int(self._video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT))