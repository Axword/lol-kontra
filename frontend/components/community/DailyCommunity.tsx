'use client'
import { FormEvent, useState } from 'react'
import { Shield } from 'lucide-react'
import { GameState } from '@/lib/api'
import { usePrefs } from '@/lib/store'
import { SupportedTeam } from '@/lib/guest-profile'
import { communityImageUrl, useDailyCommunity, usePostCommunityComment } from '@/lib/community'
import { formatApiError } from '@/lib/errors'
import { formatPoints } from '@/lib/points'

function TeamBadge({ team }: { team: SupportedTeam }) {
  const [failed, setFailed] = useState(false)
  const dark = ['dk', 'g2', 'hle', 'tlaw', 'tsw'].includes(team.id)
  return failed ? <Shield size={18} aria-hidden="true" />
    // eslint-disable-next-line @next/next/no-img-element
    : <img src={team.logo_url} alt="" width={24} height={24} title={team.name}
      className="h-6 w-6 shrink-0 object-contain p-0.5" style={{ background: dark ? '#26312d' : '#f1f4f1' }} onError={() => setFailed(true)} />
}

export default function DailyCommunity({ dailyId, state }: { dailyId: number; state?: GameState }) {
  const locale = usePrefs((current) => current.locale)
  const token = usePrefs((current) => current.guestToken)
  const pl = locale === 'pl'
  const query = useDailyCommunity(dailyId, token)
  const post = usePostCommunityComment(dailyId, token)
  const [comment, setComment] = useState('')
  const [ranking, setRanking] = useState<'players' | 'teams'>('players')
  const data = query.data
  const author = data?.author || { name: 'Axword', url: 'https://x.com/AxwordLol', description: pl ? 'Autor wyzwania' : 'Challenge author' }
  const canComment = !!data && !!state?.is_over && !state.is_practice && data.can_comment !== false && !post.isSuccess
  const publish = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!canComment || !comment.trim() || post.isPending || !token) return
    post.mutate(comment, { onSuccess: () => setComment('') })
  }
  return <section aria-label={pl ? 'Społeczność planszy' : 'Board community'} className="grid items-start gap-6 pt-4 lg:grid-cols-[minmax(0,1fr)_280px]">
    <div className="min-w-0 border bg-white" style={{ borderColor: 'var(--line)' }}>
      <div className="border-b px-5 py-5" style={{ borderColor: 'var(--line)' }}>
        <h2 className="text-base font-semibold">{pl ? 'Komentarze' : 'Comments'}{data ? ` (${data.comments.length})` : ''}</h2>
      </div>
      {canComment && <form onSubmit={publish} className="space-y-3 border-b p-5" style={{ borderColor: 'var(--line)' }}>
        <label htmlFor={`comment-${dailyId}`} className="block text-sm font-semibold">{pl ? 'Twój komentarz' : 'Your comment'}</label>
        <textarea id={`comment-${dailyId}`} value={comment} rows={3} maxLength={500} disabled={post.isPending}
          onChange={(event) => { setComment(event.target.value); post.reset() }} className="field w-full resize-y"
          aria-invalid={post.isError || undefined} aria-describedby={post.isError ? `comment-error-${dailyId}` : undefined} />
        {post.isError && <p id={`comment-error-${dailyId}`} role="alert" className="text-sm" style={{ color: 'var(--bad)' }}>
          {formatApiError(post.error, pl ? 'Nie udało się dodać komentarza.' : 'Could not post your comment.')}
        </p>}
        <div className="flex justify-end"><button type="submit" className="btn btn-gold disabled:opacity-50" disabled={!token || !comment.trim() || post.isPending}>
          {post.isPending ? (pl ? 'Publikowanie…' : 'Posting…') : (pl ? 'Opublikuj ze składem' : 'Post with roster')}
        </button></div>
      </form>}
      {post.isSuccess && <p role="status" className="border-b p-5 text-sm" style={{ borderColor: 'var(--line)', color: 'var(--gold)' }}>{pl ? 'Komentarz opublikowany.' : 'Comment posted.'}</p>}
      {query.isLoading && <p role="status" className="p-5 text-sm" style={{ color: 'var(--text-faint)' }}>{pl ? 'Wczytywanie komentarzy…' : 'Loading comments…'}</p>}
      {query.isError && <div role="alert" className="space-y-2 p-5 text-sm" style={{ color: 'var(--bad)' }}>
        <p>{formatApiError(query.error, pl ? 'Nie udało się wczytać komentarzy.' : 'Could not load comments.')}</p>
        <button type="button" onClick={() => { void query.refetch() }} className="underline">{pl ? 'Spróbuj ponownie' : 'Try again'}</button>
      </div>}
      {data && data.comments.length === 0 && <p className="p-5 text-sm" style={{ color: 'var(--text-faint)' }}>{pl ? 'Brak komentarzy.' : 'No comments yet.'}</p>}
      {data && data.comments.length > 0 && <ol>
        {data.comments.map((entry) => {
          const image = data.can_view_solutions ? communityImageUrl(entry.roster_image_url) : null
          return <li key={entry.id} className="space-y-3 border-b p-5 last:border-b-0" style={{ borderColor: 'var(--line)' }}>
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
              {entry.team && <TeamBadge team={entry.team} />}
              <span className="min-w-0 break-words text-sm font-semibold">{entry.nickname}</span>
              <span className="text-xs tabular" style={{ color: 'var(--gold)' }}>{formatPoints(entry.score, locale)}</span>
              <time dateTime={entry.created_at} className="ml-auto text-[11px]" style={{ color: 'var(--text-faint)' }}>
                {new Date(entry.created_at).toLocaleString(pl ? 'pl-PL' : 'en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}
              </time>
            </div>
            {data.can_view_solutions ? <>
              {entry.text && <p className="whitespace-pre-wrap break-words text-sm leading-relaxed" style={{ color: 'var(--text-dim)' }}>{entry.text}</p>}
              {image && <a href={image} target="_blank" rel="noopener noreferrer" className="block w-fit max-w-full">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={image} alt={pl ? `Skład gracza ${entry.nickname}` : `${entry.nickname}'s roster`} width={720} height={500}
                  loading="lazy" className="h-auto max-h-[420px] w-auto max-w-full border object-contain" style={{ borderColor: 'var(--line)' }} />
              </a>}
            </> : <p className="border px-4 py-5 text-xs" style={{ borderColor: 'var(--line-soft)', color: 'var(--text-faint)' }}>
              {pl ? 'Ukończ planszę, aby zobaczyć komentarz i skład.' : 'Finish the board to see this comment and roster.'}
            </p>}
          </li>
        })}
      </ol>}
    </div>
    <aside className="min-w-0 space-y-5">
      <div className="flex items-start gap-3 border bg-white p-5" style={{ borderColor: 'var(--line)' }}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/authors/axword.png" alt="" width={40} height={40} className="h-10 w-10 shrink-0 object-cover" />
        <div className="min-w-0 space-y-1">
          <a href={author.url} target="_blank" rel="noopener noreferrer" className="text-sm font-semibold underline-offset-4 hover:underline" style={{ color: 'var(--gold)' }}>{author.name}</a>
          <p className="text-xs leading-relaxed" style={{ color: 'var(--text-faint)' }}>{author.description}</p>
        </div>
      </div>
      <div className="border bg-white" style={{ borderColor: 'var(--line)' }}>
        <div className="space-y-3 border-b p-5" style={{ borderColor: 'var(--line)' }}>
          <h2 className="text-base font-semibold">{pl ? 'Ranking planszy' : 'Board ranking'}</h2>
          <div role="tablist" aria-label={pl ? 'Rodzaj rankingu' : 'Ranking type'} className="flex border" style={{ borderColor: 'var(--line)' }}>
            {(['players', 'teams'] as const).map((value) => <button key={value} id={`ranking-${dailyId}-${value}`} type="button" role="tab" aria-selected={ranking === value}
              aria-controls={`ranking-panel-${dailyId}`} tabIndex={ranking === value ? 0 : -1}
              onClick={() => setRanking(value)} onKeyDown={(event) => {
                if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
                event.preventDefault()
                const next = event.key === 'Home' ? 'players' : event.key === 'End' ? 'teams' : value === 'players' ? 'teams' : 'players'
                setRanking(next)
                document.getElementById(`ranking-${dailyId}-${next}`)?.focus()
              }} className="min-h-9 flex-1 px-2 text-xs font-semibold"
              style={{ color: ranking === value ? '#fff' : 'var(--text-dim)', background: ranking === value ? 'var(--gold)' : '#fff' }}>
              {value === 'players' ? (pl ? 'Gracze' : 'Players') : (pl ? 'Drużyny' : 'Teams')}
            </button>)}
          </div>
        </div>
        {data && <div id={`ranking-panel-${dailyId}`} role="tabpanel" aria-labelledby={`ranking-${dailyId}-${ranking}`}>
          {ranking === 'players' ? <ol>{data.player_ranking.slice(0, 10).map((entry, index) => <li key={`${entry.nickname}-${index}`}
            className="flex items-center gap-2 border-b px-4 py-3 text-xs last:border-b-0" style={{ borderColor: 'var(--line-soft)' }}>
            <span className="w-4 shrink-0 tabular" style={{ color: 'var(--text-faint)' }}>{index + 1}</span>
            {entry.team && <TeamBadge team={entry.team} />}
            <span className="min-w-0 flex-1 break-words font-medium">{entry.nickname}</span>
            <span className="shrink-0 tabular" style={{ color: 'var(--gold)' }}>{formatPoints(entry.score, locale)}</span>
          </li>)}</ol> : <ol>{data.team_ranking.slice(0, 10).map((entry, index) => <li key={entry.team.id}
            className="flex items-center gap-2 border-b px-4 py-3 text-xs last:border-b-0" style={{ borderColor: 'var(--line-soft)' }}>
            <span className="w-4 shrink-0 tabular" style={{ color: 'var(--text-faint)' }}>{index + 1}</span>
            <TeamBadge team={entry.team} />
            <span className="min-w-0 flex-1"><span className="block font-medium">{entry.team.name}</span>
              <span style={{ color: 'var(--text-faint)' }}>{pl ? 'Gracze' : 'Players'}: {entry.players}</span></span>
            <span className="shrink-0 tabular" title={pl ? 'Średni wynik' : 'Average score'} style={{ color: 'var(--gold)' }}>{formatPoints(entry.average_score, locale)}</span>
          </li>)}</ol>}
          {(ranking === 'players' ? data.player_ranking : data.team_ranking).length === 0 && <p className="p-5 text-xs" style={{ color: 'var(--text-faint)' }}>{pl ? 'Brak wyników.' : 'No results yet.'}</p>}
        </div>}
      </div>
    </aside>
  </section>
}
