import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { shouldUseWwwAuthenticateChallenge } from './site-basic-auth'

describe('shouldUseWwwAuthenticateChallenge', () => {
  it('keeps the browser login dialog for document navigations', () => {
    assert.equal(
      shouldUseWwwAuthenticateChallenge({
        pathname: '/adjusted-amer',
        secFetchDest: 'document',
        accept: 'text/html',
      }),
      true
    )
  })

  it('omits WWW-Authenticate for /api so fetch can read 401 JSON', () => {
    assert.equal(
      shouldUseWwwAuthenticateChallenge({
        pathname: '/api/adjusted-amer',
        secFetchDest: 'empty',
        accept: '*/*',
      }),
      false
    )
    assert.equal(
      shouldUseWwwAuthenticateChallenge({
        pathname: '/api/upload-file',
        secFetchDest: 'empty',
        accept: '*/*',
      }),
      false
    )
  })

  it('omits WWW-Authenticate for cors/empty fetch to pages', () => {
    assert.equal(
      shouldUseWwwAuthenticateChallenge({
        pathname: '/adjusted-amer',
        secFetchDest: 'empty',
        accept: 'application/json',
      }),
      false
    )
  })
})
