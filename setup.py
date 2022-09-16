"""pyar3 Setup"""

from setuptools import setup, find_packages

VERSION = "0.0.21"

setup(name='pyar3',
      version=VERSION,
      url='https://https://github.com/roland-donat/pyar3',
      author='Roland Donat',
      author_email='roland.donat@gmail.com, roland.donat@edgemind.net, roland.donat@alphabayes.fr',
      maintainer='Roland Donat',
      maintainer_email='roland.donat@gmail.com',
      keywords='Altarica3',
      classifiers=[
          'Development Status :: 3 - Alpha',
          'Intended Audience :: Science/Research',
          'License :: OSI Approved :: MIT License',
          'Operating System :: POSIX :: Linux',
          'Programming Language :: Python :: 3.8',
          'Topic :: Scientific/Engineering :: Artificial Intelligence'
      ],
      packages=find_packages(
          exclude=[
              "*.tests",
              "*.tests.*",
              "tests.*",
              "tests",
              "log",
              "log.*",
              "*.log",
              "*.log.*"
          ]
      ),
      description='Open Altarica 3 Python Tools',
      license='MIT',
      platforms='ALL',
      python_requires='>=3.8',
      install_requires=[
          "pandas>=1.4.4",
          "pydantic>=1.10.2",
          "xlsxwriter",
          "lxml",
          "colored",
      ],
      zip_safe=False,
      scripts=[
          'bin/ar3sto2xls',
          'bin/ar3simu',
      ],
      )
