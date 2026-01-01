#!/usr/bin/env python3
"""
Setup script for MiniStatus-MVP
Alternative installation method using Python standard practices
"""

from setuptools import setup, find_packages
import os

# Read README for long description
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="ministatus-mvp",
    version="1.1.0",
    author="LieAndSmile",
    description="A lightweight, self-hosted service status dashboard",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/LieAndSmile/MiniStatus-MVP",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: System Administrators",
        "Topic :: System :: Monitoring",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        "Flask>=3.1.0",
        "Flask-SQLAlchemy>=3.1.1",
        "python-dotenv>=1.1.0",
        "psutil",
        "PyYAML",
        "requests>=2.32.0",
    ],
    entry_points={
        "console_scripts": [
            "ministatus=run:main",
        ],
    },
    include_package_data=True,
)

