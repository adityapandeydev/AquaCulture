export default function Button({ children, onClick, loading }: any) {
  return (
    <button
      onClick={onClick}
      disabled={loading}
      className="
        px-5 py-2.5 
        rounded-lg 
        bg-teal-500 
        text-white 
        font-medium
        shadow-md
        hover:bg-teal-400 
        hover:shadow-lg
        active:scale-95
        transition-all duration-150
        disabled:opacity-50
      "
    >
      {loading ? "Loading..." : children}
    </button>
  )
}