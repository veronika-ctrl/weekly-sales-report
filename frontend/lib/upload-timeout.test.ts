import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import {
  SMALL_HOSTED_UPLOAD_TIMEOUT_MS,
  computeUploadTimeoutMs,
  formatOtherCardUploadingError,
  formatSkippedAfterTimeoutError,
  formatUploadFileSize,
  formatUploadTimeoutError,
  isRemoteApiUrl,
  shouldAbortRemainingUploads,
} from './upload-timeout'

describe('isRemoteApiUrl', () => {
  it('treats Render as remote and loopback as local', () => {
    assert.equal(isRemoteApiUrl('https://weekly-sales-report.onrender.com'), true)
    assert.equal(isRemoteApiUrl('http://127.0.0.1:8000'), false)
    assert.equal(isRemoteApiUrl('http://localhost:8000'), false)
    assert.equal(isRemoteApiUrl(''), false)
    assert.equal(isRemoteApiUrl('same-origin'), false)
  })
})

describe('formatUploadFileSize', () => {
  it('does not round tiny CSVs to 0.0 MB', () => {
    assert.equal(formatUploadFileSize(0), '0 B')
    assert.match(formatUploadFileSize(20 * 1024), /KB/)
    assert.equal(formatUploadFileSize(0.4 * 1024 * 1024), '0.4 MB')
    assert.equal(formatUploadFileSize(3.9 * 1024 * 1024), '3.9 MB')
  })
})

describe('computeUploadTimeoutMs', () => {
  it('fails small hosted files in 90s instead of 5 minutes', () => {
    assert.equal(computeUploadTimeoutMs(0, { remoteApi: true }), SMALL_HOSTED_UPLOAD_TIMEOUT_MS)
    assert.equal(computeUploadTimeoutMs(12_000, { remoteApi: true }), SMALL_HOSTED_UPLOAD_TIMEOUT_MS)
    assert.equal(computeUploadTimeoutMs(0.4 * 1024 * 1024, { remoteApi: true }), SMALL_HOSTED_UPLOAD_TIMEOUT_MS)
    assert.equal(computeUploadTimeoutMs(3.9 * 1024 * 1024, { remoteApi: true }), SMALL_HOSTED_UPLOAD_TIMEOUT_MS)
  })

  it('keeps a long window for large Qlik transfers', () => {
    const qlik = computeUploadTimeoutMs(91 * 1024 * 1024, { remoteApi: true })
    assert.ok(qlik >= 5 * 60 * 1000)
    assert.ok(qlik <= 15 * 60 * 1000)
  })

  it('uses 5 minutes locally for small files', () => {
    assert.equal(computeUploadTimeoutMs(12_000, { remoteApi: false }), 5 * 60 * 1000)
  })
})

describe('upload error copy', () => {
  it('tells the user to try one file at a time after a hosted timeout', () => {
    const msg = formatUploadTimeoutError({
      fileName: 'Klaviyo_email_performance_last12m.csv',
      bytes: 0,
      timeoutMs: SMALL_HOSTED_UPLOAD_TIMEOUT_MS,
      remoteApi: true,
    })
    assert.match(msg, /Klaviyo_email_performance_last12m\.csv/)
    assert.match(msg, /0 B/)
    assert.match(msg, /90 seconds/)
    assert.match(msg, /one file at a time/i)
    assert.doesNotMatch(msg, /0\.0 MB/)
  })

  it('skips the rest of a stuck batch with a one-at-a-time hint', () => {
    const msg = formatSkippedAfterTimeoutError('Revenue_by_channel_2026-08.csv')
    assert.match(msg, /Revenue_by_channel_2026-08\.csv/)
    assert.match(msg, /one small file/)
    assert.match(msg, /Current Files/)
  })

  it('blocks a second Settings card while another upload is running', () => {
    assert.match(formatOtherCardUploadingError(), /already uploading/i)
  })
})

describe('shouldAbortRemainingUploads', () => {
  it('stops the batch on timeout or dropped connection, not on a validation error', () => {
    assert.equal(
      shouldAbortRemainingUploads(
        'Upload timeout: "x.csv" (12.0 KB) did not finish within 90 seconds. Render may still be processing'
      ),
      true
    )
    assert.equal(shouldAbortRemainingUploads('Network error: API unreachable at https://example'), true)
    assert.equal(shouldAbortRemainingUploads('Qlik file must be .xlsx or .csv'), false)
  })
})
