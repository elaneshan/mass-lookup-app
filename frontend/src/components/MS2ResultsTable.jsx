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
}

function ScoreBar({ pct }) {
  const color = pct === 100 ? "bg-emerald-500"
    : pct >= 60 ? "bg-yellow-500"
    : "bg-red-500/60"
  return (
    <div className="flex items-center gap-2">
      <div className="w-20 h-1.5 bg-gray-800 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`}
             style={{ width: `${pct}%` }} />
      </div>
      <span className={`text-[11px] font-mono font-medium
        ${pct === 100 ? "text-emerald-400"
          : pct >= 60 ? "text-yellow-400"
          : "text-red-400"}`}>
        {pct}%
      </span>
    </div>
  )
}

export default function MS2ResultsTable({ data }) {
  const [expanded, setExpanded] = useState(new Set())

  if (!data) return null

  const { candidates, neutral_losses, fragment_results, n_fragments } = data

  function toggle(key) {
    setExpanded(prev => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })
  }

  function exportCSV() {
    const rows = [
      ["Rank", "Name", "Formula", "Source", "Source ID",
       "Fragments Explained", "Coverage %", "Avg ppm", "Matched Fragments"]
    ]
    candidates.forEach((c, i) => {
      const frags = c.fragment_matches
        .map(f => `${f.fragment_mass}(${f.ppm_error}ppm)`).join('; ')
      rows.push([
        i + 1, c.name, c.formula, c.source, c.source_id,
        c.fragments_explained, c.coverage_pct, c.avg_ppm, frags
      ])
    })
    const csv  = rows.map(r => r.map(v => `"${v ?? ""}"`).join(",")).join("\n")
    const blob = new Blob([csv], { type: "text/csv" })
    const a    = document.createElement("a")
    a.href     = URL.createObjectURL(blob)
    a.download = "lucid_ms2_results.csv"
    a.click()
  }

  return (
    <div className="flex flex-col gap-4">

      {/* Neutral losses detected */}
      {neutral_losses.length > 0 && (
        <div className="panel rounded-xl p-4">
          <p className="text-[10px] uppercase tracking-widest text-gray-500 mb-3">
            Neutral Losses Detected Between Fragments
          </p>
          <div className="flex flex-wrap gap-2">
            {neutral_losses.map((loss, i) => (
              <div key={i}
                   className="text-[11px] font-mono bg-cyan-500/10 border border-cyan-500/20
                              rounded px-2 py-1 text-cyan-300">
                {loss.from_mass} → {loss.to_mass}
                <span className="text-cyan-500/60 ml-1">
                  −{loss.loss_da} Da ({loss.loss_name})
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Per-fragment summary */}
      <div className="panel rounded-xl p-4">
        <p className="text-[10px] uppercase tracking-widest text-gray-500 mb-3">
          Fragment Search Summary ({n_fragments} fragments)
        </p>
        <div className="flex flex-wrap gap-2">
          {fragment_results.map((fr, i) => (
            <div key={i}
                 className={`text-[11px] font-mono px-2 py-1 rounded border
                   ${fr.hits.length > 0
                     ? "bg-gray-800 border-gray-700 text-gray-300"
                     : "bg-red-950/30 border-red-900/40 text-red-400"}`}>
              {fr.mass.toFixed(4)}
              <span className="text-gray-500 ml-1">
                {fr.hits.length > 0 ? `${fr.hits.length} hits` : "no hits"}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Candidate table */}
      <div className="panel rounded-xl overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3
                        border-b border-gray-800">
          <p className="text-[10px] uppercase tracking-widest text-gray-500">
            Candidates ranked by fragment coverage + ppm
          </p>
          <button onClick={exportCSV}
                  className="text-[11px] px-3 py-1 rounded border border-gray-700
                             text-gray-500 hover:text-cyan-400 hover:border-cyan-500/40
                             transition-colors bg-gray-900 font-mono">
            Export CSV ↓
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="bg-[#131C26] border-b border-gray-800">
              <tr className="text-[10px] uppercase tracking-wider text-gray-500">
                <th className="px-3 py-2 text-left w-8">#</th>
                <th className="px-3 py-2 text-left">Name</th>
                <th className="px-3 py-2 text-left">Formula</th>
                <th className="px-3 py-2 text-left">Coverage</th>
                <th className="px-3 py-2 text-right">Avg ppm</th>
                <th className="px-3 py-2 text-left">Source</th>
                <th className="px-3 py-2 text-left">Link</th>
                <th className="px-3 py-2 text-left">InChIKey</th>
                <th className="px-3 py-2 w-6"></th>
              </tr>
            </thead>
            <tbody>
              {candidates.map((c, i) => {
                const key      = `${c.source}_${c.source_id}`
                const isOpen   = expanded.has(key)
                const url      = SOURCE_URLS[c.source]?.(c.source_id) || null
                const pubchem  = c.inchikey
                  ? `https://pubchem.ncbi.nlm.nih.gov/#query=${c.inchikey}` : null

                return (
                  <>
                    <tr key={key}
                        onClick={() => toggle(key)}
                        className="border-t border-gray-900 hover:bg-[rgba(0,194,255,0.06)]
                                   cursor-pointer transition-colors">
                      <td className="px-3 py-2.5 text-gray-600 font-mono text-[11px]">
                        {i + 1}
                      </td>
                      <td className="px-3 py-2.5 text-gray-200 font-medium
                                     max-w-[200px] truncate">
                        {c.name || <span className="text-gray-600 italic">unnamed</span>}
                      </td>
                      <td className="px-3 py-2.5 font-mono text-cyan-300/80">
                        {c.formula}
                      </td>
                      <td className="px-3 py-2.5">
                        <div className="flex flex-col gap-1">
                          <ScoreBar pct={c.coverage_pct} />
                          <span className="text-[10px] text-gray-600 font-mono">
                            {c.fragments_explained}/{n_fragments} fragments
                          </span>
                        </div>
                      </td>
                      <td className="px-3 py-2.5 text-right font-mono">
                        <span className={
                          c.avg_ppm < 2 ? "text-emerald-400"
                          : c.avg_ppm < 5 ? "text-yellow-400"
                          : "text-red-400"
                        }>
                          {c.avg_ppm.toFixed(2)}
                        </span>
                      </td>
                      <td className="px-3 py-2.5">
                        <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium
                          ${SOURCE_BADGE[c.source] || "bg-gray-500/15 text-gray-400 border border-gray-500/25"}`}>
                          {c.source}
                        </span>
                      </td>
                      <td className="px-3 py-2.5 text-[11px] font-mono">
                        <div className="flex gap-2" onClick={e => e.stopPropagation()}>
                          {url && (
                            <a href={url} target="_blank" rel="noreferrer"
                               className="text-cyan-400 hover:text-cyan-300">
                              {c.source} ↗
                            </a>
                          )}
                          {pubchem && (
                            <a href={pubchem} target="_blank" rel="noreferrer"
                               className="text-teal-400 hover:text-teal-300">
                              PubChem ↗
                            </a>
                          )}
                        </div>
                      </td>
                      <td className="px-3 py-2.5 font-mono text-[10px] text-gray-700
                                     truncate max-w-[140px]">
                        {c.inchikey || "—"}
                      </td>
                      <td className="px-2 py-2.5 text-cyan-500/60 text-[10px]">
                        {isOpen ? "▾" : "▸"}
                      </td>
                    </tr>

                    {/* Expanded fragment match detail */}
                    {isOpen && (
                      <tr key={key + "-exp"}>
                        <td colSpan={9}
                            className="px-6 py-3 bg-gray-900/60 border-t border-gray-800/50">
                          <p className="text-[10px] uppercase tracking-widest
                                        text-gray-600 mb-2">
                            Fragment Matches
                          </p>
                          <div className="flex flex-wrap gap-2">
                            {c.fragment_matches.map((fm, fi) => (
                              <div key={fi}
                                   className="text-[11px] font-mono bg-gray-800
                                              border border-gray-700 rounded px-2 py-1">
                                <span className="text-gray-300">
                                  {fm.fragment_mass.toFixed(4)}
                                </span>
                                <span className="text-gray-600 mx-1">→</span>
                                <span className="text-cyan-300/70">
                                  {fm.matched_mass.toFixed(5)}
                                </span>
                                <span className={`ml-1 ${
                                  Math.abs(fm.ppm_error) < 2 ? "text-emerald-400"
                                  : Math.abs(fm.ppm_error) < 5 ? "text-yellow-400"
                                  : "text-red-400"}`}>
                                  ({fm.ppm_error.toFixed(2)} ppm)
                                </span>
                              </div>
                            ))}
                            {/* Show unmatched fragments */}
                            {fragment_results
                              .filter(fr => !c.fragment_matches
                                .some(fm => fm.fragment_mass === fr.mass))
                              .map((fr, fi) => (
                                <div key={"nm" + fi}
                                     className="text-[11px] font-mono bg-red-950/20
                                                border border-red-900/30 rounded px-2 py-1
                                                text-red-400/60">
                                  {fr.mass.toFixed(4)} — no match
                                </div>
                              ))
                            }
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}