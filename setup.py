from setuptools import setup, find_packages

setup(
    name="axonix",
    version="1.0.0",
    description="Axonix — Fully Local Super Agentic AI",
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
)
