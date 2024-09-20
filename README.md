# Discord Bot Linux Monitor (Python library)
[![PyPI version](https://badge.fury.io/py/DiscordBotLinuxMonitor.svg)](https://pypi.org/project/DiscordBotLinuxMonitor/) [![License: MIT](https://img.shields.io/badge/License-MIT-brightgreen.svg)](https://github.com/QuentinCG/Discord-Bot-Linux-Monitor-Python-Library/blob/master/LICENSE.md) [![Donate](https://img.shields.io/badge/Donate-PayPal-blue.svg)](https://paypal.me/QuentinCG) [![Downloads](https://static.pepy.tech/badge/DiscordBotLinuxMonitor)](https://pepy.tech/project/DiscordBotLinuxMonitor) [![Downloads](https://static.pepy.tech/badge/DiscordBotLinuxMonitor/month)](https://pepy.tech/project/DiscordBotLinuxMonitor)

## What is it

This python library is designed to be used as a Linux service to monitor the Linux server manually with discord commands and to send warning or information of the Linux server status to a discord channel periodically (if relevant).

It is possible to have separate 'private discord channel' and 'public discord channel' for:
 - Sendind discord commands to the bot (visual example in next section)
 - Getting periodic status of the Linux server (doing periodically some commands from next section)
 - Getting warnings if there is an issue in the Linux server (periodic status check)

Example of warning:
  <img src="https://raw.githubusercontent.com/QuentinCG/Discord-Bot-Linux-Monitor-Python-Library/master/example/warning_from_periodic_check.jpg" height="400">

It is compatible with python 3+ and usable only on Linux.

<img src="https://raw.githubusercontent.com/QuentinCG/Discord-Bot-Linux-Monitor-Python-Library/master/discord.png" width="300">

## List of Discord commands:

### Public and private discord channel commands
Displayed infos are not the same if you do the command in private or public channel (all info are displayed in private channel, some are hidden from public channels)

 - `/usage`: 📊 View disk space, CPU, RAM, ... 📊
 <img src="https://raw.githubusercontent.com/QuentinCG/Discord-Bot-Linux-Monitor-Python-Library/master/example/usage.jpg" height="400">

 - `/os_infos`: 🖥 View basic system information 🖥
 <img src="https://raw.githubusercontent.com/QuentinCG/Discord-Bot-Linux-Monitor-Python-Library/master/example/os_infos.jpg" height="300">

 - `/ping`: 🌐 Ping websites 🌐
 <img src="https://raw.githubusercontent.com/QuentinCG/Discord-Bot-Linux-Monitor-Python-Library/master/example/ping.jpg" height="150">

 - `/websites`: 🌐 Check websites access (GET requests) 🌐
 <img src="https://raw.githubusercontent.com/QuentinCG/Discord-Bot-Linux-Monitor-Python-Library/master/example/websites.jpg" height="150">

 - `/certificates`: 🔒 Check SSL certificates 🔒
 <img src="https://raw.githubusercontent.com/QuentinCG/Discord-Bot-Linux-Monitor-Python-Library/master/example/certificates.jpg" height="400">

 - `/services_status`: 🩺 Check services are running 🩺
 <img src="https://raw.githubusercontent.com/QuentinCG/Discord-Bot-Linux-Monitor-Python-Library/master/example/services_status.jpg" height="150">

 - `/restart_all`: 🚀 Restart all services 🚀
 <img src="https://raw.githubusercontent.com/QuentinCG/Discord-Bot-Linux-Monitor-Python-Library/master/example/restart_all.jpg" height="150">

 - `/restart_service {service_name}`: 🚀 Restart a service 🚀
 <img src="https://raw.githubusercontent.com/QuentinCG/Discord-Bot-Linux-Monitor-Python-Library/master/example/restart_service.jpg" height="150">

 - `/stop_service {service_name}`: 🚫 Stop a service 🚫

 - `/list_services`: 📋 List all available services 📋
 <img src="https://raw.githubusercontent.com/QuentinCG/Discord-Bot-Linux-Monitor-Python-Library/master/example/list_services.jpg" height="150">

 - `/ports`: 🔒 Check ports 🔒
 <img src="https://raw.githubusercontent.com/QuentinCG/Discord-Bot-Linux-Monitor-Python-Library/master/example/ports.jpg" height="200">


### Private discord channel commands:
 - `/force_sync`: 🔄 Force discord command synchronization 🔄
 <img src="https://raw.githubusercontent.com/QuentinCG/Discord-Bot-Linux-Monitor-Python-Library/master/example/force_sync.jpg" height="300">

 - `/users`: 👥 View connected users 👥
 <img src="https://raw.githubusercontent.com/QuentinCG/Discord-Bot-Linux-Monitor-Python-Library/master/example/users.jpg" height="150">

 - `/user_logins`: 👥 View last user connections 👥
 <img src="https://raw.githubusercontent.com/QuentinCG/Discord-Bot-Linux-Monitor-Python-Library/master/example/user_logins.jpg" height="150">

 - `/reboot_server`: 🔄 Restart the entire server 🔄
 <img src="https://raw.githubusercontent.com/QuentinCG/Discord-Bot-Linux-Monitor-Python-Library/master/example/reboot_server.jpg" height="100">

 - `/list_processes`: 📋 List active processes 📋
 <img src="https://raw.githubusercontent.com/QuentinCG/Discord-Bot-Linux-Monitor-Python-Library/master/example/list_processes.jpg" height="200">

 - `/kill_process`: 🚫 Stop a process by PID 🚫
 <img src="https://raw.githubusercontent.com/QuentinCG/Discord-Bot-Linux-Monitor-Python-Library/master/example/kill_process.jpg" height="200">

## How to install (for first launch)

  - Install package calling `python -m pip install discordbotlinuxmonitor` (or `python setup.py install` from the root of this repository)
  - Copy and edit [config-example.json file](https://github.com/QuentinCG/Discord-Bot-Linux-Monitor-Python-Library/blob/master/config-example.json) depending on your need (on first launch, remove all `restart_command` from config file to prevent potential looping service restart issues on your server in case your config file is not well configured)
  - Launch the lib for testing it works:
```shell
# Get help
python3 -m discordbotlinuxmonitor --help
# Use "--debug" to show more information during command
# Use "--nodebug" to not show any warning information during command

# Start the discord bot Linux monitor (First time)
python3 -m discordbotlinuxmonitor --config_file config-example.json --force_sync_on_startup --debug

# Start the discord bot Linux monitor (after first time)
python3 -m discordbotlinuxmonitor --config_file config-example.json
```
  - Go to discord (restart discord if you were already in it)
  - You should see welcome messages on channels you configured in the config file and be able to communicate with the bot using command defined in previous section


## How to install this lib as a service (to keep it running in the Linux server as a monitor)

  - Stop the discord bot and create a service to have it running even after computer reboot:
```sh
### Define all base info
DISCORD_BOT_SERVICE_USER="discordbotlinuxmonitor"
DISCORD_BOT_SERVICE_GROUP="discordbotlinuxmonitor"
DISCORD_BOT_SERVICE_NAME="discord-bot"
DISCORD_BOT_SERVICE_FILE="/etc/systemd/system/${DISCORD_BOT_SERVICE_NAME}.service"
DISCORD_BOT_FOLDER="/opt/DiscordBot/"

### Add rights to user launching the library depending on what you want it to do ###
# Only if this library should be able to reboot the server on demand:
echo "$DISCORD_BOT_SERVICE_USER ALL=(ALL) NOPASSWD: /sbin/reboot" >> /etc/sudoers.d/$DISCORD_BOT_SERVICE_USER
# Only if this library should be able to kill a process on demand:
echo "$DISCORD_BOT_SERVICE_USER ALL=(ALL) NOPASSWD: /bin/kill" >> /etc/sudoers.d/$DISCORD_BOT_SERVICE_USER
# Add also all processes added in your config JSON file you want the library to be able to execute
# Example for the existing config-example.json file:
echo "$DISCORD_BOT_SERVICE_USER ALL=(ALL) NOPASSWD: /bin/systemctl" >> /etc/sudoers.d/$DISCORD_BOT_SERVICE_USER
echo "$DISCORD_BOT_SERVICE_USER ALL=(ALL) NOPASSWD: /etc/init.d/apache2" >> /etc/sudoers.d/$DISCORD_BOT_SERVICE_USER
echo "$DISCORD_BOT_SERVICE_USER ALL=(ALL) NOPASSWD: /etc/init.d/mariadb" >> /etc/sudoers.d/$DISCORD_BOT_SERVICE_USER

### Create a specific user and group to launch the discord bot service ###
echo "Creating user $DISCORD_BOT_SERVICE_USER..."
sudo useradd -r -s /usr/sbin/nologin $DISCORD_BOT_SERVICE_USER
sudo mkdir -p /home/$DISCORD_BOT_SERVICE_USER
sudo chown $DISCORD_BOT_SERVICE_USER:$DISCORD_BOT_SERVICE_GROUP /home/$DISCORD_BOT_SERVICE_USER
sudo usermod -d /home/$DISCORD_BOT_SERVICE_USER $DISCORD_BOT_SERVICE_USER

### Install DiscordBotLinuxMonitor lib for the user ###
echo "Installing DiscordBotLinuxMonitor for user $DISCORD_BOT_SERVICE_USER..."
sudo -u $DISCORD_BOT_SERVICE_USER -s
python3 -m venv /home/$DISCORD_BOT_SERVICE_USER/venv
source /home/$DISCORD_BOT_SERVICE_USER/venv/bin/activate
python3 -m pip install discordbotlinuxmonitor
deactivate
exit

# Create the Discord bot folder where you should put the json file
sudo mkdir $DISCORD_BOT_FOLDER

### Create a systemd service file for the Discord bot ###
cat <<EOF > $DISCORD_BOT_SERVICE_FILE
[Unit]
Description=Discord Bot Linux Monitor Service
After=network.target

[Service]
ExecStart=/home/$DISCORD_BOT_SERVICE_USER/venv/bin/python3 -m discordbotlinuxmonitor --config_file ${DISCORD_BOT_FOLDER}config.json
WorkingDirectory=$DISCORD_BOT_FOLDER
User=$DISCORD_BOT_SERVICE_USER
Group=$DISCORD_BOT_SERVICE_GROUP
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

echo "Service file created at $DISCORD_BOT_SERVICE_FILE"

### Reload systemd to recognize the new service ###
echo "Reloading systemd..."
sudo systemctl daemon-reload

### Enable and start the service ###
echo "Enabling and starting the Discord bot service..."
sudo systemctl enable $DISCORD_BOT_SERVICE_NAME
```
 - Copy your config file into `$DISCORD_BOT_FOLDER/config.json`
 - Launch the service: `sudo systemctl start $DISCORD_BOT_SERVICE_NAME`

## License

This project is under MIT license. This means you can use it as you want (just don't delete the library header).

## Contribute

If you want to add more examples or improve the library, just create a pull request with proper commit message and right wrapping.
