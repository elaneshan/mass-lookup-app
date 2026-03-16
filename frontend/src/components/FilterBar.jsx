export default function FilterBar({ value, onChange }) {
  return (
    <div className="flex items-center gap-2 flex-1">
      <div className="relative flex-1 max-w-md">
        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-600 text-[11px]
                         font-mono pointer-events-none">
          /
        </span>
        <input
          type="text"
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder="filter by name, formula, source, inchikey..."
          className="w-full bg-gray-900 border border-gray-700 rounded-lg
                     pl-7 pr-3 py-1.5 text-[12px] font-mono text-gray-300
                     placeholder-gray-700
                     focus:outline-none focus:border-cyan-500/50 focus:ring-1
                     focus:ring-cyan-500/20 transition-colors"
        />
      </div>
      {value && (
        <button
          onClick={() => onChange("")}
          className="text-[11px] text-gray-600 hover:text-gray-400 transition-colors font-mono"
        >
          clear
        </button>
      )}
    </div>
  )
}