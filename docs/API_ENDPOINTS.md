# API v1 – OpenAPI summary

Base: `/api/v1/`

## Auth
- POST /auth/register/
- POST /auth/login/
- POST /auth/google/
- POST /auth/discord/
- GET /auth/me/
- POST /auth/refresh/
- POST /auth/logout/

## Players
- GET /players/?search=&role=&region=&residency=&team=&worlds_min=&active=
- GET /players/{slug}/
- GET /players/autocomplete/?q=

## Dailies
- GET /dailies/today/
- GET /dailies/{id}/
- GET /dailies/{id}/slots/
- GET /dailies/archive/?page=

## Submissions
- POST /submissions/
- GET /submissions/me/?daily_id=
- GET /submissions/{id}/result/

## Scoring / Stats
- GET /dailies/{id}/answer-stats/
- GET /leaderboard/?daily_id=&type=daily|all_time|streak
- GET /users/me/stats/

## Admin (IsStaff)
- POST /admin/dailies/
- PUT /admin/dailies/{id}/
- POST /admin/dailies/{id}/publish
- POST /admin/dailies/{id}/close
- POST /admin/dailies/{id}/rescore
- GET /admin/answer-candidates/?conditions_json=
- GET /admin/scoring-config/
- PUT /admin/scoring-config/
- POST /admin/players/
- PATCH /admin/players/{id}/
- GET /admin/stats/overview/
- POST /admin/diamond-picks/{answer_id}/revoke

Wszystkie request/response – JSON. 
Autoryzacja: Bearer JWT lub Session Cookie.
Rate limit headers: X-RateLimit-Remaining
