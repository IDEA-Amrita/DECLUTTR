import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('electron', {
  openDirectory: () => ipcRenderer.invoke('dialog:openDirectory'),
  openExternal: (url: string) => ipcRenderer.invoke('shell:openExternal', url),
})
interface Window {
  electron?: {
    openDirectory: () => Promise<string | null>
    openExternal: (url: string) => Promise<void>
  }
}