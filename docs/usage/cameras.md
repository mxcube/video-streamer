# Cameras
Our streamer supports a variety of camera types, each designed to meet different streaming needs and setups. In this section, we provide an overview of the available camera types and how to configure the streamer depending on the type you use.
## The Input URI
The streamer automatically selects the appropriate mode for the camera based on the `input_uri` parameter (see [setup](setup.md) for instructions on how to configure this parameter). The table below provides an overview of how the `input_uri` should be structured for each camera type:

|Camera|Uri|
|----------|----------|
|TestCamera|`test`|
|VideoTestCamera|`videotest`|
|MJPEGCamera|Should start with `http://` and include host and port, e.g. `http://localhost:8000`|
|RedisCamera|Should start with `redis://` and include host and port of redis server, e.g. `redis://localhost:6379`|
|LimaCamera|URI of the Tango (Lima) device|
---

## TestCamera

The `TestCamera` is the simplest type of camera, continuously streaming the same static image. As a result, the generated stream displays a fixed image. To change the displayed image, replace the `fakeimg.jpg` file located in `/video_streamer/core`. Useful for testing, debugging and mockup versions of your application.

---

## VideoTestCamera

Similar to the `TestCamera`, this type of camera generates a stream from a prerecorded video instead of a static image. The video plays in an infinite loop. To change the video, replace the `testvideo.avi` file located in `video-streamer/core`. Ensure that the video is either uncompressed or compressed using the MJPEG codec; otherwise, the camera may encounter issues when reading the frames.

---

## LimaCamera

The `LimaCamera` supports streaming from a Tango (Lima) device. by polling the images from the devices `uri` and converting them into a stream in either *MJPEG* or *MPEG1* format. If no camera is specified, according to the input URI table defined [above](#the-input-uri) the application will automatically select this camera type. 

---

## MJPEGCamera

The `MJPEGCamera` provides specialized support for *MJPEG* video streams. It is designed to fetch images from an *MJPEG* stream, such as those from a web camera or a streaming url.

> **Note**: Currently the `MJPEGCamera` is the only camera that does not support conversion to a `Redis` Pub/Sub channel (more about streaming on a [redis channel](setup.md#dual-streaming-seamlessly-serve-mjpeg-and-redis-pubsub-video-feeds))

#### Authentication for MJPEG Streams

Some MJPEG streams may require authentication to access. To support such scenarios, the `MJPEGCamera` class includes built-in authentication support. Currently, both `Basic` and `Digest` authentication methods are supported.

Below is an example of how to use the video-streamer to access a stream requiring `Basic` authentication:

```bash
video-streamer -of MPEG1 -uri <stream_url> -auth Basic -user <username> -pass <password>
```

##### Explanation of the Parameters:
- `-of`: Specifies the ouput format, here `MPEG1` is used.
- `-uri`: The URL of the MJPEG stream.
- `-auth`: Specifies the authentication method (`Basic` or `Digest`)
- `-user`: The username for authentication
- `-pass`: The password required for authentication

Replace `<stream_url>`, `<username>` and `<password>` with the appropriate values for your stream. Ensure you handle credentials securely and avoid exposing them in public or shared scripts!

---

## RedisCamera

[Redis](https://redis.io/) Pub/Sub (Publish/Subscribe) is a messaging paradigm where publishers send messages to specific channels, and subscribers receive messages from the channels they are subscribed to. It is commonly used for real-time communication between applications or components.

Instead of using a real camera, the `video-streamer` allows to use said `Redis` Pub/Sub channel to create a stream in MPEG1 or MJPEG format.

#### Command Line Example
To use the `RedisCamera`, one can use the following command:

```bash
video-streamer -d -of MPEG1 -uri redis://[host]:[port] -irc ExampleStream
```

where `host` and `port` are the respective host and port of the `Redis` server and `ExampleStream` would be the Pub/Sub channel to use for generating the stream. 

#### Correct Format for Redis Camera

For the Camera to pick up your images and correctly format them into a stream in MJPEG or MPEG1 format. You should publish each image as a dictionary containing the `base64` encoded image data and the image size.

```python
    image_dict = {
        "data": [base64 encoded image],
        "size": [image size],
    }
```

#### Example Redis Pub/Sub communication

The following script is an example on how to send a stream via `Redis` Pub/Sub channel, so that the `video-streamer` can pick it up. 

```python
import redis
import time
from PIL import Image
import io
import base64
import json

REDIS_HOST = 'localhost'
REDIS_PORT = 6379
CHANNEL_NAME = 'ExampleStream'
IMAGE_PATH = './fakeimg.jpg' # path to your test image, adjust if necessary
PUBLISH_INTERVAL = 0.1

def load_image_as_bytes(image_path):
    """Load an image and convert it to bytes."""
    with Image.open(image_path) as img:
        size = (img.height, img.width)
        byte_stream = io.BytesIO()
        img.save(byte_stream, format=img.format)
        return byte_stream.getvalue(), size

def main():
    # Connect to Redis
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)
    
    # Load image as bytes and use correct format for the video-streamer
    image_data, image_size = load_image_as_bytes(IMAGE_PATH)
    image_dict = {
        "data": base64.b64encode(image_data).decode("utf-8"),
        "size": image_size,
    }
    try:
        while True:
            redis_client.publish(CHANNEL_NAME, json.dumps(image_dict))
            time.sleep(PUBLISH_INTERVAL)
    except KeyboardInterrupt:
        print("Stopped publishing.")

if __name__ == '__main__':
    main()

```

This script sends a *jpeg* image with a frame rate of 10 frames per second to the `ExampleStream` channel. With a `Redis` server running on `localhost:6379`