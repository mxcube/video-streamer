# Installation

1. Start by cloning the repository to your local machine:

        git clone https://github.com/mxcube/video-streamer.git
        cd video-streamer

1. Optionally, you can create and activate a [conda](https://docs.conda.io/projects/conda/en/latest/index.html) environment like this:

        conda env create -f conda-environment.yml
        conda activate video-streamer
    
    If you skip this part, please make sure to have all necessary packages from `conda-environment.yml` installed.

1. Install all dependencies necessary for the code to run; either with pip:

        # for development
        pip install -e .

        #for usage
        pip install .

    or poetry:

        poetry install