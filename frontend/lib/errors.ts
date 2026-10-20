import axios from 'axios'
import type { Locale } from './locale'

const englishMessages: Record<string, string> = {
  'Nick musi być tekstem.': 'Your nickname must be text.',
  'Nick zawiera niedozwolone znaki.': 'Your nickname contains invalid characters.',
  'Nick musi mieć od 3 do 24 znaków.': 'Your nickname must be between 3 and 24 characters.',
  'Użyj liter, cyfr, spacji, myślnika lub podkreślenia.': 'Use letters, numbers, spaces, hyphens or underscores.',
  'Nick musi zawierać literę lub cyfrę.': 'Your nickname must contain a letter or number.',
  'Wybierz nick bez obraźliwych słów.': 'Choose a nickname without offensive language.',
  'Komentarz musi być tekstem.': 'Your comment must be text.',
  'Komentarz może mieć maksymalnie 500 znaków.': 'Your comment must be at most 500 characters.',
  'Komentarz zawiera niedozwolone znaki.': 'Your comment contains invalid characters.',
  'Napisz komentarz bez obraźliwych słów.': 'Write your comment without offensive language.',
  'Komentarz ze składem dodasz po zakończeniu własnej gry.': 'Finish your game before posting a comment with your roster.',
  'Nieprawidłowy identyfikator gościa.': 'Your profile access is invalid.',
  'Nie znaleziono profilu. Sprawdź, czy baza danych została już przeniesiona.': 'Profile not found. Check that its data has been transferred.',
  'Ta plansza nie jest dostępna': 'This board is not available.',
  'Dzisiejsza plansza nie jest jeszcze dostępna.': 'Today’s board is not available yet.',
  'Rozwiązania są dostępne po zakończeniu własnej gry.': 'Finish your game to view the answers.',
  'Nie znaleziono zawodnika': 'Player not found.',
  'Gra jest zakończona': 'The game has finished.',
  'Ten zawodnik jest już poprawnie wybrany na innej pozycji': 'You have already selected this player correctly for another position.',
  'Ten identyfikator rozgrywki nie jest dostępny': 'This game is not available.',
  'Każda pozycja wymaga innego zawodnika': 'Each position needs a different player.',
  'Już wysłałeś odpowiedź dla tego Daily': 'You have already submitted this board.',
}

export function formatApiError(error: unknown, fallback: string, locale: Locale = 'pl'): string {
  if (!axios.isAxiosError(error)) return fallback
  const message = (value: unknown): string | undefined => {
    if (typeof value === 'string') return value
    if (Array.isArray(value)) return value.map(message).filter(Boolean).join(' ') || undefined
    if (value && typeof value === 'object') {
      const fields = value as Record<string, unknown>
      return message(fields.detail) || message(fields.non_field_errors) ||
        Object.values(fields).map(message).filter(Boolean).join(' ') || undefined
    }
  }
  const raw = message(error.response?.data)
  if (!raw) return fallback
  // The API's custom validation messages are Polish. An unknown server message
  // uses the translated action-specific fallback instead of leaking that copy.
  return locale === 'en' ? englishMessages[raw] || fallback : raw
}

/** Missing boards should not wait through automatic network retries. */
export function retryApiQuery(failureCount: number, error: unknown) {
  if (axios.isAxiosError(error) && error.response && error.response.status < 500 && error.response.status !== 429) return false
  return failureCount < 2
}
