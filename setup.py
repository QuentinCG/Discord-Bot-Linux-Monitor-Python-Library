from setuptools import setup # type: ignore
import io

with io.open(file='README.md', mode='r', encoding='utf-8') as readme_file:
  readme = readme_file.read()

setup(
    name="DiscordBotLinuxMonitor",
    version="1.3.0",
    description="From discord channels: Get information and warning status of Linux server like service, port, ping, ssl certificate, disk/folder/cpu/ram/swap usage, ip connection, ... (Python and shell library, Linux ONLY)",
    long_description=readme,
    long_description_content_type="text/markdown",
    url='https://github.com/QuentinCG/Discord-Bot-Linux-Monitor-Python-Library',
    packages=['discordbotlinuxmonitor'],
    author='Quentin Comte-Gaz',
    author_email='quentin@comte-gaz.com',
    license='MIT',
    classifiers=[
        "Programming Language :: Python :: 3 :: Only",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Natural Language :: English",

        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",

        "Topic :: System :: Monitoring",
        "Topic :: System :: Networking :: Monitoring",
        "Topic :: System :: Systems Administration",

        "Development Status :: 5 - Production/Stable",

        "Environment :: Console"
    ],
    python_requires='>=3.3',
    keywords='discord bot warning info linux monitor monitoring server service port ping ssl certificate disk folder cpu ram swap usage ip connection',
    platforms='Linux',
    install_requires=[
        "linuxmonitor~=1.3.0",  # follows the {MAJOR}.{MINOR}.x version range (because LinuxMonitor and DiscordBotLinuxMonitor are tightly coupled and should have same major and minor version)
        "discord.py",
        "typing",
        "asyncio",
    ]
)
