import os

import aiohttp
from dotenv import load_dotenv


# Load environment variables before reading the Last.fm API key.
load_dotenv()

LASTFM_API_KEY = os.getenv("LASTFM_API_KEY")
LASTFM_API_URL = "https://ws.audioscrobbler.com/2.0/"

_session: aiohttp.ClientSession | None = None


class LastFMError(Exception):
    """Something went wrong while talking to Last.fm."""
    pass


async def get_session() -> aiohttp.ClientSession:
    """Return the shared Last.fm HTTP session."""

    global _session

    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=10),
            headers={
                "User-Agent": "KalliesMusicTracker/1.0 (Discord Last.fm bot)"
            },
        )

    return _session


async def close_session():
    """Close the shared HTTP session cleanly."""

    global _session

    if _session is not None and not _session.closed:
        await _session.close()

    _session = None


async def request_lastfm(method: str, **params):
    """Make a request to the Last.fm API."""

    if not LASTFM_API_KEY:
        raise LastFMError(
            "LASTFM_API_KEY is missing from .env"
        )

    request_params = {
        "method": method,
        "api_key": LASTFM_API_KEY,
        "format": "json",
        **params,
    }

    session = await get_session()

    try:
        async with session.get(
            LASTFM_API_URL,
            params=request_params,
        ) as response:

            if response.status != 200:
                raise LastFMError(
                    f"Last.fm returned HTTP {response.status}"
                )

            data = await response.json()

    except aiohttp.ClientError as error:
        raise LastFMError(
            "Couldn't connect to Last.fm."
        ) from error

    except TimeoutError as error:
        raise LastFMError(
            "Last.fm took too long to respond."
        ) from error

    if "error" in data:
        raise LastFMError(
            data.get(
                "message",
                "Unknown Last.fm error",
            )
        )

    return data


async def get_recent_tracks(
    username: str,
    limit: int = 10,
):
    """Return a user's most recent tracks."""

    data = await request_lastfm(
        "user.getrecenttracks",
        user=username,
        limit=limit,
        extended=1,
    )

    return data["recenttracks"]["track"]


async def get_recent_track(
    username: str,
):
    """Return a user's most recent track."""

    tracks = await get_recent_tracks(
        username,
        limit=1,
    )

    if not tracks:
        return None

    return tracks[0]


async def get_user_info(
    username: str,
):
    """Return Last.fm user information."""

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
    """Return a user's top artists."""

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
    """Return a user's top albums."""

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
    """Return a user's top tracks."""

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
    """Return Last.fm information for an artist."""

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
    """Return canonical artist name and user's playcount."""

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

    stats = artist_data.get(
        "stats",
        {},
    )

    playcount = int(
        stats.get(
            "userplaycount",
            0,
        )
    )

    return canonical_name, playcount


async def get_recent_tracks_page(
    username: str,
    *,
    page: int = 1,
    limit: int = 200,
    from_timestamp: int | None = None,
    to_timestamp: int | None = None,
):
    """
    Fetch one page of a user's scrobble history.

    Returns:
        tuple[list[dict], dict]:
            The tracks on the page and Last.fm pagination metadata.
    """

    params = {
        "user": username,
        "page": page,
        "limit": limit,
        "extended": 1,
    }

    if from_timestamp is not None:
        params["from"] = from_timestamp

    if to_timestamp is not None:
        params["to"] = to_timestamp

    data = await request_lastfm(
        "user.getrecenttracks",
        **params,
    )

    recent = data.get(
        "recenttracks",
        {},
    )

    tracks = recent.get(
        "track",
        [],
    )

    metadata = recent.get(
        "@attr",
        {},
    )

    return tracks, metadata


def _track_artist_name(track: dict) -> str:
    """Extract an artist name from a recent-track object."""

    artist = track.get(
        "artist",
        {},
    )

    if isinstance(artist, dict):
        return (
            artist.get("name")
            or artist.get("#text")
            or ""
        ).strip()

    if isinstance(artist, str):
        return artist.strip()

    return ""


async def get_oldest_scrobble(
    username: str,
    artist: str | None = None,
):
    """
    Find the oldest completed scrobble in a user's history.

    If artist is supplied, return the oldest scrobble matching
    that artist.

    Last.fm returns recent tracks newest-first. We obtain the
    number of pages, start at the oldest page, and walk toward
    the present until a matching scrobble is found.
    """

    _, metadata = await get_recent_tracks_page(
        username,
        page=1,
        limit=200,
    )

    try:
        total_pages = int(
            metadata.get(
                "totalPages",
                1,
            )
        )
    except (TypeError, ValueError):
        total_pages = 1

    total_pages = max(
        total_pages,
        1,
    )

    artist_key = (
        artist.casefold()
        if artist
        else None
    )

    for page in range(
        total_pages,
        0,
        -1,
    ):
        tracks, _ = await get_recent_tracks_page(
            username,
            page=page,
            limit=200,
        )

        # Each page is newest -> oldest.
        # Reverse it so the oldest item is examined first.
        for track in reversed(tracks):
            date = track.get("date")

            # A now-playing item does not have a completed
            # scrobble timestamp.
            if not isinstance(date, dict):
                continue

            if not date.get("uts"):
                continue

            if artist_key is not None:
                track_artist = _track_artist_name(
                    track
                )

                if (
                    track_artist.casefold()
                    != artist_key
                ):
                    continue

            return track

    return None