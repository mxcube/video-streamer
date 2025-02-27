import uvicorn
import argparse
import sys
import signal

from video_streamer.server import create_app
from video_streamer.core.config import get_config_from_dict, get_config_from_file, get_auth_config_from_dict


def handle_sigterm(signal, frame):
    print("Received SIGTERM, shutting down gracefully...")
    sys.exit(0)  # Exit the program with a clean status

def parse_args() -> argparse.Namespace:
    opt_parser = argparse.ArgumentParser(description="mxcube video streamer")

    opt_parser.add_argument(
        "-c",
        "--config",
        dest="config_file_path",
        help="Configuration file path",
        default="",
    )

    opt_parser.add_argument(
        "-uri",
        "--uri",
        dest="uri",
        help="Tango device URI",
        default="test",
    )

    opt_parser.add_argument(
        "-hs",
        "--host",
        dest="host",
        help=(
            "Host name to listen on for incomming client connections default (0.0.0.0)"
        ),
        default="0.0.0.0",
    )

    opt_parser.add_argument(
        "-p",
        "--port",
        dest="port",
        help="Port",
        default="8000",
    )

    opt_parser.add_argument(
        "-q",
        "--quality",
        dest="quality",
        help="Compression rate/quality",
        default=4,
    )

    opt_parser.add_argument(
        "-s",
        "--size",
        dest="size",
        help="size",
        default="0, 0",
    )

    opt_parser.add_argument(
        "-vf",
        "--vflip",
        action="store_true",
        dest="vertical_flip",
        help="Flip video vertically, default false",
        default=False,
    )

    opt_parser.add_argument(
        "-of",
        "--output-format",
        dest="output_format",
        help="output format, MPEG1 or MJPEG",
        default="MPEG1",
    )

    opt_parser.add_argument(
        "-id",
        "--id",
        dest="hash",
        help="Stream id",
        default="",
    )

    opt_parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        dest="debug",
        help="Debug true or false",
        default=False,
    )

    opt_parser.add_argument(
        "-r",
        "--redis",
        action="store_true",
        dest= "redis",
        help="Use redis-server",
        default=False,
    )

    opt_parser.add_argument(
        "-rhs",
        "--redis-host",
        dest= "redis_host",
        help="Host name of redis server to send to",
        default="localhost",
    )

    opt_parser.add_argument(
        "-rp",
        "--redis-port",
        dest= "redis_port",
        help="Port of redis server",
        default="6379",
    )

    opt_parser.add_argument(
        "-rk",
        "--redis-channel",
        dest= "redis_channel",
        help="Key for saving to redis database",
        default="video-streamer",
    )

    opt_parser.add_argument(
        "-irc",
        "--in_redis_channel",
        dest="in_redis_channel",
        help="Channel for RedisCamera to listen to",
        default="CameraStream",
    )

    opt_parser.add_argument(
        "-auth",
        "--auth_type",
        dest="auth_type",
        help="Type of authentication request",
        default=None,
    )

    opt_parser.add_argument(
        "-user",
        "--username",
        dest="username",
        help="Username for authentication request",
        default="",
    )

    opt_parser.add_argument(
        "-pass",
        "--password",
        dest="password",
        help="Password for authentication request",
        default="",
    )

    return opt_parser.parse_args()


def run() -> None:
    args = parse_args()

    if not args.debug:
        loglevel = "critical"
    else:
        loglevel = "info"

    _size = tuple(map(float, args.size.split(",")))
    _size = tuple(map(int, _size))

    if args.config_file_path:
        config = get_config_from_file(args.config_file_path)
    else:
        config_dict = {
            "sources": {
                "%s:%s"
                % (args.host, args.port): {
                    "input_uri": args.uri,
                    "quality": args.quality,
                    "format": args.output_format,
                    "hash": args.hash,
                    "size": _size,
                    "v_flip": args.vertical_flip,
                    "in_redis_channel": args.in_redis_channel,
                    "auth_config": get_auth_config_from_dict({
                        "type": args.auth_type,
                        "username": args.username,
                        "password": args.password
                    })
                }
            }
        }

        if args.redis:
            config_dict["sources"]["%s:%s" % (args.host, args.port)]["redis"] = "%s:%s" % (args.redis_host, args.redis_port)
            config_dict["sources"]["%s:%s" % (args.host, args.port)]["redis_channel"] = args.redis_channel
        
        config = get_config_from_dict(config_dict)

    for uri, source_config in config.sources.items():
        host, port = uri.split(":")

        app = create_app(source_config, host, int(port), debug=args.debug)

        if app:
            config = uvicorn.Config(
                app,
                host="0.0.0.0",
                port=int(port),
                reload=False,
                workers=1,
                log_level=loglevel,
            )

            signal.signal(signal.SIGTERM, handle_sigterm)
            signal.signal(signal.SIGINT, handle_sigterm)
            server = uvicorn.Server(config=config)
            server.run()


if __name__ == "__main__":
    run()
