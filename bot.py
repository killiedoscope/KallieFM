import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

from database.db import initialize_database


# Load secrets/config from .env
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing from .env")


# Discord intents
intents = discord.Intents.all()


class KalliesMusicTracker(commands.Bot):
    async def setup_hook(self):
        # Create/load our SQLite database
        await initialize_database()
        print("Database initialized.")

        # Load command modules
        await self.load_extension("cogs.lastfm")
        print("Last.fm cog loaded.")

        # Register slash commands with Discord
        synced = await self.tree.sync()
        print(f"Synced {len(synced)} slash command(s).")


bot = KalliesMusicTracker(
    command_prefix="!",
    intents=intents,
)


@bot.event
async def on_ready():
    print("=" * 45)
    print(f"KALLIE'S MUSIC TRACKER IS ONLINE")
    print(f"Logged in as: {bot.user}")
    print(f"Bot ID: {bot.user.id}")
    print(f"Ping: {round(bot.latency * 1000)}ms")
    print("=" * 45)


@bot.tree.command(
    name="ping",
    description="Check whether Kallie's Music Tracker is alive."
)
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)

    await interaction.response.send_message(
        f"🏓 Kallie's Music Tracker is alive. `{latency}ms`"
    )


bot.run(TOKEN)