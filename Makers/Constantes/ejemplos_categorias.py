def EJEMPLOS_CATEGORIAS():
    """
    Base inicial (semilla) de ejemplos ya categorizados para el RAG del revisor.

    Son ejemplos sintéticos, sin datos de clientes. "contraparte" es el nombre
    que se conserva sin anonimizar: el destinatario en un egreso y el
    remitente en un ingreso.
    """
    return [
    # alimentacion
    {"tipo": "egreso", "contraparte": "Rappi", "entidad": None, "descripcion": "Pedido a domicilio de comida", "categoria": "alimentacion"},
    {"tipo": "egreso", "contraparte": "McDonald's", "entidad": "restaurante", "descripcion": "Compra de hamburguesa en restaurante", "categoria": "alimentacion"},
    {"tipo": "egreso", "contraparte": "Crepes & Waffles", "entidad": "restaurante", "descripcion": "Almuerzo en restaurante", "categoria": "alimentacion"},
    {"tipo": "egreso", "contraparte": "Juan Valdez", "entidad": "cafetería", "descripcion": "Café y pastel en cafetería", "categoria": "alimentacion"},
    {"tipo": "egreso", "contraparte": None, "entidad": "panadería", "descripcion": "Compra en panadería", "categoria": "alimentacion"},
    # transporte
    {"tipo": "egreso", "contraparte": "Uber", "entidad": None, "descripcion": "Viaje en Uber", "categoria": "transporte"},
    {"tipo": "egreso", "contraparte": "DiDi", "entidad": None, "descripcion": "Viaje en DiDi", "categoria": "transporte"},
    {"tipo": "egreso", "contraparte": "TransMilenio", "entidad": None, "descripcion": "Recarga tarjeta de transporte público", "categoria": "transporte"},
    {"tipo": "egreso", "contraparte": "Terpel", "entidad": "estación de servicio", "descripcion": "Tanqueo de gasolina", "categoria": "transporte"},
    {"tipo": "egreso", "contraparte": None, "entidad": "peaje", "descripcion": "Pago de peaje", "categoria": "transporte"},
    {"tipo": "egreso", "contraparte": "Avianca", "entidad": "aerolínea", "descripcion": "Compra de tiquete aéreo", "categoria": "transporte"},
    # entretenimiento
    {"tipo": "egreso", "contraparte": "Netflix", "entidad": None, "descripcion": "Suscripción mensual Netflix", "categoria": "entretenimiento"},
    {"tipo": "egreso", "contraparte": "Spotify", "entidad": None, "descripcion": "Suscripción de música Spotify", "categoria": "entretenimiento"},
    {"tipo": "egreso", "contraparte": "Cine Colombia", "entidad": "cine", "descripcion": "Boletas de cine", "categoria": "entretenimiento"},
    {"tipo": "egreso", "contraparte": "Steam", "entidad": None, "descripcion": "Compra de videojuego", "categoria": "entretenimiento"},
    {"tipo": "egreso", "contraparte": "Tuboleta", "entidad": None, "descripcion": "Entradas para concierto", "categoria": "entretenimiento"},
    # vivienda
    {"tipo": "egreso", "contraparte": None, "entidad": "inmobiliaria", "descripcion": "Pago de arriendo del apartamento", "categoria": "vivienda"},
    {"tipo": "egreso", "contraparte": None, "entidad": None, "descripcion": "Cuota de administración del conjunto residencial", "categoria": "vivienda"},
    {"tipo": "egreso", "contraparte": None, "entidad": "banco", "descripcion": "Cuota del crédito hipotecario", "categoria": "vivienda"},
    # salud
    {"tipo": "egreso", "contraparte": "Farmatodo", "entidad": "farmacia", "descripcion": "Compra de medicamentos", "categoria": "salud"},
    {"tipo": "egreso", "contraparte": "Cruz Verde", "entidad": "farmacia", "descripcion": "Compra en droguería", "categoria": "salud"},
    {"tipo": "egreso", "contraparte": None, "entidad": "clínica", "descripcion": "Consulta médica particular", "categoria": "salud"},
    {"tipo": "egreso", "contraparte": "Sura", "entidad": "EPS", "descripcion": "Pago de medicina prepagada", "categoria": "salud"},
    {"tipo": "egreso", "contraparte": None, "entidad": "odontología", "descripcion": "Limpieza dental", "categoria": "salud"},
    # educacion
    {"tipo": "egreso", "contraparte": "Universidad Nacional", "entidad": "universidad", "descripcion": "Pago de matrícula del semestre", "categoria": "educacion"},
    {"tipo": "egreso", "contraparte": "Platzi", "entidad": "plataforma educativa", "descripcion": "Suscripción anual de cursos en línea", "categoria": "educacion"},
    {"tipo": "egreso", "contraparte": None, "entidad": "colegio", "descripcion": "Pensión mensual del colegio", "categoria": "educacion"},
    {"tipo": "egreso", "contraparte": "Coursera", "entidad": None, "descripcion": "Pago de certificado de curso", "categoria": "educacion"},
    # compras
    {"tipo": "egreso", "contraparte": "Éxito", "entidad": "supermercado", "descripcion": "Compra en supermercado", "categoria": "compras"},
    {"tipo": "egreso", "contraparte": "D1", "entidad": "tienda", "descripcion": "Mercado en tienda de descuento", "categoria": "compras"},
    {"tipo": "egreso", "contraparte": "Falabella", "entidad": "tienda", "descripcion": "Compra de ropa", "categoria": "compras"},
    {"tipo": "egreso", "contraparte": "Amazon", "entidad": None, "descripcion": "Compra en línea de artículos", "categoria": "compras"},
    {"tipo": "egreso", "contraparte": "Mercado Libre", "entidad": None, "descripcion": "Compra en línea de celular", "categoria": "compras"},
    {"tipo": "egreso", "contraparte": "Homecenter", "entidad": "ferretería", "descripcion": "Compra de herramientas para el hogar", "categoria": "compras"},
    # servicios
    {"tipo": "egreso", "contraparte": "Claro", "entidad": None, "descripcion": "Pago plan de telefonía móvil", "categoria": "servicios"},
    {"tipo": "egreso", "contraparte": "EPM", "entidad": None, "descripcion": "Pago de factura de energía y agua", "categoria": "servicios"},
    {"tipo": "egreso", "contraparte": "ETB", "entidad": None, "descripcion": "Pago de internet del hogar", "categoria": "servicios"},
    {"tipo": "egreso", "contraparte": "Vanti", "entidad": None, "descripcion": "Pago de factura de gas natural", "categoria": "servicios"},
    {"tipo": "egreso", "contraparte": None, "entidad": "banco", "descripcion": "Cuota de manejo de la tarjeta", "categoria": "servicios"},
    # transferencia_persona
    {"tipo": "egreso", "contraparte": "Carlos Gómez", "entidad": None, "descripcion": "Transferencia por Nequi a Carlos Gómez", "categoria": "transferencia_persona"},
    {"tipo": "egreso", "contraparte": "Laura Martínez", "entidad": None, "descripcion": "Envío de dinero por Daviplata", "categoria": "transferencia_persona"},
    {"tipo": "ingreso", "contraparte": "Andrés Rojas", "entidad": None, "descripcion": "Transferencia recibida de Andrés Rojas", "categoria": "transferencia_persona"},
    {"tipo": "ingreso", "contraparte": "Sofía Herrera", "entidad": None, "descripcion": "Me devolvieron el dinero prestado", "categoria": "transferencia_persona"},
    # ingreso_laboral
    {"tipo": "ingreso", "contraparte": None, "entidad": None, "descripcion": "Pago de nómina", "categoria": "ingreso_laboral"},
    {"tipo": "ingreso", "contraparte": "Empresa XYZ S.A.S.", "entidad": None, "descripcion": "Salario mensual", "categoria": "ingreso_laboral"},
    {"tipo": "ingreso", "contraparte": "Consultores ABC", "entidad": None, "descripcion": "Pago de honorarios por servicios profesionales", "categoria": "ingreso_laboral"},
    {"tipo": "ingreso", "contraparte": None, "entidad": None, "descripcion": "Prima de servicios de junio", "categoria": "ingreso_laboral"},
    # otros
    {"tipo": "ingreso", "contraparte": None, "entidad": "banco", "descripcion": "Intereses de la cuenta de ahorros", "categoria": "otros"},
    {"tipo": "ingreso", "contraparte": "DIAN", "entidad": None, "descripcion": "Devolución de impuestos", "categoria": "otros"},
    {"tipo": "egreso", "contraparte": None, "entidad": "cajero", "descripcion": "Retiro en cajero automático", "categoria": "otros"},
    {"tipo": "egreso", "contraparte": "DIAN", "entidad": None, "descripcion": "Pago de impuesto de renta", "categoria": "otros"},
]
