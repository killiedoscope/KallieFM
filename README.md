<div align="center">

# 🎵 KallieFM

### Kallie's Music Tracker

**Last.fm statistics, history, milestones, crowns, compatibility, and questionable amounts of Foo Fighters — directly in Discord.**

![Python](https://img.shields.io/badge/Python-3.x-3776AB?logo=python&logoColor=white)
![discord.py](https://img.shields.io/badge/discord.py-2.x-5865F2?logo=discord&logoColor=white)
![Last.fm](https://img.shields.io/badge/Last.fm-API-D51007?logo=lastdotfm&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-History_Cache-003B57?logo=sqlite&logoColor=white)

*There is no such thing as too much Foo.*

</div>

---

## ✨ What the hell is KallieFM?

KallieFM is a Last.fm Discord bot built because apparently the normal amount of music statistics wasn't enough.

It started as a music tracker.

Then it got crowns.

Then milestones.

Then compatibility analysis.

Then historical timelines.

Then an entire local scrobble index.

Things escalated.

KallieFM links Discord users to their Last.fm accounts and turns their listening history into commands, comparisons, milestones, leaderboards, and other increasingly unnecessary statistics.

---

## 🎛️ Features

| | Feature | What it does |
|---|---|---|
| 🎧 | **Listening** | Now playing, recent tracks, and listening information |
| 📊 | **Charts & stats** | Explore artists, albums, tracks, and profile statistics |
| 🤝 | **Compatibility** | Rank-weighted comparisons with linked Discord users **or any Last.fm username** |
| 👑 | **WhoKnows & crowns** | Find the biggest fan of an artist in your Discord server |
| 🏆 | **Milestones** | Keep track of artist listening milestones |
| 🕰️ | **History** | Find first scrobbles and build artist listening timelines |
| 🗃️ | **History indexing** | Optionally cache scrobble history locally for fast historical queries |
| 🎸 | **Dave's Verdict** | Completely professional musical analysis™ |

---

## 🤝 Compatibility

KallieFM compares each listener's **overall top 50 artists** using rank-weighted overlap.

That means artists near the top of your library matter more than artists sitting at #47 because you listened to an album twice in 2022.

The compatibility percentage is real.

Dave's interpretation of that percentage is another matter entirely.

```text
⚠️ DAVE SATURATION WARNING
Compatibility analysis compromised.
There is too much fucking Foo in this room.
```

Certain combinations of listening habits may produce additional highly qualified medical opinions.

This is working as intended.

Bug reports regarding excessive Dave Grohl will be investigated and subsequently ignored.

---

## 👑 WhoKnows & artist crowns

Want to know who in the server has listened to an artist the most?

That's what `/fm whoknows` is for.

KallieFM checks linked listeners in the server, builds a leaderboard, and awards the artist crown to whoever has the most plays.

Crowns persist, which also means they can be stolen.

Civil disputes over ownership are outside the scope of technical support.

---

## 🕰️ History without repeatedly bullying the API

Historical questions become expensive when someone's Last.fm account contains tens or hundreds of thousands of scrobbles.

KallieFM therefore supports an **optional local history index**.

Instead of downloading an entire listening history every time somebody asks when they first listened to an artist, the bot can index the account once and answer future historical queries from its local cache.

The index is designed to be:

- persistent across restarts
- resumable after interruption
- duplicate-safe
- incrementally updateable
- useful across artists rather than indexing one artist at a time

Once indexed, commands such as artist timelines can be answered locally instead of crawling hundreds of Last.fm API pages again.

### `/fm index`

The initial index can take a while for large libraries. After that, later syncs only need to collect newer listening history.

History indexing is optional. You do **not** need to index your account to use the normal KallieFM commands.

---

## 🎵 Linking Last.fm

KallieFM uses a linked Last.fm username for your Discord account.

```text
/fm set username:your_lastfm_username
```

Once linked, you can use the normal `/fm` commands without repeatedly entering your username.

Comparisons can also target an arbitrary Last.fm account directly:

```text
/fm compare username:someone_on_lastfm
```

They don't need to be in your Discord server.

Yes, this feature was added at approximately 5 AM.

---

## 🧠 How compatibility works

The comparison system uses each account's overall top 50 artists.

Rank #1 receives the highest weight, rank #50 receives the lowest, and shared artists contribute according to the lower weight between the two users. Identical ranked lists therefore reach 100%, while completely separate top-50 lists reach 0%.

Play volume does not directly decide the compatibility percentage, so an older account with hundreds of thousands of scrobbles isn't automatically favoured over a newer account.

Playcounts *can*, however, be relevant to certain Easter eggs.

For reasons.

---

## 🧰 Built with

- **Python**
- **discord.py**
- **aiohttp**
- **SQLite**
- **Last.fm API**
- questionable amounts of Foo Fighters

The project is intentionally kept fairly straightforward. Discord commands live separately from Last.fm API handling, persistent data lives in SQLite, and the compatibility maths is kept independent from the Discord presentation layer.

Or, put differently:

> the code is allowed to be more organised than the person writing it

---

## 📁 Project layout

```text
KallieFM/
├── bot.py
├── database/
│   └── db.py
├── lastfm/
│   ├── __init__.py
│   ├── account.py
│   ├── charts.py
│   ├── compatibility.py
│   ├── history.py
│   ├── listening.py
│   ├── milestones.py
│   ├── shared.py
│   └── social.py
├── services/
│   └── lastfm_api.py
└── README.md
```

The exact layout may change as KallieFM grows and acquires yet another feature that definitely wasn't supposed to become an entire subsystem.

---

## 🚧 Development status

KallieFM is actively developed.

Things may change. Things may break. Things may become features because somebody asked a random question at 5 AM.

The development environment currently consists of:

- VS Code
- Python
- Git
- Foo Fighters
- Jacksepticeye playing Happy Wheels in another browser tab
- an apparently optional sleep schedule

Professional operation.

---

## 🧪 Philosophy

The goal isn't to make another identical Last.fm command bot.

KallieFM should provide useful statistics while still having enough personality that using it feels fun. The numbers should be legitimate, the commentary is allowed to be stupid.

That's why compatibility uses deterministic maths while Dave is permitted to diagnose musical contamination.

That's why historical data gets a real cache instead of making the same enormous API crawl repeatedly.

And that's why a feature can be technically sensible while still responding to two Foo Fighters obsessives like the building needs to be evacuated.

---

## 🔐 Configuration

Secrets such as Discord tokens and Last.fm API credentials should be stored in environment variables and **never committed to Git**.

A typical local configuration will need credentials for Discord and Last.fm. Exact environment-variable names depend on the current project configuration.

If you're running your own copy, check the source/configuration before starting the bot rather than putting credentials directly into Python files.

---

## ⚠️ Last.fm & API usage

KallieFM uses the Last.fm API and is not affiliated with or endorsed by Last.fm.

The history index exists partly to avoid repeatedly requesting the same historical data. If you're modifying or hosting KallieFM yourself, be considerate with API traffic and follow Last.fm's current API terms and requirements.

Please do not turn the indexer into an API pressure washer.

---

## 🗺️ What's next?

KallieFM is still growing. Current areas of development include improving onboarding, making history indexing more robust, improving storage efficiency, and continuing to expand statistics and social features without turning the command list into a small novel.

There will probably also be more Easter eggs.

Unfortunately for everyone.

---

## 🤝 Contributing

KallieFM is currently a personal hobby project, but bug reports and useful ideas are welcome.

If something genuinely breaks, please include enough information to reproduce it.

If the bug report is:

> Dave said mean things about my music taste

please first consider whether Dave was correct.

---

<div align="center">

## 🎸 There is no such thing as too much Foo.

**Kallie's Music Tracker**

<sub>Made with Python, Last.fm, questionable judgement, and an unreasonable amount of Dave Grohl.</sub>

</div>
