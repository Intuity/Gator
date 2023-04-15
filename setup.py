# Copyright 2023, Peter Birch, mailto:peter@lightlogic.co.uk
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from pathlib import Path
from setuptools import setup, find_packages

with open(Path(__file__).parent / "README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="gator",
    version="1.0",
    license="Apache License, Version 2.0",
    description="Job execution management and hierarchical logging",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Peter Birch",
    url="https://github.com/Intuity",
    project_urls={
        "Source": "https://github.com/Intuity/gator",
    },
    packages=find_packages(exclude=["tests"]),
    data_files=["LICENSE"],
    include_package_data=True,
    entry_points={
        "console_scripts": ["gator=gator.__main__:main"]
    },
    python_requires=">=3.7",
    install_requires=["click",
                      "plotly",
                      "psutil",
                      "pandas",
                      "kaleido",
                      "requests",
                      "flask",
                      "rich",
                      "tabulate",
                      "pyyaml"],
    setup_requires=["pytest-runner"],
    tests_require=["pytest", "pytest-cov", "pytest-mock"],
    extras_require={},
)