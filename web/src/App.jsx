import React from 'react';
import { Link, NavLink, Route, Routes } from 'react-router-dom';
import { Activity, BarChart3, BookOpen, Cpu, Image as ImageIcon, Play } from 'lucide-react';
import LeaderboardPage from './routes/LeaderboardPage.jsx';
import PracticePage from './routes/PracticePage.jsx';
import RunsPage from './routes/RunsPage.jsx';
import ModelsPage from './routes/ModelsPage.jsx';
import SamplesPage from './routes/SamplesPage.jsx';
import AboutPage from './routes/AboutPage.jsx';
import NotFoundPage from './routes/NotFoundPage.jsx';

const NAV = [
  { to: '/', label: 'Leaderboard', icon: BarChart3, end: true },
  { to: '/practice', label: 'Practice', icon: Play },
  { to: '/runs', label: 'Runs', icon: Activity },
  { to: '/models', label: 'Models', icon: Cpu },
  { to: '/samples', label: 'Samples', icon: ImageIcon },
  { to: '/about', label: 'About', icon: BookOpen },
];

export default function App() {
  return (
    <div className="min-h-full flex flex-col">
      <header className="sticky top-0 z-40 backdrop-blur bg-white/80 border-b border-gray-100">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <Link to="/" className="font-semibold tracking-tight text-gray-900">
            Likeness <span className="text-gray-400">Detector</span>
          </Link>
          <nav className="flex items-center gap-1">
            {NAV.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  `inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-colors
                  ${isActive ? 'bg-gray-100 text-gray-900' : 'text-gray-500 hover:text-gray-900 hover:bg-gray-50'}`
                }
              >
                <Icon size={14} />
                <span className="hidden sm:inline">{label}</span>
              </NavLink>
            ))}
          </nav>
        </div>
      </header>

      <main className="flex-1">
        <Routes>
          <Route path="/" element={<LeaderboardPage />} />
          <Route path="/benchmark/:id" element={<LeaderboardPage />} />
          <Route path="/practice" element={<PracticePage />} />
          <Route path="/runs" element={<RunsPage />} />
          <Route path="/models" element={<ModelsPage />} />
          <Route path="/samples" element={<SamplesPage />} />
          <Route path="/about" element={<AboutPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </main>

      <footer className="border-t border-gray-100 py-6 text-xs text-center text-gray-400">
        likeness-bench · MCQ identity-likeness for vision-language models
      </footer>
    </div>
  );
}
