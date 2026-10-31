import io
import json
import os
import re
from datetime import date

import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image
from pypdf import PdfReader

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------
load_dotenv()  # charge GEMINI_API_KEY depuis .env

MODEL_ID = "gemma-4-26b-a4b-it"
MAX_COURSE_CHARS = 60_000
IMG_EXT = (".png", ".jpg", ".jpeg", ".webp")

st.set_page_config(page_title="Pixel Rebels - Moov & T-Money Assistant",
                   page_icon="🛡️", layout="centered")

st.markdown("""
<style>
#MainMenu, footer {visibility: hidden;}
.block-container {padding-top: 2rem; max-width: 860px;}
</style>
""", unsafe_allow_html=True)


def get_api_key():
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        try:
            key = st.secrets["GEMINI_API_KEY"]  # secours : .streamlit/secrets.toml
        except Exception:
            key = None
    return key


API_KEY = get_api_key()
if not API_KEY or API_KEY == "votre_cle_ici":
    st.error("🔑 Clé API introuvable. Créez un fichier `.env` à côté de `app.py` "
             "avec la ligne `GEMINI_API_KEY=votre_cle` (voir `.env.example`), "
             "puis relancez l'application.")
    st.stop()


@st.cache_resource
def get_client(api_key: str):
    return genai.Client(api_key=api_key)


client = get_client(API_KEY)


# ----------------------------------------------------------------------------
# Appel à Gemma + gestion des erreurs
# ----------------------------------------------------------------------------
class GemmaError(Exception):
    """Erreur lisible par l'utilisateur."""


def friendly_error(e: Exception) -> str:
    msg, low = str(e), str(e).lower()
    if "429" in msg or "quota" in low or "resource_exhausted" in low:
        return "⏳ Trop de requêtes ou quota gratuit atteint. Attendez une minute puis réessayez."
    if "api key" in low or "401" in msg or "403" in msg or "permission" in low:
        return "🔑 Clé API refusée. Vérifiez `GEMINI_API_KEY` dans votre fichier `.env`."
    if "404" in msg or "not found" in low:
        return f"🤖 Modèle `{MODEL_ID}` introuvable pour cette clé."
    if "timeout" in low or "connect" in low or "network" in low:
        return "📡 Problème de connexion Internet. Vérifiez votre réseau et réessayez."
    return f"⚠️ Erreur Gemma : {msg[:300]}"


def call_gemma(contents, system: str, temperature: float = 0.3) -> str:
    try:
        r = client.models.generate_content(
            model=MODEL_ID,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system, temperature=temperature),
        )
    except Exception as e:
        raise GemmaError(friendly_error(e)) from e
    text = (r.text or "").strip()
    if not text:
        raise GemmaError("Gemma n'a renvoyé aucune réponse. Réessayez.")
    return text


# ----------------------------------------------------------------------------
# Prompts
# ----------------------------------------------------------------------------
SCANNER_SYSTEM = """Tu es un expert anti-arnaques Mobile Money au Togo (T-Money de Togocom et Moov Money de Moov Africa).
Tu analyses un SMS (texte et/ou capture d'écran) et tu dis s'il est authentique ou s'il s'agit d'une tentative d'escroquerie.
Tu écris pour un utilisateur local, y compris dans le secteur informel : français TRÈS simple, phrases courtes, sans jargon.

Repères sur les vrais SMS officiels (à confronter avec le message) :
- Ils sont informatifs : confirmation de transaction avec montant, date, référence/ID de transaction et nouveau solde.
- L'expéditeur est un nom officiel (ex. TMONEY, MOOV MONEY), pas un numéro de téléphone personnel.
- Ils ne demandent JAMAIS le code PIN, un mot de passe, un code reçu par SMS, ni de renvoyer de l'argent.
- Ils ne promettent pas de gains à un concours auquel la personne n'a pas participé.

Signaux d'arnaque fréquents :
- « Dépôt par erreur, renvoie-moi l'argent » (le vrai SMS de dépôt n'est suivi d'aucune demande de remboursement).
- Faux concours / loterie / gains qui demandent des « frais » à payer d'abord.
- Fausses tontines ou faux investissements, promesse de gains rapides.
- Urgence, menace de blocage du compte, demande du PIN ou d'un code.
- Lien suspect, numéro personnel à rappeler, fautes de syntaxe inhabituelles, majuscules excessives.
- Montant ou référence de transaction absents ou incohérents.

Règles :
- Si tu hésites, choisis SUSPECT et explique le doute (mieux vaut prudent que faux « légitime »).
- Ne conclus LEGITIME que si le message est cohérent avec un SMS officiel et ne demande rien de risqué.
- Si le texte n'est pas un SMS Mobile Money, verdict NON_APPLICABLE.
- N'invente jamais d'information absente du message : écris "Non visible" si elle manque.

Réponds UNIQUEMENT avec un objet JSON valide, sans texte autour, sans balises markdown, avec exactement ces clés :
{
  "verdict": "LEGITIME" | "SUSPECT" | "ARNAQUE" | "NON_APPLICABLE",
  "score_risque": nombre de 0 (sûr) à 100 (arnaque certaine),
  "resume": "2 phrases maximum, français simple, qui disent clairement quoi penser du message",
  "infos": {"montant": "", "expediteur": "", "type_message": "", "reference_transaction": "", "solde": "", "lien_ou_numero": ""},
  "indices_fraude": ["indices précis relevés dans le message"],
  "indices_conformes": ["éléments qui ressemblent à un vrai SMS officiel"],
  "conseils": ["2 à 3 actions concrètes, simples"],
  "alerte_locale": ""
}"""

LEARN_SYSTEM = """Tu es un tuteur bienveillant pour des étudiants au Togo.
Tu réponds en français simple, de façon courte et structurée.
Tu t'appuies UNIQUEMENT sur le cours fourni. Si une information n'est pas dans le cours, dis-le clairement.
Tu encourages l'étudiant sans jamais te moquer de ses erreurs."""

EXAMPLES = {
    "🚨 Faux dépôt « par erreur »": "URGENT: Vous avez recu un depot de 50 000 FCFA par erreur. Renvoyez-le au 90 00 00 00 SVP, c'est l'argent de ma tontine. Merci",
    "🚨 Faux concours": "FELICITATIONS!! Vous avez gagne 2.000.000 FCFA au grand concours TMONEY. Pour retirer votre gain envoyez 15 000 FCFA de frais et votre code PIN au 91 11 11 11 avant ce soir",
    "✅ SMS type officiel (fictif)": "Vous avez recu 10 000 FCFA de KOFI A. (90 00 00 01). Nouveau solde : 25 000 FCFA. ID transaction : 1234567890. Date : 31/10/2026 10:15",
}


# ----------------------------------------------------------------------------
# État de session
# ----------------------------------------------------------------------------
def init_state():
    defaults = {
        "messages": [],          # historique affiché
        "mode": "scanner",       # "scanner" | "learning"
        "course_text": "",
        "course_images": [],
        "course_files": [],
        "course_name": "",
        "pending_quiz": None,
        "weak_topics": [],
        "learn_history": [],
        "langue": "Aucune",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_state()
s = st.session_state


def add_msg(role, content="", kind="text", **extra):
    s.messages.append({"role": role, "content": content, "kind": kind, **extra})


# ----------------------------------------------------------------------------
# Scanner d'arnaques
# ----------------------------------------------------------------------------
VERDICTS = {
    "ARNAQUE": ("🚨 ARNAQUE PROBABLE : NE RÉPONDEZ PAS, NE PAYEZ RIEN", st.error),
    "SUSPECT": ("⚠️ MESSAGE SUSPECT : SOYEZ TRÈS PRUDENT", st.warning),
    "LEGITIME": ("✅ MESSAGE PROBABLEMENT AUTHENTIQUE", st.success),
    "NON_APPLICABLE": ("ℹ️ CE N'EST PAS UN SMS MOBILE MONEY", st.info),
}
INFO_LABELS = {
    "montant": "Montant", "expediteur": "Expéditeur", "type_message": "Type de message",
    "reference_transaction": "Référence", "solde": "Solde", "lien_ou_numero": "Lien / numéro",
}


def parse_json(text: str):
    t = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    a, b = t.find("{"), t.rfind("}")
    if a == -1 or b <= a:
        return None
    try:
        return json.loads(t[a:b + 1])
    except json.JSONDecodeError:
        return None


def as_list(v):
    if isinstance(v, list):
        return [str(x) for x in v if str(x).strip()]
    return [str(v)] if v else []


def normalize_scan(data, raw: str) -> dict:
    if not isinstance(data, dict):
        return {"verdict": "SUSPECT", "score_risque": 50,
                "resume": "Je n'ai pas pu analyser ce message de façon fiable. Par prudence, ne faites rien avant de vérifier.",
                "infos": {}, "indices_fraude": [], "indices_conformes": [],
                "conseils": ["Contactez le service client officiel T-Money ou Moov Money."],
                "alerte_locale": ""}
    v = str(data.get("verdict", "")).upper().replace("É", "E").replace(" ", "_")
    if v not in VERDICTS:
        v = "SUSPECT"
    try:
        score = max(0, min(100, int(float(data.get("score_risque", 50)))))
    except (TypeError, ValueError):
        score = 50
    return {"verdict": v, "score_risque": score, "resume": str(data.get("resume", "")),
            "infos": data.get("infos") if isinstance(data.get("infos"), dict) else {},
            "indices_fraude": as_list(data.get("indices_fraude")),
            "indices_conformes": as_list(data.get("indices_conformes")),
            "conseils": as_list(data.get("conseils")),
            "alerte_locale": str(data.get("alerte_locale", "") or "")}


def prepare_image(data: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(data)).convert("RGB")
    img.thumbnail((1600, 1600))
    return img


def scan_sms(text: str, image, langue: str) -> dict:
    prompt = "Analyse ce SMS Mobile Money."
    if text:
        prompt += f'\n\nTexte du SMS :\n"""\n{text}\n"""'
    if image is not None:
        prompt += "\n\nUne capture d'écran du SMS est jointe : lis-la attentivement."
    if langue != "Aucune":
        prompt += (f"\n\nRemplis aussi 'alerte_locale' avec 2 phrases courtes en {langue}. "
                   "Si tu n'es pas sûr de ta traduction, laisse ce champ vide.")
    contents = [prompt] + ([image] if image is not None else [])
    raw = call_gemma(contents, SCANNER_SYSTEM, temperature=0.1)
    return normalize_scan(parse_json(raw), raw)


def render_scan(res: dict):
    label, banner = VERDICTS[res["verdict"]]
    banner(f"**{label}**")
    if res["verdict"] != "NON_APPLICABLE":
        st.progress(res["score_risque"] / 100, text=f"Niveau de risque : {res['score_risque']}/100")
    if res["resume"]:
        st.markdown(res["resume"])
    if res["alerte_locale"]:
        st.info(f"🗣️ {res['alerte_locale']}")
        st.caption("Traduction automatique : peut contenir des erreurs.")
    rows = [(INFO_LABELS[k], str(v)) for k, v in res["infos"].items()
            if k in INFO_LABELS and str(v).strip()]
    if rows:
        with st.expander("📋 Informations lues dans le message", expanded=True):
            for k, v in rows:
                st.markdown(f"- **{k}** : {v}")
    if res["indices_fraude"]:
        with st.expander("🔎 Indices de fraude", expanded=True):
            for i in res["indices_fraude"]:
                st.markdown(f"- 🚩 {i}")
    if res["indices_conformes"]:
        with st.expander("✔️ Éléments conformes à un vrai SMS"):
            for i in res["indices_conformes"]:
                st.markdown(f"- {i}")
    if res["conseils"]:
        st.markdown("**Que faire ?**")
        for c in res["conseils"]:
            st.markdown(f"- {c}")
    st.caption("Aucun outil n'est fiable à 100 %. En cas de doute : ne payez rien, ne donnez jamais "
               "votre code PIN, et vérifiez auprès du service client officiel.")


def handle_scan(text: str, files: list):
    images = [f for f in files if f.name.lower().endswith(IMG_EXT)]
    others = [f.name for f in files if not f.name.lower().endswith(IMG_EXT)]
    if others:
        add_msg("assistant", "📎 Les documents de cours ne sont acceptés qu'en mode apprentissage. "
                             "Tapez `/apprendre` pour l'activer.")
    if not text and not images:
        return
    img = None
    if images:
        try:
            img = prepare_image(images[0].getvalue())
        except Exception:
            add_msg("assistant", "Cette image n'a pas pu être lue. Essayez une autre capture (PNG ou JPG).", kind="error")
            return
    add_msg("assistant", kind="scan", scan=scan_sms(text, img, s.langue))


# ----------------------------------------------------------------------------
# Mode apprentissage
# ----------------------------------------------------------------------------
def extract_pdf(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    except Exception:
        return ""


def ingest_course(files: list):
    names = []
    for f in files:
        name, data = f.name, f.getvalue()
        low = name.lower()
        if low.endswith(".pdf"):
            text = extract_pdf(data)
            if len(text.strip()) >= 200:
                s.course_text += f"\n\n--- {name} ---\n{text}"
            else:  # PDF scanné : envoi du fichier à Gemma via l'API Files
                try:
                    up = client.files.upload(
                        file=io.BytesIO(data),
                        config=types.UploadFileConfig(mime_type="application/pdf", display_name=name))
                    s.course_files.append(up)
                except Exception as e:
                    add_msg("assistant", f"Impossible de lire `{name}` : {friendly_error(e)}", kind="error")
                    continue
        elif low.endswith((".txt", ".md")):
            s.course_text += f"\n\n--- {name} ---\n" + data.decode("utf-8", errors="replace")
        elif low.endswith(IMG_EXT):
            try:
                s.course_images.append(prepare_image(data))
            except Exception:
                add_msg("assistant", f"Image `{name}` illisible.", kind="error")
                continue
        else:
            add_msg("assistant", f"Format non pris en charge : `{name}`.", kind="error")
            continue
        names.append(name)
    if not names:
        return
    s.course_name = ", ".join(filter(None, [s.course_name, *names]))
    msg = f"📚 Cours chargé : **{', '.join(names)}**."
    if len(s.course_text) > MAX_COURSE_CHARS:
        s.course_text = s.course_text[:MAX_COURSE_CHARS]
        msg += " (Cours très long : seuls les premiers 60 000 caractères sont utilisés.)"
    themes = learn_call("Liste en 5 puces maximum les grands thèmes de ce cours, une ligne par thème.")
    add_msg("assistant", f"{msg}\n\n**Thèmes repérés :**\n{themes}\n\n"
            "👉 Je vous propose un plan de révision : tapez `/plan` suivi de votre date d'examen "
            "(ex. `/plan 20 novembre`). Vous pouvez aussi taper `/quiz` ou `/resume`.")


def course_loaded() -> bool:
    return bool(s.course_text.strip() or s.course_images or s.course_files)


def learn_call(instruction: str) -> str:
    history = "\n".join(f"{who} : {txt}" for who, txt in s.learn_history[-6:])
    parts = []
    if s.course_text.strip():
        parts.append("COURS :\n" + s.course_text)
    parts += s.course_images + s.course_files
    parts.append((f"Historique récent :\n{history}\n\n" if history else "") + f"Demande : {instruction}")
    reply = call_gemma(parts, LEARN_SYSTEM, temperature=0.4)
    s.learn_history.append(("Étudiant", instruction[:300]))
    s.learn_history.append(("Tuteur", reply[:600]))
    return reply


def weak_hint() -> str:
    return (f" Privilégie ces notions mal comprises : {', '.join(s.weak_topics)}."
            if s.weak_topics else "")


def handle_learning(text: str, files: list):
    if files:
        ingest_course(files)
    if not text:
        return
    if not course_loaded():
        add_msg("assistant", "Téléversez d'abord un cours (PDF, photo ou texte) avec le trombone 📎.")
        return
    if s.pending_quiz:  # l'étudiant répond à un quiz
        reply = learn_call(
            f"Question posée : {s.pending_quiz}\nRéponse de l'étudiant : {text}\n"
            "1) Dis si la réponse est correcte, partiellement correcte ou fausse. "
            "2) Donne la bonne réponse avec une courte explication tirée du cours. 3) Encourage. "
            "Termine OBLIGATOIREMENT par une dernière ligne exactement au format : "
            "NOTION_A_REVOIR: <notion courte> ou NOTION_A_REVOIR: AUCUNE")
        m = re.search(r"NOTION_A_REVOIR\s*:\s*(.+)$", reply, flags=re.M)
        if m:
            notion = m.group(1).strip().strip("*")
            if notion.upper() != "AUCUNE" and notion not in s.weak_topics:
                s.weak_topics.append(notion)
            reply = re.sub(r"\n?.*NOTION_A_REVOIR.*$", "", reply, flags=re.M).strip()
        s.pending_quiz = None
        add_msg("assistant", reply + "\n\n➡️ Tapez `/quiz` pour la question suivante.")
    else:  # question libre sur le cours
        add_msg("assistant", learn_call(f"Question de l'étudiant : {text}. Réponds d'après le cours."))


HELP = ("**Commandes disponibles**\n"
        "- `/apprendre` : active le mode apprentissage et invite à téléverser un cours\n"
        "- `/plan <date d'examen>` : plan de révision sur plusieurs jours\n"
        "- `/quiz` : pose une question et corrige votre réponse\n"
        "- `/resume` : résumé et fiches de révision\n"
        "- `/stop` : retour au scanner d'arnaques")


def handle_command(cmd: str, arg: str, files: list):
    if cmd == "/apprendre":
        s.mode = "learning"
    if files and s.mode == "learning":
        ingest_course(files)

    if cmd == "/apprendre":
        if course_loaded():
            add_msg("assistant", "🎓 Mode apprentissage actif. Votre cours est déjà chargé : "
                                 "posez une question ou tapez `/plan`, `/quiz`, `/resume`.")
        else:
            add_msg("assistant", "🎓 Mode apprentissage activé ! Téléversez votre cours (PDF, photo ou "
                                 "texte) avec le trombone 📎. Tapez `/stop` pour revenir au scanner.")
    elif cmd == "/stop":
        s.mode, s.pending_quiz = "scanner", None
        add_msg("assistant", "🛡️ Retour au **scanner d'arnaques**. Collez un SMS ou envoyez une capture.")
    elif cmd in ("/aide", "/help"):
        add_msg("assistant", HELP)
    elif cmd in ("/plan", "/quiz", "/resume"):
        if s.mode != "learning":
            add_msg("assistant", "Tapez d'abord `/apprendre` pour activer le mode apprentissage.")
        elif not course_loaded():
            add_msg("assistant", "Téléversez d'abord un cours avec le trombone 📎.")
        elif cmd == "/plan":
            if not arg:
                add_msg("assistant", "Indiquez votre date d'examen, par exemple : `/plan 20 novembre`.")
            else:
                add_msg("assistant", learn_call(
                    f"Aujourd'hui nous sommes le {date.today().strftime('%d/%m/%Y')}. "
                    f"Date d'examen indiquée : « {arg} ». Propose un plan de révision jour par jour "
                    "(de demain jusqu'à la veille de l'examen), 30 à 60 minutes par jour, basé sur les "
                    "thèmes du cours, avec un mini-quiz tous les 2 ou 3 jours et une révision finale. "
                    "Si la date est incompréhensible ou passée, demande poliment de la reformuler." + weak_hint()))
        elif cmd == "/quiz":
            q = learn_call("Pose UNE seule question de quiz (réponse courte) sur le cours, niveau moyen. "
                           "Ne donne pas la réponse. Commence par « Question : »." + weak_hint())
            s.pending_quiz = q
            add_msg("assistant", q + "\n\n✍️ Écrivez votre réponse ci-dessous.")
        else:
            add_msg("assistant", learn_call(
                "Fais un résumé clair du cours puis 5 à 8 fiches de révision (notion + définition courte)."))
    else:
        add_msg("assistant", f"Commande inconnue : `{cmd}`.\n\n{HELP}")


# ----------------------------------------------------------------------------
# Barre latérale
# ----------------------------------------------------------------------------
with st.sidebar:
    st.header("📖 Mode d'emploi")
    st.markdown("**🛡️ Mode scanner (par défaut)**\n\nCollez le texte d'un SMS ou envoyez une capture d'écran "
                "avec le trombone 📎.")
    st.markdown("**🎓 Mode apprentissage**\n\nTapez `/apprendre`, puis `/plan`, `/quiz`, `/resume`. "
                "`/stop` pour quitter.")
    st.divider()
    st.selectbox("Alerte aussi en langue locale", ["Aucune", "Éwé", "Kabiyè"], key="langue")
    st.divider()
    st.subheader("🧪 Exemples fictifs")
    st.caption("Messages inventés pour la démo : remplacez-les par des SMS anonymisés.")
    for label, sms in EXAMPLES.items():
        if st.button(label, use_container_width=True):
            st.session_state["queued"] = sms
    if s.weak_topics:
        st.divider()
        st.subheader("🎯 À revoir")
        for t in s.weak_topics:
            st.markdown(f"- {t}")
    st.divider()
    st.caption("🔒 N'utilisez jamais de vraies données personnelles ni de vrais numéros.")
    if st.button("🗑️ Nouvelle conversation", use_container_width=True):
        for k in ("messages", "course_text", "course_images", "course_files", "course_name",
                  "pending_quiz", "weak_topics", "learn_history", "mode"):
            del st.session_state[k]
        st.rerun()

# ----------------------------------------------------------------------------
# Page principale
# ----------------------------------------------------------------------------
st.title("🛡️ Moov & T-Money Assistant & Fraude Scanner")
st.caption("Détectez les faux SMS Mobile Money au Togo et révisez vos cours grâce à Gemma.")

if s.mode == "learning":
    st.info(f"🎓 **Mode apprentissage** actif"
            f"{' · cours : ' + s.course_name if s.course_name else ''}. `/stop` pour revenir au scanner.")

if not s.messages:
    st.info("👋 Collez un SMS suspect ci-dessous ou envoyez une capture d'écran. "
            "Je vous dis en quelques secondes s'il est authentique ou s'il s'agit d'une arnaque. "
            "Tapez `/aide` pour voir les commandes.")

for m in s.messages:
    with st.chat_message(m["role"]):
        if m.get("image"):
            st.image(m["image"], width=280)
        if m["kind"] == "scan":
            render_scan(m["scan"])
        elif m["kind"] == "error":
            st.error(m["content"])
        else:
            st.markdown(m["content"])

placeholder = ("Message ou commande /… (ex. /apprendre)" if s.mode == "learning"
               else "Collez un SMS suspect ou envoyez une capture d'écran…")
chat = st.chat_input(placeholder, accept_file="multiple",
                     file_type=["png", "jpg", "jpeg", "webp", "pdf", "txt", "md"])
queued = st.session_state.pop("queued", None)

if chat or queued:
    text = queued if queued else (chat.text or "").strip()
    files = [] if queued else list(chat.files or [])

    image_bytes = next((f.getvalue() for f in files if f.name.lower().endswith(IMG_EXT)), None)
    shown = text + ("".join(f"\n\n📎 {f.name}" for f in files) if files else "")
    add_msg("user", shown or "📎", image=image_bytes)

    try:
        with st.spinner("Gemma analyse…"):
            if text.startswith("/"):
                cmd, _, arg = text.partition(" ")
                handle_command(cmd.lower(), arg.strip(), files)
            elif s.mode == "learning":
                handle_learning(text, files)
            else:
                handle_scan(text, files)
    except GemmaError as e:
        add_msg("assistant", str(e), kind="error")
    except Exception as e:
        add_msg("assistant", f"Erreur inattendue : {e}", kind="error")
    st.rerun()