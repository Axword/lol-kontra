"""One best run per guest and period, using Warsaw calendar boundaries."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from django.db.models import F, Q, Window
from django.db.models.functions import Coalesce, RowNumber
from django.utils import timezone
from .models import InfinityRun

PERIODS=('daily','weekly','monthly','all_time')
WARSAW=ZoneInfo('Europe/Warsaw')


def bounds(period,at=None):
    today=(at or timezone.now()).astimezone(WARSAW).date()
    if period=='all_time':return None,None
    if period=='daily':start,end=today,today+timedelta(days=1)
    elif period=='weekly':
        start=today-timedelta(days=today.weekday());end=start+timedelta(days=7)
    else:
        start=today.replace(day=1)
        end=(start.replace(day=28)+timedelta(days=4)).replace(day=1)
    return (datetime.combine(day,datetime.min.time(),WARSAW) for day in (start,end))


def leaders(period='all_time',at=None):
    rows=InfinityRun.objects.filter(Q(correct_count__gt=0)|Q(finished_at__isnull=False)).annotate(
        rank_at=Coalesce('finished_at','updated_at'))
    start,end=bounds(period,at)
    if start:rows=rows.filter(rank_at__gte=start,rank_at__lt=end)
    return rows.annotate(personal_position=Window(expression=RowNumber(),partition_by=F('guest_profile_id'),
        order_by=[F('correct_count').desc(),F('errors_used').asc(),F('updated_at').asc(),F('id').asc()])
    ).filter(personal_position=1).order_by('-correct_count','errors_used','updated_at','id')


def snapshot(profile_id,at=None):
    result={}
    at=at or timezone.now()
    for period in PERIODS:
        rows=leaders(period,at)
        own=rows.filter(guest_profile_id=profile_id).first()
        rank=None
        if own:
            earlier=(Q(correct_count__gt=own.correct_count)
                |Q(correct_count=own.correct_count,errors_used__lt=own.errors_used)
                |Q(correct_count=own.correct_count,errors_used=own.errors_used,updated_at__lt=own.updated_at)
                |Q(correct_count=own.correct_count,errors_used=own.errors_used,updated_at=own.updated_at,id__lt=own.id))
            rank=rows.filter(earlier).count()+1
        start,_=bounds(period,at)
        result[period]={'rank':rank,'best':own.correct_count if own else 0,'total_players':rows.count(),
                        'window_start':start.isoformat() if start else None}
    return result


def finished_result(run):
    after=snapshot(run.guest_profile_id,run.finished_at)
    before=run.ranking_before.get('ranks',{})
    repeat=run.ranking_before.get('completed_runs',0)>0
    for period,row in after.items():
        old=before.get(period,{})
        previous=old.get('rank') if repeat and old.get('window_start')==row['window_start'] else None
        row.update(previous_rank=previous,improved=bool(previous is not None and row['rank'] is not None
            and row['rank']<previous and run.correct_count>old.get('best',0)))
    return {'periods':after}
