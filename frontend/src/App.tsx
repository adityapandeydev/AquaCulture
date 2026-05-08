import { Navigate, Route, Routes } from "react-router-dom"
import type { ReactElement } from "react"
import LoginPage from "./pages/LoginPage"
import Dashboard from "./pages/Dashboard"
import { isAuthenticated } from "./utils/auth"

function ProtectedRoute({ children }: { children: ReactElement }) {
  if (!isAuthenticated()) {
    return <Navigate to="/" replace />
  }
  return children
}

function App() {
  return (
    <div className="min-h-screen bg-bg text-text">
      <Routes>
        <Route path="/" element={<LoginPage />} />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          }
        />
      </Routes>
    </div>
  )
}

export default App