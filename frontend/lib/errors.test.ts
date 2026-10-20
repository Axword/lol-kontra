import { describe, expect, it } from 'vitest'
import { formatApiError } from './errors'

const apiError = (data: unknown) => ({ isAxiosError: true, response: { data } })

describe('translated API errors', () => {
  it('explains nickname validation in the selected language', () => {
    const error = apiError({ nickname: ['Nick musi mieć od 3 do 24 znaków.'] })
    expect(formatApiError(error, 'Could not save.', 'en')).toBe('Your nickname must be between 3 and 24 characters.')
    expect(formatApiError(error, 'Nie udało się zapisać.', 'pl')).toBe('Nick musi mieć od 3 do 24 znaków.')
  })
  it('translates comment moderation and duplicate-player errors', () => {
    expect(formatApiError(apiError({ comment: ['Napisz komentarz bez obraźliwych słów.'] }), 'Failed.', 'en'))
      .toBe('Write your comment without offensive language.')
    expect(formatApiError(apiError({ detail: 'Ten zawodnik jest już poprawnie wybrany na innej pozycji', code: 'duplicate_player' }), 'Failed.', 'en'))
      .toBe('You have already selected this player correctly for another position.')
  })
  it('uses the translated action fallback for unknown and network errors', () => {
    expect(formatApiError(apiError({ detail: 'Nowy komunikat po polsku' }), 'Could not load comments.', 'en')).toBe('Could not load comments.')
    expect(formatApiError(new Error('Network error'), 'Try again.', 'en')).toBe('Try again.')
  })
})
