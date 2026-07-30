"""
ICYQuant SDK - 机构级量化交易平台 Python SDK 安装脚本。

使用方式:
    pip install .
    pip install -e .
    pip install .[full]
    pip install .[dev]
"""

import os
import sys
from setuptools import setup, find_packages, Extension

here = os.path.abspath(os.path.dirname(__file__))


def read_requirements():
    """读取 requirements.txt 获取依赖列表。"""
    requirements = []
    req_file = os.path.join(here, "requirements.txt")
    if os.path.exists(req_file):
        with open(req_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    requirements.append(line)
    return requirements


def read_version():
    """从版本文件读取版本号。"""
    version_file = os.path.join(here, "src", "icyquant_sdk", "_version.py")
    if os.path.exists(version_file):
        with open(version_file, encoding="utf-8") as f:
            for line in f:
                if line.startswith("__version__"):
                    return line.split("=")[1].strip().strip('"').strip("'")
    return "0.4.0"


def check_python_version():
    """检查 Python 版本是否满足要求。"""
    if sys.version_info < (3, 9):
        raise RuntimeError(
            f"ICYQuant SDK requires Python >= 3.9, got {sys.version}. "
            f"Please upgrade your Python version."
        )


check_python_version()

setup(
    name="icyquant-sdk",
    version=read_version(),
    description="ICYQuant Platform Python SDK - 机构级量化交易平台软件开发工具包",
    long_description=open(os.path.join(here, "README.md"), encoding="utf-8").read()
    if os.path.exists(os.path.join(here, "README.md"))
    else "",
    long_description_content_type="text/markdown",
    author="ICYQuant Team",
    author_email="platform@icyquant.io",
    url="https://icyquant.io",
    project_urls={
        "Repository": "https://github.com/icyquant/icyquant",
        "Documentation": "https://docs.icyquant.io",
        "Issues": "https://github.com/icyquant/icyquant/issues",
        "Changelog": "https://github.com/icyquant/icyquant/releases",
    },
    license="MIT",
    python_requires=">=3.9",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    package_data={
        "icyquant_sdk": ["py.typed", "*.pyi"],
    },
    include_package_data=True,
    install_requires=[
        "httpx>=0.25.0",
        "pydantic>=2.0.0",
        "python-jose[cryptography]>=3.3.0",
        "cryptography>=41.0.0",
        "numpy>=1.24.0",
        "pandas>=2.0.0",
    ],
    extras_require={
        "full": [
            "websockets>=12.0",
            "redis>=5.0",
            "sqlalchemy>=2.0",
            "psycopg2-binary>=2.9",
            "kafka-python>=2.0",
        ],
        "dev": [
            "pytest>=7.0",
            "pytest-asyncio>=0.21",
            "pytest-cov>=4.0",
            "ruff>=0.1",
            "mypy>=1.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "icyquant-sdk=icyquant_sdk.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Financial and Insurance Industry",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Office/Business :: Financial",
        "Topic :: Scientific/Engineering :: Information Analysis",
    ],
    keywords=[
        "quant",
        "trading",
        "ai",
        "finance",
        "hedge-fund",
        "algorithmic-trading",
        "institutional",
    ],
    zip_safe=False,
    python_requires=">=3.9",
)