import time
from datetime import datetime, timezone

import discord
from discord import app_commands

from cache import CACHE_ENABLED, CACHE_REASON
from database.db import (
    begin_history_index,
    finish_history_index,
    get_cached_artist_scrobbles,
    get_cached_first_artist_scrobble,
    get_cached_scrobble_count,
    get_history_state,
    insert_cached_scrobbles,
    refresh_history_bounds,
    set_history_next_page,
)
from services.lastfm_api import (
    LastFMError,
    get_artist_playcount,
    get_recent_tracks_page,
    get_user_info,
)
from .shared import base_embed, finish_embed, get_image, number


TIMELINE_MILESTONES = (
    1,
    100,
    500,
    1_000,
    5_000,
    10_000,
    25_000,
    50_000,
    100_000,
)


def cached_discord_date(scrobble: dict) -> str:
    try:
        timestamp = int(scrobble["timestamp"])
    except (KeyError, TypeError, ValueError):
        return "Unknown"
    return f"<t:{timestamp}:D>"


def api_track_to_cache(track: dict) -> dict | None:
    """Reduce a Last.fm recent-track object to the fields we persist."""
    date = track.get("date")
    if not isinstance(date, dict):
        return None

    try:
        timestamp = int(date.get("uts"))
    except (TypeError, ValueError):
        return None

    artist_data = track.get("artist", {})
    if isinstance(artist_data, dict):
        artist = (
            artist_data.get("name")
            or artist_data.get("#text")
            or ""
        ).strip()
    else:
        artist = str(artist_data or "").strip()

    if not artist:
        return None

    album_data = track.get("album", {})
    if isinstance(album_data, dict):
        album = (album_data.get("#text") or "").strip()
    else:
        album = str(album_data or "").strip()

    return {
        "timestamp": timestamp,
        "artist": artist,
        "track": str(track.get("name") or "Unknown track"),
        "album": album,
        "image_url": get_image(track),
        "track_url": track.get("url"),
    }


def parse_total_pages(metadata: dict) -> int | None:
    """Return a valid Last.fm page count, or None if metadata is unusable."""
    if not isinstance(metadata, dict):
        return None

    value = metadata.get("totalPages")

    try:
        total_pages = int(value)
    except (TypeError, ValueError):
        return None

    if total_pages < 1:
        return None

    return total_pages


async def cache_page(username: str, tracks: list[dict]) -> int:
    rows = []

    for track in tracks:
        row = api_track_to_cache(track)
        if row is not None:
            rows.append(row)

    return await insert_cached_scrobbles(username, rows)


async def initial_history_index(
    username: str,
    status_message: discord.WebhookMessage,
) -> tuple[int, int]:
    """Build or resume a stable, full history index for one Last.fm account."""
    state = await get_history_state(username)

    if (
        state
        and not state["initial_sync_complete"]
        and state.get("frozen_to_timestamp")
    ):
        frozen_to = int(state["frozen_to_timestamp"])
        total_pages = int(state.get("total_pages") or 0)

        if total_pages <= 0:
            _, metadata = await get_recent_tracks_page(
                username,
                page=1,
                limit=200,
                to_timestamp=frozen_to,
            )

            total_pages = parse_total_pages(metadata)

            if total_pages is None:
                return (
                    0,
                    await get_cached_scrobble_count(username),
                )

            await begin_history_index(
                username,
                frozen_to,
                total_pages,
            )

            next_page = total_pages
        else:
            stored_next_page = state.get("next_page")

            if stored_next_page is None:
                next_page = total_pages
            else:
                next_page = int(stored_next_page)
    else:
        frozen_to = int(time.time())

        _, metadata = await get_recent_tracks_page(
            username,
            page=1,
            limit=200,
            to_timestamp=frozen_to,
        )

        total_pages = parse_total_pages(metadata)

        if total_pages is None:
            await begin_history_index(
                username,
                frozen_to,
                0,
            )

            return (
                0,
                await get_cached_scrobble_count(username),
            )

        next_page = total_pages

        await begin_history_index(
            username,
            frozen_to,
            total_pages,
        )

    inserted_total = 0
    pages_done = max(total_pages - next_page, 0)

    for page in range(next_page, 0, -1):
        tracks, _ = await get_recent_tracks_page(
            username,
            page=page,
            limit=200,
            to_timestamp=frozen_to,
        )

        if not isinstance(tracks, list):
            raise AttributeError(
                "Last.fm returned a malformed track list."
            )

        if not tracks:
            cached = await get_cached_scrobble_count(username)

            await status_message.edit(
                content=(
                    f"⚠️ Indexing `{username}` paused at page **{page}**.\n"
                    f"Last.fm advertised **{number(total_pages)}** pages, "
                    "but returned an empty page inside that range.\n"
                    "Progress is saved; run `/fm index` again to retry."
                )
            )

            return inserted_total, cached

        inserted_total += await cache_page(
            username,
            tracks,
        )

        await set_history_next_page(
            username,
            page - 1,
        )

        pages_done += 1

        if (
            pages_done == 1
            or pages_done % 25 == 0
            or page == 1
        ):
            percent = (pages_done / total_pages) * 100
            cached = await get_cached_scrobble_count(username)

            await status_message.edit(
                content=(
                    f"📚 Indexing `{username}`… **{percent:.1f}%**\n"
                    f"Pages: **{number(pages_done)}/{number(total_pages)}** • "
                    f"Cached: **{number(cached)}** scrobbles\n"
                    "You can leave this running; progress is saved after every page."
                )
            )

    await finish_history_index(username)

    cached = await get_cached_scrobble_count(username)

    return inserted_total, cached


async def incremental_history_sync(username: str) -> tuple[int, int]:
    """Fetch only scrobbles newer than the newest locally cached scrobble."""
    state = await get_history_state(username)

    if not state or not state["initial_sync_complete"]:
        return 0, await get_cached_scrobble_count(username)

    newest = state.get("newest_timestamp")

    from_timestamp = (
        int(newest) + 1
        if newest is not None
        else None
    )

    to_timestamp = int(time.time())

    tracks, metadata = await get_recent_tracks_page(
        username,
        page=1,
        limit=200,
        from_timestamp=from_timestamp,
        to_timestamp=to_timestamp,
    )

    total_pages = parse_total_pages(metadata)

    if total_pages is None:
        raise LastFMError(
            "Last.fm returned missing or malformed totalPages metadata."
        )

    if not isinstance(tracks, list):
        raise AttributeError(
            "Last.fm returned a malformed track list."
        )

    inserted = await cache_page(
        username,
        tracks,
    )

    for page in range(2, total_pages + 1):
        tracks, _ = await get_recent_tracks_page(
            username,
            page=page,
            limit=200,
            from_timestamp=from_timestamp,
            to_timestamp=to_timestamp,
        )

        if not isinstance(tracks, list):
            raise AttributeError(
                "Last.fm returned a malformed track list."
            )

        inserted += await cache_page(
            username,
            tracks,
        )

    await refresh_history_bounds(username)

    return inserted, await get_cached_scrobble_count(username)


async def require_indexed_history(
    interaction: discord.Interaction,
    username: str,
) -> bool:
    state = await get_history_state(username)

    if state and state["initial_sync_complete"]:
        return True

    await interaction.followup.send(
        f"📚 `{username}` hasn't been fully indexed yet. Run `/fm index` first."
    )

    return False


class HistoryCommands:
    @app_commands.command(
        name="index",
        description="Index your Last.fm history for instant archaeology commands.",
    )
    @app_commands.describe(
        username="Optional Last.fm username",
    )
    async def index(
        self,
        interaction: discord.Interaction,
        username: str | None = None,
    ):
        if not CACHE_ENABLED:
            await interaction.response.send_message(
                f"📚 History caching is temporarily disabled.\n{CACHE_REASON}",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        username = await self.require_username(
            interaction,
            username,
        )

        if username is None:
            return

        try:
            user = await get_user_info(username)
            canonical_username = user.get("name", username)
            state = await get_history_state(canonical_username)

            if state and state["initial_sync_complete"]:
                status = await interaction.followup.send(
                    f"🔄 Syncing new scrobbles for `{canonical_username}`…",
                    wait=True,
                )

                inserted, cached = await incremental_history_sync(
                    canonical_username,
                )

                state = await get_history_state(canonical_username)

                await status.edit(
                    content=(
                        f"✅ **History synced for `{canonical_username}`**\n"
                        f"New scrobbles: **{number(inserted)}** • "
                        f"Total cached: **{number(cached)}**\n"
                        f"Newest cached: <t:{int(state['newest_timestamp'])}:F>"
                        if state and state.get("newest_timestamp")
                        else
                        f"✅ History synced for `{canonical_username}`."
                    )
                )

                return

            resumed = bool(
                state
                and state.get("frozen_to_timestamp")
            )

            status = await interaction.followup.send(
                (
                    f"📚 {'Resuming' if resumed else 'Starting'} history index for "
                    f"`{canonical_username}`…\n"
                    "Large libraries can take several minutes. "
                    "Progress is saved after every page."
                ),
                wait=True,
            )

            inserted, cached = await initial_history_index(
                canonical_username,
                status,
            )

            state = await get_history_state(canonical_username)

            if not state or not state["initial_sync_complete"]:
                await status.edit(
                    content=(
                        f"⚠️ **History index for `{canonical_username}` "
                        "is not complete.**\n"
                        f"Cached so far: **{number(cached)}** scrobbles.\n"
                        "Progress has been saved. Run `/fm index` again to retry."
                    )
                )

                return

            if (
                state.get("oldest_timestamp")
                and state.get("newest_timestamp")
            ):
                await status.edit(
                    content=(
                        f"✅ **History indexed for `{canonical_username}`**\n"
                        f"Cached: **{number(cached)}** scrobbles "
                        f"(**{number(inserted)}** added this run)\n"
                        f"Oldest: <t:{int(state['oldest_timestamp'])}:D> • "
                        f"Newest: <t:{int(state['newest_timestamp'])}:F>\n"
                        "`/fm timeline` and `/fm firstscrobble` now use the local cache."
                    )
                )
            else:
                await status.edit(
                    content=(
                        f"✅ History indexed for `{canonical_username}` — "
                        f"**{number(cached)}** scrobbles cached."
                    )
                )

        except LastFMError as error:
            await interaction.followup.send(
                f"❌ Last.fm error: {error}",
                ephemeral=True,
            )

    @app_commands.command(
        name="firstscrobble",
        description="Find your first scrobble of an artist.",
    )
    @app_commands.describe(
        artist="Artist to search for",
        username="Optional Last.fm username",
    )
    async def firstscrobble(
        self,
        interaction: discord.Interaction,
        artist: str,
        username: str | None = None,
    ):
        if not CACHE_ENABLED:
            await interaction.response.send_message(
                f"📚 History caching is temporarily disabled.\n{CACHE_REASON}",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        username = await self.require_username(
            interaction,
            username,
        )

        if username is None:
            return

        try:
            user = await get_user_info(username)
            canonical_username = user.get("name", username)

            if not await require_indexed_history(
                interaction,
                canonical_username,
            ):
                return

            canonical_artist, artist_plays = await get_artist_playcount(
                artist,
                canonical_username,
            )

            if artist_plays <= 0:
                await interaction.followup.send(
                    f"❌ `{canonical_username}` has no scrobbles for "
                    f"**{canonical_artist}**."
                )
                return

            track = await get_cached_first_artist_scrobble(
                canonical_username,
                canonical_artist,
            )

        except LastFMError as error:
            await interaction.followup.send(
                f"❌ Last.fm error: {error}",
                ephemeral=True,
            )
            return

        if track is None:
            await interaction.followup.send(
                f"❌ Couldn't find **{canonical_artist}** in the local history cache. "
                "Try `/fm index` to sync new scrobbles."
            )
            return

        timestamp = int(track["timestamp"])
        album = track.get("album") or "Unknown album"

        embed = base_embed(
            title=f"📜 First {canonical_artist} Scrobble",
            description=(
                f"### {track.get('track') or 'Unknown track'}\n"
                f"**{canonical_artist}**\n"
                f"*{album}*"
            ),
            url=track.get("track_url"),
        )

        embed.set_author(
            name=canonical_username,
            icon_url=interaction.user.display_avatar.url,
        )

        embed.add_field(
            name="First scrobbled",
            value=f"<t:{timestamp}:F>\n<t:{timestamp}:R>",
            inline=False,
        )

        embed.add_field(
            name="Current artist plays",
            value=f"**{number(artist_plays)}**",
            inline=True,
        )

        if track.get("image_url"):
            embed.set_thumbnail(
                url=track["image_url"],
            )

        finish_embed(
            embed,
            "Listening archaeology • cached",
        )

        await interaction.followup.send(
            embed=embed,
        )

    @app_commands.command(
        name="timeline",
        description="Show major milestones in your history with an artist.",
    )
    @app_commands.describe(
        artist="Artist to build a listening timeline for",
        username="Optional Last.fm username",
    )
    async def timeline(
        self,
        interaction: discord.Interaction,
        artist: str,
        username: str | None = None,
    ):
        if not CACHE_ENABLED:
            await interaction.response.send_message(
                f"📚 History caching is temporarily disabled.\n{CACHE_REASON}",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        username = await self.require_username(
            interaction,
            username,
        )

        if username is None:
            return

        try:
            user = await get_user_info(username)
            canonical_username = user.get("name", username)

            if not await require_indexed_history(
                interaction,
                canonical_username,
            ):
                return

            canonical_artist, artist_plays = await get_artist_playcount(
                artist,
                canonical_username,
            )

            if artist_plays <= 0:
                await interaction.followup.send(
                    f"❌ `{canonical_username}` has no scrobbles for "
                    f"**{canonical_artist}**."
                )
                return

            scrobbles = await get_cached_artist_scrobbles(
                canonical_username,
                canonical_artist,
            )

        except LastFMError as error:
            await interaction.followup.send(
                f"❌ Last.fm error: {error}",
                ephemeral=True,
            )
            return

        if not scrobbles:
            await interaction.followup.send(
                f"❌ Couldn't find **{canonical_artist}** in the local history cache. "
                "Try `/fm index` to sync new scrobbles."
            )
            return

        lines = []

        for milestone in TIMELINE_MILESTONES:
            if milestone > len(scrobbles):
                continue

            scrobble = scrobbles[milestone - 1]

            label = (
                "First"
                if milestone == 1
                else number(milestone)
            )

            lines.append(
                f"**{label}** — {cached_discord_date(scrobble)}"
            )

        embed = base_embed(
            title=f"📈 {canonical_artist} — Listening Timeline",
            description="\n".join(lines),
            url=user.get("url"),
        )

        embed.set_author(
            name=canonical_username,
            icon_url=interaction.user.display_avatar.url,
        )

        embed.add_field(
            name="Current plays",
            value=f"**{number(artist_plays)}**",
            inline=True,
        )

        embed.add_field(
            name="Cached plays",
            value=f"**{number(len(scrobbles))}**",
            inline=True,
        )

        first = scrobbles[0]

        if first.get("image_url"):
            embed.set_thumbnail(
                url=first["image_url"],
            )

        finish_embed(
            embed,
            "Listening archaeology • cached",
        )

        await interaction.followup.send(
            embed=embed,
        )