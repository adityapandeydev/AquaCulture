import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClientProvider } from '@tanstack/react-query'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import './styles/base.css'
import './styles/layout.css'
import './styles/motion.css'
import { meQuery, queryClient } from './api/queries'
import { installRipples, watchTransitions } from './lib/motion'
import { Broken, Missing } from './ui/errors'
import { Shell } from './ui/shell'
import { Toasts } from './ui/toast'

// Ask for the session and the first page together, behind the boot screen.
void queryClient.prefetchQuery(meQuery)
installRipples()
watchTransitions()

const router = createBrowserRouter([
  { path: '/sign-in', hydrateFallbackElement: <></>, lazy: () => import('./pages/signin'), errorElement: <Broken /> },
  {
    path: '/', element: <Shell />, errorElement: <Broken />, hydrateFallbackElement: <></>,
    children: [
      { index: true, lazy: () => import('./pages/ponds') },
      { path: 'alerts', lazy: () => import('./pages/alerts') },
      { path: 'model', lazy: () => import('./pages/model') },
      { path: 'ponds/new', lazy: () => import('./pages/newpond') },
      {
        path: 'ponds/:id', lazy: () => import('./pages/pond'),
        children: [
          { index: true, lazy: () => import('./pages/now') },
          { path: 'data', lazy: () => import('./pages/data') },
          { path: 'devices', lazy: () => import('./pages/devices') },
          { path: 'accuracy', lazy: () => import('./pages/accuracy') },
          { path: 'settings', lazy: () => import('./pages/settings') },
        ],
      },
      { path: '*', element: <Missing /> },
    ],
  },
])

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
      <Toasts />
    </QueryClientProvider>
  </StrictMode>,
)
