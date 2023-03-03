# video-streamer
Video streamer for MXCuBE


### Installation

```
git clone https://github.com/mxcube/video-streamer.git
cd video-streamer

# optional 
conda env create -f conda-environment.yml

# For development
pip install -e .

# For usage 
pip install .
```

### Usage
```
usage: video-streamer [-h] [-c CONFIG_FILE_PATH] [-tu TANGO_URI] [-hs HOST] [-p PORT] [-q QUALITY] [-of OUTPUT_FORMAT] [-id HASH]
                      [-d DEBUG]

options:
  -h, --help            show this help message and exit
  -c CONFIG_FILE_PATH, --config CONFIG_FILE_PATH
                        Configuration file path
  -tu TANGO_URI, --tango-uri TANGO_URI
                        Tango device URI
  -hs HOST, --host-name HOST
                        host
  -p PORT, --port PORT  port
  -q QUALITY, --quality QUALITY
                        Compresion rate/quality
  -of OUTPUT_FORMAT, --output-format OUTPUT_FORMAT
                        output format, MPEG1 or MJPEG1
  -id HASH, --id HASH   Sream id
  -d DEBUG, --debug DEBUG
                        Debug true or false
```

There is the possibility to use a configuration file instead of command line arguments. All 
command line arguments except debug are ignored if a config file is used. The configuration 
file also makes it possible to configure several sources while the command line only allows 
configuration of a single source.

#### Example configuration file (config.json):
The configuration file format is JSON. A test image is used when the input_uri is set to "test".
The example below creates one MPEG1 stream and one MJPEG stream from the test image. There is a
defualt test/demo UI to see the video stream on http://localhost:[port]/ui. In example below case:
  
 MPEG1: http://localhost:8000/ui
 
 MJPEG: http://localhost:8001/ui

```
{
    "sources": {
        "0.0.0.0:8000": {
            "input_uri": "test",
            "quality": 4,
            "format": "MPEG1"
        },
        "0.0.0.0:8000": {
            "input_uri": "test",
            "quality": 4,
            "format": "MJPEG"
        }
    }
}
```
  
