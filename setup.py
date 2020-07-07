from setuptools import setup, find_packages
import pathlib

here = pathlib.Path(__file__).parent.resolve()

long_description = (here / "README.md").read_text(encoding="utf-8")

setup(
    name="pledger",  # Required
    version="1.0.0",  # Required
    description="Fetch and convert Plaid data to Ledger format",  # Optional
    long_description=long_description,  # Optional
    long_description_content_type="text/markdown",  # Optional (see note above)
    url="https://github.com/guerarda/pledger",  # Optional
    author="Alex Guerard",  # Optional
    author_email="alex@guerard.xyz",  # Optional
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3 :: Only",
    ],
    keywords="ledger, plaid, accounting",  # Optional
    packages=find_packages(),  # Required
    python_requires=">=3.6, <4",
    install_requires=["plaid-python"],  # Optional
    entry_points={"console_scripts": ["pledger=pledger:main",],},  # Optional
    project_urls={  # Optional
        "Bug Reports": "https://github.com/guerarda/pledger/issues",
        "Source": "https://github.com/guerarda/pledger/",
    },
)
