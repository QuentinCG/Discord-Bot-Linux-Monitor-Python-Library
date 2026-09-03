from .discordbotlinuxmonitor import DiscordBotLinuxMonitor

import argparse
import sys
import logging

import discord
from discord import app_commands

def main() -> None:
    parser = argparse.ArgumentParser(description='System Management Tool controled from Discord')

    # Define available arguments
    parser.add_argument('--config_file', type=str, required=True, help='Path to the configuration file (must be a JSON file)')
    parser.add_argument('--force_sync_on_startup', action='store_true', help='Force discord command synchronization on startup (do it only the first time, because after, you will have a discord command to do it if really needed)')

    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--nodebug', action='store_true', help='Disable all logs')

    # Parse arguments
    args = parser.parse_args()

    # Enable or disable debug mode
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.nodebug:
        logging.getLogger().setLevel(logging.CRITICAL)
    else:
        # Default to warning
        logging.getLogger().setLevel(logging.WARNING)

    # Ensure the config file is provided
    if not args.config_file:
        print("Error: --config_file is required")
        parser.print_help()
        sys.exit(1)
    config_file: str = args.config_file

    # Check if force_sync_on_startup is provided
    force_sync_on_startup: bool = False
    if args.force_sync_on_startup:
        force_sync_on_startup = True

    # Prepare the Discord bot (will throw an exception if the configuration is invalid)
    discord_bot_linux_monitor = DiscordBotLinuxMonitor(config_file=config_file, force_sync_on_startup=force_sync_on_startup)
    discord_bot = discord_bot_linux_monitor.bot

    #region BOT COMMANDS AND EVENTS REGIRSTRATION

    @discord_bot.event
    async def on_ready() -> None: # type: ignore
        await discord_bot_linux_monitor.on_ready()

    @discord_bot.event
    async def on_disconnect() -> None: # type: ignore
        await discord_bot_linux_monitor.on_disconnect()

    @discord_bot.event
    async def on_resumed() -> None: # type: ignore
        await discord_bot_linux_monitor.on_resumed()

    @discord_bot.tree.command(name="force_sync", description="[Private] 🔄 Force command synchronization 🔄")
    @app_commands.checks.cooldown(3, 20.0)
    async def force_sync(interaction: discord.Interaction) -> None: # type: ignore
        await discord_bot_linux_monitor.force_sync(interaction)

    @discord_bot.tree.command(name="version", description="🤖 Show bot version 🤖")
    @app_commands.checks.cooldown(3, 20.0)
    async def version(interaction: discord.Interaction) -> None: # type: ignore
        await discord_bot_linux_monitor.version(interaction)

    @discord_bot.tree.command(name="usage", description="📊 View disk space, CPU, RAM, ... 📊")
    @app_commands.checks.cooldown(3, 20.0)
    async def usage(interaction: discord.Interaction) -> None: # type: ignore
        await discord_bot_linux_monitor.usage(interaction)

    @discord_bot.tree.command(name="os_infos", description="🖥️ View basic system information 🖥️")
    @app_commands.checks.cooldown(3, 20.0)
    async def os_infos(interaction: discord.Interaction) -> None: # type: ignore
        await discord_bot_linux_monitor.os_infos(interaction)

    @discord_bot.tree.command(name="users", description="[Private] 👥 View connected users 👥")
    @app_commands.checks.cooldown(3, 20.0)
    async def users(interaction: discord.Interaction) -> None: # type: ignore
        await discord_bot_linux_monitor.users(interaction)

    @discord_bot.tree.command(name="user_logins", description="[Private] 👥 View last user connections 👥")
    @app_commands.checks.cooldown(3, 20.0)
    async def user_logins(interaction: discord.Interaction) -> None: # type: ignore
        await discord_bot_linux_monitor.user_logins(interaction)

    @discord_bot.tree.command(name="ping", description="🌐 Ping websites 🌐")
    @app_commands.checks.cooldown(3, 20.0)
    async def ping(interaction: discord.Interaction) -> None: # type: ignore
        await discord_bot_linux_monitor.ping(interaction)

    @discord_bot.tree.command(name="websites", description="🌐 Check websites access (GET requests) 🌐")
    @app_commands.checks.cooldown(3, 20.0)
    async def websites(interaction: discord.Interaction) -> None: # type: ignore
        await discord_bot_linux_monitor.websites(interaction)

    @discord_bot.tree.command(name="certificates", description="🔒 Check SSL certificates 🔒")
    @app_commands.checks.cooldown(3, 20.0)
    async def certificates(interaction: discord.Interaction) -> None: # type: ignore
        await discord_bot_linux_monitor.certificates(interaction)

    @discord_bot.tree.command(name="reboot_server", description="[Private] 🔄 Restart the entire server 🔄")
    @app_commands.checks.cooldown(1, 60.0)  # 1 use per 60 seconds - dangerous operation
    async def reboot(interaction: discord.Interaction) -> None: # type: ignore
        await discord_bot_linux_monitor.reboot(interaction)

    @discord_bot.tree.command(name="services_status", description="🩺 Check services are running 🩺")
    @app_commands.checks.cooldown(3, 20.0)
    async def services_status(interaction: discord.Interaction) -> None: # type: ignore
        await discord_bot_linux_monitor.services_status(interaction)

    @discord_bot.tree.command(name="restart_all", description="🚀 Restart all services 🚀")
    @app_commands.checks.cooldown(1, 30.0)  # 1 use per 30 seconds
    async def restart_all(interaction: discord.Interaction) -> None: # type: ignore
        await discord_bot_linux_monitor.restart_all(interaction)

    @discord_bot.tree.command(name="restart_service", description="🚀 Restart a service 🚀")
    @app_commands.autocomplete(service_name=discord_bot_linux_monitor.autocomplete_service_name)
    @app_commands.checks.cooldown(3, 20.0)  # 3 uses per 20 seconds
    async def restart_service(interaction: discord.Interaction, service_name: str) -> None: # type: ignore
        await discord_bot_linux_monitor.restart_service(interaction, service_name)

    @discord_bot.tree.command(name="stop_service", description="🚫 Stop a service 🚫")
    @app_commands.autocomplete(service_name=discord_bot_linux_monitor.autocomplete_service_name)
    @app_commands.checks.cooldown(3, 20.0)  # 3 uses per 20 seconds
    async def stop_service(interaction: discord.Interaction, service_name: str) -> None: # type: ignore
        await discord_bot_linux_monitor.stop_service(interaction, service_name)

    @discord_bot.tree.command(name="list_services", description="📋 List all available services 📋")
    @app_commands.checks.cooldown(3, 20.0)
    async def list_services(interaction: discord.Interaction) -> None: # type: ignore
        await discord_bot_linux_monitor.list_services(interaction)

    @discord_bot.tree.command(name="ports", description="🔒 Check ports 🔒")
    @app_commands.checks.cooldown(3, 20.0)
    async def ports(interaction: discord.Interaction) -> None: # type: ignore
        await discord_bot_linux_monitor.ports(interaction)

    @discord_bot.tree.command(name="list_processes", description="[Private] 📋 List active processes (ordered by RAM usage) 📋")
    @app_commands.checks.cooldown(3, 20.0)
    async def list_processes(interaction: discord.Interaction) -> None: # type: ignore
        await discord_bot_linux_monitor.list_processes(interaction, order_by_ram=True)

    @discord_bot.tree.command(name="list_processes_by_cpu_usage", description="[Private] 📋 List active processes (ordered by CPU usage) 📋")
    @app_commands.checks.cooldown(3, 20.0)
    async def list_processes_by_cpu_usage(interaction: discord.Interaction) -> None: # type: ignore
        await discord_bot_linux_monitor.list_processes(interaction, order_by_ram=False)

    @discord_bot.tree.command(name="kill_process", description="[Private] 🚫 Stop a process by PID 🚫")
    @app_commands.checks.cooldown(3, 20.0)
    async def kill_process(interaction: discord.Interaction, pid: int) -> None: # type: ignore
        await discord_bot_linux_monitor.kill_process(interaction, pid)

    @discord_bot.tree.command(name="clear_channel_messages", description="[Private] 🧹 Remove all messages from a channel 🧹")
    @app_commands.checks.cooldown(1, 120.0)  # 1 use per 120 seconds (2 minutes) - very destructive
    async def clear_channel_messages(interaction: discord.Interaction, channel: discord.TextChannel) -> None: # type: ignore
        await discord_bot_linux_monitor.clear_channel_messages(interaction, channel)

    @discord_bot.tree.command(name="list_clearable_channels", description="[Private] 🧹 List text channels and bot clear permissions 🧹")
    @app_commands.checks.cooldown(3, 20.0)
    async def list_clearable_channels(interaction: discord.Interaction) -> None: # type: ignore
        await discord_bot_linux_monitor.list_clearable_channels(interaction)

    @discord_bot.tree.command(name="list_commands", description="📋 List all available commands 📋")
    @app_commands.checks.cooldown(3, 20.0)
    async def list_commands(interaction: discord.Interaction) -> None: # type: ignore
        await discord_bot_linux_monitor.list_commands(interaction)

    @discord_bot.tree.command(name="help", description="🔍 Show Discord bot commands with info and cooldowns 🔍")
    @app_commands.checks.cooldown(3, 20.0)
    async def help_command(interaction: discord.Interaction, command_name: str = "") -> None: # type: ignore
        await discord_bot_linux_monitor.show_help(interaction, command_name)

    @discord_bot.tree.command(name="list_periodic_channels_cleanup", description="[Private] 🧹 Show auto-cleanup channel configuration and permission status 🧹")
    @app_commands.checks.cooldown(3, 20.0)
    async def list_periodic_channels_cleanup(interaction: discord.Interaction) -> None: # type: ignore
        await discord_bot_linux_monitor.show_list_periodic_channels_cleanup(interaction)

    @discord_bot.tree.command(name="execute_command", description="🚀 Execute a command (optional parameters) 🚀")
    @app_commands.autocomplete(command_name=discord_bot_linux_monitor.autocomplete_command_name)
    @app_commands.checks.cooldown(3, 20.0)  # 3 uses per 20 seconds
    async def execute_command(interaction: discord.Interaction, command_name: str, parameters: str = "") -> None: # type: ignore
        await discord_bot_linux_monitor.execute_command(interaction, command_name=command_name, parameters=parameters)

    @discord_bot.tree.command(name="execute_all_commands", description="🚀 Execute all commands 🚀")
    @app_commands.checks.cooldown(1, 60.0)  # 1 use per 60 seconds
    async def execute_all_commands(interaction: discord.Interaction) -> None: # type: ignore
        await discord_bot_linux_monitor.execute_all_commands(interaction)

    @discord_bot.tree.error
    async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None: # type: ignore
        """Handle cooldown and other command errors gracefully."""
        if isinstance(error, app_commands.CommandOnCooldown):
            retry_after = error.retry_after
            await interaction.response.send_message(
                content=f"⏳ This command is on cooldown. Please wait {retry_after:.1f} seconds before using it again.",
                ephemeral=True
            )
        elif isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                content="❌ You don't have permission to use this command.",
                ephemeral=True
            )
        else:
            logging.error(msg=f"Unhandled command error: {error}")
            try:
                await interaction.response.send_message(
                    content="❌ An unexpected error occurred. Please try again later.",
                    ephemeral=True
                )
            except discord.InteractionResponded:
                logging.warning(msg="Interaction already responded when handling error")

    #endregion

    # Start the discord bot
    logging.info(msg="Starting the Discord bot...")
    try:
        discord_bot.run(token=discord_bot_linux_monitor.server_token)
    except Exception as e:
        logging.exception(msg=f"Error while running the bot: {e}")

if __name__ == "__main__":
    main()
