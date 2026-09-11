/**
 * Process-wide lock so two Settings cards cannot POST to Render at once.
 * Each BatchFileUpload instance holds the lock for its whole sequential batch.
 */

let holderId: string | null = null

export function tryAcquireUploadLock(id: string): boolean {
  if (holderId && holderId !== id) return false
  holderId = id
  return true
}

export function releaseUploadLock(id: string): void {
  if (holderId === id) holderId = null
}

export function isUploadLockHeldByOther(id: string): boolean {
  return holderId != null && holderId !== id
}

/** Test helper. */
export function resetUploadLock(): void {
  holderId = null
}
