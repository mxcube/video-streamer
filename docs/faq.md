# FAQ

1. I use this application as part of the [web interface](http://github.com/mxcube/mxcubeweb) for MXCuBE; Unfortunately there is no stream output, what can I do?

    One possible issue could be a missing dependency for the `video-streamer`, especially `ffmpeg` is not correctly installed when the `video-streamer` is used as a dependency. You can try to fix this by simply installing `ffmpeg`.

1. What types of output streams are supported?

    Currently, *MJPEG* and *MPEG1* streams are supported, as well as the possibility to use a redis Pub/Sub channel as output. For more information about using the dual output stream with `Redis` you can read our [setup guide](./usage/setup.md#dual-streaming-seamlessly-serve-mjpeg-and-redis-pubsub-video-feeds).

1. What types of input devices are supported?

    MXCuBE's Video Streamer supports a wide range of input devices, such as Tango (Lima) devices, MJPEG streams and Redis channels, as well as prerecorded videos and even single images for test streams. For more information on the supported devices and streams, you can read the [cameras guide](./usage/cameras.md)