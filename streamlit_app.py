import io
import ezdxf
import matplotlib.pyplot as plt
import numpy as np
import streamlit as st

st.set_page_config(
    page_title="Gerador de Came -> DXF",
    page_icon="⚙️",
    layout="wide",
)


def calcular_deslocamento_trecho(u, lei):
    """u varia de 0.0 a 1.0 dentro do trecho."""
    u = np.clip(u, 0.0, 1.0)
    if lei == "cicloidal":
        return u - (1.0 / (2.0 * np.pi)) * np.sin(2.0 * np.pi * u)
    elif lei == "polinomial_345":
        return 10.0 * (u**3) - 15.0 * (u**4) + 6.0 * (u**5)
    else:  # mhs
        return 0.5 * (1.0 - np.cos(np.pi * u))


def gerar_perfil_came(raio_base, trechos, lei_selecionada, n_pontos=720):
    """
    trechos: lista de tuplas (theta_ini_deg, theta_fim_deg, tipo, H_mm)
    tipo: 'subida', 'descida' ou 'parada'
    """
    theta_deg = np.linspace(0.0, 360.0, n_pontos, endpoint=True)
    s = np.zeros_like(theta_deg)
    s_acumulado = 0.0

    for t_ini, t_fim, tipo, H in trechos:
        if t_fim <= t_ini:
            continue
        mask = (theta_deg >= t_ini) & (theta_deg <= t_fim)
        u = (theta_deg[mask] - t_ini) / (t_fim - t_ini)

        if tipo == "subida":
            s[mask] = s_acumulado + H * calcular_deslocamento_trecho(u, lei_selecionada)
            s_acumulado += H
        elif tipo == "descida":
            s[mask] = s_acumulado - H * calcular_deslocamento_trecho(u, lei_selecionada)
            s_acumulado -= H
        else:  # parada
            s[mask] = s_acumulado

    raio_mm = raio_base + s
    return theta_deg, s, raio_mm


def gerar_dxf(theta_deg, raio_mm, raio_base, raio_furo=0.0):
    theta_rad = np.deg2rad(theta_deg)
    x = raio_mm * np.cos(theta_rad)
    y = raio_mm * np.sin(theta_rad)

    pontos = [(float(px), float(py)) for px, py in zip(x, y)]
    if pontos and pontos[0] != pontos[-1]:
        pontos.append(pontos[0])

    doc = ezdxf.new(setup=True)
    doc.header["$INSUNITS"] = 4  # Milímetros
    msp = doc.modelspace()

    msp.add_lwpolyline(pontos, close=True, dxfattribs={"layer": "PERFIL_CAME"})
    msp.add_circle((0.0, 0.0), radius=float(raio_base), dxfattribs={"layer": "RAIO_BASE"})

    if raio_furo > 0:
        msp.add_circle((0.0, 0.0), radius=float(raio_furo), dxfattribs={"layer": "FURO_EIXO"})

    out = io.StringIO()
    doc.write(out)
    return out.getvalue().encode("utf-8")


st.title("⚙️ Perfil Geométrico do Came e Exportação DXF")

st.sidebar.header("Parâmetros Geométricos")
raio_base = st.sidebar.number_input("Raio Base Rb [mm]", min_value=5.0, max_value=300.0, value=27.0, step=1.0)
raio_furo = st.sidebar.number_input("Raio do Furo do Eixo [mm] (opcional)", min_value=0.0, max_value=150.0, value=10.0, step=1.0)
lei_selecionada = st.sidebar.selectbox(
    "Lei de Movimento",
    options=["polinomial_345", "cicloidal", "mhs"],
    format_func=lambda x: {
        "polinomial_345": "Polinomial 3-4-5",
        "cicloidal": "Cicloidal",
        "mhs": "Movimento Harmônico Simples (MHS)",
    }[x],
)
n_pontos = st.sidebar.slider("Resolução angular (pontos em 360°)", min_value=180, max_value=2000, value=720, step=60)

st.subheader("Configuração dos Trechos (0° a 360°)")
col1, col2 = st.columns(2)

with col1:
    st.markdown("**Trecho 1 — Subida**")
    t1_fim = st.number_input("Ângulo final da subida [°]", min_value=10.0, max_value=350.0, value=255.0, step=5.0)
    H_subida = st.number_input("Elevação H [mm]", min_value=1.0, max_value=250.0, value=83.0, step=1.0)

with col2:
    st.markdown("**Trecho 2 — Retorno até 360°**")
    st.text_input("Ângulo inicial do retorno [°]", value=f"{t1_fim:.1f}", disabled=True)
    st.text_input("Ângulo final do retorno [°]", value="360.0", disabled=True)
    H_descida = st.number_input("Descida de retorno [mm]", min_value=1.0, max_value=250.0, value=83.0, step=1.0)

if not np.isclose(H_subida, H_descida, atol=1e-6):
    st.warning("Para o came fechar em s = 0 ao completar 360°, mantenha Elevação = Descida (ou ajuste conforme seu projeto).")

trechos = [
    (0.0, t1_fim, "subida", H_subida),
    (t1_fim, 360.0, "descida", H_descida),
]

theta_deg, s, raio_mm = gerar_perfil_came(raio_base, trechos, lei_selecionada, n_pontos=n_pontos)

col_graf, col_info = st.columns([2, 1])

with col_graf:
    fig = plt.figure(figsize=(6, 6))
    ax = fig.add_subplot(111, projection="polar")
    theta_rad = np.deg2rad(theta_deg)

    ax.plot(theta_rad, raio_mm, color="black", linewidth=2.2, label="Perfil do Came")
    ax.plot(theta_rad, np.full_like(theta_rad, raio_base), "--", color="gray", label="Raio base (Rb)")
    ax.set_title("Perfil Geométrico do Came", pad=18, fontweight="bold")
    ax.legend(loc="upper right")
    st.pyplot(fig, use_container_width=True)

with col_info:
    st.metric("Raio Mínimo", f"{np.min(raio_mm):.2f} mm")
    st.metric("Raio Máximo", f"{np.max(raio_mm):.2f} mm")
    st.metric("Curso Máximo (s)", f"{np.max(s):.2f} mm")

    dxf_bytes = gerar_dxf(theta_deg, raio_mm, raio_base=raio_base, raio_furo=raio_furo)
    st.download_button(
        label="⬇️ Baixar Perfil (.DXF)",
        data=dxf_bytes,
        file_name="perfil_came.dxf",
        mime="application/dxf",
        use_container_width=True,
    )
