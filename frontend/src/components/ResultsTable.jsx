import { useState } from "react"

const SOURCE_COLORS = {
  HMDB:      "bg-blue-50",
  ChEBI:     "bg-green-50",
  LipidMaps: "bg-orange-50",
  NPAtlas:   "bg-purple-50",
  FooDB:     "bg-yellow-50",
  "MS-DIAL": "bg-pink-50",
  PubChem:   "bg-slate-50",
}

const SOURCE_URLS = {
  HMDB:      id => `https://hmdb.ca/metabolites/${id}`,
  ChEBI:     id => `https://www.ebi.ac.uk/chebi/searchId.do?chebiId=${id}`,
  LipidMaps: id => `https://www.lipidmaps.org/databases/lmsd/${id}`,
  NPAtlas:   id => `https://www.npatlas.org/explore/compounds/${id}`,
}

function buildUrl(source, sourceId) {
  const fn = SOURCE_URLS[source]
  return fn && sourceId ? fn(sourceId) : null
}

function pubchemUrl(inchikey) {
  return inchikey
    ? `https://pubchem.ncbi.nlm.nih.gov/#query=${inchikey}`
    : null
}

export default function ResultsTable({ queryResults, filterTerm }) {
  const [copiedRow, setCopiedRow] = useState(null)

  function copyRow(compound) {
    const text = [
      compound.name, compound.formula, compound.exact_mass,
      compound.mass_error, compound.ppm_error, compound.adduct,
      compound.source, compound.source_id, compound.inchikey
    ].join("\t")
    navigator.clipboard.writeText(text)
    setCopiedRow(compound.source_id)
    setTimeout(() => setCopiedRow(null), 1500)
  }

  function exportCSV() {
    const rows = [
      ["Query", "Adduct", "Name", "Formula", "Exact Mass",
       "Error (Da)", "Error (ppm)", "Source", "Source ID", "URL", "InChIKey", "PubChem"]
    ]
    for (const q of queryResults) {
      for (const r of q.results) {
        const url     = buildUrl(r.source, r.source_id) || ""
        const pchem   = pubchemUrl(r.inchikey) || ""
        rows.push([
          q.query_mass, q.adduct, r.name, r.formula,
          r.exact_mass, r.mass_error, r.ppm_error,
          r.source, r.source_id, url, r.inchikey, pchem
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

  const term = filterTerm.toLowerCase()

  function matchesFilter(r) {
    if (!term) return true
    return [r.name, r.formula, r.source, r.inchikey, r.source_id]
      .some(v => v?.toLowerCase().includes(term))
  }

  const totalVisible = queryResults.reduce(
    (sum, q) => sum + q.results.filter(matchesFilter).length, 0
  )

  return (
    <div className="flex flex-col gap-2">

      {/* Export button */}
      <div className="flex justify-end">
        <button
          onClick={exportCSV}
          className="text-xs px-3 py-1.5 rounded border border-slate-300 bg-white
                     hover:bg-slate-50 text-slate-600"
        >
          Export CSV
        </button>
      </div>

      <div className="rounded-lg border border-slate-200 overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="bg-slate-100 text-slate-600 uppercase tracking-wide text-[11px]">
              <tr>
                <th className="px-3 py-2 text-left font-semibold">Name</th>
                <th className="px-3 py-2 text-left font-semibold">Formula</th>
                <th className="px-3 py-2 text-right font-semibold">Exact Mass</th>
                <th className="px-3 py-2 text-right font-semibold">Δ Da</th>
                <th className="px-3 py-2 text-right font-semibold">Δ ppm</th>
                <th className="px-3 py-2 text-left font-semibold">Adduct</th>
                <th className="px-3 py-2 text-left font-semibold">Source</th>
                <th className="px-3 py-2 text-left font-semibold">Link</th>
                <th className="px-3 py-2 text-left font-semibold">InChIKey</th>
                <th className="px-2 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {queryResults.map((query, qi) => {
                const visible = query.results.filter(matchesFilter)
                if (visible.length === 0 && term) return null

                return (
                  <>
                    {/* Query separator row */}
                    <tr key={`sep-${qi}`} className="bg-slate-200">
                      <td colSpan={10} className="px-3 py-1.5 font-semibold text-slate-700 text-[11px]">
                        Query {qi + 1}
                        {query.query_mass
                          ? `: ${Number(query.query_mass).toFixed(4)} Da`
                          : ""}
                        {query.adduct && query.adduct !== "neutral"
                          ? ` · ${query.adduct}`
                          : ""}
                        <span className="font-normal text-slate-500 ml-2">
                          ({visible.length} result{visible.length !== 1 ? "s" : ""}
                          {term && ` matching "${filterTerm}"`})
                        </span>
                      </td>
                    </tr>

                    {visible.map((r, ri) => {
                      const url   = buildUrl(r.source, r.source_id)
                      const pchem = pubchemUrl(r.inchikey)
                      const color = SOURCE_COLORS[r.source] || "bg-white"
                      const copied = copiedRow === r.source_id

                      return (
                        <tr
                          key={`${qi}-${ri}`}
                          className={`${color} border-t border-slate-100 hover:brightness-95 transition-all`}
                        >
                          <td className="px-3 py-2 max-w-xs truncate font-medium text-slate-800">
                            {r.name || <span className="text-slate-400 italic">unnamed</span>}
                          </td>
                          <td className="px-3 py-2 font-mono text-slate-600">
                            {r.formula || "—"}
                          </td>
                          <td className="px-3 py-2 text-right font-mono text-slate-700">
                            {r.exact_mass != null ? Number(r.exact_mass).toFixed(5) : "—"}
                          </td>
                          <td className="px-3 py-2 text-right font-mono text-slate-500">
                            {r.mass_error != null ? Number(r.mass_error).toFixed(4) : "—"}
                          </td>
                          <td className="px-3 py-2 text-right font-mono text-slate-500">
                            {r.ppm_error != null ? Number(r.ppm_error).toFixed(2) : "—"}
                          </td>
                          <td className="px-3 py-2 font-mono text-slate-600 whitespace-nowrap">
                            {r.adduct || "—"}
                          </td>
                          <td className="px-3 py-2">
                            <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-semibold
                              ${r.source === "HMDB"      ? "bg-blue-100 text-blue-800" :
                                r.source === "ChEBI"     ? "bg-green-100 text-green-800" :
                                r.source === "LipidMaps" ? "bg-orange-100 text-orange-800" :
                                r.source === "NPAtlas"   ? "bg-purple-100 text-purple-800" :
                                r.source === "FooDB"     ? "bg-yellow-100 text-yellow-800" :
                                "bg-slate-100 text-slate-700"}`}>
                              {r.source}
                            </span>
                          </td>
                          <td className="px-3 py-2 whitespace-nowrap">
                            {url && (
                              <a href={url} target="_blank" rel="noreferrer"
                                className="text-blue-600 underline hover:text-blue-800 mr-2">
                                {r.source}
                              </a>
                            )}
                            {pchem && (
                              <a href={pchem} target="_blank" rel="noreferrer"
                                className="text-teal-600 underline hover:text-teal-800">
                                PubChem
                              </a>
                            )}
                          </td>
                          <td className="px-3 py-2 font-mono text-slate-400 text-[10px] max-w-[180px] truncate">
                            {r.inchikey || "—"}
                          </td>
                          <td className="px-2 py-2">
                            <button
                              onClick={() => copyRow(r)}
                              title="Copy row"
                              className="text-slate-400 hover:text-slate-600 transition-colors"
                            >
                              {copied ? "✓" : "⎘"}
                            </button>
                          </td>
                        </tr>
                      )
                    })}
                  </>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {term && (
        <p className="text-xs text-slate-400 text-right">
          Showing {totalVisible} results matching "{filterTerm}"
        </p>
      )}
    </div>
  )
}