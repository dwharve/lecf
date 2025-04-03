"""Setup script for the LECF package."""

from setuptools import find_packages, setup

# Get version from package
with open("lecf/__init__.py", "r", encoding="utf-8") as f:
    for line in f:
        if line.startswith("__version__"):
            version = line.split("=")[1].strip().strip("'\"")
            break
    else:
        version = "0.0.1"

# Get long description from README
with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

# Get requirements
with open("requirements.txt", "r", encoding="utf-8") as f:
    requirements = [
        line.strip() for line in f.readlines() if line.strip() and not line.startswith("#")
    ]

setup(
    name="lecf",
    version=version,
    description="Let's Encrypt Certificate Manager with Cloudflare DNS",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Your Name",
    author_email="your.email@example.com",
    url="https://github.com/yourusername/lecf",
    packages=find_packages(),
    include_package_data=True,
    install_requires=requirements,
    scripts=["bin/lecf"],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Internet :: WWW/HTTP :: Site Management",
        "Topic :: Security :: Cryptography",
        "Topic :: System :: Systems Administration",
    ],
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "lecf=lecf.cli:main",
        ],
    },
)
