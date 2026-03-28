import { redirect } from 'next/navigation'

/** Immediate server redirect so `/` always resolves (avoids empty client page → 404 in dev). */
export default function Home() {
  redirect('/summary')
}
