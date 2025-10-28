from setuptools import setup, find_packages

setup(
    name="enclave",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "cryptography>=41.0.0",
        "prompt-toolkit>=3.0.0",
        "msgpack>=1.0.0",
    ],
    extras_require={
        'web': [
            "flask>=3.0.0",
            "flask-socketio>=5.3.0",
            "python-socketio>=5.10.0",
            "flask-cors>=4.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "enclave=enclave.main:main",
            "enclave-web=enclave.web_launcher:main",
        ],
    },
    python_requires=">=3.8",
    include_package_data=True,
    package_data={
        'enclave': ['../web/templates/*', '../web/static/css/*', '../web/static/js/*'],
    },
)
