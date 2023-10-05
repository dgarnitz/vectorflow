from setuptools import setup

# Read the content of your README file
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="vectorflow-ai",
    version="0.1.1",  # Update version as needed
    install_requires=[
        # No dependencies right now since this is only for setting up docker-compose
    ],
    entry_points={
        'console_scripts': [
            'vectorflow=vectorflow:main',
        ],
    },
    py_modules=["vectorflow"],
    include_package_data=True,  # This ensures non-python files (like your setup.sh) are included
    long_description=long_description,
    long_description_content_type="text/markdown",  # This is important! It tells PyPI the README is in Markdown
)
