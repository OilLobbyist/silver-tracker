import React, {useState, useEffect, useRef} from 'react'
import Papa from 'papaparse'
import Box from '@mui/material/Box'
import Grid from '@mui/material/Grid'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import Typography from '@mui/material/Typography'
import Button from '@mui/material/Button'
import TextField from '@mui/material/TextField'
import Slider from '@mui/material/Slider'
import Switch from '@mui/material/Switch'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableContainer from '@mui/material/TableContainer'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'
import Paper from '@mui/material/Paper'
import Snackbar from '@mui/material/Snackbar'
import Alert from '@mui/material/Alert'
import IconButton from '@mui/material/IconButton'
import RestoreFromTrashIcon from '@mui/icons-material/RestoreFromTrash'
import UploadFileIcon from '@mui/icons-material/UploadFile'
import DownloadIcon from '@mui/icons-material/Download'
import AddIcon from '@mui/icons-material/Add'
import UndoIcon from '@mui/icons-material/Undo'
import DeleteIcon from '@mui/icons-material/Delete'

const STORAGE_KEY = 'silver_inventory_v2_enc'
const EPHEMERAL_KEY = 'silver_ephemeral_key_v2'

function defaultRow(){
  return {"Description":"","Weight (troy oz)":"","Date Acquired":"","Price Paid ($)":"","Modifier ($)":""}
}

function bufToBase64(buf){
  return btoa(String.fromCharCode(...new Uint8Array(buf)))
}
function base64ToBuf(b64){
  const bin = atob(b64)
  const arr = new Uint8Array(bin.length)
  for(let i=0;i<bin.length;i++) arr[i]=bin.charCodeAt(i)
  return arr.buffer
}

async function deriveKeyFromPassword(password, salt){
  const enc = new TextEncoder()
  const keyMaterial = await window.crypto.subtle.importKey('raw', enc.encode(password), 'PBKDF2', false, ['deriveKey'])
  return crypto.subtle.deriveKey({name:'PBKDF2', salt, iterations:150000, hash:'SHA-256'}, keyMaterial, {name:'AES-GCM', length:256}, false, ['encrypt','decrypt'])
}

async function importEphemeralKeyFromBase64(b64){
  try{
    const raw = base64ToBuf(b64)
    return crypto.subtle.importKey('raw', raw, 'AES-GCM', false, ['encrypt','decrypt'])
  }catch(e){return null}
}

async function exportKeyToBase64(key){
  const raw = await crypto.subtle.exportKey('raw', key)
  return bufToBase64(raw)
}

async function generateEphemeralKey(){
  const key = await crypto.subtle.generateKey({name:'AES-GCM', length:256}, true, ['encrypt','decrypt'])
  const b64 = await exportKeyToBase64(key)
  try{ sessionStorage.setItem(EPHEMERAL_KEY, b64) }catch(e){}
  return key
}

async function encryptJson(obj, key, saltB64=null){
  const iv = crypto.getRandomValues(new Uint8Array(12))
  const enc = new TextEncoder()
  const ct = await crypto.subtle.encrypt({name:'AES-GCM', iv}, key, enc.encode(JSON.stringify(obj)))
  return {v:1, ciphertext:bufToBase64(ct), iv:bufToBase64(iv), salt:saltB64}
}

async function decryptBlob(blob, key){
  try{
    const ct = base64ToBuf(blob.ciphertext)
    const iv = base64ToBuf(blob.iv)
    const plain = await crypto.subtle.decrypt({name:'AES-GCM', iv}, key, ct)
    const dec = new TextDecoder().decode(plain)
    return JSON.parse(dec)
  }catch(e){
    throw e
  }
}

export default function TableEditor(){
  const [rows, setRows] = useState([])
  const [spot, setSpot] = useState(25.00)
  const [status, setStatus] = useState('')
  const [persistLocal, setPersistLocal] = useState(false)
  const [passphrase, setPassphrase] = useState('')
  const [locked, setLocked] = useState(false)
  const [key, setKey] = useState(null)
  const fileRef = useRef()

  // On mount: try to load encrypted blob and prepare key
  useEffect(()=>{
    (async ()=>{
      try{
        // determine storage preference automatically (local if present)
        const localBlob = localStorage.getItem(STORAGE_KEY)
        const sessionBlob = sessionStorage.getItem(STORAGE_KEY)
        let blobStr = localBlob || sessionBlob
        if(blobStr){
          const blob = JSON.parse(blobStr)
          // If blob has salt, require passphrase to derive key
          if(blob.salt){
            setLocked(true)
            setStatus('encrypted — enter passphrase to unlock')
            return
          }
          // Otherwise, try ephemeral key
          const eph = sessionStorage.getItem(EPHEMERAL_KEY)
          if(eph){
            const imported = await importEphemeralKeyFromBase64(eph)
            if(imported){
              try{
                const data = await decryptBlob(blob, imported)
                setRows(data)
                setStatus('unlocked (ephemeral)')
                setKey(imported)
                return
              }catch(e){
                // fallthrough
              }
            }
          }
          // can't decrypt
          setLocked(true)
          setStatus('encrypted — enter passphrase to unlock')
        }
      }catch(e){console.error(e)}
    })()
  },[])

  // Save encrypted whenever rows or persistLocal or key changes
  useEffect(()=>{
    (async ()=>{
      if(!key){
        // ensure there's an ephemeral key and use it
        const eph = sessionStorage.getItem(EPHEMERAL_KEY)
        let k = null
        if(eph){ k = await importEphemeralKeyFromBase64(eph) }
        if(!k){ k = await generateEphemeralKey() }
        setKey(k)
        // proceed to save below after key set
        return
      }
      try{
        const csvRows = rows || []
        const payload = csvRows
        // if passphrase-derived key was used, include salt in blob; otherwise null
        let salt = null
        // we detect derived key by checking if passphrase provided
        if(passphrase){
          // derive salt from stored blob if exists or generate new salt
          const existing = localStorage.getItem(STORAGE_KEY) || sessionStorage.getItem(STORAGE_KEY)
          if(existing){ try{ salt = JSON.parse(existing).salt }catch(e){} }
          if(!salt){ const s = crypto.getRandomValues(new Uint8Array(16)); salt = bufToBase64(s); }
        }
        const blob = await encryptJson(payload, key, salt)
        const blobStr = JSON.stringify(blob)
        if(persistLocal){ localStorage.setItem(STORAGE_KEY, blobStr); sessionStorage.removeItem(STORAGE_KEY) }
        else { sessionStorage.setItem(STORAGE_KEY, blobStr) }
      }catch(e){ console.error(e) }
    })()
  },[rows,persistLocal,key,passphrase])

  async function onFile(e){
    const f = e.target.files[0]
    if(!f) return
    Papa.parse(f,{header:true,skipEmptyLines:true,complete:(res)=>{ setRows(res.data) }})
  }

  function addRow(){ setRows([...rows, defaultRow()]) }

  function updateCell(ridx, keyField, value){
    const next = rows.map((r,i)=> i===ridx ? {...r,[keyField]:value} : r)
    setRows(next)
  }

  const [lastRemoved, setLastRemoved] = useState(null)
  const [toastVisible, setToastVisible] = useState(false)
  const toastTimerRef = useRef(null)
  function removeRow(i){
    const removed = rows[i]
    const next = rows.filter((_,idx)=>idx!==i)
    setRows(next)
    setLastRemoved({index:i,row:removed})
    // show toast and clear undo after 8s
    setToastVisible(true)
    if(toastTimerRef.current) clearTimeout(toastTimerRef.current)
    toastTimerRef.current = setTimeout(()=>{ setLastRemoved(null); setToastVisible(false); toastTimerRef.current=null }, 8000)
  }

  function undoRemove(){
    if(!lastRemoved) return
    const copy = [...rows]
    copy.splice(lastRemoved.index,0,lastRemoved.row)
    setRows(copy)
    setLastRemoved(null)
    setToastVisible(false)
    if(toastTimerRef.current){ clearTimeout(toastTimerRef.current); toastTimerRef.current=null }
  }

  function download(){ const csv = Papa.unparse(rows||[]); const blob=new Blob([csv],{type:'text/csv'}); const url=URL.createObjectURL(blob); const a=document.createElement('a'); a.href=url; a.download=`silver_stack_${new Date().toISOString().slice(0,10)}.csv`; a.click(); URL.revokeObjectURL(url); }

  async function tryFetch(){
    setStatus('fetching...')
    const endpoints = ['https://query1.finance.yahoo.com/v7/finance/quote?symbols=SI=F','https://query1.finance.yahoo.com/v7/finance/quote?symbols=SLV']
    for(const url of endpoints){
      try{ const res = await fetch(url); if(!res.ok) throw new Error('bad'); const j=await res.json(); const q=j?.quoteResponse?.result?.[0]; const p=q?.regularMarketPrice||q?.regularMarketPreviousClose; if(p!=null){ setSpot(parseFloat(p).toFixed(2)); setStatus('fetched'); return } }catch(e){}
    }
    setStatus('failed — enter manually')
  }

  function numericSafe(val){ const n = parseFloat(val); return Number.isFinite(n)?n:0 }
  function isValidNumberInput(v){ if(v===''||v==null) return true; return /^\d*\.?\d*$/.test(v) }

  const totalWeight = rows.reduce((s,r)=> s + numericSafe(r['Weight (troy oz)']),0)
  const totalPaid = rows.reduce((s,r)=> s + numericSafe(r['Price Paid ($)']),0)
  const totalMelt = rows.reduce((s,r)=> s + ((numericSafe(r['Weight (troy oz)']) * parseFloat(spot||0)) + numericSafe(r['Modifier ($)'])),0)

  async function setPassphraseAndDerive(){
    try{
      if(!passphrase){
        // no passphrase: ensure ephemeral key exists
        let eph = sessionStorage.getItem(EPHEMERAL_KEY)
        if(!eph){ await generateEphemeralKey(); setStatus('using ephemeral key (session-only)'); setLocked(false); }
        else { const k = await importEphemeralKeyFromBase64(eph); setKey(k); setLocked(false); setStatus('unlocked (ephemeral)') }
        return
      }
      // derive key from passphrase; generate salt and store in the blob when saving will use it
      const salt = crypto.getRandomValues(new Uint8Array(16))
      const k = await deriveKeyFromPassword(passphrase, salt)
      setKey(k)
      // Save salt into storage wrapper by re-encrypting immediately
      const saltB64 = bufToBase64(salt)
      const blob = await encryptJson(rows||[], k, saltB64)
      const blobStr = JSON.stringify(blob)
      if(persistLocal){ localStorage.setItem(STORAGE_KEY, blobStr); sessionStorage.removeItem(STORAGE_KEY) }
      else { sessionStorage.setItem(STORAGE_KEY, blobStr) }
      setLocked(false)
      setStatus('passphrase set — data encrypted')
    }catch(e){ console.error(e); setStatus('failed to set passphrase') }
  }

  async function unlockWithPassphrase(){
    try{
      const stored = localStorage.getItem(STORAGE_KEY) || sessionStorage.getItem(STORAGE_KEY)
      if(!stored) { setStatus('no data to unlock'); return }
      const blob = JSON.parse(stored)
      if(!blob.salt){ setStatus('no passphrase required for stored blob'); return }
      const saltBuf = base64ToBuf(blob.salt)
      const k = await deriveKeyFromPassword(passphrase, saltBuf)
      const data = await decryptBlob(blob, k)
      setKey(k)
      setRows(data)
      setLocked(false)
      setStatus('unlocked')
    }catch(e){ console.error(e); setStatus('unlock failed — wrong passphrase?') }
  }

  return (
    <Box>
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} md={6}>
              <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                <input ref={fileRef} type="file" accept="text/csv" onChange={onFile} style={{display:'inline-block'}} />
                <Button variant="contained" size="small" startIcon={<DownloadIcon/>} onClick={download}>Download</Button>
                {lastRemoved && (
                  <Button variant="outlined" color="warning" size="small" startIcon={<UndoIcon/>} onClick={undoRemove}>Undo remove</Button>
                )}
              </Box>
            </Grid>
            <Grid item xs={12} md={6}>
              <Box sx={{ display:'flex', justifyContent: 'flex-end', gap:2 }}>
                <Typography variant="body2" color="text.secondary">{status}</Typography>
                <Typography variant="body2">Persist:</Typography>
                <Switch checked={persistLocal} onChange={e=>setPersistLocal(e.target.checked)} />
              </Box>
            </Grid>
          </Grid>

          <Grid container spacing={2} alignItems="center" sx={{ mt:2 }}>
            <Grid item xs={12} md={8}>
              <Grid container spacing={1}>
                <Grid item>
                  <Card sx={{p:1, minWidth:120, bgcolor:'#0d6efd', color:'#fff'}}>
                    <Typography variant="caption">Spot</Typography>
                    <Typography variant="h6">${parseFloat(spot||0).toFixed(2)}</Typography>
                  </Card>
                </Grid>
                <Grid item>
                  <Card sx={{p:1, minWidth:140, bgcolor:'#16a34a', color:'#fff'}}>
                    <Typography variant="caption">Melt Value</Typography>
                    <Typography variant="h6">${totalMelt.toFixed(2)}</Typography>
                  </Card>
                </Grid>
                <Grid item>
                  <Card sx={{p:1, minWidth:120, bgcolor:'#06b6d4', color:'#fff'}}>
                    <Typography variant="caption">Total oz</Typography>
                    <Typography variant="h6">{totalWeight.toFixed(2)}</Typography>
                  </Card>
                </Grid>
                <Grid item>
                  <Card sx={{p:1, minWidth:120, bgcolor: (totalMelt - totalPaid)>=0 ? '#16a34a' : '#dc2626', color:'#fff'}}>
                    <Typography variant="caption">P/L</Typography>
                    <Typography variant="h6">${(totalMelt - totalPaid).toFixed(2)}</Typography>
                  </Card>
                </Grid>
              </Grid>
            </Grid>
            <Grid item xs={12} md={4}>
              <Box>
                <TextField size="small" label="Spot Price" value={spot} onChange={e=>setSpot(e.target.value)} sx={{width: '100%'}} />
                <Box sx={{mt:1}}>
                  <Slider min={0} max={500} step={0.01} value={Number(spot||0)} onChange={(_,v)=>setSpot(v)} />
                </Box>
                <Box sx={{mt:1, display:'flex', gap:1}}>
                  <Button variant="outlined" size="small" onClick={tryFetch}>Fetch Spot</Button>
                </Box>
              </Box>
            </Grid>
          </Grid>

          <Box sx={{ mt:2 }}>
            <Typography variant="body2" sx={{ mb:1 }}>Encryption passphrase (optional — set to persist across devices)</Typography>
            <Box sx={{ display:'flex', gap:1 }}>
              <TextField type="password" size="small" placeholder="Enter passphrase to encrypt/decrypt" value={passphrase} onChange={e=>setPassphrase(e.target.value)} />
              <Button variant="outlined" size="small" onClick={setPassphraseAndDerive}>Set Passphrase</Button>
              <Button variant="outlined" size="small" onClick={unlockWithPassphrase}>Unlock</Button>
            </Box>
            {locked && <Typography variant="body2" color="error" sx={{ mt:1 }}>Data is encrypted. Enter passphrase and click Unlock to load stored inventory.</Typography>}
          </Box>

          <Box sx={{ mt:2 }}>
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Description</TableCell>
                    <TableCell>Weight (troy oz)</TableCell>
                    <TableCell>Date Acquired</TableCell>
                    <TableCell>Price Paid ($)</TableCell>
                    <TableCell>Modifier ($)</TableCell>
                    <TableCell>Melt Value ($)</TableCell>
                    <TableCell></TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {rows.map((r,i)=> (
                    <TableRow key={i}>
                      <TableCell>
                        <TextField size="small" value={r['Description']||''} onChange={e=>updateCell(i,'Description',e.target.value)} fullWidth />
                      </TableCell>
                      <TableCell>
                        <TextField size="small" value={r['Weight (troy oz)']||''} error={!isValidNumberInput(r['Weight (troy oz)'])} helperText={!isValidNumberInput(r['Weight (troy oz)'])? 'Enter a valid number' : ''} onChange={e=>{ const v=e.target.value; if(v===''||/^\d*\.?\d*$/.test(v)) updateCell(i,'Weight (troy oz)',v)}} />
                      </TableCell>
                      <TableCell>
                        <TextField size="small" value={r['Date Acquired']||''} onChange={e=>updateCell(i,'Date Acquired',e.target.value)} placeholder="YYYY-MM-DD" />
                      </TableCell>
                      <TableCell>
                        <TextField size="small" value={r['Price Paid ($)']||''} error={!isValidNumberInput(r['Price Paid ($)'])} helperText={!isValidNumberInput(r['Price Paid ($)'])? 'Enter a valid number' : ''} onChange={e=>{ const v=e.target.value; if(v===''||/^\d*\.?\d*$/.test(v)) updateCell(i,'Price Paid ($)',v)}} />
                      </TableCell>
                      <TableCell>
                        <TextField size="small" value={r['Modifier ($)']||''} error={!isValidNumberInput(r['Modifier ($)'])} helperText={!isValidNumberInput(r['Modifier ($)'])? 'Enter a valid number' : ''} onChange={e=>{ const v=e.target.value; if(v===''||/^\d*\.?\d*$/.test(v)) updateCell(i,'Modifier ($)',v)}} />
                      </TableCell>
                      <TableCell>{((numericSafe(r['Weight (troy oz)'])*parseFloat(spot||0))+numericSafe(r['Modifier ($)'])).toFixed(2)}</TableCell>
                      <TableCell>
                        <IconButton size="small" color="error" onClick={()=>removeRow(i)}><DeleteIcon/></IconButton>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Box>

          <Box sx={{ mt:2, display:'flex', justifyContent:'space-between', alignItems:'center' }}>
            <Button variant="contained" startIcon={<AddIcon/>} onClick={addRow}>Add Row</Button>
            <Box sx={{ textAlign:'right' }}>
              <Typography>Total Weight: <strong>{totalWeight.toFixed(2)}</strong></Typography>
              <Typography>Current Melt Value: <strong>${totalMelt.toFixed(2)}</strong></Typography>
              <Typography>Profit/Loss: <strong>${(totalMelt - totalPaid).toFixed(2)}</strong></Typography>
            </Box>
          </Box>
        </CardContent>
      </Card>

      <Snackbar open={toastVisible} anchorOrigin={{vertical:'bottom', horizontal:'right'}} onClose={()=>{ setToastVisible(false); setLastRemoved(null) }} action={
        <Button color="inherit" size="small" startIcon={<UndoIcon/>} onClick={undoRemove}>Undo</Button>
      }>
        <Alert severity="info">Row removed</Alert>
      </Snackbar>
    </Box>
  )
}
