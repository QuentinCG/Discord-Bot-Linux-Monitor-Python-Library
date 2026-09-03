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
__version__ = "1.7.3 (2026/09/03)"
__status__ = "Usable for any Linux project"

# pyright: reportMissingTypeStubs=false
from linuxmonitor import LinuxMonitor

import discord
from discord.app_commands.models import AppCommand
from discord import app_commands
from discord.ext import commands
import json
from typing import List, Union, Awaitable, Callable, Any, Dict, Optional, Tuple
from datetime import datetime, timedelta, timezone

import asyncio
import functools
import os
import time
import logging


class ConfirmationView(discord.ui.View):
    """Confirmation dialog for dangerous commands."""
    def __init__(self, timeout: float = 30.0):
        super().__init__(timeout=timeout)
        self.confirmed: bool = False

    @discord.ui.button(label="✅ Confirm", style=discord.ButtonStyle.red)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.confirmed = True
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.gray)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.confirmed = False
        await interaction.response.defer()
        self.stop()

    async def on_timeout(self) -> None:
        self.confirmed = False


class PaginationView(discord.ui.View):
    """Pagination view for long messages with prev/next buttons."""
    def __init__(self, chunks: List[str], timeout: float = 180.0):
        super().__init__(timeout=timeout)
        self.chunks = chunks
        self.current_page: int = 0
        self.total_pages: int = len(chunks)
        self.message: Optional[discord.Message] = None
        self._update_button_states()

    def _update_button_states(self) -> None:
        """Update button disabled states based on current page."""
        self.prev_button.disabled = self.current_page <= 0
        self.next_button.disabled = self.current_page >= self.total_pages - 1

    @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.gray)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if self.current_page > 0:
            self.current_page -= 1
            self._update_button_states()
            await interaction.response.defer()
            if self.message:
                await self.message.edit(view=self)

    @discord.ui.button(label="▶️ Next", style=discord.ButtonStyle.gray)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self._update_button_states()
            await interaction.response.defer()
            if self.message:
                await self.message.edit(view=self)

    async def on_timeout(self) -> None:
        """Disable buttons after timeout."""
        for item in self.children:
            item.disabled = True


class DiscordBotLinuxMonitor:

    #region Initialization

    def __init__(self, config_file: str, force_sync_on_startup: bool) -> None:
        logging.debug(msg=f"Loading configuration file {config_file}...")
        with open(file=config_file, mode='r', encoding='utf-8') as file:
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
        intents: discord.Intents = discord.Intents.default()
        self.bot = commands.Bot(command_prefix=self.command_prefix, intents=intents)
        
        # Initialize cleanup task
        self.cleanup_task: Optional[asyncio.Task] = None

        # Discord calls on_ready on every gateway (re)identification, not only once per process:
        # this guard avoids re-sending welcome messages and starting duplicated scheduled tasks.
        self.startup_done: bool = False
        self.process_start_time: datetime = datetime.now()
        self.gateway_ready_count: int = 0
        self.gateway_disconnect_count: int = 0
        self.gateway_resume_count: int = 0

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

    def _get_utc_timestamp(self) -> str:
        """Get current timestamp in UTC with timezone info."""
        return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

    def _log_command_audit(self, user: discord.User, guild: Optional[discord.Guild], channel: Optional[discord.TextChannel], command: str, details: str = "") -> None:
        """Log command execution for audit trail."""
        timestamp = self._get_utc_timestamp()
        guild_name = guild.name if guild else "Unknown"
        channel_name = channel.name if channel else "Unknown"
        details_str = f" | {details}" if details else ""
        logging.info(msg=f"[AUDIT] {timestamp} | User: {user} (ID: {user.id}) | Guild: {guild_name} | Channel: #{channel_name} | Command: {command}{details_str}")

    @functools.lru_cache(maxsize=128)
    def _get_cached_command_names(self, is_private: bool) -> List[Tuple[str, str]]:
        """Cache command names permanently since they never change at runtime."""
        return self.monitoring.get_command_names(is_private=is_private)

    @functools.lru_cache(maxsize=128)
    def _get_cached_service_names(self, is_private: bool) -> List[Tuple[str, str]]:
        """Cache service names permanently since they never change at runtime."""
        return self.monitoring.get_service_names(is_private=is_private)

    def _is_periodic_cleanup_enabled(self) -> bool:
        """Check if periodic channel cleanup is enabled in config."""
        cleanup_config = self.config.get('periodic_channel_cleanup', {})  # type: ignore
        return cleanup_config.get('enabled', False)

    def _get_cleanup_interval(self) -> float:
        """Get the interval (in seconds) between cleanup cycles."""
        cleanup_config = self.config.get('periodic_channel_cleanup', {})  # type: ignore
        return float(cleanup_config.get('duration_in_sec_wait_between_each_execution', 604800))

    def _get_cleanup_initial_delay(self) -> float:
        """Get the initial delay (in seconds) before first cleanup execution."""
        cleanup_config = self.config.get('periodic_channel_cleanup', {})  # type: ignore
        return float(cleanup_config.get('duration_in_sec_before_first_execution', 604800))

    def _should_cleanup_start_immediately(self) -> bool:
        """Check if cleanup should start immediately (duration = 0)."""
        return self._get_cleanup_initial_delay() == 0

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

        embed.set_footer(text=f"Bot v{__version__} • Last update: {self._get_utc_timestamp()}")
        return embed

    def _infer_embed_color(self, text: str, is_error: bool = False) -> "discord.Color":
        # Color-code the embed depending on the status hints found in the text.
        if is_error or "❌" in text or "🔴" in text:
            return discord.Color.red()
        if "⚠️" in text or "🟠" in text or "🟡" in text:
            return discord.Color.orange()
        return discord.Color.green()

    def _build_result_embed(self, title: str, description: str, color: "discord.Color") -> "discord.Embed":
        embed = discord.Embed(title=title[:256], color=color)
        embed.description = (description if description.strip() != "" else "No answer.")[:4096]
        embed.set_footer(text=f"Bot v{__version__} • {self._get_utc_timestamp()}")
        return embed

    def _split_text_for_embed(self, text: str, max_length: int = 4000) -> List[str]:
        chunks: List[str] = []
        remaining: str = text
        while len(remaining) > max_length:
            split_point = remaining.rfind('\n', 0, max_length)
            if split_point == -1:
                split_point = max_length
            chunks.append(remaining[:split_point].rstrip())
            remaining = remaining[split_point:].lstrip()
        if remaining:
            chunks.append(remaining)
        return chunks

    async def _interaction_followup_send_embed(self, interaction: discord.Interaction, title: str, msg: str, icon: str = "", is_error: bool = False, ephemeral: bool = False, enable_pagination: bool = True) -> None:
        """Send an embed message via interaction followup. Handles pagination for long messages."""
        if msg is None or msg.strip() == "":
            msg = "No answer."

        # Only log info for non-error responses to reduce log spam
        if not is_error:
            logging.info(msg=f"Sending embed follow-up '{title}'")

        color: "discord.Color" = self._infer_embed_color(text=msg, is_error=is_error)
        display_title: str = f"{icon} {title}".strip()
        chunks: List[str] = self._split_text_for_embed(text=msg)

        try:
            # If single chunk or pagination disabled, send normally
            if len(chunks) <= 1 or not enable_pagination:
                for index, chunk in enumerate(chunks):
                    page_title: str = display_title if len(chunks) == 1 else f"{display_title} ({index + 1}/{len(chunks)})"
                    embed: "discord.Embed" = self._build_result_embed(title=page_title, description=chunk, color=color)
                    try:
                        await interaction.followup.send(embed=embed, ephemeral=ephemeral)
                    except discord.InteractionResponded:
                        logging.debug(msg=f"Interaction already responded for {title}")
                        return
            else:
                # Multiple chunks: use pagination
                class PaginatedEmbedView(discord.ui.View):
                    def __init__(self, paginator_self, chunks: List[str], title_template: str, color: discord.Color, ephemeral: bool):
                        super().__init__(timeout=180.0)
                        self.paginator = paginator_self
                        self.chunks = chunks
                        self.title_template = title_template
                        self.color = color
                        self.current_page = 0
                        self.message: Optional[discord.Message] = None
                        self.ephemeral = ephemeral
                        self._update_buttons()

                    def _update_buttons(self) -> None:
                        self.prev_btn.disabled = self.current_page <= 0
                        self.next_btn.disabled = self.current_page >= len(self.chunks) - 1

                    async def _update_embed(self, interaction: discord.Interaction) -> None:
                        chunk = self.chunks[self.current_page]
                        page_title = f"{self.title_template} ({self.current_page + 1}/{len(self.chunks)})"
                        embed = self.paginator._build_result_embed(title=page_title, description=chunk, color=self.color)
                        await interaction.response.defer()
                        if self.message:
                            await self.message.edit(embed=embed, view=self)

                    @discord.ui.button(label="◀️", style=discord.ButtonStyle.gray)
                    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
                        if self.current_page > 0:
                            self.current_page -= 1
                            self._update_buttons()
                            await self._update_embed(interaction)

                    @discord.ui.button(label="▶️", style=discord.ButtonStyle.gray)
                    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
                        if self.current_page < len(self.chunks) - 1:
                            self.current_page += 1
                            self._update_buttons()
                            await self._update_embed(interaction)

                    async def on_timeout(self) -> None:
                        for item in self.children:
                            item.disabled = True
                        if self.message:
                            try:
                                await self.message.edit(view=self)
                            except Exception:
                                pass

                view = PaginatedEmbedView(self, chunks, display_title, color, ephemeral)
                embed = self._build_result_embed(title=f"{display_title} (1/{len(chunks)})", description=chunks[0], color=color)
                try:
                    view.message = await interaction.followup.send(embed=embed, view=view, ephemeral=ephemeral)
                except discord.InteractionResponded:
                    logging.debug(msg=f"Interaction already responded for {title}")
                    return

        except Exception as e:
            logging.error(msg=f"Error while sending embed follow-up message: {e}")

    async def _channel_send_embed(self, channel: discord.TextChannel, title: str, msg: str, icon: str = "", is_error: bool = False, color: Optional["discord.Color"] = None) -> None:
        if msg is None or msg.strip() == "":
            return

        logging.info(msg=f"Sending embed to channel '{channel.name}' ('{title}'):\n{msg}")

        embed_color: "discord.Color" = color if color is not None else self._infer_embed_color(text=msg, is_error=is_error)
        display_title: str = f"{icon} {title}".strip()
        chunks: List[str] = self._split_text_for_embed(text=msg)

        for index, chunk in enumerate(chunks):
            page_title: str = display_title if len(chunks) == 1 else f"{display_title} ({index + 1}/{len(chunks)})"
            embed: "discord.Embed" = self._build_result_embed(title=page_title, description=chunk, color=embed_color)
            try:
                await channel.send(embed=embed)
            except Exception as e:
                logging.error(msg=f"Error while sending embed message to channel: {e}")

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

    async def _setup_periodic_cleanup_task(self) -> None:
        """Setup and start the periodic channel cleanup task."""
        if not self._is_periodic_cleanup_enabled():
            logging.info(msg="Periodic channel cleanup is disabled in config")
            return

        logging.info(msg="Setting up periodic channel cleanup task")
        self.cleanup_task = asyncio.create_task(self._periodic_cleanup_loop())

    async def _periodic_cleanup_loop(self) -> None:
        """Loop that periodically cleans configured channels."""
        await self.bot.wait_until_ready()
        
        # Wait before first execution if not immediate
        if not self._should_cleanup_start_immediately():
            initial_delay = self._get_cleanup_initial_delay()
            logging.info(msg=f"Periodic cleanup scheduled for {self._format_duration(initial_delay)} from now")
            await asyncio.sleep(initial_delay)
        
        while True:
            try:
                for guild in self.bot.guilds:
                    if guild.id == self.server_id:
                        await self._execute_cleanup_cycle(guild)
            except Exception as e:
                logging.error(msg=f"Error in cleanup loop: {e}")
            
            interval = self._get_cleanup_interval()
            await asyncio.sleep(interval)

    async def _execute_cleanup_cycle(self, guild: discord.Guild) -> None:
        """Execute cleanup for all configured channels."""
        cleanup_config = self.config.get('periodic_channel_cleanup', {})  # type: ignore
        channels_config = cleanup_config.get('channels', [])
        
        if not channels_config:
            return
        
        logging.info(msg=f"Starting periodic cleanup cycle for {len(channels_config)} channels")
        
        for channel_config in channels_config:
            try:
                channel_name = channel_config.get('channel_name')
                min_days = channel_config.get('min_days_to_keep', 7)
                description = channel_config.get('description', '')
                
                if not channel_name:
                    logging.warning(msg="Cleanup config entry missing 'channel_name'")
                    continue
                
                channel = discord.utils.get(guild.text_channels, name=channel_name)
                if not channel:
                    logging.warning(msg=f"Cleanup channel '{channel_name}' not found in guild")
                    continue
                
                # Check permissions
                bot_member = guild.me
                if bot_member is None:
                    logging.warning(msg="Unable to resolve bot member for cleanup")
                    continue
                
                permissions = channel.permissions_for(bot_member)
                if not permissions.manage_messages or not permissions.read_message_history:
                    logging.warning(msg=f"Bot missing permissions for cleanup in channel '{channel_name}'")
                    continue
                
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=min_days)
                deleted_count = 0
                
                async for message in channel.history(oldest_first=False):
                    if message.created_at < cutoff_date:
                        try:
                            await self._delete_message_with_rate_limit_retry(
                                message=message,
                                reason=f"Periodic cleanup - keeping messages newer than {min_days} days"
                            )
                            deleted_count += 1
                        except Exception as e:
                            logging.warning(msg=f"Failed to delete message in cleanup: {e}")
                            # Continue with next message
                            continue
                
                log_msg = f"Periodic cleanup #{channel_name}: Deleted {deleted_count} messages (kept last {min_days} days)"
                if description:
                    log_msg += f" - {description}"
                logging.info(msg=log_msg)
                
            except Exception as e:
                logging.error(msg=f"Error cleaning up channel '{channel_config.get('channel_name', 'unknown')}': {e}")
                continue

    #endregion

    #region BOT COMMANDS AND EVENTS DEFINITIONS

    async def on_ready(self) -> None:
        self.gateway_ready_count += 1
        logging.info(msg=f"Discord bot '{self.bot.user}' is ready (READY #{self.gateway_ready_count}, process running since {self.process_start_time.isoformat(sep=' ', timespec='seconds')}).")

        if self.startup_done:
            # The process did NOT restart: Discord simply forced a new gateway session (network loss,
            # gateway maintenance, invalidated session, ...). Redoing the startup would duplicate the
            # welcome messages and, more importantly, the periodic monitoring tasks.
            uptime_in_sec: float = (datetime.now() - self.process_start_time).total_seconds()
            logging.warning(msg=f"Discord gateway session re-established (READY #{self.gateway_ready_count}, {self.gateway_disconnect_count} disconnections, {self.gateway_resume_count} resumes, process uptime {uptime_in_sec:.0f}sec). Startup already done, skipping welcome messages and scheduled tasks creation.")
            return

        self.startup_done = True

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
                            await self._channel_send_embed(channel=channel, title="Welcome", icon="👋", msg=self._welcome_message_with_version(self.welcome_message_for_public_commands), color=discord.Color.blurple())

                    if self.channel_name_for_private_commands != "" and channel.name == self.channel_name_for_private_commands:
                        logging.info(msg="Found the private channel, it will be possible to do private commands.")
                        private_channel_cmd_ready = True
                        if self.welcome_message_for_private_commands != "":
                            await self._channel_send_embed(channel=channel, title="Welcome", icon="👋", msg=self._welcome_message_with_version(self.welcome_message_for_private_commands), color=discord.Color.blurple())

                    if self.channel_name_for_public_error_tasks != "" and channel.name == self.channel_name_for_public_error_tasks:
                        logging.info(msg="Found the public channel for error task, it will be possible to show public status issues if found periodically.")
                        public_channel_error_task_ready = True

                        if self.welcome_message_for_public_error_tasks != "":
                            await self._channel_send_embed(channel=channel, title="Welcome", icon="👋", msg=self._welcome_message_with_version(self.welcome_message_for_public_error_tasks), color=discord.Color.blurple())

                        logging.info(msg=f"Activating automatic public follow and public service restart if down with '{self.bot.user}' and guild '{guild.name}' (id: '{guild.id}') on channel '{channel.name}' (id '{channel.id}').")
                        public_channel_for_error_task: discord.TextChannel = channel
                        send_message_public_error_task_func: Callable[[str], Awaitable[None]] = lambda msg: asyncio.create_task(self._channel_send_embed(channel=public_channel_for_error_task, title="Monitoring Alert", icon="🚨", msg=msg, is_error=True))

                        # Start the public schedule task
                        self.bot.loop.create_task(self.monitoring.schedule_task(handle_error_message=send_message_public_error_task_func, is_private=False))

                    if self.channel_name_for_public_infos_tasks != "" and channel.name == self.channel_name_for_public_infos_tasks:
                        logging.info(msg="Found the public channel for info task, it will be possible to show public info periodically.")
                        public_channel_info_task_ready = True

                        if self.welcome_message_for_public_infos_tasks != "":
                            await self._channel_send_embed(channel=channel, title="Welcome", icon="👋", msg=self._welcome_message_with_version(self.welcome_message_for_public_infos_tasks), color=discord.Color.blurple())

                        logging.info(msg=f"Activating automatic public follow info with '{self.bot.user}' and guild '{guild.name}' (id: '{guild.id}') on channel '{channel.name}' (id '{channel.id}').")
                        public_channel_for_info_task: discord.TextChannel = channel
                        send_message_public_info_task_func: Callable[[str], Awaitable[None]] = lambda msg: asyncio.create_task(self._channel_send_embed(channel=public_channel_for_info_task, title="Periodic Status", icon="📊", msg=msg))

                        # Start the public schedule task
                        self.bot.loop.create_task(self.monitoring.schedule_task_show_info(show_message=send_message_public_info_task_func, is_private=False))

                    if self.channel_name_for_private_error_tasks != "" and channel.name == self.channel_name_for_private_error_tasks:
                        logging.info(msg="Found the private channel for error task, it will be possible to show private and public status issues if found periodically.")
                        private_channel_error_task_ready = True

                        if self.welcome_message_for_private_error_tasks != "":
                            await self._channel_send_embed(channel=channel, title="Welcome", icon="👋", msg=self._welcome_message_with_version(self.welcome_message_for_private_error_tasks), color=discord.Color.blurple())

                        logging.info(msg=f"Activating automatic private follow and public service restart if down with '{self.bot.user}' and guild '{guild.name}' (id: '{guild.id}') on channel '{channel.name}' (id '{channel.id}').")
                        private_channel_for_error_task: discord.TextChannel = channel
                        send_message_private_error_task_func: Callable[[str], Awaitable[None]] = lambda msg: asyncio.create_task(self._channel_send_embed(channel=private_channel_for_error_task, title="Monitoring Alert", icon="🚨", msg=msg, is_error=True))

                        # Start the private schedule task
                        self.bot.loop.create_task(self.monitoring.schedule_task(handle_error_message=send_message_private_error_task_func, is_private=True))

                    if self.channel_name_for_private_infos_tasks != "" and channel.name == self.channel_name_for_private_infos_tasks:
                        logging.info(msg="Found the private channel for info task, it will be possible to show private info periodically.")
                        private_channel_info_task_ready = True

                        if self.welcome_message_for_private_infos_tasks != "":
                            await self._channel_send_embed(channel=channel, title="Welcome", icon="👋", msg=self._welcome_message_with_version(self.welcome_message_for_private_infos_tasks), color=discord.Color.blurple())

                        logging.info(msg=f"Activating automatic private follow info with '{self.bot.user}' and guild '{guild.name}' (id: '{guild.id}') on channel '{channel.name}' (id '{channel.id}').")
                        private_channel_for_info_task: discord.TextChannel = channel
                        send_message_private_info_task_func: Callable[[str], Awaitable[None]] = lambda msg: asyncio.create_task(self._channel_send_embed(channel=private_channel_for_info_task, title="Periodic Status", icon="📊", msg=msg))

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

        # Sync the bot's commands globally (once, after all guilds are checked)
        if self.force_sync_on_startup:
            await self._force_sync()

        # Setup periodic channel cleanup task
        await self._setup_periodic_cleanup_task()

    async def on_disconnect(self) -> None:
        """
        Called when the gateway connection is lost. Useful to know if a "restart" was only a reconnection.
        """
        self.gateway_disconnect_count += 1
        logging.warning(msg=f"Discord gateway disconnected (#{self.gateway_disconnect_count}), discord.py will try to reconnect automatically.")

    async def on_resumed(self) -> None:
        """
        Called when the gateway session is resumed (no new READY, so no welcome message).
        """
        self.gateway_resume_count += 1
        logging.info(msg=f"Discord gateway session resumed (#{self.gateway_resume_count}).")

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
        await self._interaction_followup_send_embed(interaction=interaction, title="Command Synchronization", icon="🔄", msg=out_msg)

    async def version(self, interaction: discord.Interaction) -> None:
        if not self._check_if_valid_guild(guild=interaction.guild):
            return
        if not (await self._is_bot_channel_interaction(interaction=interaction, send_message_if_not_bot=True)):
            return

        out_msg: str = (
            f"🤖 Discord bot version: {__version__}\n"
            f"- Linux Monitor library version: {self.monitoring.get_raw_version()}\n"
            f"- 🐍 Python compatibility: {__python_version__}\n"
            f"- ⏱️ Bot process started on {self.process_start_time.strftime('%d/%m/%Y %H:%M:%S')} (PID {os.getpid()})\n"
            f"- 🔌 Gateway: {self.gateway_ready_count} ready, {self.gateway_disconnect_count} disconnections, {self.gateway_resume_count} resumes"
        )
        embed = self._build_result_embed(title="🤖 Bot Version", description=out_msg, color=discord.Color.blurple())
        await interaction.response.send_message(embed=embed, ephemeral=True)

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
            await self._interaction_followup_send_embed(interaction=interaction, title="System Usage", icon="📊", msg=out_msg)
        except Exception as e:
            out_msg = f"**Internal error retrieving usage info**:\n```sh\n{e}\n```"
            logging.exception(msg=out_msg)
            await self._interaction_followup_send_embed(interaction=interaction, title="System Usage", icon="📊", msg=out_msg, is_error=True)

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
            await self._interaction_followup_send_embed(interaction=interaction, title="OS Information", icon="🖥️", msg=out_msg)
        except Exception as e:
            out_msg = f"**Internal error retrieving OS info**:\n```sh\n{e}\n```"
            logging.exception(msg=out_msg)
            await self._interaction_followup_send_embed(interaction=interaction, title="OS Information", icon="🖥️", msg=out_msg, is_error=True)

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
            await self._interaction_followup_send_embed(interaction=interaction, title="Connected Users", icon="👥", msg=out_msg)
        except Exception as e:
            out_msg = f"**Internal error retrieving connected users**:\n```sh\n{e}\n```"
            logging.exception(msg=out_msg)
            await self._interaction_followup_send_embed(interaction=interaction, title="Connected Users", icon="👥", msg=out_msg, is_error=True)

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
            await self._interaction_followup_send_embed(interaction=interaction, title="Recent User Logins", icon="🔐", msg=out_msg)

        except Exception as e:
            out_msg = f"**Internal error retrieving last user connections**:\n```sh\n{e}\n```"
            logging.exception(msg=out_msg)
            await self._interaction_followup_send_embed(interaction=interaction, title="Recent User Logins", icon="🔐", msg=out_msg, is_error=True)

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
            await self._interaction_followup_send_embed(interaction=interaction, title="Websites Ping", icon="📡", msg=out_msg)
        except Exception as e:
            out_msg = f"**Internal error during websites ping **:\n```sh\n{e}\n```"
            logging.exception(msg=out_msg)
            await self._interaction_followup_send_embed(interaction=interaction, title="Websites Ping", icon="📡", msg=out_msg, is_error=True)

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
            await self._interaction_followup_send_embed(interaction=interaction, title="Websites Access", icon="🌐", msg=out_msg)
        except Exception as e:
            out_msg = f"**Internal error during websites access check **:\n```sh\n{e}\n```"
            logging.exception(msg=out_msg)
            await self._interaction_followup_send_embed(interaction=interaction, title="Websites Access", icon="🌐", msg=out_msg, is_error=True)

    async def certificates(self, interaction: discord.Interaction) -> None:
        if not self._check_if_valid_guild(guild=interaction.guild):
            return
        if not (await self._is_bot_channel_interaction(interaction=interaction, send_message_if_not_bot=True)):
            return

        # Say to the user that the command is being processed
        await interaction.response.defer()

        try:
            is_private: bool = self._is_private_channel(channel=interaction.channel) # type: ignore
            out_msg: str = await self.monitoring.check_all_certificates(is_private=is_private, display_only_if_critical=False)

            # Respond to the user
            await self._interaction_followup_send_embed(interaction=interaction, title="SSL Certificates", icon="🔒", msg=out_msg)
        except Exception as e:
            out_msg = f"**Internal error during SSL certificate checks **:\n```sh\n{e}\n```"
            logging.exception(msg=out_msg)
            await self._interaction_followup_send_embed(interaction=interaction, title="SSL Certificates", icon="🔒", msg=out_msg, is_error=True)

    async def reboot(self, interaction: discord.Interaction) -> None:
        if not self._check_if_valid_guild(guild=interaction.guild):
            return
        if not (await self._is_bot_channel_interaction(interaction=interaction, send_message_if_not_bot=True)):
            return
        if not self._is_private_channel(channel=interaction.channel): # type: ignore
            await interaction.response.send_message(content="❌ Public channels do not allow this command.", ephemeral=True)
            return

        # Show confirmation dialog
        await interaction.response.defer(ephemeral=True)

        view = ConfirmationView()
        confirmation_msg = await interaction.followup.send(
            content="⚠️ **DANGEROUS OPERATION** ⚠️\n\nYou are about to reboot the entire server. This will disconnect all users and services!\n\nAre you sure?",
            view=view,
            ephemeral=True
        )

        await view.wait()

        if not view.confirmed:
            await confirmation_msg.edit(content="❌ Server reboot cancelled.", view=None)
            self._log_command_audit(interaction.user, interaction.guild, interaction.channel, "reboot", "CANCELLED")
            return

        # Log the audit trail
        self._log_command_audit(interaction.user, interaction.guild, interaction.channel, "reboot", "CONFIRMED")

        try:
            await confirmation_msg.edit(content="⏳ Rebooting server...", view=None)
            out_msg: str = await self.monitoring.reboot_server()
            await self._interaction_followup_send_embed(interaction=interaction, title="Server Reboot", icon="🔁", msg=out_msg)

        except Exception as e:
            out_msg = f"**Internal error during server reboot**:\n```sh\n{e}\n```"
            logging.exception(msg=out_msg)
            await self._interaction_followup_send_embed(interaction=interaction, title="Server Reboot", icon="🔁", msg=out_msg, is_error=True)

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
            await self._interaction_followup_send_embed(interaction=interaction, title="Services Status", icon="⚙️", msg=out_msg)
        except Exception as e:
            out_msg = f"**Internal error checking services are running**:\n```sh\n{e}\n```"
            logging.exception(msg=out_msg)
            await self._interaction_followup_send_embed(interaction=interaction, title="Services Status", icon="⚙️", msg=out_msg, is_error=True)

    async def restart_all(self, interaction: discord.Interaction) -> None:
        if not self._check_if_valid_guild(guild=interaction.guild):
            return
        if not (await self._is_bot_channel_interaction(interaction=interaction, send_message_if_not_bot=True)):
            return

        # Log the audit trail
        self._log_command_audit(interaction.user, interaction.guild, interaction.channel, "restart_all")

        # Say to the user that the command is being processed
        await interaction.response.defer()

        try:
            # Restart all services and get the results
            is_private: bool = self._is_private_channel(channel=interaction.channel) # type: ignore
            out_msg: str = await self.monitoring.restart_all_services(is_private=is_private)

            # Respond to the user
            await self._interaction_followup_send_embed(interaction=interaction, title="Restart All Services", icon="🔄", msg=out_msg)
        except Exception as e:
            out_msg = f"**Internal error restarting all services**:\n```sh\n{e}\n```"
            logging.exception(msg=out_msg)
            await self._interaction_followup_send_embed(interaction=interaction, title="Restart All Services", icon="🔄", msg=out_msg, is_error=True)

    async def restart_service(self, interaction: discord.Interaction, service_name: str) -> None:
        if not self._check_if_valid_guild(guild=interaction.guild):
            return
        if not (await self._is_bot_channel_interaction(interaction=interaction, send_message_if_not_bot=True)):
            return

        # Log the audit trail
        self._log_command_audit(interaction.user, interaction.guild, interaction.channel, "restart_service", f"service={service_name}")

        # Indiquer que la commande est en cours de traitement
        await interaction.response.defer()

        try:
            # Redémarrer le service et récupérer le message de sortie
            is_private: bool = self._is_private_channel(channel=interaction.channel) # type: ignore
            out_msg: str = await self.monitoring.restart_service(is_private=is_private, service_name=service_name, force_restart=True)

            # Répondre à l'utilisateur
            await self._interaction_followup_send_embed(interaction=interaction, title="Restart Service", icon="🔄", msg=out_msg)

        except Exception as e:
            out_msg = f"**Internal error restarting service {service_name}**:\n```sh\n{e}\n```"
            logging.exception(msg=out_msg)
            await self._interaction_followup_send_embed(interaction=interaction, title="Restart Service", icon="🔄", msg=out_msg, is_error=True)

    async def stop_service(self, interaction: discord.Interaction, service_name: str) -> None:
        if not self._check_if_valid_guild(guild=interaction.guild):
            return
        if not (await self._is_bot_channel_interaction(interaction=interaction, send_message_if_not_bot=True)):
            return

        # Log the audit trail
        self._log_command_audit(interaction.user, interaction.guild, interaction.channel, "stop_service", f"service={service_name}")

        # Indiquer que la commande est en cours de traitement
        await interaction.response.defer()

        try:
            # Arrêter le service et récupérer le message de sortie
            is_private: bool = self._is_private_channel(channel=interaction.channel) # type: ignore
            out_msg: str = await self.monitoring.stop_service(is_private=is_private, service_name=service_name)

            # Répondre à l'utilisateur
            await self._interaction_followup_send_embed(interaction=interaction, title="Stop Service", icon="🛑", msg=out_msg)
        except Exception as e:
            out_msg = f"**Internal error stopping service {service_name}**:\n```sh\n{e}\n```"
            logging.exception(msg=out_msg)
            await self._interaction_followup_send_embed(interaction=interaction, title="Stop Service", icon="🛑", msg=out_msg, is_error=True)

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
            await self._interaction_followup_send_embed(interaction=interaction, title="Available Services", icon="📋", msg=out_msg)
        except Exception as e:
            out_msg = f"**Internal error retrieving available services**:\n```sh\n{e}\n```"
            logging.exception(msg=out_msg)
            await self._interaction_followup_send_embed(interaction=interaction, title="Available Services", icon="📋", msg=out_msg, is_error=True)

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
            await self._interaction_followup_send_embed(interaction=interaction, title="Ports Status", icon="🔌", msg=out_msg)
        except Exception as e:
            out_msg = f"**Internal error checking ports**:\n```sh\n{e}\n```"
            logging.exception(msg=out_msg)
            await self._interaction_followup_send_embed(interaction=interaction, title="Ports Status", icon="🔌", msg=out_msg, is_error=True)

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
            await self._interaction_followup_send_embed(interaction=interaction, title="Processes List", icon="🧮", msg=out_msg)
        except Exception as e:
            out_msg = f"**Internal error retrieving active processes**:\n```sh\n{e}\n```"
            logging.exception(msg=out_msg)
            await self._interaction_followup_send_embed(interaction=interaction, title="Processes List", icon="🧮", msg=out_msg, is_error=True)

    async def kill_process(self, interaction: discord.Interaction, pid: int) -> None:
        if not self._check_if_valid_guild(guild=interaction.guild):
            return
        if not (await self._is_bot_channel_interaction(interaction=interaction, send_message_if_not_bot=True)):
            return
        if not self._is_private_channel(channel=interaction.channel): # type: ignore
            await interaction.response.send_message(content="❌ Public channels do not allow this command.", ephemeral=True)
            return

        # Log the audit trail
        self._log_command_audit(interaction.user, interaction.guild, interaction.channel, "kill_process", f"pid={pid}")

        # Indiquer que la commande est en cours de traitement
        await interaction.response.defer()

        try:
            # Arrêter le processus et récupérer le message de sortie
            out_msg: str = await self.monitoring.kill_process(pid=pid)

            # Répondre à l'utilisateur
            await self._interaction_followup_send_embed(interaction=interaction, title="Kill Process", icon="☠️", msg=out_msg)
        except Exception as e:
            out_msg = f"**Internal error stopping process of PID {pid}**:\n```sh\n{e}\n```"
            logging.exception(msg=out_msg)
            await self._interaction_followup_send_embed(interaction=interaction, title="Kill Process", icon="☠️", msg=out_msg, is_error=True)

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

        # Log the audit trail for this destructive action
        self._log_command_audit(interaction.user, interaction.guild, interaction.channel, "clear_channel_messages", f"target_channel=#{channel.name}")

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

            await self._interaction_followup_send_embed(interaction=interaction, title="Clearable Channels", icon="🧹", msg=out_msg, ephemeral=True)
        except Exception as e:
            out_msg = f"**Internal error listing clearable channels**:\n```sh\n{e}\n```"
            logging.exception(msg=out_msg)
            await self._interaction_followup_send_embed(interaction=interaction, title="Clearable Channels", icon="🧹", msg=out_msg, is_error=True, ephemeral=True)

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
            await self._interaction_followup_send_embed(interaction=interaction, title="Available Commands", icon="📖", msg=out_msg)
        except Exception as e:
            out_msg = f"**Internal error retrieving available commands**:\n```sh\n{e}\n```"
            logging.exception(msg=out_msg)
            await self._interaction_followup_send_embed(interaction=interaction, title="Available Commands", icon="📖", msg=out_msg, is_error=True)

    async def show_list_periodic_channels_cleanup(self, interaction: discord.Interaction) -> None:
        """Show auto-cleanup channel configuration and permission status."""
        if not self._check_if_valid_guild(guild=interaction.guild):
            return
        if not (await self._is_bot_channel_interaction(interaction=interaction, send_message_if_not_bot=True)):
            return
        if not self._is_private_channel(channel=interaction.channel):  # type: ignore
            await interaction.response.send_message(content="❌ This command is only available in private channels.", ephemeral=True)
            return

        await interaction.response.defer()

        try:
            # Check if cleanup is enabled
            if not self._is_periodic_cleanup_enabled():
                await self._interaction_followup_send_embed(
                    interaction=interaction,
                    title="Channel Auto-Cleanup Configuration",
                    icon="🧹",
                    msg="⚠️ **Periodic channel cleanup is DISABLED** in config"
                )
                return

            cleanup_config = self.config.get('periodic_channel_cleanup', {})  # type: ignore
            channels_config = cleanup_config.get('channels', [])

            if not channels_config:
                await self._interaction_followup_send_embed(
                    interaction=interaction,
                    title="Channel Auto-Cleanup Configuration",
                    icon="🧹",
                    msg="⚠️ **No channels configured** for auto-cleanup"
                )
                return

            guild = interaction.guild
            bot_member = guild.me if guild else None
            
            lines = [
                f"**Status**: ✅ Enabled",
                f"**Next Cleanup**: {self._format_duration(self._get_cleanup_initial_delay())} from bot start",
                f"**Cleanup Interval**: Every {self._format_duration(self._get_cleanup_interval())}",
                "",
                "**Configured Channels**:",
                ""
            ]

            for idx, channel_config in enumerate(channels_config, 1):
                channel_name = channel_config.get('channel_name', 'unknown')
                min_days = channel_config.get('min_days_to_keep', 7)
                description = channel_config.get('description', '')

                # Find channel
                channel = discord.utils.get(guild.text_channels, name=channel_name) if guild else None
                channel_status = "✅" if channel else "❌"

                # Check permissions if channel exists
                perms_status = "✅"
                perms_details = []
                if channel and bot_member:
                    permissions = channel.permissions_for(bot_member)
                    if not permissions.manage_messages:
                        perms_status = "❌"
                        perms_details.append("missing `manage_messages`")
                    if not permissions.read_message_history:
                        perms_status = "❌"
                        perms_details.append("missing `read_message_history`")
                elif channel and not bot_member:
                    perms_status = "⚠️"
                    perms_details.append("bot member not found")
                elif not channel:
                    perms_status = "N/A"
                    perms_details.append("channel not found")

                # Build channel line
                channel_line = f"**{idx}. {channel_status} #{channel_name}**"
                if description:
                    channel_line += f"\n   📝 {description}"
                channel_line += f"\n   🕐 Keep messages: Last {min_days} days"
                channel_line += f"\n   🔐 Permissions: {perms_status}"
                if perms_details:
                    channel_line += f" ({', '.join(perms_details)})"

                lines.append(channel_line)
                lines.append("")

            # Summary
            summary_icon = "✅"
            all_ok = True
            for ch in channels_config:
                channel_name = ch.get('channel_name', '')
                channel = discord.utils.get(guild.text_channels, name=channel_name) if guild else None
                if not channel or not bot_member:
                    all_ok = False
                    break

                permissions = channel.permissions_for(bot_member)
                if not permissions.manage_messages or not permissions.read_message_history:
                    all_ok = False
                    break

            if not all_ok:
                summary_icon = "⚠️"

            lines.append(f"**Overall Status**: {summary_icon} " + ("All channels properly configured" if all_ok else "Some issues need attention"))

            msg = "\n".join(lines)
            is_error = not all_ok
            
            await self._interaction_followup_send_embed(
                interaction=interaction,
                title="Channel Auto-Cleanup Configuration",
                icon="🧹",
                msg=msg,
                is_error=is_error
            )

        except Exception as e:
            out_msg = f"**Internal error checking cleanup configuration**:\n```sh\n{e}\n```"
            logging.exception(msg=out_msg)
            await self._interaction_followup_send_embed(
                interaction=interaction,
                title="Channel Auto-Cleanup Configuration",
                icon="🧹",
                msg=out_msg,
                is_error=True
            )

    async def show_help(self, interaction: discord.Interaction, command_name: str = "") -> None:
        """Show help for Discord bot commands with cooldown info."""
        if not self._check_if_valid_guild(guild=interaction.guild):
            return
        if not (await self._is_bot_channel_interaction(interaction=interaction, send_message_if_not_bot=True)):
            return

        await interaction.response.defer()

        try:
            # Get all commands from the bot tree
            commands_list: List[str] = []
            
            # Command metadata with descriptions, cooldowns, and requirements
            command_info = {
                "force_sync": {"desc": "🔄 Force command synchronization", "cooldown": "3/20s", "private": True},
                "version": {"desc": "🤖 Show bot version", "cooldown": "3/20s", "private": False},
                "usage": {"desc": "📊 View disk space, CPU, RAM", "cooldown": "3/20s", "private": False},
                "os_infos": {"desc": "🖥️ View basic system info", "cooldown": "3/20s", "private": False},
                "users": {"desc": "👥 View connected users (private)", "cooldown": "3/20s", "private": True},
                "user_logins": {"desc": "👥 View last user connections (private)", "cooldown": "3/20s", "private": True},
                "ping": {"desc": "🌐 Ping websites", "cooldown": "3/20s", "private": False},
                "websites": {"desc": "🌐 Check website access", "cooldown": "3/20s", "private": False},
                "certificates": {"desc": "🔒 Check SSL certificates", "cooldown": "3/20s", "private": False},
                "reboot_server": {"desc": "🔄 Restart the entire server (private, requires confirmation)", "cooldown": "1/60s", "private": True},
                "services_status": {"desc": "🩺 Check services status", "cooldown": "3/20s", "private": False},
                "restart_all": {"desc": "🚀 Restart all services", "cooldown": "1/30s", "private": False},
                "restart_service": {"desc": "🚀 Restart a specific service", "cooldown": "3/20s", "private": False},
                "stop_service": {"desc": "🛑 Stop a service", "cooldown": "3/20s", "private": False},
                "list_services": {"desc": "📋 List all services", "cooldown": "3/20s", "private": False},
                "ports": {"desc": "🔒 Check ports", "cooldown": "3/20s", "private": False},
                "list_processes": {"desc": "📋 List processes by RAM (private)", "cooldown": "3/20s", "private": True},
                "list_processes_by_cpu_usage": {"desc": "📋 List processes by CPU (private)", "cooldown": "3/20s", "private": True},
                "kill_process": {"desc": "☠️ Kill process by PID (private)", "cooldown": "3/20s", "private": True},
                "clear_channel_messages": {"desc": "🧹 Clear channel messages (private, destructive)", "cooldown": "1/120s", "private": True},
                "list_clearable_channels": {"desc": "🧹 Show clearable channels (private)", "cooldown": "3/20s", "private": True},
                "list_commands": {"desc": "📋 List Linux monitor commands", "cooldown": "3/20s", "private": False},
                "execute_command": {"desc": "🚀 Execute a Linux command", "cooldown": "3/20s", "private": False},
                "execute_all_commands": {"desc": "🚀 Execute all Linux commands", "cooldown": "1/60s", "private": False},
                "help": {"desc": "🔍 Show this help message", "cooldown": "3/20s", "private": False},
                "list_periodic_channels_cleanup": {"desc": "🧹 Show auto-cleanup channel configuration and permission status", "cooldown": "3/20s", "private": True},
            }

            # Filter commands based on channel privacy
            is_private_channel = self._is_private_channel(channel=interaction.channel)  # type: ignore
            filtered_commands = {k: v for k, v in command_info.items() if v.get("private", False) == is_private_channel or not v.get("private", False)}
            
            # Filter by command name if provided
            if command_name:
                command_name_lower = command_name.lower()
                matching_cmds = {k: v for k, v in filtered_commands.items() if command_name_lower in k.lower()}
                if not matching_cmds:
                    out_msg = f"❌ No commands found matching '{command_name}'"
                    await self._interaction_followup_send_embed(interaction=interaction, title="Help", icon="🔍", msg=out_msg)
                    return
                command_info = matching_cmds
            else:
                command_info = filtered_commands

            # Build help text
            out_msg = ""
            for cmd, info in sorted(command_info.items()):
                private_indicator = "🔒 Private" if info["private"] else "🌐 Public"
                out_msg += f"**/{cmd}** — {info['desc']}\n"
                out_msg += f"  └─ {private_indicator} | ⏳ Cooldown: {info['cooldown']}\n\n"

            await self._interaction_followup_send_embed(interaction=interaction, title="Discord Bot Commands Help", icon="🔍", msg=out_msg)
        except Exception as e:
            out_msg = f"**Internal error retrieving help**:\n```sh\n{e}\n```"
            logging.exception(msg=out_msg)
            await self._interaction_followup_send_embed(interaction=interaction, title="Help", icon="🔍", msg=out_msg, is_error=True)


    async def autocomplete_command_name(self, interaction: discord.Interaction, current: str) -> List["app_commands.Choice[str]"]:
        # Suggest the configured command names so the user picks from a list instead of typing them.
        try:
            is_private: bool = self._is_private_channel(channel=interaction.channel) # type: ignore
            current_lower: str = current.lower()
            choices: List["app_commands.Choice[str]"] = []
            for command_name, display_name in self._get_cached_command_names(is_private=is_private):
                if current_lower == "" or current_lower in command_name.lower() or current_lower in display_name.lower():
                    label: str = f"{command_name} — {display_name}"
                    choices.append(app_commands.Choice(name=label[:100], value=command_name))
                if len(choices) >= 25: # Discord limits autocomplete to 25 choices
                    break
            return choices
        except Exception as e:
            logging.error(msg=f"Error while building command autocomplete: {e}")
            return []

    async def autocomplete_service_name(self, interaction: discord.Interaction, current: str) -> List["app_commands.Choice[str]"]:
        # Suggest the configured service names so the user picks from a list instead of typing them.
        try:
            is_private: bool = self._is_private_channel(channel=interaction.channel) # type: ignore
            current_lower: str = current.lower()
            choices: List["app_commands.Choice[str]"] = []
            for service_name, display_name in self._get_cached_service_names(is_private=is_private):
                if current_lower == "" or current_lower in service_name.lower() or current_lower in display_name.lower():
                    label: str = f"{service_name} — {display_name}"
                    choices.append(app_commands.Choice(name=label[:100], value=service_name))
                if len(choices) >= 25: # Discord limits autocomplete to 25 choices
                    break
            return choices
        except Exception as e:
            logging.error(msg=f"Error while building service autocomplete: {e}")
            return []

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
            await self._interaction_followup_send_embed(interaction=interaction, title=f"Execute Command — {command_name}", icon="▶️", msg=out_msg)
        except Exception as e:
            out_msg = f"**Internal error executing command '{command_name}'**:\n```sh\n{e}\n```"
            logging.exception(msg=out_msg)
            await self._interaction_followup_send_embed(interaction=interaction, title=f"Execute Command — {command_name}", icon="▶️", msg=out_msg, is_error=True)

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
            await self._interaction_followup_send_embed(interaction=interaction, title="Execute All Commands", icon="⏩", msg=out_msg)
        except Exception as e:
            out_msg = f"**Internal error executing all commands**:\n```sh\n{e}\n```"
            logging.exception(msg=out_msg)
            await self._interaction_followup_send_embed(interaction=interaction, title="Execute All Commands", icon="⏩", msg=out_msg, is_error=True)

    #endregion
