"""
Setup configuration for GT 2.0 API Standards package
"""

from setuptools import setup, find_packages

setup(
    name="gt2-api-standards",
    version="1.0.0",
    description="GT 2.0 Capability-Based REST (CB-REST) API Standards",
    author="GT Edge AI",
    author_email="engineering@gtedgeai.com",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.11",
    install_requires=[
        "fastapi>=0.104.0",
        "pydantic>=2.0.0",
        "pyjwt>=2.8.0",
        "python-jose[cryptography]>=3.3.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.1.0",
            "black>=23.0.0",
            "mypy>=1.5.0",
        ]
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)