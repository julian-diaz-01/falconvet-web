import streamlit as st
import base64, json, os, io, urllib.request, urllib.error, re
from PIL import Image
from datetime import datetime

st.set_page_config(page_title="FalconVet", layout="wide")
st.markdown("""<style>
.stApp { background-color: #0D0F14; color: #E8EAF0; }
.topbar { background: #141720; padding: 12px 20px; border-bottom: 3px solid #C8A84B; display: flex; justify-content: space-between; align-items: center; }
.topbar h1 { color: #C8A84B; font-family: Georgia, serif; margin: 0; font-size: 30px; }
.topbar span { color: #7A8099; }
.panel { background: #141720; border-radius: 10px; padding: 16px; }
.card { background: #1C2030; border-radius: 8px; padding: 14px; }
.stButton>button { background-color: #2A2F42 !important; color: #C8A84B !important; font-weight: bold !important; border: 2px solid #C8A84B !important; border-radius: 6px !important; }
.stButton>button:hover { background-color: #1C2030 !important; }
.badge-ok { background: #4CAF72; color: white; padding: 6px 14px; font-weight: bold; border-radius: 4px; display: inline-block; }
.badge-warn { background: #E8A838; color: white; padding: 6px 14px; font-weight: bold; border-radius: 4px; display: inline-block; }
.badge-danger { background: #E84B4B; color: white; padding: 6px 14px; font-weight: bold; border-radius: 4px; display: inline-block; }
.badge-none { background: #1C2030; color: #7A8099; padding: 6px 14px; font-weight: bold; border-radius: 4px; display: inline-block; }
.small { color: #7A8099; font-size: 13px; }
</style>""", unsafe_allow_html=True)

MODEL = os.environ.get("OPENROUTER_MODEL", "qwen/qwen3.8-omni-flash")
def get_key():
    try:
        return st.secrets["OPENROUTER_API_KEY"]
    except Exception:
        return os.environ.get("OPENROUTER_API_KEY", "")

def estado_de(txt):
    t = (txt or "").upper().replace("PRECAUCIÓN", "PRECAUCION")
    iu, ip, inn = t.rfind("URGENTE"), t.rfind("PRECAUCION"), t.rfind("NORMAL")
    m = max(iu, ip, inn)
    if m == -1 or m == inn: return "NORMAL"
    if m == iu: return "URGENTE"
    return "PRECAUCION"

def badge(est):
    cls = {"NORMAL": "badge-ok", "PRECAUCION": "badge-warn", "URGENTE": "badge-danger"}.get(est, "badge-none")
    return f"<span class='{cls}'>&nbsp;&nbsp;{est}&nbsp;&nbsp;</span>"

PROMPT = """Eres FalconVet, veterinario de ganado bovino en Colombia.
Comienza con: "Segun el analisis realizado, se ha observado lo siguiente:"
1. CONDICION CORPORAL (1-5): flaca, normal u obesa? costillas?
2. POSTURA Y MOVILIDAD: de pie, caida, cojera?
3. CABEZA: ojos, nariz, boca.
4. PELAJE Y PIEL: brillante, zonas sin pelo, costras?
5. VIENTRE Y UBRE: hinchado, ubre inflamada?
6. ACTITUD: alerta o decaida?
7. DIAGNOSTICO: simple, solo si hay signos claros (aftosa, mastitis, parasitosis, neumonia, tristeza, timpanismo).
8. RECOMENDACIONES: 3 pasos.
Ultima linea EXACTA, una palabra: NORMAL o PRECAUCION o URGENTE"""

PREGUNTAS = [
    ("tiempo", "Hace cuanto noto algo raro?", ["Hoy mismo", "1 a 3 dias", "4 a 7 dias", "Mas de una semana", "Nada raro"]),
    ("apetito", "Come y bebe normal?", ["Si normal", "Come menos", "No comio hoy", "Bebe mucho mas", "No se"]),
    ("temp", "Temperatura?", ["No medida", "Normal 38-39.5", "Alta +39.5", "Baja -38"]),
    ("mov", "Movilidad?", ["Camina normal", "Cojea", "Cuesta levantarse", "Echado sin pararse"]),
    ("heces", "Heces u orina raras?", ["Todo normal", "Diarrea", "Sangre en heces", "Orina oscura/sangre"]),
    ("lote", "Otros animales igual?", ["No, solo este", "1 o 2 mas", "Varios del lote"]),
    ("vacunas", "Vacunas al dia?", ["Si al dia", "Vencidas", "No vacunado", "No se"]),
]

def llamar_ia(prompt, b64):
    key = get_key()
    if not key: return None, "Falta OPENROUTER_API_KEY."
    payload = json.dumps({"model": MODEL,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}]}],
        "max_tokens": 1500}).encode()
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions",
        data=payload, headers={"Content-Type": "application/json",
        "Authorization": f"Bearer {key}"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            res = json.loads(r.read().decode())
        txt = res["choices"][0]["message"]["content"]
        if isinstance(txt, list):
            txt = "".join([b.get("text", "") if isinstance(b, dict) else b for b in txt])
        return txt.strip(), None
    except urllib.error.HTTPError as e:
        return None, f"Error {e.code}: revisa key, saldo o modelo."
    except Exception as e:
        return None, f"Error: {e}"

st.markdown("<div class='topbar'><h1>FalconVet <span style='font-size:15px'>Diagnostico Bovino IA</span></h1><span>Sistema Listo</span></div>", unsafe_allow_html=True)
st.warning("Orienta, no reemplaza al veterinario.")
for k in ("hist", "diag", "b64"):
    if k not in st.session_state: st.session_state[k] = [] if k == "hist" else None

izq, der = st.columns([1, 1.25])
with izq:
    st.markdown("<div class='panel'><b style='color:#7A8099'>IMAGEN DE LA VACA</b>", unsafe_allow_html=True)
    foto = st.file_uploader("Sube foto", type=["jpg", "jpeg", "png", "webp"])
    if foto:
        img = Image.open(foto).convert("RGB")
        st.image(img, width=420)
        c1, c2 = st.columns(2)
        with c1:
            subir = st.button("Cargar foto")
        with c2:
            go = st.button("Analizar Salud")
        if go:
            img.thumbnail((1024, 1024))
            buf = io.BytesIO(); img.save(buf, format="JPEG", quality=85)
            st.session_state.b64 = base64.b64encode(buf.getvalue()).decode()
            with st.spinner("Analizando..."):
                txt, err = llamar_ia(PROMPT, st.session_state.b64)
            if err: st.error(err)
            else:
                st.session_state.diag = txt
                st.session_state.hist.insert(0, {"fecha": datetime.now().strftime("%d/%m %H:%M"), "txt": txt[:120]})
                st.rerun()
    st.markdown("<b style='color:#7A8099'>HISTORIAL DE ANALISIS</b>", unsafe_allow_html=True)
    for h in st.session_state.hist:
        st.markdown(f"<div class='card small'>{h['fecha']} - {h['txt']}</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

with der:
    st.markdown("<div class='panel'><b style='color:#7A8099'>DIAGNOSTICO IA</b><br><br>", unsafe_allow_html=True)
    est = estado_de(st.session_state.diag) if st.session_state.diag else "SIN ANALISIS"
    st.markdown(badge(est) if est != "SIN ANALISIS" else "<span class='badge-none'>&nbsp;&nbsp;SIN ANALISIS&nbsp;&nbsp;</span>", unsafe_allow_html=True)
    if st.session_state.diag:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.write(st.session_state.diag)
        st.markdown("</div>", unsafe_allow_html=True)
        st.info("Esta de acuerdo con este diagnostico?")
        a, b = st.columns(2)
        if a.button("Si, estoy de acuerdo"):
            st.success("Diagnostico confirmado. Siga las recomendaciones.")
        if b.button("Mejorar con preguntas"):
            st.session_state.preg = True
    else:
        st.write("Carga una foto y presiona Analizar Salud.")
    st.markdown("</div>", unsafe_allow_html=True)

if st.session_state.get("preg") and st.session_state.diag:
    st.markdown("<div class='panel'><b style='color:#C8A84B'>PREGUNTAS PARA UN DIAGNOSTICO MAS PRECISO</b>", unsafe_allow_html=True)
    resp = {}
    for pid, texto, ops in PREGUNTAS:
        resp[pid] = st.selectbox(texto, ["(sin responder)"] + ops, key="q_" + pid)
    extra = st.text_area("Dato adicional (zona inundada, parto reciente...)")
    if st.button("Generar diagnostico complementario"):
        info = "\n".join([f"- {t}: {resp[p]}" for p, t, o in PREGUNTAS if resp[p] != "(sin responder)"])
        if extra.strip(): info += f"\n- Adicional: {extra.strip()}"
        if not info.strip(): st.warning("Responde al menos 1 pregunta.")
        else:
            pc = f"Eres FalconVet. Analisis previo:\n---\n{st.session_state.diag}\n---\nDatos del ganadero:\n{info}\nActualiza el diagnostico con 9 puntos (condicion, postura, cabeza, pelaje, vientre, senales reportadas, diagnostico actualizado, urgencia, 3 acciones). Ultima linea EXACTA una palabra: NORMAL o PRECAUCION o URGENTE"
            with st.spinner("Refinando..."):
                txt2, err2 = llamar_ia(pc, st.session_state.b64)
            if err2: st.error(err2)
            else:
                st.write(txt2)
                st.session_state.hist.insert(0, {"fecha": datetime.now().strftime("%d/%m %H:%M"), "txt": txt2[:120]})
    st.markdown("</div>", unsafe_allow_html=True)