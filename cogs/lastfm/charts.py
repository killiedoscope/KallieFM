import discord
from discord import app_commands

from services.lastfm_api import LastFMError, get_top_artists, get_top_albums, get_top_tracks, get_user_info
from .shared import PERIODS, PERIOD_CHOICES, base_embed, finish_embed, get_image, medal, number


class ChartCommands:
    @app_commands.command(
        name="topartists",
        description="Show a Last.fm user's top artists.",
    )
    @app_commands.describe(
        period="Time period",
        username="Optional Last.fm username",
    )
    @app_commands.choices(
        period=PERIOD_CHOICES
    )
    async def topartists(
        self,
        interaction: discord.Interaction,
        period: app_commands.Choice[str] | None = None,
        username: str | None = None,
    ):
        await interaction.response.defer()

        username = await self.require_username(
            interaction,
            username,
        )

        if username is None:
            return

        period_value = (
            period.value
            if period
            else "overall"
        )

        try:
            artists = await get_top_artists(
                username,
                period=period_value,
                limit=10,
            )

            user = await get_user_info(username)

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

        lines = []

        for index, artist in enumerate(
            artists,
            start=1,
        ):
            lines.append(
                f"{medal(index)} "
                f"**{artist.get('name', 'Unknown artist')}**\n"
                f"　{number(artist.get('playcount'))} plays"
            )

        embed = base_embed(
            title=f"🎤 {canonical_username}'s Top Artists",
            description="\n".join(lines),
            url=user.get("url"),
        )

        finish_embed(
            embed,
            PERIODS[period_value],
        )

        await interaction.followup.send(
            embed=embed
        )


    @app_commands.command(
        name="topalbums",
        description="Show a Last.fm user's top albums.",
    )
    @app_commands.describe(
        period="Time period",
        username="Optional Last.fm username",
    )
    @app_commands.choices(
        period=PERIOD_CHOICES
    )
    async def topalbums(
        self,
        interaction: discord.Interaction,
        period: app_commands.Choice[str] | None = None,
        username: str | None = None,
    ):
        await interaction.response.defer()

        username = await self.require_username(
            interaction,
            username,
        )

        if username is None:
            return

        period_value = (
            period.value
            if period
            else "overall"
        )

        try:
            albums = await get_top_albums(
                username,
                period=period_value,
                limit=10,
            )

            user = await get_user_info(username)

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

        lines = []

        for index, album in enumerate(
            albums,
            start=1,
        ):
            artist = (
                album.get("artist", {}).get("name")
                or "Unknown artist"
            )

            lines.append(
                f"{medal(index)} "
                f"**{album.get('name', 'Unknown album')}**\n"
                f"　{artist} • "
                f"{number(album.get('playcount'))} plays"
            )

        embed = base_embed(
            title=f"💿 {canonical_username}'s Top Albums",
            description="\n".join(lines),
            url=user.get("url"),
        )

        if albums:
            artwork = get_image(
                albums[0]
            )

            if artwork:
                embed.set_thumbnail(
                    url=artwork
                )

        finish_embed(
            embed,
            PERIODS[period_value],
        )

        await interaction.followup.send(
            embed=embed
        )


    @app_commands.command(
        name="toptracks",
        description="Show a Last.fm user's top tracks.",
    )
    @app_commands.describe(
        period="Time period",
        username="Optional Last.fm username",
    )
    @app_commands.choices(
        period=PERIOD_CHOICES
    )
    async def toptracks(
        self,
        interaction: discord.Interaction,
        period: app_commands.Choice[str] | None = None,
        username: str | None = None,
    ):
        await interaction.response.defer()

        username = await self.require_username(
            interaction,
            username,
        )

        if username is None:
            return

        period_value = (
            period.value
            if period
            else "overall"
        )

        try:
            tracks = await get_top_tracks(
                username,
                period=period_value,
                limit=10,
            )

            user = await get_user_info(username)

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

        lines = []

        for index, track in enumerate(
            tracks,
            start=1,
        ):
            artist = (
                track.get("artist", {}).get("name")
                or "Unknown artist"
            )

            lines.append(
                f"{medal(index)} "
                f"**{track.get('name', 'Unknown track')}**\n"
                f"　{artist} • "
                f"{number(track.get('playcount'))} plays"
            )

        embed = base_embed(
            title=f"🎵 {canonical_username}'s Top Tracks",
            description="\n".join(lines),
            url=user.get("url"),
        )

        finish_embed(
            embed,
            PERIODS[period_value],
        )

        await interaction.followup.send(
            embed=embed
        )


