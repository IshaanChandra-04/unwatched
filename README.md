# unwatched

Turn the reels you saved or sent yourself into a document you will actually read.

You save a reel, or send it to your alt account, meaning to come back to it. You never do.
`unwatched` collects those reels from your DM thread and your saved page every day, downloads
the audio, transcribes it on your own machine, and hands one file to Claude Code, which keeps a
master document of what matters to you: the tools, the recipes, the clothes, whatever your
interest profile says. Nothing leaves your computer except the requests Instagram would see
if you opened the posts yourself.

## Five-minute setup

You need Python 3.11 or newer and [uv](https://docs.astral.sh/uv/).

```bash
uv tool install git+https://github.com/<handle>/unwatched
uvx --from git+https://github.com/<handle>/unwatched playwright install chromium
unwatched login
```

`unwatched login` opens a browser window that belongs to the tool. Sign in to Instagram there
yourself (the tool types nothing and never sees your password). The session is kept in
`~/.unwatched/browser-profile` for the daily job.

Then copy [`unwatched.example.toml`](unwatched.example.toml) somewhere outside the repo, point
it at your DM thread, a work folder, a profile and a master document, and:

```bash
unwatched ingest --links my-old-links.md --seen --work <work>   # optional: posts you already know
unwatched schedule install --config <path-to-your-unwatched.toml>
```

The first command marks posts you have already dealt with as seen so they are not fetched or
digested again. The second registers the daily job.

## Commands

| Command | What it does |
|---|---|
| `unwatched login` | Sign in once in the tool's own browser window. |
| `unwatched ingest [EXPORT...] [--links FILE] [--dm URL] [--saved] [--seen] [--full]` | Collect posts from a data export, a text file of links, a DM thread, or your saved page. |
| `unwatched fetch [--kinds saved,dm] [--thread NAME] [--since DATE] [--max 300] [--delay 3]` | Download metadata and audio for new posts, one at a time, with a cap you must raise on purpose. |
| `unwatched transcribe [--model small\|large-v3-turbo] [--only CODE...]` | Transcribe locally with faster-whisper on the CPU. |
| `unwatched build [--out FILE] [--new-only]` | Write the digest input: one file with every post's caption and transcript. |
| `unwatched digest --profile FILE --master FILE` | Run Claude Code headlessly to update your master document from the new posts. |
| `unwatched run --config FILE` | All of the above in order, with a dated log and a one-line summary. |
| `unwatched schedule install\|remove\|status` | Manage the daily Task Scheduler job. |
| `unwatched status` | Last run, last digest, post count, and anything that needs you. |

Exit codes: `3` sign-in expired (run `unwatched login`), `4` fetch cap exceeded, `5` digest
failed, `2` bad arguments.

## The daily job

`unwatched schedule install` registers a Windows Task Scheduler task at 15:00 local time that
runs `unwatched run --config <your file>`. Each run sweeps your thread and saved page newest
first and stops as soon as it reaches posts it already knows, so the traffic is a few page loads.
What can hold it up:

- **Computer off.** Nothing runs. The task is set to run as soon as you next sign in, and the
  sweep catches up on every missed day.
- **Computer asleep.** The task can wake it if your power plan allows wake timers; laptops on
  battery often block this. Hibernate and shutdown cannot be woken.
- **Not signed in to Windows.** The browser needs a desktop session, so the task runs only when
  you are logged on. A locked screen is fine.
- **Instagram asks you to sign in again.** The run stops with exit code 3 and `unwatched status`
  says so. Run `unwatched login` once; the next run resumes.
- **A long gap.** If the catch-up selects more than the fetch cap, the run stops before
  downloading and tells you the number. Rerun `unwatched fetch --max <n>` to continue.
- **Cost.** With `digest = true` the last step runs Claude Code headlessly, which spends one run a
  day from your Claude plan. Set `digest = false` to keep collection and transcription only.

On macOS or Linux the scheduler command is not implemented yet; a cron line does the same job:
`0 15 * * * unwatched run --config /path/to/unwatched.toml`.

## Profiles

A profile is a short markdown file that tells Claude what to keep, what to skip, what to extract
from each kept post, and what the output should look like. Four are bundled in
[`profiles/`](profiles/): `tech.md`, `design.md`, `cooking.md`, `fashion.md`. Copy one and edit the
four lines; there is no schema.

## Claude Code plugin

The skill that does the judgement is also a Claude Code plugin, so you can run the whole flow
from a Claude Code session:

```bash
claude plugin marketplace add <handle>/unwatched
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

## Privacy

Everything stays on your machine: the browser profile and cookies in `~/.unwatched/`, the posts,
audio, transcripts and logs in your work folder. The only network traffic is to Instagram (the
page loads of the sweep and the per-post downloads through yt-dlp) and, if you enable it, your own
Claude Code install. Never commit your work folder, your `unwatched.toml`, or anything under
`~/.unwatched/`; the repo's `.gitignore` already excludes the first two.

## Instagram's terms

Automated collection is against Instagram's terms of use, even at this gentle pace and even on
your own account. The tool keeps the risk low (one thread, one saved page, newest first, stop at
known posts, one download at a time with a delay, a cap on catch-up) but the account you use is
yours to risk. Use an alt account if that worries you.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md). The design is in
[`docs/superpowers/specs/`](docs/superpowers/specs/) and the implementation plan in
[`docs/superpowers/plans/`](docs/superpowers/plans/).
