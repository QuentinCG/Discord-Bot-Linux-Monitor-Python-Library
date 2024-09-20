from .discordbotlinuxmonitor import DiscordBotLinuxMonitor

import argparse
import sys
import logging

import discord

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

    @discord_bot.tree.command(name="force_sync", description="[Private] 🔄 Force command synchronization 🔄")
    async def force_sync(interaction: discord.Interaction) -> None: # type: ignore
        await discord_bot_linux_monitor.force_sync(interaction)

    @discord_bot.tree.command(name="usage", description="📊 View disk space, CPU, RAM, ... 📊")
    async def usage(interaction: discord.Interaction) -> None: # type: ignore
        await discord_bot_linux_monitor.usage(interaction)

    @discord_bot.tree.command(name="os_infos", description="🖥️ View basic system information 🖥️")
    async def os_infos(interaction: discord.Interaction) -> None: # type: ignore
        await discord_bot_linux_monitor.os_infos(interaction)

    @discord_bot.tree.command(name="users", description="[Private] 👥 View connected users 👥")
    async def users(interaction: discord.Interaction) -> None: # type: ignore
        await discord_bot_linux_monitor.users(interaction)

    @discord_bot.tree.command(name="user_logins", description="[Private] 👥 View last user connections 👥")
    async def user_logins(interaction: discord.Interaction) -> None: # type: ignore
        await discord_bot_linux_monitor.user_logins(interaction)

    @discord_bot.tree.command(name="ping", description="🌐 Ping websites 🌐")
    async def ping(interaction: discord.Interaction) -> None: # type: ignore
        await discord_bot_linux_monitor.ping(interaction)

    @discord_bot.tree.command(name="websites", description="🌐 Check websites access (GET requests) 🌐")
    async def websites(interaction: discord.Interaction) -> None: # type: ignore
        await discord_bot_linux_monitor.websites(interaction)

    @discord_bot.tree.command(name="certificates", description="🔒 Check SSL certificates 🔒")
    async def certificates(interaction: discord.Interaction) -> None: # type: ignore
        await discord_bot_linux_monitor.certificates(interaction)

    @discord_bot.tree.command(name="reboot_server", description="[Private] 🔄 Restart the entire server 🔄")
    async def reboot(interaction: discord.Interaction) -> None: # type: ignore
        await discord_bot_linux_monitor.reboot(interaction)

    @discord_bot.tree.command(name="services_status", description="🩺 Check services are running 🩺")
    async def services_status(interaction: discord.Interaction) -> None: # type: ignore
        await discord_bot_linux_monitor.services_status(interaction)

    @discord_bot.tree.command(name="restart_all", description="🚀 Restart all services 🚀")
    async def restart_all(interaction: discord.Interaction) -> None: # type: ignore
        await discord_bot_linux_monitor.restart_all(interaction)

    @discord_bot.tree.command(name="restart_service", description="🚀 Restart a service 🚀")
    async def restart_service(interaction: discord.Interaction, service_name: str) -> None: # type: ignore
        await discord_bot_linux_monitor.restart_service(interaction, service_name)

    @discord_bot.tree.command(name="stop_service", description="🚫 Stop a service 🚫")
    async def stop_service(interaction: discord.Interaction, service_name: str) -> None: # type: ignore
        await discord_bot_linux_monitor.stop_service(interaction, service_name)

    @discord_bot.tree.command(name="list_services", description="📋 List all available services 📋")
    async def list_services(interaction: discord.Interaction) -> None: # type: ignore
        await discord_bot_linux_monitor.list_services(interaction)

    @discord_bot.tree.command(name="ports", description="🔒 Check ports 🔒")
    async def ports(interaction: discord.Interaction) -> None: # type: ignore
        await discord_bot_linux_monitor.ports(interaction)

    @discord_bot.tree.command(name="list_processes", description="[Private] 📋 List active processes 📋")
    async def list_processes(interaction: discord.Interaction) -> None: # type: ignore
        await discord_bot_linux_monitor.list_processes(interaction)

    @discord_bot.tree.command(name="kill_process", description="[Private] 🚫 Stop a process by PID 🚫")
    async def kill_process(interaction: discord.Interaction, pid: int) -> None: # type: ignore
        await discord_bot_linux_monitor.kill_process(interaction, pid)

    #endregion

    # Start the discord bot
    logging.info(msg="Starting the Discord bot...")
    try:
        discord_bot.run(token=discord_bot_linux_monitor.server_token)
    except Exception as e:
        logging.exception(msg=f"Error while running the bot: {e}")

if __name__ == "__main__":
    main()
