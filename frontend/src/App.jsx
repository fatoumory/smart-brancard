import { ShieldCheck, UserCheck } from 'lucide-react';

function App() {
  return (
    <div className="min-h-screen bg-slate-900 text-white flex flex-col items-center justify-center p-4">
      <div className="flex items-center gap-2 mb-4">
        <ShieldCheck className="w-10 h-10 text-emerald-400" />
        <h1 className="text-3xl font-bold tracking-wide">Smart Brancard</h1>
      </div>
      <p className="text-slate-400 flex items-center gap-2">
        <UserCheck className="w-5 h-5 text-blue-400" /> Tailwind CSS, Lucide & React Router sont prêts !
      </p>
    </div>

  );
}

export default App
