import os
import uvicorn
import argparse
import multiprocessing

from video_streamer.server import create_app
from video_streamer.core.config import get_config_from_dict, get_config_from_file


def parse_args() -> None:
    opt_parser = argparse.ArgumentParser(
        description="mxcube-web Backend server command line utility."
    )

    opt_parser.add_argument(
        "-c",
        "--config",
        dest="config_file_path",
        help="Configuration file path",
        default="",
    )

    opt_parser.add_argument(
        "-tu",
        "--tango-uri",
        dest="tango_uri",
        help="Tango device URI",
        default="test",
    )

    opt_parser.add_argument(
        "-hs",
        "--host-name",
        dest="host",
        help="host",
        default="0.0.0.0",
    )

    opt_parser.add_argument(
        "-p",
        "--port",
        dest="port",
        help="port",
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
        dest="debug",
        help="Debug true or false",
        default=False,
    )

    return opt_parser.parse_args()


def run() -> None:
    args = parse_args()

    if args.config_file_path:
        config = get_config_from_file(args.config_file_path)
    else:
        config = get_config_from_dict(
            {
                "sources": {
                    "%s:%s"
                    % (args.host, args.port): {
                        "input_uri": args.tango_uri,
                        "quality": args.quality,
                        "format": args.output_format,
                        "hash": args.hash,
                    }
                }
            }
        )

    for uri, source_config in config.sources.items():
        host, port = uri.split(":")
        app = create_app(source_config, host, int(port), debug=args.debug)

        if app:
            config = uvicorn.Config(
                app, host=host, port=int(port), reload=False, workers=1
            )

            server = uvicorn.Server(config=config)
            server.run()

            p = multiprocessing.Process(
                target=server.run,
            )

            p.start()


if __name__ == "__main__":
    run()
