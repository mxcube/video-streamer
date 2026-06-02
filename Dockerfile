FROM python:3.11

ENV DEBIAN_FRONTEND=noninteractive

RUN apt update && apt install -y --no-install-recommends ffmpeg libsm6 libxext6

RUN pip install mxcube-video-streamer[tango]
RUN pip install mxcube-video-streamer[epics]

ENTRYPOINT ["video-streamer"]
