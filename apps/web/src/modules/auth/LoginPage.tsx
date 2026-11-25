import { LogIn } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { errorText } from "@/components/feedback/states";
import { Button, Field } from "@/components/ui/primitives";
import { api } from "@/services/api";
import { useAuth } from "@/stores/auth";

const DEMO = [
  ["Administrador", "admin@edumaster.ai"], ["Estudiante", "estudiante@edumaster.ai"], ["Docente", "docente@edumaster.ai"], ["Coordinador", "coordinador@edumaster.ai"],
  ["ML Engineer", "ml@edumaster.ai"], ["Analista", "analista@edumaster.ai"], ["Auditor", "auditor@edumaster.ai"], ["Superadmin", "superadmin@edumaster.ai"],
];

/** Pequeña red decorativa estática en el login (no simula actividad: no hay datos aquí). */
function Constellation() {
  const cols = [4, 6, 6, 3];
  const pts = cols.flatMap((n, c) => Array.from({ length: n }, (_, i) => [60 + c * 110, 40 + ((i + 0.5) * 300) / n, c] as const));
  return (
    <svg viewBox="0 0 450 340" className="w-full max-w-md" aria-hidden>
      {pts.map(([x1, y1, c1], i) => pts.filter(([, , c2]) => c2 === c1 + 1).map(([x2, y2], j) => (
        <path key={`${i}-${j}`} d={`M${x1},${y1} C${(x1 + x2) / 2},${y1} ${(x1 + x2) / 2},${y2} ${x2},${y2}`} stroke="rgba(140,100,255,.18)" fill="none" />
      )))}
      {pts.map(([x, y, c], i) => <circle key={i} cx={x} cy={y} r={7} fill={["#FF5FD2", "#7C5CFF", "#FF9F43", "#2DE2A6"][c]} style={{ filter: "drop-shadow(0 0 8px currentColor)" }} />)}
    </svg>
  );
}

const DEMO_PW = (import.meta.env.VITE_DEMO_PASSWORD as string | undefined) ?? (import.meta.env.DEV ? "EduMaster#2026" : "");

export function LoginPage() {
  const nav = useNavigate();
  const { setTokens, setMe } = useAuth();
  const [email, setEmail] = useState("admin@edumaster.ai");
  const [password, setPassword] = useState(DEMO_PW);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const t = await api("/auth/login", { body: { email, password } });
      setTokens(t.access_token, t.refresh_token);
      setMe(await api("/auth/me"));
      nav("/");
    } catch (e) {
      setErr(errorText(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="grid min-h-full lg:grid-cols-[1.1fr_1fr]">
      <div className="relative hidden flex-col justify-between overflow-hidden p-12 lg:flex">
        <div className="flex items-center gap-3"><img src="/favicon.svg" className="size-11" alt="" /><span className="font-display text-2xl font-semibold">EduMaster<span className="text-cyan">.ai</span></span></div>
        <div>
          <h1 className="font-display max-w-lg text-[44px] leading-[1.08] font-semibold">Aprende, practica y destaca con IA que puedes ver por dentro.</h1>
          <p className="mt-4 max-w-md text-[15px] text-mist">Gestión académica, analítica en tiempo real y cinco redes neuronales gobernadas: cada predicción con versión, fuente y nivel de confianza.</p>
        </div>
        <Constellation />
      </div>
      <div className="flex items-center justify-center p-6">
        <form onSubmit={submit} className="panel panel-glow w-full max-w-md p-7" aria-labelledby="login-title">
          <h2 id="login-title" className="font-display text-2xl font-semibold">Iniciar sesión</h2>
          <p className="mt-1 mb-5 text-[13px] text-mist">Entorno de demostración con datos sintéticos rotulados.</p>
          <div className="grid gap-4">
            <Field label="Correo institucional"><input type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required /></Field>
            <Field label="Contraseña"><input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6} /></Field>
            {err && <p role="alert" className="rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-[13px] text-danger">{err}</p>}
            <Button type="submit" loading={busy} className="w-full"><LogIn /> Entrar</Button>
          </div>
          <div className="mt-6 border-t border-line/60 pt-4">
            <p className="mb-2 text-[12px] text-mist">Cuentas demo{DEMO_PW ? ` (contraseña ${DEMO_PW})` : " (contraseña entregada por administración)"}:</p>
            <div className="flex flex-wrap gap-1.5">
              {DEMO.map(([r, e]) => (
                <button type="button" key={e} onClick={() => { setEmail(e); if (DEMO_PW) setPassword(DEMO_PW); }}
                  className={`rounded-full border px-2.5 py-1 text-[12px] ${email === e ? "border-cyan bg-cyan/15 text-frost" : "border-line text-mist hover:text-frost"}`}>{r}</button>
              ))}
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
