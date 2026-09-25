import os
import time

import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

from database.db import initialize_database
from services.lastfm_api import close_session


load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing from .env")


# ============================================================
# BOT CONFIG
# ============================================================

intents = discord.Intents.all()

# Kallie's accounts
OWNER_IDS = {
    844108893697343569,
    1021330920663416832,
}


# ============================================================
# ROTATING STATUS
# ============================================================

STATUSES = [
    discord.Activity(
        type=discord.ActivityType.listening,
        name="Listening to your scrobbles",
    ),
    discord.Activity(
        type=discord.ActivityType.watching,
        name="Watching the crown wars",
    ),
    discord.Game(
        name="Powered by Dave Grohl",
    ),
    discord.Activity(
        type=discord.ActivityType.listening,
        name="Recovering from Okeefeboss's Nickelback poisoning",
    ),
    discord.Activity(
        type=discord.ActivityType.watching,
        name="Please do not set Dave on fire",
    ),
]


# ============================================================
# /SAY MODAL
# ============================================================

class SayModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Speak as Dave")

        self.message = discord.ui.TextInput(
            label="What should Dave say?",
            style=discord.TextStyle.paragraph,
            placeholder="Enter Dave's message...",
            required=True,
            max_length=2000,
        )

        self.add_item(self.message)

    async def on_submit(self, interaction: discord.Interaction):
        # Double-check ownership even though /say itself is protected.
        if interaction.user.id not in OWNER_IDS:
            await interaction.response.send_message(
                "❌ You are not authorised to possess the Dave microphone.",
                ephemeral=True,
            )
            return

        message = str(self.message.value)

        # ====================================================
        # SERVER
        # ====================================================
        #
        # In a guild, Dave is actually present in the channel,
        # so he can send a normal standalone bot message.
        #
        # This preserves the original /say behaviour:
        # it looks like Dave simply decided to speak.
        #
        if interaction.guild is not None:
            if interaction.channel is None:
                await interaction.response.send_message(
                    "❌ Dave couldn't determine where to speak.",
                    ephemeral=True,
                )
                return

            try:
                await interaction.channel.send(message)

            except discord.Forbidden:
                await interaction.response.send_message(
                    "❌ Dave doesn't have permission to speak here.",
                    ephemeral=True,
                )
                return

            except discord.HTTPException as exc:
                await interaction.response.send_message(
                    f"❌ Dave failed to speak: {exc}",
                    ephemeral=True,
                )
                return

            # Only Kallie sees this confirmation.
            await interaction.response.send_message(
                "🎤 Dave has spoken.",
                ephemeral=True,
            )
            return

        # ====================================================
        # DM / PRIVATE CHANNEL
        # ====================================================
        #
        # A user-installed app may receive the interaction here
        # without the bot account itself being able to perform
        # channel.send().
        #
        # Therefore Dave speaks through the interaction response.
        #
        try:
            await interaction.response.send_message(
                message,
                ephemeral=False,
            )

        except discord.HTTPException as exc:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"❌ Dave failed to speak: {exc}",
                    ephemeral=True,
                )


# ============================================================
# BOT
# ============================================================

class KalliesMusicTracker(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
        )

        self.status_index = 0

    async def setup_hook(self):
        await initialize_database()
        print("Database initialized.")

        await self.load_extension("cogs.lastfm")
        print("Last.fm cog loaded.")

        synced = await self.tree.sync()
        print(f"Synced {len(synced)} slash command(s).")

        if not self.rotate_status.is_running():
            self.rotate_status.start()

    async def close(self):
        if self.rotate_status.is_running():
            self.rotate_status.cancel()

        print("Closing Last.fm session...")
        await close_session()

        await super().close()

    @tasks.loop(seconds=30)
    async def rotate_status(self):
        activity = STATUSES[self.status_index]

        await self.change_presence(
            status=discord.Status.online,
            activity=activity,
        )

        self.status_index = (self.status_index + 1) % len(STATUSES)

    @rotate_status.before_loop
    async def before_rotate_status(self):
        await self.wait_until_ready()


bot = KalliesMusicTracker()


# ============================================================
# EVENTS
# ============================================================

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print(f"Bot ID: {bot.user.id}")
    print("Dave is online.")


# ============================================================
# /PING
# ============================================================

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
    description="Check Dave's latency.",
)
async def ping(interaction: discord.Interaction):
    start = time.perf_counter()

    await interaction.response.send_message(
        "🏓 Measuring Dave..."
    )

    end = time.perf_counter()

    interaction_latency = round((end - start) * 1000)
    gateway_latency = round(bot.latency * 1000)

    await interaction.edit_original_response(
        content=(
            "🏓 **Pong!**\n"
            f"Interaction: `{interaction_latency}ms`\n"
            f"Gateway: `{gateway_latency}ms`"
        )
    )


# ============================================================
# /SAY
# ============================================================

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
    name="say",
    description="Speak through KallieFM.",
)
async def say(interaction: discord.Interaction):
    if interaction.user.id not in OWNER_IDS:
        await interaction.response.send_message(
            "❌ You are not authorised to possess the Dave microphone.",
            ephemeral=True,
        )
        return

    await interaction.response.send_modal(
        SayModal()
    )


# ============================================================
# START BOT
# ============================================================

bot.run(TOKEN)