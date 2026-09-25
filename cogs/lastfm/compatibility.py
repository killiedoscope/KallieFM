"""Pure, deterministic comparison of Last.fm overall top-50 artist lists."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RankedArtist:
    name: str
    rank: int
    plays: int

    @property
    def weight(self) -> int:
        return 51 - self.rank


def ranked_artists(artists: list[dict]) -> dict[str, RankedArtist]:
    result = {}

    for rank, artist in enumerate(artists[:50], start=1):
        name = artist.get("name", "").strip()
        key = name.casefold()
        plays = max(0, int(artist.get("playcount", 0)))

        if key and plays and key not in result:
            result[key] = RankedArtist(
                name,
                rank,
                plays,
            )

    return result


def compare_artists(left, right):
    """
    Weighted Dice compatibility.

    Rank r has weight 51-r:
    #1 = 50 points
    #50 = 1 point

    Missing artists have weight zero.

    Identical ranked lists score 100%.
    Completely disjoint lists score 0%.

    The score is symmetric and independent of account age/play volume.
    Short lists use their actual weight totals.
    Empty histories score zero.
    """

    shared = sorted(
        left.keys() & right.keys(),
        key=lambda key: (
            -min(
                left[key].weight,
                right[key].weight,
            ),
            -(
                left[key].weight
                + right[key].weight
            ),
            key,
        ),
    )

    total = (
        sum(
            artist.weight
            for artist in left.values()
        )
        + sum(
            artist.weight
            for artist in right.values()
        )
    )

    if total:
        score = (
            200
            * sum(
                min(
                    left[key].weight,
                    right[key].weight,
                )
                for key in shared
            )
            / total
        )
    else:
        score = 0

    return score, shared


def is_obsessed(
    artists,
    artist_name: str,
    total_plays: int,
) -> bool:
    """
    Strong obsession requires:

    - Artist is in the user's top 3
    - At least 1,000 artist plays
    - At least 10% of all account scrobbles

    This deliberately requires substantial listening while still allowing
    long-running accounts with broader libraries to trigger easter eggs.
    """

    artist = artists.get(
        artist_name.casefold()
    )

    return bool(
        artist
        and artist.rank <= 3
        and artist.plays >= 1000
        and total_plays > 0
        and artist.plays / total_plays >= 0.10
    )


def daves_verdict(
    score,
    left,
    right,
    left_total,
    right_total,
):
    left_foo = is_obsessed(
        left,
        "Foo Fighters",
        left_total,
    )

    right_foo = is_obsessed(
        right,
        "Foo Fighters",
        right_total,
    )

    if left_foo and right_foo:
        return (
            "⚠️ DAVE SATURATION WARNING\n"
            "Compatibility analysis compromised. "
            "There is too much fucking Foo in this room."
        )

    foo_vs_nickelback = (
        left_foo
        and is_obsessed(
            right,
            "Nickelback",
            right_total,
        )
    ) or (
        right_foo
        and is_obsessed(
            left,
            "Nickelback",
            left_total,
        )
    )

    if foo_vs_nickelback:
        return (
            "⚠️ MUSICAL CONTAMINATION DETECTED\n\n"
            "Dave has reviewed these listening histories and diagnosed "
            "an excessive Foo Fighters dependency in one listener.\n\n"
            "The other listens to Nickelback.\n\n"
            "These conditions are not equivalent. One is enthusiasm. "
            "The other has previously required medical intervention.\n\n"
            "Recommended treatment: 50cc of White Limo and immediate "
            "Photograph isolation."
        )

    if score >= 75:
        return (
            "Dave approves. You're practically sharing "
            "a pair of headphones."
        )

    if score >= 50:
        return (
            "Solid overlap. Dave would trust you two "
            "with the tour-bus aux cable."
        )

    if score >= 25:
        return (
            "Some common ground. Build a playlist together "
            "and see what sticks."
        )

    if score > 0:
        return (
            "A few shared riffs in very different record collections. "
            "Trade recommendations."
        )

    return (
        "No shared artists in these top lists. "
        "Dave suggests a musical exchange programme."
    )