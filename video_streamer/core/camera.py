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

from typing import Union, IO, Tuple

from PIL import Image

try:
    from PyTango import DeviceProxy
except ImportError:
    logging.warning("PyTango not available.")


class Camera:
    def __init__(self, device_uri: str, sleep_time: int, debug: bool = False, redis: str = None, redis_channel: str = None, save_folder: str = None):
        self._device_uri = device_uri
        self._sleep_time = sleep_time
        self._debug = debug
        self._width = -1
        self._height = -1
        self._output = None
        self._redis = redis
        self._redis_channel = redis_channel
        self._save_folder = save_folder

        if self._save_folder and not os.path.exists(self._save_folder):
            os.makedirs(self._save_folder)

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
    def __init__(self, device_uri: str, sleep_time: int, debug: bool = False, redis: str = None, redis_channel: str = None, save_folder: str = None):
        super().__init__(device_uri, sleep_time, debug, redis, redis_channel, save_folder)

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
    def __init__(self, device_uri: str, sleep_time: int, debug: bool = False, redis: str = None, redis_channel: str = None, save_folder: str = None):
        super().__init__(device_uri, sleep_time, debug, redis, redis_channel, save_folder)

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
                self._redis_client.publish(self._redis_channel, self._raw_data)
            
            if self._save_folder:
                img = Image.frombytes("RGB", ( width, height ), raw_data, "raw")
                img.save(os.path.join(self._save_folder, 'img'+ str(frame_number) + '.jpg'), format="JPEG")

        time.sleep(self._sleep_time / 2)


class TestCamera(Camera):
    def __init__(self, device_uri: str, sleep_time: int, debug: bool = False, redis: str = None, redis_channel: str = None, save_folder: str = None):
        super().__init__(device_uri, sleep_time, debug, redis, redis_channel, save_folder)
        self._sleep_time = 0.05
        testimg_fpath = os.path.join(os.path.dirname(__file__), "fakeimg.jpg")
        self._im = Image.open(testimg_fpath, "r")
        self.counter = 0
        self._raw_data = self._im.convert("RGB").tobytes()
        self._width, self._height = self._im.size

    def _poll_once(self) -> None:
        self._write_data(self._raw_data)
        
        if self._redis:
            self._redis_client.publish(self._redis_channel, self._raw_data)
        
        if self._save_folder:
            img = Image.frombytes("RGB", self._im.size, self._raw_data, "raw")
            img.save(os.path.join(self._save_folder, 'img'+ str(self.counter) + '.jpg'), format='JPEG')
            self.counter+=1

        time.sleep(self._sleep_time)
