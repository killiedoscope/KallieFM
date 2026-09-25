import discord
from discord import app_commands

from services.lastfm_api import LastFMError, get_recent_track, get_recent_tracks, get_user_info, get_artist_playcount
from .shared import base_embed, finish_embed, get_image, number


class ListeningCommands:
    @app_commands.command(
        name="now",
        description="Show what you or another Last.fm user is listening to.",
    )
    @app_commands.describe(
        username="Optional Last.fm username",
    )
    async def now(
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
            track = await get_recent_track(username)
            user = await get_user_info(username)

        except LastFMError as error:
            await interaction.followup.send(
                f"❌ Last.fm error: {error}",
                ephemeral=True,
            )
            return

        if track is None:
            await interaction.followup.send(
                f"❌ No recent tracks found for `{username}`."
            )
            return

        title = track.get(
            "name",
            "Unknown track",
        )

        artist = (
            track.get("artist", {}).get("name")
            or "Unknown artist"
        )

        album = (
            track.get("album", {}).get("#text")
            or "Unknown album"
        )

        now_playing = (
            track.get("@attr", {}).get("nowplaying")
            == "true"
        )

        canonical_username = user.get(
            "name",
            username,
        )

        artist_plays = None

        try:
            _, artist_plays = await get_artist_playcount(
                artist,
                canonical_username,
            )

        except LastFMError:
            pass

        status = (
            "🎧 NOW PLAYING"
            if now_playing
            else "🎵 LAST PLAYED"
        )

        embed = base_embed(
            title=title,
            description=(
                f"### {artist}\n"
                f"*{album}*"
            ),
            url=track.get("url"),
        )

        embed.set_author(
            name=f"{status}  •  {canonical_username}",
            icon_url=interaction.user.display_avatar.url,
        )

        if artist_plays is not None:
            embed.add_field(
                name="Artist plays",
                value=f"**{number(artist_plays)}**",
                inline=True,
            )

        embed.add_field(
            name="Total scrobbles",
            value=f"**{number(user.get('playcount'))}**",
            inline=True,
        )

        artwork = get_image(track)

        if artwork:
            embed.set_thumbnail(url=artwork)

        finish_embed(
            embed,
            "Last.fm",
        )

        await interaction.followup.send(
            embed=embed
        )


    @app_commands.command(
        name="recent",
        description="Show a Last.fm user's 10 most recent tracks.",
    )
    @app_commands.describe(
        username="Optional Last.fm username",
    )
    async def recent(
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
            tracks = await get_recent_tracks(
                username,
                limit=10,
            )

            user = await get_user_info(username)

        except LastFMError as error:
            await interaction.followup.send(
                f"❌ Last.fm error: {error}",
                ephemeral=True,
            )
            return

        if not tracks:
            await interaction.followup.send(
                f"❌ No recent tracks found for `{username}`."
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

            title = track.get(
                "name",
                "Unknown track",
            )

            playing = (
                track.get("@attr", {}).get("nowplaying")
                == "true"
            )

            marker = " `NOW`" if playing else ""

            lines.append(
                f"**{index}. {artist}** — {title}{marker}"
            )

        embed = base_embed(
            title=f"🕒 {canonical_username}'s Recent Tracks",
            description="\n".join(lines),
            url=user.get("url"),
        )

        artwork = get_image(
            tracks[0]
        )

        if artwork:
            embed.set_thumbnail(
                url=artwork
            )

        finish_embed(
            embed,
            "10 most recent scrobbles",
        )

        await interaction.followup.send(
            embed=embed
        )


