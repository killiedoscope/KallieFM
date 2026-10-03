from pathlib import Path

import aiosqlite
import cache


DB_PATH = Path("data/bot.db")


async def initialize_database():
    DB_PATH.parent.mkdir(exist_ok=True)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS lastfm_users (
                discord_id INTEGER PRIMARY KEY,
                lastfm_username TEXT NOT NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS artist_crowns (
                guild_id INTEGER NOT NULL,
                artist_key TEXT NOT NULL,
                artist_name TEXT NOT NULL,
                discord_id INTEGER NOT NULL,
                playcount INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, artist_key)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS artist_milestones (
                discord_id INTEGER NOT NULL,
                lastfm_username TEXT NOT NULL,
                artist_key TEXT NOT NULL,
                artist_name TEXT NOT NULL,
                goal INTEGER NOT NULL CHECK (goal > 0),
                PRIMARY KEY (discord_id, lastfm_username, artist_key)
            )
        """)

        await db.commit()

    await initialize_lastfm_history_cache()


async def set_lastfm_user(
    discord_id: int,
    username: str,
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO lastfm_users (
                discord_id,
                lastfm_username
            )
            VALUES (?, ?)
            ON CONFLICT(discord_id)
            DO UPDATE SET
                lastfm_username = excluded.lastfm_username
        """, (
            discord_id,
            username,
        ))
        await db.commit()


async def get_lastfm_user(
    discord_id: int,
):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT lastfm_username
            FROM lastfm_users
            WHERE discord_id = ?
        """, (
            discord_id,
        ))
        row = await cursor.fetchone()

    return row[0] if row else None


async def get_all_lastfm_users():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT
                discord_id,
                lastfm_username
            FROM lastfm_users
        """)
        rows = await cursor.fetchall()

    return rows


async def get_artist_crown(
    guild_id: int,
    artist_key: str,
):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT
                artist_name,
                discord_id,
                playcount
            FROM artist_crowns
            WHERE guild_id = ?
            AND artist_key = ?
        """, (
            guild_id,
            artist_key,
        ))
        row = await cursor.fetchone()

    if row is None:
        return None

    return {
        "artist_name": row[0],
        "discord_id": row[1],
        "playcount": row[2],
    }


async def set_artist_crown(
    guild_id: int,
    artist_key: str,
    artist_name: str,
    discord_id: int,
    playcount: int,
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO artist_crowns (
                guild_id,
                artist_key,
                artist_name,
                discord_id,
                playcount
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(guild_id, artist_key)
            DO UPDATE SET
                artist_name = excluded.artist_name,
                discord_id = excluded.discord_id,
                playcount = excluded.playcount
        """, (
            guild_id,
            artist_key,
            artist_name,
            discord_id,
            playcount,
        ))
        await db.commit()


async def get_user_crowns(
    guild_id: int,
    discord_id: int,
):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT
                artist_name,
                playcount
            FROM artist_crowns
            WHERE guild_id = ?
            AND discord_id = ?
            ORDER BY artist_name COLLATE NOCASE
        """, (
            guild_id,
            discord_id,
        ))
        rows = await cursor.fetchall()

    return rows


async def set_artist_milestone(
    discord_id: int,
    username: str,
    artist: str,
    goal: int,
):
    """One goal per artist/account; relinking never applies goals to another account."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO artist_milestones
                (discord_id, lastfm_username, artist_key, artist_name, goal)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(discord_id, lastfm_username, artist_key)
            DO UPDATE SET
                artist_name = excluded.artist_name,
                goal = excluded.goal
        """, (
            discord_id,
            username.strip().casefold(),
            artist.strip().casefold(),
            artist,
            goal,
        ))
        await db.commit()


async def get_artist_milestones(
    discord_id: int,
    username: str,
):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT artist_name, goal
            FROM artist_milestones
            WHERE discord_id = ?
            AND lastfm_username = ?
            ORDER BY artist_key
        """, (
            discord_id,
            username.strip().casefold(),
        ))

        return await cursor.fetchall()


async def remove_artist_milestone(
    discord_id: int,
    username: str,
    artist: str,
) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            DELETE FROM artist_milestones
            WHERE discord_id = ?
            AND lastfm_username = ?
            AND artist_key = ?
        """, (
            discord_id,
            username.strip().casefold(),
            artist.strip().casefold(),
        ))

        await db.commit()

        return cursor.rowcount > 0


async def initialize_lastfm_history_cache():
    DB_PATH.parent.mkdir(exist_ok=True)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS lastfm_scrobbles (
                username_key TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                artist TEXT NOT NULL,
                artist_key TEXT NOT NULL,
                track TEXT NOT NULL,
                album TEXT NOT NULL DEFAULT '',
                image_url TEXT,
                track_url TEXT,
                PRIMARY KEY (
                    username_key,
                    timestamp,
                    artist_key,
                    track,
                    album
                )
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS lastfm_history_state (
                username_key TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                initial_sync_complete INTEGER NOT NULL DEFAULT 0,
                frozen_to_timestamp INTEGER,
                total_pages INTEGER,
                next_page INTEGER,
                oldest_timestamp INTEGER,
                newest_timestamp INTEGER,
                updated_at INTEGER NOT NULL DEFAULT 0
            )
        """)

        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_lastfm_scrobbles_user_artist_time
            ON lastfm_scrobbles (username_key, artist_key, timestamp)
        """)

        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_lastfm_scrobbles_user_time
            ON lastfm_scrobbles (username_key, timestamp)
        """)

        await db.commit()


async def get_history_state(username: str):
    username_key = username.strip().casefold()

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("""
            SELECT *
            FROM lastfm_history_state
            WHERE username_key = ?
        """, (
            username_key,
        ))

        row = await cursor.fetchone()

    return dict(row) if row else None


async def begin_history_index(
    username: str,
    frozen_to_timestamp: int,
    total_pages: int,
):
    if not cache.CACHE_ENABLED:
        return

    username_key = username.strip().casefold()

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO lastfm_history_state (
                username_key,
                username,
                initial_sync_complete,
                frozen_to_timestamp,
                total_pages,
                next_page,
                updated_at
            )
            VALUES (?, ?, 0, ?, ?, ?, strftime('%s', 'now'))
            ON CONFLICT(username_key)
            DO UPDATE SET
                username = excluded.username,
                frozen_to_timestamp = excluded.frozen_to_timestamp,
                total_pages = excluded.total_pages,
                next_page = excluded.next_page,
                updated_at = excluded.updated_at
        """, (
            username_key,
            username,
            frozen_to_timestamp,
            total_pages,
            total_pages,
        ))

        await db.commit()


async def set_history_next_page(
    username: str,
    next_page: int,
):
    if not cache.CACHE_ENABLED:
        return

    username_key = username.strip().casefold()

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE lastfm_history_state
            SET next_page = ?,
                updated_at = strftime('%s', 'now')
            WHERE username_key = ?
        """, (
            next_page,
            username_key,
        ))

        await db.commit()


async def finish_history_index(username: str):
    if not cache.CACHE_ENABLED:
        return

    username_key = username.strip().casefold()

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT MIN(timestamp), MAX(timestamp)
            FROM lastfm_scrobbles
            WHERE username_key = ?
        """, (
            username_key,
        ))

        oldest, newest = await cursor.fetchone()

        await db.execute("""
            UPDATE lastfm_history_state
            SET initial_sync_complete = 1,
                next_page = 0,
                oldest_timestamp = ?,
                newest_timestamp = ?,
                updated_at = strftime('%s', 'now')
            WHERE username_key = ?
        """, (
            oldest,
            newest,
            username_key,
        ))

        await db.commit()


async def refresh_history_bounds(username: str):
    if not cache.CACHE_ENABLED:
        return None, None

    username_key = username.strip().casefold()

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT MIN(timestamp), MAX(timestamp)
            FROM lastfm_scrobbles
            WHERE username_key = ?
        """, (
            username_key,
        ))

        oldest, newest = await cursor.fetchone()

        await db.execute("""
            UPDATE lastfm_history_state
            SET oldest_timestamp = ?,
                newest_timestamp = ?,
                updated_at = strftime('%s', 'now')
            WHERE username_key = ?
        """, (
            oldest,
            newest,
            username_key,
        ))

        await db.commit()

    return oldest, newest


async def insert_cached_scrobbles(
    username: str,
    scrobbles: list[dict],
) -> int:
    if not cache.CACHE_ENABLED or not scrobbles:
        return 0

    username_key = username.strip().casefold()

    rows = []

    for item in scrobbles:
        rows.append((
            username_key,
            int(item["timestamp"]),
            item["artist"],
            item["artist"].strip().casefold(),
            item["track"],
            item.get("album", ""),
            item.get("image_url"),
            item.get("track_url"),
        ))

    async with aiosqlite.connect(DB_PATH) as db:
        before = db.total_changes

        await db.executemany("""
            INSERT OR IGNORE INTO lastfm_scrobbles (
                username_key,
                timestamp,
                artist,
                artist_key,
                track,
                album,
                image_url,
                track_url
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)

        inserted = db.total_changes - before

        await db.commit()

    return inserted


async def get_cached_scrobble_count(
    username: str,
) -> int:
    username_key = username.strip().casefold()

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT COUNT(*)
            FROM lastfm_scrobbles
            WHERE username_key = ?
        """, (
            username_key,
        ))

        row = await cursor.fetchone()

    return int(row[0]) if row else 0


async def get_cached_artist_scrobbles(
    username: str,
    artist: str,
):
    username_key = username.strip().casefold()
    artist_key = artist.strip().casefold()

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("""
            SELECT
                timestamp,
                artist,
                track,
                album,
                image_url,
                track_url
            FROM lastfm_scrobbles
            WHERE username_key = ?
            AND artist_key = ?
            ORDER BY timestamp ASC
        """, (
            username_key,
            artist_key,
        ))

        rows = await cursor.fetchall()

    return [dict(row) for row in rows]


async def get_cached_first_artist_scrobble(
    username: str,
    artist: str,
):
    username_key = username.strip().casefold()
    artist_key = artist.strip().casefold()

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("""
            SELECT
                timestamp,
                artist,
                track,
                album,
                image_url,
                track_url
            FROM lastfm_scrobbles
            WHERE username_key = ?
            AND artist_key = ?
            ORDER BY timestamp ASC
            LIMIT 1
        """, (
            username_key,
            artist_key,
        ))

        row = await cursor.fetchone()

    return dict(row) if row else None