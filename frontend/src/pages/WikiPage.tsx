import { Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import WikiList from '../components/wiki/WikiList'

export default function WikiPage() {
  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-[1200px] mx-auto">
        <div className="flex items-center gap-3 mb-6">
          <Link
            to="/"
            className="text-content-secondary hover:text-content-primary transition-colors"
          >
            <ArrowLeft size={20} />
          </Link>
          <h1 className="text-xl font-bold text-content-primary">Personal Wiki</h1>
        </div>
        <WikiList />
      </div>
    </div>
  )
}
