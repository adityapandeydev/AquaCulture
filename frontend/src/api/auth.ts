import API from "./client"

export const login = async (email: string, password: string) => {
  const formData = new URLSearchParams()
  formData.append("username", email)
  formData.append("password", password)

  const res = await API.post("/auth/login", formData.toString(), {
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
  })

  return res.data
}