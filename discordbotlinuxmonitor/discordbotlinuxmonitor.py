"""
Discord bot to:
    - monitor a Linux server and inform about its status (in case of issues or periodical info) through Discord channels
    - execute commands from Discord channels

Non exhaustive list of features (available by using it in shell or in python script):
    - Do all checks bellow in a scheduled tasks and display the results only if there is an issue (only in console if using only the library)
    - Do all checks bellow in a scheduled tasks and display the results every time (only in console if using only the library)

    - Check CPU, RAM, SWAP, Temperature
    - Check disk usage
    - Check folder usage
    - Check websites basic availability (ping)
    - Check websites access with optional authentication (GET request)
    - Check services status and restart them if needed
    - Check certificates expiration and validity
    - Check last user connections IPs
    - Check uptime (to inform if the server has been rebooted)

    - Get hostname, OS details, kernel version, server datetime, uptime
    - Get connected users

    - Restart/Stop a service

    - Get processes list (PID and name)
    - Kill a process by PID

    - Reboot server
"""

__author__ = 'Quentin Comte-Gaz'
__email__ = "quentin@comte-gaz.com"
__license__ = "MIT License"
__copyright__ = "Copyright Quentin Comte-Gaz (2024)"
__python_version__ = "3.+"
__version__ = "1.3.0 (2024/09/19)"
__status__ = "Usable for any Linux project"

# pyright: reportMissingTypeStubs=false
from linuxmonitor import LinuxMonitor

import discord
from discord.app_commands.models import AppCommand
from discord.ext import commands
import json
from typing import List, Union, Awaitable, Callable

import asyncio

import logging

class DiscordBotLinuxMonitor:

    #region Initialization

    def __init__(self, config_file: str, force_sync_on_startup: bool) -> None:
        logging.debug(msg=f"Loading configuration file {config_file}...")
        with open(file=config_file, mode='r') as file:
            self.config = json.load(file)

        # Check if the configuration is correct
        self._init_and_check_configuration()

        # Initialize the LinuxMonitor
        self.monitoring = LinuxMonitor(
                        config_file=config_file,
                        allow_scheduled_tasks_check_for_issues=(self.channel_name_for_public_error_tasks != "" or self.channel_name_for_private_error_tasks != ""), # type: ignore
                        allow_scheduled_task_show_info=(self.channel_name_for_public_infos_tasks != "" or self.channel_name_for_private_infos_tasks != "") # type: ignore
                    )

        # Initialize the bot
        self.force_sync_on_startup: bool = force_sync_on_startup
        self.MAX_LENGTH_OF_DISCORD_MESSAGE = 2000 # Forced by Discord API
        intents: discord.Intents = discord.Intents.default()
        self.bot = commands.Bot(command_prefix=self.command_prefix, intents=intents)

    def _init_and_check_configuration(self) -> None:
        """
        Check if the JSON configuration file is correct for discord usage.
        """
        # Check if the configuration is a dictionary
        if not isinstance(self.config, dict):
            raise ValueError("The configuration must be a dictionary")

        # Check if the configuration contains the necessary keys
        if 'discord_config' not in self.config: # type: ignore
            raise ValueError("The configuration must contain the 'discord_config' key")

        # Get the discord configuration (check if it is a dictionary)
        discord_config: Dict[str, Any] = self.config.get('discord_config', {}) # type: ignore
        if not isinstance(discord_config, dict):
            raise ValueError("The discord configuration (discord_config) must be a dictionary")

        if 'server_id' not in discord_config:
            raise ValueError("The basic configuration must contain the 'server_id' key")
        self.server_id: int = discord_config.get('server_id') # type: ignore

        if 'server_token' not in discord_config:
            raise ValueError("The basic configuration must contain the 'server_token' key")
        self.server_token: str = discord_config.get('server_token') # type: ignore

        if 'command_prefix' not in discord_config:
            raise ValueError("The basic configuration must contain the 'command_prefix' key")
        self.command_prefix: str = discord_config.get('command_prefix', "/") # type: ignore

        if 'channel_name_for_private_commands' not in discord_config:
            raise ValueError("The basic configuration must contain the 'channel_name_for_private_commands' key")
        self.channel_name_for_private_commands: str = discord_config.get('channel_name_for_private_commands', "") # type: ignore

        if 'channel_name_for_public_commands' not in discord_config:
            raise ValueError("The basic configuration must contain the 'channel_name_for_public_commands' key")
        self.channel_name_for_public_commands: str = discord_config.get('channel_name_for_public_commands', "") # type: ignore

        if 'channel_name_for_private_error_tasks' not in discord_config:
            raise ValueError("The basic configuration must contain the 'channel_name_for_private_error_tasks' key")
        self.channel_name_for_private_error_tasks: str = discord_config.get('channel_name_for_private_error_tasks', "") # type: ignore

        if 'channel_name_for_public_error_tasks' not in discord_config:
            raise ValueError("The basic configuration must contain the 'channel_name_for_public_error_tasks' key")
        self.channel_name_for_public_error_tasks: str = discord_config.get('channel_name_for_public_error_tasks', "") # type: ignore

        if 'channel_name_for_private_infos_tasks' not in discord_config:
            raise ValueError("The basic configuration must contain the 'channel_name_for_private_infos_tasks' key")
        self.channel_name_for_private_infos_tasks: str = discord_config.get('channel_name_for_private_infos_tasks', "") # type: ignore

        if 'channel_name_for_public_infos_tasks' not in discord_config:
            raise ValueError("The basic configuration must contain the 'channel_name_for_public_infos_tasks' key")
        self.channel_name_for_public_infos_tasks: str = discord_config.get('channel_name_for_public_infos_tasks', "") # type: ignore

        if self.channel_name_for_private_commands != "": # type: ignore
            if 'welcome_message_for_private_commands' not in discord_config:
                raise ValueError("The basic configuration must contain the 'welcome_message_for_private_commands' key")
            self.welcome_message_for_private_commands: str = discord_config.get('welcome_message_for_private_commands', "") # type: ignore

        if self.channel_name_for_public_commands != "": # type: ignore
            if 'welcome_message_for_public_commands' not in discord_config:
                raise ValueError("The basic configuration must contain the 'welcome_message_for_public_commands' key")
            self.welcome_message_for_public_commands: str = discord_config.get('welcome_message_for_public_commands', "") # type: ignore

        if self.channel_name_for_private_error_tasks != "": # type: ignore
            if 'welcome_message_for_private_error_tasks' not in discord_config:
                raise ValueError("The basic configuration must contain the 'welcome_message_for_private_error_tasks' key")
            self.welcome_message_for_private_error_tasks: str = discord_config.get('welcome_message_for_private_error_tasks', "") # type: ignore

        if self.channel_name_for_public_error_tasks != "": # type: ignore
            if 'welcome_message_for_public_error_tasks' not in discord_config:
                raise ValueError("The basic configuration must contain the 'welcome_message_for_public_error_tasks' key")
            self.welcome_message_for_public_error_tasks: str = discord_config.get('welcome_message_for_public_error_tasks', "") # type: ignore

        if self.channel_name_for_private_infos_tasks != "": # type: ignore
            if 'welcome_message_for_private_infos_tasks' not in discord_config:
                raise ValueError("The basic configuration must contain the 'welcome_message_for_private_infos_tasks' key")
            self.welcome_message_for_private_infos_tasks: str = discord_config.get('welcome_message_for_private_infos_tasks', "") # type: ignore

        if self.channel_name_for_public_infos_tasks != "": # type: ignore
            if 'welcome_message_for_public_infos_tasks' not in discord_config:
                raise ValueError("The basic configuration must contain the 'welcome_message_for_public_infos_tasks' key")
            self.welcome_message_for_public_infos_tasks: str = discord_config.get('welcome_message_for_public_infos_tasks', "") # type: ignore

        # Check that at least one channel is defined
        if self.channel_name_for_private_commands == "" and self.channel_name_for_public_commands == "" and self.channel_name_for_private_error_tasks == "" and self.channel_name_for_public_error_tasks == "" and self.channel_name_for_private_infos_tasks == "" and self.channel_name_for_public_infos_tasks == "": # type: ignore
            raise ValueError("At least one channel must be defined (private or public) in the configuration file, else there is no point to use this lib (channel_name_for_private_commands, channel_name_for_public_commands, channel_name_for_private_error_tasks, channel_name_for_public_error_tasks, channel_name_for_private_infos_tasks, channel_name_for_public_infos_tasks)")

    #endregion

    #region Private methods

    def _check_if_valid_guild(self, guild: Union[None,discord.Guild]) -> bool:
        if guild is None:
            return False

        # Be sure it is from the correct server
        if guild.id != self.server_id:
            logging.warning(msg=f"Message received from invalid guild '{guild.name}' (id: '{guild.id}'), IGNORING THIS MESSAGE.")
            return False
        return True

    async def _is_bot_channel_interaction(self, interaction: discord.Interaction, send_message_if_not_bot: bool) -> bool:
        res: bool = self._is_bot_channel(channel=interaction.channel) # type: ignore
        if not res and send_message_if_not_bot:
            await interaction.response.send_message(content=f"❌ This is not the right channel to send commands to the bot. You need to communicate in the private channel '{self.channel_name_for_private_commands}' or the public channel '{self.channel_name_for_public_commands}'.", ephemeral=True)
        return res

    def _is_bot_channel(self, channel) -> bool: # type: ignore
        return self._is_private_channel(channel=channel) or self._is_public_channel(channel=channel) # type: ignore

    def _is_private_channel(self, channel) -> bool: # type: ignore
        if channel is None:
            return False

        if self.channel_name_for_private_commands == "":
            return False

        res: bool = (self.channel_name_for_private_commands == channel.name) # type: ignore
        return res # type: ignore

    def _is_public_channel(self, channel) -> bool: # type: ignore
        if channel is None:
            return False

        if self._is_private_channel(channel=channel): # type: ignore
            return False

        if self.channel_name_for_public_commands == "":
            return False

        res: bool = (self.channel_name_for_public_commands == channel.name) # type: ignore
        return res # type: ignore

    async def _channel_send_no_limit(self, channel: discord.TextChannel, msg: str) -> None:
        logging.info(msg=f"Sending message to channel '{channel.name}':\n{msg}")

        while len(msg) > self.MAX_LENGTH_OF_DISCORD_MESSAGE:
            # Find the last newline within the limit
            split_point = msg.rfind('\n', 0, self.MAX_LENGTH_OF_DISCORD_MESSAGE)
            if split_point == -1:  # No newline found, split at max_length
                split_point = self.MAX_LENGTH_OF_DISCORD_MESSAGE

            # Send the chunk and remove it from the message
            await channel.send(content=msg[:split_point].rstrip())
            msg = msg[split_point:].lstrip()

        # Send the remaining message
        if msg:
            await channel.send(content=msg)

    async def _interaction_followup_send_no_limit(self, interaction: discord.Interaction, msg: str) -> None:
        logging.info(msg=f"Sending follow-up message:\n{msg}")

        # Send the first chunk as a follow-up message
        try:
            if msg == "":
                # Send generic interaction response if no message is returned
                msg = "No answer."

            if len(msg) > self.MAX_LENGTH_OF_DISCORD_MESSAGE:
                # Find the last newline within the limit or just split at max_length
                split_point = msg.rfind('\n', 0, self.MAX_LENGTH_OF_DISCORD_MESSAGE)
                if split_point == -1:  # No newline found, split at max_length
                    split_point = self.MAX_LENGTH_OF_DISCORD_MESSAGE

                await interaction.followup.send(content=msg[:split_point].rstrip())
                msg = msg[split_point:].lstrip()
            else:
                await interaction.followup.send(content=msg)
                return  # Exit if the message fits within the limit

        except Exception as e:
            logging.error(msg=f"Error while sending follow-up message: {e}")
            return

        # Handle additional messages that exceed the initial follow-up limit
        while len(msg) > self.MAX_LENGTH_OF_DISCORD_MESSAGE:
            split_point = msg.rfind('\n', 0, self.MAX_LENGTH_OF_DISCORD_MESSAGE)
            if split_point == -1:
                split_point = self.MAX_LENGTH_OF_DISCORD_MESSAGE

            try:
                await interaction.channel.send(content=msg[:split_point].rstrip()) # type: ignore
            except Exception as e:
                logging.error(msg=f"Error while sending message to channel: {e}")

            msg = msg[split_point:].lstrip()

        # Send any remaining message directly to the channel
        if msg:
            try:
                await interaction.channel.send(content=msg) # type: ignore
            except Exception as e:
                logging.error(msg=f"Error while sending message to channel: {e}")

    async def _force_sync(self) -> str:
        try:
            logging.info(msg="Forcing the sync of the bot's commands...")
            synced: List[AppCommand] = await self.bot.tree.sync()

            out_msg: str = f"🔄 **Commands synchronized successfully** 🔄"
            for s in synced:
                out_msg += f"\n- `{s.name}`: {s.description}"

            logging.info(msg=out_msg)
            return out_msg
        except Exception as e:
            out_msg = f"**Internal error during command synchronization**:\n```sh\n{e}\n```"
            logging.exception(msg=out_msg)
            return out_msg

    #endregion

    #region BOT COMMANDS AND EVENTS DEFINITIONS

    async def on_ready(self) -> None:
        logging.info(msg=f"Discord bot '{self.bot.user}' is ready.")
        logging.info(msg=f"Connected to the following guilds (will check them): {[guild.name for guild in self.bot.guilds]}")
        for guild in self.bot.guilds:
            if guild.id == self.server_id:
                # Found the correct guild
                logging.info(msg=f"Bot '{self.bot.user}' is connected to the following wanted guild: '{guild.name}' (id: '{guild.id}')..")

                public_channel_cmd_ready: bool = (self.channel_name_for_public_commands == "")
                private_channel_cmd_ready: bool = (self.channel_name_for_private_commands == "")
                public_channel_error_task_ready: bool = (self.channel_name_for_public_error_tasks == "")
                private_channel_error_task_ready: bool = (self.channel_name_for_private_error_tasks == "")
                public_channel_info_task_ready: bool = (self.channel_name_for_public_infos_tasks == "")
                private_channel_info_task_ready: bool = (self.channel_name_for_private_infos_tasks == "")

                for channel in guild.text_channels:
                    if self.channel_name_for_public_commands != "" and channel.name == self.channel_name_for_public_commands:
                        logging.info(msg="Found the public channel, it will be possible to do public commands.")
                        public_channel_cmd_ready = True
                        if self.welcome_message_for_public_commands != "":
                            await self._channel_send_no_limit(channel=channel, msg=self.welcome_message_for_public_commands)

                    if self.channel_name_for_private_commands != "" and channel.name == self.channel_name_for_private_commands:
                        logging.info(msg="Found the private channel, it will be possible to do private commands.")
                        private_channel_cmd_ready = True
                        if self.welcome_message_for_private_commands != "":
                            await self._channel_send_no_limit(channel=channel, msg=self.welcome_message_for_private_commands)

                    if self.channel_name_for_public_error_tasks != "" and channel.name == self.channel_name_for_public_error_tasks:
                        logging.info(msg="Found the public channel for error task, it will be possible to show public status issues if found periodically.")
                        public_channel_error_task_ready = True

                        if self.welcome_message_for_public_error_tasks != "":
                            await self._channel_send_no_limit(channel=channel, msg=self.welcome_message_for_public_error_tasks)

                        logging.info(msg=f"Activating automatic public follow and public service restart if down with '{self.bot.user}' and guild '{guild.name}' (id: '{guild.id}') on channel '{channel.name}' (id '{channel.id}').")
                        public_channel_for_error_task: discord.TextChannel = channel
                        send_message_public_error_task_func: Callable[[str], Awaitable[None]] = lambda msg: asyncio.create_task(self._channel_send_no_limit(channel=public_channel_for_error_task, msg=msg))

                        # Start the public schedule task
                        self.bot.loop.create_task(self.monitoring.schedule_task(handle_error_message=send_message_public_error_task_func, is_private=False))

                    if self.channel_name_for_public_infos_tasks != "" and channel.name == self.channel_name_for_public_infos_tasks:
                        logging.info(msg="Found the public channel for info task, it will be possible to show public info periodically.")
                        public_channel_info_task_ready = True

                        if self.welcome_message_for_public_infos_tasks != "":
                            await self._channel_send_no_limit(channel=channel, msg=self.welcome_message_for_public_infos_tasks)

                        logging.info(msg=f"Activating automatic public follow info with '{self.bot.user}' and guild '{guild.name}' (id: '{guild.id}') on channel '{channel.name}' (id '{channel.id}').")
                        public_channel_for_info_task: discord.TextChannel = channel
                        send_message_public_info_task_func: Callable[[str], Awaitable[None]] = lambda msg: asyncio.create_task(self._channel_send_no_limit(channel=public_channel_for_info_task, msg=msg))

                        # Start the public schedule task
                        self.bot.loop.create_task(self.monitoring.schedule_task_show_info(show_message=send_message_public_info_task_func, is_private=False))

                    if self.channel_name_for_private_error_tasks != "" and channel.name == self.channel_name_for_private_error_tasks:
                        logging.info(msg="Found the private channel for error task, it will be possible to show private and public status issues if found periodically.")
                        private_channel_error_task_ready = True

                        if self.welcome_message_for_private_error_tasks != "":
                            await self._channel_send_no_limit(channel=channel, msg=self.welcome_message_for_private_error_tasks)

                        logging.info(msg=f"Activating automatic private follow and public service restart if down with '{self.bot.user}' and guild '{guild.name}' (id: '{guild.id}') on channel '{channel.name}' (id '{channel.id}').")
                        private_channel_for_error_task: discord.TextChannel = channel
                        send_message_private_error_task_func: Callable[[str], Awaitable[None]] = lambda msg: asyncio.create_task(self._channel_send_no_limit(channel=private_channel_for_error_task, msg=msg))

                        # Start the private schedule task
                        self.bot.loop.create_task(self.monitoring.schedule_task(handle_error_message=send_message_private_error_task_func, is_private=True))

                    if self.channel_name_for_private_infos_tasks != "" and channel.name == self.channel_name_for_private_infos_tasks:
                        logging.info(msg="Found the private channel for info task, it will be possible to show private info periodically.")
                        private_channel_info_task_ready = True

                        if self.welcome_message_for_private_infos_tasks != "":
                            await self._channel_send_no_limit(channel=channel, msg=self.welcome_message_for_private_infos_tasks)

                        logging.info(msg=f"Activating automatic private follow info with '{self.bot.user}' and guild '{guild.name}' (id: '{guild.id}') on channel '{channel.name}' (id '{channel.id}').")
                        private_channel_for_info_task: discord.TextChannel = channel
                        send_message_private_info_task_func: Callable[[str], Awaitable[None]] = lambda msg: asyncio.create_task(self._channel_send_no_limit(channel=private_channel_for_info_task, msg=msg))

                        # Start the private schedule task
                        self.bot.loop.create_task(self.monitoring.schedule_task_show_info(show_message=send_message_private_info_task_func, is_private=True))

                # Show a warning if a channel is not found and should be found
                if not public_channel_cmd_ready:
                    logging.critical(msg=f"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                    logging.critical(msg=f"Public channel '{self.channel_name_for_public_commands}' not found in server: '{guild.name}', public commands will not be available.")
                    logging.critical(msg=f"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                if not private_channel_cmd_ready:
                    logging.critical(msg=f"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                    logging.critical(msg=f"Private channel '{self.channel_name_for_private_commands}' not found in server: '{guild.name}', private commands will not be available.")
                    logging.critical(msg=f"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                if not public_channel_error_task_ready:
                    logging.critical(msg=f"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                    logging.critical(msg=f"Public channel '{self.channel_name_for_public_error_tasks}' not found in server: '{guild.name}', public status issues will not be shown periodically if found.")
                    logging.critical(msg=f"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                if not private_channel_error_task_ready:
                    logging.critical(msg=f"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                    logging.critical(msg=f"Private channel '{self.channel_name_for_private_error_tasks}' not found in server: '{guild.name}', private and public status issues will not be shown periodically if found.")
                    logging.critical(msg=f"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                if not public_channel_info_task_ready:
                    logging.critical(msg=f"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                    logging.critical(msg=f"Public channel '{self.channel_name_for_public_infos_tasks}' not found in server: '{guild.name}', public info will not be shown periodically.")
                    logging.critical(msg=f"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                if not private_channel_info_task_ready:
                    logging.critical(msg=f"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                    logging.critical(msg=f"Private channel '{self.channel_name_for_private_infos_tasks}' not found in server: '{guild.name}', private info will not be shown periodically.")
                    logging.critical(msg=f"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            else:
                # Found an undesired guild, disconnect
                logging.info(msg=f"Bot '{self.bot.user}' is connected to the following UNDESIRED guild: '{guild.name}' (id: '{guild.id}'), IGNORING THIS GUILD.")

            # Sync the bot's commands globally
            if self.force_sync_on_startup:
                await self._force_sync()

    async def force_sync(self, interaction: discord.Interaction) -> None:
        if not self._check_if_valid_guild(guild=interaction.guild):
            return
        if not (await self._is_bot_channel_interaction(interaction=interaction, send_message_if_not_bot=True)):
            return

        if not self._is_private_channel(channel=interaction.channel): # type: ignore
            await interaction.response.send_message(content="❌ Public channels do not allow this command.", ephemeral=True)
            return

        # Say to the user that the command is being processed
        await interaction.response.defer()

        # Sync the bot's commands only on the 2 public and private channels
        out_msg: str = await self._force_sync()

        # Respond to the user
        await self._interaction_followup_send_no_limit(interaction=interaction, msg=out_msg)

    async def usage(self, interaction: discord.Interaction) -> None:
        if not self._check_if_valid_guild(guild=interaction.guild):
            return
        if not (await self._is_bot_channel_interaction(interaction=interaction, send_message_if_not_bot=True)):
            return

        # Say to the user that the command is being processed
        await interaction.response.defer()

        try:
            is_private: bool = self._is_private_channel(channel=interaction.channel) # type: ignore
            out_msg: str = self.monitoring.check_all_disk_usage(is_private=is_private, display_only_if_critical=False)

            msg: str = self.monitoring.check_all_folder_usage(is_private=is_private, display_only_if_critical=False)
            if msg != "":
                if out_msg != "":
                    out_msg += "\n"
                out_msg += msg

            if is_private:
                out_msg += "\n"
                out_msg += self.monitoring.check_cpu_usage(display_only_if_critical=False) + "\n"
                out_msg += self.monitoring.check_ram_usage(display_only_if_critical=False) + "\n"
                out_msg += self.monitoring.check_swap_usage(display_only_if_critical=False) + "\n"
                out_msg += self.monitoring.check_cpu_temperature(display_only_if_critical=False) + "\n"
                out_msg += self.monitoring.get_network_info()

            # Respond to the user
            await self._interaction_followup_send_no_limit(interaction=interaction, msg=out_msg)
        except Exception as e:
            out_msg = f"**Internal error retrieving usage info**:\n```sh\n{e}\n```"
            logging.exception(msg=out_msg)
            await self._interaction_followup_send_no_limit(interaction=interaction, msg=out_msg)

    async def os_infos(self, interaction: discord.Interaction) -> None:
        if not self._check_if_valid_guild(guild=interaction.guild):
            return
        if not (await self._is_bot_channel_interaction(interaction=interaction, send_message_if_not_bot=True)):
            return

        # Say to the user that the command is being processed
        await interaction.response.defer()

        try:
            out_msg: str = self.monitoring.get_hostname() + "\n"
            out_msg += self.monitoring.get_os_details() + "\n"
            out_msg += self.monitoring.get_kernel_version() + "\n"
            out_msg += self.monitoring.check_uptime(display_only_if_critical=False) + "\n"
            out_msg += self.monitoring.get_server_datetime()

            # Respond to the user
            await self._interaction_followup_send_no_limit(interaction=interaction, msg=out_msg)
        except Exception as e:
            out_msg = f"**Internal error retrieving OS info**:\n```sh\n{e}\n```"
            logging.exception(msg=out_msg)
            await self._interaction_followup_send_no_limit(interaction=interaction, msg=out_msg)

    async def users(self, interaction: discord.Interaction) -> None:
        if not self._check_if_valid_guild(guild=interaction.guild):
            return
        if not (await self._is_bot_channel_interaction(interaction=interaction, send_message_if_not_bot=True)):
            return
        if not self._is_private_channel(channel=interaction.channel): # type: ignore
            await interaction.response.send_message(content="❌ Public channels do not allow this command.", ephemeral=True)
            return

        # Say to the user that the command is being processed
        await interaction.response.defer()

        try:
            out_msg: str = self.monitoring.get_connected_users()

            # Respond to the user
            await self._interaction_followup_send_no_limit(interaction=interaction, msg=out_msg)
        except Exception as e:
            out_msg = f"**Internal error retrieving connected users**:\n```sh\n{e}\n```"
            logging.exception(msg=out_msg)
            await self._interaction_followup_send_no_limit(interaction=interaction, msg=out_msg)

    async def user_logins(self, interaction: discord.Interaction) -> None:
        if not self._check_if_valid_guild(guild=interaction.guild):
            return
        if not (await self._is_bot_channel_interaction(interaction=interaction, send_message_if_not_bot=True)):
            return

        if not self._is_private_channel(channel=interaction.channel): # type: ignore
            await interaction.response.send_message(content="❌ Public channels do not allow this command.", ephemeral=True)
            return

        # Indiquer que la commande est en cours de traitement
        await interaction.response.defer()

        try:
            # Récupérer les dernières connexions des utilisateurs
            out_msg: str = self.monitoring.check_all_recent_user_logins(display_only_if_critical=False)

            # Répondre à l'utilisateur
            await self._interaction_followup_send_no_limit(interaction=interaction, msg=out_msg)

        except Exception as e:
            out_msg = f"**Internal error retrieving last user connections**:\n```sh\n{e}\n```"
            logging.exception(msg=out_msg)
            await self._interaction_followup_send_no_limit(interaction=interaction, msg=out_msg)

    async def ping(self, interaction: discord.Interaction) -> None:
        if not self._check_if_valid_guild(guild=interaction.guild):
            return
        if not (await self._is_bot_channel_interaction(interaction=interaction, send_message_if_not_bot=True)):
            return

        # Say to the user that the command is being processed
        await interaction.response.defer()

        try:
            is_private: bool = self._is_private_channel(channel=interaction.channel) # type: ignore
            out_msg: str = await self.monitoring.ping_all_websites(is_private=is_private, display_only_if_critical=False)

            # Respond to the user
            await self._interaction_followup_send_no_limit(interaction=interaction, msg=out_msg)
        except Exception as e:
            out_msg = f"**Internal error during websites ping **:\n```sh\n{e}\n```"
            logging.exception(msg=out_msg)
            await self._interaction_followup_send_no_limit(interaction=interaction, msg=out_msg)

    async def websites(self, interaction: discord.Interaction) -> None:
        if not self._check_if_valid_guild(guild=interaction.guild):
            return
        if not (await self._is_bot_channel_interaction(interaction=interaction, send_message_if_not_bot=True)):
            return

        # Say to the user that the command is being processed
        await interaction.response.defer()

        try:
            is_private: bool = self._is_private_channel(channel=interaction.channel) # type: ignore
            out_msg: str = await self.monitoring.check_all_websites(is_private=is_private, display_only_if_critical=False)

            # Respond to the user
            await self._interaction_followup_send_no_limit(interaction=interaction, msg=out_msg)
        except Exception as e:
            out_msg = f"**Internal error during websites access check **:\n```sh\n{e}\n```"
            logging.exception(msg=out_msg)
            await self._interaction_followup_send_no_limit(interaction=interaction, msg=out_msg)

    async def certificates(self, interaction: discord.Interaction) -> None:
        if not self._check_if_valid_guild(guild=interaction.guild):
            return
        if not (await self._is_bot_channel_interaction(interaction=interaction, send_message_if_not_bot=True)):
            return

        # Say to the user that the command is being processed
        await interaction.response.defer()

        try:
            is_private: bool = self._is_private_channel(channel=interaction.channel) # type: ignore
            out_msg: str = self.monitoring.check_all_certificates(is_private=is_private, display_only_if_critical=False)

            # Respond to the user
            await self._interaction_followup_send_no_limit(interaction=interaction, msg=out_msg)
        except Exception as e:
            out_msg = f"**Internal error during SSL certificate checks **:\n```sh\n{e}\n```"
            logging.exception(msg=out_msg)
            await self._interaction_followup_send_no_limit(interaction=interaction, msg=out_msg)

    async def reboot(self, interaction: discord.Interaction) -> None:
        if not self._check_if_valid_guild(guild=interaction.guild):
            return
        if not (await self._is_bot_channel_interaction(interaction=interaction, send_message_if_not_bot=True)):
            return
        if not self._is_private_channel(channel=interaction.channel): # type: ignore
            await interaction.response.send_message(content="❌ Public channels do not allow this command.", ephemeral=True)
            return

        # Say to the user that the command is being processed
        await interaction.response.defer()

        try:
            out_msg: str = await self.monitoring.reboot_server()
            await self._interaction_followup_send_no_limit(interaction=interaction, msg=out_msg)

        except Exception as e:
            out_msg = f"**Internal error during server reboot**:\n```sh\n{e}\n```"
            logging.exception(msg=out_msg)
            await self._interaction_followup_send_no_limit(interaction=interaction, msg=out_msg)

    async def services_status(self, interaction: discord.Interaction) -> None:
        if not self._check_if_valid_guild(guild=interaction.guild):
            return
        if not (await self._is_bot_channel_interaction(interaction=interaction, send_message_if_not_bot=True)):
            return

        # Say to the user that the command is being processed
        await interaction.response.defer()

        try:
            is_private: bool = self._is_private_channel(channel=interaction.channel) # type: ignore
            out_msg: str = await self.monitoring.check_all_services_status(is_private=is_private)

            # Respond to the user
            await self._interaction_followup_send_no_limit(interaction=interaction, msg=out_msg)
        except Exception as e:
            out_msg = f"**Internal error checking services are running**:\n```sh\n{e}\n```"
            logging.exception(msg=out_msg)
            await self._interaction_followup_send_no_limit(interaction=interaction, msg=out_msg)

    async def restart_all(self, interaction: discord.Interaction) -> None:
        if not self._check_if_valid_guild(guild=interaction.guild):
            return
        if not (await self._is_bot_channel_interaction(interaction=interaction, send_message_if_not_bot=True)):
            return

        # Say to the user that the command is being processed
        await interaction.response.defer()

        try:
            # Restart all services and get the results
            is_private: bool = self._is_private_channel(channel=interaction.channel) # type: ignore
            out_msg: str = await self.monitoring.restart_all_services(is_private=is_private)

            # Respond to the user
            await self._interaction_followup_send_no_limit(interaction=interaction, msg=out_msg)
        except Exception as e:
            out_msg = f"**Internal error restarting all services**:\n```sh\n{e}\n```"
            logging.exception(msg=out_msg)
            await self._interaction_followup_send_no_limit(interaction=interaction, msg=out_msg)

    async def restart_service(self, interaction: discord.Interaction, service_name: str) -> None:
        if not self._check_if_valid_guild(guild=interaction.guild):
            return
        if not (await self._is_bot_channel_interaction(interaction=interaction, send_message_if_not_bot=True)):
            return

        # Indiquer que la commande est en cours de traitement
        await interaction.response.defer()

        try:
            # Redémarrer le service et récupérer le message de sortie
            is_private: bool = self._is_private_channel(channel=interaction.channel) # type: ignore
            out_msg: str = await self.monitoring.restart_service(is_private=is_private, service_name=service_name, force_restart=True)

            # Répondre à l'utilisateur
            await self._interaction_followup_send_no_limit(interaction=interaction, msg=out_msg)

        except Exception as e:
            out_msg = f"**Internal error restarting service {service_name}**:\n```sh\n{e}\n```"
            logging.exception(msg=out_msg)
            await self._interaction_followup_send_no_limit(interaction=interaction, msg=out_msg)

    async def stop_service(self, interaction: discord.Interaction, service_name: str) -> None:
        if not self._check_if_valid_guild(guild=interaction.guild):
            return
        if not (await self._is_bot_channel_interaction(interaction=interaction, send_message_if_not_bot=True)):
            return

        # Indiquer que la commande est en cours de traitement
        await interaction.response.defer()

        try:
            # Arrêter le service et récupérer le message de sortie
            is_private: bool = self._is_private_channel(channel=interaction.channel) # type: ignore
            out_msg: str = await self.monitoring.stop_service(is_private=is_private, service_name=service_name)

            # Répondre à l'utilisateur
            await self._interaction_followup_send_no_limit(interaction=interaction, msg=out_msg)
        except Exception as e:
            out_msg = f"**Internal error stopping service {service_name}**:\n```sh\n{e}\n```"
            logging.exception(msg=out_msg)
            await self._interaction_followup_send_no_limit(interaction=interaction, msg=out_msg)

    async def list_services(self, interaction: discord.Interaction) -> None:
        if not self._check_if_valid_guild(guild=interaction.guild):
            return
        if not (await self._is_bot_channel_interaction(interaction=interaction, send_message_if_not_bot=True)):
            return

        # Indiquer que la commande est en cours de traitement
        await interaction.response.defer()

        try:
            # Récupérer la liste des services
            is_private: bool = self._is_private_channel(channel=interaction.channel) # type: ignore
            out_msg: str = self.monitoring.get_all_services(is_private=is_private)

            # Répondre à l'utilisateur
            await self._interaction_followup_send_no_limit(interaction=interaction, msg=out_msg)
        except Exception as e:
            out_msg = f"**Internal error retrieving available services**:\n```sh\n{e}\n```"
            logging.exception(msg=out_msg)
            await self._interaction_followup_send_no_limit(interaction=interaction, msg=out_msg)

    async def ports(self, interaction: discord.Interaction) -> None:
        if not self._check_if_valid_guild(guild=interaction.guild):
            return
        if not (await self._is_bot_channel_interaction(interaction=interaction, send_message_if_not_bot=True)):
            return

        # Indiquer que la commande est en cours de traitement
        await interaction.response.defer()

        try:
            # Récupérer le statut des ports
            is_private: bool = self._is_private_channel(channel=interaction.channel) # type: ignore
            out_msg: str = await self.monitoring.check_all_ports(is_private=is_private, display_only_if_critical=False)

            # Répondre à l'utilisateur
            await self._interaction_followup_send_no_limit(interaction=interaction, msg=out_msg)
        except Exception as e:
            out_msg = f"**Internal error checking ports**:\n```sh\n{e}\n```"
            logging.exception(msg=out_msg)
            await self._interaction_followup_send_no_limit(interaction=interaction, msg=out_msg)

    async def list_processes(self, interaction: discord.Interaction) -> None:
        if not self._check_if_valid_guild(guild=interaction.guild):
            return
        if not (await self._is_bot_channel_interaction(interaction=interaction, send_message_if_not_bot=True)):
            return
        if not self._is_private_channel(channel=interaction.channel): # type: ignore
            await interaction.response.send_message(content="❌ Public channels do not allow this command.", ephemeral=True)
            return

        # Indiquer que la commande est en cours de traitement
        await interaction.response.defer()

        try:
            # Récupérer la liste des processus actifs
            out_msg: str = self.monitoring.get_ordered_processes()

            # Répondre à l'utilisateur
            await self._interaction_followup_send_no_limit(interaction=interaction, msg=out_msg)
        except Exception as e:
            out_msg = f"**Internal error retrieving active processes**:\n```sh\n{e}\n```"
            logging.exception(msg=out_msg)
            await self._interaction_followup_send_no_limit(interaction=interaction, msg=out_msg)

    async def kill_process(self, interaction: discord.Interaction, pid: int) -> None:
        if not self._check_if_valid_guild(guild=interaction.guild):
            return
        if not (await self._is_bot_channel_interaction(interaction=interaction, send_message_if_not_bot=True)):
            return
        if not self._is_private_channel(channel=interaction.channel): # type: ignore
            await interaction.response.send_message(content="❌ Public channels do not allow this command.", ephemeral=True)
            return

        # Indiquer que la commande est en cours de traitement
        await interaction.response.defer()

        try:
            # Arrêter le processus et récupérer le message de sortie
            out_msg: str = await self.monitoring.kill_process(pid=pid)

            # Répondre à l'utilisateur
            await self._interaction_followup_send_no_limit(interaction=interaction, msg=out_msg)
        except Exception as e:
            out_msg = f"**Internal error stopping process of PID {pid}**:\n```sh\n{e}\n```"
            logging.exception(msg=out_msg)
            await self._interaction_followup_send_no_limit(interaction=interaction, msg=out_msg)

    #endregion
