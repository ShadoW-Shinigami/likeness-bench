import React from 'react';
import { Link } from 'react-router-dom';

export default function NotFoundPage() {
  return (
    <section className="max-w-md mx-auto px-6 py-20 text-center">
      <h1 className="text-3xl font-semibold tracking-tight">404</h1>
      <p className="text-sm text-gray-500 mt-2">No such page.</p>
      <Link to="/" className="inline-block mt-4 text-sm px-3 py-1.5 bg-black text-white rounded hover:bg-gray-800">
        Back to leaderboard
      </Link>
    </section>
  );
}
