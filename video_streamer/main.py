import uvicorn
import argparse
import multiprocessing

from video_streamer.server import create_app
from video_streamer.core.config import get_config_from_dict, get_config_from_file


def parse_args() -> None:
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
        help="Host name to listen on for incomming client connections defualt (0.0.0.0)",
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
        help="Compresion rate/quality",
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
        "-of",
        "--output-format",
        dest="output_format",
        help="output format, MPEG1 or MJPEG1",
        default="MPEG1",
    )

    opt_parser.add_argument(
        "-id",
        "--id",
        dest="hash",
        help="Sream id",
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

    return opt_parser.parse_args()


def run() -> None:
    args = parse_args()

    if not args.debug:
        loglevel = "critical"
    else:
        loglevel = "info"

    if args.config_file_path:
        config = get_config_from_file(args.config_file_path)
    else:
        config = get_config_from_dict(
            {
                "sources": {
                    "%s:%s"
                    % (args.host, args.port): {
                        "input_uri": args.uri,
                        "quality": args.quality,
                        "format": args.output_format,
                        "hash": args.hash,
                        "size": args.size.split(","),
                    }
                }
            }
        )

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

            server = uvicorn.Server(config=config)
            server.run()

if __name__ == "__main__":
    run()
