export default function Card({ children }: any) {
  return (
    <div className="bg-card p-4 rounded-xl border border-border shadow-sm">
      {children}
    </div>
  )
}