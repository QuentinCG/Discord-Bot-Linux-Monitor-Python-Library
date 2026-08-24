"""
Discord bot to:
    - monitor a Linux server and inform about its status (in case of issues or periodical info) through Discord channels
    - execute commands from Discord channels

Non exhaustive list of features (available by using it in shell or in python script):
    - Do all checks bellow in a scheduled tasks and display the results only if there is an issue (only in console if using only the library)
    - Do all checks bellow in a scheduled tasks and display the results every time (only in console if using only the library)

    - Check Load Average, CPU, RAM, SWAP, Temperature
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
__copyright__ = "Copyright Quentin Comte-Gaz (2026)"
__python_version__ = "3.+"
__version__ = "1.6.6 (2026/08/24)"
__status__ = "Usable for any Linux project"

# pyright: reportMissingTypeStubs=false
from linuxmonitor import LinuxMonitor

import discord
from discord.app_commands.models import AppCommand
from discord.ext import commands
import json
from typing import List, Union, Awaitable, Callable, Any, Dict, Optional
from datetime import datetime, timedelta, timezone

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

    def _welcome_message_with_version(self, welcome_message: str) -> str:
        return f"{welcome_message}\n\n🤖 Bot version: {__version__}"

    def _get_rate_limit_wait_seconds(self, error: discord.HTTPException, fallback_seconds: float = 1.5) -> float:
        retry_after = getattr(error, "retry_after", None)
        if isinstance(retry_after, (int, float)) and retry_after > 0:
            return float(retry_after)

        response = getattr(error, "response", None)
        if response is not None:
            headers = getattr(response, "headers", None)
            if headers is not None:
                header_retry_after = headers.get("Retry-After")
                if header_retry_after is not None:
                    try:
                        parsed_retry_after = float(header_retry_after)
                        if parsed_retry_after > 0:
                            return parsed_retry_after
                    except (ValueError, TypeError):
                        pass

        return fallback_seconds

    def _format_duration(self, total_seconds: float) -> str:
        seconds: int = max(0, int(total_seconds))

        days, remainder = divmod(seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, secs = divmod(remainder, 60)

        parts: List[str] = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if secs > 0 or len(parts) == 0:
            parts.append(f"{secs}s")

        return " ".join(parts)

    def _get_message_preview(self, message: discord.Message, max_length: int = 80) -> str:
        content: str = str(getattr(message, "content", "") or "").strip()

        if content == "":
            attachments = getattr(message, "attachments", [])
            embeds = getattr(message, "embeds", [])
            if len(attachments) > 0:
                content = f"[{len(attachments)} attachment(s)]"
            elif len(embeds) > 0:
                content = f"[{len(embeds)} embed(s)]"
            else:
                content = "[no text]"

        content = content.replace("\n", " ").replace("\r", " ")
        created_at = getattr(message, "created_at", None)
        if created_at is not None:
            try:
                timestamp = created_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            except Exception:
                timestamp = str(created_at)
        else:
            timestamp = "unknown-time"

        if len(content) > max_length:
            content = content[:max_length - 3] + "..."

        return f"[{timestamp}] {content}"

    def _build_cleanup_embed(self, channel_name: str, state: str, deleted_count: int, rate_limit_retries: int, elapsed_seconds: float, last_deleted_preview: str, spinner_frame: str = "", scanned_count: Optional[int] = None, error_text: str = "") -> "discord.Embed":
        # state is one of: "running", "done", "error".
        if state == "done":
            color = discord.Color.green()
            title = "🧹 Channel Cleanup — Completed"
            status_value = "✅ Completed"
        elif state == "error":
            color = discord.Color.red()
            title = "🧹 Channel Cleanup — Failed"
            status_value = "❌ Failed"
        else:
            color = discord.Color.blurple()
            title = "🧹 Channel Cleanup — In progress"
            status_value = f"{spinner_frame} Working…".strip()

        embed = discord.Embed(title=title, color=color)
        embed.description = f"Target channel: **#{channel_name}**"

        embed.add_field(name="Status", value=status_value, inline=True)
        embed.add_field(name="🗑️ Deleted", value=f"**{deleted_count}** message(s)", inline=True)
        embed.add_field(name="⏳ Elapsed", value=self._format_duration(elapsed_seconds), inline=True)

        if scanned_count is not None:
            embed.add_field(name="🔎 Scanned", value=f"{scanned_count} message(s)", inline=True)
        embed.add_field(name="🚦 Rate-limit waits", value=str(rate_limit_retries), inline=True)

        if error_text != "":
            embed.add_field(name="⚠️ Error", value=f"```sh\n{error_text[:1000]}\n```", inline=False)

        embed.add_field(name="🕗 Last deleted message", value=(last_deleted_preview if last_deleted_preview != "" else "N/A")[:1024], inline=False)

        embed.set_footer(text=f"Bot v{__version__} • Last update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        return embed

    async def _delete_message_with_rate_limit_retry(self, message: discord.Message, reason: str, max_retries: int = 10, on_rate_limit: Optional[Callable[[], None]] = None) -> None:
        for attempt in range(max_retries + 1):
            try:
                try:
                    await message.delete(reason=reason)
                except TypeError:
                    # Some discord.py objects (e.g. PartialMessage) do not accept `reason`.
                    await message.delete()
                return
            except discord.NotFound:
                return
            except discord.HTTPException as e:
                if e.status == 429 and attempt < max_retries:
                    if on_rate_limit is not None:
                        on_rate_limit()
                    wait_seconds = self._get_rate_limit_wait_seconds(error=e)
                    logging.warning(msg=f"Rate limited while deleting message {message.id}, waiting {wait_seconds:.2f}s before retry...")
                    await asyncio.sleep(wait_seconds)
                    continue
                raise

    async def _bulk_delete_messages_with_rate_limit_retry(self, channel: discord.TextChannel, messages: List[discord.Message], reason: str, max_retries: int = 10, on_rate_limit: Optional[Callable[[], None]] = None) -> None:
        if len(messages) == 0:
            return

        for attempt in range(max_retries + 1):
            try:
                if len(messages) == 1:
                    try:
                        await messages[0].delete(reason=reason)
                    except TypeError:
                        # Some discord.py objects (e.g. PartialMessage) do not accept `reason`.
                        await messages[0].delete()
                else:
                    await channel.delete_messages(messages, reason=reason)
                return
            except discord.NotFound:
                return
            except discord.HTTPException as e:
                if e.status == 429 and attempt < max_retries:
                    if on_rate_limit is not None:
                        on_rate_limit()
                    wait_seconds = self._get_rate_limit_wait_seconds(error=e)
                    logging.warning(msg=f"Rate limited while bulk deleting {len(messages)} messages in '{channel.name}', waiting {wait_seconds:.2f}s before retry...")
                    await asyncio.sleep(wait_seconds)
                    continue
                raise

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
                            await self._channel_send_no_limit(channel=channel, msg=self._welcome_message_with_version(self.welcome_message_for_public_commands))

                    if self.channel_name_for_private_commands != "" and channel.name == self.channel_name_for_private_commands:
                        logging.info(msg="Found the private channel, it will be possible to do private commands.")
                        private_channel_cmd_ready = True
                        if self.welcome_message_for_private_commands != "":
                            await self._channel_send_no_limit(channel=channel, msg=self._welcome_message_with_version(self.welcome_message_for_private_commands))

                    if self.channel_name_for_public_error_tasks != "" and channel.name == self.channel_name_for_public_error_tasks:
                        logging.info(msg="Found the public channel for error task, it will be possible to show public status issues if found periodically.")
                        public_channel_error_task_ready = True

                        if self.welcome_message_for_public_error_tasks != "":
                            await self._channel_send_no_limit(channel=channel, msg=self._welcome_message_with_version(self.welcome_message_for_public_error_tasks))

                        logging.info(msg=f"Activating automatic public follow and public service restart if down with '{self.bot.user}' and guild '{guild.name}' (id: '{guild.id}') on channel '{channel.name}' (id '{channel.id}').")
                        public_channel_for_error_task: discord.TextChannel = channel
                        send_message_public_error_task_func: Callable[[str], Awaitable[None]] = lambda msg: asyncio.create_task(self._channel_send_no_limit(channel=public_channel_for_error_task, msg=msg))

                        # Start the public schedule task
                        self.bot.loop.create_task(self.monitoring.schedule_task(handle_error_message=send_message_public_error_task_func, is_private=False))

                    if self.channel_name_for_public_infos_tasks != "" and channel.name == self.channel_name_for_public_infos_tasks:
                        logging.info(msg="Found the public channel for info task, it will be possible to show public info periodically.")
                        public_channel_info_task_ready = True

                        if self.welcome_message_for_public_infos_tasks != "":
                            await self._channel_send_no_limit(channel=channel, msg=self._welcome_message_with_version(self.welcome_message_for_public_infos_tasks))

                        logging.info(msg=f"Activating automatic public follow info with '{self.bot.user}' and guild '{guild.name}' (id: '{guild.id}') on channel '{channel.name}' (id '{channel.id}').")
                        public_channel_for_info_task: discord.TextChannel = channel
                        send_message_public_info_task_func: Callable[[str], Awaitable[None]] = lambda msg: asyncio.create_task(self._channel_send_no_limit(channel=public_channel_for_info_task, msg=msg))

                        # Start the public schedule task
                        self.bot.loop.create_task(self.monitoring.schedule_task_show_info(show_message=send_message_public_info_task_func, is_private=False))

                    if self.channel_name_for_private_error_tasks != "" and channel.name == self.channel_name_for_private_error_tasks:
                        logging.info(msg="Found the private channel for error task, it will be possible to show private and public status issues if found periodically.")
                        private_channel_error_task_ready = True

                        if self.welcome_message_for_private_error_tasks != "":
                            await self._channel_send_no_limit(channel=channel, msg=self._welcome_message_with_version(self.welcome_message_for_private_error_tasks))

                        logging.info(msg=f"Activating automatic private follow and public service restart if down with '{self.bot.user}' and guild '{guild.name}' (id: '{guild.id}') on channel '{channel.name}' (id '{channel.id}').")
                        private_channel_for_error_task: discord.TextChannel = channel
                        send_message_private_error_task_func: Callable[[str], Awaitable[None]] = lambda msg: asyncio.create_task(self._channel_send_no_limit(channel=private_channel_for_error_task, msg=msg))

                        # Start the private schedule task
                        self.bot.loop.create_task(self.monitoring.schedule_task(handle_error_message=send_message_private_error_task_func, is_private=True))

                    if self.channel_name_for_private_infos_tasks != "" and channel.name == self.channel_name_for_private_infos_tasks:
                        logging.info(msg="Found the private channel for info task, it will be possible to show private info periodically.")
                        private_channel_info_task_ready = True

                        if self.welcome_message_for_private_infos_tasks != "":
                            await self._channel_send_no_limit(channel=channel, msg=self._welcome_message_with_version(self.welcome_message_for_private_infos_tasks))

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

    async def version(self, interaction: discord.Interaction) -> None:
        if not self._check_if_valid_guild(guild=interaction.guild):
            return
        if not (await self._is_bot_channel_interaction(interaction=interaction, send_message_if_not_bot=True)):
            return

        out_msg: str = (
            f"🤖 Bot version: {__version__}\n"
            f"🐍 Python compatibility: {__python_version__}"
        )
        await interaction.response.send_message(content=out_msg, ephemeral=True)

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
                out_msg += await self.monitoring.check_load_average(display_only_if_critical=False) + "\n"
                out_msg += await self.monitoring.check_cpu_usage(display_only_if_critical=False) + "\n"
                out_msg += await self.monitoring.check_ram_usage(display_only_if_critical=False) + "\n"
                out_msg += await self.monitoring.check_swap_usage(display_only_if_critical=False) + "\n"
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

    async def list_processes(self, interaction: discord.Interaction, order_by_ram: bool) -> None:
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
            out_msg: str = await self.monitoring.get_ordered_processes(get_non_consuming_processes=False, order_by_ram=order_by_ram, max_processes=20)

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

    async def clear_channel_messages(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        if not self._check_if_valid_guild(guild=interaction.guild):
            return
        if not (await self._is_bot_channel_interaction(interaction=interaction, send_message_if_not_bot=True)):
            return
        if not self._is_private_channel(channel=interaction.channel): # type: ignore
            await interaction.response.send_message(content="❌ Public channels do not allow this command.", ephemeral=True)
            return

        # Make sure only authorized users can trigger a destructive command.
        permissions = channel.permissions_for(interaction.user) # type: ignore
        if not permissions.manage_messages:
            await interaction.response.send_message(content=f"❌ You need 'Manage Messages' permission on channel '{channel.name}' to clear it.", ephemeral=True)
            return

        bot_member = interaction.guild.me if interaction.guild is not None else None # type: ignore
        if bot_member is None:
            await interaction.response.send_message(content="❌ Unable to resolve bot permissions.", ephemeral=True)
            return

        bot_permissions = channel.permissions_for(bot_member)
        if not bot_permissions.manage_messages or not bot_permissions.read_message_history:
            await interaction.response.send_message(content=f"❌ Bot is missing required permissions on channel '{channel.name}' (Manage Messages and Read Message History).", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        deleted_count: int = 0
        rate_limit_retries: int = 0
        delete_reason: str = f"Requested by {interaction.user} from private channel"
        two_weeks_ago = datetime.now(timezone.utc) - timedelta(days=14)
        progress_every_seconds: float = 2.5
        progress_every_deleted_messages: int = 200
        started_monotonic: float = asyncio.get_running_loop().time()
        last_progress_monotonic: float = started_monotonic
        last_reported_deleted_count: int = 0
        heartbeat_frames: List[str] = ["◐", "◓", "◑", "◒"]
        heartbeat_index: int = 0
        heartbeat_stop_event = asyncio.Event()
        heartbeat_task: Optional[asyncio.Task] = None
        last_deleted_message_preview: str = "N/A"
        scanned_count: int = 0

        def _on_rate_limit_hit() -> None:
            nonlocal rate_limit_retries
            rate_limit_retries += 1

        async def _update_progress(force: bool = False) -> None:
            nonlocal last_progress_monotonic
            nonlocal last_reported_deleted_count
            nonlocal heartbeat_index

            now = asyncio.get_running_loop().time()
            should_update = force
            if not should_update:
                enough_time_elapsed = (now - last_progress_monotonic) >= progress_every_seconds
                enough_messages_deleted = (deleted_count - last_reported_deleted_count) >= progress_every_deleted_messages
                should_update = enough_time_elapsed or enough_messages_deleted

            if not should_update:
                return

            heartbeat_frame = heartbeat_frames[heartbeat_index % len(heartbeat_frames)]
            heartbeat_index += 1
            embed = self._build_cleanup_embed(
                channel_name=channel.name,
                state="running",
                deleted_count=deleted_count,
                rate_limit_retries=rate_limit_retries,
                elapsed_seconds=now - started_monotonic,
                last_deleted_preview=last_deleted_message_preview,
                spinner_frame=heartbeat_frame,
                scanned_count=scanned_count,
            )

            try:
                await interaction.edit_original_response(content=None, embed=embed)
                last_progress_monotonic = now
                last_reported_deleted_count = deleted_count
            except discord.HTTPException as e:
                if e.status == 429:
                    _on_rate_limit_hit()
                    wait_seconds = self._get_rate_limit_wait_seconds(error=e)
                    await asyncio.sleep(wait_seconds)
                else:
                    logging.warning(msg=f"Failed to update cleanup progress message: {e}")

        async def _heartbeat_loop() -> None:
            while not heartbeat_stop_event.is_set():
                await asyncio.sleep(5)
                if heartbeat_stop_event.is_set():
                    return
                await _update_progress(force=True)

        try:
            await _update_progress(force=True)
            heartbeat_task = asyncio.create_task(_heartbeat_loop())
            recent_batch: List[discord.Message] = []

            async for message in channel.history(limit=None, oldest_first=False):
                scanned_count += 1
                if message.created_at >= two_weeks_ago:
                    recent_batch.append(message)

                    # Bulk delete by chunks of 100 to reduce API calls and rate-limit pressure.
                    if len(recent_batch) == 100:
                        last_deleted_message_preview = self._get_message_preview(recent_batch[-1])
                        await self._bulk_delete_messages_with_rate_limit_retry(channel=channel, messages=recent_batch, reason=delete_reason, on_rate_limit=_on_rate_limit_hit)
                        deleted_count += len(recent_batch)
                        recent_batch = []
                        await _update_progress()
                else:
                    last_deleted_message_preview = self._get_message_preview(message)
                    await self._delete_message_with_rate_limit_retry(message=message, reason=delete_reason, on_rate_limit=_on_rate_limit_hit)
                    deleted_count += 1
                    await _update_progress()

            if len(recent_batch) > 0:
                last_deleted_message_preview = self._get_message_preview(recent_batch[-1])
                await self._bulk_delete_messages_with_rate_limit_retry(channel=channel, messages=recent_batch, reason=delete_reason, on_rate_limit=_on_rate_limit_hit)
                deleted_count += len(recent_batch)
                await _update_progress()

            embed = self._build_cleanup_embed(
                channel_name=channel.name,
                state="done",
                deleted_count=deleted_count,
                rate_limit_retries=rate_limit_retries,
                elapsed_seconds=asyncio.get_running_loop().time() - started_monotonic,
                last_deleted_preview=last_deleted_message_preview,
                scanned_count=scanned_count,
            )
            await interaction.edit_original_response(content=None, embed=embed)
        except discord.HTTPException as e:
            if e.status == 429:
                _on_rate_limit_hit()
            embed = self._build_cleanup_embed(
                channel_name=channel.name,
                state="error",
                deleted_count=deleted_count,
                rate_limit_retries=rate_limit_retries,
                elapsed_seconds=asyncio.get_running_loop().time() - started_monotonic,
                last_deleted_preview=last_deleted_message_preview,
                scanned_count=scanned_count,
                error_text=f"Discord API error (status {e.status}): {e}",
            )
            logging.exception(msg=f"Discord API error while clearing messages in channel '{channel.name}': {e}")
            await interaction.edit_original_response(content=None, embed=embed)
        except Exception as e:
            embed = self._build_cleanup_embed(
                channel_name=channel.name,
                state="error",
                deleted_count=deleted_count,
                rate_limit_retries=rate_limit_retries,
                elapsed_seconds=asyncio.get_running_loop().time() - started_monotonic,
                last_deleted_preview=last_deleted_message_preview,
                scanned_count=scanned_count,
                error_text=str(e),
            )
            logging.exception(msg=f"Internal error while clearing messages in channel '{channel.name}': {e}")
            await interaction.edit_original_response(content=None, embed=embed)
        finally:
            heartbeat_stop_event.set()
            if heartbeat_task is not None and not heartbeat_task.done():
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass

    async def list_clearable_channels(self, interaction: discord.Interaction) -> None:
        if not self._check_if_valid_guild(guild=interaction.guild):
            return
        if not (await self._is_bot_channel_interaction(interaction=interaction, send_message_if_not_bot=True)):
            return
        if not self._is_private_channel(channel=interaction.channel): # type: ignore
            await interaction.response.send_message(content="❌ Public channels do not allow this command.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        bot_member = guild.me if guild is not None else None # type: ignore
        if guild is None or bot_member is None:
            await interaction.followup.send(content="❌ Unable to resolve the guild or bot member.", ephemeral=True)
            return

        try:
            clearable_lines: List[str] = []
            blocked_lines: List[str] = []

            for text_channel in guild.text_channels:
                perms = text_channel.permissions_for(bot_member)
                can_view: bool = perms.view_channel
                can_read_history: bool = perms.read_message_history
                can_manage: bool = perms.manage_messages
                is_clearable: bool = can_view and can_read_history and can_manage

                line = (
                    f"{'✅' if is_clearable else '❌'} #{text_channel.name} "
                    f"(View: {'✔' if can_view else '✘'}, "
                    f"History: {'✔' if can_read_history else '✘'}, "
                    f"Manage: {'✔' if can_manage else '✘'})"
                )
                if is_clearable:
                    clearable_lines.append(line)
                else:
                    blocked_lines.append(line)

            out_msg = f"🧹 **Clearable channels report** ({len(clearable_lines)} clearable / {len(guild.text_channels)} text channels)\n\n"
            out_msg += "**✅ Clearable:**\n" + ("\n".join(clearable_lines) if clearable_lines else "None") + "\n\n"
            out_msg += "**❌ Blocked (missing bot permission):**\n" + ("\n".join(blocked_lines) if blocked_lines else "None")

            await self._interaction_followup_send_no_limit(interaction=interaction, msg=out_msg)
        except Exception as e:
            out_msg = f"**Internal error listing clearable channels**:\n```sh\n{e}\n```"
            logging.exception(msg=out_msg)
            await self._interaction_followup_send_no_limit(interaction=interaction, msg=out_msg)

    async def list_commands(self, interaction: discord.Interaction) -> None:
        if not self._check_if_valid_guild(guild=interaction.guild):
            return
        if not (await self._is_bot_channel_interaction(interaction=interaction, send_message_if_not_bot=True)):
            return

        # Indiquer que la commande est en cours de traitement
        await interaction.response.defer()

        try:
            is_private: bool = self._is_private_channel(channel=interaction.channel) # type: ignore
            # Récupérer la liste des commandes disponibles
            out_msg: str = await self.monitoring.list_commands(is_private=is_private)

            # Répondre à l'utilisateur
            await self._interaction_followup_send_no_limit(interaction=interaction, msg=out_msg)
        except Exception as e:
            out_msg = f"**Internal error retrieving available commands**:\n```sh\n{e}\n```"
            logging.exception(msg=out_msg)
            await self._interaction_followup_send_no_limit(interaction=interaction, msg=out_msg)


    async def execute_command(self, interaction: discord.Interaction, command_name: str, parameters: str = "") -> None:
        if not self._check_if_valid_guild(guild=interaction.guild):
            return
        if not (await self._is_bot_channel_interaction(interaction=interaction, send_message_if_not_bot=True)):
            return

        # Indiquer que la commande est en cours de traitement
        await interaction.response.defer()

        try:
            is_private: bool = self._is_private_channel(channel=interaction.channel) # type: ignore
            # Exécuter la commande demandée
            out_msg: str = await self.monitoring.execute_command(is_private=is_private, command_name=command_name, parameters=parameters)

            # Répondre à l'utilisateur
            await self._interaction_followup_send_no_limit(interaction=interaction, msg=out_msg)
        except Exception as e:
            out_msg = f"**Internal error executing command '{command_name}'**:\n```sh\n{e}\n```"
            logging.exception(msg=out_msg)
            await self._interaction_followup_send_no_limit(interaction=interaction, msg=out_msg)

    async def execute_all_commands(self, interaction: discord.Interaction) -> None:
        if not self._check_if_valid_guild(guild=interaction.guild):
            return
        if not (await self._is_bot_channel_interaction(interaction=interaction, send_message_if_not_bot=True)):
            return

        # Indiquer que la commande est en cours de traitement
        await interaction.response.defer()

        try:
            is_private: bool = self._is_private_channel(channel=interaction.channel) # type: ignore
            # Exécuter toutes les commandes
            out_msg: str = await self.monitoring.execute_all_commands(is_private=is_private)

            # Répondre à l'utilisateur
            await self._interaction_followup_send_no_limit(interaction=interaction, msg=out_msg)
        except Exception as e:
            out_msg = f"**Internal error executing all commands**:\n```sh\n{e}\n```"
            logging.exception(msg=out_msg)
            await self._interaction_followup_send_no_limit(interaction=interaction, msg=out_msg)

    #endregion
