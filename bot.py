import os

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from database.db import initialize_database


load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing from .env")


intents = discord.Intents.all()


class KalliesMusicTracker(commands.Bot):
    async def setup_hook(self):
        await initialize_database()
        print("Database initialized.")

        await self.load_extension("cogs.lastfm")
        print("Last.fm cog loaded.")

        synced = await self.tree.sync()
        print(f"Synced {len(synced)} slash command(s).")


bot = KalliesMusicTracker(
    command_prefix="!",
    intents=intents,
)


@bot.event
async def on_ready():
    print("=" * 45)
    print("KALLIE'S MUSIC TRACKER IS ONLINE")
    print(f"Logged in as: {bot.user}")
    print(f"Bot ID: {bot.user.id}")
    print(f"Ping: {round(bot.latency * 1000)}ms")
    print("=" * 45)


@app_commands.allowed_installs(
    guilds=True,
    users=True,
)
@app_commands.allowed_contexts(
    guilds=True,
    dms=True,
    private_channels=True,
)
@bot.tree.command(
    name="ping",
    description="Check whether Kallie's Music Tracker is alive.",
)
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)

    await interaction.response.send_message(
        f"🏓 Kallie's Music Tracker is alive. `{latency}ms`"
    )


bot.run(TOKEN)