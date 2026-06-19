"""
Sistema de nichos para IA al Día.
Rota diariamente: cada día usa un nicho distinto para máxima variedad.
"""
from datetime import date

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

# Orden de rotación diaria
ROTATION_ORDER = [
    "ia_noticias",
    "finanzas",
    "negocios_digitales",
    "productividad_ia",
    "cripto_inversiones",
    "ia_noticias",
    "productividad_ia",  # IA 2x por semana para mantener marca
]

def get_niche(lang_code="es"):
    """Retorna el nicho del día. Inglés siempre usa ia_noticias."""
    if lang_code == "en":
        return "ia_noticias", NICHES["ia_noticias"]
    day_of_year = date.today().timetuple().tm_yday
    key = ROTATION_ORDER[day_of_year % len(ROTATION_ORDER)]
    return key, NICHES[key]

def get_niche_by_key(key):
    return NICHES.get(key, NICHES["ia_noticias"])
