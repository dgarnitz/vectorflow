from setuptools import setup

setup(
    name="vectorflow",
    version="0.1.0",  # Update version as needed
    install_requires=[
        # List your project dependencies here if any
    ],
    entry_points={
        'console_scripts': [
            'vectorflow=vectorflow:main',
        ],
    },
    py_modules=["vectorflow"],
    include_package_data=True,  # This ensures non-python files (like your setup.sh) are included
)
