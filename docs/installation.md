# Installation

Start by cloning the repository to your local machine:

```bash
git clone https://github.com/mxcube/video-streamer.git
cd video-streamer
```

Optionally you can create a [conda](https://docs.conda.io/projects/conda/en/latest/index.html) environment like this:

```bash
conda env create -f conda-environment.yml
```

Install all dependencies necessary for the code to run either with pip:

```bash
# for development
pip install -e .

#for usage
pip install .
```

or poetry:
```bash
poetry install
```