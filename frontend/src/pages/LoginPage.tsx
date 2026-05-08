import { useState } from "react"
import { login, register } from "../api/auth"
import { useNavigate } from "react-router-dom"
import { setToken } from "../utils/auth"

export default function LoginPage() {
  const [name, setName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [registerMode, setRegisterMode] = useState(false)
  const navigate = useNavigate()

  const handleAuth = async () => {
    setLoading(true)
    setError("")

    try {
      if (registerMode) {
        await register(name || "Farmer", email, password)
      }

      const res = await login(email, password)
      if (!res.access_token) {
        setError("No access token returned from server.")
        return
      }

      setToken(res.access_token)
      navigate("/dashboard")
    } catch (err: unknown) {
      if (err && typeof err === "object" && "response" in err) {
        const apiError = err as { response?: { data?: { detail?: string } } }
        setError(apiError.response?.data?.detail || "Authentication failed")
      } else {
        setError("Authentication failed")
      }
    } finally {
      setLoading(false)
    }
  }


  return (
    <div className="min-h-screen grid place-items-center px-4">
      <div className="w-full max-w-md bg-surface p-8 rounded-2xl border border-border shadow-xl">
        <h1 className="text-2xl mb-2 font-bold">AquaTech</h1>
        <p className="text-muted mb-6">
          {registerMode ? "Create your account to manage ponds." : "Login to access your pond dashboard."}
        </p>

        {registerMode && (
          <input
            className="w-full p-3 mb-4 bg-bg border border-border rounded-lg"
            placeholder="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        )}

        <input
          className="w-full p-3 mb-4 bg-bg border border-border rounded-lg"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />

        <input
          type="password"
          className="w-full p-3 mb-4 bg-bg border border-border rounded-lg"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />

        {error && <p className="text-danger text-sm mb-3">{error}</p>}

        <button
          onClick={handleAuth}
          disabled={loading}
          className="w-full bg-primary hover:bg-primary-hover p-3 rounded-lg disabled:opacity-50"
        >
          {loading ? "Please wait..." : registerMode ? "Register & Login" : "Login"}
        </button>

        <button
          onClick={() => setRegisterMode((prev) => !prev)}
          className="w-full mt-3 text-sm text-muted hover:text-text"
        >
          {registerMode ? "Already have an account? Login" : "No account? Register"}
        </button>
      </div>
    </div>
  )
}