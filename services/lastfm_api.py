import os

import aiohttp


LASTFM_API_KEY = os.getenv("LASTFM_API_KEY")
LASTFM_API_URL = "https://ws.audioscrobbler.com/2.0/"


class LastFMError(Exception):
    """Something went wrong while talking to Last.fm."""
    pass


async def request_lastfm(method: str, **params):
    if not LASTFM_API_KEY:
        raise LastFMError("LASTFM_API_KEY is missing from .env")

    request_params = {
        "method": method,
        "api_key": LASTFM_API_KEY,
        "format": "json",
        **params,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                LASTFM_API_URL,
                params=request_params,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:

                if response.status != 200:
                    raise LastFMError(
                        f"Last.fm returned HTTP {response.status}"
                    )

                data = await response.json()

    except aiohttp.ClientError:
        raise LastFMError("Couldn't connect to Last.fm.")

    if "error" in data:
        raise LastFMError(
            data.get("message", "Unknown Last.fm error")
        )

    return data


async def get_recent_tracks(username: str, limit: int = 10):
    data = await request_lastfm(
        "user.getrecenttracks",
        user=username,
        limit=limit,
        extended=1,
    )

    return data["recenttracks"]["track"]


async def get_recent_track(username: str):
    tracks = await get_recent_tracks(
        username,
        limit=1,
    )

    if not tracks:
        return None

    return tracks[0]


async def get_user_info(username: str):
    data = await request_lastfm(
        "user.getinfo",
        user=username,
    )

    return data["user"]


async def get_top_artists(
    username: str,
    period: str = "overall",
    limit: int = 10,
):
    data = await request_lastfm(
        "user.gettopartists",
        user=username,
        period=period,
        limit=limit,
    )

    return data["topartists"]["artist"]


async def get_top_albums(
    username: str,
    period: str = "overall",
    limit: int = 10,
):
    data = await request_lastfm(
        "user.gettopalbums",
        user=username,
        period=period,
        limit=limit,
    )

    return data["topalbums"]["album"]


async def get_top_tracks(
    username: str,
    period: str = "overall",
    limit: int = 10,
):
    data = await request_lastfm(
        "user.gettoptracks",
        user=username,
        period=period,
        limit=limit,
    )

    return data["toptracks"]["track"]


async def get_artist_info(
    artist: str,
    username: str | None = None,
):
    params = {
        "artist": artist,
        "autocorrect": 1,
    }

    if username:
        params["username"] = username

    data = await request_lastfm(
        "artist.getinfo",
        **params,
    )

    return data["artist"]


async def get_artist_playcount(
    artist: str,
    username: str,
):
    data = await request_lastfm(
        "artist.getinfo",
        artist=artist,
        username=username,
        autocorrect=1,
    )

    artist_data = data["artist"]

    canonical_name = artist_data.get(
        "name",
        artist,
    )

    stats = artist_data.get("stats", {})

    playcount = int(
        stats.get("userplaycount", 0)
    )

    return canonical_name, playcount