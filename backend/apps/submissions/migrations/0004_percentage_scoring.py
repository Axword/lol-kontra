from collections import Counter

from django.db import migrations, models


def convert_scores(apps, schema_editor):
    """Keep all game/answer IDs while converting the old points and mode flags."""
    Submission = apps.get_model('submissions', 'Submission')
    Answer = apps.get_model('submissions', 'SubmissionAnswer')
    Slot = apps.get_model('dailies', 'DailySlot')
    Stats = apps.get_model('scoring', 'AnswerStatsDaily')
    UserStats = apps.get_model('users', 'UserStats')
    alias = schema_editor.connection.alias

    # Old official and practice games could share an identity. Keep the official
    # game canonical; preserve colliding practice games and their answers intact
    # under their existing legacy flag. Unambiguous archive games become official.
    for game in Submission.objects.using(alias).filter(is_practice=True).order_by('pk'):
        identity = {'user_id': game.user_id} if game.user_id else {'user__isnull': True, 'guest_token': game.guest_token}
        if not Submission.objects.using(alias).filter(daily_id=game.daily_id, is_practice=False, **identity).exists():
            Submission.objects.using(alias).filter(pk=game.pk).update(is_practice=False)

    Answer.objects.using(alias).all().update(is_diamond_pick=False, diamond_awarded_at=None)
    totals, counts = {}, {}
    for slot in Slot.objects.using(alias).all().iterator():
        population = Counter(Answer.objects.using(alias).filter(
            daily_slot_id=slot.pk, is_correct=True, submission__is_practice=False,
        ).values_list('player_id', flat=True))
        total = sum(population.values())
        totals[slot.pk], counts[slot.pk] = total, population
        Stats.objects.using(alias).filter(daily_slot_id=slot.pk).delete()
        for player_id, count in population.items():
            percent = count / total * 100.0
            tier = 'common' if percent > 20 else 'rare' if percent > 10 else 'epic' if percent > 1 else 'legendary'
            Stats.objects.using(alias).create(daily_slot_id=slot.pk, player_id=player_id,
                pick_count=count, pick_percent=percent, rarity_tier=tier, is_correct=True)

    for answer in Answer.objects.using(alias).all().iterator():
        total = totals.get(answer.daily_slot_id, 0) if answer.is_correct else 0
        count = counts.get(answer.daily_slot_id, {}).get(answer.player_id, 0) if answer.is_correct else 0
        percent = count / total * 100.0 if total else 0.0
        tier = 'common' if percent > 20 else 'rare' if percent > 10 else 'epic' if percent > 1 else 'legendary'
        Answer.objects.using(alias).filter(pk=answer.pk).update(
            points_awarded=-percent if answer.is_correct else 0.0,
            rarity_percent=percent if answer.is_correct else None,
            rarity_tier=tier if answer.is_correct else None,
            scoring_pick_count=count, scoring_sample_size=total,
        )

    user_games = {}
    for game in Submission.objects.using(alias).all().iterator():
        answers = list(Answer.objects.using(alias).filter(submission_id=game.pk, is_correct=True))
        slot_count = Slot.objects.using(alias).filter(daily_id=game.daily_id).count()
        finished = game.is_scored or game.errors_used >= 10 or (slot_count > 0 and len(answers) >= slot_count)
        missing = max(0, slot_count - len(answers)) if finished else 0
        score = round(max(0.0, min(500.0, 500.0 + sum(a.points_awarded for a in answers) - missing * 100)), 6)
        Submission.objects.using(alias).filter(pk=game.pk).update(total_points=score)
        if game.user_id and finished and not game.is_practice and not game.is_seed:
            user_games.setdefault(game.user_id, []).append((score, answers))
    for stats in UserStats.objects.using(alias).all().iterator():
        games = user_games.get(stats.user_id, [])
        total = sum(score for score, _ in games)
        UserStats.objects.using(alias).filter(pk=stats.pk).update(
            games_played=len(games), total_points=total, avg_points=total / len(games) if games else 0,
            best_score=max((score for score, _ in games), default=0), diamond_picks=0,
            legendary_answers=sum(a.rarity_tier == 'legendary' for _, answers in games for a in answers),
        )


class Migration(migrations.Migration):
    dependencies = [
        ('submissions', '0003_archive_practice'),
        ('scoring', '0002_percentage_scoring'),
        ('users', '0002_preserve_fractional_scores'),
    ]

    operations = [
        migrations.AddField(model_name='submission', name='is_seed', field=models.BooleanField(default=False)),
        migrations.AlterField(model_name='submission', name='total_points', field=models.FloatField(default=500.0)),
        migrations.AddField(model_name='submissionanswer', name='scoring_pick_count', field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name='submissionanswer', name='scoring_sample_size', field=models.PositiveIntegerField(default=0)),
        migrations.RunPython(convert_scores, migrations.RunPython.noop),
    ]
