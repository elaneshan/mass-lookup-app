import { useState } from "react"

const SOURCE_URLS = {
  HMDB:      id => `https://hmdb.ca/metabolites/${id}`,
  ChEBI:     id => `https://www.ebi.ac.uk/chebi/searchId.do?chebiId=${id}`,
  LipidMaps: id => `https://www.lipidmaps.org/databases/lmsd/${id}`,
  NPAtlas:   id => `https://www.npatlas.org/explore/compounds/${id}`,
}

const SOURCE_BADGE = {
  HMDB:      "bg-blue-500/15 text-blue-400 border border-blue-500/25",
  ChEBI:     "bg-emerald-500/15 text-emerald-400 border border-emerald-500/25",
  LipidMaps: "bg-orange-500/15 text-orange-400 border border-orange-500/25",
  NPAtlas:   "bg-purple-500/15 text-purple-400 border border-purple-500/25",
  FooDB:     "bg-yellow-500/15 text-yellow-400 border border-yellow-500/25",
  "MS-DIAL": "bg-pink-500/15 text-pink-400 border border-pink-500/25",
  PubChem:   "bg-gray-500/15 text-gray-400 border border-gray-500/25",
}

function groupResults(results) {
  // Group by InChIKey if available, else by formula+name as fallback key
  const groups = new Map()

  for (const r of results) {
    // Group by InChIKey layer 1 (first 14 chars = molecular skeleton)
    // This collapses stereoisomers, salts, and alternative names of the same compound
    const key = r.inchikey && r.inchikey !== 'None' && r.inchikey.includes('-')
      ? r.inchikey.split('-')[0]
      : `${r.formula || ''}__${r.name || ''}`

    if (!groups.has(key)) {
      groups.set(key, [])
    }
    groups.get(key).push(r)
  }

  return Array.from(groups.values())
}

function ppmColor(ppm) {
  if (ppm == null) return "text-gray-500"
  const val = Math.abs(ppm)
  if (val < 2) return "text-emerald-400"
  if (val < 5) return "text-yellow-400"
  return "text-red-400"
}

export default function ResultsTable({ queryResults, filterTerm }) {
  const [expandedGroups, setExpandedGroups] = useState(new Set())
  const [copiedCol, setCopiedCol]           = useState(null)

  const term = filterTerm.toLowerCase()

  function matches(r) {
    if (!term) return true
    return [r.name, r.formula, r.source, r.inchikey, r.source_id]
      .some(v => v?.toLowerCase().includes(term))
  }

  function toggleGroup(key) {
    setExpandedGroups(prev => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })
  }

  function allVisible() {
    return queryResults.flatMap(q => q.results.filter(matches))
  }

  function copyColumn(col) {
    const values = allVisible().map(r => {
      if (col === 'name')     return r.name || ''
      if (col === 'formula')  return r.formula || ''
      if (col === 'inchikey') return r.inchikey || ''
      if (col === 'mass')     return r.exact_mass != null ? Number(r.exact_mass).toFixed(5) : ''
      return ''
    }).filter(Boolean)
    navigator.clipboard.writeText(values.join('\n'))
    setCopiedCol(col)
    setTimeout(() => setCopiedCol(null), 1500)
  }

  function exportCSV() {
    const rows = [
      ["Query", "Adduct", "Name", "Formula", "Exact Mass", "Error (Da)",
       "Error (ppm)", "Source", "Source ID", "URL", "InChIKey", "PubChem"]
    ]
    for (const q of queryResults) {
      for (const r of q.results.filter(matches)) {
        const url     = SOURCE_URLS[r.source]?.(r.source_id) || ''
        const pubchem = r.inchikey
          ? `https://pubchem.ncbi.nlm.nih.gov/#query=${r.inchikey}` : ''
        rows.push([
          q.query_mass, q.adduct, r.name, r.formula, r.exact_mass,
          r.mass_error, r.ppm_error, r.source, r.source_id,
          url, r.inchikey, pubchem
        ])
      }
    }
    const csv  = rows.map(r => r.map(v => `"${v ?? ""}"`).join(",")).join("\n")
    const blob = new Blob([csv], { type: "text/csv" })
    const a    = document.createElement("a")
    a.href     = URL.createObjectURL(blob)
    a.download = "lucid_results.csv"
    a.click()
  }

  const copyableCols = [
    { key: 'name',     label: 'Name' },
    { key: 'formula',  label: 'Formula' },
    { key: 'mass',     label: 'Mass' },
    { key: 'inchikey', label: 'InChIKey' },
  ]

  return (
    <div className="panel rounded-xl overflow-hidden flex flex-col gap-2">

      {/* Toolbar */}
      <div className="flex items-center gap-3 px-1 pt-1 flex-wrap">
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] text-gray-600 uppercase tracking-widest mr-1">
            Copy column:
          </span>
          {copyableCols.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => copyColumn(key)}
              className={`text-[11px] px-2 py-1 rounded border transition-colors font-mono
                ${copiedCol === key
                  ? "border-cyan-500/60 text-cyan-400 bg-cyan-500/10"
                  : "border-gray-700 text-gray-500 hover:text-cyan-400 hover:border-cyan-500/40 bg-gray-900"}`}
            >
              {copiedCol === key ? "✓ Copied" : label}
            </button>
          ))}
        </div>
        <button
          onClick={exportCSV}
          className="ml-auto text-[11px] px-3 py-1 rounded border border-gray-700
                     text-gray-500 hover:text-cyan-400 hover:border-cyan-500/40
                     transition-colors bg-gray-900 font-mono"
        >
          Export CSV ↓
        </button>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">

          <thead className="sticky top-0 bg-[#131C26] border-b border-gray-800 z-10">
            <tr className="text-[10px] uppercase tracking-wider text-gray-400">
              <th className="px-3 py-2 text-left w-6"></th>
              <th className="px-3 py-2 text-left">Name</th>
              <th className="px-3 py-2 text-left">Formula</th>
              <th className="px-3 py-2 text-right">Exact Mass</th>
              <th className="px-3 py-2 text-right">Δ Da</th>
              <th className="px-3 py-2 text-right">Δ ppm</th>
              <th className="px-3 py-2 text-left">Adduct</th>
              <th className="px-3 py-2 text-left">Sources</th>
              <th className="px-3 py-2 text-left">Links</th>
              <th className="px-3 py-2 text-left">InChIKey</th>
            </tr>
          </thead>

          <tbody>
            {queryResults.map((query, qi) => {
              const visible = query.results.filter(matches)
              const groups  = groupResults(visible)

              return (
                <>
                  {/* Query separator */}
                  <tr key={"query" + qi}
                      className="bg-[#111922] border-t border-b border-gray-800">
                    <td colSpan={10} className="px-3 py-2 text-[11px]">
                      <span className="font-mono text-cyan-400">
                        Q{qi + 1} · {typeof query.query_mass === 'number'
                          ? query.query_mass.toFixed(4) + " Da"
                          : query.query_mass}
                      </span>
                      <span className="text-gray-500 ml-2">
                        {groups.length} compound{groups.length !== 1 ? "s" : ""}
                        {groups.length !== visible.length &&
                          ` (${visible.length} entries across databases)`}
                      </span>
                    </td>
                  </tr>

                  {groups.map((group, gi) => {
                    const rep      = group[0]  // representative row
                    const groupKey = `${qi}-${gi}`
                    const isExpanded = expandedGroups.has(groupKey)
                    const isGrouped  = group.length > 1

                    // Best mass error across group
                    const bestErr = group.reduce((best, r) =>
                      r.mass_error != null && (best == null || r.mass_error < best)
                        ? r.mass_error : best, null)
                    const bestPpm = group.reduce((best, r) =>
                      r.ppm_error != null && (best == null || Math.abs(r.ppm_error) < Math.abs(best))
                        ? r.ppm_error : best, null)

                    const pubchem = rep.inchikey
                      ? `https://pubchem.ncbi.nlm.nih.gov/#query=${rep.inchikey}`
                      : null

                    return (
                      <>
                        {/* Grouped/summary row */}
                        <tr
                          key={groupKey}
                          onClick={isGrouped ? () => toggleGroup(groupKey) : undefined}
                          className={`border-t border-gray-900 transition-colors
                            ${isGrouped
                              ? "hover:bg-[rgba(0,194,255,0.08)] cursor-pointer"
                              : "hover:bg-[rgba(0,194,255,0.05)]"}`}
                        >
                          {/* Expand arrow */}
                          <td className="px-2 py-2 text-gray-600 text-center">
                            {isGrouped && (
                              <span className={`text-[10px] transition-transform inline-block
                                ${isExpanded ? "rotate-90" : ""}`}>
                                ▶
                              </span>
                            )}
                          </td>

                          {/* Name */}
                          <td className="px-3 py-2 text-gray-200 max-w-[220px] truncate font-medium">
                            {rep.name || <span className="text-gray-600 italic">unnamed</span>}
                          </td>

                          {/* Formula */}
                          <td className="px-3 py-2 font-mono text-cyan-300/80">
                            {rep.formula}
                          </td>

                          {/* Exact mass */}
                          <td className="px-3 py-2 text-right font-mono text-gray-300">
                            {rep.exact_mass != null
                              ? Number(rep.exact_mass).toFixed(5) : "—"}
                          </td>

                          {/* Δ Da */}
                          <td className="px-3 py-2 text-right font-mono text-gray-500">
                            {bestErr != null ? Number(bestErr).toFixed(4) : "—"}
                          </td>

                          {/* Δ ppm */}
                          <td className={`px-3 py-2 text-right font-mono ${ppmColor(bestPpm)}`}>
                            {bestPpm != null ? Number(bestPpm).toFixed(2) : "—"}
                          </td>

                          {/* Adduct */}
                          <td className="px-3 py-2 font-mono text-gray-500 text-[11px]">
                            {rep.adduct || "—"}
                          </td>

                          {/* Source badges — all sources in group */}
                          <td className="px-3 py-2">
                            <div className="flex flex-wrap gap-1">
                              {[...new Set(group.map(r => r.source))].map(src => (
                                <span key={src}
                                      className={`text-[10px] px-1.5 py-0.5 rounded font-medium
                                        ${SOURCE_BADGE[src] || "bg-gray-500/15 text-gray-400 border border-gray-500/25"}`}>
                                  {src}
                                </span>
                              ))}
                            </div>
                          </td>

                          {/* Links — one per source, deduped */}
                          <td className="px-3 py-2 text-[11px] font-mono">
                            <div className="flex gap-2 flex-wrap">
                              {[...new Map(group.map(r => [r.source, r])).values()].map(r => {
                                const url = SOURCE_URLS[r.source]?.(r.source_id)
                                return url ? (
                                  <a key={r.source} href={url} target="_blank" rel="noreferrer"
                                     onClick={e => e.stopPropagation()}
                                     className="text-cyan-400 hover:text-cyan-300">
                                    {r.source} ↗
                                  </a>
                                ) : null
                              })}
                              {pubchem && (
                                <a href={pubchem} target="_blank" rel="noreferrer"
                                   onClick={e => e.stopPropagation()}
                                   className="text-teal-400 hover:text-teal-300">
                                  PubChem ↗
                                </a>
                              )}
                            </div>
                          </td>

                          {/* InChIKey */}
                          <td className="px-3 py-2 font-mono text-[10px] text-gray-600
                                         truncate max-w-[160px]">
                            {rep.inchikey || "—"}
                          </td>
                        </tr>

                        {/* Expanded rows — individual database entries */}
                        {isExpanded && isGrouped && group.map((r, ri) => {
                          const url     = SOURCE_URLS[r.source]?.(r.source_id) || null
                          const pchem   = r.inchikey
                            ? `https://pubchem.ncbi.nlm.nih.gov/#query=${r.inchikey}` : null

                          return (
                            <tr key={`${groupKey}-exp-${ri}`}
                                className="border-t border-gray-900/50
                                           bg-[rgba(0,194,255,0.03)]">
                              <td className="px-2 py-1.5 text-gray-800 text-center
                                             border-l-2 border-cyan-900/30">
                                └
                              </td>
                              <td className="px-3 py-1.5 text-gray-400 max-w-[220px] truncate text-[11px]">
                                {r.name}
                              </td>
                              <td className="px-3 py-1.5 font-mono text-cyan-300/50 text-[11px]">
                                {r.formula}
                              </td>
                              <td className="px-3 py-1.5 text-right font-mono text-gray-500 text-[11px]">
                                {r.exact_mass != null ? Number(r.exact_mass).toFixed(5) : "—"}
                              </td>
                              <td className="px-3 py-1.5 text-right font-mono text-gray-600 text-[11px]">
                                {r.mass_error != null ? Number(r.mass_error).toFixed(4) : "—"}
                              </td>
                              <td className={`px-3 py-1.5 text-right font-mono text-[11px] ${ppmColor(r.ppm_error)}`}>
                                {r.ppm_error != null ? Number(r.ppm_error).toFixed(2) : "—"}
                              </td>
                              <td className="px-3 py-1.5 font-mono text-gray-600 text-[11px]">
                                {r.adduct || "—"}
                              </td>
                              <td className="px-3 py-1.5">
                                <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium
                                  ${SOURCE_BADGE[r.source] || "bg-gray-500/15 text-gray-400 border border-gray-500/25"}`}>
                                  {r.source}
                                </span>
                              </td>
                              <td className="px-3 py-1.5 text-[11px] font-mono">
                                <div className="flex gap-2">
                                  {url && (
                                    <a href={url} target="_blank" rel="noreferrer"
                                       className="text-cyan-400/70 hover:text-cyan-300">
                                      {r.source} ↗
                                    </a>
                                  )}
                                  {pchem && (
                                    <a href={pchem} target="_blank" rel="noreferrer"
                                       className="text-teal-400/70 hover:text-teal-300">
                                      PubChem ↗
                                    </a>
                                  )}
                                </div>
                              </td>
                              <td className="px-3 py-1.5 font-mono text-[10px] text-gray-700
                                             truncate max-w-[160px]">
                                {r.inchikey || "—"}
                              </td>
                            </tr>
                          )
                        })}
                      </>
                    )
                  })}
                </>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}