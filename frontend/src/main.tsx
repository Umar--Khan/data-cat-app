import '@/index.css'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App } from '@/app/app'
import { ErrorBoundary } from '@/app/error-boundary'
import { Providers } from '@/app/providers'

const root = document.getElementById('root')
if (!root) throw new Error('index.html has no #root element')

// The boundary sits outside the providers, so a failure inside them gets the fallback too.
createRoot(root).render(
  <StrictMode>
    <ErrorBoundary>
      <Providers>
        <App />
      </Providers>
    </ErrorBoundary>
  </StrictMode>,
)
