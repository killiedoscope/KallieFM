import discord
from discord import app_commands

from datetime import datetime, timezone
from database.db import set_lastfm_user
from services.lastfm_api import LastFMError, get_user_info, get_recent_track
from .shared import base_embed, finish_embed, get_image, number


class AccountCommands:
    @app_commands.command(
        name="set",
        description="Link your Discord account to Last.fm.",
    )
    @app_commands.describe(
        username="Your Last.fm username",
    )
    async def set_user(
        self,
        interaction: discord.Interaction,
        username: str,
    ):
        await interaction.response.defer(
            ephemeral=True
        )

        try:
            user = await get_user_info(username)

        except LastFMError as error:
            await interaction.followup.send(
                f"❌ Last.fm error: {error}",
                ephemeral=True,
            )
            return

        username = user["name"]

        await set_lastfm_user(
            interaction.user.id,
            username,
        )

        await interaction.followup.send(
            f"✅ Linked your Discord account to **{username}**.",
            ephemeral=True,
        )


    @app_commands.command(
        name="stats",
        description="Show a Last.fm user's profile statistics.",
    )
    @app_commands.describe(
        username="Optional Last.fm username",
    )
    async def stats(
        self,
        interaction: discord.Interaction,
        username: str | None = None,
    ):
        await interaction.response.defer()

        username = await self.require_username(
            interaction,
            username,
        )

        if username is None:
            return

        try:
            user = await get_user_info(username)
            track = await get_recent_track(username)

        except LastFMError as error:
            await interaction.followup.send(
                f"❌ Last.fm error: {error}",
                ephemeral=True,
            )
            return

        canonical_username = user.get(
            "name",
            username,
        )

        embed = base_embed(
            title=f"📊 {canonical_username}'s Last.fm",
            url=user.get("url"),
        )

        embed.set_author(
            name="LISTENING PROFILE",
            icon_url=interaction.user.display_avatar.url,
        )

        embed.add_field(
            name="🎵 Scrobbles",
            value=f"**{number(user.get('playcount'))}**",
            inline=True,
        )

        embed.add_field(
            name="🎤 Artists",
            value=f"**{number(user.get('artist_count'))}**",
            inline=True,
        )

        embed.add_field(
            name="💿 Albums",
            value=f"**{number(user.get('album_count'))}**",
            inline=True,
        )

        embed.add_field(
            name="🎶 Tracks",
            value=f"**{number(user.get('track_count'))}**",
            inline=True,
        )

        registered = user.get(
            "registered",
            {},
        ).get("unixtime")

        if registered:
            registered_date = datetime.fromtimestamp(
                int(registered),
                tz=timezone.utc,
            ).strftime("%d %b %Y")
        else:
            registered_date = "Unknown"

        embed.add_field(
            name="📅 Scrobbling since",
            value=f"**{registered_date}**",
            inline=True,
        )

        if track:
            artist = (
                track.get("artist", {}).get("name")
                or "Unknown artist"
            )

            title = track.get(
                "name",
                "Unknown track",
            )

            playing = (
                track.get("@attr", {}).get("nowplaying")
                == "true"
            )

            embed.add_field(
                name=(
                    "🎧 Now Playing"
                    if playing
                    else "🎵 Last Played"
                ),
                value=f"**{artist}**\n{title}",
                inline=False,
            )

        profile_image = get_image(user)

        if profile_image:
            embed.set_thumbnail(
                url=profile_image
            )

        finish_embed(
            embed,
            "Profile statistics",
        )

        await interaction.followup.send(
            embed=embed
        )


