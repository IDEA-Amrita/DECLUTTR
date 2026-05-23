import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import { Home, HardDrive, Image, BarChart2 } from 'lucide-react'
import { Dashboard } from './pages/Dashboard'
import { StoragePage } from './pages/StoragePage'
import { PhotoPickerPage } from './pages/PhotoPickerPage'
import { ReportPage } from './pages/ReportPage'

const navItems = [
  { to: '/',        icon: Home,      label: 'Home'    },
  { to: '/storage', icon: HardDrive, label: 'Storage' },
  { to: '/photos',  icon: Image,     label: 'Photos'  },
  { to: '/report',  icon: BarChart2, label: 'Report'  },
]

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen" style={{ background: '#0D0D0F' }}>
        <nav
          className="w-16 flex flex-col items-center py-6 gap-2 shrink-0"
          style={{ background: '#161618', borderRight: '1px solid #2A2A2E' }}
        >
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex flex-col items-center gap-1 p-2.5 rounded-lg w-12 transition-colors ${
                  isActive ? '' : 'hover:bg-[#2A2A2E]'
                }`
              }
              style={({ isActive }) => ({
                color: isActive ? '#7B61FF' : '#8A8A96',
                background: isActive ? '#7B61FF22' : undefined,
              })}
              title={label}
            >
              <Icon size={20} />
              <span style={{ fontSize: 9, fontFamily: 'DM Mono' }}>{label}</span>
            </NavLink>
          ))}
        </nav>

        <main className="flex-1 overflow-y-auto">
          <Routes>
            <Route path="/"        element={<Dashboard />} />
            <Route path="/storage" element={<StoragePage />} />
            <Route path="/photos"  element={<PhotoPickerPage />} />
            <Route path="/report"  element={<ReportPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
