interface Window {
  electron?: {
    openDirectory: () => Promise<string | null>
  }
}
