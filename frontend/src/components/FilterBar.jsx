export default function FilterBar({ value, onChange }) {
  return (
    <div className="flex items-center gap-2 flex-1">
      <label className="text-xs text-slate-500 whitespace-nowrap">Filter results:</label>
      <input
        type="text"
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder="Filter by name, formula, source, InChIKey..."
        className="flex-1 max-w-md rounded border border-slate-300 px-3 py-1.5 text-sm
                   focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
      {value && (
        <button
          onClick={() => onChange("")}
          className="text-xs text-slate-400 hover:text-slate-600"
        >
          Clear
        </button>
      )}
    </div>
  )
}