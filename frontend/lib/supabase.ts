import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
const disableSupabase = process.env.NEXT_PUBLIC_DISABLE_SUPABASE === 'true'

// Create Supabase client if environment variables are available
// Otherwise, export null so the app can gracefully handle missing Supabase config
// Wrap in try-catch to handle invalid URLs gracefully
let supabase: ReturnType<typeof createClient> | null = null
let supabaseAvailable = false

try {
  if (disableSupabase) {
    console.warn('Supabase disabled via NEXT_PUBLIC_DISABLE_SUPABASE')
    supabase = null
    supabaseAvailable = false
  } else if (supabaseUrl && supabaseAnonKey) {
    // Validate URL format before creating client
    try {
      const url = new URL(supabaseUrl)
      // Only create client if URL looks valid
      if (url.protocol === 'https:' && url.hostname.includes('supabase.co')) {
        supabase = createClient(supabaseUrl, supabaseAnonKey, {
          // Disable realtime to avoid unnecessary network connections
          realtime: {
            params: {
              eventsPerSecond: 0
            }
          }
        })
        supabaseAvailable = true
        console.log('✅ Supabase client initialized successfully')
      } else {
        console.warn('Invalid Supabase URL format, Supabase features will be disabled')
        supabase = null
        supabaseAvailable = false
      }
    } catch (urlError) {
      console.warn('Invalid Supabase URL format, Supabase features will be disabled:', urlError)
      supabase = null
      supabaseAvailable = false
    }
  }
} catch (error) {
  console.warn('Failed to initialize Supabase client, Supabase features will be disabled:', error)
  supabase = null
  supabaseAvailable = false
}

// Export a function to check if Supabase is available
export function isSupabaseAvailable(): boolean {
  if (disableSupabase) return false
  return supabaseAvailable && supabase !== null
}

export { supabase }
