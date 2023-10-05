from setuptools import setup

setup(
    name="vectorflow-ai",
    version="0.1.0",  # Update version as needed
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
)
