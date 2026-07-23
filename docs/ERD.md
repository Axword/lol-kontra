# Entity Relationship Diagram — LoL Kontra

## Models & Relationships

```
┌─────────────────────────────────────────────────────────────────────┐
│                          PLAYERS APP                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────┐    1:N     ┌─────────────────────┐    N:1    ┌──────┐ │
│  │  Player   │──────────▶│ PlayerTeamHistory    │◀─────────│ Team │ │
│  │          │            │ (start/end dates)    │          │      │ │
│  │ slug (PK)│            └─────────────────────┘          │slug  │ │
│  │ nickname │                                             │(PK)  │ │
│  │ role     │    1:N     ┌─────────────────────┐    N:1   │name  │ │
│  │ country  │──────────▶│TournamentAppearance  │◀─────────│region│ │
│  │ residency│            │ (year, placement)    │          └──────┘ │
│  │ continent│            └─────────────────────┘                    │
│  │ is_active│                                                       │
│  │ worlds_* │    1:N     ┌─────────────────────┐    N:1    ┌──────┐│
│  │ attributes│──────────▶│PlayerCoachHistory   │◀─────────│Coach ││
│  │ (JSON)   │            │ (year, team)         │          │      ││
│  └──────────┘            └─────────────────────┘          │slug  ││
│       │                                                   │(PK)  ││
│       │  1:N     ┌─────────────────────┐                  │name  ││
│       └─────────▶│CareerChampionStat   │                  └──────┘│
│                  │ (games, KDA, dmg)   │                           │
│                  └─────────────────────┘                           │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                          DAILIES APP                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────┐    1:N     ┌──────────────┐    1:N    ┌────────────┐ │
│  │  Daily    │──────────▶│  DailySlot    │─────────▶│DailySlot   │ │
│  │          │            │              │          │Condition   │ │
│  │ id (PK)  │            │ id (PK)      │          │            │ │
│  │ date (UQ)│            │ daily (FK)   │          │ slot (FK)  │ │
│  │ status   │            │ position 1-5 │          │ type       │ │
│  │ reveal   │            │ role         │          │ operator   │ │
│  │ created_by│           │ label_pl/en  │          │ value(JSON)│ │
│  └──────────┘            └──────────────┘          │ label_pl/en│ │
│                                                     └────────────┘ │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                        SUBMISSIONS APP                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐    1:N    ┌──────────────────┐                    │
│  │  Submission   │─────────▶│ SubmissionAnswer  │                    │
│  │              │          │                  │                    │
│  │ id (PK)      │          │ id (PK)          │                    │
│  │ daily (FK)   │          │ submission (FK)  │                    │
│  │ user (FK)    │          │ daily_slot (FK)  │──── to DailySlot   │
│  │ guest_token  │          │ player (FK)      │──── to Player      │
│  │ is_scored    │          │ is_correct       │                    │
│  │ total_points │          │ rarity_tier      │                    │
│  │ (Float)      │          │ rarity_percent   │                    │
│  │              │          │ points_awarded   │                    │
│  │              │          │ (Float)          │                    │
│  │              │          │ is_diamond_pick  │                    │
│  └──────────────┘          └──────────────────┘                    │
│                                                                      │
│  CONSTRAINTS:                                                        │
│  • UNIQUE(daily, user) when user IS NOT NULL                        │
│  • UNIQUE(daily, guest_token) when guest_token IS NOT NULL          │
│  • UNIQUE(submission, daily_slot) — 1 answer per slot              │
│  • UNIQUE(daily_slot, player) WHERE is_diamond_pick=TRUE            │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                         SCORING APP                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────┐           ┌──────────────┐                    │
│  │ AnswerStatsDaily  │           │ScoringConfig │                    │
│  │                  │           │              │                    │
│  │ daily_slot (FK)──│── to Slot │ is_active    │                    │
│  │ player (FK)──────│── to Plyr │ points_*     │                    │
│  │ pick_count       │           │ threshold_*  │                    │
│  │ pick_percent     │           └──────────────┘                    │
│  │ rarity_tier      │                                                │
│  │                  │           (singleton — only 1 active config)  │
│  │ UNIQUE(slot,plyr)│                                                │
│  └──────────────────┘                                                │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                          USERS APP                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────┐   1:1    ┌──────────────┐                            │
│  │   User    │─────────▶│  UserStats    │                            │
│  │ (Django) │          │              │                            │
│  │          │          │ games_played │                            │
│  │          │          │ total_points │                            │
│  │          │          │ best_score   │                            │
│  │          │          │ streaks      │                            │
│  └──────────┘          └──────────────┘                            │
└─────────────────────────────────────────────────────────────────────┘
```

## Cross-App Foreign Keys

| From | To | Field | On Delete | Related Name |
|------|-----|-------|-----------|-------------|
| Daily → User | auth.User | `created_by` | SET_NULL | — |
| DailySlot → Daily | dailies.Daily | `daily` | CASCADE | `slots` |
| DailySlotCondition → DailySlot | dailies.DailySlot | `slot` | CASCADE | `conditions` |
| Submission → Daily | dailies.Daily | `daily` | CASCADE | `submissions` |
| Submission → User | auth.User | `user` | SET_NULL | — |
| SubmissionAnswer → Submission | submissions.Submission | `submission` | CASCADE | `answers` |
| SubmissionAnswer → DailySlot | dailies.DailySlot | `daily_slot` | PROTECT | `answers` |
| SubmissionAnswer → Player | players.Player | `player` | PROTECT | `submission_answers` |
| AnswerStatsDaily → DailySlot | dailies.DailySlot | `daily_slot` | CASCADE | `answer_stats` |
| AnswerStatsDaily → Player | players.Player | `player` | CASCADE | `answer_stats` |
| PlayerTeamHistory → Player | players.Player | `player` | CASCADE | `team_history` |
| PlayerTeamHistory → Team | players.Team | `team` | CASCADE | `player_histories` |
| CareerChampionStat → Player | players.Player | `player` | CASCADE | `champion_stats` |
| UserStats → User | auth.User | `user` | CASCADE | `stats` |

## On Delete Strategy

| Strategy | Used For | Rationale |
|----------|----------|-----------|
| **CASCADE** | Slot→Daily, Condition→Slot, Answer→Submission | Child records meaningless without parent |
| **PROTECT** | SubmissionAnswer→Player, SubmissionAnswer→DailySlot | Never delete a player/slot that has answers |
| **SET_NULL** | Daily→User, Submission→User | Keep records when user account is deleted |

## Indexes

| Model | Index | Purpose |
|-------|-------|---------|
| Submission | `(daily, is_scored)` | Scoring engine: fetch unscored submissions |
| SubmissionAnswer | `(daily_slot, is_correct)` | Scoring: count correct answers per slot |
| SubmissionAnswer | `(daily_slot, player)` | Stats: group by slot+player |
| SubmissionAnswer | `is_correct` | Filter correct answers |
| SubmissionAnswer | `is_diamond_pick` | Filter diamond picks |
| Submission | `is_scored` | Filter scored/unscored |
| AnswerStatsDaily | `daily_slot` | Fetch stats for a daily |
| Player | `(primary_role, is_active)` | Active players by role |
| Player | `attributes` (GIN) | JSON queries on attributes |

## Data Flow

```
Frontend                  Backend                      Database
────────                  ───────                      ────────
                          
GET /dailies/today/  ──▶  DailyViewSet.today()   ──▶  Daily + DailySlot + Conditions
                          auto-creates if missing      (no answers exposed!)

GET /players/         ──▶  PlayerViewSet           ──▶  Player (876 records)
                          ?search=Faker               autocomplete endpoint

POST /submissions/    ──▶  AnswerCreateSerializer  ──▶  Submission + SubmissionAnswer
     answer/              validates player vs slot     validate_and_score_answer()
                          awards diamond (first)       cache SETNX for diamond lock
                          computes instant score       
                          
GET /dailies/{id}/    ──▶  ScoringViewSet           ──▶  AnswerStatsDaily
     answer-stats/        select_related (no N+1)      (computed by score_daily)
                          
score_daily()         ──▶  engine.score_daily()    ──▶  Update all SubmissionAnswer
     (nightly/manual)     count picks per slot         rarity_tier, rarity_percent
                          compute pick_percent         points_awarded
                          assign rarity tiers          Update Submission.total_points
```
