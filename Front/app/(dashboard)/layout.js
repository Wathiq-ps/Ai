'use client'

import { LanguageProvider } from '@/context/LanguageContext'
import { SidebarProvider }  from '@/context/SidebarContext'
import { Sidebar }          from '@/components/dashboard/Sidebar'
import { TopBar }           from '@/components/dashboard/TopBar'
import { AdminGuard }       from '@/components/dashboard/AdminGuard'

export default function DashboardLayout({ children }) {
  return (
    <LanguageProvider>
      <SidebarProvider>
        <div className="dashboard-root">
          <Sidebar />
          <div className="main-area">
            <TopBar />
            <main className="main-content">
              <AdminGuard>{children}</AdminGuard>
            </main>
          </div>
        </div>
      </SidebarProvider>
    </LanguageProvider>
  )
}
