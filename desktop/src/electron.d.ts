interface Window {
  electron?: {
    openDirectory: () => Promise<string | null>
    openExternal: (url: string) => Promise<void>
  }
}
