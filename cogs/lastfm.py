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


# --------------------------------------------------
# Visual configuration
# --------------------------------------------------

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


@app_commands.allowed_installs(
    guilds=True,
    users=True,
)
@app_commands.allowed_contexts(
    guilds=True,
    dms=True,
    private_channels=True,
)
class LastFM(commands.GroupCog, group_name="fm"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # --------------------------------------------------
    # Shared account helpers
    # --------------------------------------------------

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

    # ==================================================
    # /fm set
    # ==================================================

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

    # ==================================================
    # /fm now
    # ==================================================

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

    # ==================================================
    # /fm stats
    # ==================================================

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

    # ==================================================
    # /fm recent
    # ==================================================

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

    # ==================================================
    # /fm topartists
    # ==================================================

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

    # ==================================================
    # /fm topalbums
    # ==================================================

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

    # ==================================================
    # /fm toptracks
    # ==================================================

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

    # ==================================================
    # /fm whoknows
    # ==================================================

    @app_commands.command(
        name="whoknows",
        description="See who in the server listens to an artist the most.",
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
                "❌ WhoKnows can only be used inside a server.",
                ephemeral=True,
            )
            return

        linked_users = await get_all_lastfm_users()

        results = []
        canonical_artist = artist

        for discord_id, lastfm_username in linked_users:
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
                    "username": lastfm_username,
                    "plays": playcount,
                }
            )

        results.sort(
            key=lambda item: item["plays"],
            reverse=True,
        )

        listeners = [
            item
            for item in results
            if item["plays"] > 0
        ]

        if not listeners:
            await interaction.followup.send(
                f"Nobody here has scrobbled **{canonical_artist}** yet."
            )
            return

        winner = listeners[0]

        artist_key = (
            canonical_artist
            .strip()
            .casefold()
        )

        previous_crown = await get_artist_crown(
            guild.id,
            artist_key,
        )

        crown_stolen = (
            previous_crown is not None
            and previous_crown["discord_id"]
            != winner["member"].id
        )

        previous_owner = None

        if crown_stolen:
            previous_owner = guild.get_member(
                previous_crown["discord_id"]
            )

        await set_artist_crown(
            guild_id=guild.id,
            artist_key=artist_key,
            artist_name=canonical_artist,
            discord_id=winner["member"].id,
            playcount=winner["plays"],
        )

        lines = []

        combined_plays = sum(
            item["plays"]
            for item in listeners
        )

        for index, item in enumerate(
            listeners[:10],
            start=1,
        ):
            crown = (
                " 👑"
                if index == 1
                else ""
            )

            lines.append(
                f"{medal(index)} "
                f"**{item['member'].display_name}**{crown}\n"
                f"　{number(item['plays'])} plays"
            )

        embed = base_embed(
            title=f"👑 Who Knows — {canonical_artist}",
            description="\n".join(lines),
        )

        embed.set_thumbnail(
            url=winner["member"].display_avatar.url
        )

        if crown_stolen:
            if previous_owner:
                old_owner = previous_owner.mention
            else:
                old_owner = "the previous owner"

            embed.add_field(
                name="🚨 CROWN STOLEN",
                value=(
                    f"{winner['member'].mention} stole the "
                    f"**{canonical_artist}** crown from "
                    f"{old_owner}!"
                ),
                inline=False,
            )

        else:
            embed.add_field(
                name="👑 Crown holder",
                value=winner["member"].mention,
                inline=True,
            )

            embed.add_field(
                name="Crown score",
                value=f"**{number(winner['plays'])}** plays",
                inline=True,
            )

        finish_embed(
            embed,
            (
                f"{len(listeners)} listeners • "
                f"{number(combined_plays)} combined plays"
            ),
        )

        await interaction.followup.send(
            embed=embed
        )

    # ==================================================
    # /fm crowns
    # ==================================================

    @app_commands.command(
        name="crowns",
        description="Show the artist crowns owned by a server member.",
    )
    @app_commands.describe(
        member="Member to check. Defaults to yourself.",
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
                "❌ Crowns can only be viewed inside a server.",
                ephemeral=True,
            )
            return

        target = member or interaction.user

        crowns = await get_user_crowns(
            guild.id,
            target.id,
        )

        if not crowns:
            await interaction.followup.send(
                f"👑 {target.mention} doesn't own any artist crowns yet."
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
                f"**{index}. {artist_name}**\n"
                f"　👑 {number(playcount)} plays"
            )

        embed = base_embed(
            title=f"👑 {target.display_name}'s Crown Cabinet",
            description="\n".join(lines),
        )

        embed.set_author(
            name="ARTIST CROWNS",
            icon_url=target.display_avatar.url,
        )

        embed.set_thumbnail(
            url=target.display_avatar.url
        )

        finish_embed(
            embed,
            (
                f"{len(crowns)} crown"
                f"{'' if len(crowns) == 1 else 's'}"
            ),
        )

        await interaction.followup.send(
            embed=embed
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(
        LastFM(bot)
    )