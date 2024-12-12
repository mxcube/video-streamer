# FAQ

## Troubleshooting

1. I use this application as part of the [web interface](http://github.com/mxcube/mxcubeweb) for MXCuBE; Unfortunately there is no stream output, what can I do?

    One possible issue could be a missing dependency for the `video-streamer`, especially `ffmpeg` is not correctly installed when the `video-streamer` is used as a dependency. You can try to fix this by simply installing `ffmpeg`.

2. I do see a stream, however after a few seconds the server connection closes and the stream blocks, what can I do?

    This could mean that the video-streamer is not keeping up with the frame rate of your camera. A fast way to check if that is the case is by changing the hardcoded `_expt` value in the `streamer.py` file. Depending on the used format (*MJPEG* or *MPEG1*), you need to look for this value on the corresponding streamer's (`MJPEGStreamer` for *MJPEG*, `FFMPEGStreamer` for *MPEG1*) `__init__` function. For higher frame rates, reduce the value and re-run your server.

    *Detailed Explanation:* The `expt` value represents the latency value for the streamer to pick up the images from the camera object and converting them into the corresponding stream. If the value is too high, the streamer misses frames, if it is too low, the streamer will pick up images more often than it needs too, possibly resolving in overheating.

## Supported Features

1. What types of output streams are supported?

    Currently, *MJPEG* and *MPEG1* streams are supported, as well as the possibility to use a redis Pub/Sub channel as output. For more information about using the dual output stream with `Redis` you can read our [setup guide](./usage/setup.md#dual-streaming-seamlessly-serve-mjpeg-and-redis-pubsub-video-feeds).

1. What types of input devices are supported?

    MXCuBE's Video Streamer supports a wide range of input devices, such as Tango (Lima) devices, MJPEG streams and Redis channels, as well as prerecorded videos and even single images for test streams. For more information on the supported devices and streams, you can read the [cameras guide](./usage/cameras.md)