import { Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import SandboxStatus from '../components/sandbox/SandboxStatus'
import ArtifactsPanel from '../components/sandbox/ArtifactsPanel'

export default function SandboxPage() {
  return (
    <div className="min-h-screen bg-slate-900 p-6">
      <div className="max-w-4xl mx-auto space-y-4">
        <div className="flex items-center gap-3">
          <Link to="/" className="text-slate-400 hover:text-white transition-colors">
            <ArrowLeft size={20} />
          </Link>
          <h1 className="text-xl font-bold text-white">Sandbox</h1>
        </div>
        <SandboxStatus />
        <ArtifactsPanel />
      </div>
    </div>
  )
}
