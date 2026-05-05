import { useState } from "react"
import { login } from "../api/auth"
import { useNavigate } from "react-router-dom"

export default function LoginPage() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const navigate = useNavigate()

  const handleLogin = async () => {
  try {
    const res = await login(email, password)

    console.log("FULL RESPONSE:", res)

    if (!res.access_token) {
      console.error("No token received", res)
      alert("Login failed: No token")
      return
    }

    localStorage.setItem("token", res.access_token)

    navigate("/dashboard")
  } catch (err: any) {
    console.error("ERROR:", err)
    console.error("DATA:", err.response?.data)

    alert("Login failed")
  }
}


  return (
    <div className="flex items-center justify-center h-screen">
      <div className="bg-surface p-8 rounded-2xl w-96 shadow-lg">
        <h1 className="text-2xl mb-6 font-bold">AquaTech Login</h1>

        <input
          className="w-full p-3 mb-4 bg-background border border-primary/20 rounded-lg"
          placeholder="Email"
          onChange={(e) => setEmail(e.target.value)}
        />

        <input
          type="password"
          className="w-full p-3 mb-4 bg-background border border-primary/20 rounded-lg"
          placeholder="Password"
          onChange={(e) => setPassword(e.target.value)}
        />

        <button
          onClick={handleLogin}
          className="w-full bg-primary hover:bg-primaryLight p-3 rounded-lg"
        >
          Login
        </button>
      </div>
    </div>
  )
}