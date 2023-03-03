import subprocess
import multiprocessing
import queue

from video_streamer.core.camera import TestCamera, LimaCamera
from video_streamer.core.config import SourceConfiguration


class Streamer:
    def __init__(self, config: SourceConfiguration, host: str, port: int, debug: bool):
        self._config = config
        self._host = host
        self._port = port
        self._debug = debug

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass


class MJPEGStreamer(Streamer):
    def __init__(self, config: SourceConfiguration, host: str, port: int, debug: bool):
        super().__init__(config, host, port, debug)
        self._poll_image_p = None

        if self._config.input_uri == "test":
            self._camera = TestCamera("TANGO_URI", 0.02, False)
        else:
            self._camera = LimaCamera(self._config.input_uri, 0.02, False)

    def start(self) -> None:
        _q = multiprocessing.Queue(1)

        self._poll_image_p = multiprocessing.Process(
            target=self._camera.poll_image, args=(_q,)
        )
        self._poll_image_p.start()

        last_frame = _q.get()

        while True:
            try:
                _data = _q.get_nowait()
            except queue.Empty:
                pass
            else:
                last_frame = _data

            yield (
                b"--frame\r\n"
                b"--!>\nContent-type: image/jpeg\n\n"
                + self._camera.get_jpeg(last_frame)
                + b"\r\n"
            )

    def stop(self) -> None:
        if self._poll_image_p:
            self._poll_image_p.kill()


class FFMPGStreamer(Streamer):
    def __init__(self, config: SourceConfiguration, host: str, port: int, debug: bool):
        super().__init__(config, host, port, debug)
        self._ffmpeg_process = None
        self._poll_image_p = None

    def _start_ffmpeg(
        self,
        size: Tuple[float, float],
        scale: Tuple[float, float],
        quality: int = 4,
        port: int = 8000,
    ) -> None:
        """
        Start encoding with ffmpeg and stream the video with the node
        websocket relay.

        :param str scale: Video width and height
        :returns: Processes performing encoding
        :rtype: tuple
        """

        size = "%sx%s" % size
        w, h = scale

        ffmpeg_args = [
            "ffmpeg",
            "-fflags",
            "nobuffer",
            "-fflags",
            "discardcorrupt",
            "-flags",
            "low_delay",
            "-f",
            "rawvideo",
            "-pixel_format",
            "rgb24",
            "-s",
            size,
            "-i",
            "-",
            "-f",
            "mpegts",
            "-q:v",
            "%s" % quality,
            "-vcodec",
            "mpeg1video",
            "http://127.0.0.1:%s/video_input/" % port,
        ]

        stderr = subprocess.DEVNULL if not self._debug else subprocess.STDOUT

        ffmpeg = subprocess.Popen(
            ffmpeg_args,
            stderr=stderr,
            stdin=subprocess.PIPE,
            shell=False,
            close_fds=False,
        )

        return ffmpeg

    def start(self) -> None:
        if self._config.input_uri == "test":
            camera = TestCamera("TANGO_URI", 0.02, False)
        else:
            camera = LimaCamera(self._config.input_uri, 0.02, False)

        ffmpeg_p = self._start_ffmpeg(
            camera.size, (1, 1), self._config.quality, self._port
        )

        self._poll_image_p = multiprocessing.Process(
            target=camera.poll_image, args=(ffmpeg_p.stdin,)
        )

        self._poll_image_p.start()
        self._ffmpeg_process = ffmpeg_p
        return ffmpeg_p

    def stop(self) -> None:
        if self._ffmpeg_process:
            self._ffmpeg_process.kill()

        if self._poll_image_p:
            self._poll_image_p.kill()
