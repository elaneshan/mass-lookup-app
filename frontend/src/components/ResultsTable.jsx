import { useState } from "react"

const SOURCE_BADGE = {
  HMDB:      "bg-blue-500/15 text-blue-400 border-blue-500/25",
  ChEBI:     "bg-emerald-500/15 text-emerald-400 border-emerald-500/25",
  LipidMaps: "bg-orange-500/15 text-orange-400 border-orange-500/25",
  NPAtlas:   "bg-purple-500/15 text-purple-400 border-purple-500/25",
  FooDB:     "bg-yellow-500/15 text-yellow-400 border-yellow-500/25",
  "MS-DIAL": "bg-pink-500/15 text-pink-400 border-pink-500/25",
  PubChem:   "bg-gray-500/15 text-gray-400 border-gray-500/25",
}

const SOURCE_ROW = {
  HMDB:      "border-l-2 border-l-blue-500/30",
  ChEBI:     "border-l-2 border-l-emerald-500/30",
  LipidMaps: "border-l-2 border-l-orange-500/30",
  NPAtlas:   "border-l-2 border-l-purple-500/30",
  FooDB:     "border-l-2 border-l-yellow-500/30",
  "MS-DIAL": "border-l-2 border-l-pink-500/30",
  PubChem:   "border-l-2 border-l-gray-500/30",
}

const SOURCE_URLS = {
  HMDB:      id => `https://hmdb.ca/metabolites/${id}`,
  ChEBI:     id => `https://www.ebi.ac.uk/chebi/searchId.do?chebiId=${id}`,
  LipidMaps: id => `https://www.lipidmaps.org/databases/lmsd/${id}`,
  NPAtlas:   id => `https://www.npatlas.org/explore/compounds/${id}`,
}

function buildUrl(source, id) {
  return SOURCE_URLS[source]?.(id) || null
}

function pubchemUrl(inchikey) {
  return inchikey ? `https://pubchem.ncbi.nlm.nih.gov/#query=${inchikey}` : null
}

export default function ResultsTable({ queryResults, filterTerm }) {
  const [copied, setCopied] = useState(null)

  function copyRow(r) {
    const text = [r.name, r.formula, r.exact_mass, r.mass_error,
                  r.ppm_error, r.adduct, r.source, r.source_id, r.inchikey].join("\t")
    navigator.clipboard.writeText(text)
    setCopied(r.source_id)
    setTimeout(() => setCopied(null), 1500)
  }

  function exportCSV() {
    const rows = [["Query","Adduct","Name","Formula","Exact Mass","Δ Da","Δ ppm",
                   "Source","Source ID","URL","InChIKey","PubChem"]]
    for (const q of queryResults) {
      for (const r of q.results) {
        rows.push([q.query_mass, q.adduct, r.name, r.formula, r.exact_mass,
                   r.mass_error, r.ppm_error, r.source, r.source_id,
                   buildUrl(r.source, r.source_id) || "",
                   r.inchikey || "", pubchemUrl(r.inchikey) || ""])
      }
    }
    const csv  = rows.map(r => r.map(v => `"${v ?? ""}"`).join(",")).join("\n")
    const blob = new Blob([csv], { type: "text/csv" })
    const a    = document.createElement("a")
    a.href     = URL.createObjectURL(blob)
    a.download = "lucid_results.csv"
    a.click()
  }

  const term = filterTerm.toLowerCase()

  function matches(r) {
    if (!term) return true
    return [r.name, r.formula, r.source, r.inchikey, r.source_id]
      .some(v => v?.toLowerCase().includes(term))
  }

  const thClass = `px-3 py-2.5 text-left text-[10px] font-medium text-gray-500
                   uppercase tracking-widest whitespace-nowrap`

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <button onClick={exportCSV}
                className="text-[11px] px-3 py-1.5 rounded-lg border border-gray-700
                           text-gray-500 hover:text-cyan-400 hover:border-cyan-500/40
                           transition-colors bg-gray-900 font-mono">
          Export CSV ↓
        </button>
      </div>

      <div className="rounded-xl border border-gray-800 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr className="bg-gray-900 border-b border-gray-800">
                <th className={thClass}>Name</th>
                <th className={thClass}>Formula</th>
                <th className={thClass + " text-right"}>Exact Mass</th>
                <th className={thClass + " text-right"}>Δ Da</th>
                <th className={thClass + " text-right"}>Δ ppm</th>
                <th className={thClass}>Adduct</th>
                <th className={thClass}>Source</th>
                <th className={thClass}>Links</th>
                <th className={thClass}>InChIKey</th>
                <th className={thClass}></th>
              </tr>
            </thead>
            <tbody>
              {queryResults.map((query, qi) => {
                const visible = query.results.filter(matches)
                if (!visible.length && term) return null

                return (
                  <tbody key={`q-${qi}`}>
                    {/* Query separator */}
                    <tr className="bg-gray-900/80 border-t border-b border-gray-800/60">
                      <td colSpan={10} className="px-3 py-2">
                        <div className="flex items-center gap-3">
                          <span className="text-[10px] font-mono text-gray-600">
                            Q{qi + 1}
                          </span>
                          <span className="text-[11px] font-mono text-cyan-400/80">
                            {typeof query.query_mass === 'number'
                              ? `${Number(query.query_mass).toFixed(4)} Da`
                              : query.query_mass}
                          </span>
                          {query.adduct && query.adduct !== 'formula' && query.adduct !== 'neutral' && (
                            <span className="text-[10px] font-mono text-gray-500">
                              {query.adduct}
                            </span>
                          )}
                          <span className="text-[10px] text-gray-600 ml-1">
                            {visible.length} result{visible.length !== 1 ? "s" : ""}
                            {term && ` · filtered`}
                          </span>
                        </div>
                      </td>
                    </tr>

                    {visible.map((r, ri) => {
                      const url   = buildUrl(r.source, r.source_id)
                      const pchem = pubchemUrl(r.inchikey)
                      const badge = SOURCE_BADGE[r.source] || "bg-gray-500/15 text-gray-400 border-gray-500/25"
                      const rowBorder = SOURCE_ROW[r.source] || ""

                      return (
                        <tr key={`${qi}-${ri}`}
                            className={`result-row border-t border-gray-900 bg-gray-950/50 ${rowBorder}`}>
                          <td className="px-3 py-2 max-w-[200px]">
                            <span className="text-gray-200 font-medium truncate block"
                                  title={r.name}>
                              {r.name || <span className="text-gray-700 italic">unnamed</span>}
                            </span>
                          </td>
                          <td className="px-3 py-2">
                            <span className="font-mono text-cyan-300/70">{r.formula || "—"}</span>
                          </td>
                          <td className="px-3 py-2 text-right">
                            <span className="font-mono text-gray-300">
                              {r.exact_mass != null ? Number(r.exact_mass).toFixed(5) : "—"}
                            </span>
                          </td>
                          <td className="px-3 py-2 text-right">
                            <span className="font-mono text-gray-500 text-[11px]">
                              {r.mass_error != null ? Number(r.mass_error).toFixed(4) : "—"}
                            </span>
                          </td>
                          <td className="px-3 py-2 text-right">
                            <span className="font-mono text-gray-500 text-[11px]">
                              {r.ppm_error != null ? Number(r.ppm_error).toFixed(2) : "—"}
                            </span>
                          </td>
                          <td className="px-3 py-2">
                            <span className="font-mono text-gray-500 text-[11px]">
                              {r.adduct || "—"}
                            </span>
                          </td>
                          <td className="px-3 py-2">
                            <span className={`inline-flex items-center px-1.5 py-0.5 rounded
                                             border text-[10px] font-medium ${badge}`}>
                              {r.source}
                            </span>
                          </td>
                          <td className="px-3 py-2 whitespace-nowrap">
                            <div className="flex items-center gap-2">
                              {url && (
                                <a href={url} target="_blank" rel="noreferrer"
                                   className="text-[11px] text-cyan-500/70 hover:text-cyan-400
                                              transition-colors font-mono">
                                  {r.source} ↗
                                </a>
                              )}
                              {pchem && (
                                <a href={pchem} target="_blank" rel="noreferrer"
                                   className="text-[11px] text-teal-500/60 hover:text-teal-400
                                              transition-colors font-mono">
                                  PubChem ↗
                                </a>
                              )}
                            </div>
                          </td>
                          <td className="px-3 py-2 max-w-[160px]">
                            <span className="font-mono text-[10px] text-gray-700 truncate block"
                                  title={r.inchikey}>
                              {r.inchikey || "—"}
                            </span>
                          </td>
                          <td className="px-2 py-2">
                            <button onClick={() => copyRow(r)}
                                    className="text-gray-700 hover:text-cyan-400 transition-colors
                                               text-[11px] font-mono">
                              {copied === r.source_id ? "✓" : "⎘"}
                            </button>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}