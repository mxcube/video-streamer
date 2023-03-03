import uvicorn
import argparse
import multiprocessing

from video_streamer.server import create_app
from video_streamer.core.config import get_config


def parse_args() -> None:
    opt_parser = argparse.ArgumentParser(
        description="mxcube-web Backend server command line utility."
    )

    opt_parser.add_argument(
        "-c",
        "--config",
        dest="config_file_path",
        help="Configuration file path",
        default="config.json",
    )

    return opt_parser.parse_args()


def run() -> None:
    args = parse_args()
    config = get_config(args.config_file_path)

    for uri, source_config in config.sources.items():
        host, port = uri.split(":")
        app = create_app(source_config, host, int(port))

        if app:
            config = uvicorn.Config(
                app, host=host, port=int(port), reload=False, workers=1
            )

            server = uvicorn.Server(config=config)

            p = multiprocessing.Process(
                target=server.run,
            )

            p.start()


if __name__ == "__main__":
    run()
