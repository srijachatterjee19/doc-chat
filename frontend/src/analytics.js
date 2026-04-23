import ReactGA from 'react-ga4'

function getUserId() {
  let id = localStorage.getItem('analytics_uid')
  if (!id) {
    id = crypto.randomUUID()
    localStorage.setItem('analytics_uid', id)
  }
  return id
}

export function track(event, properties = {}) {
  const user_id = getUserId()

  // GA4
  ReactGA.event(event, { ...properties, user_id })

  // Backend
  fetch('/api/metrics/event', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ event, user_id, properties }),
  }).catch(() => {})
}
