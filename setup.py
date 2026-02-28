"""
This configuration file manages the installation and packaging of AXONIX-ZERO.
It defines dependencies, entry points, and metadata required to distribute 
the application professionally as a Python package.
"""

from setuptools import setup, find_packages

setup(
    name="axonix",
    version="1.0.0",
    author="AKIK FARAJI",
    author_email="akikfaraji@gmail.com",
    description="AXONIX-ZERO: A premium, fully autonomous local AI coding agent.",
    long_description=open("README.md").read() if open("README.md") else "",
    long_description_content_type="text/markdown",
    url="https://github.com/Akik-Forazi/AXONIX",
    packages=find_packages(),
    package_data={
        "axonix": ["web/static/*.html"],
    },
    install_requires=[
        "ollama",
        "llama-cpp-python",
    ],
    extras_require={
        "dev": ["flake8", "black", "pytest", "pyinstaller"],
    },
    entry_points={
        "console_scripts": [
            "axonix=axonix.core.runner:main",
        ],
    },
    python_requires=">=3.10",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: Other/Proprietary License",
        "Operating System :: Microsoft :: Windows",
        "Programming Language :: Python :: 3.10",
    ],
)
