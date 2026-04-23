import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import ReactGA from 'react-ga4'
import './tailwind.css'
import './App.css'
import App from './App.jsx'

ReactGA.initialize(import.meta.env.VITE_GA_MEASUREMENT_ID)
ReactGA.send('pageview')

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
)
