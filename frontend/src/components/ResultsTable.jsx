import { useState } from "react"

export default function ResultsTable({ queryResults, filterTerm }) {

const [copied,setCopied]=useState(null)

const term = filterTerm.toLowerCase()

function matches(r){
if(!term)return true
return [r.name,r.formula,r.source,r.inchikey,r.source_id]
.some(v=>v?.toLowerCase().includes(term))
}

function ppmColor(ppm){

if(ppm==null)return "text-gray-500"

const val=Math.abs(ppm)

if(val<2)return "text-emerald-400"
if(val<5)return "text-yellow-400"

return "text-red-400"
}

function shortenUrl(url){

try{

const u = new URL(url)

const path = u.pathname.length>14
?u.pathname.slice(0,14)+"..."
:u.pathname

return u.hostname+path

}catch{

return url

}

}

return(

<div className="panel rounded-xl overflow-hidden">

<div className="overflow-x-auto">

<table className="w-full text-xs">

<thead className="sticky top-0 bg-[#131C26] border-b border-gray-800 z-10">

<tr className="text-[10px] uppercase tracking-wider text-gray-400">

<th className="px-3 py-2 text-left">Name</th>
<th className="px-3 py-2 text-left">Formula</th>
<th className="px-3 py-2 text-right">Exact Mass</th>
<th className="px-3 py-2 text-right">Δ Da</th>
<th className="px-3 py-2 text-right">Δ ppm</th>
<th className="px-3 py-2 text-left">Adduct</th>
<th className="px-3 py-2 text-left">Source</th>
<th className="px-3 py-2 text-left">Links</th>
<th className="px-3 py-2 text-left">InChIKey</th>

</tr>
</thead>

<tbody>

{queryResults.map((query,qi)=>{

const visible=query.results.filter(matches)

return(
<>

<tr
key={"query"+qi}
className="bg-[#111922] border-t border-b border-gray-800"
>

<td colSpan={9} className="px-3 py-2 text-[11px]">

<span className="font-mono text-cyan-400">

Q{qi+1} · {typeof query.query_mass==='number'
?query.query_mass.toFixed(4)+" Da"
:query.query_mass}

</span>

<span className="text-gray-500 ml-2">
{visible.length} results
</span>

</td>
</tr>

{visible.map((r,ri)=>{

const SOURCE_URLS = {
  HMDB:      id => `https://hmdb.ca/metabolites/${id}`,
  ChEBI:     id => `https://www.ebi.ac.uk/chebi/searchId.do?chebiId=${id}`,
  LipidMaps: id => `https://www.lipidmaps.org/databases/lmsd/${id}`,
  NPAtlas:   id => `https://www.npatlas.org/explore/compounds/${id}`,
}

const url = SOURCE_URLS[r.source]?.(r.source_id) || null
const pubchem = r.inchikey
  ? `https://pubchem.ncbi.nlm.nih.gov/#query=${r.inchikey}`
  : null

return(

    <tr
        key={qi + "-" + ri}
        className="result-row border-t border-gray-900 hover:bg-[rgba(0,194,255,0.08)] transition-colors"
    >

        <td className="px-3 py-2 text-gray-200 max-w-[220px] truncate">
            {r.name}
        </td>

        <td className="px-3 py-2 font-mono text-cyan-300/80">
            {r.formula}
        </td>

        <td className="px-3 py-2 text-right font-mono">
            {Number(r.exact_mass).toFixed(5)}
        </td>

        <td className="px-3 py-2 text-right font-mono text-gray-500">
            {r.mass_error != null ? Number(r.mass_error).toFixed(4) : "—"}
        </td>

        <td className={`px-3 py-2 text-right font-mono ${ppmColor(r.ppm_error)}`}>
            {r.ppm_error != null ? Number(r.ppm_error).toFixed(2) : "—"}
        </td>

        <td className="px-3 py-2 font-mono text-gray-500 text-[11px]">
            {r.adduct}
        </td>

        <td className="px-3 py-2 text-gray-400">
            {r.source}
        </td>

        <td className="px-3 py-2 text-[11px] font-mono">
            <div className="flex gap-2">
                {url ? (
                    <a href={url} target="_blank" rel="noreferrer"
                       className="text-cyan-400 hover:text-cyan-300">
                        {r.source} ↗
                    </a>
                ) : null}
                {pubchem ? (
                    <a href={pubchem} target="_blank" rel="noreferrer"
                       className="text-teal-400 hover:text-teal-300">
                        PubChem ↗
                    </a>
                ) : null}
                {!url && !pubchem && <span className="text-gray-600">—</span>}
            </div>
        </td>

        <td className="px-3 py-2 font-mono text-[10px] text-gray-600 truncate max-w-[160px]">
            {r.inchikey}
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

)

}