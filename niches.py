"""
Sistema de nichos para IA al Día — CANAL 100% DEPORTES.
  Jun 11 – Jul 19 2026: Mundial 2026 (mundial_2026)
  Jul 20 en adelante:   Deportes (deportes) — permanente
"""
from datetime import date

# Mundial 2026: 11 junio – 19 julio 2026
_MUNDIAL_START      = date(2026, 6, 11)
_MUNDIAL_END        = date(2026, 7, 19)

# Puente post-Mundial: transferencias + pretemporada European leagues
_POST_MUNDIAL_START = date(2026, 7, 20)

# Champions League 2026-27: inicia fase de grupos ~16 sep
_UCL_START          = date(2026, 9, 16)

NICHES = {
    "ia_noticias": {
        "nombre": "IA al Día",
        "rss_feeds": [
            "https://venturebeat.com/category/ai/feed/",
            "https://techcrunch.com/category/artificial-intelligence/feed/",
            "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
            "https://feeds.arstechnica.com/arstechnica/technology-lab",
        ],
        "pexels_queries": [
            "man talking camera professional",
            "woman speaking camera presenter",
            "journalist interview camera portrait",
            "news anchor speaking portrait",
            "man explaining camera close up",
        ],
        "tags": ["ia 2026","inteligencia artificial noticias","chatgpt novedades","ia herramientas",
                 "ia al dia","shorts ia","tecnologia latina","ia trabajo","futuro ia",
                 "automatizacion","ia español","ia impacto"],
        "hashtags": "#Shorts #IA #InteligenciaArtificial #ChatGPT #Tecnologia #IaAlDia",
        "prompt_nicho": """Eres el periodista de IA más influyente de América Latina.
TEMA: Noticias de inteligencia artificial, modelos de lenguaje, automatización, big tech.
ENFOQUE: Cómo la IA afecta empleos, empresas y vida diaria en LATAM.
GANCHO IDEAS:
• "Acaban de confirmar que [empresa] despidió [N] personas por IA"
• "El nuevo modelo de [empresa] hace esto y nadie en LATAM lo sabía"
• "[N]% de los trabajos en [sector] van a desaparecer según [fuente real]"
""",
        "fallback": {
            "titulo": "IA 2026: lo que nadie te cuenta 🤖",
            "guion": "Nadie te dijo esto sobre la inteligencia artificial. El 40% de los empleos actuales van a cambiar en los próximos 3 años según la ONU. Una empresa que conozco despidió 30 personas el mes pasado. Contrató un solo modelo de IA. Lo que nadie menciona es que aún puedes adaptarte. Pero sí es tarde para ignorarlo. La pregunta no es si te va a afectar. La pregunta es qué vas a hacer antes de que llegue. Sígueme para más IA al Día.",
            "hook_texto": "Nadie te dijo esto sobre la IA",
            "descripcion": "Todo sobre inteligencia artificial en 2026. #Shorts #IA #InteligenciaArtificial #IaAlDia",
        },
    },

    "finanzas": {
        "nombre": "Finanzas al Día",
        "rss_feeds": [
            "https://feeds.feedburner.com/entrepreneur/latest",
            "https://www.cnbc.com/id/10000664/device/rss/rss.html",
            "https://feeds.bloomberg.com/markets/news.rss",
            "https://www.businessinsider.com/rss",
        ],
        "pexels_queries": [
            "money cash counting hands close up",
            "business woman office success portrait",
            "person phone stock market portrait",
            "piggy bank savings money portrait",
            "man laptop work home office portrait",
        ],
        "tags": ["finanzas personales","como ahorrar dinero","inversiones 2026","dinero latam",
                 "libertad financiera","ahorro","inversion","ganar dinero","finanzas shorts",
                 "educacion financiera","plata","presupuesto personal"],
        "hashtags": "#Shorts #Finanzas #Dinero #Inversion #LibertadFinanciera #FinanzasPersonales",
        "prompt_nicho": """Eres el experto en finanzas personales más seguido de América Latina.
TEMA: Finanzas personales, ahorro, inversiones, inflación, salarios, cómo ganar más dinero.
ENFOQUE: Consejos accionables con cifras reales para personas de clase media latinoamericana.
GANCHO IDEAS:
• "Si tienes $[N] pesos/dólares y no haces esto, los estás perdiendo"
• "[N]% de latinoamericanos no saben que su banco les cobra esto"
• "Con $[N] al mes puedes tener [resultado concreto] en [N] años"
• "La inflación en [país] ya subió [N]%. Esto es lo que debes hacer HOY"
""",
        "fallback": {
            "titulo": "El error de dinero que comete el 80% 💸",
            "guion": "El 80% de los latinoamericanos comete este error con su dinero cada mes. Lo guardan en cuenta corriente. La inflación promedio en la región es del 8% anual. Si tienes 5 millones de pesos parados, pierdes 400 mil pesos al año sin hacer nada. Lo que sí puedes hacer hoy: abrir un fondo de inversión conservador. Rendimiento promedio: entre 6 y 12% anual. En 10 años, esos 5 millones se convierten en 9 millones. La diferencia es una sola decisión. Sígueme para más finanzas al día.",
            "hook_texto": "El 80% comete este error con su dinero",
            "descripcion": "Finanzas personales para latinoamericanos con datos reales. #Shorts #Finanzas #Dinero #Ahorro",
        },
    },

    "negocios_digitales": {
        "nombre": "Negocios Digitales",
        "rss_feeds": [
            "https://feeds.feedburner.com/entrepreneur/latest",
            "https://techcrunch.com/feed/",
            "https://www.producthunt.com/feed",
            "https://feeds.feedburner.com/SmartPassiveIncome",
        ],
        "pexels_queries": [
            "entrepreneur working laptop coffee portrait",
            "startup team meeting office portrait",
            "ecommerce online shopping phone portrait",
            "young person success business portrait",
            "man phone digital marketing portrait",
        ],
        "tags": ["negocios digitales","emprendimiento latam","ganar dinero online","dropshipping 2026",
                 "ecommerce","negocio desde casa","freelance","marketing digital","negocio online",
                 "emprendedor","como emprender","shopify"],
        "hashtags": "#Shorts #Negocios #Emprendimiento #NegociosDigitales #GanarDinero #Ecommerce",
        "prompt_nicho": """Eres el emprendedor digital más exitoso de América Latina.
TEMA: Negocios online, e-commerce, dropshipping, freelance, marketing digital, startups.
ENFOQUE: Casos reales de personas que ganaron dinero online en LATAM, con cifras y pasos concretos.
GANCHO IDEAS:
• "Este negocio online generó $[N] en [N] meses desde [país LATAM]"
• "Hay [N] personas en LATAM ganando $[N] al mes haciendo esto desde casa"
• "El negocio que más crece en [país] en 2026 y nadie lo está aprovechando"
• "Con $[N] de inversión este negocio devuelve $[N] al mes"
""",
        "fallback": {
            "titulo": "Negocio digital que funciona en Chile 2026 💼",
            "guion": "Hay personas en Chile ganando 3 millones de pesos al mes desde su casa. El modelo es dropshipping con productos locales. Invierten 200 mil pesos al inicio. En 60 días ya recuperaron la inversión. Lo que hacen diferente: venden en redes sociales, no en marketplaces. El margen promedio es del 40%. La plataforma más usada es Shopify. El producto que más se vende en Chile ahora son artículos de hogar con envío express. Esto no requiere bodega ni inventario. Solo tiempo y un celular. Sígueme para más negocios digitales.",
            "hook_texto": "Personas en LATAM ganando esto desde casa",
            "descripcion": "Negocios digitales que funcionan en América Latina con cifras reales. #Shorts #Negocios #Dropshipping",
        },
    },

    "cripto_inversiones": {
        "nombre": "Cripto al Día",
        "rss_feeds": [
            "https://cointelegraph.com/rss",
            "https://coindesk.com/arc/outboundfeeds/rss/",
            "https://decrypt.co/feed",
            "https://www.coindesk.com/feed",
        ],
        "pexels_queries": [
            "bitcoin gold coin portrait close",
            "man phone trading crypto portrait",
            "stock market chart screen portrait",
            "digital money blockchain technology portrait",
            "investor laptop charts portrait",
        ],
        "tags": ["bitcoin 2026","cripto latam","ethereum precio","criptomonedas","defi",
                 "bitcoin precio hoy","cripto shorts","inversion cripto","web3","altcoins",
                 "cripto noticias","btc"],
        "hashtags": "#Shorts #Bitcoin #Cripto #Criptomonedas #BTC #Ethereum #Inversion",
        "prompt_nicho": """Eres el analista de criptomonedas más confiable de América Latina.
TEMA: Bitcoin, Ethereum, altcoins, DeFi, precios, regulaciones, adopción en LATAM.
ENFOQUE: Datos de precio reales, movimientos de mercado, cómo afecta a inversores latinoamericanos.
IMPORTANTE: Siempre incluye descargo: "Esto no es consejo financiero."
GANCHO IDEAS:
• "Bitcoin acaba de [subir/bajar] a $[N]. Esto es lo que significa para ti"
• "[País LATAM] acaba de [regular/adoptar] cripto. Esto cambia todo"
• "El [N]% de los latinoamericanos ya usa cripto para protegerse de la inflación"
• "Esta altcoin subió [N]% en [N] días. Aquí los datos reales"
""",
        "fallback": {
            "titulo": "Bitcoin 2026: lo que nadie te explica ₿",
            "guion": "Bitcoin está cambiando cómo los latinoamericanos guardan su dinero. En países con inflación alta como Argentina y Venezuela, más del 15% de la población ya usa cripto. El motivo es simple: el dólar es difícil de conseguir. Bitcoin es accesible desde el celular. El precio actual ronda los 90 mil dólares. La tendencia de los últimos 4 años muestra mínimos cada vez más altos. Pero hay riesgo: la volatilidad puede bajar 30% en semanas. Diversifica, nunca pongas más del 10% de tus ahorros en cripto. Esto no es consejo financiero. Sígueme para más cripto al día.",
            "hook_texto": "Bitcoin está cambiando LATAM y pocos lo ven",
            "descripcion": "Criptomonedas con datos reales para América Latina. No es consejo financiero. #Shorts #Bitcoin #Cripto",
        },
    },

    "deportes": {
        "nombre": "Deportes al Día",
        "rss_feeds": [
            "https://www.espn.com/espn/rss/news",
            "https://www.marca.com/rss/portada.xml",
            "https://www.foxsports.com/rss-feeds",
            "https://feeds.bbci.co.uk/sport/football/rss.xml",
            "https://www.mundodeportivo.com/rss/futbol/mundial.xml",
            "https://rss.nytimes.com/services/xml/rss/nyt/Soccer.xml",
        ],
        "pexels_queries": [
            "football fans flags celebration stadium crowd",
            "soccer supporters cheering portrait",
            "sports fan face paint national colors portrait",
            "football stadium crowd atmosphere",
            "fans celebrating goal crowd portrait",
        ],
        "tags": ["deportes 2026","futbol latam","champions league 2026","transferencias futbol",
                 "deportes shorts","deporte viral","premier league","seleccion nacional",
                 "fichajes futbol","highlights futbol","gol viral","futbol shorts",
                 "champions league","laliga","futbol europeo"],
        "hashtags": "#Deportes #Futbol #FutbolLatam #Shorts #Mundial2026",
        "prompt_nicho": """Eres el periodista deportivo más riguroso y seguido de América Latina.
CONTEXTO ACTUAL (julio 2026): Mundial 2026 en cuartos/semis/final + mercado de pases abierto.
TEMA: Fútbol — Mundial 2026, transferencias, Champions League, resultados, estadísticas reales.
ENFOQUE: Hechos concretos con contexto histórico. No resúmenes, sino análisis con datos.
ESTILO OBLIGATORIO:
• Frases de 12-20 palabras. Fluidas, no telegráficas.
• Cada oración aporta un dato nuevo: minuto, nombre, cifra, récord, antecedente.
• Prohibido: "Tendencia", "explotó en redes", "viral", "enloquece", "nadie puede creer".
ANTI-ALUCINACIÓN — CRÍTICO:
• SOLO usa datos presentes en los titulares RSS o en el VIRAL_CONTEXT proporcionado.
• NUNCA inventes goles, asistencias, minutos, tarjetas o resultados no confirmados.
• Si no tienes el dato exacto, omitilo — no lo inventes ni estimes.
• Si el VIRAL_CONTEXT incluye datos específicos, PRIORIZALOS y úsalos textualmente.
GANCHOS PRIORITARIOS:
• "[Jugador] MARCA doblete y [Selección] avanza al [fase] del Mundial"
• "[Club] FICHA a [Jugador]: el precio que nadie esperaba — [cifra real]"
• "Champions League 2026-27: el grupo más difícil ya está confirmado"
TONO: Autoridad periodística. Informativo, preciso, con el ritmo de quien sabe más que todos.
""",
        "fallback": {
            "titulo": "La noticia deportiva que sacude LATAM hoy ⚽",
            "guion": "Hay una noticia deportiva que nadie esperaba esta semana. En la Champions League, el VAR volvió a ser el protagonista de la polémica. Tres decisiones en un solo partido. Una de ellas anuló un gol en el minuto 89. El entrenador salió furioso a la prensa y dijo algo que nadie esperaba escuchar. Los hinchas en redes sociales hicieron explotar el tema en minutos. Más de 2 millones de menciones en 4 horas. Lo que nadie dice es que esta es la tercera vez en la temporada que el mismo árbitro dirige ese equipo. ¿Coincidencia? Los números dicen otra cosa. Sígueme para deportes al día.",
            "hook_texto": "La noticia deportiva que nadie esperaba",
            "descripcion": "Noticias deportivas con datos reales para América Latina. #Shorts #Deportes #Futbol",
        },
    },

    "politica_latam": {
        "nombre": "Política al Día",
        "rss_feeds": [
            "https://feeds.bbci.co.uk/mundo/rss.xml",
            "https://feeds.reuters.com/reuters/MXinternationalNews",
            "https://www.infobae.com/feeds/rss/politica/",
            "https://www.france24.com/es/rss",
            "https://www.dw.com/es/rss",
        ],
        "pexels_queries": [
            "politician speaking microphone portrait",
            "government congress building portrait",
            "protest march crowd portrait",
            "president press conference portrait",
            "election voting booth portrait",
        ],
        "tags": ["politica latam","noticias hoy","elecciones 2026","gobierno latinoamerica",
                 "politica shorts","congreso","presidente noticias","economia politica",
                 "corrupcion","democracia latam","relaciones internacionales","política"],
        "hashtags": "#Shorts #Politica #NoticiasLatam #Gobierno #Elecciones #LATAM",
        "prompt_nicho": """Eres el analista político más claro y directo de América Latina.
TEMA: Política latinoamericana, gobiernos, elecciones, economía política, relaciones internacionales.
ENFOQUE: Explicar qué pasó, por qué importa, y cómo afecta al ciudadano común. Sin partido, solo datos.
GANCHO IDEAS:
• "El presidente de [país] acaba de anunciar [decisión] y esto es lo que significa para ti"
• "Lo que nadie te explica sobre [crisis/decisión política] en [país]"
• "[País] en [situación crítica]: los 3 datos que necesitas entender"
• "Confirmado: [hecho político] cambia el escenario en [país/región]"
TONO: Analítico pero accesible. Sin sesgo. Explica como si tu audiencia no sigue política habitualmente.
""",
        "fallback": {
            "titulo": "La decisión política que afecta a millones en LATAM 🌎",
            "guion": "Una decisión política en América Latina afecta a millones esta semana y pocos la están explicando bien. Se trata de cambios en la política económica de uno de los países más grandes de la región. El dólar reaccionó. Los mercados también. Y la ciudadanía siente el efecto en el precio de los alimentos. Lo que los medios no explican es el contexto: esta decisión viene de una negociación que lleva 8 meses. No fue de un día para otro. Hay tres actores clave que nadie menciona. Y cada uno tiene un interés diferente. Sígueme para política al día sin filtros.",
            "hook_texto": "Esta decisión política afecta a millones y nadie la explica bien",
            "descripcion": "Análisis político latinoamericano con datos reales. #Shorts #Politica #LATAM",
        },
    },

    "entretenimiento": {
        "nombre": "Entretenimiento al Día",
        "rss_feeds": [
            "https://www.eonline.com/syndication/feeds/rssfeeds/espanol.xml",
            "https://www.billboard.com/feed/",
            "https://trends.google.com/trending/rss?geo=MX",
            "https://trends.google.com/trending/rss?geo=AR",
            "https://trends.google.com/trending/rss?geo=CO",
        ],
        "pexels_queries": [
            "celebrity red carpet portrait",
            "music concert stage portrait",
            "actress movie premiere portrait",
            "singer microphone performance portrait",
            "influencer content creator portrait",
        ],
        "tags": ["entretenimiento latam","chismes famosos","celebrities 2026","musica viral",
                 "pelea famosos","netflix serie","taylor swift","bad bunny noticias",
                 "farandula latam","reality show","actor noticias","viral shorts"],
        "hashtags": "#Shorts #Entretenimiento #Chismes #Celebrities #Farandula #Viral",
        "prompt_nicho": """Eres el periodista de entretenimiento más viral de habla hispana, con un enfoque ÚNICO: usas IA para analizar, predecir y revelar lo que nadie más detectó.
TEMA: Chismes de famosos, música viral, series, peleas entre celebrities, reality shows — SIEMPRE con el ángulo de qué detectó o predijo la IA.
ENFOQUE: La IA como lente que revela lo oculto. No solo reportas el chisme — la IA lo analizó, lo predijo, o detectó algo que nadie más vio.
GANCHO IDEAS:
• "La IA analizó la letra de [artista] y encontró esto que nadie vio 😱"
• "Gemini predijo el drama entre [A] y [B] hace [N] semanas. Tenía razón 🤯"
• "La IA detectó que [famoso] eliminó [N] posts en [N] horas: esto significa algo 😱"
• "[Famoso] reaccionó así cuando le mostraron lo que dijo la IA sobre él"
ARTISTAS/CELEBRIDADES LATAM prioritarios: Shakira, Bad Bunny, Karol G, Peso Pluma, Bizarrap, Maluma, J Balvin, Rosalía, Anuel, Nicki Nicole.
TONO: Urgente, como si acabaras de descubrir algo. La IA es tu fuente exclusiva que nadie más tiene.
""",
        "fallback": {
            "titulo": "La IA detectó esto en la canción de Bad Bunny 🤯",
            "guion": "Pasé la última canción de Bad Bunny por análisis de inteligencia artificial y lo que encontró nadie lo esperaba. La IA detectó 3 referencias ocultas que pasan desapercibidas al oído humano. Una de ellas apunta directamente a alguien del círculo cercano del artista. Hay una frecuencia en la producción que se repite exactamente en su canción más polémica de 2024. ¿Coincidencia o mensaje? Las redes ya están hablando. Más de 2 millones de reproducciones en 6 horas. El equipo del artista no ha comentado nada todavía. Sígueme para entretenimiento con IA al día.",
            "hook_texto": "La IA encontró esto en la canción",
            "descripcion": "IA analiza el entretenimiento y chismes de LATAM con datos reales. #Shorts #Chismes #IA #Entretenimiento #BadBunny",
        },
    },

    "mundial_2026": {
        "nombre": "Mundial 2026",
        "rss_feeds": [
            "https://www.espn.com/espn/rss/news",
            "https://www.marca.com/rss/portada.xml",
            "https://feeds.bbci.co.uk/sport/football/rss.xml",
            "https://www.foxsports.com/rss-feeds",
            "https://www.mundodeportivo.com/rss/futbol/mundial.xml",
            "https://rss.nytimes.com/services/xml/rss/nyt/Soccer.xml",
        ],
        "pexels_queries": [
            "football fans flags waving stadium crowd",
            "world cup fans face paint celebration portrait",
            "soccer supporters national flag cheering",
            "football fans singing crowd stadium atmosphere",
            "fans celebrating goal crowd portrait colorful",
        ],
        "tags": ["mundial 2026","world cup 2026","copa del mundo","goles mundial",
                 "futbol mundial","shorts mundial","resultados mundial",
                 "cuartos de final","semifinal mundial","messi mundial",
                 "futbol viral","highlights","gol del dia","futbol shorts"],
        "hashtags": "#Mundial2026 #Futbol #WorldCup #CopaDelMundo #Shorts",
        "prompt_nicho": """Eres el mejor periodista del Mundial 2026. Narrás con precisión y profundidad.
TEMA: Jugadas, goles, polémicas, datos históricos y contexto del Mundial 2026 (USA, Canadá, México).
FORMATO OBLIGATORIO: Narración en audio — describís cada momento con detalle concreto, sin imágenes.
ESTILO OBLIGATORIO:
• Frases de 14-22 palabras. Cada oración suma información nueva.
• Usá números reales: minutos, estadísticas históricas, nombres completos, posiciones en la tabla.
• Prohibido: "Tendencia", "explotó", "viral", "las redes enloquecen", "nadie puede creer".
• Nunca digas "como viste" o "en el video" — el oyente no tiene imágenes.
ANTI-ALUCINACIÓN — CRÍTICO:
• SOLO usa datos presentes en los titulares RSS o en el VIRAL_CONTEXT proporcionado.
• NUNCA inventes goles, asistencias, minutos, tarjetas o resultados no confirmados.
• Si no tienes el dato exacto, omitilo — no lo inventes ni estimes.
• Si el VIRAL_CONTEXT incluye datos específicos (marcador, goleadores, minutos), PRIORIZALOS y úsalos textualmente.
GANCHO IDEAS (con datos, no adjetivos):
• "Minuto [N]. [Jugador] recibió el balón en [posición] y [acción exacta] — es el [N]º gol de su carrera en Mundiales."
• "[Selección] llegó al partido con [dato de contexto] — y lo que pasó en el área en el minuto [N] explica por qué."
• "[Jugador] anotó en el [N]º gol de su carrera en Mundiales — solo [N] jugadores lo lograron antes."
TONO: Periodista con autoridad y pasión contenida. Informativo y cinematográfico al mismo tiempo.
""",
        "fallback": {
            "titulo": "El gol que paró al mundo en el Mundial 2026 ⚽🌍",
            "guion": "Cuarenta y dos mil personas en silencio. Después, un estallido que se escuchó a tres cuadras del estadio. Así fue el gol que paró al mundo entero en el Mundial 2026. El jugador recibió el balón de espaldas, giró 180 grados, y definió al ángulo opuesto sin mirar. El arquero no se movió. Nadie se movió. El dato que ningún medio menciona: fue el mismo movimiento exacto que hizo en semifinales hace cuatro años. Como si lo hubiera ensayado toda su vida para este momento. Las redes colapsaron en ocho minutos. Cuarenta millones de menciones en una hora. Sígueme y te cuento todo lo que pasa en el Mundial antes que nadie.",
            "hook_texto": "Cuarenta y dos mil personas en silencio",
            "descripcion": "Los goles, polémicas y datos del Mundial 2026 narrados como nunca. #Shorts #Mundial2026 #WorldCup #Futbol",
        },
    },

    "productividad_ia": {
        "nombre": "Productividad con IA",
        "rss_feeds": [
            "https://zapier.com/blog/feeds/latest/",
            "https://www.makeuseof.com/feed/",
            "https://lifehacker.com/rss",
            "https://techcrunch.com/category/artificial-intelligence/feed/",
        ],
        "pexels_queries": [
            "person productivity laptop focused portrait",
            "woman working organized desk portrait",
            "man phone apps tools portrait",
            "student studying focused portrait",
            "professional multitasking office portrait",
        ],
        "tags": ["productividad ia","herramientas ia gratis","chatgpt trucos","ia para trabajar",
                 "automatizar trabajo","ia productividad","prompts chatgpt","ia gratis 2026",
                 "shortcuts ia","trabajar menos ia","ia freelance","claude ia"],
        "hashtags": "#Shorts #Productividad #IA #ChatGPT #HerramientasIA #Automatizacion #Trabajo",
        "prompt_nicho": """Eres el experto en productividad con IA más práctico de habla hispana.
TEMA: Herramientas IA gratuitas y de pago, prompts, automatizaciones, trucos para trabajar menos.
ENFOQUE: Demos concretos de herramientas reales, con tiempo ahorrado y resultados medibles.
GANCHO IDEAS:
• "Esta herramienta IA hace en 3 minutos lo que te toma 3 horas"
• "Los [N] prompts de ChatGPT que usan los freelancers top de LATAM"
• "Gané [N] horas esta semana con estas [N] herramientas IA gratuitas"
• "Esta IA acaba de reemplazar a [rol] en muchas empresas. Aquí cómo usarla tú"
""",
        "fallback": {
            "titulo": "3 herramientas IA que te ahorran 10 horas/semana ⚡",
            "guion": "Hay tres herramientas IA que los freelancers top de LATAM usan cada día y que son gratuitas. Primera: ChatGPT para redactar emails y propuestas en 2 minutos. Segunda: Canva IA para crear diseños profesionales sin experiencia. Tercera: Otter AI para transcribir reuniones automáticamente. En promedio ahorran 10 horas a la semana. Eso son 40 horas al mes. Un mes de trabajo extra que puedes usar para otro cliente o para descansar. Las tres tienen plan gratuito. El único costo es aprender a usarlas. Sígueme para más herramientas IA al día.",
            "hook_texto": "Estas 3 herramientas IA ahorran 10 horas",
            "descripcion": "Herramientas IA gratuitas para ser más productivo en 2026. #Shorts #IA #Productividad #ChatGPT",
        },
    },
}

def get_niche(lang_code="es", learned_weights: dict = None):
    """
    Canal 100% deportes.
    Durante el Mundial (Jun 11 – Jul 19 2026) usa mundial_2026.
    El resto del tiempo siempre deportes.
    """
    today = date.today()
    if _MUNDIAL_START <= today <= _MUNDIAL_END:
        return "mundial_2026", NICHES["mundial_2026"]
    return "deportes", NICHES["deportes"]

def get_niche_by_key(key):
    return NICHES.get(key, NICHES["ia_noticias"])
