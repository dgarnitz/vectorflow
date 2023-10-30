from setuptools import setup, find_packages

setup(
    name="vectorflow-client",
    version="0.0.2",
    packages=find_packages(where="client") + ["shared"],
    package_dir={"": "client", "shared": "src/shared"},
    install_requires=[
        'requests==2.31.0'
    ],
    include_package_data=True,  # This is the line that reads the MANIFEST.in
)
