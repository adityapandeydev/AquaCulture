import type { ReactNode } from "react"

interface ButtonProps {
  children: ReactNode
  onClick: () => void
  loading?: boolean
  variant?: "primary" | "secondary" | "danger"
}

export default function Button({ children, onClick, loading, variant = "primary" }: ButtonProps) {
  const variantClasses =
    variant === "secondary"
      ? "bg-slate-700 hover:bg-slate-600"
      : variant === "danger"
      ? "bg-rose-600 hover:bg-rose-500"
      : "bg-teal-500 hover:bg-teal-400"

  return (
    <button
      onClick={onClick}
      disabled={loading}
      className={`px-5 py-2.5 rounded-lg text-white font-medium shadow-md hover:shadow-lg active:scale-95 transition-all duration-150 disabled:opacity-50 disabled:cursor-not-allowed ${variantClasses}`}
    >
      {loading ? "Loading..." : children}
    </button>
  )
}