import React from 'react'
import TableEditor from './components/TableEditor'
import { ThemeProvider, createTheme } from '@mui/material/styles'
import CssBaseline from '@mui/material/CssBaseline'
import Container from '@mui/material/Container'
import Typography from '@mui/material/Typography'

const theme = createTheme({ palette: { mode: 'light' } })

export default function App(){
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Container maxWidth="lg" style={{paddingTop:20, paddingBottom:40}}>
        <div className="d-flex justify-content-between align-items-center mb-3">
          <Typography variant="h5" component="h1">Silver Tracker</Typography>
          <Typography variant="body2" color="textSecondary">Privacy-first — client-side only</Typography>
        </div>
        <div className="row">
          <div className="col-lg-8">
            <TableEditor />
          </div>
        </div>
        <footer className="mt-4 text-muted small">© Private App — data stays in your browser unless you download it.</footer>
      </Container>
    </ThemeProvider>
  )
}
