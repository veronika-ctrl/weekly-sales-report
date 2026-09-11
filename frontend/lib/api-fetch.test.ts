import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import {
  API_FETCH_CREDENTIALS,
  describeApiFetchFailure,
  describeHttpError,
  isNetworkFetchErrorMessage,
  withApiCredentials,
} from './api-fetch'

describe('api-fetch credentials', () => {
  it('defaults fetch credentials to include so Basic Auth is sent', () => {
    assert.equal(API_FETCH_CREDENTIALS, 'include')
    const init = withApiCredentials({ method: 'GET' })
    assert.equal(init.credentials, 'include')
    assert.equal(init.method, 'GET')
  })

  it('lets an explicit credentials value override the default when spread last', () => {
    const init = withApiCredentials({ credentials: 'omit' })
    assert.equal(init.credentials, 'omit')
  })
})

describe('describeHttpError', () => {
  it('maps 401 to a readable auth hint instead of Failed to fetch', () => {
    const msg = describeHttpError(401, 'Authentication required')
    assert.match(msg, /401/)
    assert.match(msg, /site password/i)
    assert.doesNotMatch(msg, /Failed to fetch/)
  })

  it('maps 502/504 to gateway timeout copy', () => {
    const msg = describeHttpError(502, 'Bad Gateway')
    assert.match(msg, /502/)
    assert.match(msg, /timeout|unavailable/i)
  })

  it('strips HTML from 500 bodies', () => {
    const msg = describeHttpError(500, '<html><body>Internal Server Error</body></html>')
    assert.match(msg, /Internal Server Error/)
    assert.doesNotMatch(msg, /<html>/)
  })
})

describe('describeApiFetchFailure', () => {
  it('recognizes the browser TypeError Failed to fetch', () => {
    assert.equal(isNetworkFetchErrorMessage('Failed to fetch'), true)
    const msg = describeApiFetchFailure(new TypeError('Failed to fetch'), {
      endpoint: '/api/adjusted-amer',
    })
    assert.match(msg, /\/api\/adjusted-amer/)
    assert.match(msg, /site password|CORS|network/i)
    assert.match(msg, /do not need to re-upload/i)
  })

  it('keeps AbortError as a timeout', () => {
    const err = new Error('aborted')
    err.name = 'AbortError'
    const msg = describeApiFetchFailure(err, { timeoutMs: 180_000, endpoint: '/api/adjusted-amer' })
    assert.match(msg, /timed out after 180s/)
  })

  it('passes through already-mapped timeout text', () => {
    const msg = describeApiFetchFailure(new Error('Request timed out after 60s (http://127.0.0.1:8000).'))
    assert.match(msg, /Request timed out after 60s/)
  })
})
