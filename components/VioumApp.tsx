"use client";

import Image from "next/image";
import {
  ArrowRight, BookOpen, Brain, CaretDown, ChatCircleDots, CheckCircle, Globe,
  ClockCounterClockwise, Copy, FileText, GraduationCap, House, Info,
  List, LockKey, PaperPlaneTilt, Paperclip, Plus, Scan, ShieldCheck,
  Sparkle, TextAa, Trash, WarningCircle, X,
} from "@phosphor-icons/react";
import { FormEvent, useEffect, useRef, useState } from "react";

type Message = { role: "user" | "assistant"; content: string };
type Attachment = { name: string; mime: string; data: string; preview?: string };
type Chat = { id: string; title: string; messages: Message[]; learning: boolean; updated: number };
type Language = "fr" | "en" | "ee";
type FontMode = "soft" | "modern" | "classic";

const STARTERS = [
  { icon: WarningCircle, tone: "violet", title: "Dépôt par erreur", text: "On me demande de renvoyer un transfert reçu par erreur. Est-ce une arnaque ?" },
  { icon: Scan, tone: "blue", title: "Analyser une capture", text: "Je souhaite analyser la capture d’un SMS Mobile Money suspect." },
  { icon: ShieldCheck, tone: "cyan", title: "Bons réflexes", text: "Quels sont les bons réflexes pour repérer une arnaque Mobile Money ?" },
];

function cleanTitle(text: string) {
  return text.replace(/^\//, "").replace(/\s+/g, " ").trim().slice(0, 38) || "Analyse de message";
}

export default function VioumApp() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [learning, setLearning] = useState(false);
  const [course, setCourse] = useState("");
  const [attachment, setAttachment] = useState<Attachment | null>(null);
  const [busy, setBusy] = useState(false);
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [history, setHistory] = useState<Chat[]>([]);
  const [chatId, setChatId] = useState(() => crypto.randomUUID());
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [language, setLanguage] = useState<Language>("fr");
  const [fontMode, setFontMode] = useState<FontMode>("soft");
  const fileRef = useRef<HTMLInputElement>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    try {
      setHistory(JSON.parse(localStorage.getItem("vioum-chats") || "[]"));
      setLanguage((localStorage.getItem("vioum-language") as Language) || "fr");
      setFontMode((localStorage.getItem("vioum-font") as FontMode) || "soft");
    } catch { setHistory([]); }
    fetch("/api/health").then((r) => r.json()).then((d) => setConfigured(Boolean(d.configured))).catch(() => setConfigured(false));
  }, []);
  useEffect(() => { localStorage.setItem("vioum-language", language); }, [language]);
  useEffect(() => { localStorage.setItem("vioum-font", fontMode); }, [fontMode]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, busy]);

  function saveChat(next: Message[], mode = learning) {
    const title = cleanTitle(next.find((m) => m.role === "user")?.content || "Conversation");
    const chat: Chat = { id: chatId, title, messages: next.slice(-30), learning: mode, updated: Date.now() };
    const updated = [chat, ...history.filter((c) => c.id !== chatId)].slice(0, 12);
    setHistory(updated);
    localStorage.setItem("vioum-chats", JSON.stringify(updated));
  }

  function reset() {
    setMessages([]); setInput(""); setLearning(false); setCourse(""); setAttachment(null);
    setChatId(crypto.randomUUID()); setSidebarOpen(false);
  }

  function loadChat(chat: Chat) {
    setMessages(chat.messages); setLearning(chat.learning); setCourse(""); setAttachment(null);
    setChatId(chat.id); setSidebarOpen(false);
  }

  async function onFile(file?: File) {
    if (!file) return;
    if (file.size > 8 * 1024 * 1024) return alert("Le fichier dépasse 8 Mo.");
    if (!learning && (file.type === "application/pdf" || file.type === "text/plain")) {
      setInput("/apprendre");
      return alert("Activez d’abord le mode apprentissage, puis ajoutez votre cours.");
    }
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result);
      setAttachment({ name: file.name, mime: file.type || "text/plain", data: result.split(",")[1], preview: file.type.startsWith("image/") ? result : undefined });
    };
    reader.readAsDataURL(file);
  }

  async function send(text = input) {
    const content = text.trim();
    if (busy || (!content && !attachment)) return;
    const userMessage: Message = { role: "user", content: content || (learning ? "Étudie ce cours." : "Analyse cette capture.") };
    const pending = [...messages, userMessage];
    setMessages(pending); setInput(""); setBusy(true);
    try {
      const response = await fetch("/api/chat", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: pending, learning, course, attachment, language }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Vioum ne répond pas pour le moment.");
      const complete = [...pending, { role: "assistant", content: data.reply } as Message];
      setMessages(complete); setLearning(Boolean(data.learning)); setCourse(data.course || ""); setAttachment(null);
      saveChat(complete, Boolean(data.learning));
    } catch (error) {
      const complete = [...pending, { role: "assistant", content: error instanceof Error ? error.message : "Une erreur est survenue." } as Message];
      setMessages(complete); saveChat(complete);
    } finally { setBusy(false); }
  }

  function submit(event: FormEvent) { event.preventDefault(); send(); }

  return (
    <div className={`app-shell font-${fontMode}`}>
      <aside className={`sidebar ${sidebarOpen ? "open" : ""}`}>
        <div className="brand"><Image src="/logo.webp" width={42} height={42} alt="Logo Vioum" priority /><span>Vioum</span></div>
        <button className="new-chat" onClick={reset}><Plus size={18} weight="bold" /> Nouvelle analyse <ArrowRight size={16} /></button>
        <p className="nav-label">ESPACE DE TRAVAIL</p>
        <nav>
          <button className={!learning ? "nav-active" : ""} onClick={() => learning ? send("/stop") : setSidebarOpen(false)}><House size={19} /> Tableau de bord</button>
          <button className={!learning ? "nav-active secondary" : "secondary"} onClick={() => setSidebarOpen(false)}><Scan size={19} /> Scanner <span className="pill">IA</span></button>
          <button className={learning ? "nav-active" : ""} onClick={() => { setInput("/apprendre"); setSidebarOpen(false); }}><GraduationCap size={19} /> Apprendre <span className="shortcut">/</span></button>
        </nav>
        <div className="history-title"><p className="nav-label">CONVERSATIONS</p><button aria-label="Effacer l’historique" onClick={() => { setHistory([]); localStorage.removeItem("vioum-chats"); }}><Trash size={15} /></button></div>
        <div className="history-list">
          {history.length ? history.map((chat) => <button key={chat.id} onClick={() => loadChat(chat)}><ChatCircleDots size={16} /><span>{chat.title}</span></button>) : <p>Aucune conversation enregistrée.</p>}
        </div>
        <div className="security-card"><LockKey size={24} /><strong>Gardez vos codes secrets.</strong><p>Vioum ne vous demandera jamais votre PIN ou votre OTP.</p></div>
        <div className="sidebar-footer"><div className="status-avatar">V</div><div><strong>Vioum Protect</strong><small>Vos échanges sur cet appareil</small></div><span className="online-dot" /></div>
      </aside>

      <div className="main-area">
        <header className="topbar">
          <div className="topbar-left"><button className="mobile-menu" onClick={() => setSidebarOpen(true)} aria-label="Ouvrir le menu"><List size={22} /></button><div><span>{learning ? "Espace apprentissage" : "Tableau de bord"}</span><small> / {messages.length ? "Conversation active" : "Nouvelle analyse"}</small></div></div>
          <div className="topbar-actions"><span className={`api-status ${configured ? "ready" : ""}`}><span />{configured === null ? "Connexion…" : configured ? "Gemma connecté" : "Clé à configurer"}</span><label className="preference" title="Langue de réponse"><Globe size={16} /><select value={language} onChange={(e) => setLanguage(e.target.value as Language)} aria-label="Choisir la langue"><option value="fr">Français</option><option value="en">English</option><option value="ee">Eʋegbe</option></select><CaretDown size={12} /></label><label className="preference font-choice" title="Police d’affichage"><TextAa size={17} /><select value={fontMode} onChange={(e) => setFontMode(e.target.value as FontMode)} aria-label="Choisir la police"><option value="soft">Moderne</option><option value="modern">Nette</option><option value="classic">Classique</option></select><CaretDown size={12} /></label><button aria-label="Aide" onClick={() => setHelpOpen(true)}><Info size={21} /></button><div className="avatar"><Image src="/logo.webp" width={34} height={34} alt="" /></div></div>
        </header>

        <main className={messages.length ? "chat-main" : "dashboard-main"}>
          {!messages.length ? (
            <>
              <section className="hero-card">
                <div><span className="hero-kicker"><Sparkle size={14} weight="fill" /> PROTECTION MOBILE MONEY</span><h1>Un doute sur un message ?<br /><b>Vioum vous aide à voir clair.</b></h1><p>Collez un SMS ou ajoutez une capture. Gemma repère les indices suspects et vous conseille en français simple.</p><button onClick={() => document.getElementById("message-box")?.focus()}>Commencer l’analyse <ArrowRight size={17} weight="bold" /></button></div>
                <div className="hero-mark"><Image src="/logo.webp" width={150} height={110} alt="Mascotte Vioum" /></div>
              </section>

              <div className="stats-grid">
                <article><div className="stat-icon violet"><Scan size={21} /></div><div><small>ANALYSE</small><strong>Texte & capture</strong><p>SMS, WhatsApp, Mobile Money</p></div><CheckCircle size={20} color="#3bb58f" weight="fill" /></article>
                <article><div className="stat-icon blue"><Brain size={21} /></div><div><small>MODÈLE</small><strong>Gemma 4</strong><p>Analyse contextuelle multimodale</p></div><CheckCircle size={20} color="#3bb58f" weight="fill" /></article>
                <article><div className="stat-icon cyan"><LockKey size={21} /></div><div><small>CONFIDENTIALITÉ</small><strong>Fichiers éphémères</strong><p>Aucun stockage côté serveur</p></div><CheckCircle size={20} color="#3bb58f" weight="fill" /></article>
              </div>

              <section className="workspace-grid">
                <div className="start-panel"><div className="section-heading"><div><span>ANALYSE RAPIDE</span><h2>Que souhaitez-vous vérifier ?</h2></div><ShieldCheck size={30} color="#6f63e8" /></div><div className="starter-grid">{STARTERS.map(({ icon: Icon, tone, title, text }) => <button key={title} onClick={() => setInput(text)}><span className={`starter-icon ${tone}`}><Icon size={23} /></span><strong>{title}</strong><p>{text}</p><span className="starter-link">Commencer <ArrowRight size={14} /></span></button>)}</div></div>
                <aside className="learn-panel"><div className="learn-icon"><BookOpen size={27} /></div><span>NOUVEAU</span><h2>Révisez vos cours avec Vioum</h2><p>Ajoutez un PDF, une photo ou vos notes. Créez un résumé, un plan ou un quiz personnalisé.</p><button onClick={() => setInput("/apprendre")}>Activer /apprendre <ArrowRight size={15} /></button><div className="command-list"><span><FileText size={16} /> /resume</span><span><ClockCounterClockwise size={16} /> /plan</span><span><Brain size={16} /> /quiz</span></div></aside>
              </section>
            </>
          ) : (
            <section className="conversation">
              <div className="conversation-head"><div><span>{learning ? "SESSION D’ÉTUDE" : "ANALYSE EN COURS"}</span><h1>{learning ? "Apprendre avec Vioum" : "Analyse de sécurité"}</h1></div>{learning && <button onClick={() => send("/stop")}>Quitter /stop</button>}</div>
              <div className="message-list">{messages.map((message, index) => <article key={index} className={`message ${message.role}`}><div className="message-avatar">{message.role === "assistant" ? <Image src="/logo.webp" width={28} height={28} alt="" /> : "V"}</div><div><strong>{message.role === "assistant" ? "Vioum" : "Vous"}</strong><p>{message.content}</p>{message.role === "assistant" && <button onClick={() => navigator.clipboard.writeText(message.content)}><Copy size={14} /> Copier</button>}</div></article>)}{busy && <article className="message assistant loading"><div className="message-avatar"><Image src="/logo.webp" width={28} height={28} alt="" /></div><div><strong>Vioum</strong><p>Analyse en cours<span>…</span></p></div></article>}<div ref={endRef} /></div>
            </section>
          )}
        </main>

        <footer className="composer-wrap">
          <div className="composer">
            {learning && <div className="learning-bar"><span><GraduationCap size={17} /> Mode apprentissage</span><div><button onClick={() => send("/resume")}>Résumé</button><button onClick={() => send("/plan")}>Plan</button><button onClick={() => send("/quiz")}>Quiz</button></div></div>}
            {attachment && <div className="attachment-chip">{attachment.preview ? <Image src={attachment.preview} width={42} height={42} alt="Aperçu" unoptimized /> : <FileText size={24} />}<span>{attachment.name}</span><button onClick={() => setAttachment(null)} aria-label="Retirer le fichier"><X size={16} /></button></div>}
            <form onSubmit={submit}><textarea id="message-box" value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }} placeholder={learning ? "Posez une question sur votre cours…" : "Collez votre SMS ou décrivez la situation…"} rows={2} disabled={busy} /><div className="composer-actions"><div><button type="button" onClick={() => fileRef.current?.click()} aria-label="Joindre un fichier"><Paperclip size={19} /></button><span>PNG, JPG, PDF ou TXT · 8 Mo max.</span></div><button className="send-button" type="submit" disabled={busy || (!input.trim() && !attachment)}><PaperPlaneTilt size={19} weight="fill" /> Envoyer</button></div></form>
            <input ref={fileRef} hidden type="file" accept="image/png,image/jpeg,image/webp,.pdf,.txt" onChange={(e) => onFile(e.target.files?.[0])} />
          </div>
          <p className="disclaimer"><ShieldCheck size={14} /> Vioum peut se tromper. Vérifiez toujours le solde dans le canal officiel de votre opérateur.</p>
        </footer>
      </div>

      {sidebarOpen && <button className="overlay" onClick={() => setSidebarOpen(false)} aria-label="Fermer le menu" />}
      {helpOpen && <div className="modal-backdrop" onClick={() => setHelpOpen(false)}><div className="help-modal" onClick={(e) => e.stopPropagation()}><button className="modal-close" onClick={() => setHelpOpen(false)}><X size={19} /></button><Image src="/logo.webp" width={58} height={58} alt="Logo Vioum" /><h2>Comment utiliser Vioum ?</h2><p>Collez un SMS anonymisé ou ajoutez une capture. Vioum relève les indices suspects, puis vous propose des actions concrètes.</p><div><strong>Pour réviser</strong><p>Envoyez <b>/apprendre</b>, joignez votre cours, puis utilisez <b>/resume</b>, <b>/plan</b> ou <b>/quiz</b>.</p></div><small>Une analyse ne confirme jamais un paiement. Ne partagez ni PIN, ni OTP.</small></div></div>}
    </div>
  );
}
