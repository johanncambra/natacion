import itertools
from io import BytesIO

import pandas as pd
import streamlit as st
from pulp import (
    PULP_CBC_CMD,
    LpBinary,
    LpMinimize,
    LpProblem,
    LpStatus,
    LpVariable,
    lpSum,
)

st.set_page_config(page_title="Optimizador de Equipos de Posta", layout="wide")
st.title("🏊 Optimizador de Equipos de Posta")
st.markdown(
    "<style>div[data-testid='stSidebar'] {font-size: 1.1rem !important;} .main {background-color: #f7f9fa;} .stTabs [data-baseweb='tab']{font-size: 1.1rem !important;}</style>",
    unsafe_allow_html=True,
)
st.markdown(
    """
    <div style='padding:1em; background-color:#d9ecff; border-radius:10px; border-left: 8px solid #3399ff;'>
    <b>¿Cómo funciona esta app?</b><br>
    <ul>
        <li><b>Pestaña 1:</b> Cargá o editá tus datos de nadadores y categorías.</li>
        <li><b>Pestaña 2:</b> Formá equipos buscando el <b>tiempo total mínimo</b> (equipos más rápidos).</li>
        <li><b>Pestaña 3:</b> Formá equipos <b>balanceados</b> (minimiza la diferencia de tiempos entre equipos).</li>
        <li><b>Pestaña 4:</b> Armá <b>una cantidad específica de equipos por categoría</b>; el resto se asigna automáticamente.</li>
    </ul>
    </div>
    """,
    unsafe_allow_html=True,
)

tabs = st.tabs(
    ["📥 Cargar y editar datos", "🕒 Mínimo tiempo total", "⚖️ Balancear equipos", "🧩 Fijar equipos por categoría"]
)

with tabs[0]:
    st.header("📥 Cargar archivo de datos")
    st.info(
        "En esta sección podés cargar, editar y validar los datos de nadadores y categorías. Recordá que estos datos serán usados en las siguientes pestañas para armar los equipos."
    )

    def generar_archivo_ejemplo_25m():
        nadadores = pd.DataFrame(
            {
                "Nadador": [f"alumno_{i+1}" for i in range(10)],
                "Edad": [28, 30, 32, 33, 31, 34, 29, 35, 36, 27],
                "Tiempos": [34, 33, 32, 31, 30, 34, 35, 36, 33, 32],
                "Genero": ["M", "F", "M", "M", "F", "M", "M", "F", "M", "F"],
            }
        )
        categorias = pd.DataFrame(
            {
                "Categoria": ["A", "B", "C", "D", "E", "F"],
                "min": [200, 281, 361, 441, 521, 601],
                "max": [280, 360, 440, 520, 600, 1000],
            }
        )
        with BytesIO() as b:
            with pd.ExcelWriter(b, engine="openpyxl") as writer:
                nadadores.to_excel(writer, index=False, sheet_name="Nadadores")
                categorias.to_excel(writer, index=False, sheet_name="Categorias")
            return b.getvalue()

    def generar_archivo_ejemplo_50m():
        nadadores = pd.DataFrame(
            {
                "Nadador": [f"alumno_{i+1}" for i in range(10)],
                "Edad": [28, 30, 32, 33, 31, 34, 29, 35, 36, 27],
                "Tiempos": [34, 33, 32, 31, 30, 34, 35, 36, 33, 32],
                "Genero": ["M", "F", "M", "M", "F", "M", "M", "F", "M", "F"],
            }
        )
        categorias = pd.DataFrame(
            {
                "Categoria": ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"],
                "min": [120, 145, 175, 235, 295, 325, 355, 385, 415, 445, 475, 505],
                "max": [144, 174, 234, 294, 324, 354, 384, 414, 444, 474, 504, 534],
            }
        )
        with BytesIO() as b:
            with pd.ExcelWriter(b, engine="openpyxl") as writer:
                nadadores.to_excel(writer, index=False, sheet_name="Nadadores")
                categorias.to_excel(writer, index=False, sheet_name="Categorias")
            return b.getvalue()

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "📥 Descargar archivo de ejemplo postas 25 metros",
            data=generar_archivo_ejemplo_25m(),
            file_name="ejemplo_postas_25m.xlsx",
        )
    with col2:
        st.download_button(
            "📥 Descargar archivo de ejemplo postas 50 metros",
            data=generar_archivo_ejemplo_50m(),
            file_name="ejemplo_postas_50m.xlsx",
        )

    archivo = st.file_uploader("📤 Sube tu archivo Excel con los nadadores y categorías", type=["xlsx"])

    if archivo:
        st.session_state.df_nadadores = pd.read_excel(archivo, sheet_name=0)
        st.session_state.df_categorias = pd.read_excel(archivo, sheet_name=1)

        st.subheader("✏️ Editar datos cargados")
        st.session_state.df_nadadores = st.data_editor(
            st.session_state.df_nadadores, num_rows="dynamic", key="editor_nadadores"
        )
        st.session_state.df_categorias = st.data_editor(
            st.session_state.df_categorias, num_rows="dynamic", key="editor_categorias"
        )

        if "ID" not in st.session_state.df_nadadores.columns:
            st.session_state.df_nadadores["ID"] = range(len(st.session_state.df_nadadores))

        errores = []
        df1 = st.session_state.df_nadadores
        df2 = st.session_state.df_categorias

        if not all(df1["Edad"].apply(lambda x: isinstance(x, (int, float)) and 0 < x < 100)):
            errores.append("Todas las edades deben ser mayores que 0 y menores que 100.")
        if not all(df1["Tiempos"].apply(lambda x: isinstance(x, (int, float)) and x > 0)):
            errores.append("Todos los tiempos deben ser mayores que 0.")
        if not all(df1["Genero"].apply(lambda x: str(x).upper() in ["M", "F"])):
            errores.append("El género debe ser 'M' o 'F'.")
        if not all(df2["min"].apply(lambda x: isinstance(x, (int, float)) and x >= 0)):
            errores.append("El valor mínimo de las categorías debe ser un número positivo.")
        if not all(df2["max"].apply(lambda x: isinstance(x, (int, float)) and x >= 0)):
            errores.append("El valor máximo de las categorías debe ser un número positivo.")
        if not all(df2["max"] >= df2["min"]):
            errores.append("En cada categoría, el valor máximo debe ser mayor o igual al mínimo.")

        if errores:
            st.session_state.validado = False
            st.error("\n".join(errores))
        else:
            st.session_state.validado = True
            st.success(
                "✅ Datos validados correctamente. Ahora puedes ir a las siguientes pestañas para armar los equipos."
            )


def asignar_equipos(
    df_nadadores,
    df_categorias,
    tam_equipo,
    min_mujeres,
    modo="min_total",
    equipos_categoria=None,
    equipos_a_formar=0,
    categoria_fija=None,
    drop_id=True,
):
    df_nadadores = df_nadadores.copy().reset_index(drop=True)
    num_nadadores = len(df_nadadores)
    df_nadadores["ID"] = range(num_nadadores)
    if equipos_a_formar > 0:
        total_equipos = equipos_a_formar
    elif equipos_categoria:
        total_equipos = sum(equipos_categoria.values())
    else:
        total_equipos = num_nadadores // tam_equipo

    model = LpProblem("Asignacion_Equipos", LpMinimize)
    x = {(i, j): LpVariable(f"x_{i}_{j}", cat=LpBinary) for i in range(num_nadadores) for j in range(total_equipos)}

    tiempos = df_nadadores["Tiempos"].tolist()

    if modo == "min_total":
        model += lpSum(x[i, j] * tiempos[i] for i in range(num_nadadores) for j in range(total_equipos))
    elif modo == "balance":
        team_times = [lpSum(x[i, j] * tiempos[i] for i in range(num_nadadores)) for j in range(total_equipos)]
        max_time = LpVariable("max_time", lowBound=0)
        min_time = LpVariable("min_time", lowBound=0)
        model += max_time - min_time
        for t in team_times:
            model += t <= max_time
            model += t >= min_time

    for i in range(num_nadadores):
        model += lpSum(x[i, j] for j in range(total_equipos)) <= 1

    for j in range(total_equipos):
        model += lpSum(x[i, j] for i in range(num_nadadores)) == tam_equipo
        es_mujer = [1 if str(g).upper() == "F" else 0 for g in df_nadadores["Genero"]]
        model += lpSum(x[i, j] * es_mujer[i] for i in range(num_nadadores)) >= min_mujeres

    team_total_age = {
        j: lpSum(x[i, j] * df_nadadores.loc[i, "Edad"] for i in range(num_nadadores)) for j in range(total_equipos)
    }
    if categoria_fija is not None:
        min_edad, max_edad, nombre_categoria = categoria_fija
        for j in range(total_equipos):
            model += team_total_age[j] >= min_edad
            model += team_total_age[j] <= max_edad
        team_age_bounds = [(min_edad, max_edad, nombre_categoria)]
    else:
        team_age_bounds = [(row["min"], row["max"], row["Categoria"]) for _, row in df_categorias.iterrows()]
        for j in range(total_equipos):
            min_edad = min(b[0] for b in team_age_bounds)
            max_edad = max(b[1] for b in team_age_bounds)
            model += team_total_age[j] >= min_edad
            model += team_total_age[j] <= max_edad

    model.solve(PULP_CBC_CMD(msg=0))

    if LpStatus[model.status] != "Optimal":
        return pd.DataFrame(), "❌ No se pudo encontrar una solución óptima."

    equipos = []
    for j in range(total_equipos):
        miembros = [i for i in range(num_nadadores) if x[i, j].varValue == 1]
        suma_edad = sum(df_nadadores.loc[i, "Edad"] for i in miembros)
        suma_tiempos = sum(df_nadadores.loc[i, "Tiempos"] for i in miembros)
        if categoria_fija is not None:
            categoria_equipo = nombre_categoria
        else:
            categoria_equipo = next(
                (cat for (minv, maxv, cat) in team_age_bounds if minv <= suma_edad <= maxv), "Sin categoría"
            )
        for i in miembros:
            fila = df_nadadores.loc[i].copy()
            fila["Equipo"] = j + 1
            fila["Categoria"] = categoria_equipo
            fila["Suma_Edades_Equipo"] = suma_edad
            fila["Suma_Tiempos_Equipo"] = suma_tiempos
            equipos.append(fila)

    if not equipos:
        return pd.DataFrame(), "❌ No se pudieron formar equipos con los datos proporcionados."
    df_resultado = pd.DataFrame(equipos).sort_values(by="Equipo")
    if drop_id and "ID" in df_resultado.columns:
        df_resultado.drop(columns=["ID"], inplace=True)
    return df_resultado, "✅ Optimización completada."


def puede_formar_equipo(candidatos, tam, min_f, min_age, max_age):
    if len(candidatos) < tam:
        return False, "No hay suficientes nadadores."
    mujeres = candidatos[candidatos["Genero"].str.upper() == "F"]
    if len(mujeres) < min_f:
        return False, "No hay suficientes mujeres."
    edades = candidatos["Edad"].sort_values(ascending=False).values
    for comb in itertools.combinations(edades, tam):
        s = sum(comb)
        if min_age <= s <= max_age:
            return True, ""
    return False, "No se puede lograr la suma de edades requerida."


def mostrar_resultado(df_resultado, mensaje):
    st.success(mensaje)
    st.dataframe(df_resultado, use_container_width=True)

    def convertir_excel(df):
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)
        return output.getvalue()

    st.download_button(
        "📥 Descargar resultados en Excel", data=convertir_excel(df_resultado), file_name="equipos_optimizados.xlsx"
    )


# ---------- Pestaña 2: minimizar tiempo ----------
with tabs[1]:
    st.header("🕒 Minimizar tiempo total")
    st.info(
        "Forma equipos con el menor tiempo total posible. Es la opción competitiva: los equipos estarán ordenados para nadar lo más rápido posible, cumpliendo los requisitos de género y edad/categoría."
    )
    if st.session_state.get("validado"):
        tam = st.number_input("Cantidad de nadadores por equipo", min_value=2, value=10)
        min_f = st.number_input("Mínimo de mujeres por equipo", min_value=1, max_value=tam, value=2)
        if st.button("🚀 Ejecutar optimización (tiempo mínimo)", disabled=not st.session_state.get("validado")):
            df, msg = asignar_equipos(
                st.session_state.df_nadadores, st.session_state.df_categorias, tam, min_f, modo="min_total"
            )
            mostrar_resultado(df, msg)
    else:
        tam = st.number_input("Cantidad de nadadores por equipo", min_value=2, value=10, disabled=True)
        min_f = st.number_input("Mínimo de mujeres por equipo", min_value=1, max_value=tam, value=2, disabled=True)
        st.button("🚀 Ejecutar optimización (tiempo mínimo)", disabled=True)

# ---------- Pestaña 3: balancear ----------
with tabs[2]:
    st.header("⚖️ Balancear equipos")
    st.info(
        "Forma equipos balanceados: minimiza la diferencia de tiempo entre los equipos. Ideal para prácticas, recreación o competencias internas justas."
    )
    if st.session_state.get("validado"):
        tam = st.number_input("Cantidad de nadadores por equipo", min_value=2, value=10, key="tam_bal")
        min_f = st.number_input("Mínimo de mujeres por equipo", min_value=1, max_value=tam, value=2, key="minf_bal")
        if st.button("🚀 Ejecutar optimización (balance)", disabled=not st.session_state.get("validado")):
            df, msg = asignar_equipos(
                st.session_state.df_nadadores, st.session_state.df_categorias, tam, min_f, modo="balance"
            )
            mostrar_resultado(df, msg)
    else:
        tam = st.number_input("Cantidad de nadadores por equipo", min_value=2, value=10, key="tam_bal", disabled=True)
        min_f = st.number_input(
            "Mínimo de mujeres por equipo", min_value=1, max_value=tam, value=2, key="minf_bal", disabled=True
        )
        st.button("🚀 Ejecutar optimización (balance)", disabled=True)

# ---------- Pestaña 4: por categoría ----------
with tabs[3]:
    st.header("🧩 Fijar cantidad de equipos por categoría")
    st.info(
        "En esta sección podés especificar cuántos equipos querés formar por cada categoría. La app intentará cumplir esas cantidades (si es posible) y luego distribuir el resto de nadadores de la forma más óptima posible."
    )
    if st.session_state.get("validado"):
        st.write("Define cuántos equipos querés formar por cada categoría:")
        df_cats = st.session_state.df_categorias[["Categoria"]].copy()
        df_cats["Equipos"] = 0
        df_cats = st.data_editor(df_cats, num_rows="fixed", key="equipos_por_categoria")

        tam = st.number_input("Cantidad de nadadores por equipo", min_value=2, value=10, key="tam_cat")
        min_f = st.number_input("Mínimo de mujeres por equipo", min_value=1, max_value=tam, value=2, key="minf_cat")

        if st.button("🚀 Ejecutar optimización por categoría", disabled=not st.session_state.get("validado")):
            equipos_categoria = {
                row["Categoria"]: int(row["Equipos"]) for _, row in df_cats.iterrows() if int(row["Equipos"]) > 0
            }

            df_nad = st.session_state.df_nadadores.copy()
            df_cat = st.session_state.df_categorias.copy()
            cat_bounds = {row["Categoria"]: (row["min"], row["max"]) for _, row in df_cat.iterrows()}

            resultado_final = []
            if "ID" not in df_nad.columns:
                df_nad["ID"] = range(len(df_nad))
            restantes = df_nad.copy()
            equipo_id = 1
            error = False
            equipos_armados = {cat: 0 for cat in equipos_categoria.keys()}
            usados_ids = set()
            for cat, cantidad in equipos_categoria.items():
                min_age, max_age = cat_bounds[cat]
                for _ in range(cantidad):
                    candidatos = restantes[~restantes["ID"].isin(usados_ids)].copy()
                    puede_formar, mensaje = puede_formar_equipo(candidatos, tam, min_f, min_age, max_age)
                    if not puede_formar:
                        error = True
                        st.error(f"No se pudo formar un equipo válido para la categoría {cat}: {mensaje}")
                        break
                    df_temp, msg = asignar_equipos(
                        candidatos,
                        df_cat,
                        tam,
                        min_f,
                        modo="min_total",
                        equipos_a_formar=1,
                        categoria_fija=(min_age, max_age, cat),
                        drop_id=False,
                    )
                    if df_temp.empty or (df_temp["Categoria"].iloc[0] != cat):
                        error = True
                        st.error(f"No se pudo formar un equipo válido para la categoría {cat}.")
                        break
                    else:
                        df_temp["Equipo"] = equipo_id
                        resultado_final.append(df_temp)
                        nuevos_usados = set(df_temp["ID"])
                        usados_ids.update(nuevos_usados)
                        equipo_id += 1
                        equipos_armados[cat] += 1
                if error:
                    break

            restantes_finales = restantes[~restantes["ID"].isin(usados_ids)].copy()
            if not error and len(restantes_finales) >= tam:
                df_extra, msg = asignar_equipos(
                    restantes_finales,
                    df_cat,
                    tam,
                    min_f,
                    modo="min_total",
                    equipos_a_formar=(len(restantes_finales) // tam),
                    drop_id=False,
                )
                if not df_extra.empty:
                    df_extra["Equipo"] += equipo_id - 1
                    resultado_final.append(df_extra)

            if resultado_final and not error:
                df_out = pd.concat(resultado_final, ignore_index=True)
                if "ID" in df_out.columns:
                    df_out.drop(columns=["ID"], inplace=True)
                mostrar_resultado(df_out, "✅ Optimización completa con equipos por categoría.")
                total_armados = sum(equipos_armados.values())
                nadadores_fuera = len(st.session_state.df_nadadores) - len(df_out)
                st.info(
                    f"Resumen: Se armaron {total_armados} equipos por categoría. Quedaron {nadadores_fuera} nadadores fuera."
                )
    else:
        df_cats = (
            st.session_state.df_categorias[["Categoria"]].copy()
            if "df_categorias" in st.session_state
            else pd.DataFrame(columns=["Categoria"])
        )
        df_cats["Equipos"] = 0
        st.data_editor(df_cats, num_rows="fixed", key="equipos_por_categoria", disabled=True)
        st.number_input("Cantidad de nadadores por equipo", min_value=2, value=10, key="tam_cat", disabled=True)
        st.number_input(
            "Mínimo de mujeres por equipo", min_value=1, max_value=10, value=2, key="minf_cat", disabled=True
        )
        st.button("🚀 Ejecutar optimización por categoría", disabled=True)
