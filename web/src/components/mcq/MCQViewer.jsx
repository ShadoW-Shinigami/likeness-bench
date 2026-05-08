import React from 'react';
import clsx from 'clsx';
import { CheckCircle, XCircle, Sparkles, Slash } from 'lucide-react';
import ImageWithSkeleton from '../shared/ImageWithSkeleton.jsx';
import { api } from '../../utils/api.js';

const LETTERS = ['A', 'B', 'C', 'D', 'E'];

export default function MCQViewer({
  benchmarkId,
  sample,
  selected,
  revealed,
  onSelect,
}) {
  if (!sample) return null;
  const { id, options, correct_answer } = sample;
  const baseUrl = api.imageUrl(benchmarkId, id, sample.base_image);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
      <div className="lg:col-span-7">
        <div className="rounded-2xl border border-gray-200 bg-white aspect-square overflow-hidden shadow-[0_2px_8px_rgba(0,0,0,0.04)]">
          <ImageWithSkeleton src={baseUrl} alt="Reference" className="w-full h-full" />
        </div>
        <p className="mt-3 text-xs text-gray-500 uppercase tracking-wider">Reference</p>
      </div>

      <div className="lg:col-span-5 grid grid-cols-2 gap-3 content-start">
        {LETTERS.slice(0, 4).map((letter) => {
          const opt = options[letter];
          if (!opt) return null;
          const url = api.imageUrl(benchmarkId, id, opt.image);
          return (
            <Tile
              key={letter}
              letter={letter}
              url={url}
              tier={opt.similarity_tier}
              showSynthBadge={
                opt.generated_by?.includes('nano-banana')
                || opt.source?.includes('synthetic_inpaint')
                || opt.source?.includes('nb2')
              }
              selected={selected === letter}
              correct={revealed && correct_answer === letter}
              wrongSelected={revealed && selected === letter && correct_answer !== letter}
              dimmed={revealed && selected !== letter && correct_answer !== letter}
              disabled={revealed}
              onClick={() => onSelect?.(letter)}
            />
          );
        })}
        <NoneOfAboveTile
          letter="E"
          selected={selected === 'E'}
          correct={revealed && correct_answer === 'E'}
          wrongSelected={revealed && selected === 'E' && correct_answer !== 'E'}
          dimmed={revealed && selected !== 'E' && correct_answer !== 'E'}
          disabled={revealed}
          onClick={() => onSelect?.('E')}
        />
      </div>
    </div>
  );
}

function Tile({ letter, url, tier, showSynthBadge, selected, correct, wrongSelected, dimmed, disabled, onClick }) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      aria-pressed={selected}
      className={clsx(
        'group relative aspect-square rounded-xl border bg-white text-left overflow-hidden transition-all',
        !disabled && 'hover:border-gray-400 hover:shadow-md',
        selected && !correct && !wrongSelected && 'border-black ring-2 ring-black/30',
        correct && 'border-emerald-500 bg-emerald-50 ring-1 ring-emerald-500',
        wrongSelected && 'border-red-400 bg-red-50',
        dimmed && 'border-gray-100 opacity-50 bg-gray-50',
        !selected && !correct && !wrongSelected && !dimmed && 'border-gray-200',
      )}
    >
      <ImageWithSkeleton src={url} alt={`Candidate ${letter}`} className="w-full h-full" />
      <div className="absolute top-2 left-2">
        <span className={clsx(
          'w-6 h-6 inline-flex items-center justify-center rounded text-xs font-bold',
          correct ? 'bg-emerald-200 text-emerald-800'
            : wrongSelected ? 'bg-red-200 text-red-700'
            : 'bg-white/90 backdrop-blur text-gray-700 border border-gray-200',
        )}>{letter}</span>
      </div>
      {tier && (
        <span className="absolute top-2 right-2 px-1.5 py-0.5 text-[10px] bg-white/90 backdrop-blur border border-gray-200 rounded">
          {tier}
        </span>
      )}
      {showSynthBadge && (
        <span className="absolute bottom-2 left-2 inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 bg-purple-100 text-purple-700 rounded">
          <Sparkles size={10} /> SynthID
        </span>
      )}
      {correct && <CheckCircle size={18} className="absolute bottom-2 right-2 text-emerald-600" />}
      {wrongSelected && <XCircle size={18} className="absolute bottom-2 right-2 text-red-500" />}
    </button>
  );
}

function NoneOfAboveTile({ letter, selected, correct, wrongSelected, dimmed, disabled, onClick }) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      aria-pressed={selected}
      className={clsx(
        'col-span-2 aspect-[4/1] rounded-xl border-2 border-dashed bg-white text-left transition-all flex items-center justify-center gap-3 px-4',
        !disabled && 'hover:border-gray-500 hover:bg-gray-50',
        selected && !correct && !wrongSelected && 'border-black ring-2 ring-black/30',
        correct && 'border-emerald-500 bg-emerald-50 ring-1 ring-emerald-500',
        wrongSelected && 'border-red-400 bg-red-50',
        dimmed && 'border-gray-200 opacity-50',
        !selected && !correct && !wrongSelected && !dimmed && 'border-gray-300',
      )}
    >
      <span className={clsx(
        'w-6 h-6 inline-flex items-center justify-center rounded text-xs font-bold',
        correct ? 'bg-emerald-200 text-emerald-800'
          : wrongSelected ? 'bg-red-200 text-red-700'
          : 'bg-gray-100 text-gray-700',
      )}>{letter}</span>
      <Slash size={16} className="text-gray-400" />
      <span className="text-sm font-medium text-gray-700">None of the above</span>
      {correct && <CheckCircle size={18} className="ml-auto text-emerald-600" />}
      {wrongSelected && <XCircle size={18} className="ml-auto text-red-500" />}
    </button>
  );
}
