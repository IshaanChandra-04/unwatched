# unwatched

Turn the reels you saved or sent yourself into a document you will actually read.

You save a reel, or send it to your alt account, meaning to come back to it. You never do.
`unwatched` collects those reels from your DM thread and your saved page every day, downloads
the audio and a small video stream, transcribes the speech on your own machine, picks the frames
that show something new, has Claude Code write down what is on screen (the lists, the repository
names, the site being demonstrated), and hands one file to Claude Code, which keeps a master
document of what matters to you: the tools, the recipes, the clothes, whatever your interest
profile says. Nothing leaves your computer except the requests Instagram would see if you opened
the posts yourself, and the headless Claude Code runs you turn on.

## Five-minute setup

You need Python 3.11 to 3.13 and [uv](https://docs.astral.sh/uv/). For the digest and the
on-screen text you also need [Claude Code](https://docs.claude.com/en/docs/claude-code) signed in
on the same machine; without it, collection and transcription still run.

```bash
uv tool install git+https://github.com/IshaanChandra-04/unwatched
unwatched login
unwatched doctor
```

`unwatched login` opens a browser window that belongs to the tool (it downloads the browser
first, about 200 MB, once). Sign in to Instagram there yourself; the tool types nothing and never
sees your password. The session is kept in `~/.unwatched/browser-profile` for the daily job.
`unwatched doctor` checks everything the tool needs and says what to fix.

Then copy [`unwatched.example.toml`](unwatched.example.toml) somewhere outside the repo
(`~/.unwatched/unwatched.toml` is a good place), point it at your DM thread, a work folder, a
profile (`"tech"`, `"design"`, `"cooking"` or `"fashion"` names a bundled one) and a master
document, and:

```bash
unwatched doctor --config ~/.unwatched/unwatched.toml
unwatched ingest --links my-old-links.md --seen --work <work>   # optional: posts you already know
unwatched schedule install --config ~/.unwatched/unwatched.toml
```

The `ingest --seen` line marks posts you have already dealt with as seen so they are not fetched
or digested again. The last line registers the daily job for your system.

On Linux the browser also needs a few system libraries once:
`uvx --from playwright playwright install-deps chromium` (asks for sudo). If `unwatched` is not
found after the install, run `uv tool update-shell` and open a new terminal.

## What a run does

```
ingest ──> fetch ──> pictures ──> frames ──> transcribe ──> describe ──> build ──> digest
sweep      yt-dlp    browser:     PyAV:       faster-      Claude Code:   one      Claude Code:
DM thread  caption,  slides of    frames      whisper on   what is on     file     update the
and saved  audio,    image posts  that        the CPU      screen, per              master
page       video     and their    change                   post                     document
                     captions
```

Every stage leaves files in the work folder (`posts.jsonl`, `meta/`, `audio/`, `video/`,
`frames/<code>/NN.jpg`, `frames/<code>.md`, `transcripts/`, `digest-input.md`, `state.json`), so a
failed stage is retried next time and nothing is downloaded twice. A post is shown to the digest
when it is new or has gained material (a transcript, the on-screen text), at most
`digest_max_posts` per run.

## Commands

| Command | What it does |
|---|---|
| `unwatched login` | Sign in once in the tool's own browser window (installs the browser the first time). |
| `unwatched doctor [--config FILE]` | Check Python, the dependencies, the browser, the sign-in and your config; say what to fix. |
| `unwatched ingest [EXPORT...] [--links FILE] [--dm URL] [--saved] [--seen] [--full]` | Collect posts from a data export, a text file of links, a DM thread, or your saved page. |
| `unwatched fetch [--kinds saved,dm] [--thread NAME] [--since DATE] [--max 300] [--delay 3]` | Download caption, audio, video stream and cover picture for new posts, one at a time, with a cap you must raise on purpose. |
| `unwatched pictures [--only CODE...]` | Download every slide and the caption of image posts through the signed-in browser. |
| `unwatched frames [--only CODE...]` | Pick the frames of each video that show something new (twelve at most). |
| `unwatched transcribe [--model small\|large-v3-turbo] [--only CODE...]` | Transcribe locally with faster-whisper on the CPU. |
| `unwatched describe [--only CODE...] [--claude X]` | Have Claude Code read each post's pictures and write what is on screen. |
| `unwatched build [--out FILE] [--new-only]` | Write the digest input: one file with every post's caption, transcript and on-screen text. |
| `unwatched digest --profile FILE --master FILE [--max-posts 40]` | Run Claude Code headlessly to update your master document from the due posts. |
| `unwatched run --config FILE` | All of the above in order, with a dated log and a one-line summary. |
| `unwatched schedule install\|remove\|status [--config FILE] [--at HH:MM]` | Manage the daily job (Task Scheduler, launchd or cron). |
| `unwatched status` | Last run, last digest, post count, and anything that needs you. |

Exit codes: `3` sign-in expired (run `unwatched login`), `4` fetch cap exceeded, `5` digest
failed, `2` bad arguments or config, `130` interrupted.

## The daily job

`unwatched schedule install` registers a job at 15:00 local time (change it with `--at`) that
runs `unwatched run --config <your file>`:

- **Windows:** a Task Scheduler task that runs when you are logged on, catches up a missed day
  as soon as you next sign in, and can wake the machine if your power plan allows wake timers.
- **macOS:** a launchd agent in `~/Library/LaunchAgents/com.unwatched.daily.plist`. A time slept
  through runs at wake. Output goes to `~/.unwatched/launchd.log`.
- **Linux:** a line in your crontab tagged `# unwatched daily`, with the full path of the command
  and `DISPLAY=:0`, because the sweep opens a visible browser window and needs your desktop
  session. cron does not catch up missed runs.

Each run sweeps your thread and saved page newest first and stops as soon as it reaches posts it
already knows, so the traffic is a few page loads. What can hold it up:

- **Instagram asks you to sign in again.** The run stops with exit code 3 and `unwatched status`
  says so. Run `unwatched login` once; the next run resumes.
- **A long gap.** If the catch-up selects more than the fetch cap, the run stops before
  downloading and tells you the number. Rerun `unwatched fetch --max <n>` to continue.
- **Cost.** With `digest = true` the run spends Claude Code usage from your plan: one short run
  per new post to write the on-screen text (`frames = false` turns that off) and one digest run
  for the batch. Set `digest = false` to keep collection and transcription only.
- **A big backlog.** The digest takes `digest_max_posts` (default 40) posts per run and the
  summary says how many are waiting; run `unwatched digest` again to continue, or wait a day.
- **A digest that runs out of turns.** Claude gets `digest_max_turns` tool turns (default 60). If
  it fails, the run exits 5, `status` shows the reason, and the next run offers the same posts
  again, so raise the limit in your config or run `unwatched digest` by hand with `--max-turns`.
- **Claude not on PATH.** The scheduled job sees a smaller PATH than your shell. If `status` or
  `doctor` shows `claude not found`, set `claude = "<full path to claude>"` in your config.
- **Every fetch failed.** Usually the Instagram session or cookies went stale. `status` says so;
  run `unwatched login` once.
- **The first transcription is slow.** faster-whisper downloads its model the first time (about
  500 MB for `small`, 1.6 GB for `large-v3-turbo`); the log says so.
- **The task's time limit.** The Windows task stops after two hours; a very large catch-up with
  CPU transcription can hit it. The files written so far are kept and the next run continues.
- **Upgrading from 0.1.** The first runs complete the posts you already had: the video stream and
  the pictures are downloaded (not counted against the fetch cap), and the on-screen text is
  written for up to `digest_max_posts` old posts per run, each a short Claude run. Set
  `frames = false` first if you would rather not spend that.

## Profiles

A profile is a short markdown file that tells Claude what to keep, what to skip, what to extract
from each kept post, and what the output should look like. Four ship with the tool and can be
named in the config as `profile = "tech"`, `"design"`, `"cooking"` or `"fashion"`; see
[`profiles/`](profiles/). Copy one and edit the four lines to make your own; there is no schema.

## Claude Code plugin

The skill that does the judgement is also a Claude Code plugin, so you can run the whole flow
from a Claude Code session:

```bash
claude plugin marketplace add IshaanChandra-04/unwatched
claude plugin install unwatched
```

Then say "digest my saved reels" and Claude walks you through it.

## Backfill from your data export

Likes and your own archived posts are only available through Instagram's data export, which also
covers every DM thread and saved post in one go. In the Instagram app or on the web: Accounts
Center, Your information and permissions, Download your information, select the account that
receives the reels (your alt account, if you use one), choose JSON format and all time, and tick
at least Saved, Likes, Messages and Content. It arrives by email in a few hours to a couple of
days. Then:

```bash
unwatched ingest path/to/instagram-export.zip --work <work>
```

Meta does not document the export's layout, and this parser was written against the file names
and fields seen in earlier exports (`saved_posts.json`, `liked_posts.json`,
`messages/inbox/*/message_*.json`, `archived_posts.json`). If ingest reports no posts from an
export, open an issue with the list of file names in your zip (no contents needed).

## Troubleshooting

| You see | Do |
|---|---|
| `Executable doesn't exist` from Playwright | `unwatched login` installs the browser; or `python -m playwright install chromium` in the tool's environment. |
| `sign-in expired, run: unwatched login` (exit 3) | Run `unwatched login` and sign in; the daily run resumes by itself. |
| `could not find your username` | Instagram is not in English on your account; set `username = "<your handle>"` in the config. |
| `claude not found` | Install Claude Code, or set `claude = "<full path>"` in the config for the scheduled job. |
| `cannot read unwatched.toml: unknown key ...` | A typo in the config; the keys are the ones in `unwatched.example.toml`. |
| `selected N posts, cap is 300` (exit 4) | A big backlog; `unwatched fetch --max N` to go on, on purpose. |
| `N more waiting, run unwatched digest again` | Not an error: the digest works in batches of `digest_max_posts`. |
| Nothing happens at the scheduled time | `unwatched schedule status`, then the dated file in `<work>/logs/`. On Linux the desktop must be unlocked for the browser window. |
| `unwatched: command not found` after install | `uv tool update-shell`, then a new terminal. |

## Privacy

Everything stays on your machine: the browser profile and cookies in `~/.unwatched/`, the posts,
audio, video, pictures, transcripts and logs in your work folder. The only network traffic is to
Instagram (the page loads of the sweep and the per-post downloads through yt-dlp) and, if you
enable it, your own Claude Code install, which reads the pictures and the digest input. Never
commit your work folder, your `unwatched.toml`, or anything under `~/.unwatched/`; the repo's
`.gitignore` already excludes the first two.

## Instagram's terms

Automated collection is against Instagram's terms of use, even at this gentle pace and even on
your own account. The tool keeps the risk low (one thread, one saved page, newest first, stop at
known posts, one download at a time with a delay, a cap on catch-up) but the account you use is
yours to risk. Use an alt account if that worries you.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md). The design is in
[`docs/superpowers/specs/`](docs/superpowers/specs/) and the implementation plans in
[`docs/superpowers/plans/`](docs/superpowers/plans/).
