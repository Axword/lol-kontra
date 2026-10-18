# Guest nicknames and statistics

`POST /api/v1/guest/profile/` uses the same private `guest_token` already stored
by the browser for games. The body accepts a 16–64 character token containing
ASCII letters, digits, `_` or `-`, plus an optional `nickname`.

- Omit `nickname` to load or create the guest profile.
- Send a name to update it, or an empty string to restore the generated name.
- The response contains `nickname` (a string or `null`), `display_name` and
  `stats`: `games_played`, `total_points`, `avg_points`, `best_score`,
  `legendary_answers`, `diamond_picks`, `current_streak` and `max_streak`.
- Public leaderboard names are `Gość-Nickname`, or `Gość-XXXXXXXX` for the
  deterministic generated fallback. Registered usernames are unchanged.
- Validation errors use HTTP 400 with a `nickname` or `guest_token` field.
  The endpoint uses the normal API rate limits and sends `Cache-Control:
  private, no-store`.

Names have 3–24 normalized characters. Unicode letters, digits, spaces, hyphens
and underscores are allowed; URLs, markup, emoji, control/invisible characters
and names made only of punctuation are rejected. Repeated spaces are collapsed.
The local Polish/English filter rejects common profanity, slurs and common
letter/number or separator obfuscation. Short ambiguous words use whole-word
matches; a narrow list of clear severe roots also matches inside decorated names.
No local blocklist can detect every offensive expression.

The new `GuestProfile` table stores an HMAC-SHA256 token key, never the raw bearer
token. Neither key nor token is returned by the profile or leaderboard response.
Nicknames are labels, not login credentials: two people may use the same name
without sharing games or statistics. Keeping the browser token is necessary to
retain guest identity; naming never creates submissions, votes or accounts.

Guest statistics are derived from existing finished, non-practice, non-seed
games on public available boards. This also picks up games played before a nick
was chosen. Renaming or resetting the nickname leaves progress and scores intact.

Deploy migration `users.0004_guestprofile` with the normal database bootstrap.
It only creates the profile table and does not rewrite submissions or accounts.
