from setuptools import setup, find_packages

setup(
    name="devnet",
    version="2.0.0",
    description="Fully Local Super Agentic AI — Ollama powered",
    packages=find_packages(),
    package_data={
        "devnet": ["web/static/*.html"],
    },
    install_requires=[
        "ollama",
    ],
    extras_require={
        "dev": ["flake8", "black", "pytest", "pyinstaller"],
    },
    entry_points={
        "console_scripts": [
            "devnet=devnet.core.runner:main",
        ],
    },
    python_requires=">=3.9",
)
