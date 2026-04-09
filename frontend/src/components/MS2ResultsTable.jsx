import { useState } from "react"
const formatPPM = (ppm) => {
  if (ppm == null) return "—"

  if (ppm < 0.001) return ppm.toExponential(2)   // e.g. 1.81e-4
  if (ppm < 0.01)  return ppm.toFixed(5)
  if (ppm < 1)     return ppm.toFixed(4)
  return ppm.toFixed(2)
}

const SOURCE_URLS = {
  HMDB:      id => `https://hmdb.ca/metabolites/${id}`,
  ChEBI:     id => `https://www.ebi.ac.uk/chebi/searchId.do?chebiId=${id}`,
  LipidMaps: id => `https://www.lipidmaps.org/databases/lmsd/${id}`,
  NPAtlas:   id => `https://www.npatlas.org/explore/compounds/${id}`,
}

const CONFIDENCE_STYLES = {
  high:     { text: "text-emerald-400", border: "border-emerald-500/30", bg: "bg-emerald-500/5",  badge: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30" },
  moderate: { text: "text-yellow-400",  border: "border-yellow-500/30",  bg: "bg-yellow-500/5",   badge: "bg-yellow-500/10 text-yellow-400 border-yellow-500/30"   },
  low:      { text: "text-orange-400",  border: "border-orange-500/30",  bg: "bg-orange-500/5",   badge: "bg-orange-500/10 text-orange-400 border-orange-500/30"   },
  none:     { text: "text-gray-500",    border: "border-gray-700",       bg: "bg-gray-900/40",    badge: "bg-gray-800 text-gray-500 border-gray-700"               },
}

const CLASS_COLORS = {
  anthocyanin: "bg-pink-500/10 text-pink-400 border-pink-500/30",
  flavonol:    "bg-cyan-500/10 text-cyan-400 border-cyan-500/30",
}

const LOSS_CLASS_COLORS = {
  "Hexose":              "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  "Deoxyhexose":         "bg-teal-500/10 text-teal-400 border-teal-500/20",
  "Pentose":             "bg-blue-500/10 text-blue-400 border-blue-500/20",
  "Hexose Disaccharide": "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  "Hexose Deoxyhexose":  "bg-teal-500/10 text-teal-400 border-teal-500/20",
  "Acyl Hexose":         "bg-violet-500/10 text-violet-400 border-violet-500/20",
  "Acyl Deoxyhexose":    "bg-violet-500/10 text-violet-400 border-violet-500/20",
  "Acyl Moiety":         "bg-orange-500/10 text-orange-400 border-orange-500/20",
}

function CompositionBadge({ name, count, lossClass }) {
  const color = LOSS_CLASS_COLORS[lossClass] ?? "bg-gray-800 text-gray-400 border-gray-700"
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono border ${color}`}>
      {count}× {name}
    </span>
  )
}

function LadderAnnotationPanel({ annotation }) {
  const [showDetails, setShowDetails] = useState(false)
  if (!annotation) return null

  const conf       = CONFIDENCE_STYLES[annotation.confidence] ?? CONFIDENCE_STYLES.none
  const aglyconeUrl = annotation.aglycone_matches?.[0]
    ? SOURCE_URLS[annotation.aglycone_source]?.(annotation.aglycone_source_id)
    : null

  const isobars        = annotation.aglycone_matches ?? []
  const isAmbiguous    = annotation.aglycone_ambiguous
  const hasAnthocyanin = annotation.has_anthocyanin
  const hasFlavonol    = annotation.has_flavonol

  return (
    <div className={`rounded-xl border ${conf.border} ${conf.bg} p-5 flex flex-col gap-4`}>

      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="text-[10px] text-gray-500 uppercase tracking-widest">
          Structural Prediction · Flavonoid MS² Analysis
        </div>
        <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full border ${conf.badge}`}>
          {annotation.confidence} confidence
        </span>
      </div>

      {/* Main prediction */}
      <div>
        <div className={`text-xl font-semibold ${conf.text} leading-snug`}>
          {annotation.predicted_structure}
        </div>
        <div className="text-[11px] text-gray-500 mt-1 font-mono">
          Predicted neutral mass of parent: {annotation.predicted_parent_neutral} Da
        </div>
      </div>

      {/* Sugar composition badges */}
      {annotation.composition_parts?.length > 0 && (
        <div>
          <div className="text-[10px] text-gray-600 uppercase tracking-widest mb-1.5">
            Sugar / acyl composition
          </div>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(annotation.loss_name_counts ?? {})
              .sort((a, b) => b[1] - a[1])
              .map(([name, count]) => {
                // Find the class for this loss name from sequential losses
                const matchingLoss = annotation.sequential_losses?.find(sl => sl.loss_name === name)
                const lossClass    = matchingLoss?.loss_class ?? "Acyl Moiety"
                return <CompositionBadge key={name} name={name} count={count} lossClass={lossClass} />
              })
            }
          </div>
        </div>
      )}

      {/* Aglycone section */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="flex flex-col gap-1.5">
          <span className="text-[10px] text-gray-600 uppercase tracking-widest">Aglycone</span>

          {/* Isobar list */}
          {isobars.length > 0 ? (
            <div className="flex flex-col gap-1">
              {isobars.map((ag, i) => (
                <div key={i} className="flex items-center gap-2">
                  <span className={`text-[10px] font-medium px-1.5 py-px rounded border ${CLASS_COLORS[ag.class] ?? "bg-gray-800 text-gray-400 border-gray-700"}`}>
                    {ag.class}
                  </span>
                  <span className={`text-[12px] font-medium ${i === 0 ? "text-gray-100" : "text-gray-400"}`}>
                    {ag.name}
                  </span>
                  <span className="text-[10px] font-mono text-gray-600">
                    {formatPPM(ag.ppm_error)} ppm
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <span className="text-[12px] text-gray-500 italic">
              {annotation.aglycone_name ?? "not matched to flavonoid library"}
            </span>
          )}

          {/* Isobar ambiguity warning */}
          {isAmbiguous && hasAnthocyanin && hasFlavonol && (
            <div className="rounded-lg border border-yellow-500/20 bg-yellow-500/5 px-2 py-1.5 mt-1">
              <div className="text-[10px] text-yellow-400 font-medium">
                ⚠ Anthocyanin/flavonol isobars at {annotation.aglycone_mass} Da
              </div>
              <div className="text-[9px] text-yellow-600 mt-0.5 leading-relaxed">
                These compounds share the same mass in both positive and negative mode.
                Use UV absorbance (~520 nm anthocyanin, ~350 nm flavonol) or MS³ to distinguish.
              </div>
            </div>
          )}
          {isAmbiguous && !(hasAnthocyanin && hasFlavonol) && (
            <div className="rounded-lg border border-yellow-500/20 bg-yellow-500/5 px-2 py-1.5 mt-1">
              <div className="text-[10px] text-yellow-400 font-medium">
                ⚠ Multiple {isobars[0]?.class ?? ""} isobars at this mass
              </div>
              <div className="text-[9px] text-yellow-600 mt-0.5">
                Authentic standards or MS³ required to confirm.
              </div>
            </div>
          )}
        </div>

        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-0.5">
            <span className="text-[10px] text-gray-600 uppercase tracking-widest">Aglycone fragment</span>
            <span className="text-[12px] font-mono text-gray-200">{annotation.aglycone_mass} Da</span>
            {annotation.aglycone_ppm != null && (
              <span className="text-[10px] font-mono text-gray-600">{formatPPM(annotation.aglycone_ppm)} ppm error</span>
            )}
          </div>
          <div className="flex flex-col gap-0.5">
            <span className="text-[10px] text-gray-600 uppercase tracking-widest">Ladder</span>
            <span className="text-[12px] text-gray-200">{annotation.ladder_length} fragments</span>
            <span className="text-[10px] text-gray-600">{annotation.total_sequential_losses} sequential losses</span>
          </div>
        </div>
      </div>

      {/* Sequential ladder — collapsible */}
      {annotation.sequential_losses?.length > 0 && (
        <div>
          <button
            type="button"
            onClick={() => setShowDetails(s => !s)}
            className="text-[10px] text-gray-600 hover:text-cyan-400 transition-colors uppercase tracking-widest"
          >
            {showDetails ? "Hide ladder ↑" : "Show sequential ladder ↓"}
          </button>
          {showDetails && (
            <div className="mt-2 flex flex-wrap items-center gap-1 font-mono text-[10px]">
              {annotation.sequential_losses.map((sl, i) => {
                const color = LOSS_CLASS_COLORS[sl.loss_class] ?? "bg-gray-800 text-gray-400 border-gray-700"
                return (
                  <span key={i} className="flex items-center gap-1">
                    <span className="text-gray-300">{sl.to_mass.toFixed(2)}</span>
                    <span className={`px-1.5 py-px rounded border ${color}`}>
                      +{sl.loss_da} Da ({sl.loss_name})
                    </span>
                    <span className="text-gray-300">{sl.from_mass.toFixed(2)}</span>
                    {i < annotation.sequential_losses.length - 1 && (
                      <span className="text-gray-700 mx-0.5">·</span>
                    )}
                  </span>
                )
              })}
            </div>
          )}
        </div>
      )}

      <div className="text-[10px] text-gray-600 border-t border-gray-800/60 pt-3">
        Optimized for flavonoid glycosides. Computational prediction — verify with authentic standards.
      </div>
    </div>
  )
}

export default function MS2ResultsTable({ ms2Result }) {
  if (!ms2Result) return null

  const fragments         = Array.isArray(ms2Result.fragments)      ? ms2Result.fragments      : []
  const neutral_losses    = Array.isArray(ms2Result.neutral_losses) ? ms2Result.neutral_losses : []
  const ladder_annotation = ms2Result.ladder_annotation ?? null

  return (
    <div className="flex flex-col gap-5">

      {/* Summary */}
      <div className="flex items-center gap-4 flex-wrap">
        <div className="text-[11px] font-mono text-gray-500">
          <span className="text-cyan-400 font-medium">{fragments.length}</span> fragments analyzed
        </div>
        {neutral_losses.length > 0 && (
          <div className="text-[11px] font-mono text-gray-500">
            <span className="text-cyan-400 font-medium">{neutral_losses.length}</span> neutral losses detected
          </div>
        )}
      </div>

      {/* Structural annotation */}
      {ladder_annotation
        ? <LadderAnnotationPanel annotation={ladder_annotation} />
        : (
          <div className="text-center py-16 text-gray-600 text-sm">
            No flavonoid pattern detected in these fragment masses.
          </div>
        )
      }

    </div>
  )
}