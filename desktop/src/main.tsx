import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
// @ts-ignore: side-effect CSS import without type declarations
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
