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

mxcube-web Backend server command line utility.

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

    
  
