import assert from 'node:assert/strict'
import { describe, it, beforeEach } from 'node:test'
import {
  isUploadLockHeldByOther,
  releaseUploadLock,
  resetUploadLock,
  tryAcquireUploadLock,
} from './upload-lock'

describe('upload lock', () => {
  beforeEach(() => {
    resetUploadLock()
  })

  it('allows only one card at a time', () => {
    assert.equal(tryAcquireUploadLock('a'), true)
    assert.equal(tryAcquireUploadLock('b'), false)
    assert.equal(isUploadLockHeldByOther('b'), true)
    releaseUploadLock('a')
    assert.equal(tryAcquireUploadLock('b'), true)
  })

  it('is re-entrant for the holder', () => {
    assert.equal(tryAcquireUploadLock('a'), true)
    assert.equal(tryAcquireUploadLock('a'), true)
    releaseUploadLock('a')
    assert.equal(isUploadLockHeldByOther('b'), false)
  })
})
