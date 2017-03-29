from setuptools import *

description = 'Extended web remote control interface for VLC'

setup(
    name='vlcc',
    version='1.0.0a1',
    description=description,
    long_description=description,
    url='https://github.com/baliame/vlcc',
    author='Baliame',
    author_email='akos.toth@cheppers.com',
    license='MIT',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Topic :: Software Development :: User Interfaces',
    ],
    keywords='vlc remote control interface',
    packages=find_packages(),
    install_requires=[
    ],
    entry_points={
        'console_scripts': ['vlcc=vlcc.vlcc:main'],
    }
)
