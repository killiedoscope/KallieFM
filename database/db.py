from pathlib import Path

import aiosqlite


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

        await db.commit()


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