/** Fired after a Settings upload so the week bar re-reads qlik_weeks. */
export const UPLOAD_WEEKS_CHANGED_EVENT = 'weekly-report-uploads-changed'

export function notifyUploadWeeksChanged(): void {
  if (typeof window === 'undefined') return
  window.dispatchEvent(new Event(UPLOAD_WEEKS_CHANGED_EVENT))
}
