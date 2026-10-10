"""
Detección de inyección de prompt por reglas, compartida por el pipeline de
extracción y por el asistente.

Son reglas deterministas: no dependen de que un modelo "se acuerde" de
detectar el ataque. El pipeline las aplica al texto de cada extracto y el
asistente a cada pregunta.
"""
import re
import unicodedata


# ───────────────────────── 1. Sanear ─────────────────────────

def sanear(texto, max_largo=None):
    """
    Texto de una sola línea, sin caracteres invisibles.

    NFKC pliega variantes Unicode (letras de ancho completo, ligaduras) a su
    forma corriente. Los caracteres de formato (Cf: ancho cero, marcas bidi)
    se eliminan porque sirven para esconder palabras a los filtros; los de
    control (Cc, incluidos los saltos de línea) se vuelven espacios.
    """
    if not isinstance(texto, str):
        return ""
    texto = unicodedata.normalize("NFKC", texto)
    limpio = []
    for caracter in texto:
        categoria = unicodedata.category(caracter)
        if categoria == "Cf":
            continue
        limpio.append(" " if categoria == "Cc" else caracter)
    texto = re.sub(r"\s+", " ", "".join(limpio)).strip()
    return texto[:max_largo] if max_largo else texto


def plano(texto):
    """Minúsculas y sin tildes, solo para comparar contra patrones."""
    texto = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


# ───────────────────────── 3. Reglas de inyección ─────────────────────────

_IDIOMAS = r"(?:ingles|english|frances|aleman|portugues|italiano|chino|japones|ruso|otro idioma)"

_PATRONES_INYECCION = [re.compile(p) for p in (
    # español
    r"\bignor\w*\s+(?:\w+\s+){0,4}(?:instruccion\w*|regla\w*|indicacion\w*|prompt|orden\w*|anterior\w*)",
    r"\bolvid\w*\s+(?:\w+\s+){0,4}(?:instruccion\w*|regla\w*|indicacion\w*|anterior\w*|todo|lo que)",
    r"\b(?:prompt|instrucciones)\s+(?:del\s+)?(?:sistema|system)\b",
    r"\bsystem\s*prompt\b",
    r"\b(?:revela|muestra|dime|imprime|repite|copia|escribe)\w*\s+(?:\w+\s+){0,4}(?:prompt|instrucciones|reglas|configuracion)\b",
    r"\b(?:a partir de ahora|de ahora en adelante|desde ahora en adelante)\b",
    r"\b(?:ahora eres|ahora seras|eres ahora|actua como|actuar como|comportate como|haz de cuenta)\b",
    r"\b(?:finge|pretende|simula)\s+(?:ser|que)\b",
    rf"\b(?:responde|contesta|habla|escribe)\w*\s+(?:(?:solo|solamente|unicamente|siempre|ahora)\s+)?en\s+{_IDIOMAS}\b",
    r"\b(?:nuevas instrucciones|instrucciones nuevas|nueva tarea|cambia de rol|cambio de rol|cambia tu rol)\b",
    r"\b(?:sin restricciones|sin limites|sin filtros|sin reglas|no tienes reglas|modo desarrollador|modo dan|jailbreak)\b",
    # Cualquier alusión a las reglas del propio asistente. Una pregunta sobre
    # finanzas personales no tiene por qué mencionarlas.
    r"\b(?:tus|sus)\s+(?:propias\s+)?(?:reglas|instrucciones|indicaciones|directrices|restricciones)\b",
    r"\b(?:tu|su)\s+(?:configuracion|programacion|prompt)\b",
    # inglés
    r"\b(?:ignore|disregard|forget|override)\s+(?:\w+\s+){0,4}(?:instructions?|rules|prompt|previous|above)\b",
    r"\b(?:you are now|act as|pretend to be|from now on|developer mode|dan mode|no restrictions)\b",
    r"\b(?:reveal|show|print|repeat)\s+(?:\w+\s+){0,3}(?:prompt|instructions|system)\b",
    # marcas de plantilla, roles y código
    r"<\|[^|]*\|>",
    r"\[/?inst\]",
    r"<<\s*/?sys\s*>>",
    r"(?:^|\s)(?:system|assistant|sistema|asistente)\s*:",
    r"#{2,}\s*(?:system|instruction|sistema|instruccion)",
    r"\b(?:drop\s+table|union\s+select|delete\s+from|insert\s+into|rm\s+-rf|import\s+os|subprocess)\b",
    r"\b(?:eval|exec)\s*\(",
)]

# Detecta las mismas frases escritas con espacios o símbolos intercalados
# ("i g n o r a  l a s  i n s t r u c c i o n e s").
_COMPACTOS = (
    "ignoratodaslasinstrucciones", "ignoralasinstrucciones", "ignoralasreglas",
    "olvidatodaslasinstrucciones", "olvidalasinstrucciones", "systemprompt",
    "promptdelsistema", "ignorepreviousinstructions", "ignoreallpreviousinstructions",
    "ignoreallinstructions",
)


def detectar_inyeccion(texto):
    normalizado = plano(texto)
    if any(p.search(normalizado) for p in _PATRONES_INYECCION):
        return True
    compacto = re.sub(r"[^a-z]", "", normalizado)
    return any(c in compacto for c in _COMPACTOS)
