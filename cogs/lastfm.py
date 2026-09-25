from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from database.db import (
    get_all_lastfm_users,
    get_artist_crown,
    get_lastfm_user,
    get_user_crowns,
    set_artist_crown,
    set_lastfm_user,
)

from services.lastfm_api import (
    LastFMError,
    get_artist_playcount,
    get_recent_track,
    get_recent_tracks,
    get_top_albums,
    get_top_artists,
    get_top_tracks,
    get_user_info,
)


PERIODS = {
    "7day": "7 days",
    "1month": "1 month",
    "3month": "3 months",
    "6month": "6 months",
    "12month": "1 year",
    "overall": "All time",
}


PERIOD_CHOICES = [
    app_commands.Choice(
        name="7 days",
        value="7day",
    ),
    app_commands.Choice(
        name="1 month",
        value="1month",
    ),
    app_commands.Choice(
        name="3 months",
        value="3month",
    ),
    app_commands.Choice(
        name="6 months",
        value="6month",
    ),
    app_commands.Choice(
        name="1 year",
        value="12month",
    ),
    app_commands.Choice(
        name="All time",
        value="overall",
    ),
]


class LastFM(
    commands.GroupCog,
    group_name="fm",
):
    def __init__(
        self,
        bot: commands.Bot,
    ):
        self.bot = bot

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
                "❌ You haven't linked a Last.fm "
                "account yet. Use `/fm set` first.",
                ephemeral=True,
            )

            return None

        return username

    # /fm set

    @app_commands.command(
        name="set",
        description=(
            "Link your Discord account to Last.fm."
        ),
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
            user = await get_user_info(
                username
            )

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
            (
                "✅ Your Last.fm account is now "
                f"linked to **{username}**."
            ),
            ephemeral=True,
        )

    # /fm now

    @app_commands.command(
        name="now",
        description=(
            "Show what you or another Last.fm "
            "user is listening to."
        ),
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
            track = await get_recent_track(
                username
            )

            user = await get_user_info(
                username
            )

        except LastFMError as error:
            await interaction.followup.send(
                f"❌ Last.fm error: {error}",
                ephemeral=True,
            )
            return

        if track is None:
            await interaction.followup.send(
                (
                    "❌ No recent tracks found for "
                    f"`{username}`."
                )
            )
            return

        title = track["name"]

        artist = (
            track.get(
                "artist",
                {},
            ).get("name")
            or "Unknown artist"
        )

        album = (
            track.get(
                "album",
                {},
            ).get("#text")
            or "Unknown album"
        )

        now_playing = (
            track.get(
                "@attr",
                {},
            ).get("nowplaying")
            == "true"
        )

        images = track.get(
            "image",
            [],
        )

        artwork = (
            images[-1].get("#text")
            if images
            else None
        )

        scrobbles = int(
            user.get(
                "playcount",
                0,
            )
        )

        canonical_username = user.get(
            "name",
            username,
        )

        embed = discord.Embed(
            title=title,
            description=(
                f"**{artist}**\n{album}"
            ),
            url=track.get("url"),
        )

        embed.set_author(
            name=(
                f"{canonical_username} — "
                f"{'Now Playing' if now_playing else 'Last Played'}"
            )
        )

        embed.add_field(
            name="Total scrobbles",
            value=f"{scrobbles:,}",
            inline=True,
        )

        if artwork:
            embed.set_thumbnail(
                url=artwork
            )

        embed.set_footer(
            text=(
                "Kallie's Music Tracker • "
                "Last.fm"
            )
        )

        await interaction.followup.send(
            embed=embed
        )

    # /fm stats

    @app_commands.command(
        name="stats",
        description=(
            "Show a Last.fm user's profile "
            "statistics."
        ),
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
            user = await get_user_info(
                username
            )

            track = await get_recent_track(
                username
            )

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

        scrobbles = int(
            user.get(
                "playcount",
                0,
            )
        )

        artist_count = int(
            user.get(
                "artist_count",
                0,
            )
        )

        album_count = int(
            user.get(
                "album_count",
                0,
            )
        )

        track_count = int(
            user.get(
                "track_count",
                0,
            )
        )

        registered = user.get(
            "registered",
            {},
        )

        registered_timestamp = (
            registered.get("unixtime")
        )

        if registered_timestamp:
            registered_date = (
                datetime.fromtimestamp(
                    int(
                        registered_timestamp
                    ),
                    tz=timezone.utc,
                ).strftime(
                    "%d %B %Y"
                )
            )

        else:
            registered_date = "Unknown"

        embed = discord.Embed(
            title=(
                f"📊 {canonical_username}'s "
                "Last.fm"
            ),
            url=user.get("url"),
        )

        embed.add_field(
            name="Scrobbles",
            value=f"{scrobbles:,}",
            inline=True,
        )

        embed.add_field(
            name="Artists",
            value=f"{artist_count:,}",
            inline=True,
        )

        embed.add_field(
            name="Albums",
            value=f"{album_count:,}",
            inline=True,
        )

        embed.add_field(
            name="Tracks",
            value=f"{track_count:,}",
            inline=True,
        )

        embed.add_field(
            name="Registered",
            value=registered_date,
            inline=True,
        )

        if track:
            artist = (
                track.get(
                    "artist",
                    {},
                ).get("name")
                or "Unknown artist"
            )

            title = track.get(
                "name",
                "Unknown track",
            )

            now_playing = (
                track.get(
                    "@attr",
                    {},
                ).get("nowplaying")
                == "true"
            )

            status = (
                "🎧 Now Playing"
                if now_playing
                else "🎵 Last Played"
            )

            embed.add_field(
                name=status,
                value=(
                    f"**{artist}** — "
                    f"{title}"
                ),
                inline=False,
            )

        images = user.get(
            "image",
            [],
        )

        if images:
            profile_image = (
                images[-1].get("#text")
            )

            if profile_image:
                embed.set_thumbnail(
                    url=profile_image
                )

        embed.set_footer(
            text=(
                "Kallie's Music Tracker • "
                "Last.fm"
            )
        )

        await interaction.followup.send(
            embed=embed
        )

    # /fm recent

    @app_commands.command(
        name="recent",
        description=(
            "Show a Last.fm user's 10 most "
            "recent tracks."
        ),
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

            user = await get_user_info(
                username
            )

        except LastFMError as error:
            await interaction.followup.send(
                f"❌ Last.fm error: {error}",
                ephemeral=True,
            )
            return

        if not tracks:
            await interaction.followup.send(
                (
                    "❌ No recent tracks found for "
                    f"`{username}`."
                )
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
                track.get(
                    "artist",
                    {},
                ).get("name")
                or "Unknown artist"
            )

            title = track.get(
                "name",
                "Unknown track",
            )

            now_playing = (
                track.get(
                    "@attr",
                    {},
                ).get("nowplaying")
                == "true"
            )

            marker = (
                " 🎧"
                if now_playing
                else ""
            )

            lines.append(
                (
                    f"`{index:>2}.` "
                    f"**{artist}** — "
                    f"{title}{marker}"
                )
            )

        embed = discord.Embed(
            title=(
                f"🕒 {canonical_username}'s "
                "Recent Tracks"
            ),
            description="\n".join(
                lines
            ),
            url=user.get("url"),
        )

        images = tracks[0].get(
            "image",
            [],
        )

        if images:
            artwork = (
                images[-1].get("#text")
            )

            if artwork:
                embed.set_thumbnail(
                    url=artwork
                )

        embed.set_footer(
            text=(
                "🎧 = currently playing • "
                "Kallie's Music Tracker"
            )
        )

        await interaction.followup.send(
            embed=embed
        )

    # /fm topartists

    @app_commands.command(
        name="topartists",
        description=(
            "Show a Last.fm user's top artists."
        ),
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
        period: (
            app_commands.Choice[str]
            | None
        ) = None,
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

            user = await get_user_info(
                username
            )

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
            name = artist.get(
                "name",
                "Unknown artist",
            )

            plays = int(
                artist.get(
                    "playcount",
                    0,
                )
            )

            medal = {
                1: "🥇",
                2: "🥈",
                3: "🥉",
            }.get(
                index,
                f"`{index}.`",
            )

            lines.append(
                (
                    f"{medal} **{name}** — "
                    f"{plays:,} plays"
                )
            )

        embed = discord.Embed(
            title=(
                f"🎤 {canonical_username}'s "
                "Top Artists"
            ),
            description="\n".join(
                lines
            ),
            url=user.get("url"),
        )

        embed.set_footer(
            text=(
                f"{PERIODS[period_value]} • "
                "Kallie's Music Tracker"
            )
        )

        await interaction.followup.send(
            embed=embed
        )

    # /fm topalbums

    @app_commands.command(
        name="topalbums",
        description=(
            "Show a Last.fm user's top albums."
        ),
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
        period: (
            app_commands.Choice[str]
            | None
        ) = None,
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

            user = await get_user_info(
                username
            )

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
            name = album.get(
                "name",
                "Unknown album",
            )

            artist = (
                album.get(
                    "artist",
                    {},
                ).get("name")
                or "Unknown artist"
            )

            plays = int(
                album.get(
                    "playcount",
                    0,
                )
            )

            medal = {
                1: "🥇",
                2: "🥈",
                3: "🥉",
            }.get(
                index,
                f"`{index}.`",
            )

            lines.append(
                (
                    f"{medal} **{name}** — "
                    f"{artist} "
                    f"({plays:,} plays)"
                )
            )

        embed = discord.Embed(
            title=(
                f"💿 {canonical_username}'s "
                "Top Albums"
            ),
            description="\n".join(
                lines
            ),
            url=user.get("url"),
        )

        if albums:
            images = albums[0].get(
                "image",
                [],
            )

            if images:
                artwork = (
                    images[-1].get(
                        "#text"
                    )
                )

                if artwork:
                    embed.set_thumbnail(
                        url=artwork
                    )

        embed.set_footer(
            text=(
                f"{PERIODS[period_value]} • "
                "Kallie's Music Tracker"
            )
        )

        await interaction.followup.send(
            embed=embed
        )

    # /fm toptracks

    @app_commands.command(
        name="toptracks",
        description=(
            "Show a Last.fm user's top tracks."
        ),
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
        period: (
            app_commands.Choice[str]
            | None
        ) = None,
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

            user = await get_user_info(
                username
            )

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
            title = track.get(
                "name",
                "Unknown track",
            )

            artist = (
                track.get(
                    "artist",
                    {},
                ).get("name")
                or "Unknown artist"
            )

            plays = int(
                track.get(
                    "playcount",
                    0,
                )
            )

            medal = {
                1: "🥇",
                2: "🥈",
                3: "🥉",
            }.get(
                index,
                f"`{index}.`",
            )

            lines.append(
                (
                    f"{medal} **{title}** — "
                    f"{artist} "
                    f"({plays:,} plays)"
                )
            )

        embed = discord.Embed(
            title=(
                f"🎵 {canonical_username}'s "
                "Top Tracks"
            ),
            description="\n".join(
                lines
            ),
            url=user.get("url"),
        )

        embed.set_footer(
            text=(
                f"{PERIODS[period_value]} • "
                "Kallie's Music Tracker"
            )
        )

        await interaction.followup.send(
            embed=embed
        )

    # /fm whoknows

    @app_commands.command(
        name="whoknows",
        description=(
            "See who in the server listens "
            "to an artist the most."
        ),
    )
    @app_commands.describe(
        artist="Artist to check",
    )
    async def whoknows(
        self,
        interaction: discord.Interaction,
        artist: str,
    ):
        await interaction.response.defer()

        guild = interaction.guild

        if guild is None:
            await interaction.followup.send(
                (
                    "❌ WhoKnows can only be "
                    "used inside a server."
                ),
                ephemeral=True,
            )
            return

        linked_users = (
            await get_all_lastfm_users()
        )

        results = []
        canonical_artist = artist

        for (
            discord_id,
            lastfm_username,
        ) in linked_users:
            member = guild.get_member(
                discord_id
            )

            if member is None:
                continue

            try:
                (
                    artist_name,
                    playcount,
                ) = await get_artist_playcount(
                    artist,
                    lastfm_username,
                )

            except LastFMError:
                continue

            canonical_artist = artist_name

            results.append(
                {
                    "member": member,
                    "username": (
                        lastfm_username
                    ),
                    "plays": playcount,
                }
            )

        if not results:
            await interaction.followup.send(
                (
                    "❌ Nobody in this server "
                    "has a linked Last.fm "
                    "account that could be "
                    "checked."
                )
            )
            return

        results.sort(
            key=lambda result: (
                result["plays"]
            ),
            reverse=True,
        )

        listeners = [
            result
            for result in results
            if result["plays"] > 0
        ]

        if not listeners:
            await interaction.followup.send(
                (
                    "Nobody with a linked "
                    "Last.fm account has "
                    f"scrobbled "
                    f"**{canonical_artist}** "
                    "yet."
                )
            )
            return

        winner = listeners[0]

        artist_key = (
            canonical_artist
            .strip()
            .casefold()
        )

        previous_crown = (
            await get_artist_crown(
                guild.id,
                artist_key,
            )
        )

        crown_stolen = False
        previous_owner = None

        if previous_crown is not None:
            previous_owner_id = (
                previous_crown[
                    "discord_id"
                ]
            )

            if (
                previous_owner_id
                != winner["member"].id
            ):
                crown_stolen = True

                previous_owner = (
                    guild.get_member(
                        previous_owner_id
                    )
                )

        await set_artist_crown(
            guild_id=guild.id,
            artist_key=artist_key,
            artist_name=canonical_artist,
            discord_id=(
                winner["member"].id
            ),
            playcount=winner["plays"],
        )

        lines = []

        for index, result in enumerate(
            listeners[:10],
            start=1,
        ):
            member = result["member"]
            plays = result["plays"]

            if index == 1:
                rank = "🥇"

            elif index == 2:
                rank = "🥈"

            elif index == 3:
                rank = "🥉"

            else:
                rank = f"`{index}.`"

            crown = (
                " 👑"
                if index == 1
                else ""
            )

            lines.append(
                (
                    f"{rank} "
                    f"{member.mention} — "
                    f"**{plays:,}** plays"
                    f"{crown}"
                )
            )

        embed = discord.Embed(
            title=(
                f"👑 Who Knows "
                f"{canonical_artist}?"
            ),
            description="\n".join(
                lines
            ),
        )

        if crown_stolen:
            if previous_owner:
                steal_text = (
                    f"{winner['member'].mention} "
                    f"stole the "
                    f"**{canonical_artist}** "
                    "crown from "
                    f"{previous_owner.mention}!"
                )

            else:
                steal_text = (
                    f"{winner['member'].mention} "
                    f"claimed the "
                    f"**{canonical_artist}** "
                    "crown from its previous "
                    "owner!"
                )

            embed.add_field(
                name="🚨 CROWN STOLEN",
                value=steal_text,
                inline=False,
            )

        else:
            embed.add_field(
                name="Crown",
                value=(
                    f"{winner['member'].mention} "
                    f"owns the "
                    f"**{canonical_artist}** "
                    "crown with "
                    f"**{winner['plays']:,}** "
                    "plays."
                ),
                inline=False,
            )

        embed.set_footer(
            text=(
                f"{len(listeners)} listener"
                f"{'' if len(listeners) == 1 else 's'} "
                "ranked • "
                "Kallie's Music Tracker"
            )
        )

        await interaction.followup.send(
            embed=embed
        )

    # /fm crowns

    @app_commands.command(
        name="crowns",
        description=(
            "Show the artist crowns owned "
            "by a server member."
        ),
    )
    @app_commands.describe(
        member=(
            "Member to check. Defaults "
            "to yourself."
        ),
    )
    async def crowns(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
    ):
        await interaction.response.defer()

        guild = interaction.guild

        if guild is None:
            await interaction.followup.send(
                (
                    "❌ Crowns can only be "
                    "viewed inside a server."
                ),
                ephemeral=True,
            )
            return

        target = (
            member
            or interaction.user
        )

        crowns = await get_user_crowns(
            guild.id,
            target.id,
        )

        if not crowns:
            await interaction.followup.send(
                (
                    f"👑 {target.mention} "
                    "doesn't own any artist "
                    "crowns yet."
                )
            )
            return

        lines = []

        for index, (
            artist_name,
            playcount,
        ) in enumerate(
            crowns,
            start=1,
        ):
            lines.append(
                (
                    f"`{index}.` "
                    f"**{artist_name}** — "
                    f"{playcount:,} plays"
                )
            )

        embed = discord.Embed(
            title=(
                f"👑 {target.display_name}'s "
                "Crowns"
            ),
            description="\n".join(
                lines
            ),
        )

        embed.set_thumbnail(
            url=target.display_avatar.url
        )

        embed.set_footer(
            text=(
                f"{len(crowns)} crown"
                f"{'' if len(crowns) == 1 else 's'} • "
                "Kallie's Music Tracker"
            )
        )

        await interaction.followup.send(
            embed=embed
        )


async def setup(
    bot: commands.Bot,
):
    await bot.add_cog(
        LastFM(bot)
    )