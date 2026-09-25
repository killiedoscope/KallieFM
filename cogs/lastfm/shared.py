from datetime import datetime, timezone

import discord
from discord import app_commands
from database.db import get_lastfm_user


LASTFM_RED = discord.Colour.from_rgb(213, 16, 7)

PERIODS = {
    "7day": "7 days",
    "1month": "1 month",
    "3month": "3 months",
    "6month": "6 months",
    "12month": "1 year",
    "overall": "All time",
}

PERIOD_CHOICES = [
    app_commands.Choice(name="7 days", value="7day"),
    app_commands.Choice(name="1 month", value="1month"),
    app_commands.Choice(name="3 months", value="3month"),
    app_commands.Choice(name="6 months", value="6month"),
    app_commands.Choice(name="1 year", value="12month"),
    app_commands.Choice(name="All time", value="overall"),
]


def number(value) -> str:
    """Format numbers like 51036 -> 51,036."""
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "0"


def get_image(data: dict) -> str | None:
    """Get the largest Last.fm image from an API object."""
    images = data.get("image", [])

    for image in reversed(images):
        url = image.get("#text")

        if url:
            return url

    return None


def base_embed(
    *,
    title: str,
    description: str | None = None,
    url: str | None = None,
) -> discord.Embed:
    """Create a consistent Kallie's Music Tracker embed."""
    return discord.Embed(
        title=title,
        description=description,
        url=url,
        colour=LASTFM_RED,
        timestamp=datetime.now(timezone.utc),
    )


def finish_embed(
    embed: discord.Embed,
    text: str | None = None,
):
    footer = "Kallie's Music Tracker"

    if text:
        footer = f"{text} • {footer}"

    embed.set_footer(text=footer)

    return embed


def medal(index: int) -> str:
    return {
        1: "🥇",
        2: "🥈",
        3: "🥉",
    }.get(index, f"`{index}.`")


class AccountHelpers:
    async def resolve_username(
        self,
        interaction: discord.Interaction,
        username: str | None,
    ):
        if username:
            return username

        return await get_lastfm_user(
            interaction.user.id
        )


    async def require_username(
        self,
        interaction: discord.Interaction,
        username: str | None,
    ):
        username = await self.resolve_username(
            interaction,
            username,
        )

        if username is None:
            await interaction.followup.send(
                "❌ You haven't linked a Last.fm account yet. "
                "Use `/fm set` first.",
                ephemeral=True,
            )

            return None

        return username


