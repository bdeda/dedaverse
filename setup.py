import os
import glob
from setuptools import setup, find_packages


setup(
    name="dedaverse",
    version="0.1.0",
    packages=find_packages('src'),
    package_dir={'': 'src'},
    py_modules=[os.path.splitext(os.path.basename(path))[0] for path in glob.glob('src/*.py')],
    include_package_data=True,    
)