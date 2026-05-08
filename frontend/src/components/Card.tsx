import type { ReactNode } from "react"

interface CardProps {
  children: ReactNode
}

export default function Card({ children }: CardProps) {
  return (
    <div className="bg-card p-4 rounded-xl border border-border shadow-sm">
      {children}
    </div>
  )
}